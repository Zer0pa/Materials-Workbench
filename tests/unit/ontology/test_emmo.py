"""Tests for the EMMO-aligned ontology bindings (A1 §Audit Trail And KG)."""

from __future__ import annotations

import re

import pytest

from zer0pa_materials.audit.kg import KGEdgeType, KGNodeType
from zer0pa_materials.ontology.emmo import (
    EMMO_BASE_IRI,
    EMMO_TERMS,
    KG_EDGE_TO_EMMO,
    KG_NODE_TO_EMMO,
    OPTIMADE_BASE_IRI,
    OPTIMADE_VERSION,
    PROV_BASE_IRI,
    SPDX_BASE_IRI,
    ZER0PA_EXTENSION_BASE_IRI,
    EmmoTerm,
    iri_for_kg_edge,
    iri_for_kg_node,
)


# ----------------------------------------------------------------------------
# Namespace / version
# ----------------------------------------------------------------------------


def test_emmo_base_iri_is_w3id():
    assert EMMO_BASE_IRI.startswith("https://w3id.org/emmo")


def test_optimade_base_iri_is_canonical():
    assert OPTIMADE_BASE_IRI.startswith("https://schema.optimade.org")


def test_optimade_version_is_at_least_1_3():
    """PRD §Audit Trail And KG: 'OPTIMADE v1.3-first'."""
    assert OPTIMADE_VERSION == "1.3"


def test_zer0pa_extension_namespace():
    assert ZER0PA_EXTENSION_BASE_IRI == "https://schema.zer0pa.ai/materials#"


def test_prov_base_iri():
    assert PROV_BASE_IRI == "http://www.w3.org/ns/prov#"


def test_spdx_base_iri():
    assert SPDX_BASE_IRI == "http://spdx.org/licenses/"


# ----------------------------------------------------------------------------
# EMMO term subset
# ----------------------------------------------------------------------------


def test_emmo_terms_cover_required_classes():
    """PRD requires Material, Composition, Phase, Property, Process, Model,
    Simulation, Measurement, Reasoning, Provenance."""
    required = {
        "Material",
        "Composition",
        "Phase",
        "Property",
        "Process",
        "Model",
        "Simulation",
        "Measurement",
        "Reasoning",
        "Provenance",
    }
    assert required.issubset(set(EMMO_TERMS.keys()))


def test_emmo_terms_have_iris():
    for name, term in EMMO_TERMS.items():
        assert term.iri.startswith(("http://", "https://"))


def test_emmo_term_is_immutable():
    term = EMMO_TERMS["Material"]
    with pytest.raises(Exception):
        term.iri = "x"  # type: ignore[misc]


# ----------------------------------------------------------------------------
# KG node → EMMO mapping coverage
# ----------------------------------------------------------------------------


def test_every_kg_node_type_maps_to_at_least_one_iri():
    """Every PRD KG node type must have at least one ontology IRI."""
    for ntype in KGNodeType:
        mapping = KG_NODE_TO_EMMO.get(ntype.value)
        assert mapping is not None, f"missing mapping for {ntype.value}"
        assert len(mapping.iris) >= 1
        assert mapping.primary_iri in mapping.iris


def test_every_kg_node_iri_is_valid_uri():
    iri_re = re.compile(r"^https?://[^\s]+$")
    for ntype in KGNodeType:
        mapping = KG_NODE_TO_EMMO[ntype.value]
        for iri in mapping.iris:
            assert iri_re.match(iri), f"{ntype.value} → {iri!r} is not a URI"


def test_iri_for_kg_node_returns_primary():
    iri = iri_for_kg_node("CandidateMaterial")
    assert iri == EMMO_TERMS["Material"].iri


def test_iri_for_kg_node_raises_on_unknown():
    with pytest.raises(KeyError, match="unknown KG node type"):
        iri_for_kg_node("NotAType")


# ----------------------------------------------------------------------------
# KG edge → EMMO/PROV mapping coverage
# ----------------------------------------------------------------------------


def test_every_kg_edge_type_maps_to_at_least_one_iri():
    for etype in KGEdgeType:
        mapping = KG_EDGE_TO_EMMO.get(etype.value)
        assert mapping is not None, f"missing edge mapping for {etype.value}"
        assert len(mapping.iris) >= 1
        assert mapping.primary_iri in mapping.iris


def test_prov_edges_use_prov_o_iris():
    """DERIVED_FROM, USED, GENERATED, ATTRIBUTED_TO map to PROV-O."""
    for etype, expected in [
        ("DERIVED_FROM", "wasDerivedFrom"),
        ("USED", "used"),
        ("GENERATED", "generated"),
        ("ATTRIBUTED_TO", "wasAttributedTo"),
    ]:
        iri = iri_for_kg_edge(etype)
        assert iri.startswith(PROV_BASE_IRI)
        assert iri.endswith(expected)


def test_iri_for_kg_edge_raises_on_unknown():
    with pytest.raises(KeyError, match="unknown KG edge type"):
        iri_for_kg_edge("NOT_AN_EDGE")


# ----------------------------------------------------------------------------
# OPTIMADE v1.3 mapping for OPTIMADEResource node
# ----------------------------------------------------------------------------


def test_optimade_resource_maps_to_v1_3():
    mapping = KG_NODE_TO_EMMO["OPTIMADEResource"]
    assert any("1.3" in iri for iri in mapping.iris)


# ----------------------------------------------------------------------------
# License mapping uses SPDX
# ----------------------------------------------------------------------------


def test_license_maps_to_spdx():
    mapping = KG_NODE_TO_EMMO["License"]
    assert any(iri.startswith(SPDX_BASE_IRI) for iri in mapping.iris)


# ----------------------------------------------------------------------------
# Provenance node maps to prov:Activity
# ----------------------------------------------------------------------------


def test_provenance_node_links_to_prov_o():
    """Provenance class subClassOf prov:Activity."""
    term = EMMO_TERMS["Provenance"]
    assert any(p.startswith(PROV_BASE_IRI) for p in term.parents)


# ----------------------------------------------------------------------------
# Construction safety
# ----------------------------------------------------------------------------


def test_emmo_term_rejects_extra_fields():
    with pytest.raises(Exception):
        EmmoTerm(
            iri="https://x.com",
            pref_label="X",
            extra="bad",  # type: ignore[call-arg]
        )
