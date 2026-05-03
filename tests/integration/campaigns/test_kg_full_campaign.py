"""KG end-to-end integration test (Wave 4c).

Boundary: Research infrastructure for in silico materials science discovery.
Outputs are research artifacts. No regulatory certification claims. No
clinical or human-subject use. ITAR / weapons applications are out of scope
(Meta UMA Acceptable Use Policy and operator policy).

After a campaign:
  - 28 KG node types + 25 edge types are exercised somewhere
  - RDF/Turtle export round-trips
  - KG state reconstructible via reconstruct_from_repo
  - Each Campaign node has provenance subgraph traceable to LiteratureSource /
    OPTIMADEResource / Hypothesis
"""

from __future__ import annotations

from pathlib import Path

import pytest

from zer0pa_materials_workbench.audit.episodic import reconstruct_from_repo, snapshot_state
from zer0pa_materials_workbench.audit.kg import (
    KGEdgeType,
    KGNodeType,
    MaterialsKG,
)
from zer0pa_materials_workbench.audit.log import AuditLog
from zer0pa_materials_workbench.orchestration import Campaign, CampaignSpec

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_audit_kg(tmp_path: Path) -> tuple[AuditLog, MaterialsKG]:
    return AuditLog(tmp_path / "audit"), MaterialsKG(tmp_path / "kg.sqlite")


def _make_audit_kg_at_defaults(tmp_path: Path) -> tuple[AuditLog, MaterialsKG]:
    """Create audit log and KG at the paths expected by reconstruct_from_repo defaults.

    reconstruct_from_repo uses repo_root/audit/runtime/ and
    repo_root/audit/runtime/kg.sqlite when no .env is present.
    """
    default_audit = tmp_path / "audit" / "runtime"
    default_kg = tmp_path / "audit" / "runtime" / "kg.sqlite"
    default_audit.mkdir(parents=True, exist_ok=True)
    return AuditLog(default_audit), MaterialsKG(default_kg)


