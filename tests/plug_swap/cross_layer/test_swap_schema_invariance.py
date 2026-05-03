"""Cross-cutting schema invariance test — Wave 5b.

Research infrastructure for in silico materials science discovery.
Outputs are research artifacts. No regulatory certification claims.
No clinical or human-subject use. ITAR / weapons applications are
out of scope (Meta UMA Acceptable Use Policy and operator policy).

For every (layer, adapter_a, adapter_b) triple in the registry, asserts
that the envelope schemas produced by both adapters are invariant:

    * Same top-level JSON key-set (excluding tool_adapter and audit).
    * Same ``layer`` value on both envelopes.
    * Both outputs validate against the layer's registered schema.
    * Both envelopes carry the research boundary verbatim.

PRD §Plug-replaceability acceptance test, step 4b:
    "schemas validate"
"""

from __future__ import annotations

from zer0pa_materials_workbench.plugswap import PlugSwapHarness


# All registered layers pulled from the session-scoped fixture.
def pytest_generate_tests(metafunc):
    if "layer" in metafunc.fixturenames:
        from tests.plug_swap.conftest import GLOBAL_REGISTRY  # noqa: F401 — triggers population
        from zer0pa_materials_workbench.plugswap import GLOBAL_REGISTRY as REG
        layers = REG.layers()
        metafunc.parametrize("layer", layers, ids=layers)


def test_schema_invariant_for_layer(layer: str, plug_swap_harness: PlugSwapHarness) -> None:
    """Schema must be invariant across adapter A and adapter B for every layer."""
    result = plug_swap_harness.run_swap_test(layer)
    item = result.schema_invariant
    assert item.status == "pass", (
        f"Schema invariance FAILED for layer {layer!r}:\n"
        f"  adapter_a={result.adapter_a_name!r}\n"
        f"  adapter_b={result.adapter_b_name!r}\n"
        f"  threshold={item.threshold!r}\n"
        f"  actual={item.actual!r}\n"
        f"  rationale={item.rationale!r}"
    )
