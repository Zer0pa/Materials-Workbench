"""Falsification wave report generator (Wave 6).

Boundary
--------
Research infrastructure for in silico materials science discovery. Outputs
are research artifacts. No regulatory certification claims. No clinical or
human-subject use. ITAR / weapons applications are out of scope (Meta UMA
Acceptable Use Policy and operator policy).

Produces the markdown report cited by EXECUTION-REPORT.md. Crucially, the
report's verdict semantics are inverted from a normal test report:

* "fired correctly" means the gate caught its deliberate failure.
* "did NOT fire" or "fired wrong falsifier" means a real bug in the gate.

The report header explicitly documents this so an unfamiliar reader does
not mistake "failed" for "broken pipeline".
"""

from __future__ import annotations

import json
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any

from zer0pa_materials.boundary import RESEARCH_BOUNDARY
from zer0pa_materials.falsifiers.wave_runner import (
    DEFAULT_CASES,
    COFIRES,
    FalsificationCaseResult,
    FalsificationWaveResult,
    WAVE_CASE_ORDER,
)

__all__ = ["generate_falsification_wave_report", "render_case_table_row"]


# ---------------------------------------------------------------------------
# Repo metadata
# ---------------------------------------------------------------------------


def _git_commit_hash(repo_root: Path) -> str:
    """Best-effort git HEAD hash; returns 'unknown' on any failure."""
    try:
        out = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
        return out.stdout.strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def _git_branch_name(repo_root: Path) -> str:
    try:
        out = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "--abbrev-ref", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
        return out.stdout.strip()
    except Exception:  # noqa: BLE001
        return "unknown"


# ---------------------------------------------------------------------------
# Per-row rendering
# ---------------------------------------------------------------------------


_VERDICT_GLYPH: dict[str, str] = {
    "correct": "PASS",
    "missed": "FAIL",
    "spurious": "WARN",
    "chain_break": "FAIL",
}


def render_case_table_row(case_result: FalsificationCaseResult) -> str:
    """Render one row of the Markdown verdict table."""
    case = case_result.case
    fired_names = sorted(
        {
            f"{item.name}={item.status}"
            for item in case_result.triggered_falsifiers
            if item.status == "fail"
        }
    )
    fired = ", ".join(fired_names) if fired_names else "—"
    glyph = _VERDICT_GLYPH.get(case_result.verdict, "?")
    if case_result.error:
        glyph = "ERR"
        fired = f"error={case_result.error[:96]}"
    fixture_label = case.fixture_dir or "(synthesizer)"
    return (
        f"| {case.name} | {fixture_label} | {case.expected_layer} | "
        f"{case.target_falsifier} | {fired} | {glyph} |"
    )


# ---------------------------------------------------------------------------
# Report generator
# ---------------------------------------------------------------------------


