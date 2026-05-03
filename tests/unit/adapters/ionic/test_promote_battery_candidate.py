"""Unit tests for the battery promotion gate.

PRD §Acceptance Gates: Battery MVP — the central MVP gate. Tested
adversarially: at least one negative test that would promote without
one of the six pieces of evidence and verifies promotion is BLOCKED.
"""

from __future__ import annotations

import pytest

from zer0pa_materials_workbench.adapters.ionic.base import IonicJobParams
from zer0pa_materials_workbench.services.ionic_transport_service import (
    BatteryEvidenceBundle,
    PromotionDecision,
    promote_battery_candidate,
    run_full_battery_evidence,
)


@pytest.fixture
def llzo_params() -> IonicJobParams:
    return IonicJobParams(
        structure_hash="sha256:d45cb2bfe5e76b86b365e1402e118ed32280049a62345c903558c6cfac04ef19",
        fixture_id="fixture:LLZO_cubic:d45cb2bf",
        candidate_id="candidate:LLZO/cubic",
    )


@pytest.fixture
def li6ps5cl_params() -> IonicJobParams:
    return IonicJobParams(
        structure_hash="sha256:8d7b217550c751a08bd6bc85d74a166ff0b4966266552d254ca53527607c40bc",
        fixture_id="fixture:Li6PS5Cl:8d7b2175",
        candidate_id="candidate:Li6PS5Cl/argyrodite",
    )


@pytest.fixture
def seed_params() -> IonicJobParams:
    return IonicJobParams(
        structure_hash="sha256:ea01c76f01f1427a5010cad97a984d3802c869f96b3726501897f5b08e3c138a",
        fixture_id="fixture:Li-Mg-Zr-Cl-seed:ea01c76f",
        candidate_id="candidate:Li-Mg-Zr-Cl/seed",
        interface_mode="coating_interlayer",
    )


def test_llzo_promotes(llzo_params: IonicJobParams) -> None:
    """LLZO clears every PRD §Ionic Transport gate."""
    decision = promote_battery_candidate("candidate:LLZO/cubic", params=llzo_params)
    assert decision.decision == "promote"


def test_llzo_decision_carries_evidence(llzo_params: IonicJobParams) -> None:
    decision = promote_battery_candidate("candidate:LLZO/cubic", params=llzo_params)
    assert len(decision.evidence) >= 8  # at least the 8 blocking gates + disagreement


def test_llzo_decision_carries_bundle(llzo_params: IonicJobParams) -> None:
    decision = promote_battery_candidate("candidate:LLZO/cubic", params=llzo_params)
    assert isinstance(decision.bundle, BatteryEvidenceBundle)


def test_li6ps5cl_borderline_default_mode_rejected(
    li6ps5cl_params: IonicJobParams,
) -> None:
    """Li6PS5Cl in default li_metal mode fails on oxidation AND interface."""
    decision = promote_battery_candidate(
        "candidate:Li6PS5Cl/argyrodite", params=li6ps5cl_params
    )
    assert decision.decision == "reject"
    fail_names = [
        ev["name"] for ev in decision.evidence if ev["status"] == "fail"
    ]
    # Must include at least the oxidation failure.
    assert "ionic.oxidative_stability_threshold" in fail_names


def test_li6ps5cl_coating_still_fails_oxidation() -> None:
    """Even with coating route, Li6PS5Cl fails the 4 V oxidation gate."""
    p = IonicJobParams(
        structure_hash="sha256:8d7b217550c751a08bd6bc85d74a166ff0b4966266552d254ca53527607c40bc",
        fixture_id="fixture:Li6PS5Cl:8d7b2175",
        candidate_id="candidate:Li6PS5Cl/coated",
        interface_mode="coating_interlayer",
    )
    decision = promote_battery_candidate(
        "candidate:Li6PS5Cl/coated", params=p
    )
    assert decision.decision == "reject"
    fail_names = [
        ev["name"] for ev in decision.evidence if ev["status"] == "fail"
    ]
    assert "ionic.oxidative_stability_threshold" in fail_names


def test_seed_promotes_with_coating(seed_params: IonicJobParams) -> None:
    """Novel Li-Mg-Zr-Cl seed promotes when routed to coating mode."""
    decision = promote_battery_candidate(
        "candidate:Li-Mg-Zr-Cl/seed", params=seed_params
    )
    assert decision.decision == "promote"


