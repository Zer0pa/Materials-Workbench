"""Plug-swap test: MLIP-MD and AIMD adapters share the same envelope shape.

The plug-replaceability invariant (PRD §Plug-replaceability acceptance
test) requires that the AIMD and MLIP-MD adapters emit envelopes with
the same canonical key set, the same layer-output schema, and the same
top-level envelope shape. The two adapters differ ONLY in:

* ``tool_adapter.name``
* ``tool_adapter.engine``
* method-seeded numeric values (D, sigma_NE, MSD)

Everything else is identical.
"""

from __future__ import annotations

import pytest

from zer0pa_materials_workbench.adapters.ionic.aimd import AimdDiffusionAdapter
from zer0pa_materials_workbench.adapters.ionic.base import IonicJobParams
from zer0pa_materials_workbench.adapters.ionic.mlip_md import MlipMdDiffusionAdapter
from zer0pa_materials_workbench.envelope import (
    IonicTransportOutput,
    validate_layer_output,
)

_FIXTURES = [
    (
        "fixture:LLZO_cubic:d45cb2bf",
        "sha256:d45cb2bfe5e76b86b365e1402e118ed32280049a62345c903558c6cfac04ef19",
    ),
    (
        "fixture:Li6PS5Cl:8d7b2175",
        "sha256:8d7b217550c751a08bd6bc85d74a166ff0b4966266552d254ca53527607c40bc",
    ),
    (
        "fixture:Li-Mg-Zr-Cl-seed:ea01c76f",
        "sha256:ea01c76f01f1427a5010cad97a984d3802c869f96b3726501897f5b08e3c138a",
    ),
]


def _params(fixture_id: str, structure_hash: str) -> IonicJobParams:
    return IonicJobParams(
        structure_hash=structure_hash,
        fixture_id=fixture_id,
        candidate_id=f"candidate:{fixture_id}",
    )


@pytest.mark.parametrize("fixture_id,structure_hash", _FIXTURES)
def test_mlip_and_aimd_share_envelope_keys(
    fixture_id: str, structure_hash: str
) -> None:
    p = _params(fixture_id, structure_hash)
    env_m = MlipMdDiffusionAdapter().compute(p)
    env_a = AimdDiffusionAdapter().compute(p)
    cd_m = env_m.canonical_dict()
    cd_a = env_a.canonical_dict()
    assert set(cd_m) == set(cd_a)


@pytest.mark.parametrize("fixture_id,structure_hash", _FIXTURES)
def test_mlip_and_aimd_share_output_keys(
    fixture_id: str, structure_hash: str
) -> None:
    p = _params(fixture_id, structure_hash)
    env_m = MlipMdDiffusionAdapter().compute(p)
    env_a = AimdDiffusionAdapter().compute(p)
    assert set(env_m.output.keys()) == set(env_a.output.keys())


@pytest.mark.parametrize("fixture_id,structure_hash", _FIXTURES)
def test_mlip_and_aimd_validate_against_ionic_output_schema(
    fixture_id: str, structure_hash: str
) -> None:
    p = _params(fixture_id, structure_hash)
    env_m = MlipMdDiffusionAdapter().compute(p)
    env_a = AimdDiffusionAdapter().compute(p)
    out_m = IonicTransportOutput.model_validate(env_m.output)
    out_a = IonicTransportOutput.model_validate(env_a.output)
    assert out_m.diffusion_coefficient_cm2_per_s is not None
    assert out_a.diffusion_coefficient_cm2_per_s is not None
    # Registry view should also validate.
    validate_layer_output("ionic", env_m.output)
    validate_layer_output("ionic", env_a.output)


def test_mlip_and_aimd_have_distinct_method_seeds() -> None:
    assert MlipMdDiffusionAdapter.METHOD_SEED != AimdDiffusionAdapter.METHOD_SEED


@pytest.mark.parametrize("fixture_id,structure_hash", _FIXTURES)
def test_mlip_and_aimd_envelopes_have_same_layer(
    fixture_id: str, structure_hash: str
) -> None:
    p = _params(fixture_id, structure_hash)
    env_m = MlipMdDiffusionAdapter().compute(p)
    env_a = AimdDiffusionAdapter().compute(p)
    assert env_m.layer == env_a.layer == "ionic"


@pytest.mark.parametrize("fixture_id,structure_hash", _FIXTURES)
def test_mlip_and_aimd_envelopes_share_same_input_refs(
    fixture_id: str, structure_hash: str
) -> None:
    """Both adapters should reference the same IonicTransportService."""
    p = _params(fixture_id, structure_hash)
    env_m = MlipMdDiffusionAdapter().compute(p)
    env_a = AimdDiffusionAdapter().compute(p)
    assert set(env_m.input_refs) == set(env_a.input_refs)


def test_mlip_and_aimd_falsifier_item_names_overlap() -> None:
    """Both adapters emit the same set of named falsifier items."""
    p = IonicJobParams(
        structure_hash="sha256:" + "a" * 64,
        fixture_id="fixture:LLZO_cubic:d45cb2bf",
    )
    env_m = MlipMdDiffusionAdapter().compute(p)
    env_a = AimdDiffusionAdapter().compute(p)
    names_m = {it.name for it in env_m.falsifier.items}
    names_a = {it.name for it in env_a.falsifier.items}
    assert names_m == names_a