def generate_falsification_wave_report(
    wave_result: FalsificationWaveResult,
    *,
    repo_root: Path | str | None = None,
    operator: str = "wave-runner",
) -> str:
    """Return a single markdown string summarising the wave run.

    The report header carries the verbatim research boundary and an
    explanatory note about the inverted semantics. The case table lists
    every case, what fixture or synthesizer was used, the expected
    layer, the target falsifier, the falsifiers that actually fired, and
    a verdict glyph.
    """
    if repo_root is None:
        repo_root = Path(__file__).resolve().parents[3]
    repo_root = Path(repo_root)
    commit = _git_commit_hash(repo_root)
    branch = _git_branch_name(repo_root)

    lines: list[str] = []
    lines.append("# Falsification Wave Report — Wave 6")
    lines.append("")
    lines.append("## Boundary")
    lines.append("")
    lines.append(RESEARCH_BOUNDARY)
    lines.append("")
    lines.append("## Run metadata")
    lines.append("")
    lines.append(f"- **Started at:** `{wave_result.started_at}`")
    lines.append(f"- **Finished at:** `{wave_result.finished_at}`")
    lines.append(f"- **Operator:** `{operator}`")
    lines.append(f"- **Repo commit:** `{commit}` (branch `{branch}`)")
    lines.append(f"- **Audit dir:** `{wave_result.audit_dir}`")
    lines.append(f"- **Python:** `{sys.version.split()[0]}` on `{platform.system()}`")
    lines.append("")
    lines.append("## Verdict semantics (inverted)")
    lines.append("")
    lines.append(
        "This wave is **adversarial**. A `PASS` verdict means the gate FIRED "
        "CORRECTLY when shown its deliberate failure. A `FAIL` verdict means "
        "the gate DID NOT FIRE — that is a real bug in the layer's "
        "falsifier and must be surfaced for a fix loop. A `WARN` (spurious) "
        "verdict means the target fired but at least one undocumented extra "
        "falsifier also fired; the wave still detected the deliberate "
        "failure but the per-layer attribution discipline weakened. A "
        "`chain_break` verdict means the audit hash chain failed validation "
        "after the case was recorded — that is also a hard failure."
    )
    lines.append("")

    # Aggregate counts
    total = len(wave_result.case_results)
    correct = wave_result.cases_correct
    missed = wave_result.cases_missed
    spurious = wave_result.cases_spurious
    chain_break = wave_result.cases_chain_break

    lines.append("## Aggregate")
    lines.append("")
    lines.append("| Metric | Count |")
    lines.append("|---|---|")
    lines.append(f"| Cases run | {total} |")
    lines.append(f"| Fired correctly (target = target, no extras, chain valid) | {correct} |")
    lines.append(f"| Missed (target did NOT fire — real bug) | {missed} |")
    lines.append(f"| Spurious extras (target fired but >0 undocumented co-fires) | {spurious} |")
    lines.append(f"| Audit chain broke after case | {chain_break} |")
    lines.append(f"| Total falsifier rows in `falsifiers.jsonl` | {wave_result.total_falsifier_rows_written} |")
    lines.append(f"| Total decision rows in `decisions.jsonl` | {wave_result.total_decision_rows_written} |")
    lines.append(f"| KG nodes after wave | {wave_result.kg_node_count_after} |")
    lines.append(
        f"| Audit hash chain validates (post-wave) | "
        f"{'**yes**' if wave_result.chain_validation_ok else '**NO** — see chain errors below'} |"
    )
    lines.append("")

    # Verdict table
    lines.append("## Per-case verdict")
    lines.append("")
    lines.append(
        "| Case | Fixture | Expected layer | Target falsifier | Fired (status=fail) | Verdict |"
    )
    lines.append("|---|---|---|---|---|---|")
    for cr in wave_result.case_results:
        lines.append(render_case_table_row(cr))
    lines.append("")

    # Issues
    issue_lines: list[str] = []
    for cr in wave_result.case_results:
        if cr.verdict == "missed":
            issue_lines.append(
                f"- **Missed**: case `{cr.case.name}` did NOT fire its target "
                f"`{cr.case.target_falsifier}`. The deliberate failure passed "
                f"through the layer gate. Real bug — the lead agent must "
                f"either fix the gate or document it as a known issue with "
                f"a tracked TODO."
            )
        elif cr.verdict == "spurious":
            extras = sorted(
                {
                    item.name
                    for item in cr.triggered_falsifiers
                    if item.status == "fail"
                    and item.name != cr.case.target_falsifier
                    and item.name not in COFIRES.get(cr.case.name, set())
                }
            )
            issue_lines.append(
                f"- **Spurious extra**: case `{cr.case.name}` fired its target "
                f"plus {len(extras)} undocumented extra falsifier(s): "
                f"{extras}. The target was still detected, but the "
                f"per-layer attribution loosened. Either the negative "
                f"fixture has unintended side effects, or the new co-fire "
                f"belongs in `COFIRES` after rationale."
            )
        elif cr.verdict == "chain_break":
            issue_lines.append(
                f"- **Chain break**: case `{cr.case.name}` produced audit-chain "
                f"errors: {cr.chain_errors}. The hash chain MUST validate at "
                f"every checkpoint per PRD §Audit Trail And KG."
            )
        if cr.error:
            issue_lines.append(
                f"- **Run error**: case `{cr.case.name}` raised "
                f"`{cr.error}` before any falsifier could record. The "
                f"runner's dispatch path may need a fix; the wave cannot "
                f"verify a gate it cannot reach."
            )

    if issue_lines:
        lines.append("## Issues found")
        lines.append("")
        lines.extend(issue_lines)
        lines.append("")

    # Chain errors block (if any).
    if not wave_result.chain_validation_ok:
        lines.append("## Audit hash chain errors")
        lines.append("")
        lines.append("```")
        for err in wave_result.chain_errors[:64]:
            lines.append(err)
        if len(wave_result.chain_errors) > 64:
            lines.append(
                f"... ({len(wave_result.chain_errors) - 64} more errors omitted)"
            )
        lines.append("```")
        lines.append("")

    # Wave F5 post-PRD recompute sweep.
    if wave_result.recompute_sweep is not None:
        sweep = wave_result.recompute_sweep
        lines.append("## Wave F5 post-PRD recompute sweep")
        lines.append("")
        lines.append(
            "After the 16 PRD cases, the runner feeds a **synthetic forged-"
            "evidence chain** through every Wave D hardened recompute gate. "
            "Each row below shows the gate, the status it returned for the "
            "forged input, and whether the production wiring is alive."
        )
        lines.append("")
        lines.append(
            f"- **Forged chain caught:** `{sweep.forged_chain_caught}`  "
            f"(at least 4 of 7 gates fail-tripped on the forged chain)"
        )
        lines.append(
            f"- **Failed (correctly): {sweep.n_failed} / {sweep.n_total}**"
        )
        lines.append("")
        lines.append("| Gate | Status (on forged input) | Rationale |")
        lines.append("|---|---|---|")
        for gate_name, item in sweep.gate_results.items():
            r = (item.rationale or "").replace("|", "\\|")[:120]
            lines.append(f"| `{gate_name}` | `{item.status}` | {r} |")
        lines.append("")

    # Co-fire policy footnote.
    lines.append("## Documented co-fires (allowed extras)")
    lines.append("")
    if not COFIRES:
        lines.append("_No co-fires currently allowed._")
    else:
        for case_name, cofires in sorted(COFIRES.items()):
            if not cofires:
                lines.append(f"- `{case_name}`: (none — single-trigger only)")
                continue
            lines.append(
                f"- `{case_name}` → also accepts: {sorted(cofires)}"
            )
    lines.append("")

    # Verified-working footnote: list correct cases.
    lines.append("## Verified working")
    lines.append("")
    correct_cases = [cr for cr in wave_result.case_results if cr.verdict == "correct"]
    if correct_cases:
        lines.append(
            f"The following {len(correct_cases)} adversarial case(s) fired their "
            "PRD-mandated target falsifier with `status=fail`, with no "
            "undocumented co-fires and a clean audit hash chain after the "
            "row was recorded:"
        )
        lines.append("")
        for cr in correct_cases:
            lines.append(f"- `{cr.case.name}` → `{cr.case.target_falsifier}`")
    else:
        lines.append(
            "_No cases verified as cleanly correct in this run. See "
            "Issues found above._"
        )
    lines.append("")

    # Footer.
    lines.append("---")
    lines.append("")
    lines.append(
        "_This report is the artifact cited by `EXECUTION-REPORT.md` per "
        "PRD §Acceptance Gates / Falsification wave. The 16 cases include "
        "the 15 PRD-mandated deliberate failures plus the L3 quarantine-"
        "breach negative fixture delivered in A2. Every case must show: "
        "input that should fail → exactly the right falsifier fires → "
        "no others fire spuriously._"
    )

    return "\n".join(lines) + "\n"
