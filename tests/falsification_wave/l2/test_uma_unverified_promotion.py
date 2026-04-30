"""Falsification wave: UMA without verified license triggers uma_license_gate.

Synthetic L2 envelope claims a UMA prediction but omits the _uma_gate record.
The ``uma_license_gate`` falsifier MUST return status == "fail".
"""

from __future__ import annotations

import pytest

from zer0pa_materials.falsifiers.l2_falsifiers import (
    dpa_mace_disagreement_routing,
    single_model_promotion_block,
    uma_license_gate,
)


def _make_uma_envelope(include_gate: bool = False, gate_complete: bool = True) -> dict:
    """Synthetic L2 envelope with UMA prediction."""
    env = {
        "output": {
            "predictions": [
                {"model": "DPA-3.1-3M", "energy_eV_per_atom": -5.0, "force_rmse_eV_per_Ang": 0.05},
                {"model": "MACE-MPA-0", "energy_eV_per_atom": -5.01, "force_rmse_eV_per_Ang": 0.05},
                {"model": "UMA-s", "energy_eV_per_atom": -5.02, "force_rmse_eV_per_Ang": 0.05},
            ],
            "energy_disagreement_meV_per_atom": 10.0,
            "force_rmse_disagreement_eV_per_Ang": 0.01,
            "routing_decision": "promote",
        },
        "disagreement": {"metrics": []},
    }
    if include_gate:
        if gate_complete:
            env["_uma_gate"] = {
                "hf_org": "zer0pa-materials",
                "hf_token_hint": "hf_...9999",
                "aup_accepted_at": "2026-04-30T12:00:00+00:00",
            }
        else:
            env["_uma_gate"] = {
                "hf_org": "zer0pa-materials",
                "aup_accepted_at": None,
            }
    return env


class TestUmaUnverifiedPromotion:
    def test_uma_without_gate_fails(self):
        """Synthetic UMA envelope without _uma_gate → uma_license_gate fails."""
        env = _make_uma_envelope(include_gate=False)
        result = uma_license_gate(env)
        assert result.status == "fail", (
            f"Expected 'fail' but got '{result.status}'. UMA used without license gate."
        )

    def test_uma_name_in_actual(self):
        env = _make_uma_envelope(include_gate=False)
        result = uma_license_gate(env)
        # actual should be the count of UMA models.
        assert result.actual == 1.0

    def test_uma_with_complete_gate_passes(self):
        env = _make_uma_envelope(include_gate=True, gate_complete=True)
        result = uma_license_gate(env)
        assert result.status == "pass"

    def test_uma_with_incomplete_gate_fails(self):
        """Partial gate (aup_accepted_at=None) → fail."""
        env = _make_uma_envelope(include_gate=True, gate_complete=False)
        result = uma_license_gate(env)
        assert result.status == "fail"

    def test_dpa_mace_routing_passes_for_uma_envelope(self):
        """The UMA envelope has low energy disagreement → routing passes."""
        env = _make_uma_envelope(include_gate=False)
        result = dpa_mace_disagreement_routing(env)
        assert result.status == "pass"

    def test_single_model_block_passes_for_three_models(self):
        """Three distinct models present, routing=promote → single_model_block passes."""
        env = _make_uma_envelope(include_gate=False)
        result = single_model_promotion_block(env)
        assert result.status == "pass"


class TestUmaFalsifierNameAndThreshold:
    def test_falsifier_name_correct(self):
        env = _make_uma_envelope(include_gate=False)
        result = uma_license_gate(env)
        assert result.name == "l2.uma_license_gate"

    def test_threshold_mentions_fair_chem(self):
        env = _make_uma_envelope(include_gate=False)
        result = uma_license_gate(env)
        assert "FAIR Chemistry" in result.threshold

    def test_threshold_mentions_hf_org(self):
        env = _make_uma_envelope(include_gate=False)
        result = uma_license_gate(env)
        assert "hf_org" in result.threshold


class TestNoUmaNoFire:
    def test_no_uma_envelope_gate_does_not_fire(self):
        """Envelope with only DPA and MACE → uma_license_gate passes."""
        env = {
            "output": {
                "predictions": [
                    {"model": "DPA-3.1-3M", "energy_eV_per_atom": -5.0, "force_rmse_eV_per_Ang": 0.05},
                    {"model": "MACE-MPA-0", "energy_eV_per_atom": -5.01, "force_rmse_eV_per_Ang": 0.05},
                ],
                "energy_disagreement_meV_per_atom": 10.0,
                "force_rmse_disagreement_eV_per_Ang": 0.01,
                "routing_decision": "promote",
            },
            "disagreement": {"metrics": []},
        }
        result = uma_license_gate(env)
        assert result.status == "pass"
