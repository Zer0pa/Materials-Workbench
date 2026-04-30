"""Unit tests for L1.5 falsifiers.

PRD §L1.5 Falsifiers — every falsifier must trigger correctly:
1. dynamical_stability — fails for imaginary mode > 0.25 THz.
2. mlip_dft_force_rmse — flags RMSE > 0.05 eV/Å.
3. phonopy_hiphive_frequency_rmse — flags RMSE > 0.20 THz or κ_L delta > 20%.
4. q_mesh_convergence — flags delta > 10%.
5. zt_rank_stability — flags if ZT rank changes between BoltzTraP2 and AMSET.
6. phonon_does_not_substitute_for_ionic — pass if no ionic claim in envelope.
"""

from __future__ import annotations

import pytest

from zer0pa_materials.adapters.l1_5.base import L15JobParams, make_l15_envelope
from zer0pa_materials.adapters.l1_5.zt_assembler import ThermoelectricZtAssembler
from zer0pa_materials.boundary import RESEARCH_BOUNDARY
from zer0pa_materials.envelope import (
    AuditBlock,
    Envelope,
    FalsifierItem,
    L15PhononOutput,
    RightsBlock,
    ToolAdapter,
)
from zer0pa_materials.falsifiers.l1_5_falsifiers import (
    dynamical_stability,
    mlip_dft_force_rmse,
    phonopy_hiphive_frequency_rmse,
    q_mesh_convergence,
    zt_rank_stability,
    phonon_does_not_substitute_for_ionic,
)


def _make_simple_l15_envelope(
    imaginary_mode_max_THz: float = 0.0,
    mlip_vs_dft_force_rmse_eV_per_Ang: float | None = None,
    qmesh_convergence_pct: float | None = None,
    seebeck_uV_per_K: float | None = None,
    electrical_conductivity_S_per_cm: float | None = None,
    thermal_conductivity_W_per_mK: float | None = None,
    zt: float | None = None,
    extra_output: dict | None = None,
) -> Envelope:
    """Helper to create a minimal L1.5 envelope for falsifier testing."""
    output = L15PhononOutput(
        imaginary_mode_max_THz=imaginary_mode_max_THz,
        mlip_vs_dft_force_rmse_eV_per_Ang=mlip_vs_dft_force_rmse_eV_per_Ang,
        qmesh_convergence_pct=qmesh_convergence_pct,
        seebeck_uV_per_K=seebeck_uV_per_K,
        electrical_conductivity_S_per_cm=electrical_conductivity_S_per_cm,
        thermal_conductivity_W_per_mK=thermal_conductivity_W_per_mK,
        zt=zt,
    )
    params = L15JobParams(
        structure_hash="sha256:falsifier_test_struct_hash_0001",
        material_id="Bi2Te3",
    )
    env = make_l15_envelope(
        output=output,
        params=params,
        adapter_name="TestAdapter",
        adapter_version="0.0.1",
        backend="stub",
        engine="test",
    )
    if extra_output:
        # Merge extra fields into the output dict
        updated_output = dict(env.output)
        updated_output.update(extra_output)
        # Rebuild envelope with updated output
        env = Envelope(
            research_boundary=env.research_boundary,
            run_id=env.run_id,
            campaign_id=env.campaign_id,
            candidate_id=env.candidate_id,
            layer=env.layer,
            tool_adapter=env.tool_adapter,
            input_refs=env.input_refs,
            output=updated_output,
            falsifier=env.falsifier,
            audit=env.audit,
            rights=env.rights,
        )
    return env


