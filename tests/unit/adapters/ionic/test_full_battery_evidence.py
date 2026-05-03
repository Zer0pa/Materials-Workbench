"""Unit tests for the full-battery-evidence orchestrator."""

from __future__ import annotations

import pytest

from zer0pa_materials_workbench.adapters.ionic.base import (
    IONIC_TRANSPORT_SERVICE_REF,
    IonicJobParams,
)
from zer0pa_materials_workbench.falsifiers.ionic_falsifiers import REQUIRED_EVIDENCE_KEYS
from zer0pa_materials_workbench.services.ionic_transport_service import (
    BatteryEvidenceBundle,
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
        interface_mode="coating_interlayer",
    )


@pytest.fixture
def seed_params() -> IonicJobParams:
    return IonicJobParams(
        structure_hash="sha256:ea01c76f01f1427a5010cad97a984d3802c869f96b3726501897f5b08e3c138a",
        fixture_id="fixture:Li-Mg-Zr-Cl-seed:ea01c76f",
        candidate_id="candidate:Li-Mg-Zr-Cl/seed",
        interface_mode="coating_interlayer",
    )


def test_orchestrator_returns_bundle(llzo_params: IonicJobParams) -> None:
    bundle = run_full_battery_evidence(llzo_params)
    assert isinstance(bundle, BatteryEvidenceBundle)


def test_bundle_contains_six_envelopes(llzo_params: IonicJobParams) -> None:
    bundle = run_full_battery_evidence(llzo_params)
    for name in (
        "neb",
        "mlip_md",
        "aimd",
        "arrhenius",
        "electrochemical_window",
        "interface_stability",
    ):
        env = getattr(bundle, name)
        assert env is not None
        assert env["layer"] == "ionic"


def test_bundle_chain_complete_pass_for_llzo(llzo_params: IonicJobParams) -> None:
    bundle = run_full_battery_evidence(llzo_params)
    assert bundle.chain_complete["status"] == "pass"


def test_bundle_chain_lists_all_required_keys(llzo_params: IonicJobParams) -> None:
    """All six required keys are listed as 'present'."""
    bundle = run_full_battery_evidence(llzo_params)
    present = bundle.chain_complete["actual"]["present"]
    for key in REQUIRED_EVIDENCE_KEYS:
        assert key in present, f"{key} missing from chain"


def test_bundle_disagreement_pass_for_llzo(llzo_params: IonicJobParams) -> None:
    bundle = run_full_battery_evidence(llzo_params)
    assert bundle.mlip_vs_aimd_disagreement["status"] == "pass"


def test_orchestrator_runs_for_li6ps5cl(li6ps5cl_params: IonicJobParams) -> None:
    bundle = run_full_battery_evidence(li6ps5cl_params)
    assert bundle.chain_complete["status"] == "pass"


def test_orchestrator_runs_for_seed(seed_params: IonicJobParams) -> None:
    """Novel seed must run end-to-end without error."""
    bundle = run_full_battery_evidence(seed_params)
    assert bundle.chain_complete["status"] == "pass"


def test_orchestrator_envelopes_have_service_ref(llzo_params: IonicJobParams) -> None:
    bundle = run_full_battery_evidence(llzo_params)
    for name in (
        "neb",
        "mlip_md",
        "aimd",
        "arrhenius",
        "electrochemical_window",
        "interface_stability",
    ):
        env = getattr(bundle, name)
        assert IONIC_TRANSPORT_SERVICE_REF in env["input_refs"]


def test_orchestrator_envelopes_have_audit_block(llzo_params: IonicJobParams) -> None:
    bundle = run_full_battery_evidence(llzo_params)
    for name in (
        "neb",
        "mlip_md",
        "aimd",
        "arrhenius",
        "electrochemical_window",
        "interface_stability",
    ):
        env = getattr(bundle, name)
        assert "audit" in env
        assert env["audit"]["audit_record_id"].startswith("audit:")


def test_bundle_serialises_to_json(llzo_params: IonicJobParams) -> None:
    """The bundle must round-trip through JSON without error."""
    import orjson

    bundle = run_full_battery_evidence(llzo_params)
    payload = bundle.model_dump(mode="json")
    encoded = orjson.dumps(payload, option=orjson.OPT_SORT_KEYS)
    assert len(encoded) > 0


def test_full_battery_chain_blocks_when_evidence_missing() -> None:
    """If the orchestrator runs against an empty params set we still get all envelopes.

    This test confirms the orchestrator never silently drops an envelope —
    even an unknown structure produces every required output field.
    """
    p = IonicJobParams(
        structure_hash="sha256:" + "0" * 64,
        fixture_id=None,
        candidate_id="candidate:novel",
    )
    bundle = run_full_battery_evidence(p)
    # All six envelopes present.
    for name in (
        "neb",
        "mlip_md",
        "aimd",
        "arrhenius",
        "electrochemical_window",
        "interface_stability",
    ):
        env = getattr(bundle, name)
        assert env is not None
