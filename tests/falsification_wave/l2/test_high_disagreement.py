"""Falsification wave test: high_disagreement fixture triggers hard_reject.

PRD mandate (PRD §L2 Falsifiers + PRD §Falsification wave):
    The ``fixtures/negatives/high_disagreement/`` fixture contains a synthetic
    L2 envelope with energy_disagreement_meV_per_atom = 95.0 (> 75 hard-reject
    threshold).  This test verifies that:

    1. ``dpa_mace_disagreement_routing`` returns status == "fail".
    2. The ``routing_decision`` in the fixture is "hard_reject".
    3. No other L2 falsifier in the fixture triggers independently
       (the energy disagreement is the ONLY load-bearing failure — the
       force_rmse_disagreement = 0.10 is between the promote (0.15) and
       hard-reject (0.35) bands, so it does NOT independently fail).
"""

from __future__ import annotations

import json
from pathlib import Path

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

FIXTURE_DIR = Path(__file__).parent.parent.parent.parent / "fixtures" / "negatives" / "high_disagreement"
FIXTURE_FILE = FIXTURE_DIR / "l2_result.json"


@pytest.fixture(scope="module")
def high_disagreement_fixture() -> dict:
    """Load the high_disagreement fixture as a wire-level envelope dict."""
    with FIXTURE_FILE.open() as f:
        raw = json.load(f)

    # The fixture stores data at the top level (not wrapped in Envelope).
    # Wrap it in the envelope-like structure that falsifiers expect.
    return {
        "output": {
            "predictions": raw.get("predictions", []),
            "energy_disagreement_meV_per_atom": raw["energy_disagreement_meV_per_atom"],
            "force_rmse_disagreement_eV_per_Ang": raw["force_rmse_disagreement_eV_per_Ang"],
            "routing_decision": raw["routing_decision"],
        },
        "research_boundary": raw.get("research_boundary", ""),
        "disagreement": {"metrics": []},
    }


class TestHighDisagreementFixtureExists:
    def test_fixture_file_exists(self):
        assert FIXTURE_FILE.exists(), f"high_disagreement fixture missing: {FIXTURE_FILE}"

    def test_fixture_parseable(self):
        with FIXTURE_FILE.open() as f:
            data = json.load(f)
        assert "energy_disagreement_meV_per_atom" in data

    def test_fixture_energy_above_hard_reject(self):
        with FIXTURE_FILE.open() as f:
            data = json.load(f)
        assert data["energy_disagreement_meV_per_atom"] > 75.0, (
            "Fixture must have energy_disagreement > 75 to trigger hard_reject"
        )

    def test_fixture_routing_is_hard_reject(self):
        with FIXTURE_FILE.open() as f:
            data = json.load(f)
        assert data["routing_decision"] == "hard_reject"


class TestHighDisagreementTriggersFalsifier:
    def test_dpa_mace_disagreement_routing_fails(self, high_disagreement_fixture):
        """PRIMARY GATE: energy_disagreement=95 meV > 75 → status=='fail'."""
        result = dpa_mace_disagreement_routing(high_disagreement_fixture)
        assert result.status == "fail", (
            f"Expected 'fail' but got '{result.status}'. "
            f"actual={result.actual}, fixture routing="
            f"{high_disagreement_fixture['output']['routing_decision']}"
        )

    def test_dpa_mace_routing_actual_is_95(self, high_disagreement_fixture):
        result = dpa_mace_disagreement_routing(high_disagreement_fixture)
        assert result.actual == pytest.approx(95.0)

    def test_routing_decision_is_hard_reject(self, high_disagreement_fixture):
        assert high_disagreement_fixture["output"]["routing_decision"] == "hard_reject"


class TestHighDisagreementNonLoadBearingFalsifiers:
    """The force_rmse = 0.10 is between promote (0.15) and hard-reject (0.35) bands.
    Per fixture notes, force_rmse should NOT add an independent fail.
    The force_rmse_threshold falsifier will fail (0.10 > 0, <= 0.15 passes).
    """

    def test_force_rmse_does_not_fail_independently(self, high_disagreement_fixture):
        """force_rmse_disagreement=0.10 < 0.15 → pass (below queue_dft threshold)."""
        result = force_rmse_threshold(high_disagreement_fixture)
        assert result.status == "pass", (
            f"force_rmse=0.10 is below 0.15 promote threshold; expected 'pass', got '{result.status}'"
        )

    def test_single_model_does_not_block(self, high_disagreement_fixture):
        """Two models present → single_model_promotion_block passes."""
        result = single_model_promotion_block(high_disagreement_fixture)
        # routing is hard_reject (not promote), so this gate doesn't fire.
        assert result.status == "pass"

    def test_uma_gate_passes(self, high_disagreement_fixture):
        """No UMA predictions in fixture → uma_license_gate passes."""
        result = uma_license_gate(high_disagreement_fixture)
        assert result.status == "pass"

    def test_volume_drift_passes(self, high_disagreement_fixture):
        """No relaxation data → volume_drift_threshold passes."""
        result = volume_drift_threshold(high_disagreement_fixture)
        assert result.status == "pass"

    def test_space_group_passes(self, high_disagreement_fixture):
        """No relaxation data → space_group_drift_threshold passes."""
        result = space_group_drift_threshold(high_disagreement_fixture)
        assert result.status == "pass"

    def test_committee_passes(self, high_disagreement_fixture):
        """No committee data → committee_uncertainty_threshold passes."""
        result = committee_uncertainty_threshold(high_disagreement_fixture)
        assert result.status == "pass"


class TestHighDisagreementExclusivity:
    """Verify EXACTLY ONE falsifier fires (energy disagreement only)."""

    def test_exactly_one_falsifier_fails(self, high_disagreement_fixture):
        """Only dpa_mace_disagreement_routing should fail."""
        results = {
            "dpa_mace_disagreement_routing": dpa_mace_disagreement_routing(high_disagreement_fixture),
            "single_model_promotion_block": single_model_promotion_block(high_disagreement_fixture),
            "force_rmse_threshold": force_rmse_threshold(high_disagreement_fixture),
            "volume_drift_threshold": volume_drift_threshold(high_disagreement_fixture),
            "space_group_drift_threshold": space_group_drift_threshold(high_disagreement_fixture),
            "uma_license_gate": uma_license_gate(high_disagreement_fixture),
            "committee_uncertainty_threshold": committee_uncertainty_threshold(high_disagreement_fixture),
        }
        failed = [name for name, r in results.items() if r.status == "fail"]
        assert failed == ["dpa_mace_disagreement_routing"], (
            f"Expected only 'dpa_mace_disagreement_routing' to fail; got: {failed}"
        )
