"""Unit tests for Phono3pyAnharmonicBTEAdapter.

PRD §L1.5 verification:
- Si κ_L is within literature range (synthetic stub).
- Bi2Te3 κ_L is within literature range (~1.5 W/(m·K) at 300 K).
- q-mesh convergence is reported.
- Convergence delta is computed correctly.
"""

from __future__ import annotations

import pytest

from zer0pa_materials_workbench.adapters.l1_5.base import L15JobParams
from zer0pa_materials_workbench.adapters.l1_5.phono3py_bte import (
    Phono3pyAnharmonicBTEAdapter,
    compute_qmesh_convergence,
    synthetic_kappa_L,
)
from zer0pa_materials_workbench.envelope import Envelope, L15PhononOutput


class TestSyntheticKappaL:
    """Tests for synthetic_kappa_L helper."""

    def test_si_kappa_at_300K(self) -> None:
        """Si κ_L should be ~147 W/(m·K) at 300 K (Glassbrenner & Slack 1964)."""
        kappa = synthetic_kappa_L("Si", 300.0)
        assert 120.0 <= kappa <= 180.0, f"Si κ_L = {kappa:.1f} W/(m·K), expected 130-150"

    def test_bi2te3_kappa_at_300K(self) -> None:
        """Bi2Te3 κ_L should be ~1.5 W/(m·K) at 300 K."""
        kappa = synthetic_kappa_L("Bi2Te3", 300.0)
        assert 0.5 <= kappa <= 3.0, f"Bi2Te3 κ_L = {kappa:.2f} W/(m·K), expected ~1.5"

    def test_pbte_kappa_at_300K(self) -> None:
        """PbTe κ_L should be ~2.0 W/(m·K) at 300 K."""
        kappa = synthetic_kappa_L("PbTe", 300.0)
        assert 0.5 <= kappa <= 5.0, f"PbTe κ_L = {kappa:.2f} W/(m·K), expected ~2.0"

    def test_snse_kappa_at_300K(self) -> None:
        """SnSe κ_L should be ~0.7 W/(m·K) at 300 K."""
        kappa = synthetic_kappa_L("SnSe", 300.0)
        assert 0.2 <= kappa <= 2.0, f"SnSe κ_L = {kappa:.2f} W/(m·K), expected ~0.7"

    def test_kappa_decreases_with_temperature(self) -> None:
        """κ_L ∝ 1/T — higher temperature → lower κ_L."""
        k_300 = synthetic_kappa_L("Si", 300.0)
        k_600 = synthetic_kappa_L("Si", 600.0)
        assert k_600 < k_300, "κ_L should decrease with temperature"

    def test_kappa_at_700K_for_pbte(self) -> None:
        """PbTe at 700 K should have significantly lower κ_L than 300 K."""
        kappa = synthetic_kappa_L("PbTe", 700.0)
        assert kappa < 2.0, f"PbTe κ_L at 700 K = {kappa:.3f} W/(m·K), expected < 2.0"


class TestQmeshConvergence:
    """Tests for compute_qmesh_convergence helper."""

    def test_convergence_zero_for_identical_values(self) -> None:
        assert compute_qmesh_convergence([5.0, 5.0, 5.0]) == 0.0

    def test_convergence_correct_formula(self) -> None:
        # (6 - 4) / 4 * 100 = 50%
        result = compute_qmesh_convergence([4.0, 5.0, 6.0])
        assert abs(result - 50.0) < 1e-9

    def test_convergence_empty_list(self) -> None:
        assert compute_qmesh_convergence([]) == 0.0

    def test_convergence_single_value(self) -> None:
        assert compute_qmesh_convergence([5.0]) == 0.0


