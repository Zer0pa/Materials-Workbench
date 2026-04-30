"""Test the AcceptanceGate composition.

Covers the seven sub-gates from PRD §L7 Falsifiers:
  1. boundary block
  2. audit provenance
  3. cross-layer disagreement
  4. rights / reuse-scope
  5. duplicate-rejection
  6. layer-specific falsifiers
  7. ionic battery evidence (optional)
"""

from __future__ import annotations

from typing import Any

import pytest

from zer0pa_materials.audit.rights import RightsClaim
from zer0pa_materials.boundary import RESEARCH_BOUNDARY
from zer0pa_materials.envelope import (
    AuditBlock,
    Envelope,
    FalsifierBlock,
    FalsifierItem,
    IonicTransportOutput,
    L1DftOutput,
    L2MlipOutput,
    L6GenerativeOutput,
    RightsBlock,
    ToolAdapter,
    sha256_of,
)
from zer0pa_materials.envelope.layer_outputs import L2ModelPrediction, L6DedupResult
from zer0pa_materials.orchestration.acceptance_gates import (
    AcceptanceGate,
    GateContext,
)


# ---------------------------------------------------------------------------
# Builder helpers
# ---------------------------------------------------------------------------


def _audit_id(suffix: str) -> str:
    return f"audit:test:{suffix}"


def _envelope(
    layer: str,
    output_dict: dict[str, Any],
    rights_scope: str = "tenant_only",
    rights_claim_id: str = "rights:test:claim-1",
    falsifier_status: str = "pass",
    falsifier_items: list[FalsifierItem] | None = None,
    audit_id: str | None = None,
    research_boundary: str = RESEARCH_BOUNDARY,
) -> Envelope:
    audit_id = audit_id or _audit_id(layer)
    return Envelope(
        research_boundary=research_boundary,
        run_id=f"run:test:{layer}",
        campaign_id="campaign:test/mvp",
        candidate_id="candidate:test/llzo-1",
        layer=layer,  # type: ignore[arg-type]
        tool_adapter=ToolAdapter(name=f"{layer}-stub", version="0.1.0", backend="stub", engine=f"{layer}-stub"),
        input_refs=[],
        output=output_dict,
        falsifier=FalsifierBlock(
            status=falsifier_status,  # type: ignore[arg-type]
            items=falsifier_items or [],
        ),
        audit=AuditBlock(
            audit_record_id=audit_id,
            input_hash=sha256_of({"layer": layer, "in": "x"}),
            output_hash=sha256_of(output_dict),
        ),
        rights=RightsBlock(
            rights_claim_id=rights_claim_id,
            reuse_scope=rights_scope,  # type: ignore[arg-type]
        ),
    )


def _l6_envelope(rights_scope: str = "tenant_only") -> Envelope:
    out = L6GenerativeOutput(
        candidate_uri="file:///tmp/c.cif",
        structure_hash="sha256:" + "a" * 64,
        novelty_status="novel",
        dedup_results=[L6DedupResult(source="MP", matched=False)],
    )
    return _envelope("L6", out.model_dump(mode="json"), rights_scope=rights_scope, falsifier_items=out.falsifier_items())


def _l1_envelope(rights_scope: str = "tenant_only") -> Envelope:
    out = L1DftOutput(
        code="QE",
        functional="PBE",
        total_energy_eV=-100.0,
        force_rmse_eV_per_Ang=0.01,
        kpoint_mesh=[4, 4, 4],
        convergence_delta_meV_per_atom=2.0,
        publication_grade=True,
    )
    return _envelope("L1", out.model_dump(mode="json"), rights_scope=rights_scope, falsifier_items=out.falsifier_items())


def _l2_envelope(rights_scope: str = "tenant_only") -> Envelope:
    out = L2MlipOutput(
        predictions=[
            L2ModelPrediction(model="DPA-3.1-3M", energy_eV_per_atom=-1.0, force_rmse_eV_per_Ang=0.05),
            L2ModelPrediction(model="MACE-MPA-0", energy_eV_per_atom=-1.01, force_rmse_eV_per_Ang=0.06),
        ],
        energy_disagreement_meV_per_atom=10.0,
        force_rmse_disagreement_eV_per_Ang=0.05,
        routing_decision="promote",
    )
    return _envelope("L2", out.model_dump(mode="json"), rights_scope=rights_scope, falsifier_items=out.falsifier_items())


def _ionic_envelope_complete(rights_scope: str = "tenant_only") -> Envelope:
    out = IonicTransportOutput(
        migration_barrier_eV=0.30,
        msd_A2=10.0,
        diffusion_coefficient_cm2_per_s=1e-7,
        nernst_einstein_conductivity_S_per_cm=2e-3,
        arrhenius={"activation_energy_eV": 0.30, "activation_energy_uncertainty_eV": 0.02},  # type: ignore[arg-type]
        electrochemical_window_V_vs_LiLi=(0.0, 4.5),
        interface_stability="li_metal_stable",
        defect_disorder_assumptions=["Li/La antisite ordered"],
        confidence=0.8,
    )
    return _envelope("ionic", out.model_dump(mode="json"), rights_scope=rights_scope, falsifier_items=out.falsifier_items())


