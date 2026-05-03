"""Unit tests for PhonopyHarmonicAdapter.

PRD §L1.5 verification:
- Si phonon spectrum has correct mode count (6 modes).
- Acoustic sum rule is applied (Gamma acoustic modes set to zero).
- Stability classification correctly identifies stable/unstable systems.
- Imaginary mode magnitude threshold (0.25 THz) is enforced.
- L1.5 envelope boundary invariants are satisfied.
"""

from __future__ import annotations

import pytest

from zer0pa_materials_workbench.adapters.l1_5.base import L15_SERVICE_REF, L15JobParams
from zer0pa_materials_workbench.adapters.l1_5.phonopy_harmonic import (
    PhonopyHarmonicAdapter,
    apply_acoustic_sum_rule,
    classify_stability,
    synthetic_phonon_spectrum,
)
from zer0pa_materials_workbench.envelope import Envelope, L15PhononOutput

SI_HASH = "sha256:si_fixture_canonical_hash_0000000001"
NACL_HASH = "sha256:nacl_fixture_canonical_hash_000000001"
BI2TE3_HASH = "sha256:bi2te3_fixture_canonical_hash_00000001"


@pytest.fixture
def si_params() -> L15JobParams:
    return L15JobParams(
        structure_hash=SI_HASH,
        material_id="Si",
        candidate_id="candidate:Si/primitive",
        campaign_id="campaign:unit-test",
    )


@pytest.fixture
def nacl_params() -> L15JobParams:
    return L15JobParams(
        structure_hash=NACL_HASH,
        material_id="NaCl",
        candidate_id="candidate:NaCl/primitive",
        campaign_id="campaign:unit-test",
    )


class TestSyntheticPhononSpectrum:
    """Tests for synthetic_phonon_spectrum helper."""

    def test_si_spectrum_has_correct_qpoints(self) -> None:
        spectrum = synthetic_phonon_spectrum("Si", SI_HASH, [6, 6, 6])
        assert "Gamma" in spectrum
        assert len(spectrum) >= 1

    def test_si_spectrum_gamma_has_6_modes(self) -> None:
        """Si primitive cell has 2 atoms → 6 phonon modes."""
        spectrum = synthetic_phonon_spectrum("Si", SI_HASH, [6, 6, 6])
        assert len(spectrum["Gamma"]) == 6

    def test_si_acoustic_modes_near_zero_at_gamma(self) -> None:
        """The 3 acoustic modes at Gamma should be zero."""
        spectrum = synthetic_phonon_spectrum("Si", SI_HASH, [6, 6, 6])
        gamma = sorted(spectrum["Gamma"])
        acoustic = gamma[:3]
        for f in acoustic:
            assert abs(f) < 0.1, f"Acoustic mode {f:.4f} THz not near zero at Gamma"

    def test_si_optical_modes_around_16_thz(self) -> None:
        """Si optical modes should be near 16 THz."""
        spectrum = synthetic_phonon_spectrum("Si", SI_HASH, [6, 6, 6])
        gamma = sorted(spectrum["Gamma"])
        optical = gamma[3:]
        for f in optical:
            assert 12.0 <= f <= 20.0, f"Si optical mode {f:.4f} THz out of expected range"

    def test_nacl_spectrum_has_6_modes(self) -> None:
        spectrum = synthetic_phonon_spectrum("NaCl", NACL_HASH, [6, 6, 6])
        assert len(spectrum["Gamma"]) == 6

    def test_bi2te3_spectrum_has_15_modes(self) -> None:
        """Bi2Te3 primitive cell has 5 atoms → 15 phonon modes."""
        spectrum = synthetic_phonon_spectrum("Bi2Te3", BI2TE3_HASH, [6, 6, 6])
        assert len(spectrum["Gamma"]) == 15

    def test_unknown_material_returns_spectrum(self) -> None:
        """Unknown materials get a Si-like fallback with hash jitter."""
        spectrum = synthetic_phonon_spectrum(None, "sha256:unknown0000000001", [4, 4, 4])
        assert "Gamma" in spectrum
        assert len(spectrum["Gamma"]) == 6

    def test_determinism(self) -> None:
        """Same inputs return same spectrum (no random state)."""
        s1 = synthetic_phonon_spectrum("Si", SI_HASH, [6, 6, 6])
        s2 = synthetic_phonon_spectrum("Si", SI_HASH, [6, 6, 6])
        assert s1 == s2


class TestAcousticSumRule:
    """Tests for apply_acoustic_sum_rule helper."""

    def test_asr_sets_acoustic_modes_to_zero(self) -> None:
        spectrum = {"Gamma": [0.01, -0.02, 0.005, 16.0, 16.0, 16.1]}
        corrected, residual = apply_acoustic_sum_rule(spectrum, n_acoustic=3)
        gamma = sorted(corrected["Gamma"])
        assert all(f == 0.0 for f in gamma[:3])

    def test_asr_residual_is_max_correction(self) -> None:
        spectrum = {"Gamma": [0.01, -0.02, 0.005, 16.0, 16.0, 16.1]}
        _, residual = apply_acoustic_sum_rule(spectrum, n_acoustic=3)
        assert abs(residual - 0.02) < 1e-9

    def test_asr_does_not_modify_non_gamma_points(self) -> None:
        spectrum = {
            "Gamma": [0.0, 0.0, 0.0, 16.0, 16.0, 16.0],
            "X": [4.5, 4.5, 6.8, 13.9, 14.2, 16.0],
        }
        corrected, _ = apply_acoustic_sum_rule(spectrum)
        assert corrected["X"] == spectrum["X"]

    def test_asr_residual_zero_for_perfect_acoustic(self) -> None:
        spectrum = {"Gamma": [0.0, 0.0, 0.0, 16.0, 16.0, 16.0]}
        _, residual = apply_acoustic_sum_rule(spectrum)
        assert residual == 0.0


