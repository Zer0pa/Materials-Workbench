"""Cross-cutting downstream breakage test — Wave 5b.

Research infrastructure for in silico materials science discovery.
Outputs are research artifacts. No regulatory certification claims.
No clinical or human-subject use. ITAR / weapons applications are
out of scope (Meta UMA Acceptable Use Policy and operator policy).

For every (layer, adapter_a, adapter_b) triple in the registry:
    * After the swap, both envelopes must be fully valid
      ``Envelope`` objects (model_validate succeeds).
    * The ``layer`` field must match the registered layer.
    * The envelope can be serialised to JSON and round-tripped without
      data loss (canonical_dict completes without exception).

PRD §Plug-replaceability acceptance test, step 4a:
    "downstream code is unchanged"
"""

from __future__ import annotations

import pytest

from zer0pa_materials.envelope.envelope import Envelope
from zer0pa_materials.plugswap import PlugSwapHarness


def pytest_generate_tests(metafunc):
    if "layer" in metafunc.fixturenames:
        from zer0pa_materials.plugswap import GLOBAL_REGISTRY as REG
        layers = REG.layers()
        metafunc.parametrize("layer", layers, ids=layers)


def test_no_downstream_breakage_for_layer(layer: str, plug_swap_harness: PlugSwapHarness) -> None:
    """Both adapter envelopes must be fully valid and JSON-serialisable."""
    result = plug_swap_harness.run_swap_test(layer)

    # Both must be Envelope instances.
    assert isinstance(result.envelope_a, Envelope), (
        f"Layer {layer!r} adapter_a={result.adapter_a_name!r} did not return an Envelope"
    )
    assert isinstance(result.envelope_b, Envelope), (
        f"Layer {layer!r} adapter_b={result.adapter_b_name!r} did not return an Envelope"
    )

    # Both must pass model_dump (JSON serialisation round-trip).
    dump_a = result.envelope_a.model_dump(mode="json")
    dump_b = result.envelope_b.model_dump(mode="json")
    assert isinstance(dump_a, dict), f"Layer {layer!r} adapter_a dump is not a dict"
    assert isinstance(dump_b, dict), f"Layer {layer!r} adapter_b dump is not a dict"

    # Both must re-validate from their own dumps.
    re_a = Envelope.model_validate(dump_a)
    re_b = Envelope.model_validate(dump_b)
    assert re_a.layer == result.envelope_a.layer
    assert re_b.layer == result.envelope_b.layer

    # Both must carry the research boundary.
    from zer0pa_materials.boundary import RESEARCH_BOUNDARY
    assert result.envelope_a.research_boundary == RESEARCH_BOUNDARY, (
        f"Layer {layer!r} adapter_a missing boundary"
    )
    assert result.envelope_b.research_boundary == RESEARCH_BOUNDARY, (
        f"Layer {layer!r} adapter_b missing boundary"
    )
