"""<1-day swap wallclock timing test — Wave 5b.

Research infrastructure for in silico materials science discovery.
Outputs are research artifacts. No regulatory certification claims.
No clinical or human-subject use. ITAR / weapons applications are
out of scope (Meta UMA Acceptable Use Policy and operator policy).

For every (layer, adapter_a, adapter_b) triple in the registry:
    The register + verify leg must complete in < 5 seconds.

The "<1 day swap" invariant is decomposed as:
    1. Adapter authoring time  — human-bounded (1–8 h); NOT timed here.
    2. Register + verify leg   — machine-measurable; MUST be < 5 seconds.

Acceptance criterion: ``result.within_budget == True`` for every layer.

Assumption documented here (PRD §Architecture Invariant):
    An engineer familiar with the base class contract can write a new
    conformant adapter in 1–8 hours.  This is empirically validated via
    the Waves 3A/3B/4a experience: each layer adapter was written in a
    single session.  The machine portion (this test) must be < 5 seconds
    so the combined total remains well within 1 day.
"""

from __future__ import annotations

from zer0pa_materials_workbench.plugswap import GLOBAL_REGISTRY
from zer0pa_materials_workbench.plugswap.timing import (
    SWAP_WALLCLOCK_BUDGET_SECONDS,
    measure_swap_wallclock,
)


def pytest_generate_tests(metafunc):
    if "layer" in metafunc.fixturenames:
        layers = GLOBAL_REGISTRY.layers()
        metafunc.parametrize("layer", layers, ids=layers)


def test_swap_wallclock_within_budget(layer: str) -> None:
    """Register + verify leg must complete in < 5 seconds for every layer."""
    entries = GLOBAL_REGISTRY.get(layer)
    assert entries, f"No swap registration for layer {layer!r}"
    entry = entries[0]

    timing = measure_swap_wallclock(
        adapter_factory_a=entry.adapter_factory_a,
        adapter_factory_b=entry.adapter_factory_b,
        golden_seed_fn=entry.golden_seed_fn,
        call_fn=entry.call_fn,
        layer=layer,
        adapter_a_name=entry.adapter_a_name,
        adapter_b_name=entry.adapter_b_name,
    )

    assert timing.within_budget, (
        f"Layer {layer!r}: swap wallclock {timing.wallclock_seconds:.3f}s "
        f"exceeds budget of {SWAP_WALLCLOCK_BUDGET_SECONDS}s.\n"
        f"  adapter_a={timing.adapter_a_name!r}\n"
        f"  adapter_b={timing.adapter_b_name!r}\n"
        f"  git_head={timing.git_head!r}\n"
        "Assumption: engineer authoring time (1–8 h, human-bounded) is NOT "
        "included; only the register + verify leg is timed here."
    )
