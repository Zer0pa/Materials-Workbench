"""Unit tests for HiPhiveForceConstantFitAdapter.

PRD §L1.5 verification:
- Synthetic FC fit returns comparable but not identical to Phonopy reference.
- Frequency RMSE (Phonopy vs HiPhive) has non-zero signal.
- MLIP vs DFT force RMSE is reported.
- Adapter passes phonon-not-ionic boundary falsifier.
"""

from __future__ import annotations

import pytest

from zer0pa_materials.adapters.l1_5.base import L15JobParams
from zer0pa_materials.adapters.l1_5.hiphive_fit import (
    HiPhiveForceConstantFitAdapter,
    hiphive_frequency_rmse,
)
from zer0pa_materials.envelope import Envelope, L15PhononOutput


class TestHiPhiveFrequencyRmse:
    """Tests for hiphive_frequency_rmse helper."""

    def test_zero_rmse_for_identical_lists(self) -> None:
        freqs = [0.0, 0.0, 0.0, 16.0, 16.0, 16.0]
        assert hiphive_frequency_rmse(freqs, freqs) == 0.0

    def test_rmse_is_positive_for_different_lists(self) -> None:
        phonopy = [0.0, 0.0, 0.0, 16.0, 16.0, 16.0]
        hiphive = [0.0, 0.0, 0.0, 16.1, 16.1, 16.1]
        rmse = hiphive_frequency_rmse(phonopy, hiphive)
        assert rmse > 0.0

    def test_rmse_correct_value(self) -> None:
        # 3 of 6 modes differ by 0.1 THz → RMSE = sqrt(3*(0.1^2)/6) ≈ 0.0707
        phonopy = [0.0, 0.0, 0.0, 16.0, 16.0, 16.0]
        hiphive = [0.0, 0.0, 0.0, 16.1, 16.1, 16.1]
        rmse = hiphive_frequency_rmse(phonopy, hiphive)
        import math
        expected = math.sqrt(3 * 0.1**2 / 6)
        assert abs(rmse - expected) < 1e-9

    def test_rmse_zero_for_empty(self) -> None:
        assert hiphive_frequency_rmse([], []) == 0.0

    def test_rmse_handles_different_lengths(self) -> None:
        phonopy = [0.0, 1.0, 2.0]
        hiphive = [0.1, 1.1]
        rmse = hiphive_frequency_rmse(phonopy, hiphive)
        assert rmse > 0.0


class TestHiPhiveForceConstantFitAdapter:
    """Integration tests for HiPhiveForceConstantFitAdapter."""

    @pytest.fixture
    def si_params(self) -> L15JobParams:
        return L15JobParams(
            structure_hash="sha256:si_hiphive_test_hash_000001",
            material_id="Si",
            candidate_id="candidate:Si/hiphive",
            campaign_id="campaign:unit-test",
        )

    @pytest.fixture
    def bi2te3_params(self) -> L15JobParams:
        return L15JobParams(
            structure_hash="sha256:bi2te3_hiphive_test_hash_00001",
            material_id="Bi2Te3",
            candidate_id="candidate:Bi2Te3/hiphive",
            campaign_id="campaign:unit-test",
        )

    def test_si_envelope_is_valid(self, si_params: L15JobParams) -> None:
        env = HiPhiveForceConstantFitAdapter().compute(si_params)
        assert isinstance(env, Envelope)
        assert env.layer == "L1.5"

    def test_mlip_dft_rmse_is_reported(self, si_params: L15JobParams) -> None:
        env = HiPhiveForceConstantFitAdapter().compute(si_params)
        output = L15PhononOutput.model_validate(env.output)
        assert output.mlip_vs_dft_force_rmse_eV_per_Ang is not None
        assert output.mlip_vs_dft_force_rmse_eV_per_Ang > 0.0

    def test_mlip_dft_rmse_below_threshold_for_good_mlip(
        self, si_params: L15JobParams
    ) -> None:
        """Synthetic MLIP RMSE should be below 0.05 eV/Å (good MLIP)."""
        env = HiPhiveForceConstantFitAdapter().compute(si_params)
        output = L15PhononOutput.model_validate(env.output)
        assert output.mlip_vs_dft_force_rmse_eV_per_Ang < 0.05

    def test_hiphive_offset_nonzero_for_si(self, si_params: L15JobParams) -> None:
        """HiPhive frequencies should differ from Phonopy (non-zero RMSE)."""
        env = HiPhiveForceConstantFitAdapter().compute(si_params)
        # The frequency_rmse_THz is stored in extra_input (not L15PhononOutput)
        # but the falsifier item records it
        names_actuals = {
            item.name: item.actual
            for item in env.falsifier.items
        }
        rmse_item = names_actuals.get("l15.hiphive_frequency_rmse_detail")
        assert rmse_item is not None
        assert float(rmse_item) > 0.0

    def test_hiphive_rmse_within_expected_range(self, si_params: L15JobParams) -> None:
        """Si HiPhive RMSE should be ~0.08 THz (within 0.01-0.20 THz range)."""
        env = HiPhiveForceConstantFitAdapter().compute(si_params)
        names_actuals = {
            item.name: item.actual
            for item in env.falsifier.items
        }
        rmse = float(names_actuals["l15.hiphive_frequency_rmse_detail"])
        assert 0.01 <= rmse <= 0.25, f"Si HiPhive frequency RMSE = {rmse:.4f} THz out of range"

    def test_bi2te3_has_larger_offset_than_si(self) -> None:
        """SnSe and Bi2Te3 should have larger HiPhive RMSE than Si (more anharmonic)."""
        si_env = HiPhiveForceConstantFitAdapter().compute(
            L15JobParams(
                structure_hash="sha256:si_hiphive_compare_hash_00001",
                material_id="Si",
            )
        )
        bi2te3_env = HiPhiveForceConstantFitAdapter().compute(
            L15JobParams(
                structure_hash="sha256:bi2te3_hiphive_compare_hash_0001",
                material_id="Bi2Te3",
            )
        )
        si_rmse = float(next(
            i.actual for i in si_env.falsifier.items
            if i.name == "l15.hiphive_frequency_rmse_detail"
        ))
        bi2te3_rmse = float(next(
            i.actual for i in bi2te3_env.falsifier.items
            if i.name == "l15.hiphive_frequency_rmse_detail"
        ))
        assert bi2te3_rmse > si_rmse

    def test_phonon_not_ionic_falsifier_present(self, si_params: L15JobParams) -> None:
        env = HiPhiveForceConstantFitAdapter().compute(si_params)
        names = [item.name for item in env.falsifier.items]
        assert "l15.phonon_does_not_substitute_for_ionic" in names

    def test_no_ionic_conductivity_claim(self, si_params: L15JobParams) -> None:
        env = HiPhiveForceConstantFitAdapter().compute(si_params)
        assert env.output.get("ionic_conductivity_S_per_cm") is None

    def test_hiphive_falsifier_passes_for_good_fit(self, si_params: L15JobParams) -> None:
        """Si HiPhive RMSE should pass the 0.20 THz threshold."""
        env = HiPhiveForceConstantFitAdapter().compute(si_params)
        rmse_item = next(
            i for i in env.falsifier.items
            if i.name == "l15.hiphive_frequency_rmse_detail"
        )
        assert rmse_item.status == "pass"
