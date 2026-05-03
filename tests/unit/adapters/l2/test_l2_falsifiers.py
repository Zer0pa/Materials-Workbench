"""Unit tests for L2 falsifiers — every falsifier must trigger correctly."""

from __future__ import annotations

import pytest

from zer0pa_materials_workbench.falsifiers.l2_falsifiers import (
    committee_uncertainty_threshold,
    dpa_mace_disagreement_routing,
    force_rmse_threshold,
    single_model_promotion_block,
    space_group_drift_threshold,
    uma_license_gate,
    volume_drift_threshold,
)


def _make_envelope(
    energy_disagreement_meV: float = 10.0,
    force_rmse_disagreement: float = 0.05,
    routing: str = "promote",
    predictions: list | None = None,
    uma_gate: dict | None = None,
    ensemble_meta: dict | None = None,
    disagreement_metrics: list | None = None,
) -> dict:
    if predictions is None:
        predictions = [
            {"model": "DPA-3.1-3M", "energy_eV_per_atom": -5.0, "force_rmse_eV_per_Ang": 0.05},
            {"model": "MACE-MPA-0", "energy_eV_per_atom": -5.01, "force_rmse_eV_per_Ang": 0.05},
        ]
    env = {
        "output": {
            "predictions": predictions,
            "energy_disagreement_meV_per_atom": energy_disagreement_meV,
            "force_rmse_disagreement_eV_per_Ang": force_rmse_disagreement,
            "routing_decision": routing,
        },
        "disagreement": {"metrics": disagreement_metrics or []},
    }
    if uma_gate is not None:
        env["_uma_gate"] = uma_gate
    if ensemble_meta is not None:
        env["_ensemble_meta"] = ensemble_meta
    return env


# ---------------------------------------------------------------------------
# dpa_mace_disagreement_routing
# ---------------------------------------------------------------------------

class TestDpaMaceDisagreementRouting:
    def test_pass_when_promote(self):
        env = _make_envelope(energy_disagreement_meV=10.0, routing="promote")
        result = dpa_mace_disagreement_routing(env)
        assert result.status == "pass"
        assert result.name == "l2.dpa_mace_disagreement_routing"

    def test_fail_when_queue_dft(self):
        env = _make_envelope(energy_disagreement_meV=30.0, routing="queue_dft")
        result = dpa_mace_disagreement_routing(env)
        assert result.status == "fail"

    def test_fail_when_hard_reject(self):
        env = _make_envelope(energy_disagreement_meV=95.0, routing="hard_reject")
        result = dpa_mace_disagreement_routing(env)
        assert result.status == "fail"

    def test_blocked_when_output_missing(self):
        result = dpa_mace_disagreement_routing({})
        assert result.status == "blocked"

    def test_blocked_when_energy_disagree_missing(self):
        env = {"output": {"routing_decision": "promote"}}
        result = dpa_mace_disagreement_routing(env)
        assert result.status == "blocked"

    def test_actual_is_energy_value(self):
        env = _make_envelope(energy_disagreement_meV=15.3, routing="promote")
        result = dpa_mace_disagreement_routing(env)
        assert result.actual == pytest.approx(15.3)


# ---------------------------------------------------------------------------
# single_model_promotion_block
# ---------------------------------------------------------------------------

class TestSingleModelPromotionBlock:
    def test_pass_when_two_models(self):
        env = _make_envelope(routing="promote")
        result = single_model_promotion_block(env)
        assert result.status == "pass"

    def test_fail_when_one_model_promotes(self):
        env = _make_envelope(
            routing="promote",
            predictions=[
                {"model": "DPA-3.1-3M", "energy_eV_per_atom": -5.0, "force_rmse_eV_per_Ang": 0.05}
            ],
        )
        result = single_model_promotion_block(env)
        assert result.status == "fail"

    def test_pass_when_one_model_but_queue_dft(self):
        """Single model with queue_dft routing is not a single_model_promotion_block fail."""
        env = _make_envelope(
            routing="queue_dft",
            predictions=[
                {"model": "DPA-3.1-3M", "energy_eV_per_atom": -5.0, "force_rmse_eV_per_Ang": 0.05}
            ],
        )
        result = single_model_promotion_block(env)
        assert result.status == "pass"

    def test_blocked_when_no_output(self):
        result = single_model_promotion_block({})
        assert result.status == "blocked"

    def test_actual_is_distinct_count(self):
        env = _make_envelope(routing="promote")
        result = single_model_promotion_block(env)
        assert result.actual == 2.0


# ---------------------------------------------------------------------------
# force_rmse_threshold
# ---------------------------------------------------------------------------

class TestForceRmseThreshold:
    def test_pass_below_015(self):
        env = _make_envelope(force_rmse_disagreement=0.05)
        result = force_rmse_threshold(env)
        assert result.status == "pass"

    def test_fail_between_015_and_035(self):
        env = _make_envelope(force_rmse_disagreement=0.20)
        result = force_rmse_threshold(env)
        assert result.status == "fail"

    def test_fail_above_035(self):
        env = _make_envelope(force_rmse_disagreement=0.40)
        result = force_rmse_threshold(env)
        assert result.status == "fail"

    def test_pass_at_015(self):
        env = _make_envelope(force_rmse_disagreement=0.15)
        result = force_rmse_threshold(env)
        assert result.status == "pass"

    def test_blocked_when_no_output(self):
        result = force_rmse_threshold({})
        assert result.status == "blocked"


# ---------------------------------------------------------------------------
# volume_drift_threshold
# ---------------------------------------------------------------------------

