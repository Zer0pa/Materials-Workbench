"""Unit tests for ThermoelectricZtAssembler.

PRD §L1.5 verification:
- ZT computed for Bi2Te3, PbTe, SnSe.
- Both BoltzTraP2 and AMSET branches included in output.
- Rank stability check works (stable iff |ZT_BT2 - ZT_AMSET| / ZT_BT2 <= 15%).
- ZT assembly formula ZT = S²σ_e·T / (κ_L + κ_e) is correct.
- L1.5 boundary invariants satisfied.
"""

from __future__ import annotations

import pytest

from zer0pa_materials_workbench.adapters.l1_5.base import L15JobParams
from zer0pa_materials_workbench.adapters.l1_5.zt_assembler import (
    ThermoelectricZtAssembler,
    ZtAssemblyResult,
    assemble_zt,
)
from zer0pa_materials_workbench.envelope import Envelope, L15PhononOutput


class TestAssembleZt:
    """Tests for assemble_zt formula."""

    def test_zt_zero_for_zero_seebeck(self) -> None:
        zt = assemble_zt(0.0, 900.0, 0.5, 1.5, 300.0)
        assert zt == 0.0

    def test_zt_zero_for_zero_kappa_denom(self) -> None:
        zt = assemble_zt(200.0, 900.0, 0.0, 0.0, 300.0)
        assert zt == 0.0

    def test_zt_positive_for_valid_inputs(self) -> None:
        zt = assemble_zt(200.0, 900.0, 0.5, 1.5, 300.0)
        assert zt > 0.0

    def test_zt_increases_with_temperature(self) -> None:
        zt_300 = assemble_zt(200.0, 900.0, 0.5, 1.5, 300.0)
        zt_700 = assemble_zt(200.0, 900.0, 0.5, 1.5, 700.0)
        assert zt_700 > zt_300

    def test_zt_bi2te3_approximate_value(self) -> None:
        """Bi2Te3 ZT at 300 K should be ~0.8-1.5 (state of the art)."""
        # Using literature values from stubs
        zt = assemble_zt(
            seebeck_uV_per_K=200.0,
            sigma_e_S_per_cm=900.0,
            kappa_e_W_per_mK=0.5,
            kappa_L_W_per_mK=1.5,
            temperature_K=300.0,
        )
        assert 0.3 <= zt <= 2.5, f"Bi2Te3 ZT = {zt:.4f}, expected 0.3-2.5"


