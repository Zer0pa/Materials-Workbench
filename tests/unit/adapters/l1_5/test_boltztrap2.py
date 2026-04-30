"""Unit tests for BoltzTraP2RigidBandTransportAdapter.

PRD §L1.5 verification:
- Bi2Te3 Seebeck within literature range (~200 µV/K at 300 K p-type).
- PbTe Seebeck within literature range (~250 µV/K at 700 K).
- SnSe Seebeck within literature range (~400 µV/K at 800 K, record holder).
- Power factor computed correctly.
- L1.5 boundary invariants satisfied.
"""

from __future__ import annotations

import pytest

from zer0pa_materials.adapters.l1_5.base import L15JobParams
from zer0pa_materials.adapters.l1_5.boltztrap2 import (
    BoltzTraP2RigidBandTransportAdapter,
    compute_power_factor,
    TE_LITERATURE_TRANSPORT,
)
from zer0pa_materials.envelope import Envelope, L15PhononOutput


class TestComputePowerFactor:
    """Tests for compute_power_factor helper."""

    def test_power_factor_zero_for_zero_seebeck(self) -> None:
        assert compute_power_factor(0.0, 1000.0) == 0.0

    def test_power_factor_positive(self) -> None:
        pf = compute_power_factor(200.0, 900.0)
        assert pf > 0.0

    def test_power_factor_units_bi2te3(self) -> None:
        """Bi2Te3 PF: (200 µV/K)² × 90 S/cm = 3.6 µW/(cm·K²)."""
        pf = compute_power_factor(200.0, 90.0)
        assert 2.0 <= pf <= 6.0, f"Bi2Te3 PF = {pf:.3f}, expected 2-6 µW/(cm·K²)"

    def test_power_factor_formula_correct(self) -> None:
        # S = 100 µV/K = 1e-4 V/K; sigma = 100 S/cm
        # PF = (1e-4)^2 * 100 * 1e6 = 1e-8 * 100 * 1e6 = 1.0 µW/(cm·K²)
        pf = compute_power_factor(100.0, 100.0)
        assert abs(pf - 1.0) < 1e-9


class TestBoltzTraP2Transport:
    """Integration tests for BoltzTraP2RigidBandTransportAdapter."""

    @pytest.mark.parametrize("material_id,expected_seebeck_range,temperature", [
        ("Bi2Te3", (150.0, 280.0), 300.0),   # ~200 µV/K at 300 K p-type
        ("PbTe",   (180.0, 320.0), 700.0),   # ~250 µV/K at 700 K
        ("SnSe",   (300.0, 500.0), 800.0),   # ~400 µV/K at 800 K (record)
    ])
    def test_seebeck_within_literature_range(
        self, material_id: str, expected_seebeck_range: tuple[float, float], temperature: float
    ) -> None:
        params = L15JobParams(
            structure_hash=f"sha256:{material_id.lower()}_bt2_test_hash_000001",
            material_id=material_id,
            temperature_K=temperature,
        )
        env = BoltzTraP2RigidBandTransportAdapter().compute(params)
        output = L15PhononOutput.model_validate(env.output)
        seebeck = output.seebeck_uV_per_K
        assert seebeck is not None
        lo, hi = expected_seebeck_range
        assert lo <= seebeck <= hi, (
            f"{material_id} Seebeck = {seebeck:.1f} µV/K, expected [{lo}, {hi}]"
        )

    def test_bi2te3_electrical_conductivity_positive(self) -> None:
        params = L15JobParams(
            structure_hash="sha256:bi2te3_bt2_sigma_test_00001",
            material_id="Bi2Te3",
        )
        env = BoltzTraP2RigidBandTransportAdapter().compute(params)
        output = L15PhononOutput.model_validate(env.output)
        assert output.electrical_conductivity_S_per_cm is not None
        assert output.electrical_conductivity_S_per_cm > 0.0

    def test_bi2te3_electronic_kappa_positive(self) -> None:
        params = L15JobParams(
            structure_hash="sha256:bi2te3_bt2_kappa_test_00001",
            material_id="Bi2Te3",
        )
        env = BoltzTraP2RigidBandTransportAdapter().compute(params)
        output = L15PhononOutput.model_validate(env.output)
        assert output.thermal_conductivity_W_per_mK is not None
        assert output.thermal_conductivity_W_per_mK > 0.0

    def test_zt_is_none_from_bt2(self) -> None:
        """BoltzTraP2 adapter alone does not compute ZT (needs κ_L from Phono3py)."""
        params = L15JobParams(
            structure_hash="sha256:bi2te3_bt2_zt_test_000001",
            material_id="Bi2Te3",
        )
        env = BoltzTraP2RigidBandTransportAdapter().compute(params)
        output = L15PhononOutput.model_validate(env.output)
        assert output.zt is None

    def test_power_factor_falsifier_present(self) -> None:
        params = L15JobParams(
            structure_hash="sha256:bi2te3_bt2_pf_test_0000001",
            material_id="Bi2Te3",
        )
        env = BoltzTraP2RigidBandTransportAdapter().compute(params)
        names = [item.name for item in env.falsifier.items]
        assert "l15.boltztrap2_power_factor" in names

    def test_power_factor_passes_for_bi2te3(self) -> None:
        params = L15JobParams(
            structure_hash="sha256:bi2te3_bt2_pf_pass_test_0001",
            material_id="Bi2Te3",
        )
        env = BoltzTraP2RigidBandTransportAdapter().compute(params)
        pf_item = next(
            i for i in env.falsifier.items
            if i.name == "l15.boltztrap2_power_factor"
        )
        assert pf_item.status == "pass"

    def test_phonon_not_ionic_falsifier_present(self) -> None:
        params = L15JobParams(
            structure_hash="sha256:bi2te3_bt2_ionic_test_00001",
            material_id="Bi2Te3",
        )
        env = BoltzTraP2RigidBandTransportAdapter().compute(params)
        names = [item.name for item in env.falsifier.items]
        assert "l15.phonon_does_not_substitute_for_ionic" in names

    def test_envelope_layer_is_L15(self) -> None:
        params = L15JobParams(
            structure_hash="sha256:si_bt2_layer_test_0000001",
            material_id="Si",
        )
        env = BoltzTraP2RigidBandTransportAdapter().compute(params)
        assert env.layer == "L1.5"

    def test_no_ionic_conductivity_claim(self) -> None:
        params = L15JobParams(
            structure_hash="sha256:si_bt2_no_ionic_test_000001",
            material_id="Si",
        )
        env = BoltzTraP2RigidBandTransportAdapter().compute(params)
        assert env.output.get("ionic_conductivity_S_per_cm") is None