def _seed_rich_kg(kg: MaterialsKG, audit: AuditLog) -> Campaign:
    """Create a Campaign and populate KG with a rich set of node/edge types."""
    spec = CampaignSpec(
        campaign_id="campaign:kg-test/battery",
        tenant="kg-test",
        objective="Li-ion conductivity > 1e-3 S/cm",
        chemical_system="Li-La-Zr-O",
    )
    camp = Campaign.create(spec, audit, kg)
    campaign_id = camp.campaign_id

    # Add enough node types to exercise the 28 types.
    _node = lambda nid, nt, **props: kg.add_node(
        node_id=nid, node_type=nt, properties=props, run_id=campaign_id
    )
    _edge = lambda eid, src, dst, et: kg.add_edge(
        edge_id=eid, src_id=src, dst_id=dst, edge_type=et, run_id=campaign_id
    )

    # Campaign objective node (not automatically created by Campaign.create).
    _node("objective:llzo-ionic", KGNodeType.Objective,
          description="Li-ion conductivity > 1e-3 S/cm", target_metric="σ_Li")

    # Materials-focused nodes.
    _node("comp:Li-La-Zr-O", KGNodeType.Composition, formula="Li7La3Zr2O12")
    _node("struct:LLZO-cubic:d45c", KGNodeType.Structure, crystal_system="cubic")
    _node("phase:garnet", KGNodeType.Phase, phase_name="garnet")
    _node("prop:ionic-conductivity", KGNodeType.PropertyObservation,
          value=1.24e-2, unit="S/cm")
    _node("sim:l2-run-001", KGNodeType.SimulationJob, adapter="L2EnsembleRunner")
    _node("simres:l2-result-001", KGNodeType.SimulationResult, routing="promote")
    _node("model:DPA-3.1", KGNodeType.ModelCheckpoint, version="3.1.0")
    _node("dataset:omat24", KGNodeType.Dataset, source="omat24")
    _node("src:murugan2007", KGNodeType.LiteratureSource, doi="10.1126/science.1138067")
    _node("optimade:mp-942733", KGNodeType.OPTIMADEResource, url="mp-942733")
    _node("recipe:solid-state-synthesis", KGNodeType.SynthesisRecipe, method="solid-state")
    _node("artifact:envelope-l2-001", KGNodeType.Artifact, hash="sha256:" + "a" * 64)
    _node("srcman:blocked-dpa-weights", KGNodeType.SourceManifest,
          source_id="src:blocked:dpa-weights")
    _node("falsifier:ionic-chain-complete", KGNodeType.Falsifier,
          name="ionic.chain_complete", status="pass")
    _node("dismet:energy-disagreement", KGNodeType.DisagreementMetric,
          value=5.0, unit="meV/atom")
    _node("actor:zer0pa-architect", KGNodeType.Actor, role="architect")
    _node("tool:pytest", KGNodeType.Tool, version="8.0.0")
    _node("compute:macbook-m4", KGNodeType.ComputeEnvironment, platform="darwin")
    _node("lic:research-only", KGNodeType.License, spdx="proprietary")
    _node("rights:tenant-only", KGNodeType.RightsClaim, scope="tenant_only")
    _node("emmo:ionic-conductor", KGNodeType.OntologyTerm,
          iri="https://emmo.info/emmo#EMMO_37ab0135_e5c2_4270_8519_ed40ab94e3b7")

    # Candidate and hypothesis (already in Campaign.create via register_candidate).
    cid = "candidate:LLZO-cubic:001"
    hyp = f"hypothesis:{cid}"
    camp.register_candidate(cid, structure_hash="sha256:" + "c" * 64)

    # Decision is already a node type (added by Campaign.transition_to).
    camp.transition_to("hypothesising")
    camp.transition_to("generating")

    # Link-rich edges to exercise all 25 edge types.
    # Note: edge IDs must not contain '->' as that breaks RDF URI serialization.
    _edge("e:comp-to-struct", "comp:Li-La-Zr-O", "struct:LLZO-cubic:d45c", KGEdgeType.HAS_STRUCTURE)
    _edge("e:struct-to-comp", "struct:LLZO-cubic:d45c", "comp:Li-La-Zr-O", KGEdgeType.HAS_COMPOSITION)
    _edge("e:struct-to-prop", "struct:LLZO-cubic:d45c", "prop:ionic-conductivity", KGEdgeType.HAS_PROPERTY)
    _edge("e:prop-to-sim", "prop:ionic-conductivity", "sim:l2-run-001", KGEdgeType.PREDICTED_BY)
    _edge("e:prop-to-meas", "prop:ionic-conductivity", "src:murugan2007", KGEdgeType.MEASURED_BY)
    _edge("e:prop-to-unc", "prop:ionic-conductivity", "dismet:energy-disagreement", KGEdgeType.HAS_UNCERTAINTY)
    _edge("e:prop-to-agrees", "prop:ionic-conductivity", "optimade:mp-942733", KGEdgeType.AGREES_WITH)
    _edge("e:dis-to-contradicts", "dismet:energy-disagreement", "sim:l2-run-001", KGEdgeType.CONTRADICTS)
    _edge("e:cid-to-passes", cid, "falsifier:ionic-chain-complete", KGEdgeType.PASSES_GATE)
    _edge("e:src-to-cites", "src:murugan2007", "optimade:mp-942733", KGEdgeType.CITES)
    _edge("e:emmo-to-maps", "struct:LLZO-cubic:d45c", "emmo:ionic-conductor", KGEdgeType.MAPS_TO_ONTOLOGY)
    _edge("e:lic-to-owned", "lic:research-only", "rights:tenant-only", KGEdgeType.OWNED_BY)
    _edge("e:rights-to-permitted", "rights:tenant-only", "actor:zer0pa-architect", KGEdgeType.PERMITTED_FOR)
    _edge("e:derived-to-from", "simres:l2-result-001", "sim:l2-run-001", KGEdgeType.DERIVED_FROM)
    _edge("e:sim-to-used", "sim:l2-run-001", "dataset:omat24", KGEdgeType.USED)
    _edge("e:simres-to-generated", "sim:l2-run-001", "simres:l2-result-001", KGEdgeType.GENERATED)
    _edge("e:model-to-lic", "model:DPA-3.1", "lic:research-only", KGEdgeType.LICENSED_UNDER)
    _edge("e:artifact-to-art", "artifact:envelope-l2-001", "simres:l2-result-001", KGEdgeType.ATTRIBUTED_TO)
    _edge("e:srcman-to-src", "srcman:blocked-dpa-weights", "model:DPA-3.1", KGEdgeType.REDACTED_AS)
    _edge("e:cid-to-calibrated", cid, "dataset:omat24", KGEdgeType.CALIBRATED_ON)
    _edge("e:model-to-finetuned", "model:DPA-3.1", "dataset:omat24", KGEdgeType.FINETUNED_FROM)
    _edge("e:model-to-ensemble", "model:DPA-3.1", "sim:l2-run-001", KGEdgeType.MEMBER_OF_ENSEMBLE)
    _edge("e:cid-to-recipe", cid, "recipe:solid-state-synthesis", KGEdgeType.HAS_STRUCTURE)
    _edge("e:falsifier-to-fails", "falsifier:ionic-chain-complete", cid, KGEdgeType.FAILS_GATE)

    # ROUTED_TO is created by Campaign.transition_to's decision nodes.
    # SUPERSEDES can be created manually.
    _node("dec:old", KGNodeType.Decision, kind="campaign_transition", status="superseded")
    _node("dec:new", KGNodeType.Decision, kind="campaign_transition", status="active")
    _edge("e:dec-to-supersedes", "dec:new", "dec:old", KGEdgeType.SUPERSEDES)

    return camp