class TestDynamicalStability:
    """Tests for dynamical_stability falsifier."""

    def test_pass_for_zero_imaginary(self) -> None:
        env = _make_simple_l15_envelope(imaginary_mode_max_THz=0.0)
        item = dynamical_stability(env)
        assert item.status == "pass"
        assert item.name == "l15.dynamical_stability"

    def test_pass_for_small_imaginary(self) -> None:
        """0.25 THz is the threshold — exactly at threshold should pass."""
        env = _make_simple_l15_envelope(imaginary_mode_max_THz=0.25)
        item = dynamical_stability(env)
        assert item.status == "pass"

    def test_fail_for_large_imaginary(self) -> None:
        """Imaginary mode > 0.25 THz → fail."""
        env = _make_simple_l15_envelope(imaginary_mode_max_THz=0.30)
        item = dynamical_stability(env)
        assert item.status == "fail"

    def test_fail_for_very_large_imaginary(self) -> None:
        """Large imaginary mode (like unstable_phonon fixture: 1.42 THz) → fail."""
        env = _make_simple_l15_envelope(imaginary_mode_max_THz=1.42)
        item = dynamical_stability(env)
        assert item.status == "fail"

    def test_blocked_when_field_missing(self) -> None:
        """If imaginary_mode_max_THz is not in output, status is blocked."""
        env = _make_simple_l15_envelope(imaginary_mode_max_THz=0.0)
        # Remove the field from output
        modified_output = {k: v for k, v in env.output.items()
                          if k != "imaginary_mode_max_THz"}
        env2 = Envelope(
            research_boundary=env.research_boundary,
            run_id=env.run_id,
            campaign_id=env.campaign_id,
            candidate_id=env.candidate_id,
            layer=env.layer,
            tool_adapter=env.tool_adapter,
            input_refs=env.input_refs,
            output=modified_output,
            falsifier=env.falsifier,
            audit=env.audit,
            rights=env.rights,
        )
        item = dynamical_stability(env2)
        assert item.status == "blocked"

    def test_actual_value_is_recorded(self) -> None:
        env = _make_simple_l15_envelope(imaginary_mode_max_THz=1.42)
        item = dynamical_stability(env)
        assert item.actual == pytest.approx(1.42, abs=1e-9)


class TestMlipDftForceRmse:
    """Tests for mlip_dft_force_rmse falsifier."""

    def test_pass_for_low_rmse(self) -> None:
        env = _make_simple_l15_envelope(mlip_vs_dft_force_rmse_eV_per_Ang=0.02)
        item = mlip_dft_force_rmse(env)
        assert item.status == "pass"

    def test_pass_for_exactly_threshold(self) -> None:
        env = _make_simple_l15_envelope(mlip_vs_dft_force_rmse_eV_per_Ang=0.05)
        item = mlip_dft_force_rmse(env)
        assert item.status == "pass"

    def test_fail_for_high_rmse(self) -> None:
        env = _make_simple_l15_envelope(mlip_vs_dft_force_rmse_eV_per_Ang=0.08)
        item = mlip_dft_force_rmse(env)
        assert item.status == "fail"

    def test_blocked_when_field_missing(self) -> None:
        env = _make_simple_l15_envelope(mlip_vs_dft_force_rmse_eV_per_Ang=None)
        item = mlip_dft_force_rmse(env)
        assert item.status == "blocked"


class TestPhonopyHiphiveFrequencyRmse:
    """Tests for phonopy_hiphive_frequency_rmse falsifier."""

    def test_pass_when_rmse_low(self) -> None:
        phonopy_env = _make_simple_l15_envelope(
            extra_output={"frequency_rmse_THz": 0.10}
        )
        hiphive_env = _make_simple_l15_envelope(
            extra_output={"frequency_rmse_THz": 0.10}
        )
        item = phonopy_hiphive_frequency_rmse(phonopy_env, hiphive_env)
        assert item.status == "pass"

    def test_fail_when_rmse_high(self) -> None:
        phonopy_env = _make_simple_l15_envelope()
        hiphive_env = _make_simple_l15_envelope(
            extra_output={"frequency_rmse_THz": 0.25}
        )
        item = phonopy_hiphive_frequency_rmse(phonopy_env, hiphive_env)
        assert item.status == "fail"

    def test_blocked_when_no_data(self) -> None:
        phonopy_env = _make_simple_l15_envelope()
        hiphive_env = _make_simple_l15_envelope()
        item = phonopy_hiphive_frequency_rmse(phonopy_env, hiphive_env)
        assert item.status == "blocked"

    def test_fail_when_kappa_delta_high(self) -> None:
        """κ_L delta > 20% should trigger fail."""
        phonopy_env = _make_simple_l15_envelope(thermal_conductivity_W_per_mK=1.5)
        hiphive_env = _make_simple_l15_envelope(thermal_conductivity_W_per_mK=2.0)
        # delta = |1.5 - 2.0| / 1.5 * 100 = 33.3% > 20%
        item = phonopy_hiphive_frequency_rmse(phonopy_env, hiphive_env)
        assert item.status == "fail"


class TestQMeshConvergence:
    """Tests for q_mesh_convergence falsifier."""

    def test_pass_for_small_convergence(self) -> None:
        env = _make_simple_l15_envelope(qmesh_convergence_pct=5.0)
        item = q_mesh_convergence(env)
        assert item.status == "pass"

    def test_fail_for_large_convergence(self) -> None:
        env = _make_simple_l15_envelope(qmesh_convergence_pct=15.0)
        item = q_mesh_convergence(env)
        assert item.status == "fail"

    def test_blocked_when_field_missing(self) -> None:
        env = _make_simple_l15_envelope(qmesh_convergence_pct=None)
        item = q_mesh_convergence(env)
        assert item.status == "blocked"

    def test_custom_threshold(self) -> None:
        env = _make_simple_l15_envelope(qmesh_convergence_pct=8.0)
        item = q_mesh_convergence(env, threshold=5.0)
        assert item.status == "fail"


