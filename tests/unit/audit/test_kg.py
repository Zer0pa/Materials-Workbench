"""Tests for the SQLite-backed KG (A1 §Audit Trail And KG)."""

from __future__ import annotations

import pytest

from zer0pa_materials_workbench.audit.kg import (
    KGEdgeType,
    KGNodeType,
    KGTypeError,
    MaterialsKG,
)

# ----------------------------------------------------------------------------
# Node insertion
# ----------------------------------------------------------------------------


def test_kg_can_insert_all_27_node_types(tmp_path):
    """Every PRD-listed node type must be insertable.

    The PRD lists 28 node types (Campaign...OntologyTerm). All must work.
    """
    kg = MaterialsKG(tmp_path / "kg.sqlite")
    try:
        for i, ntype in enumerate(KGNodeType):
            node = kg.add_node(
                node_id=f"node:test:{ntype.value}:{i}",
                node_type=ntype,
                run_id="run:test",
            )
            assert node.node_type == ntype
            assert node.ontology_term.startswith(("https://", "http://"))
        assert kg.count_nodes() == len(list(KGNodeType))
    finally:
        kg.close()


def test_kg_rejects_non_canonical_node_type(tmp_path):
    kg = MaterialsKG(tmp_path / "kg.sqlite")
    try:
        with pytest.raises(KGTypeError, match="unknown KG node type"):
            kg.add_node("node:bad:1", node_type="NotARealType", run_id="run:t")
    finally:
        kg.close()


def test_kg_node_round_trips_with_properties(tmp_path):
    kg = MaterialsKG(tmp_path / "kg.sqlite")
    try:
        kg.add_node(
            node_id="node:llzo",
            node_type=KGNodeType.CandidateMaterial,
            properties={"formula": "Li7La3Zr2O12", "polymorph": "cubic"},
            run_id="run:test",
        )
        loaded = kg.get_node("node:llzo")
        assert loaded is not None
        assert loaded.properties["formula"] == "Li7La3Zr2O12"
        assert loaded.properties["polymorph"] == "cubic"
    finally:
        kg.close()


def test_kg_node_default_ontology_term(tmp_path):
    """If no ontology_term given, use the EMMO mapping primary IRI."""
    kg = MaterialsKG(tmp_path / "kg.sqlite")
    try:
        node = kg.add_node(
            node_id="node:test:material",
            node_type=KGNodeType.CandidateMaterial,
            run_id="run:t",
        )
        # The Material → EMMO mapping resolves to an EMMO IRI.
        assert "emmo" in node.ontology_term.lower() or "zer0pa" in node.ontology_term.lower()
    finally:
        kg.close()


def test_kg_get_node_returns_none_for_missing(tmp_path):
    kg = MaterialsKG(tmp_path / "kg.sqlite")
    try:
        assert kg.get_node("node:does-not-exist") is None
    finally:
        kg.close()


# ----------------------------------------------------------------------------
# Edge insertion
# ----------------------------------------------------------------------------


def _seed_two_nodes(kg: MaterialsKG):
    a = kg.add_node("node:a", KGNodeType.CandidateMaterial, run_id="run:t")
    b = kg.add_node("node:b", KGNodeType.SimulationJob, run_id="run:t")
    return a, b


def test_kg_can_insert_all_25_edge_types(tmp_path):
    """Every PRD-listed edge type must be insertable."""
    kg = MaterialsKG(tmp_path / "kg.sqlite")
    try:
        a, b = _seed_two_nodes(kg)
        for i, etype in enumerate(KGEdgeType):
            kg.add_edge(
                edge_id=f"edge:test:{etype.value}:{i}",
                src_id=a.node_id,
                dst_id=b.node_id,
                edge_type=etype,
                run_id="run:t",
            )
        assert kg.count_edges() == len(list(KGEdgeType))
    finally:
        kg.close()


def test_kg_rejects_non_canonical_edge_type(tmp_path):
    kg = MaterialsKG(tmp_path / "kg.sqlite")
    try:
        a, b = _seed_two_nodes(kg)
        with pytest.raises(KGTypeError, match="unknown KG edge type"):
            kg.add_edge(
                edge_id="edge:bad",
                src_id=a.node_id,
                dst_id=b.node_id,
                edge_type="NOT_AN_EDGE",
                run_id="run:t",
            )
    finally:
        kg.close()