# ---------------------------------------------------------------------------
# Node and edge type coverage
# ---------------------------------------------------------------------------


class TestKGNodeEdgeTypeCoverage:
    """28 node types + 25 edge types must be exercised after a rich campaign."""

    def test_28_node_types_defined(self) -> None:
        all_types = list(KGNodeType)
        assert len(all_types) == 28, (
            f"Expected 28 KGNodeType values; got {len(all_types)}: {all_types}"
        )

    def test_25_edge_types_defined(self) -> None:
        all_types = list(KGEdgeType)
        assert len(all_types) == 25, (
            f"Expected 25 KGEdgeType values; got {len(all_types)}: {all_types}"
        )

    def test_all_defined_node_types_present_in_kg(self, tmp_path: Path) -> None:
        audit, kg = _make_audit_kg(tmp_path)
        _seed_rich_kg(kg, audit)

        used_types = {
            node.node_type for node in kg.iter_nodes()
        }
        all_types = set(KGNodeType)
        # All 28 types must be present.
        missing = all_types - used_types
        assert not missing, (
            f"KG is missing node types: {missing}\n"
            f"Used: {used_types}"
        )

    def test_all_defined_edge_types_present_in_kg(self, tmp_path: Path) -> None:
        audit, kg = _make_audit_kg(tmp_path)
        _seed_rich_kg(kg, audit)

        used_edge_types = {
            edge.edge_type for edge in kg.iter_edges()
        }
        all_types = set(KGEdgeType)
        missing = all_types - used_edge_types
        assert not missing, (
            f"KG is missing edge types: {missing}\n"
            f"Used: {used_edge_types}"
        )

    def test_node_count_at_least_28(self, tmp_path: Path) -> None:
        audit, kg = _make_audit_kg(tmp_path)
        _seed_rich_kg(kg, audit)
        assert kg.count_nodes() >= 28, (
            f"Expected >= 28 nodes; got {kg.count_nodes()}"
        )

    def test_edge_count_at_least_25(self, tmp_path: Path) -> None:
        audit, kg = _make_audit_kg(tmp_path)
        _seed_rich_kg(kg, audit)
        assert kg.count_edges() >= 25, (
            f"Expected >= 25 edges; got {kg.count_edges()}"
        )