class TestVolumeDriftThreshold:
    def test_pass_when_no_drift_data(self):
        env = _make_envelope()
        result = volume_drift_threshold(env)
        assert result.status == "pass"
        assert result.actual is None

    def test_pass_when_drift_small(self):
        env = _make_envelope(ensemble_meta={"volume_drift_pct": 1.5})
        result = volume_drift_threshold(env)
        assert result.status == "pass"

    def test_fail_when_drift_large(self):
        env = _make_envelope(ensemble_meta={"volume_drift_pct": 3.5})
        result = volume_drift_threshold(env)
        assert result.status == "fail"

    def test_fail_at_exactly_2pct_plus(self):
        env = _make_envelope(ensemble_meta={"volume_drift_pct": 2.001})
        result = volume_drift_threshold(env)
        assert result.status == "fail"

    def test_actual_is_drift_value(self):
        env = _make_envelope(ensemble_meta={"volume_drift_pct": 1.0})
        result = volume_drift_threshold(env)
        assert result.actual == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# space_group_drift_threshold
# ---------------------------------------------------------------------------

class TestSpaceGroupDriftThreshold:
    def test_pass_when_no_data(self):
        env = _make_envelope()
        result = space_group_drift_threshold(env)
        assert result.status == "pass"

    def test_pass_when_agrees(self):
        env = _make_envelope(ensemble_meta={"space_group_agrees": True})
        result = space_group_drift_threshold(env)
        assert result.status == "pass"

    def test_fail_when_disagrees(self):
        env = _make_envelope(ensemble_meta={"space_group_agrees": False})
        result = space_group_drift_threshold(env)
        assert result.status == "fail"


# ---------------------------------------------------------------------------
# uma_license_gate
# ---------------------------------------------------------------------------

class TestUmaLicenseGate:
    def test_pass_when_no_uma(self):
        env = _make_envelope()
        result = uma_license_gate(env)
        assert result.status == "pass"

    def test_fail_when_uma_without_gate(self):
        env = _make_envelope(
            predictions=[
                {"model": "DPA-3.1-3M", "energy_eV_per_atom": -5.0, "force_rmse_eV_per_Ang": 0.05},
                {"model": "MACE-MPA-0", "energy_eV_per_atom": -5.01, "force_rmse_eV_per_Ang": 0.05},
                {"model": "UMA-s", "energy_eV_per_atom": -5.02, "force_rmse_eV_per_Ang": 0.05},
            ],
        )
        result = uma_license_gate(env)
        assert result.status == "fail"

    def test_pass_when_uma_with_gate(self):
        env = _make_envelope(
            predictions=[
                {"model": "DPA-3.1-3M", "energy_eV_per_atom": -5.0, "force_rmse_eV_per_Ang": 0.05},
                {"model": "MACE-MPA-0", "energy_eV_per_atom": -5.01, "force_rmse_eV_per_Ang": 0.05},
                {"model": "UMA-s", "energy_eV_per_atom": -5.02, "force_rmse_eV_per_Ang": 0.05},
            ],
            uma_gate={
                "hf_org": "zer0pa-materials",
                "hf_token_hint": "hf_...1234",
                "aup_accepted_at": "2026-04-30T12:00:00+00:00",
            },
        )
        result = uma_license_gate(env)
        assert result.status == "pass"

    def test_fail_when_uma_partial_gate(self):
        """Gate present but missing aup_accepted_at → fail."""
        env = _make_envelope(
            predictions=[
                {"model": "UMA-s", "energy_eV_per_atom": -5.0, "force_rmse_eV_per_Ang": 0.05},
            ],
            uma_gate={"hf_org": "zer0pa", "aup_accepted_at": None},
        )
        result = uma_license_gate(env)
        assert result.status == "fail"

    def test_blocked_when_no_output(self):
        result = uma_license_gate({})
        assert result.status == "blocked"


# ---------------------------------------------------------------------------
# committee_uncertainty_threshold
# ---------------------------------------------------------------------------

class TestCommitteeUncertaintyThreshold:
    def test_pass_when_no_committee_data(self):
        env = _make_envelope()
        result = committee_uncertainty_threshold(env)
        assert result.status == "pass"

    def test_pass_when_variance_below_threshold(self):
        env = _make_envelope(
            disagreement_metrics=[
                {"name": "mace_committee_energy_variance", "value": 5.0, "unit": "meV^2/atom"}
            ]
        )
        result = committee_uncertainty_threshold(env, threshold_meV=10.0)
        assert result.status == "pass"

    def test_fail_when_variance_above_threshold(self):
        env = _make_envelope(
            disagreement_metrics=[
                {"name": "mace_committee_energy_variance", "value": 15.0, "unit": "meV^2/atom"}
            ]
        )
        result = committee_uncertainty_threshold(env, threshold_meV=10.0)
        assert result.status == "fail"

    def test_pass_with_dpa_committee_metric(self):
        env = _make_envelope(
            disagreement_metrics=[
                {"name": "dpa_committee_energy_variance", "value": 3.0, "unit": "meV^2/atom"}
            ]
        )
        result = committee_uncertainty_threshold(env, threshold_meV=10.0)
        assert result.status == "pass"

    def test_custom_threshold(self):
        env = _make_envelope(
            disagreement_metrics=[
                {"name": "mace_committee_energy_variance", "value": 2.0, "unit": "meV^2/atom"}
            ]
        )
        result = committee_uncertainty_threshold(env, threshold_meV=1.0)
        assert result.status == "fail"
