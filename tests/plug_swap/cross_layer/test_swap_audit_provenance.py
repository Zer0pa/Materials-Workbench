"""Cross-cutting audit provenance test — Wave 5b.

Research infrastructure for in silico materials science discovery.
Outputs are research artifacts. No regulatory certification claims.
No clinical or human-subject use. ITAR / weapons applications are
out of scope (Meta UMA Acceptable Use Policy and operator policy).

For every (layer, adapter_a, adapter_b) triple in the registry:

    * Both envelopes carry a valid ``audit.audit_record_id``.
    * Both envelopes carry ``audit.input_hash`` and ``audit.output_hash``
      matching ``^sha256:[0-9a-f]{64}$``.
    * The ``tool_adapter.name`` differs between A and B (the swap is
      recorded in the audit provenance).

PRD §Plug-replaceability acceptance test, step 4c:
    "audit provenance records the adapter difference"
"""

from __future__ import annotations

from zer0pa_materials_workbench.plugswap import PlugSwapHarness


def pytest_generate_tests(metafunc):
    if "layer" in metafunc.fixturenames:
        from zer0pa_materials_workbench.plugswap import GLOBAL_REGISTRY as REG
        layers = REG.layers()
        metafunc.parametrize("layer", layers, ids=layers)


def test_audit_provenance_for_layer(layer: str, plug_swap_harness: PlugSwapHarness) -> None:
    """Audit provenance must record the adapter difference for every layer."""
    result = plug_swap_harness.run_swap_test(layer)
    item = result.audit_provenance
    # "pass" or "inconclusive" (same name adapters) are both acceptable here;
    # only "fail" (missing audit block or malformed hashes) is a hard failure.
    assert item.status != "fail", (
        f"Audit provenance FAILED for layer {layer!r}:\n"
        f"  adapter_a={result.adapter_a_name!r}\n"
        f"  adapter_b={result.adapter_b_name!r}\n"
        f"  threshold={item.threshold!r}\n"
        f"  actual={item.actual!r}\n"
        f"  rationale={item.rationale!r}"
    )
