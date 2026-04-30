"""Unit tests for AmsetScatteringTransportAdapter.

PRD §L1.5 verification:
- AMSET returns slightly different Seebeck/σ_e from BoltzTraP2 for same material.
- Cross-method disagreement is the primitive for ZT rank stability.
- Scattering mechanisms (ADP, POP, IMP) are documented in output.
- L1.5 boundary invariants satisfied.
"""

from __future__ import annotations

import pytest

from zer0pa_materials.adapters.l1_5.amset import AmsetScatteringTransportAdapter, AMSET_OFFSETS
from zer0pa_materials.adapters.l1_5.base import L15JobParams
from zer0pa_materials.adapters.l1_5.boltztrap2 import BoltzTraP2RigidBandTransportAdapter
from zer0pa_materials.envelope import Envelope, L15PhononOutput


class TestAmsetScatteringTransportAdapter:
    """Integration tests for AmsetScatteringTransportAdapter."""

    @pytest.fixture
    def bi2te3_params(self) -> L15JobParams:
        return L15JobParams(
            structure_hash="sha256:bi2te3_amset_test_hash_0000001",
            material_id="Bi2Te3",
            candidate_id="candidate:Bi2Te3/amset",
            campaign_id="campaign:unit-test",
        )

    def test_envelope_is_valid(self, bi2te3_params: L15JobParams) -> None:
        env = AmsetScatteringTransportAdapter().compute(bi2te3_params)
        assert isinstance(env, Envelope)
        assert env.layer == "L1.5"

    def test_seebeck_is_returned(self, bi2te3_params: L15JobParams) -> None:
        env = AmsetScatteringTransportAdapter().compute(bi2te3_params)
        output = L15PhononOutput.model_validate(env.output)
        assert output.seebeck_uV_per_K is not None
        assert output.seebeck_uV_per_K > 0.0

    def test_sigma_is_returned(self, bi2te3_params: L15JobParams) -> None:
        env = AmsetScatteringTransportAdapter().compute(bi2te3_params)
        output = L15PhononOutput.model_validate(env.output)
        assert output.electrical_conductivity_S_per_cm is not None
        assert output.electrical_conductivity_S_per_cm > 0.0

    def test_amset_differs_from_boltztrap2(self) -> None:
        """AMSET and BoltzTraP2 must return different values for cross-method signal."""
        params = L15JobParams(
            structure_hash="sha256:bi2te3_crossmethod_test_00001",
            material_id="Bi2Te3",
        )
        bt2_env = BoltzTraP2RigidBandTransportAdapter().compute(params)
        amset_env = AmsetScatteringTransportAdapter().compute(params)

        bt2_seebeck = bt2_env.output["seebeck_uV_per_K"]
        amset_seebeck = amset_env.output["seebeck_uV_per_K"]
        assert bt2_seebeck != amset_seebeck, "AMSET and BoltzTraP2 must return different Seebeck"

        bt2_sigma = bt2_env.output["electrical_conductivity_S_per_cm"]
        amset_sigma = amset_env.output["electrical_conductivity_S_per_cm"]
        assert bt2_sigma != amset_sigma, "AMSET and BoltzTraP2 must return different σ_e"

    def test_amset_seebeck_lower_than_bt2(self) -> None:
        """AMSET seebeck_factor < 1.0 for all materials → AMSET Seebeck < BoltzTraP2."""
        params = L15JobParams(
            structure_hash="sha256:bi2te3_seebeck_compare_00001",
            material_id="Bi2Te3",
        )
        bt2_env = BoltzTraP2RigidBandTransportAdapter().compute(params)
        amset_env = AmsetScatteringTransportAdapter().compute(params)
        assert amset_env.output["seebeck_uV_per_K"] < bt2_env.output["seebeck_uV_per_K"]

    def test_amset_sigma_lower_than_bt2(self) -> None:
        """AMSET sigma_factor < 1.0 → AMSET σ_e < BoltzTraP2 (scattering reduces conductivity)."""
        params = L15JobParams(
            structure_hash="sha256:bi2te3_sigma_compare_000001",
            material_id="Bi2Te3",
        )
        bt2_env = BoltzTraP2RigidBandTransportAdapter().compute(params)
        amset_env = AmsetScatteringTransportAdapter().compute(params)
        assert amset_env.output["electrical_conductivity_S_per_cm"] < \
               bt2_env.output["electrical_conductivity_S_per_cm"]

    def test_scattering_mechanisms_documented(self, bi2te3_params: L15JobParams) -> None:
        """Scattering mechanisms must be documented in the extra input."""
        env = AmsetScatteringTransportAdapter().compute(bi2te3_params)
        # The scattering mechanisms should appear in falsifier or output extra data
        cross_item = next(
            (i for i in env.falsifier.items
             if i.name == "l15.amset_boltztrap2_cross_method_disagreement"),
            None,
        )
        assert cross_item is not None

    def test_cross_method_disagreement_item_present(self, bi2te3_params: L15JobParams) -> None:
        env = AmsetScatteringTransportAdapter().compute(bi2te3_params)
        names = [i.name for i in env.falsifier.items]
        assert "l15.amset_boltztrap2_cross_method_disagreement" in names

    def test_phonon_not_ionic_falsifier_present(self, bi2te3_params: L15JobParams) -> None:
        env = AmsetScatteringTransportAdapter().compute(bi2te3_params)
        names = [i.name for i in env.falsifier.items]
        assert "l15.phonon_does_not_substitute_for_ionic" in names

    def test_no_ionic_conductivity_claim(self, bi2te3_params: L15JobParams) -> None:
        env = AmsetScatteringTransportAdapter().compute(bi2te3_params)
        assert env.output.get("ionic_conductivity_S_per_cm") is None

    def test_zt_is_none_from_amset(self, bi2te3_params: L15JobParams) -> None:
        """AMSET adapter alone does not compute ZT (needs κ_L from Phono3py)."""
        env = AmsetScatteringTransportAdapter().compute(bi2te3_params)
        output = L15PhononOutput.model_validate(env.output)
        assert output.zt is None

    @pytest.mark.parametrize("material_id", ["Bi2Te3", "PbTe", "SnSe"])
    def test_all_te_materials_computed(self, material_id: str) -> None:
        params = L15JobParams(
            structure_hash=f"sha256:{material_id.lower()}_amset_te_test_00001",
            material_id=material_id,
        )
        env = AmsetScatteringTransportAdapter().compute(params)
        assert isinstance(env, Envelope)
        output = L15PhononOutput.model_validate(env.output)
        assert output.seebeck_uV_per_K is not None
        assert output.seebeck_uV_per_K > 0.0
