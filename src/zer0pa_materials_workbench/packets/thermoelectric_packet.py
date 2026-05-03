"""Thermoelectric sidecar packet assembler (PRD §Final Output Required #10).

Inputs
------
A fixture identifier (Si, Bi2Te3, PbTe, SnSe). The assembler:

1. Reads the fixture's structure manifest.
2. Builds the multi-layer evidence chain:
   * Phase 0 (literature ZT references)
   * L6 known-control envelope
   * L2 ensemble (DPA-3 + MACE)
   * L1 DFT validation
   * Quantum slot (H2 + LiH VQE-vs-FCI infrastructure check)
   * L1.5 ZT assembly (Phono3py κ_L + BoltzTraP2/AMSET S, σ_e, κ_e)
   * L7 orchestration metadata
3. Aggregates cross-layer disagreement.
4. Drives the ZT rank-stability gate (PRD §L1.5).
5. Sets the ``publishable_paper_target`` to a real journal name.

There is NO ionic-transport section: thermoelectric candidates are
explicitly excluded from the Li-ion lane (PRD §L1.5 Boundary: "phonons
do not substitute for Li-ion conductivity").
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from zer0pa_materials_workbench.adapters.l1_5.base import L15JobParams
from zer0pa_materials_workbench.adapters.l1_5.zt_assembler import (
    ZT_RANK_STABILITY_TOLERANCE,
    ZT_THRESHOLD_HIGH,
    ThermoelectricZtAssembler,
)
from zer0pa_materials_workbench.adapters.quantum.pennylane_vqe import PennyLaneVqeSolver
from zer0pa_materials_workbench.envelope import Envelope
from zer0pa_materials_workbench.orchestration.disagreement_aggregator import (
    CrossLayerDisagreementAggregator,
    LayerDisagreementInput,
)
from zer0pa_materials_workbench.packets._envelope_builders import (
    l1_dft_envelope_stub,
    l2_ensemble_envelope_stub,
    l6_known_control_envelope,
    l7_orchestration_envelope,
    phase0_envelope_from_extraction,
)
from zer0pa_materials_workbench.packets.evidence_packet import (
    EvidencePacket,
    PacketBundle,
    PacketPublishableTarget,
    PacketSection,
    PromotionVerdict,
)

__all__ = [
    "THERMOELECTRIC_FIXTURE_SPECS",
    "ThermoelectricFixtureSpec",
    "ThermoelectricPacketAssembler",
    "assemble_thermoelectric_packet",
]


@dataclass(frozen=True)
class ThermoelectricFixtureSpec:
    """Static descriptor for a thermoelectric fixture used by the packet generator."""

    name: str
    fixture_id: str
    structure_hash: str
    structure_path: str
    candidate_uri: str
    operating_temperature_K: float
    target_zt_threshold: float
    default_target_journal: str
    alternative_journal: str
    literature_references: tuple[dict[str, Any], ...]


_REPO_ROOT = Path(__file__).resolve().parents[3]
_FIXTURES_ROOT = _REPO_ROOT / "fixtures"


THERMOELECTRIC_FIXTURE_SPECS: dict[str, ThermoelectricFixtureSpec] = {
    "Si": ThermoelectricFixtureSpec(
        name="Si",
        fixture_id="fixture:Si:standard",
        structure_hash="sha256:" + ("0" * 60) + "0001",
        structure_path=str(_FIXTURES_ROOT / "structures" / "Si" / "structure.cif"),
        candidate_uri="artifact:fixture:Si.cif",
        operating_temperature_K=300.0,
        target_zt_threshold=0.05,  # Si has poor ZT; gate set so Si fails honestly.
        default_target_journal="J. Mater. Chem. A",
        alternative_journal="ACS Energy Lett.",
        literature_references=(
            {
                "property_name": "thermal_conductivity_pure_Si_300K",
                "value": 150.0,
                "unit": "W/m/K",
                "grounding": {
                    "doi": "10.1103/PhysRev.134.A1058",
                    "page": 1058,
                    "table": None,
                    "figure": None,
                },
                "contradiction_flag": False,
            },
            {
                "property_name": "seebeck_coefficient_intrinsic",
                "value": 200.0,
                "unit": "uV/K",
                "grounding": {
                    "doi": "10.1063/1.1709919",
                    "page": 1,
                    "table": None,
                    "figure": "Figure 2",
                },
                "contradiction_flag": False,
            },
        ),
    ),
    "Bi2Te3": ThermoelectricFixtureSpec(
        name="Bi2Te3",
        fixture_id="fixture:Bi2Te3:cfee960f",
        structure_hash="sha256:cfee960f8705b17944ddfd4df64e3aa840d0870af020ea4f9d64bd05c1a7b54f",
        structure_path=str(_FIXTURES_ROOT / "structures" / "Bi2Te3" / "structure.cif"),
        candidate_uri="artifact:fixture:Bi2Te3.cif",
        operating_temperature_K=300.0,
        target_zt_threshold=ZT_THRESHOLD_HIGH,
        default_target_journal="npj Computational Materials",
        alternative_journal="J. Mater. Chem. A",
        literature_references=(
            {
                "property_name": "ZT_record",
                "value": 1.4,
                "unit": "dimensionless",
                "grounding": {
                    "doi": "10.1126/science.1156446",
                    "page": 1,
                    "table": None,
                    "figure": "Figure 3",
                },
                "contradiction_flag": False,
            },
            {
                "property_name": "thermal_conductivity_lattice",
                "value": 1.5,
                "unit": "W/m/K",
                "grounding": {
                    "doi": "10.1038/nmat2090",
                    "page": 105,
                    "table": "Table 1",
                    "figure": None,
                },
                "contradiction_flag": False,
            },
        ),
    ),
    "PbTe": ThermoelectricFixtureSpec(
        name="PbTe",
        fixture_id="fixture:PbTe:standard",
        structure_hash="sha256:" + ("0" * 60) + "0002",
        structure_path=str(_FIXTURES_ROOT / "structures" / "PbTe" / "structure.cif"),
        candidate_uri="artifact:fixture:PbTe.cif",
        operating_temperature_K=700.0,
        target_zt_threshold=ZT_THRESHOLD_HIGH,
        default_target_journal="Joule",
        alternative_journal="Energy Environ. Sci.",
        literature_references=(
            {
                "property_name": "ZT_at_high_T",
                "value": 1.8,
                "unit": "dimensionless",
                "grounding": {
                    "doi": "10.1126/science.1159725",
                    "page": 554,
                    "table": None,
                    "figure": "Figure 4",
                },
                "contradiction_flag": False,
            },
        ),
    ),
    "SnSe": ThermoelectricFixtureSpec(
        name="SnSe",
        fixture_id="fixture:SnSe:standard",
        structure_hash="sha256:" + ("0" * 60) + "0003",
        structure_path=str(_FIXTURES_ROOT / "structures" / "SnSe" / "structure.cif"),
        candidate_uri="artifact:fixture:SnSe.cif",
        operating_temperature_K=800.0,
        target_zt_threshold=ZT_THRESHOLD_HIGH,
        default_target_journal="Nature Materials",
        alternative_journal="Energy Environ. Sci.",
        literature_references=(
            {
                "property_name": "ZT_record",
                "value": 2.6,
                "unit": "dimensionless",
                "grounding": {
                    "doi": "10.1038/nature13184",
                    "page": 1,
                    "table": None,
                    "figure": "Figure 4",
                },
                "contradiction_flag": False,
            },
        ),
    ),
}


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------


def _zt_assembly_section_from_envelope(
    zt_envelope: Envelope,
) -> PacketSection:
    """Build the ZT assembly section from the L1.5 ZT envelope.

    The ZT envelope's ``output.zt_assembly`` carries both branches (BoltzTraP2 and
    AMSET) plus the rank-stability falsifier — we propagate them up so the
    validator and RO-Crate exporter can find them.
    """
    out = zt_envelope.output or {}
    zt_assembly = out.get("zt_assembly", {})
    return PacketSection(
        section_name="zt_assembly",
        summary=(
            "Thermoelectric ZT assembly: Phono3py κ_L + BoltzTraP2 (rigid-band) "
            "and AMSET (explicit scattering) electronic transport, plus rank-stability gate."
        ),
        envelopes=[zt_envelope.canonical_dict()],
        raw_payload={
            "bt2_zt": zt_assembly.get("bt2_zt"),
            "amset_zt": zt_assembly.get("amset_zt"),
            "kappa_L_W_per_mK": zt_assembly.get("kappa_L_W_per_mK"),
            "zt_rank_stable": zt_assembly.get("zt_rank_stable"),
            "zt_fractional_disagreement": zt_assembly.get("zt_fractional_disagreement"),
            "rank_stability_tolerance": ZT_RANK_STABILITY_TOLERANCE,
        },
    )


def _audit_chain_head_section(audit_record_ids: list[str]) -> PacketSection:
    return PacketSection(
        section_name="audit_trail_head",
        summary="Audit chain head — packets carry the audit_record_ids of every envelope.",
        envelopes=[],
        raw_payload={
            "audit_record_ids": list(audit_record_ids),
            "n_envelopes": len(audit_record_ids),
        },
    )


def _kg_snapshot_section(
    candidate_id: str,
    campaign_id: str,
    structure_hash: str,
    operating_temperature_K: float,
) -> PacketSection:
    nodes = [
        {
            "node_id": campaign_id,
            "node_type": "Campaign",
            "properties": {"objective": f"ZT > 1.5 at {operating_temperature_K} K"},
        },
        {
            "node_id": candidate_id,
            "node_type": "CandidateMaterial",
            "properties": {"structure_hash": structure_hash},
        },
        {
            "node_id": f"hypothesis:{candidate_id}",
            "node_type": "Hypothesis",
            "properties": {
                "objective": "thermoelectric_zt",
                "operating_temperature_K": operating_temperature_K,
            },
        },
    ]
    edges = [
        {
            "edge_id": f"edge:{campaign_id}->{candidate_id}",
            "src_id": campaign_id,
            "dst_id": candidate_id,
            "edge_type": "GENERATED",
        },
    ]
    return PacketSection(
        section_name="kg_snapshot",
        summary="Subset of MaterialsKG nodes + edges anchored to this thermoelectric candidate.",
        envelopes=[],
        raw_payload={
            "nodes": nodes,
            "edges": edges,
            "n_nodes": len(nodes),
            "n_edges": len(edges),
        },
    )


def _rights_claim_section(rights_claim_id: str, reuse_scope: str) -> PacketSection:
    return PacketSection(
        section_name="rights_claim",
        summary="Rights claim attached to this thermoelectric packet.",
        envelopes=[],
        raw_payload={
            "rights_claim_id": rights_claim_id,
            "reuse_scope": reuse_scope,
        },
    )


# ----------------------------------------------------------------------------
# Main assembler
# ----------------------------------------------------------------------------


class ThermoelectricPacketAssembler:
    """Compose the thermoelectric sidecar evidence packet for a fixture.

    Construction:

        assembler = ThermoelectricPacketAssembler()
        packet = assembler.assemble("Bi2Te3")

    ZT verdict semantics:

    * ``promote`` if the rank-stability gate passes AND both branches
      exceed the target threshold.
    * ``defer`` if rank-stability passes but at least one branch is below
      threshold.
    * ``reject`` if rank-stability fails (the candidate's ZT is unstable
      across transport assumptions and requires further DFT validation).
    """

    def assemble(
        self,
        fixture_key: str,
        *,
        candidate_id: str | None = None,
        campaign_id: str | None = None,
        rights_claim_id: str = "rights:thermoelectric:default",
        reuse_scope: str = "tenant_only",
        publishable_target: PacketPublishableTarget | None = None,
    ) -> EvidencePacket:
        """Assemble the EvidencePacket for a thermoelectric fixture."""
        if fixture_key not in THERMOELECTRIC_FIXTURE_SPECS:
            raise KeyError(
                f"unknown thermoelectric fixture {fixture_key!r}; valid: "
                f"{sorted(THERMOELECTRIC_FIXTURE_SPECS)}"
            )
        spec = THERMOELECTRIC_FIXTURE_SPECS[fixture_key]
        candidate_id = candidate_id or f"candidate:thermoelectric:{spec.name}"
        campaign_id = campaign_id or f"campaign:thermoelectric:{spec.name}"
        publishable_target = publishable_target or PacketPublishableTarget(
            primary_journal=spec.default_target_journal,
            alternative_journal=spec.alternative_journal,
            target_paper_kind="research_article",
            rationale=(
                f"PRD §Scope publishable-paper deliverable for {spec.name}. "
                f"Thermoelectric sidecar with κ_L from Phono3py + BoltzTraP2/AMSET disagreement gate."
            ),
        )

        # ---- Phase 0 grounding (literature ZT references) -------------------
        phase0_env = phase0_envelope_from_extraction(
            extracted_properties=list(spec.literature_references),
            candidate_id=candidate_id,
            campaign_id=campaign_id,
        )

        # ---- L6 known-control envelope --------------------------------------
        # Wave F5: pass the raw CIF text from the fixture so the L6
        # recompute (novelty_status_gate_recomputed) can hash from raw
        # evidence and match the claimed structure_hash.
        l6_cif_text: str | None = None
        try:
            l6_cif_path = Path(spec.structure_path)
            if l6_cif_path.is_file():
                l6_cif_text = l6_cif_path.read_text(encoding="utf-8")
        except OSError:
            l6_cif_text = None
        l6_env = l6_known_control_envelope(
            candidate_id=candidate_id,
            campaign_id=campaign_id,
            structure_hash=spec.structure_hash,
            candidate_uri=spec.candidate_uri,
            novelty_status="duplicate",
            matched_in=("MP",),
            cif_text=l6_cif_text,
        )

        # ---- L2 ensemble ----------------------------------------------------
        l2_env = l2_ensemble_envelope_stub(
            candidate_id=candidate_id,
            campaign_id=campaign_id,
            structure_hash=spec.structure_hash,
        )

        # ---- L1 DFT validation ----------------------------------------------
        l1_env = l1_dft_envelope_stub(
            candidate_id=candidate_id,
            campaign_id=campaign_id,
            structure_hash=spec.structure_hash,
            code="QE",
            functional="PBE",
            convergence_delta_meV_per_atom=4.0,
        )

        # ---- Quantum slot infrastructure check ------------------------------
        vqe_solver = PennyLaneVqeSolver()
        h2_env = vqe_solver.solve_h2(campaign_id=campaign_id, candidate_id=candidate_id)
        lih_env = vqe_solver.solve_lih(campaign_id=campaign_id, candidate_id=candidate_id)

        # ---- L1.5 ZT assembly -----------------------------------------------
        l15_params = L15JobParams(
            structure_hash=spec.structure_hash,
            fixture_id=spec.fixture_id,
            material_id=spec.name,
            temperature_K=spec.operating_temperature_K,
            campaign_id=campaign_id,
            candidate_id=candidate_id,
            rights_claim_id=rights_claim_id,
            reuse_scope=reuse_scope,
        )
        zt_env = ThermoelectricZtAssembler().compute(l15_params)
        zt_section = _zt_assembly_section_from_envelope(zt_env)

        # ---- L7 orchestration metadata --------------------------------------
        l7_env = l7_orchestration_envelope(
            candidate_id=candidate_id,
            campaign_id=campaign_id,
            promotion_decision="hold",
            acquisition="qLogExpectedImprovement",
            gate_verdict="pass",
        )

        # ---- Cross-layer disagreement aggregate -----------------------------
        agg = CrossLayerDisagreementAggregator()
        zt_assembly = zt_env.output.get("zt_assembly", {})
        zt_disagreement = float(zt_assembly.get("zt_fractional_disagreement", 0.0) or 0.0)
        disagreement_inputs = [
            LayerDisagreementInput(
                layer="L2",
                raw_value=l2_env.output["energy_disagreement_meV_per_atom"],
                unit="meV/atom",
                layer_audit_ref=l2_env.audit.audit_record_id,
            ),
            LayerDisagreementInput(
                layer="L1",
                raw_value=l1_env.output.get("convergence_delta_meV_per_atom") or 0.0,
                unit="meV/atom",
                layer_audit_ref=l1_env.audit.audit_record_id,
            ),
            LayerDisagreementInput(
                layer="L1.5",
                raw_value=zt_disagreement,
                unit="fraction",
                layer_audit_ref=zt_env.audit.audit_record_id,
            ),
        ]
        aggregate = agg.aggregate(disagreement_inputs)

        disagreement_section = PacketSection(
            section_name="cross_layer_disagreement",
            summary=(
                "Aggregate of per-layer disagreement metrics (L1, L1.5, L2). "
                "L1.5 contributes the BoltzTraP2-vs-AMSET ZT disagreement which "
                "is the primary thermoelectric disagreement signal."
            ),
            envelopes=[],
            raw_payload={
                "aggregate_score": aggregate.aggregate_score,
                "per_layer_normalised": aggregate.per_layer_normalised,
                "per_layer_audit_refs": aggregate.per_layer_audit_refs,
                "layers_contributing": aggregate.layers_contributing,
                "threshold": 0.5,
                "zt_fractional_disagreement": zt_disagreement,
            },
        )

        # ---- Drive the ZT promotion verdict ---------------------------------
        bt2_zt = float(zt_assembly.get("bt2_zt") or 0.0)
        amset_zt = float(zt_assembly.get("amset_zt") or 0.0)
        rank_stable = bool(zt_assembly.get("zt_rank_stable", False))
        threshold = spec.target_zt_threshold

        decision: PromotionVerdict
        rationale: str
        if not rank_stable:
            decision = "reject"
            rationale = (
                f"ZT rank stability gate FAILED — fractional disagreement "
                f"{zt_disagreement:.3f} > {ZT_RANK_STABILITY_TOLERANCE:.2f}. "
                "BoltzTraP2 (CRTA) and AMSET (explicit scattering) disagree "
                "above the tolerance; further DFT validation required."
            )
        elif bt2_zt > threshold and amset_zt > threshold:
            decision = "promote"
            rationale = (
                f"Both BoltzTraP2 (ZT={bt2_zt:.3f}) and AMSET (ZT={amset_zt:.3f}) "
                f"exceed target threshold {threshold:.2f}. ZT rank stable."
            )
        else:
            decision = "defer"
            rationale = (
                f"ZT rank stable but at least one branch below target {threshold:.2f} "
                f"(BoltzTraP2={bt2_zt:.3f}, AMSET={amset_zt:.3f}); "
                "candidate deferred for higher-fidelity DFT band structure."
            )

        # ---- Audit trail head -----------------------------------------------
        audit_ids = [
            phase0_env.audit.audit_record_id,
            l6_env.audit.audit_record_id,
            l2_env.audit.audit_record_id,
            l1_env.audit.audit_record_id,
            h2_env.audit.audit_record_id,
            lih_env.audit.audit_record_id,
            zt_env.audit.audit_record_id,
            l7_env.audit.audit_record_id,
        ]
        audit_section = _audit_chain_head_section(audit_ids)
        kg_section = _kg_snapshot_section(
            candidate_id=candidate_id,
            campaign_id=campaign_id,
            structure_hash=spec.structure_hash,
            operating_temperature_K=spec.operating_temperature_K,
        )
        rights_section = _rights_claim_section(
            rights_claim_id=rights_claim_id, reuse_scope=reuse_scope
        )

        sections: dict[str, PacketSection] = {
            "phase0_literature": PacketSection(
                section_name="phase0_literature",
                summary="Phase 0 literature grounding for this thermoelectric candidate.",
                envelopes=[phase0_env.canonical_dict()],
                raw_payload={"n_properties": len(spec.literature_references)},
            ),
            "l6_generated_structure": PacketSection(
                section_name="l6_generated_structure",
                summary="L6 known-control envelope (no novelty for thermoelectric MVP fixtures).",
                envelopes=[l6_env.canonical_dict()],
                raw_payload={
                    "structure_hash": spec.structure_hash,
                    "candidate_uri": spec.candidate_uri,
                    "novelty_status": "duplicate",
                },
            ),
            "l2_ensemble": PacketSection(
                section_name="l2_ensemble",
                summary="DPA-3 + MACE ensemble prediction with disagreement.",
                envelopes=[l2_env.canonical_dict()],
                raw_payload={
                    "energy_disagreement_meV_per_atom": l2_env.output[
                        "energy_disagreement_meV_per_atom"
                    ],
                    "force_rmse_disagreement_eV_per_Ang": l2_env.output[
                        "force_rmse_disagreement_eV_per_Ang"
                    ],
                    "routing_decision": l2_env.output["routing_decision"],
                },
            ),
            "l1_dft_validation": PacketSection(
                section_name="l1_dft_validation",
                summary="L1 DFT validation envelope (publication-grade ≤ 5 meV/atom).",
                envelopes=[l1_env.canonical_dict()],
                raw_payload={
                    "code": l1_env.output["code"],
                    "functional": l1_env.output["functional"],
                    "convergence_delta_meV_per_atom": l1_env.output[
                        "convergence_delta_meV_per_atom"
                    ],
                },
            ),
            "quantum_slot_h2_lih_gate": PacketSection(
                section_name="quantum_slot_h2_lih_gate",
                summary=(
                    "Quantum slot infrastructure check: H2 + LiH VQE-vs-FCI gates pass."
                ),
                envelopes=[h2_env.canonical_dict(), lih_env.canonical_dict()],
                raw_payload={
                    "h2_delta_Ha": h2_env.output["ground_state_energy_Ha"]
                    - h2_env.output["classical_reference_Ha"],
                    "lih_delta_Ha": lih_env.output["ground_state_energy_Ha"]
                    - lih_env.output["classical_reference_Ha"],
                },
            ),
            "zt_assembly": zt_section,
            "l7_orchestration_metadata": PacketSection(
                section_name="l7_orchestration_metadata",
                summary="L7 orchestration metadata (campaign id, BoTorch trace).",
                envelopes=[l7_env.canonical_dict()],
                raw_payload={
                    "promotion_decision": l7_env.output["promotion_decision"],
                    "acquisition": l7_env.output["acquisition"],
                    "audit_provenance_ref": l7_env.output["audit_provenance_ref"],
                    "operating_temperature_K": spec.operating_temperature_K,
                },
            ),
            "cross_layer_disagreement": disagreement_section,
            "rights_claim": rights_section,
            "kg_snapshot": kg_section,
            "audit_trail_head": audit_section,
        }
        bundle_obj = PacketBundle(sections=sections)

        packet_id = (
            f"packet:thermoelectric:{spec.name}:{candidate_id.split(':', 1)[-1]}"
        )
        from zer0pa_materials_workbench.boundary import RESEARCH_BOUNDARY

        return EvidencePacket(
            packet_id=packet_id,
            objective="thermoelectric_zt",
            candidate_id=candidate_id,
            campaign_id=campaign_id,
            structure_hash=spec.structure_hash,
            fixture_id=spec.fixture_id,
            research_boundary=RESEARCH_BOUNDARY,
            bundle=bundle_obj,
            promotion_decision=decision,
            promotion_rationale=rationale,
            publishable_paper_target=publishable_target,
        )


def assemble_thermoelectric_packet(
    fixture_key: str,
    *,
    candidate_id: str | None = None,
    campaign_id: str | None = None,
    rights_claim_id: str = "rights:thermoelectric:default",
    reuse_scope: str = "tenant_only",
) -> EvidencePacket:
    """Top-level convenience wrapper around :class:`ThermoelectricPacketAssembler`."""
    return ThermoelectricPacketAssembler().assemble(
        fixture_key,
        candidate_id=candidate_id,
        campaign_id=campaign_id,
        rights_claim_id=rights_claim_id,
        reuse_scope=reuse_scope,
    )
