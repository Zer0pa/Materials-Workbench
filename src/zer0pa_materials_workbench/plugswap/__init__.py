"""Plug-swap test framework — Wave 5b (Zer0pa Materials).

Research infrastructure for in silico materials science discovery.
Outputs are research artifacts. No regulatory certification claims.
No clinical or human-subject use. ITAR / weapons applications are
out of scope (Meta UMA Acceptable Use Policy and operator policy).

Public surface
--------------
* :class:`PlugSwapHarness` — pytest-friendly harness; register layers and
  run the 4-step PRD invariant test.
* :class:`PlugSwapResult` — structured verdict returned by
  :meth:`PlugSwapHarness.run_swap_test`.
* :class:`SwapRegistry` — singleton that accumulates (layer, adapterA,
  adapterB, seed) registrations for use across the test suite.
* :func:`measure_swap_wallclock` — timing leg of the "<1 day swap" invariant.

All heavy logic lives in :mod:`zer0pa_materials_workbench.plugswap.framework` and
:mod:`zer0pa_materials_workbench.plugswap.timing`.
"""

from zer0pa_materials_workbench.plugswap.framework import (
    GLOBAL_REGISTRY,
    PlugSwapHarness,
    PlugSwapResult,
    SwapRegistry,
)
from zer0pa_materials_workbench.plugswap.timing import measure_swap_wallclock

__all__ = [
    "GLOBAL_REGISTRY",
    "PlugSwapHarness",
    "PlugSwapResult",
    "SwapRegistry",
    "measure_swap_wallclock",
]
