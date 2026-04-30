"""Tests for RDF / PROV-O export of the SQLite KG (A1 §Audit Trail And KG)."""

from __future__ import annotations

from pathlib import Path

import pytest
from rdflib import Graph, URIRef
from rdflib.namespace import RDF

from zer0pa_materials.audit.kg import KGEdgeType, KGNodeType, MaterialsKG
from zer0pa_materials.audit.rdf_export import (
    export_kg_graph,
    export_kg_to_turtle,
    round_trip_validate,
)
from zer0pa_materials.ontology.emmo import (
    PROV_BASE_IRI,
    ZER0PA_EXTENSION_BASE_IRI,
)


def _seed_minimal_graph(kg: MaterialsKG) -> tuple[str, str]:
    """Build a small KG with one of each provenance-relevant node + a few edges."""
    a = kg.add_node("node:campaign:1", KGNodeType.Campaign, run_id="run:1")
    b = kg.add_node(
        "node:material:llzo", KGNodeType.CandidateMaterial,
        properties={"formula": "Li7La3Zr2O12"}, run_id="run:1"
    )
    c = kg.add_node("node:job:dft1", KGNodeType.SimulationJob, run_id="run:1")
    d = kg.add_node("node:artifact:cif1", KGNodeType.Artifact, run_id="run:1")
    e = kg.add_node("node:actor:lead", KGNodeType.Actor, run_id="run:1")
    kg.add_edge("edge:1", c.node_id, b.node_id, KGEdgeType.USED, run_id="run:1")
    kg.add_edge("edge:2", c.node_id, d.node_id, KGEdgeType.GENERATED, run_id="run:1")
    kg.add_edge("edge:3", c.node_id, e.node_id, KGEdgeType.ATTRIBUTED_TO, run_id="run:1")
    return a.node_id, c.node_id


# ----------------------------------------------------------------------------
# In-memory graph
# ----------------------------------------------------------------------------


def test_export_kg_graph_emits_triples(tmp_path):
    kg = MaterialsKG(tmp_path / "kg.sqlite")
    try:
        _seed_minimal_graph(kg)
        g = export_kg_graph(kg)
        assert len(g) > 0
    finally:
        kg.close()


def test_export_kg_graph_includes_prov_activity_for_simulation_job(tmp_path):
    kg = MaterialsKG(tmp_path / "kg.sqlite")
    try:
        _seed_minimal_graph(kg)
        g = export_kg_graph(kg)
        prov_activity = URIRef(f"{PROV_BASE_IRI}Activity")
        # At least the SimulationJob node has rdf:type prov:Activity.
        rows = list(g.triples((None, RDF.type, prov_activity)))
        assert rows, "no prov:Activity triples emitted"
    finally:
        kg.close()


def test_export_kg_graph_includes_prov_entity_for_artifact(tmp_path):
    kg = MaterialsKG(tmp_path / "kg.sqlite")
    try:
        _seed_minimal_graph(kg)
        g = export_kg_graph(kg)
        prov_entity = URIRef(f"{PROV_BASE_IRI}Entity")
        rows = list(g.triples((None, RDF.type, prov_entity)))
        assert rows, "no prov:Entity triples emitted"
    finally:
        kg.close()


def test_export_kg_graph_includes_prov_agent_for_actor(tmp_path):
    kg = MaterialsKG(tmp_path / "kg.sqlite")
    try:
        _seed_minimal_graph(kg)
        g = export_kg_graph(kg)
        prov_agent = URIRef(f"{PROV_BASE_IRI}Agent")
        rows = list(g.triples((None, RDF.type, prov_agent)))
        assert rows, "no prov:Agent triples emitted"
    finally:
        kg.close()


# ----------------------------------------------------------------------------
# Turtle round trip
# ----------------------------------------------------------------------------


def test_export_kg_to_turtle_writes_file(tmp_path):
    kg = MaterialsKG(tmp_path / "kg.sqlite")
    try:
        _seed_minimal_graph(kg)
        out = tmp_path / "kg.ttl"
        export_kg_to_turtle(kg, out)
        assert out.exists()
        assert out.stat().st_size > 0
        text = out.read_text(encoding="utf-8")
        # Turtle prefix declarations.
        assert "@prefix" in text or "PREFIX" in text
    finally:
        kg.close()


def test_round_trip_node_and_edge_counts_match(tmp_path):
    kg = MaterialsKG(tmp_path / "kg.sqlite")
    try:
        _seed_minimal_graph(kg)
        out = tmp_path / "kg.ttl"
        export_kg_to_turtle(kg, out)
        loaded_nodes, loaded_edges = round_trip_validate(kg, out)
        assert loaded_nodes == kg.count_nodes()
        assert loaded_edges == kg.count_edges()
    finally:
        kg.close()


def test_round_trip_with_larger_graph(tmp_path):
    kg = MaterialsKG(tmp_path / "kg.sqlite")
    try:
        # Insert one of each node type.
        for i, ntype in enumerate(KGNodeType):
            kg.add_node(f"node:bulk:{i}", ntype, run_id="run:1")
        # Plus a few edges.
        kg.add_edge(
            "edge:1", "node:bulk:0", "node:bulk:1",
            KGEdgeType.DERIVED_FROM, run_id="run:1"
        )
        kg.add_edge(
            "edge:2", "node:bulk:1", "node:bulk:2",
            KGEdgeType.GENERATED, run_id="run:1"
        )
        out = tmp_path / "kg.ttl"
        export_kg_to_turtle(kg, out)
        loaded_nodes, loaded_edges = round_trip_validate(kg, out)
        assert loaded_nodes == kg.count_nodes()
        assert loaded_edges == kg.count_edges()
    finally:
        kg.close()


def test_round_trip_preserves_node_properties(tmp_path):
    kg = MaterialsKG(tmp_path / "kg.sqlite")
    try:
        kg.add_node(
            "node:material",
            KGNodeType.CandidateMaterial,
            properties={"formula": "Li7La3Zr2O12", "num_atoms": 192},
            run_id="run:1",
        )
        out = tmp_path / "kg.ttl"
        export_kg_to_turtle(kg, out)
        # Reload graph and confirm we can find the formula property.
        g = Graph()
        g.parse(str(out), format="turtle")
        formula_pred = URIRef(f"{ZER0PA_EXTENSION_BASE_IRI}formula")
        rows = list(g.triples((None, formula_pred, None)))
        assert rows, "property not preserved in Turtle export"
        # The property value should round-trip.
        values = {str(r[2]) for r in rows}
        assert "Li7La3Zr2O12" in values
    finally:
        kg.close()


def test_export_empty_kg_produces_minimal_turtle(tmp_path):
    kg = MaterialsKG(tmp_path / "kg.sqlite")
    try:
        out = tmp_path / "kg.ttl"
        export_kg_to_turtle(kg, out)
        assert out.exists()
        # Empty KG should still produce parseable Turtle.
        g = Graph()
        g.parse(str(out), format="turtle")
        # No nodes / no edges.
        assert len(g) == 0
    finally:
        kg.close()