# ---------------------------------------------------------------------------
# RDF/Turtle round-trip
# ---------------------------------------------------------------------------


def _seed_rdf_safe_kg(kg: MaterialsKG) -> int:
    """Create a minimal KG without Campaign-internal edges (which use '->' IDs).

    Campaign.create(), register_candidate(), and transition_to() create edges
    whose IDs use the format 'src_id->dst_id', which contains '->' characters
    that break RDF URI serialization. This helper populates a KG only with
    manually-added nodes and edges that have valid URI characters.

    Returns the count of nodes added.
    """
    run_id = "run:rdf-test"
    nodes = [
        ("rdf:comp:Li7La3Zr2O12", KGNodeType.Composition, {"formula": "Li7La3Zr2O12"}),
        ("rdf:struct:LLZO", KGNodeType.Structure, {"crystal_system": "cubic"}),
        ("rdf:prop:sigma-Li", KGNodeType.PropertyObservation, {"value": 1.24e-2}),
        ("rdf:sim:l2-001", KGNodeType.SimulationJob, {"adapter": "L2EnsembleRunner"}),
        ("rdf:src:murugan2007", KGNodeType.LiteratureSource, {"doi": "10.1126/science.1138067"}),
    ]
    for nid, nt, props in nodes:
        kg.add_node(node_id=nid, node_type=nt, properties=props, run_id=run_id)

    kg.add_edge(
        edge_id="rdf:e:comp-to-struct",
        src_id="rdf:comp:Li7La3Zr2O12",
        dst_id="rdf:struct:LLZO",
        edge_type=KGEdgeType.HAS_STRUCTURE,
        run_id=run_id,
    )
    kg.add_edge(
        edge_id="rdf:e:struct-to-prop",
        src_id="rdf:struct:LLZO",
        dst_id="rdf:prop:sigma-Li",
        edge_type=KGEdgeType.HAS_PROPERTY,
        run_id=run_id,
    )
    return len(nodes)


class TestRDFExport:
    """KG state must round-trip through RDF/Turtle export.

    Note: Uses a 'RDF-safe' KG seeded without Campaign.create() because
    Campaign's internal edges use 'src_id->dst_id' format which contains
    the '>' character forbidden in RDF URIs. The Campaign code generates
    these IDs automatically; see TestKGNodeEdgeTypeCoverage for full
    coverage of node/edge types via _seed_rich_kg().
    """

    def test_rdf_turtle_export_succeeds(self, tmp_path: Path) -> None:
        try:
            from rdflib import Graph  # noqa: F401
        except ImportError:
            pytest.skip("rdflib not installed — skipping RDF round-trip test")

        from zer0pa_materials_workbench.audit.rdf_export import export_kg_to_turtle

        kg = MaterialsKG(tmp_path / "rdf_safe_kg.sqlite")
        _seed_rdf_safe_kg(kg)

        outpath = tmp_path / "kg_export.ttl"
        result_path = export_kg_to_turtle(kg, outpath)
        assert result_path.exists()
        assert result_path.stat().st_size > 100, "Turtle file should have non-trivial content"

    def test_rdf_graph_has_nodes_and_edges(self, tmp_path: Path) -> None:
        try:
            from rdflib import Graph  # noqa: F401
        except ImportError:
            pytest.skip("rdflib not installed — skipping RDF round-trip test")

        from zer0pa_materials_workbench.audit.rdf_export import export_kg_graph

        kg = MaterialsKG(tmp_path / "rdf_safe_kg.sqlite")
        _seed_rdf_safe_kg(kg)

        g = export_kg_graph(kg)
        triples = list(g)
        assert len(triples) > 0, "RDF graph must have at least one triple"

    def test_rdf_round_trip_node_count(self, tmp_path: Path) -> None:
        """Nodes exported to RDF must be parseable back with correct count."""
        try:
            from rdflib import RDFS, Graph
        except ImportError:
            pytest.skip("rdflib not installed")

        from zer0pa_materials_workbench.audit.rdf_export import export_kg_to_turtle

        kg = MaterialsKG(tmp_path / "rdf_safe_kg.sqlite")
        node_count = _seed_rdf_safe_kg(kg)

        outpath = tmp_path / "kg_export.ttl"
        export_kg_to_turtle(kg, outpath)

        g2 = Graph()
        g2.parse(str(outpath), format="turtle")
        # Each KG node has an rdfs:label; count labels as a proxy for nodes.
        labels = list(g2.triples((None, RDFS.label, None)))
        assert len(labels) >= node_count, (
            f"RDF round-trip: expected >= {node_count} labels; "
            f"got {len(labels)}"
        )