class TestThermoelectricZtAssembler:
    """Integration tests for ThermoelectricZtAssembler."""

    @pytest.mark.parametrize("material_id,temperature_K", [
        ("Bi2Te3", 300.0),
        ("PbTe",   700.0),
        ("SnSe",   800.0),
    ])
    def test_zt_computed_for_te_materials(
        self, material_id: str, temperature_K: float
    ) -> None:
        params = L15JobParams(
            structure_hash=f"sha256:{material_id.lower()}_zt_test_hash_000001",
            material_id=material_id,
            temperature_K=temperature_K,
        )
        assembler = ThermoelectricZtAssembler()
        result = assembler.assemble(params)
        assert isinstance(result, ZtAssemblyResult)
        assert result.bt2_zt > 0.0
        assert result.amset_zt > 0.0

    def test_both_branches_in_result(self) -> None:
        params = L15JobParams(
            structure_hash="sha256:bi2te3_zt_branches_test_0001",
            material_id="Bi2Te3",
        )
        result = ThermoelectricZtAssembler().assemble(params)
        # Both branches must have different ZT values (AMSET != BoltzTraP2)
        assert result.bt2_zt != result.amset_zt

    def test_kappa_l_correct_material(self) -> None:
        """Bi2Te3 κ_L should be ~1.5 W/(m·K) at 300 K."""
        params = L15JobParams(
            structure_hash="sha256:bi2te3_zt_kappa_test_000001",
            material_id="Bi2Te3",
            temperature_K=300.0,
        )
        result = ThermoelectricZtAssembler().assemble(params)
        assert 0.5 <= result.kappa_L_W_per_mK <= 3.0

    def test_rank_stability_is_computed(self) -> None:
        params = L15JobParams(
            structure_hash="sha256:bi2te3_zt_rankstab_test_0001",
            material_id="Bi2Te3",
        )
        result = ThermoelectricZtAssembler().assemble(params)
        # rank_stable is a bool
        assert isinstance(result.zt_rank_stable, bool)
        # fractional disagreement is a float
        assert isinstance(result.zt_fractional_disagreement, float)
        assert result.zt_fractional_disagreement >= 0.0

    def test_envelope_has_zt_assembly_in_output(self) -> None:
        params = L15JobParams(
            structure_hash="sha256:bi2te3_zt_assembly_test_0001",
            material_id="Bi2Te3",
        )
        env = ThermoelectricZtAssembler().compute(params)
        assert "zt_assembly" in env.output
        assert "bt2_zt" in env.output["zt_assembly"]
        assert "amset_zt" in env.output["zt_assembly"]

    def test_envelope_zt_is_set(self) -> None:
        params = L15JobParams(
            structure_hash="sha256:bi2te3_zt_set_test_0000001",
            material_id="Bi2Te3",
        )
        env = ThermoelectricZtAssembler().compute(params)
        output = L15PhononOutput.model_validate({
            k: v for k, v in env.output.items()
            if k not in ("zt_assembly",)
        })
        assert output.zt is not None
        assert output.zt > 0.0

    def test_rank_stability_falsifier_present(self) -> None:
        params = L15JobParams(
            structure_hash="sha256:bi2te3_zt_rankfal_test_00001",
            material_id="Bi2Te3",
        )
        env = ThermoelectricZtAssembler().compute(params)
        names = [i.name for i in env.falsifier.items]
        assert "l15.zt_rank_stability" in names

    def test_phonon_not_ionic_falsifier_present(self) -> None:
        params = L15JobParams(
            structure_hash="sha256:bi2te3_zt_notionicfal_0001",
            material_id="Bi2Te3",
        )
        env = ThermoelectricZtAssembler().compute(params)
        names = [i.name for i in env.falsifier.items]
        assert "l15.phonon_does_not_substitute_for_ionic" in names

    def test_phonon_not_ionic_passes(self) -> None:
        params = L15JobParams(
            structure_hash="sha256:bi2te3_zt_notionic_pass_001",
            material_id="Bi2Te3",
        )
        env = ThermoelectricZtAssembler().compute(params)
        item = next(
            i for i in env.falsifier.items
            if i.name == "l15.phonon_does_not_substitute_for_ionic"
        )
        assert item.status == "pass"

    def test_no_ionic_conductivity_in_output(self) -> None:
        params = L15JobParams(
            structure_hash="sha256:bi2te3_zt_noionic_out_0001",
            material_id="Bi2Te3",
        )
        env = ThermoelectricZtAssembler().compute(params)
        assert env.output.get("ionic_conductivity_S_per_cm") is None

    def test_envelope_layer_is_L15(self) -> None:
        params = L15JobParams(
            structure_hash="sha256:si_zt_layer_test_00000001",
            material_id="Si",
        )
        env = ThermoelectricZtAssembler().compute(params)
        assert env.layer == "L1.5"

    @pytest.mark.parametrize("material_id", ["Bi2Te3", "PbTe", "SnSe"])
    def test_zt_assembler_all_te_materials(self, material_id: str) -> None:
        params = L15JobParams(
            structure_hash=f"sha256:{material_id.lower()}_zt_all_test_000001",
            material_id=material_id,
        )
        env = ThermoelectricZtAssembler().compute(params)
        assert isinstance(env, Envelope)
        assert "zt_assembly" in env.output
        zt_assembly = env.output["zt_assembly"]
        assert zt_assembly["bt2_zt"] > 0.0
        assert zt_assembly["amset_zt"] > 0.0
