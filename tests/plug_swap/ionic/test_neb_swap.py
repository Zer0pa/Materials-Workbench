"""Plug-swap test: NebMigrationBarrierAdapter must emit a schema-conformant envelope.

The plug-replaceability invariant (PRD §Plug-replaceability acceptance
test) demands that any concrete ionic adapter, regardless of backend,
returns an envelope whose ``output`` validates against
:class:`IonicTransportOutput`. We exercise this by:

1. Calling the stub adapter on the three battery fixtures.
2. Round-tripping the output dict through ``IonicTransportOutput.model_validate``.
3. Asserting the envelope's top-level shape matches
   :class:`Envelope.canonical_dict`.

If a real backend is wired later (real CINEB, etc.), the same test will
exercise it as long as the adapter is registered.
"""

from __future__ import annotations

import pytest

from zer0pa_materials.adapters.ionic.base import IonicJobParams
from zer0pa_materials.adapters.ionic.neb import NebMigrationBarrierAdapter
from zer0pa_materials.envelope import (
    Envelope,
    IonicTransportOutput,
    validate_layer_output,
)


@pytest.mark.parametrize(
    "fixture_id,structure_hash",
    [
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
    ],
)
def test_neb_envelope_validates(
    fixture_id: str, structure_hash: str
) -> None:
    p = IonicJobParams(
        structure_hash=structure_hash,
        fixture_id=fixture_id,
        candidate_id=f"candidate:{fixture_id}",
    )
    env = NebMigrationBarrierAdapter().compute(p)
    # 1. Envelope is a fully-populated model.
    assert isinstance(env, Envelope)
    # 2. The output dict validates against IonicTransportOutput.
    output_obj = IonicTransportOutput.model_validate(env.output)
    assert output_obj.migration_barrier_eV is not None
    # 3. The layer-output registry validates the same shape.
    validated = validate_layer_output("ionic", env.output)
    assert validated.migration_barrier_eV == output_obj.migration_barrier_eV


def test_neb_envelope_canonical_dict_keys() -> None:
    p = IonicJobParams(
        structure_hash="sha256:" + "a" * 64,
        fixture_id="fixture:LLZO_cubic:d45cb2bf",
    )
    env = NebMigrationBarrierAdapter().compute(p)
    cd = env.canonical_dict()
    for key in (
        "contract_version",
        "research_boundary",
        "run_id",
        "campaign_id",
        "candidate_id",
        "layer",
        "tool_adapter",
        "input_refs",
        "output",
        "confidence",
        "disagreement",
        "falsifier",
        "audit",
        "rights",
    ):
        assert key in cd, f"missing top-level key: {key}"
    assert cd["layer"] == "ionic"


def test_neb_tool_adapter_metadata() -> None:
    """The tool_adapter block is fully populated with adapter identity."""
    p = IonicJobParams(
        structure_hash="sha256:" + "a" * 64,
        fixture_id="fixture:LLZO_cubic:d45cb2bf",
    )
    env = NebMigrationBarrierAdapter().compute(p)
    assert env.tool_adapter.name == "NebMigrationBarrierAdapter"
    assert env.tool_adapter.version == "0.1.0"
    assert env.tool_adapter.backend == "stub"


def test_neb_envelope_input_hash_is_canonical() -> None:
    """Two runs with same params produce the same input_hash."""
    p = IonicJobParams(
        structure_hash="sha256:" + "a" * 64,
        fixture_id="fixture:LLZO_cubic:d45cb2bf",
        candidate_id="candidate:test",
    )
    e1 = NebMigrationBarrierAdapter().compute(p)
    e2 = NebMigrationBarrierAdapter().compute(p)
    assert e1.audit.input_hash == e2.audit.input_hash