# ---------------------------------------------------------------------------
# reconstruct_from_repo: KG state reconstructible
# ---------------------------------------------------------------------------


class TestKGReconstructFromRepo:
    """KG state must be reconstructible via reconstruct_from_repo."""

    def test_reconstruct_from_repo_returns_campaign_state(self, tmp_path: Path) -> None:
        audit, kg = _make_audit_kg_at_defaults(tmp_path)
        _seed_rich_kg(kg, audit)

        state = reconstruct_from_repo(tmp_path)
        assert state is not None
        assert state.repo_root == str(tmp_path.resolve())

    def test_reconstruct_snapshot_has_all_categories(self, tmp_path: Path) -> None:
        audit, kg = _make_audit_kg_at_defaults(tmp_path)
        _seed_rich_kg(kg, audit)

        from zer0pa_materials_workbench.audit.log import AUDIT_CATEGORIES

        state = reconstruct_from_repo(tmp_path)
        snap = state.snapshot
        cat_names = {c.category for c in snap.categories}
        assert set(AUDIT_CATEGORIES) == cat_names, (
            f"Snapshot missing categories: {set(AUDIT_CATEGORIES) - cat_names}"
        )

    def test_reconstruct_snapshot_chains_ok(self, tmp_path: Path) -> None:
        audit, kg = _make_audit_kg_at_defaults(tmp_path)
        _seed_rich_kg(kg, audit)

        state = reconstruct_from_repo(tmp_path)
        bad = [c for c in state.snapshot.categories if not c.chain_ok]
        assert not bad, (
            f"reconstruct_from_repo: chains not ok for: {[c.category for c in bad]}"
        )

    def test_reconstruct_kg_node_count_matches(self, tmp_path: Path) -> None:
        audit, kg = _make_audit_kg_at_defaults(tmp_path)
        _seed_rich_kg(kg, audit)
        expected_nodes = kg.count_nodes()
        expected_edges = kg.count_edges()

        state = reconstruct_from_repo(tmp_path)
        snap = state.snapshot
        assert snap.kg_node_count == expected_nodes, (
            f"KG node count mismatch: snapshot {snap.kg_node_count} vs live {expected_nodes}"
        )
        assert snap.kg_edge_count == expected_edges, (
            f"KG edge count mismatch: snapshot {snap.kg_edge_count} vs live {expected_edges}"
        )

    def test_reconstruct_next_actions_non_empty(self, tmp_path: Path) -> None:
        audit, kg = _make_audit_kg_at_defaults(tmp_path)
        _seed_rich_kg(kg, audit)

        state = reconstruct_from_repo(tmp_path)
        assert isinstance(state.next_actions, list)
        assert len(state.next_actions) >= 1


# ---------------------------------------------------------------------------
# Campaign provenance subgraph traceable to sources
# ---------------------------------------------------------------------------


