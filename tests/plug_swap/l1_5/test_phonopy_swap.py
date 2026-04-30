"""Plug-swap test: PhonopyHarmonicAdapter must emit schema-conformant envelopes.

PRD §Plug-replaceability: any concrete L1.5 adapter must return an envelope whose
``output`` validates against :class:`L15PhononOutput`, regardless of backend.

Tests cover the stub backend (always available) and would cover real Phonopy
if installed with L15_FORCE_BACKEND=runpod_rest.
"""

from __future__ import annotations

import pytest

from zer0pa_materials.adapters.l1_5.base import L15JobParams
from zer0pa_materials.adapters.l1_5.phono3py_bte import Phono3pyAnharmonicBTEAdapter
from zer0pa_materials.adapters.l1_5.phonopy_harmonic import PhonopyHarmonicAdapter
from zer0pa_materials.envelope import (
    Envelope,
    L15PhononOutput,
    validate_layer_output,
)


_TE_FIXTURES = [
    (
        "fixture:Bi2Te3:ae87f3b2",
        "sha256:bi2te3_plug_swap_hash_000000000001",
        "Bi2Te3",
    ),
    (
        "fixture:PbTe:9a3f1c22",
        "sha256:pbte_plug_swap_hash_0000000000001",
        "PbTe",
    ),
    (
        "fixture:SnSe:7b2e8d41",
        "sha256:snse_plug_swap_hash_0000000000001",
        "SnSe",
    ),
    (
        "fixture:Si:primitive",
        "sha256:si_plug_swap_hash_00000000000001",
        "Si",
    ),
    (
        "fixture:NaCl:primitive",
        "sha256:nacl_plug_swap_hash_0000000000001",
        "NaCl",
    ),
]


@pytest.mark.parametrize("fixture_id,structure_hash,material_id", _TE_FIXTURES)
def test_phonopy_harmonic_envelope_validates(
    fixture_id: str, structure_hash: str, material_id: str
) -> None:
    """PhonopyHarmonicAdapter must produce a schema-conformant envelope for each fixture."""
    p = L15JobParams(
        structure_hash=structure_hash,
        fixture_id=fixture_id,
        material_id=material_id,
        candidate_id=f"candidate:{fixture_id}",
        campaign_id="campaign:plug-swap",
    )
    env = PhonopyHarmonicAdapter().compute(p)

    # 1. Envelope is a fully-populated model
    assert isinstance(env, Envelope)

    # 2. Layer is L1.5
    assert env.layer == "L1.5"

    # 3. The output dict validates against L15PhononOutput
    output_obj = L15PhononOutput.model_validate(env.output)
    assert output_obj.imaginary_mode_max_THz >= 0.0

    # 4. validate_layer_output confirms the registry match (returns the model, not bool)
    validated = validate_layer_output("L1.5", env.output)
    assert validated is not None

    # 5. No ionic conductivity claim
    assert env.output.get("ionic_conductivity_S_per_cm") is None

    # 6. Boundary is present
    assert env.research_boundary is not None


@pytest.mark.parametrize("fixture_id,structure_hash,material_id", _TE_FIXTURES)
def test_phono3py_bte_envelope_validates(
    fixture_id: str, structure_hash: str, material_id: str
) -> None:
    """Phono3pyAnharmonicBTEAdapter must produce a schema-conformant envelope."""
    p = L15JobParams(
        structure_hash=structure_hash,
        fixture_id=fixture_id,
        material_id=material_id,
        candidate_id=f"candidate:{fixture_id}",
        campaign_id="campaign:plug-swap",
    )
    env = Phono3pyAnharmonicBTEAdapter().compute(p)

    assert isinstance(env, Envelope)
    assert env.layer == "L1.5"

    output_obj = L15PhononOutput.model_validate(env.output)
    assert output_obj.thermal_conductivity_W_per_mK is not None
    assert output_obj.thermal_conductivity_W_per_mK >= 0.0

    assert validate_layer_output("L1.5", env.output) is not None


def test_phonopy_adapter_name_is_stable() -> None:
    """ADAPTER_NAME must be stable for plug-swap registry lookup."""
    assert PhonopyHarmonicAdapter.ADAPTER_NAME == "PhonopyHarmonicAdapter"
    assert Phono3pyAnharmonicBTEAdapter.ADAPTER_NAME == "Phono3pyAnharmonicBTEAdapter"


def test_all_l15_adapters_share_layer() -> None:
    """All L1.5 adapters must emit layer='L1.5' envelopes."""
    from zer0pa_materials.adapters.l1_5.hiphive_fit import HiPhiveForceConstantFitAdapter
    from zer0pa_materials.adapters.l1_5.boltztrap2 import BoltzTraP2RigidBandTransportAdapter
    from zer0pa_materials.adapters.l1_5.amset import AmsetScatteringTransportAdapter
    from zer0pa_materials.adapters.l1_5.zt_assembler import ThermoelectricZtAssembler

    params = L15JobParams(
        structure_hash="sha256:bi2te3_plug_swap_all_adapters_0001",
        material_id="Bi2Te3",
        candidate_id="candidate:Bi2Te3/plug-swap-all",
        campaign_id="campaign:plug-swap",
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
        assert env.layer == "L1.5", (
            f"{adapter.ADAPTER_NAME} returned layer={env.layer!r}, expected 'L1.5'"
        )