def test_kg_get_edges_from_with_type_filter(tmp_path):
    kg = MaterialsKG(tmp_path / "kg.sqlite")
    try:
        a, b = _seed_two_nodes(kg)
        kg.add_edge("edge:1", a.node_id, b.node_id, KGEdgeType.GENERATED, run_id="run:t")
        kg.add_edge("edge:2", a.node_id, b.node_id, KGEdgeType.USED, run_id="run:t")
        kg.add_edge("edge:3", a.node_id, b.node_id, KGEdgeType.DERIVED_FROM, run_id="run:t")
        all_from_a = kg.get_edges_from(a.node_id)
        assert len(all_from_a) == 3
        only_used = kg.get_edges_from(a.node_id, KGEdgeType.USED)
        assert len(only_used) == 1
        assert only_used[0].edge_id == "edge:2"
    finally:
        kg.close()


def test_kg_get_edges_to_with_type_filter(tmp_path):
    kg = MaterialsKG(tmp_path / "kg.sqlite")
    try:
        a, b = _seed_two_nodes(kg)
        c = kg.add_node("node:c", KGNodeType.SimulationResult, run_id="run:t")
        kg.add_edge("edge:1", a.node_id, b.node_id, KGEdgeType.GENERATED, run_id="run:t")
        kg.add_edge("edge:2", c.node_id, b.node_id, KGEdgeType.GENERATED, run_id="run:t")
        kg.add_edge("edge:3", a.node_id, c.node_id, KGEdgeType.USED, run_id="run:t")
        edges_to_b = kg.get_edges_to(b.node_id)
        assert len(edges_to_b) == 2
        edges_to_b_used = kg.get_edges_to(b.node_id, KGEdgeType.USED)
        assert len(edges_to_b_used) == 0
    finally:
        kg.close()


# ----------------------------------------------------------------------------
# Indexing — sanity check
# ----------------------------------------------------------------------------


def test_kg_indexes_exist(tmp_path):
    """Confirm the indexes we declared in DDL actually got created."""
    kg = MaterialsKG(tmp_path / "kg.sqlite")
    try:
        cur = kg._conn.execute("SELECT name FROM sqlite_master WHERE type='index'")
        names = {row[0] for row in cur.fetchall()}
        assert "kg_edge_src_idx" in names
        assert "kg_edge_dst_idx" in names
        assert "kg_node_type_idx" in names
    finally:
        kg.close()


def test_kg_count_nodes_by_type(tmp_path):
    kg = MaterialsKG(tmp_path / "kg.sqlite")
    try:
        kg.add_node("n1", KGNodeType.CandidateMaterial, run_id="r")
        kg.add_node("n2", KGNodeType.CandidateMaterial, run_id="r")
        kg.add_node("n3", KGNodeType.SimulationJob, run_id="r")
        counts = kg.count_nodes_by_type()
        assert counts.get("CandidateMaterial") == 2
        assert counts.get("SimulationJob") == 1
    finally:
        kg.close()


# ----------------------------------------------------------------------------
# Resume capture / reload
# ----------------------------------------------------------------------------


def test_kg_resume_capture_and_load(tmp_path):
    kg = MaterialsKG(tmp_path / "kg.sqlite")
    try:
        kg.capture_resume(
            run_id="run:overnight:2026-04-30",
            last_event_hash="sha256:" + "a" * 64,
            last_node_id="node:llzo",
            last_edge_id="edge:llzo:dft:1",
        )
        m = kg.load_resume("run:overnight:2026-04-30")
        assert m is not None
        assert m.last_event_hash == "sha256:" + "a" * 64
        assert m.last_node_id == "node:llzo"
        assert m.last_edge_id == "edge:llzo:dft:1"
    finally:
        kg.close()


def test_kg_resume_overwrites_on_repeat_run_id(tmp_path):
    kg = MaterialsKG(tmp_path / "kg.sqlite")
    try:
        kg.capture_resume(
            run_id="run:1",
            last_event_hash="sha256:" + "a" * 64,
        )
        kg.capture_resume(
            run_id="run:1",
            last_event_hash="sha256:" + "b" * 64,
            last_node_id="node:later",
        )
        m = kg.load_resume("run:1")
        assert m.last_event_hash == "sha256:" + "b" * 64
        assert m.last_node_id == "node:later"
    finally:
        kg.close()


def test_kg_resume_load_returns_none_for_missing_run(tmp_path):
    kg = MaterialsKG(tmp_path / "kg.sqlite")
    try:
        assert kg.load_resume("run:nonexistent") is None
    finally:
        kg.close()


# ----------------------------------------------------------------------------
# Reopen — schema is idempotent
# ----------------------------------------------------------------------------


def test_kg_can_reopen_existing_db(tmp_path):
    db = tmp_path / "kg.sqlite"
    kg = MaterialsKG(db)
    try:
        kg.add_node("node:keep", KGNodeType.CandidateMaterial, run_id="run:t")
    finally:
        kg.close()
    kg2 = MaterialsKG(db)
    try:
        node = kg2.get_node("node:keep")
        assert node is not None
    finally:
        kg2.close()
