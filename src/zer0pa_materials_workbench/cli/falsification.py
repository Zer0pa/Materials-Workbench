"""CLI subapp for the full falsification wave (Wave 6).

Boundary
--------
Research infrastructure for in silico materials science discovery. Outputs
are research artifacts. No regulatory certification claims. No clinical or
human-subject use. ITAR / weapons applications are out of scope (Meta UMA
Acceptable Use Policy and operator policy).

Commands
--------

* ``falsification run`` — Execute the 16-case adversarial wave end-to-end,
  write ``falsifiers.jsonl`` rows, persist the markdown report, and exit
  non-zero if any case missed its target.
* ``falsification validate-chain`` — Standalone validator for the
  ``falsifiers.jsonl`` and ``decisions.jsonl`` hash chains after a wave run.
* ``falsification list-cases`` — Print the ordered case list (16 entries).

The lead agent wires :data:`falsification_app` into ``cli/main.py`` after
this wave completes. Until then the subapp is importable and runnable
standalone via ``python -m zer0pa_materials_workbench.cli.falsification``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from zer0pa_materials_workbench.audit.kg import MaterialsKG
from zer0pa_materials_workbench.audit.log import AuditLog
from zer0pa_materials_workbench.boundary import RESEARCH_BOUNDARY
from zer0pa_materials_workbench.falsifiers.wave_report import generate_falsification_wave_report
from zer0pa_materials_workbench.falsifiers.wave_runner import (
    DEFAULT_CASES,
    WAVE_CASE_ORDER,
    FalsificationWaveRunner,
)

__all__ = ["falsification_app"]


falsification_app = typer.Typer(
    name="falsification",
    help=(
        "Run the 16-case adversarial falsification wave. "
        "Boundary: Research infrastructure for in silico materials science "
        "discovery. No regulatory certification claims. No clinical or "
        "human-subject use. ITAR/weapons out of scope."
    ),
    no_args_is_help=True,
    add_completion=False,
)
console = Console()


_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_FIXTURES_ROOT = _REPO_ROOT / "fixtures" / "negatives"
_DEFAULT_AUDIT_DIR = _REPO_ROOT / "audit" / "wave6"
_DEFAULT_REPORT_PATH = (
    _REPO_ROOT / "phases" / "Falsification-wave" / "FALSIFICATION-WAVE-REPORT.md"
)
_DEFAULT_KG_PATH = _REPO_ROOT / "audit" / "wave6" / "kg.sqlite"


@falsification_app.command("run")
def run_full_wave(
    audit_dir: Annotated[
        str | None,
        typer.Option(
            "--audit-dir",
            help=(
                "Directory for the falsifiers.jsonl + decisions.jsonl hash-"
                "chained audit log (default: audit/wave6/)."
            ),
        ),
    ] = None,
    fixtures_root: Annotated[
        str | None,
        typer.Option(
            "--fixtures-root",
            help="Root of the negative fixtures (default: fixtures/negatives/).",
        ),
    ] = None,
    report_path: Annotated[
        str | None,
        typer.Option(
            "--report",
            help="Where to write FALSIFICATION-WAVE-REPORT.md.",
        ),
    ] = None,
    kg_path: Annotated[
        str | None,
        typer.Option(
            "--kg-path",
            help="SQLite path for the MaterialsKG (default: audit/wave6/kg.sqlite).",
        ),
    ] = None,
    operator: Annotated[
        str,
        typer.Option("--operator", help="Operator name recorded in the report."),
    ] = "wave-runner",
    json_output: Annotated[
        bool,
        typer.Option("--json/--text", help="Print JSON summary instead of text."),
    ] = False,
) -> None:
    """Run the 16-case falsification wave end-to-end.

    Exit codes:

    * ``0`` — every case fired its PRD-mandated target falsifier and the
      audit hash chain validates.
    * ``2`` — at least one case missed its target, fired spurious extras,
      or broke the hash chain. The report still gets written so the lead
      agent can read what went wrong.
    """
    audit = AuditLog(Path(audit_dir or _DEFAULT_AUDIT_DIR))
    kg = MaterialsKG(Path(kg_path or _DEFAULT_KG_PATH))
    fix_root = Path(fixtures_root or _DEFAULT_FIXTURES_ROOT)
    if not fix_root.exists():
        console.print(f"[red]fixtures root does not exist:[/red] {fix_root}")
        raise typer.Exit(code=2)

    runner = FalsificationWaveRunner(audit_log=audit, kg=kg)
    result = runner.run_all(fix_root)

    report_md = generate_falsification_wave_report(result, operator=operator)
    target_path = Path(report_path or _DEFAULT_REPORT_PATH)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(report_md, encoding="utf-8")

    if json_output:
        summary = {
            "research_boundary": RESEARCH_BOUNDARY,
            "started_at": result.started_at,
            "finished_at": result.finished_at,
            "audit_dir": str(result.audit_dir),
            "report_path": str(target_path),
            "cases_run": len(result.case_results),
            "cases_correct": result.cases_correct,
            "cases_missed": result.cases_missed,
            "cases_spurious": result.cases_spurious,
            "cases_chain_break": result.cases_chain_break,
            "chain_validation_ok": result.chain_validation_ok,
            "kg_node_count_after": result.kg_node_count_after,
        }
        typer.echo(json.dumps(summary, indent=2, sort_keys=True))
    else:
        _print_text_summary(result, target_path)

    bad = (
        result.cases_missed
        + result.cases_spurious
        + result.cases_chain_break
    )
    raise typer.Exit(code=0 if bad == 0 and result.chain_validation_ok else 2)


@falsification_app.command("validate-chain")
def validate_falsifiers_chain(
    audit_dir: Annotated[
        str | None,
        typer.Option(
            "--audit-dir",
            help="Audit directory containing falsifiers.jsonl (default: audit/wave6/).",
        ),
    ] = None,
) -> None:
    """Validate the falsifiers.jsonl + decisions.jsonl hash chains.

    Exits ``0`` when both chains validate, ``2`` otherwise.
    """
    audit = AuditLog(Path(audit_dir or _DEFAULT_AUDIT_DIR))
    falsifiers = audit.validate_chain("falsifiers")
    decisions = audit.validate_chain("decisions")
    table = Table(title="Hash chain validation")
    table.add_column("Category")
    table.add_column("Rows")
    table.add_column("OK")
    table.add_column("First bad index")
    for category, result in (("falsifiers", falsifiers), ("decisions", decisions)):
        ok_glyph = "[green]yes[/green]" if result.ok else "[red]NO[/red]"
        table.add_row(
            category,
            str(result.checked_rows),
            ok_glyph,
            str(result.first_bad_index) if result.first_bad_index is not None else "—",
        )
    console.print(table)
    if not (falsifiers.ok and decisions.ok):
        for err in (falsifiers.errors + decisions.errors)[:32]:
            console.print(f"  [red]-[/red] {err}")
        raise typer.Exit(code=2)


@falsification_app.command("list-cases")
def list_cases() -> None:
    """Print the deterministic 16-case wave order (PRD §Falsification wave + A2)."""
    table = Table(title="Falsification wave — 16 deliberate failures")
    table.add_column("#")
    table.add_column("Case name")
    table.add_column("Layer")
    table.add_column("Target falsifier")
    table.add_column("Fixture / synth")
    for idx, case in enumerate(DEFAULT_CASES, start=1):
        loc = case.fixture_dir or "(synth)"
        table.add_row(
            str(idx),
            case.name,
            case.expected_layer,
            case.target_falsifier,
            loc,
        )
    console.print(table)
    console.print(
        f"\n[dim]Order matches WAVE_CASE_ORDER constant ({len(WAVE_CASE_ORDER)} cases).[/dim]"
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _print_text_summary(result, target_path: Path) -> None:
    summary = (
        f"Cases run: {len(result.case_results)} | "
        f"correct: {result.cases_correct} | "
        f"missed: {result.cases_missed} | "
        f"spurious: {result.cases_spurious} | "
        f"chain-break: {result.cases_chain_break}"
    )
    chain_ok = "yes" if result.chain_validation_ok else "NO"
    console.print(
        Panel(
            f"[bold]Falsification Wave 6 complete[/bold]\n\n"
            f"{summary}\n"
            f"Audit hash chain: {chain_ok}\n"
            f"Report written: {target_path}\n"
            f"Audit dir:      {result.audit_dir}",
            expand=False,
        )
    )

    table = Table(title="Per-case verdict")
    table.add_column("Case")
    table.add_column("Layer")
    table.add_column("Target")
    table.add_column("Verdict")
    for cr in result.case_results:
        glyph = {
            "correct": "[green]correct[/green]",
            "missed": "[red]MISSED[/red]",
            "spurious": "[yellow]spurious[/yellow]",
            "chain_break": "[red]chain_break[/red]",
        }.get(cr.verdict, cr.verdict)
        if cr.error:
            glyph = f"[red]ERR: {cr.error[:64]}[/red]"
        table.add_row(cr.case.name, cr.case.expected_layer, cr.case.target_falsifier, glyph)
    console.print(table)


# Allow ``python -m zer0pa_materials_workbench.cli.falsification`` invocation.
if __name__ == "__main__":  # pragma: no cover
    falsification_app()