class TestDynamicalStabilityClassification:
    """Tests for classify_stability helper."""

    def test_no_imaginary_is_stable(self) -> None:
        result = classify_stability([])
        assert result == "stable"

    def test_small_imaginary_is_acoustic_only(self) -> None:
        """Imaginary modes ≤ 0.25 THz: unstable_acoustic_only."""
        result = classify_stability([0.10, 0.20])
        assert result == "unstable_acoustic_only"

    def test_exactly_threshold_is_acoustic_only(self) -> None:
        result = classify_stability([0.25])
        assert result == "unstable_acoustic_only"

    def test_large_imaginary_is_non_acoustic(self) -> None:
        """Imaginary mode > 0.25 THz: unstable_non_acoustic."""
        result = classify_stability([0.30])
        assert result == "unstable_non_acoustic"

    def test_mix_passes_if_max_exceeds_threshold(self) -> None:
        result = classify_stability([0.10, 0.40, 0.05])
        assert result == "unstable_non_acoustic"


class TestPhonopyHarmonicAdapter:
    """Integration tests for PhonopyHarmonicAdapter."""

    def test_si_envelope_is_valid_envelope(self, si_params: L15JobParams) -> None:
        env = PhonopyHarmonicAdapter().compute(si_params)
        assert isinstance(env, Envelope)

    def test_si_envelope_layer_is_L15(self, si_params: L15JobParams) -> None:
        env = PhonopyHarmonicAdapter().compute(si_params)
        assert env.layer == "L1.5"

    def test_si_envelope_has_research_boundary(self, si_params: L15JobParams) -> None:
        env = PhonopyHarmonicAdapter().compute(si_params)
        assert env.research_boundary is not None
        assert len(env.research_boundary) > 20

    def test_si_output_validates_against_L15PhononOutput(self, si_params: L15JobParams) -> None:
        env = PhonopyHarmonicAdapter().compute(si_params)
        output = L15PhononOutput.model_validate(env.output)
        assert output.imaginary_mode_max_THz >= 0.0

    def test_si_is_stable(self, si_params: L15JobParams) -> None:
        """Si should be dynamically stable (no imaginary non-acoustic modes)."""
        env = PhonopyHarmonicAdapter().compute(si_params)
        output = L15PhononOutput.model_validate(env.output)
        assert output.imaginary_mode_max_THz == 0.0

    def test_envelope_has_falsifier_block(self, si_params: L15JobParams) -> None:
        env = PhonopyHarmonicAdapter().compute(si_params)
        assert env.falsifier is not None
        assert hasattr(env.falsifier, "items")
        assert len(env.falsifier.items) >= 1

    def test_phonon_not_ionic_falsifier_is_always_present(self, si_params: L15JobParams) -> None:
        """Hardcoded boundary falsifier must be in every envelope."""
        env = PhonopyHarmonicAdapter().compute(si_params)
        names = [item.name for item in env.falsifier.items]
        assert "l15.phonon_does_not_substitute_for_ionic" in names

    def test_phonon_not_ionic_falsifier_passes(self, si_params: L15JobParams) -> None:
        env = PhonopyHarmonicAdapter().compute(si_params)
        item = next(
            i for i in env.falsifier.items
            if i.name == "l15.phonon_does_not_substitute_for_ionic"
        )
        assert item.status == "pass"

    def test_service_ref_in_input_refs(self, si_params: L15JobParams) -> None:
        env = PhonopyHarmonicAdapter().compute(si_params)
        assert L15_SERVICE_REF in env.input_refs

    def test_audit_block_has_hashes(self, si_params: L15JobParams) -> None:
        env = PhonopyHarmonicAdapter().compute(si_params)
        assert env.audit is not None
        assert env.audit.input_hash.startswith("sha256:")
        assert env.audit.output_hash.startswith("sha256:")

    def test_nacl_spectrum_computed(self, nacl_params: L15JobParams) -> None:
        env = PhonopyHarmonicAdapter().compute(nacl_params)
        assert isinstance(env, Envelope)
        output = L15PhononOutput.model_validate(env.output)
        assert output.imaginary_mode_max_THz >= 0.0

    def test_stability_classification_in_extra_falsifiers(
        self, si_params: L15JobParams
    ) -> None:
        env = PhonopyHarmonicAdapter().compute(si_params)
        names = [item.name for item in env.falsifier.items]
        assert "l15.dynamical_stability_classification" in names

    def test_no_ionic_conductivity_in_output(self, si_params: L15JobParams) -> None:
        """L1.5 envelope MUST NOT claim ionic_conductivity_S_per_cm."""
        env = PhonopyHarmonicAdapter().compute(si_params)
        assert "ionic_conductivity_S_per_cm" not in env.output or \
               env.output.get("ionic_conductivity_S_per_cm") is None

    @pytest.mark.parametrize("material_id", ["Si", "NaCl", "Bi2Te3", "PbTe", "SnSe"])
    def test_all_te_fixtures_compute(self, material_id: str) -> None:
        params = L15JobParams(
            structure_hash=f"sha256:{material_id.lower()}_test_hash_0000001",
            material_id=material_id,
        )
        env = PhonopyHarmonicAdapter().compute(params)
        assert isinstance(env, Envelope)
        assert env.layer == "L1.5"