class TestPhono3pyAnharmonicBTEAdapter:
    """Integration tests for Phono3pyAnharmonicBTEAdapter."""

    @pytest.fixture
    def si_params(self) -> L15JobParams:
        return L15JobParams(
            structure_hash="sha256:si_phono3py_test_hash_00000001",
            material_id="Si",
            candidate_id="candidate:Si/phono3py",
            campaign_id="campaign:unit-test",
        )

    @pytest.fixture
    def bi2te3_params(self) -> L15JobParams:
        return L15JobParams(
            structure_hash="sha256:bi2te3_phono3py_test_hash_000001",
            material_id="Bi2Te3",
            candidate_id="candidate:Bi2Te3/phono3py",
            campaign_id="campaign:unit-test",
        )

    def test_si_envelope_is_valid(self, si_params: L15JobParams) -> None:
        env = Phono3pyAnharmonicBTEAdapter().compute(si_params)
        assert isinstance(env, Envelope)
        assert env.layer == "L1.5"

    def test_si_kappa_within_literature_range(self, si_params: L15JobParams) -> None:
        env = Phono3pyAnharmonicBTEAdapter().compute(si_params)
        output = L15PhononOutput.model_validate(env.output)
        kappa = output.thermal_conductivity_W_per_mK
        assert kappa is not None
        assert 120.0 <= kappa <= 180.0, f"Si κ_L = {kappa:.1f}, expected 120-180 W/(m·K)"

    def test_bi2te3_kappa_within_literature_range(self, bi2te3_params: L15JobParams) -> None:
        env = Phono3pyAnharmonicBTEAdapter().compute(bi2te3_params)
        output = L15PhononOutput.model_validate(env.output)
        kappa = output.thermal_conductivity_W_per_mK
        assert kappa is not None
        assert 0.5 <= kappa <= 3.0, f"Bi2Te3 κ_L = {kappa:.2f}, expected 0.5-3.0 W/(m·K)"

    def test_qmesh_convergence_is_reported(self, si_params: L15JobParams) -> None:
        env = Phono3pyAnharmonicBTEAdapter().compute(si_params)
        output = L15PhononOutput.model_validate(env.output)
        assert output.qmesh_convergence_pct is not None
        assert output.qmesh_convergence_pct >= 0.0

    def test_qmesh_convergence_is_small_for_good_fixtures(self, si_params: L15JobParams) -> None:
        """Synthetic stubs should have < 10% convergence (publishable threshold)."""
        env = Phono3pyAnharmonicBTEAdapter().compute(si_params)
        output = L15PhononOutput.model_validate(env.output)
        assert output.qmesh_convergence_pct < 10.0

    def test_convergence_detail_in_falsifier(self, si_params: L15JobParams) -> None:
        env = Phono3pyAnharmonicBTEAdapter().compute(si_params)
        names = [item.name for item in env.falsifier.items]
        assert "l15.phono3py_qmesh_convergence_detail" in names

    def test_phonon_not_ionic_falsifier_present(self, si_params: L15JobParams) -> None:
        env = Phono3pyAnharmonicBTEAdapter().compute(si_params)
        names = [item.name for item in env.falsifier.items]
        assert "l15.phonon_does_not_substitute_for_ionic" in names

    def test_no_ionic_conductivity_claim(self, si_params: L15JobParams) -> None:
        env = Phono3pyAnharmonicBTEAdapter().compute(si_params)
        assert env.output.get("ionic_conductivity_S_per_cm") is None

    @pytest.mark.parametrize("material_id,expected_range", [
        ("Si",     (120.0, 180.0)),
        ("Bi2Te3", (0.5,   3.0)),
        ("PbTe",   (0.5,   5.0)),
        ("SnSe",   (0.2,   2.0)),
    ])
    def test_kappa_ranges_for_te_fixtures(
        self, material_id: str, expected_range: tuple[float, float]
    ) -> None:
        params = L15JobParams(
            structure_hash=f"sha256:{material_id.lower()}_bte_hash_0000001",
            material_id=material_id,
        )
        env = Phono3pyAnharmonicBTEAdapter().compute(params)
        output = L15PhononOutput.model_validate(env.output)
        kappa = output.thermal_conductivity_W_per_mK
        assert kappa is not None
        lo, hi = expected_range
        assert lo <= kappa <= hi, (
            f"{material_id} κ_L = {kappa:.3f} W/(m·K), expected [{lo}, {hi}]"
        )
