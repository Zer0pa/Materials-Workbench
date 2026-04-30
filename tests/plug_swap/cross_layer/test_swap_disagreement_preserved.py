"""Cross-cutting disagreement state preservation test — Wave 5b.

Research infrastructure for in silico materials science discovery.
Outputs are research artifacts. No regulatory certification claims.
No clinical or human-subject use. ITAR / weapons applications are
out of scope (Meta UMA Acceptable Use Policy and operator policy).

For every (layer, adapter_a, adapter_b) triple in the registry:
    The disagreement block must be either present in both envelopes or
    absent in both.  A swap must NOT add or remove the disagreement
    structure — only values inside it may change.

PRD §Plug-replaceability acceptance test, step 4d:
    "disagreement/falsifier state is preserved"
"""

from __future__ import annotations

import pytest

from zer0pa_materials.plugswap import PlugSwapHarness


def pytest_generate_tests(metafunc):
    if "layer" in metafunc.fixturenames:
        from zer0pa_materials.plugswap import GLOBAL_REGISTRY as REG
        layers = REG.layers()
        metafunc.parametrize("layer", layers, ids=layers)


def test_disagreement_state_preserved_for_layer(layer: str, plug_swap_harness: PlugSwapHarness) -> None:
    """Disagreement structure must be symmetric across adapter swap for every layer."""
    result = plug_swap_harness.run_swap_test(layer)
    item = result.disagreement_state
    assert item.status == "pass", (
        f"Disagreement state FAILED for layer {layer!r}:\n"
        f"  adapter_a={result.adapter_a_name!r}\n"
        f"  adapter_b={result.adapter_b_name!r}\n"
        f"  threshold={item.threshold!r}\n"
        f"  actual={item.actual!r}\n"
        f"  rationale={item.rationale!r}"
    )