class TestZtRankStability:
    """Tests for zt_rank_stability falsifier."""

    def test_pass_when_zt_close(self) -> None:
        bt2_env = _make_simple_l15_envelope(zt=1.8)
        amset_env = _make_simple_l15_envelope(zt=1.7)
        # Disagreement: |1.8 - 1.7| / 1.8 = 5.6% < 15%
        item = zt_rank_stability(bt2_env, amset_env)
        assert item.status == "pass"

    def test_fail_when_zt_diverges(self) -> None:
        bt2_env = _make_simple_l15_envelope(zt=2.0)
        amset_env = _make_simple_l15_envelope(zt=1.0)
        # Disagreement: |2.0 - 1.0| / 2.0 = 50% > 15%
        item = zt_rank_stability(bt2_env, amset_env)
        assert item.status == "fail"

    def test_blocked_when_zt_missing(self) -> None:
        bt2_env = _make_simple_l15_envelope(zt=None)
        amset_env = _make_simple_l15_envelope(zt=None)
        item = zt_rank_stability(bt2_env, amset_env)
        assert item.status == "blocked"

    def test_uses_zt_assembly_dict_when_available(self) -> None:
        """The assembler envelope has a zt_assembly dict — falsifier should use it."""
        params = L15JobParams(
            structure_hash="sha256:zt_assembler_rankstab_test_001",
            material_id="Bi2Te3",
        )
        zt_env = ThermoelectricZtAssembler().compute(params)
        item = zt_rank_stability(zt_env, zt_env)
        # Should read from zt_assembly dict, not the top-level zt field
        assert item.name == "l15.zt_rank_stability"
        assert item.status in ("pass", "fail")  # depends on disagreement magnitude


class TestPhononDoesNotSubstituteForIonic:
    """Tests for phonon_does_not_substitute_for_ionic falsifier."""

    def test_pass_for_clean_phonon_envelope(self) -> None:
        env = _make_simple_l15_envelope()
        item = phonon_does_not_substitute_for_ionic(env)
        assert item.status == "pass"
        assert item.name == "l15.phonon_does_not_substitute_for_ionic"

    def test_fail_if_envelope_claims_ionic_conductivity(self) -> None:
        """If the output has ionic_conductivity_S_per_cm, the falsifier must fail."""
        env = _make_simple_l15_envelope(
            extra_output={"ionic_conductivity_S_per_cm": 1e-3}
        )
        item = phonon_does_not_substitute_for_ionic(env)
        assert item.status == "fail"

    def test_pass_for_none_ionic_conductivity(self) -> None:
        """If ionic_conductivity_S_per_cm is None, the falsifier should pass."""
        env = _make_simple_l15_envelope(
            extra_output={"ionic_conductivity_S_per_cm": None}
        )
        item = phonon_does_not_substitute_for_ionic(env)
        assert item.status == "pass"

    def test_all_te_adapters_pass_ionic_boundary(self) -> None:
        """All L1.5 adapters must pass the phonon-not-ionic falsifier."""
        from zer0pa_materials.adapters.l1_5.phonopy_harmonic import PhonopyHarmonicAdapter
        from zer0pa_materials.adapters.l1_5.phono3py_bte import Phono3pyAnharmonicBTEAdapter
        from zer0pa_materials.adapters.l1_5.hiphive_fit import HiPhiveForceConstantFitAdapter
        from zer0pa_materials.adapters.l1_5.boltztrap2 import BoltzTraP2RigidBandTransportAdapter
        from zer0pa_materials.adapters.l1_5.amset import AmsetScatteringTransportAdapter

        params = L15JobParams(
            structure_hash="sha256:bi2te3_ionic_boundary_all_adapters",
            material_id="Bi2Te3",
        )
        adapters = [
            PhonopyHarmonicAdapter(),
            Phono3pyAnharmonicBTEAdapter(),
            HiPhiveForceConstantFitAdapter(),
            BoltzTraP2RigidBandTransportAdapter(),
            AmsetScatteringTransportAdapter(),
            ThermoelectricZtAssembler(),
        ]
        for adapter in adapters:
            env = adapter.compute(params)
            item = phonon_does_not_substitute_for_ionic(env)
            assert item.status == "pass", (
                f"{adapter.ADAPTER_NAME} failed phonon_does_not_substitute_for_ionic: "
                f"{item.rationale}"
            )