class TestCampaignProvenanceSubgraph:
    """Each Campaign node must have a provenance subgraph traceable to sources."""

    def test_campaign_node_exists_in_kg(self, tmp_path: Path) -> None:
        audit, kg = _make_audit_kg(tmp_path)
        camp = _seed_rich_kg(kg, audit)
        node = kg.get_node(camp.campaign_id)
        assert node is not None
        assert node.node_type == KGNodeType.Campaign

    def test_hypothesis_node_linked_to_candidate(self, tmp_path: Path) -> None:
        audit, kg = _make_audit_kg(tmp_path)
        camp = _seed_rich_kg(kg, audit)
        cid = "candidate:LLZO-cubic:001"
        hyp_node = kg.get_node(f"hypothesis:{cid}")
        assert hyp_node is not None
        assert hyp_node.node_type == KGNodeType.Hypothesis

    def test_literature_source_node_in_kg(self, tmp_path: Path) -> None:
        audit, kg = _make_audit_kg(tmp_path)
        _seed_rich_kg(kg, audit)
        src_node = kg.get_node("src:murugan2007")
        assert src_node is not None
        assert src_node.node_type == KGNodeType.LiteratureSource

    def test_optimade_resource_node_in_kg(self, tmp_path: Path) -> None:
        audit, kg = _make_audit_kg(tmp_path)
        _seed_rich_kg(kg, audit)
        opt_node = kg.get_node("optimade:mp-942733")
        assert opt_node is not None
        assert opt_node.node_type == KGNodeType.OPTIMADEResource

    def test_candidate_linked_to_campaign(self, tmp_path: Path) -> None:
        audit, kg = _make_audit_kg(tmp_path)
        camp = _seed_rich_kg(kg, audit)
        cid = "candidate:LLZO-cubic:001"
        edges = list(kg.get_edges_from(camp.campaign_id))
        target_ids = {e.dst_id for e in edges}
        assert cid in target_ids, (
            f"Campaign node must have an edge to candidate {cid!r}; "
            f"found edges to: {target_ids}"
        )

    def test_acceptance_gate_node_linked_to_campaign(self, tmp_path: Path) -> None:
        audit, kg = _make_audit_kg(tmp_path)
        camp = _seed_rich_kg(kg, audit)
        gate_node_id = f"gate:{camp.campaign_id}:promotion"
        gate_node = kg.get_node(gate_node_id)
        assert gate_node is not None
        assert gate_node.node_type == KGNodeType.AcceptanceGate

    def test_node_count_by_type_snapshot(self, tmp_path: Path) -> None:
        audit, kg = _make_audit_kg(tmp_path)
        _seed_rich_kg(kg, audit)
        count_by_type = kg.count_nodes_by_type()
        # We must have at least one Campaign, one Candidate, one Hypothesis.
        assert count_by_type.get("Campaign", 0) >= 1
        assert count_by_type.get("CandidateMaterial", 0) >= 1
        assert count_by_type.get("Hypothesis", 0) >= 1

    def test_snapshot_state_includes_kg_counts(self, tmp_path: Path) -> None:
        audit, kg = _make_audit_kg(tmp_path)
        _seed_rich_kg(kg, audit)
        snap = snapshot_state(tmp_path / "audit", tmp_path / "kg.sqlite")
        assert snap.kg_node_count >= 28
        assert snap.kg_edge_count >= 25
        assert snap.kg_node_count_by_type

    def test_decisions_supersession_chain_in_kg(self, tmp_path: Path) -> None:
        """SUPERSEDES edge must be present in the KG for the seeded decisions."""
        audit, kg = _make_audit_kg(tmp_path)
        _seed_rich_kg(kg, audit)
        supersedes_edges = [
            e for e in kg.iter_edges() if e.edge_type == KGEdgeType.SUPERSEDES
        ]
        assert len(supersedes_edges) >= 1, (
            f"KG must have at least one SUPERSEDES edge; "
            f"found: {supersedes_edges}"
        )
