"""<1-day swap timing leg — Wave 5b.

Research infrastructure for in silico materials science discovery.
Outputs are research artifacts. No regulatory certification claims.
No clinical or human-subject use. ITAR / weapons applications are
out of scope (Meta UMA Acceptable Use Policy and operator policy).

The "<1 day swap" invariant (PRD §Architecture Invariant)
---------------------------------------------------------
The PRD states: "swap any layer's tool in <1 day with no downstream
breakage."

The total swap time decomposes into:

    1. Adapter authoring time — human-bounded; cannot be timed automatically.
       Assumption: an engineer who knows the base-class contract writes a new
       adapter in 1–8 hours.  This is not measured here.

    2. Register + verify leg — the time to (a) register the new adapter in
       the harness and (b) run the plug-swap invariant test suite against it.
       This IS the machine-measurable portion.  Acceptance: < 5 seconds.

:func:`measure_swap_wallclock` times only leg 2 so the test is deterministic
and environment-independent.  The function does NOT write files or modify
adapters; it performs an in-memory swap via the :class:`PlugSwapHarness` API.

Architectural note on "git rev-parse HEAD"
------------------------------------------
The PRD describes snapshotting the codebase via ``git rev-parse HEAD`` before
the swap.  We record this in the timing result for traceability without
making the test git-dependent (CI may run in an untracked working tree).
The snapshot is informational only; the timing check does not compare commit
hashes.
"""

from __future__ import annotations

import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from zer0pa_materials_workbench.envelope.envelope import Envelope
from zer0pa_materials_workbench.plugswap.framework import (
    PlugSwapHarness,
    PlugSwapResult,
    SwapRegistry,
)

__all__ = [
    "SWAP_WALLCLOCK_BUDGET_SECONDS",
    "SwapWallclockResult",
    "measure_swap_wallclock",
]

# Acceptance threshold: the register + verify leg must complete within this
# budget.  5 seconds is conservative for any CPU-side stub adapter.
SWAP_WALLCLOCK_BUDGET_SECONDS: float = 5.0


@dataclass
class SwapWallclockResult:
    """Result of a single wallclock timing run.

    Attributes
    ----------
    layer:
        The layer that was timed.
    adapter_a_name:
        Human-readable name of the baseline adapter.
    adapter_b_name:
        Human-readable name of the replacement adapter.
    wallclock_seconds:
        Elapsed real time (seconds) for the register + verify leg.
    within_budget:
        True when ``wallclock_seconds < SWAP_WALLCLOCK_BUDGET_SECONDS``.
    git_head:
        Output of ``git rev-parse HEAD`` at the time of measurement, or
        ``"<untracked>"`` if the working tree is not in a git repository.
    swap_result:
        The full :class:`PlugSwapResult` from the harness.
    """

    layer: str
    adapter_a_name: str
    adapter_b_name: str
    wallclock_seconds: float
    within_budget: bool
    git_head: str
    swap_result: PlugSwapResult


def _git_head() -> str:
    """Return the current git HEAD hash, or '<untracked>' if unavailable."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return "<untracked>"


def measure_swap_wallclock(
    adapter_factory_a: Callable[[], Any],
    adapter_factory_b: Callable[[], Any],
    golden_seed_fn: Callable[[], Any],
    call_fn: Callable[[Any, Any], Envelope],
    layer: str,
    adapter_a_name: str = "",
    adapter_b_name: str = "",
) -> SwapWallclockResult:
    """Time the register + verify leg of an adapter swap.

    This function is read-only with respect to all layer adapters.  It
    performs an in-memory swap only: it creates a fresh :class:`SwapRegistry`,
    registers the replacement adapter (adapter B), and runs the full
    :meth:`PlugSwapHarness.run_swap_test` — all in memory, no file writes.

    Parameters
    ----------
    adapter_factory_a:
        Zero-argument callable returning the baseline adapter instance.
    adapter_factory_b:
        Zero-argument callable returning the replacement adapter instance.
    golden_seed_fn:
        Zero-argument callable returning the seed for both adapters.
    call_fn:
        ``(adapter, seed) -> Envelope`` callable for the layer's API.
    layer:
        Layer key (e.g. ``"L1"``).
    adapter_a_name:
        Human-readable name override for adapter A.
    adapter_b_name:
        Human-readable name override for adapter B.

    Returns
    -------
    SwapWallclockResult
        Contains elapsed time, within-budget flag, git HEAD, and full
        PlugSwapResult for further inspection.

    Acceptance criterion
    --------------------
    ``result.within_budget`` must be True for the layer to pass the
    "<1 day swap" invariant's machine-measurable leg.

    Assumption
    ----------
    Adapter authoring time (human leg) is assumed to be 1–8 hours for an
    engineer familiar with the base class contract.  This is not measured
    here.  Only the register + verify leg (< 5 seconds) is timed.
    """
    head = _git_head()

    # --- Timed region: register + run the swap invariant test. ---
    t0 = time.perf_counter()

    # Step 1 — synthetic in-memory "swap": register B as the replacement.
    registry = SwapRegistry()
    registry.register_layer(
        layer=layer,
        adapter_factory_a=adapter_factory_a,
        adapter_factory_b=adapter_factory_b,
        golden_seed_fn=golden_seed_fn,
        call_fn=call_fn,
        adapter_a_name=adapter_a_name,
        adapter_b_name=adapter_b_name,
    )
    harness = PlugSwapHarness(registry=registry)

    # Step 2 — run the 4-step PRD invariant test.
    swap_result = harness.run_swap_test(layer)

    t1 = time.perf_counter()
    # --- End timed region. ---

    elapsed = t1 - t0

    return SwapWallclockResult(
        layer=layer,
        adapter_a_name=adapter_a_name or swap_result.adapter_a_name,
        adapter_b_name=adapter_b_name or swap_result.adapter_b_name,
        wallclock_seconds=elapsed,
        within_budget=elapsed < SWAP_WALLCLOCK_BUDGET_SECONDS,
        git_head=head,
        swap_result=swap_result,
    )
