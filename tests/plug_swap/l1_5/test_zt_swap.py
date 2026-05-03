"""Plug-swap test: ThermoelectricZtAssembler must produce consistent ZT envelopes.

The ZT assembler is the primary user-facing adapter. Its plug-swap test
verifies that:
1. Both BoltzTraP2 and AMSET branches are always populated.
2. ZT rank stability is always computed and reported.
3. The output validates against L15PhononOutput (extended with zt_assembly).
4. The phonon-not-ionic boundary is maintained.
"""

from __future__ import annotations

import pytest

from zer0pa_materials_workbench.adapters.l1_5.base import L15JobParams
from zer0pa_materials_workbench.adapters.l1_5.zt_assembler import ThermoelectricZtAssembler
from zer0pa_materials_workbench.envelope import L15PhononOutput, validate_layer_output

_ZT_FIXTURES = [
    ("Bi2Te3", 300.0, "sha256:bi2te3_zt_swap_hash_300k_00001"),
    ("PbTe",   700.0, "sha256:pbte_zt_swap_hash_700k_000001"),
    ("SnSe",   800.0, "sha256:snse_zt_swap_hash_800k_000001"),
]


@pytest.mark.parametrize("material_id,temperature_K,structure_hash", _ZT_FIXTURES)
def test_zt_assembler_envelope_validates(
    material_id: str, temperature_K: float, structure_hash: str
) -> None:
    """ZT assembler must produce a schema-conformant envelope for each TE fixture."""
    params = L15JobParams(
        structure_hash=structure_hash,
        material_id=material_id,
        temperature_K=temperature_K,
        candidate_id=f"candidate:{material_id}/zt-swap",
        campaign_id="campaign:plug-swap",
    )
    assembler = ThermoelectricZtAssembler()
    env = assembler.compute(params)

    # Layer and boundary
    assert env.layer == "L1.5"
    assert env.research_boundary is not None

    # Output schema compliance
    base_output = {k: v for k, v in env.output.items() if k != "zt_assembly"}
    output_obj = L15PhononOutput.model_validate(base_output)
    assert output_obj.zt is not None
    assert output_obj.zt > 0.0

    # Layer registry validation (returns the model object, not bool)
    assert validate_layer_output("L1.5", base_output) is not None

    # ZT assembly dict present
    assert "zt_assembly" in env.output
    zt_assembly = env.output["zt_assembly"]
    assert "bt2_zt" in zt_assembly
    assert "amset_zt" in zt_assembly
    assert zt_assembly["bt2_zt"] > 0.0
    assert zt_assembly["amset_zt"] > 0.0

    # Rank stability is computed
    assert "zt_rank_stable" in zt_assembly
    assert isinstance(zt_assembly["zt_rank_stable"], bool)

    # No ionic conductivity claim
    assert env.output.get("ionic_conductivity_S_per_cm") is None


@pytest.mark.parametrize("material_id,temperature_K,structure_hash", _ZT_FIXTURES)
def test_zt_assembler_bt2_and_amset_differ(
    material_id: str, temperature_K: float, structure_hash: str
) -> None:
    """BoltzTraP2 and AMSET branches must have different ZT values."""
    params = L15JobParams(
        structure_hash=structure_hash,
        material_id=material_id,
        temperature_K=temperature_K,
    )
    env = ThermoelectricZtAssembler().compute(params)
    zt_assembly = env.output["zt_assembly"]
    assert zt_assembly["bt2_zt"] != zt_assembly["amset_zt"], (
        f"{material_id} at {temperature_K} K: BoltzTraP2 ZT == AMSET ZT; "
        "cross-method disagreement must be non-zero"
    )


@pytest.mark.parametrize("material_id,temperature_K,structure_hash", _ZT_FIXTURES)
def test_zt_assembler_rank_stability_falsifier(
    material_id: str, temperature_K: float, structure_hash: str
) -> None:
    """ZT rank stability falsifier must be present in the envelope."""
    params = L15JobParams(
        structure_hash=structure_hash,
        material_id=material_id,
        temperature_K=temperature_K,
    )
    env = ThermoelectricZtAssembler().compute(params)
    names = [i.name for i in env.falsifier.items]
    assert "l15.zt_rank_stability" in names
    assert "l15.phonon_does_not_substitute_for_ionic" in names


def test_zt_assembler_snse_record_holder_seebeck() -> None:
    """SnSe at 800 K should have Seebeck > 300 µV/K (record holder)."""
    params = L15JobParams(
        structure_hash="sha256:snse_zt_record_seebeck_test_001",
        material_id="SnSe",
        temperature_K=800.0,
    )
    env = ThermoelectricZtAssembler().compute(params)
    seebeck = env.output.get("seebeck_uV_per_K")
    assert seebeck is not None
    assert seebeck > 300.0, f"SnSe Seebeck = {seebeck} µV/K, expected > 300"
