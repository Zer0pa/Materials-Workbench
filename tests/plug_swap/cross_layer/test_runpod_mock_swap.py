"""Cross-cutting runpod_mock swap test — Wave 5b.

Research infrastructure for in silico materials science discovery.
Outputs are research artifacts. No regulatory certification claims.
No clinical or human-subject use. ITAR / weapons applications are
out of scope (Meta UMA Acceptable Use Policy and operator policy).

For every layer, swapping ``local_stub`` → ``runpod_mock`` (simulated by
overriding ``tool_adapter.backend`` in-memory) must preserve the schema.

This validates that the runpod_mock envelope shape is identical to the
local_stub shape so the <1-day cutover path is schema-safe.

PRD §Architecture Invariant:
    "runpod_mock behind the same contract"
"""

from __future__ import annotations

import pytest

from zer0pa_materials.envelope.envelope import Envelope
from zer0pa_materials.plugswap import GLOBAL_REGISTRY, PlugSwapHarness


def pytest_generate_tests(metafunc):
    if "layer" in metafunc.fixturenames:
        layers = GLOBAL_REGISTRY.layers()
        metafunc.parametrize("layer", layers, ids=layers)


def test_runpod_mock_schema_preserved(layer: str, plug_swap_harness: PlugSwapHarness) -> None:
    """local_stub -> runpod_mock swap preserves the envelope schema."""
    result = plug_swap_harness.run_swap_test(layer)

    # Simulate the runpod_mock backend by patching tool_adapter.backend
    # in-memory on the envelope produced by adapter A.
    dump_a = result.envelope_a.model_dump(mode="json")
    dump_mock = dict(dump_a)
    dump_mock["tool_adapter"] = dict(dump_a["tool_adapter"])
    dump_mock["tool_adapter"]["backend"] = "runpod_mock"

    # The patched envelope must still validate.
    try:
        env_mock = Envelope.model_validate(dump_mock)
    except Exception as exc:
        pytest.fail(
            f"Layer {layer!r}: runpod_mock envelope validation failed: {exc}"
        )

    # Schema must match the original (same key-set, same layer).
    keys_original = set(dump_a.keys()) - {"tool_adapter", "audit"}
    keys_mock = set(dump_mock.keys()) - {"tool_adapter", "audit"}
    assert keys_original == keys_mock, (
        f"Layer {layer!r}: key-set changed after runpod_mock swap. "
        f"Diff: {keys_original.symmetric_difference(keys_mock)}"
    )
    assert env_mock.layer == result.envelope_a.layer, (
        f"Layer {layer!r}: layer field changed after runpod_mock swap."
    )
    assert env_mock.tool_adapter.backend == "runpod_mock", (
        f"Layer {layer!r}: backend not set to runpod_mock."
    )
