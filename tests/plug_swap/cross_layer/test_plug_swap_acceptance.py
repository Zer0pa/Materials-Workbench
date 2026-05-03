"""Plug-swap acceptance report — Wave 5b.

Research infrastructure for in silico materials science discovery.
Outputs are research artifacts. No regulatory certification claims.
No clinical or human-subject use. ITAR / weapons applications are
out of scope (Meta UMA Acceptable Use Policy and operator policy).

When run with ``-s``, prints a markdown table summarising swap verdicts
and wallclock times for all registered layers, then writes the table to
``phases/Plug-swap-framework/acceptance-report.md``.

This test is informational (no assertion failures from the report itself);
the individual boundary tests carry the hard assertions.

Usage::

    .venv/bin/python -m pytest tests/plug_swap/cross_layer/test_plug_swap_acceptance.py -v -s

"""

from __future__ import annotations

from pathlib import Path

import pytest

from zer0pa_materials_workbench.plugswap import GLOBAL_REGISTRY, PlugSwapHarness
from zer0pa_materials_workbench.plugswap.timing import (
    SWAP_WALLCLOCK_BUDGET_SECONDS,
    measure_swap_wallclock,
)

_REPORT_DIR = Path(__file__).parents[3] / "phases" / "Plug-swap-framework"
_REPORT_PATH = _REPORT_DIR / "acceptance-report.md"

_BOUNDARY = (
    "Research infrastructure for in silico materials science discovery. "
    "Outputs are research artifacts. No regulatory certification claims. "
    "No clinical or human-subject use. ITAR / weapons applications are "
    "out of scope (Meta UMA Acceptable Use Policy and operator policy)."
)


def _verdict(status: str) -> str:
    return "OK" if status == "pass" else ("WARN" if status == "inconclusive" else "FAIL")


def test_plug_swap_acceptance_report(plug_swap_harness: PlugSwapHarness) -> None:
    """Generate the plug-swap acceptance report for all registered layers."""
    layers = GLOBAL_REGISTRY.layers()
    rows: list[dict] = []

    for layer in layers:
        entries = GLOBAL_REGISTRY.get(layer)
        assert entries, f"No registration for layer {layer!r}"
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
        result = timing.swap_result

        rows.append({
            "layer": layer,
            "adapter_a": entry.adapter_a_name,
            "adapter_b": entry.adapter_b_name,
            "schema": _verdict(result.schema_invariant.status),
            "audit": _verdict(result.audit_provenance.status),
            "disagreement": _verdict(result.disagreement_state.status),
            "falsifier": _verdict(result.falsifier_state.status),
            "wallclock": f"{timing.wallclock_seconds:.3f}s",
            "within_budget": "YES" if timing.within_budget else "NO",
        })

    # --- Build markdown table ---
    header = (
        "| Layer | Adapter A | Adapter B | Schema | Audit | "
        "Disagreement | Falsifier | Wallclock | Budget |"
    )
    sep = "|---|---|---|---|---|---|---|---|---|"
    table_rows: list[str] = []
    for r in rows:
        table_rows.append(
            f"| {r['layer']} | {r['adapter_a']} | {r['adapter_b']} | "
            f"{r['schema']} | {r['audit']} | {r['disagreement']} | "
            f"{r['falsifier']} | {r['wallclock']} | {r['within_budget']} |"
        )

    report_lines = [
        "# Plug-Swap Acceptance Report",
        "",
        f"> **Boundary**: {_BOUNDARY}",
        "",
        f"> **Budget**: register + verify leg < {SWAP_WALLCLOCK_BUDGET_SECONDS}s per layer.",
        "> Assumption: adapter authoring time (human-bounded, 1–8 h) is not timed.",
        "",
        header,
        sep,
        *table_rows,
        "",
        "## Legend",
        "- **OK** — verdict `pass`",
        "- **WARN** — verdict `inconclusive` (informational; not a hard failure)",
        "- **FAIL** — verdict `fail` (hard failure — see individual boundary tests)",
        "- **Budget** — register + verify leg < 5 seconds (YES / NO)",
        "",
    ]

    report_text = "\n".join(report_lines)

    # Print to stdout (visible with -s).
    print("\n\n" + report_text)

    # Only regenerate the committed snapshot when the operator explicitly asks
    # (env var ``ZER0PA_REGENERATE_ACCEPTANCE_REPORT=1``). Otherwise the test
    # would dirty the working tree on every run because wallclock measurements
    # vary across hardware and load. Reviewers running ``pytest`` should NOT
    # see a modified file in ``git status``.
    import os as _os
    if _os.environ.get("ZER0PA_REGENERATE_ACCEPTANCE_REPORT") == "1":
        _REPORT_DIR.mkdir(parents=True, exist_ok=True)
        _REPORT_PATH.write_text(report_text, encoding="utf-8")
        print(f"\nReport regenerated at: {_REPORT_PATH}")
    else:
        print(
            "\n(set ZER0PA_REGENERATE_ACCEPTANCE_REPORT=1 to regenerate the "
            "committed snapshot at phases/Plug-swap-framework/acceptance-report.md)"
        )

    # Hard assertion: every layer's schema, disagreement, and falsifier must pass.
    # Audit provenance may be inconclusive (same-name adapters) — that is allowed.
    failures: list[str] = []
    for r in rows:
        if r["schema"] == "FAIL":
            failures.append(f"Layer {r['layer']!r}: schema FAIL")
        if r["disagreement"] == "FAIL":
            failures.append(f"Layer {r['layer']!r}: disagreement FAIL")
        if r["falsifier"] == "FAIL":
            failures.append(f"Layer {r['layer']!r}: falsifier FAIL")
        if r["within_budget"] == "NO":
            failures.append(f"Layer {r['layer']!r}: wallclock over budget ({r['wallclock']})")

    if failures:
        pytest.fail(
            "Plug-swap acceptance gate FAILED:\n" + "\n".join(f"  - {f}" for f in failures)
        )