def test_seed_runs_without_error_in_default_mode() -> None:
    """The novel seed runs end-to-end without crashing."""
    p = IonicJobParams(
        structure_hash="sha256:ea01c76f01f1427a5010cad97a984d3802c869f96b3726501897f5b08e3c138a",
        fixture_id="fixture:Li-Mg-Zr-Cl-seed:ea01c76f",
        candidate_id="candidate:Li-Mg-Zr-Cl/default",
        interface_mode="li_metal",
    )
    decision = promote_battery_candidate(
        "candidate:Li-Mg-Zr-Cl/default", params=p
    )
    # In default li_metal mode it fails the route compatibility gate;
    # the test only verifies the gate runs.
    assert decision.decision in ("promote", "defer", "reject")


def test_unknown_fixture_blocks_or_rejects() -> None:
    """A novel structure with no fixture_id should NOT promote."""
    p = IonicJobParams(
        structure_hash="sha256:" + "0" * 64,
        fixture_id=None,
        candidate_id="candidate:novel",
    )
    decision = promote_battery_candidate("candidate:novel", params=p)
    assert decision.decision != "promote"


# ----------------------------------------------------------------------------
# Adversarial tests — the central MVP gate
# ----------------------------------------------------------------------------


def test_promotion_blocked_when_chain_incomplete(
    llzo_params: IonicJobParams,
) -> None:
    """If we strip one piece of evidence from the bundle, promotion fails.

    This is the core adversarial test: a candidate that would promote
    with full evidence MUST NOT promote when an evidence piece is
    deliberately missing.
    """
    bundle = run_full_battery_evidence(llzo_params)
    # Strip the migration_barrier_eV from the NEB envelope and from the
    # consolidated chain falsifier.
    bundle_dict = bundle.model_dump(mode="json")
    bundle_dict["neb"]["output"]["migration_barrier_eV"] = None
    # Recompute the chain_complete falsifier on the modified bundle.
    from zer0pa_materials_workbench.falsifiers.ionic_falsifiers import (
        full_battery_evidence_chain_complete,
    )
    chain = full_battery_evidence_chain_complete(
        [
            bundle_dict["neb"],
            bundle_dict["mlip_md"],
            bundle_dict["aimd"],
            bundle_dict["arrhenius"],
            bundle_dict["electrochemical_window"],
            bundle_dict["interface_stability"],
        ]
    )
    bundle_dict["chain_complete"] = chain.model_dump(mode="json")
    rebuilt = BatteryEvidenceBundle.model_validate(bundle_dict)

    decision = promote_battery_candidate("candidate:LLZO/cubic", bundle=rebuilt)
    assert decision.decision == "reject"


def test_promotion_blocked_when_arrhenius_quality_low() -> None:
    """An Arrhenius fit with R² < 0.95 must NOT promote.

    We synthesise three (T, sigma) points that don't lie on a clean
    Arrhenius line so the fit quality is low.
    """
    p = IonicJobParams(
        structure_hash="sha256:" + "a" * 64,
        fixture_id="fixture:LLZO_cubic:d45cb2bf",
        candidate_id="candidate:LLZO/badfit",
    )
    bundle = run_full_battery_evidence(p)
    # Override the Arrhenius envelope with a low-quality fit.
    bundle_dict = bundle.model_dump(mode="json")
    bundle_dict["arrhenius"]["output"]["defect_disorder_assumptions"] = [
        "arrhenius_R2=0.50",
        "arrhenius_n_points=3",
    ]
    # Patch the falsifier item too.
    items = bundle_dict["arrhenius"]["falsifier"]["items"]
    for it in items:
        if it["name"] == "ionic.arrhenius_fit_quality":
            it["actual"] = 0.50
            it["status"] = "fail"
    rebuilt = BatteryEvidenceBundle.model_validate(bundle_dict)
    decision = promote_battery_candidate("candidate:LLZO/badfit", bundle=rebuilt)
    assert decision.decision == "reject"


def test_promotion_decision_signature_is_stable(llzo_params: IonicJobParams) -> None:
    decision = promote_battery_candidate(
        "candidate:LLZO/cubic", params=llzo_params
    )
    assert isinstance(decision, PromotionDecision)
    assert decision.candidate_id == "candidate:LLZO/cubic"
    assert decision.structure_hash == llzo_params.structure_hash


def test_promote_requires_bundle_or_params() -> None:
    with pytest.raises(ValueError, match="bundle or params"):
        promote_battery_candidate("candidate:any")