def _rights_claim(scope: str = "tenant_only") -> RightsClaim:
    return RightsClaim(
        rights_claim_id="rights:test:claim-1",
        tenant="test",
        data_class="raw_simulation_output",
        ownership="customer",
        reuse_scope=scope,  # type: ignore[arg-type]
        contract_mode="strict_sovereign",
        rationale="test fixture",
    )


# ---------------------------------------------------------------------------
# Composition tests
# ---------------------------------------------------------------------------


def test_full_pass():
    """LLZO-shaped candidate clears every gate."""
    ctx = GateContext(
        candidate_id="candidate:test/llzo-1",
        campaign_id="campaign:test/mvp",
        layer_envelopes={
            "L6": _l6_envelope(),
            "L2": _l2_envelope(),
            "L1": _l1_envelope(),
            "ionic": _ionic_envelope_complete(),
        },
        rights_claim=_rights_claim(),
        aggregate_disagreement_score=0.2,
        expected_layers=("L6", "L2", "L1", "ionic"),
    )
    gate = AcceptanceGate()
    verdict = gate.evaluate(ctx)
    assert verdict.overall == "pass", verdict.rationale
    assert verdict.failure_reasons == []


def test_missing_audit_record_id_blocks():
    """An envelope with empty audit_record_id (impossible structurally) is detected via the chain check."""
    # We can't construct an envelope with empty audit_record_id (validators forbid).
    # Instead, supply a non-empty chain and a non-anchored record.
    ctx = GateContext(
        candidate_id="candidate:test/llzo-1",
        campaign_id="campaign:test/mvp",
        layer_envelopes={"L6": _l6_envelope(), "L2": _l2_envelope(), "L1": _l1_envelope()},
        rights_claim=_rights_claim(),
        aggregate_disagreement_score=0.2,
        audit_provenance_chain={"audit:test:nope"},  # neither L6 nor L2 nor L1 audit IDs
        expected_layers=("L6", "L2", "L1"),
    )
    verdict = AcceptanceGate(include_ionic_battery_evidence=False).evaluate(ctx)
    assert verdict.overall == "fail"
    assert "missing_audit_provenance" in verdict.failure_reasons


def test_disagreement_above_threshold_fails():
    ctx = GateContext(
        candidate_id="candidate:test/llzo-1",
        campaign_id="campaign:test/mvp",
        layer_envelopes={"L6": _l6_envelope(), "L2": _l2_envelope(), "L1": _l1_envelope()},
        rights_claim=_rights_claim(),
        aggregate_disagreement_score=0.9,
        disagreement_threshold=0.5,
        expected_layers=("L6", "L2", "L1"),
    )
    verdict = AcceptanceGate(include_ionic_battery_evidence=False).evaluate(ctx)
    assert verdict.overall == "fail"
    assert "disagreement_above_threshold" in verdict.failure_reasons


def test_disagreement_missing_blocks():
    ctx = GateContext(
        candidate_id="candidate:test/llzo-1",
        campaign_id="campaign:test/mvp",
        layer_envelopes={"L6": _l6_envelope(), "L2": _l2_envelope(), "L1": _l1_envelope()},
        rights_claim=_rights_claim(),
        aggregate_disagreement_score=None,
        expected_layers=("L6", "L2", "L1"),
    )
    verdict = AcceptanceGate(include_ionic_battery_evidence=False).evaluate(ctx)
    assert verdict.overall in ("blocked", "fail")
    assert "disagreement_above_threshold" in verdict.failure_reasons


def test_rights_violation_fails():
    """Envelope with reuse_scope='shared_learning' under tenant_only claim fails."""
    bad_l1 = _l1_envelope(rights_scope="shared_learning")
    ctx = GateContext(
        candidate_id="candidate:test/llzo-1",
        campaign_id="campaign:test/mvp",
        layer_envelopes={"L6": _l6_envelope(), "L2": _l2_envelope(), "L1": bad_l1},
        rights_claim=_rights_claim(scope="tenant_only"),
        aggregate_disagreement_score=0.1,
        expected_layers=("L6", "L2", "L1"),
    )
    verdict = AcceptanceGate(include_ionic_battery_evidence=False).evaluate(ctx)
    assert verdict.overall == "fail"
    assert "reuse_scope_violation" in verdict.failure_reasons


def test_duplicate_of_rejected_candidate_fails():
    ctx = GateContext(
        candidate_id="candidate:test/llzo-1",
        campaign_id="campaign:test/mvp",
        layer_envelopes={"L6": _l6_envelope(), "L2": _l2_envelope(), "L1": _l1_envelope()},
        rights_claim=_rights_claim(),
        aggregate_disagreement_score=0.1,
        rejected_candidate_ids={"candidate:test/llzo-1"},
        expected_layers=("L6", "L2", "L1"),
    )
    verdict = AcceptanceGate(include_ionic_battery_evidence=False).evaluate(ctx)
    assert verdict.overall == "fail"
    assert "duplicate_of_rejected_candidate" in verdict.failure_reasons


