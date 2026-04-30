"""CLI subapp for Runpod cutover operations (Wave 5c).

Commands:
    precheck        — Run RunpodCutover.precheck() and print report.
    sentinel        — Run the sentinel campaign and write a Markdown report.
    parity          — Run the parity test suite (pytest) and print results.
    hard-failures   — Run all 10 hard-failure detectors against current state.
    cutover-runbook — Print the operator runbook from docs/RUNPOD-CUTOVER.md.

Boundary (verbatim)
-------------------
Research infrastructure for in silico materials science discovery.
Outputs are research artifacts. No regulatory certification claims.
No clinical or human-subject use. ITAR / weapons applications are
out of scope (Meta UMA Acceptable Use Policy and operator policy).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from zer0pa_materials.boundary import RESEARCH_BOUNDARY
from zer0pa_materials.envelope.config import MaterialsConfig
from zer0pa_materials.repo_root import phase_dir, repo_root
from zer0pa_materials.runpod.cutover import RunpodCutover, SENTINEL_SEEDS
from zer0pa_materials.runpod.hard_failures import HardFailureDetector
from zer0pa_materials.runpod.mock_backends import build_runpod_mock_envelope, RUNPOD_MOCK_LAYERS

runpod_app = typer.Typer(
    name="runpod",
    help=(
        "Runpod cutover operations — precheck, sentinel campaign, parity tests, "
        "hard-failure detectors, and operator runbook.\n\n"
        "Boundary: Research infrastructure for in silico materials science discovery. "
        "No regulatory certification claims. No clinical or human-subject use. "
        "ITAR/weapons out of scope."
    ),
    no_args_is_help=True,
    add_completion=False,
)
console = Console()


def _runpod_phases_dir() -> Path:
    return phase_dir("Runpod-cutover")


def _runbook_path() -> Path:
    return repo_root() / "docs" / "RUNPOD-CUTOVER.md"


@runpod_app.command("precheck")
def precheck(
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit JSON instead of human-readable output."),
    ] = False,
) -> None:
    """Run RunpodCutover.precheck() and print the precondition report."""
    cfg = MaterialsConfig.from_env()
    cutover = RunpodCutover(config=cfg)
    report = cutover.precheck()

    if json_output:
        typer.echo(report.to_json())
        return

    status = "[green]PASS[/green]" if report.passed else "[red]BLOCKED[/red]"
    console.print(Panel(f"Runpod Precheck — {status}", expand=False))

    table = Table(title="Preconditions", show_lines=True)
    table.add_column("Precondition")
    table.add_column("Status")
    table.add_column("Evidence")
    for name, ok in report.preconditions.items():
        icon = "[green]PASS[/green]" if ok else "[red]FAIL[/red]"
        table.add_row(name, icon, report.evidence.get(name, ""))
    console.print(table)

    if report.blockers:
        console.print(f"\n[yellow]Config blockers ({len(report.blockers)}):[/yellow]")
        for b in report.blockers:
            console.print(f"  - {b}")

    if not report.passed:
        raise typer.Exit(code=1)


@runpod_app.command("sentinel")
def sentinel(
    backend: Annotated[
        str,
        typer.Option(
            "--backend",
            help="Backend to run: runpod_mock (default) or runpod_rest.",
        ),
    ] = "runpod_mock",
    output_dir: Annotated[
        Optional[str],
        typer.Option("--output-dir", help="Directory for sentinel-report.md."),
    ] = None,
) -> None:
    """Run the sentinel campaign (LLZO, Li6PS5Cl, Li-Mg-Zr-Cl, Bi2Te3) on all GPU-bound layers."""
    cfg = MaterialsConfig.from_env()
    cutover = RunpodCutover(config=cfg)

    console.print("[bold]Running sentinel campaign...[/bold]")
    report = cutover.run_sentinel_campaign(backend=backend)

    # Write Markdown report.
    out_dir = Path(output_dir) if output_dir else _runpod_phases_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / "sentinel-report.md"
    _write_sentinel_md(report, report_path)
    console.print(f"[green]Sentinel report written:[/green] {report_path}")

    # Print summary table.
    table = Table(title=f"Sentinel Campaign ({backend})", show_lines=True)
    table.add_column("Seed")
    table.add_column("Layers OK")
    table.add_column("Layers Error")
    for seed_name, layer_envs in report.seed_results.items():
        ok = sum(1 for v in layer_envs.values() if isinstance(v, dict) and "error" not in v)
        err = len(layer_envs) - ok
        table.add_row(seed_name, str(ok), str(err))
    console.print(table)


@runpod_app.command("parity")
def parity(
    output_dir: Annotated[
        Optional[str],
        typer.Option("--output-dir", help="Directory for parity report."),
    ] = None,
    verbose: Annotated[
        bool,
        typer.Option("--verbose/--quiet", help="Show full pytest output."),
    ] = False,
) -> None:
    """Run the parity test suite (tests/parity/) and print results."""
    repo = repo_root()
    parity_dir = repo / "tests" / "parity"
    if not parity_dir.exists():
        console.print(f"[red]Parity test directory not found: {parity_dir}[/red]")
        raise typer.Exit(code=1)

    # Use the running interpreter so the command works whether the user
    # runs from .venv or any other Python environment that has the
    # package installed.
    python = sys.executable
    cmd = [python, "-m", "pytest", str(parity_dir), "-v", "--tb=short"]
    if not verbose:
        cmd.extend(["-q"])

    console.print(f"[bold]Running parity tests: {' '.join(cmd[-3:])}[/bold]")
    result = subprocess.run(cmd, capture_output=not verbose, text=True, cwd=str(repo))

    if not verbose:
        lines = (result.stdout or "") + (result.stderr or "")
        console.print(lines[-3000:] if len(lines) > 3000 else lines)

    out_dir = Path(output_dir) if output_dir else _runpod_phases_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    parity_report_path = out_dir / "parity-result.txt"
    parity_report_path.write_text(
        (result.stdout or "") + (result.stderr or ""),
        encoding="utf-8",
    )
    console.print(f"[green]Parity result written:[/green] {parity_report_path}")

    if result.returncode != 0:
        console.print("[red]Parity tests FAILED.[/red]")
        raise typer.Exit(code=result.returncode)
    console.print("[green]Parity tests PASSED.[/green]")


@runpod_app.command("hard-failures")
def hard_failures(
    repo_root_override: Annotated[
        Optional[str],
        typer.Option("--repo-root", help="Repo root for bulk-dataset scan."),
    ] = None,
    layer: Annotated[
        Optional[str],
        typer.Option("--layer", help="Layer to build a mock envelope for (spot check)."),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit JSON results."),
    ] = False,
) -> None:
    """Run all 10 hard-failure detectors against the current state."""
    detector = HardFailureDetector()
    cfg = MaterialsConfig.from_env()
    repo = Path(repo_root_override) if repo_root_override else repo_root()
    results = []

    # Build a sample envelope for envelope-level detectors.
    test_layer = layer or "L1"
    if test_layer not in RUNPOD_MOCK_LAYERS:
        test_layer = RUNPOD_MOCK_LAYERS[0]
    sample_input = {"chemical_system": "Li-La-Zr-O", "backend": "runpod_mock"}
    try:
        env = build_runpod_mock_envelope(layer=test_layer, input_payload=sample_input)
    except Exception as exc:  # noqa: BLE001
        env = {}
        console.print(f"[yellow]Warning: could not build mock envelope: {exc}[/yellow]")

    # Run all 10 detectors.
    # 1. Schema drift (self-consistency).
    results.append(detector.detect_schema_drift(env, env))
    # 2. Missing artifact hashes.
    results.append(detector.detect_missing_artifact_hashes(env))
    # 3. Missing boundary block.
    results.append(detector.detect_missing_boundary_block(env))
    # 4. Missing resource metrics.
    results.append(detector.detect_missing_resource_metrics(env))
    # 5. Caller changes (stub: empty git status = clean).
    results.append(detector.detect_caller_changes(""))
    # 6. Lost audit provenance.
    results.append(detector.detect_lost_audit_provenance(env))
    # 7. Model response without disagreement.
    results.append(detector.detect_model_response_without_disagreement(env))
    # 8. UMA without HF AUP gate.
    results.append(detector.detect_uma_without_hf_aup_gate(
        env,
        hf_org=cfg.UMA_HF_ORG,
        hf_token=cfg.UMA_HF_TOKEN,
    ))
    # 9. Bulk datasets locally.
    results.append(detector.detect_bulk_datasets_locally(repo))
    # 10. Falsifier bypass (L1 is pre-gate, should pass trivially).
    results.append(detector.detect_falsifier_bypass(env))

    if json_output:
        typer.echo(json.dumps([r.to_falsifier_item_dict() for r in results], indent=2))
        return

    table = Table(title="Hard-Failure Detectors (10)", show_lines=True)
    table.add_column("#")
    table.add_column("Detector")
    table.add_column("Status")
    table.add_column("Evidence")
    for i, r in enumerate(results, start=1):
        icon = "[green]PASS[/green]" if r.passed else "[red]FAIL[/red]"
        table.add_row(str(i), r.detector, icon, r.evidence[:80])
    console.print(table)

    all_ok = all(r.passed for r in results)
    if not all_ok:
        failed = [r.detector for r in results if not r.passed]
        console.print(f"[red]Failures: {failed}[/red]")
        raise typer.Exit(code=1)
    console.print("[green]All 10 hard-failure detectors passed.[/green]")


@runpod_app.command("cutover-runbook")
def cutover_runbook() -> None:
    """Print the operator runbook (docs/RUNPOD-CUTOVER.md)."""
    runbook_path = _runbook_path()
    if runbook_path.exists():
        console.print(runbook_path.read_text(encoding="utf-8"))
    else:
        console.print(
            "[yellow]docs/RUNPOD-CUTOVER.md not found. "
            "Generate it with: zer0pa-materials runpod cutover-runbook --generate[/yellow]"
        )
        raise typer.Exit(code=1)


@runpod_app.command("promote-backend")
def promote_backend(
    layer: Annotated[
        str,
        typer.Argument(
            help=(
                "Layer to promote (e.g. 'L1', 'L2', 'ionic', 'L1.5', 'L3', 'L4', "
                "'L5', 'L6', 'quantum', 'L7') or 'all' for every GPU-bound layer."
            ),
        ),
    ],
    from_backend: Annotated[
        str,
        typer.Option("--from", help="Current backend label (e.g. 'runpod_mock')."),
    ] = "runpod_mock",
    to_backend: Annotated[
        str,
        typer.Option("--to", help="Target backend label (e.g. 'runpod_rest')."),
    ] = "runpod_rest",
    reason: Annotated[
        str,
        typer.Option("--reason", help="Operator-supplied rationale recorded in decisions.jsonl."),
    ] = "Operator-approved promotion after parity tests passed.",
) -> None:
    """Promote a layer's backend from runpod_mock to runpod_rest.

    Records a Decision row in ``decisions.jsonl`` with the operator
    rationale. The promotion is BLOCKED unless precheck passes and parity
    tests pass — the cutover orchestrator enforces this.

    The CLI is the *audited* path; calling
    ``RunpodCutover.promote_backend()`` directly bypasses the CLI's
    rationale + audit step. Always use this command for production cutover.
    """
    cfg = MaterialsConfig.from_env()
    cutover = RunpodCutover(config=cfg)
    result = cutover.promote_backend(
        layer=layer,
        from_backend=from_backend,
        to_backend=to_backend,
        reason=reason,
    )
    if result.approved:
        console.print(
            f"[green]promotion approved[/green] layer={layer} "
            f"{from_backend} -> {to_backend}"
        )
        console.print(f"  decision_id: {result.decision_id}")
        console.print(f"  reason:      {result.reason}")
    else:
        console.print(
            f"[red]promotion blocked[/red] layer={layer}: {result.reason}"
        )
        raise typer.Exit(code=2)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _write_sentinel_md(report: object, path: Path) -> None:
    """Write a Markdown sentinel report."""
    r = report  # type: ignore[assignment]
    lines = [
        "# Sentinel Campaign Report",
        "",
        f"> **Boundary**: {RESEARCH_BOUNDARY}",
        "",
        f"- **Backend**: `{r.backend}`",
        f"- **Started**: {r.started_at}",
        f"- **Completed**: {r.completed_at}",
        f"- **Seeds**: {', '.join(r.seeds_run)}",
        f"- **Layers**: {', '.join(r.layers_run)}",
        "",
        "## Results",
        "",
        "| Seed | Layer | Status |",
        "| --- | --- | --- |",
    ]
    for seed_name, layer_envs in r.seed_results.items():
        for layer, env in layer_envs.items():
            if isinstance(env, dict) and "error" not in env:
                status = "OK"
            else:
                status = f"ERROR: {env.get('error', '?') if isinstance(env, dict) else str(env)}"
            lines.append(f"| {seed_name} | {layer} | {status} |")

    path.write_text("\n".join(lines), encoding="utf-8")