def test_missing_expected_layer_blocks():
    ctx = GateContext(
        candidate_id="candidate:test/llzo-1",
        campaign_id="campaign:test/mvp",
        layer_envelopes={"L6": _l6_envelope()},
        rights_claim=_rights_claim(),
        aggregate_disagreement_score=0.1,
        expected_layers=("L6", "L2", "L1"),
    )
    verdict = AcceptanceGate(include_ionic_battery_evidence=False).evaluate(ctx)
    assert verdict.overall in ("blocked", "fail")


def test_ionic_evidence_complete_passes():
    ctx = GateContext(
        candidate_id="candidate:test/llzo-1",
        campaign_id="campaign:test/mvp",
        layer_envelopes={
            "L6": _l6_envelope(),
            "L2": _l2_envelope(),
            "L1": _l1_envelope(),
            "ionic": _ionic_envelope_complete(),
        },
        rights_claim=_rights_claim(),
        aggregate_disagreement_score=0.1,
        expected_layers=("L6", "L2", "L1", "ionic"),
    )
    verdict = AcceptanceGate(include_ionic_battery_evidence=True).evaluate(ctx)
    assert verdict.overall == "pass"


def test_ionic_evidence_incomplete_blocks():
    bad_ionic = _envelope(
        "ionic",
        IonicTransportOutput(
            migration_barrier_eV=None,  # missing
            interface_stability="unknown",
        ).model_dump(mode="json"),
    )
    ctx = GateContext(
        candidate_id="candidate:test/llzo-1",
        campaign_id="campaign:test/mvp",
        layer_envelopes={
            "L6": _l6_envelope(),
            "L2": _l2_envelope(),
            "L1": _l1_envelope(),
            "ionic": bad_ionic,
        },
        rights_claim=_rights_claim(),
        aggregate_disagreement_score=0.1,
        expected_layers=("L6", "L2", "L1", "ionic"),
    )
    verdict = AcceptanceGate(include_ionic_battery_evidence=True).evaluate(ctx)
    assert verdict.overall == "fail"
    assert "ionic_evidence_incomplete" in verdict.failure_reasons


def test_battery_seeds_compose():
    """LLZO promotes; Li6PS5Cl rejects on oxidation; Li-Mg-Zr-Cl with coating_interlayer promotes.

    This exercises the full composition with the three battery seeds the
    PRD calls out (LLZO/Li6PS5Cl/Li-Mg-Zr-Cl).
    """
    # LLZO — promote.
    llzo_ionic = _ionic_envelope_complete()
    ctx_llzo = GateContext(
        candidate_id="candidate:test/llzo",
        campaign_id="campaign:test/mvp",
        layer_envelopes={
            "L6": _l6_envelope(),
            "L2": _l2_envelope(),
            "L1": _l1_envelope(),
            "ionic": llzo_ionic,
        },
        rights_claim=_rights_claim(),
        aggregate_disagreement_score=0.1,
        expected_layers=("L6", "L2", "L1", "ionic"),
    )
    assert AcceptanceGate().evaluate(ctx_llzo).overall == "pass"

    # Li6PS5Cl — fail on oxidation (window upper edge < 4.0 V).
    li6ps5cl_out = IonicTransportOutput(
        migration_barrier_eV=0.20,
        msd_A2=10.0,
        diffusion_coefficient_cm2_per_s=1e-7,
        nernst_einstein_conductivity_S_per_cm=2e-3,
        arrhenius={"activation_energy_eV": 0.20, "activation_energy_uncertainty_eV": 0.02},  # type: ignore[arg-type]
        electrochemical_window_V_vs_LiLi=(0.0, 2.5),  # ox window low → fails 4.0 threshold
        interface_stability="li_metal_unstable_coating_required",
        defect_disorder_assumptions=["S/Cl mixing"],
        confidence=0.6,
    )
    li6ps5cl_env = _envelope(
        "ionic",
        li6ps5cl_out.model_dump(mode="json"),
        falsifier_items=li6ps5cl_out.falsifier_items(),
    )
    ctx_li6ps5cl = GateContext(
        candidate_id="candidate:test/li6ps5cl",
        campaign_id="campaign:test/mvp",
        layer_envelopes={
            "L6": _l6_envelope(),
            "L2": _l2_envelope(),
            "L1": _l1_envelope(),
            "ionic": li6ps5cl_env,
        },
        rights_claim=_rights_claim(),
        aggregate_disagreement_score=0.1,
        expected_layers=("L6", "L2", "L1", "ionic"),
    )
    v = AcceptanceGate().evaluate(ctx_li6ps5cl)
    assert v.overall == "fail"  # oxidation gate fails inside the layer falsifiers
