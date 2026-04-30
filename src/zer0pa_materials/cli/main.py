"""``zer0pa-materials`` Typer-based CLI.

Commands at A0/A1:

* ``envelope-schema`` — print the JSON schema of the universal envelope.
* ``check-config``  — load ``.env`` via :class:`MaterialsConfig` and
  validate. Prints cutover blockers if any.
* ``audit add-source`` — append a :class:`SourceManifest` to ``sources.jsonl``
  via the hash-chained audit log.
* ``audit add-blocked-source`` — append a :class:`BlockedSourceManifest`
  for a lookup that could not complete.
* ``audit validate-chain`` — validate the hash chain for a category file.
* ``audit reconstruct`` — print the brain-functionality state for a repo root.
* ``run-falsification-wave`` — placeholder; downstream waves wire to the
  real implementation in :mod:`zer0pa_materials.falsifiers`.
* ``version`` — print package version.

The CLI is intentionally thin. It exists so:

1. CI can call ``zer0pa-materials envelope-schema > runtime/schemas/envelope.v1.schema.json``
   to regenerate the contract artifact in one place.
2. Operators can sanity-check a ``.env`` before triggering an overnight run.
3. Subagents can append source manifests / blocked sources from the shell.
"""

from __future__ import annotations

import datetime as _dt
import json
import sys
from pathlib import Path
from typing import Annotated, Optional

import orjson
import typer
from rich.console import Console

from zer0pa_materials import __version__
from zer0pa_materials.audit import (
    AUDIT_CATEGORIES,
    AuditLog,
    BlockedSourceManifest,
    SourceManifest,
    reconstruct_from_repo,
)
from zer0pa_materials.cli.phase0 import phase0_app  # phase0 wave (kept)
from zer0pa_materials.cli.l6 import l6_app  # l6 wave (kept)
from zer0pa_materials.cli.ionic import app as ionic_app  # ionic wave
from zer0pa_materials.cli.l3 import l3_app  # l3 wave
from zer0pa_materials.cli.l4 import l4_app  # l4 wave
from zer0pa_materials.envelope import (
    LAYER_OUTPUT_REGISTRY,
    Envelope,
    MaterialsConfig,
)

app = typer.Typer(
    name="zer0pa-materials",
    help="Zer0pa Materials — research infrastructure for in silico materials science discovery.",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()


@app.command("version")
def version() -> None:
    """Print the package version."""
    typer.echo(__version__)


@app.command("envelope-schema")
def envelope_schema(
    layer: Annotated[
        str | None,
        typer.Option(
            "--layer",
            help="If set, print the layer-output schema instead of the envelope schema.",
        ),
    ] = None,
    pretty: Annotated[
        bool,
        typer.Option("--pretty/--compact", help="Pretty-print the JSON."),
    ] = True,
) -> None:
    """Print the JSON schema of the universal envelope (or a layer-output schema)."""
    if layer is None:
        schema = Envelope.model_json_schema()
    else:
        if layer not in LAYER_OUTPUT_REGISTRY:
            valid = ", ".join(sorted(LAYER_OUTPUT_REGISTRY))
            raise typer.BadParameter(f"unknown layer {layer!r}; valid: {valid}")
        schema = LAYER_OUTPUT_REGISTRY[layer].model_json_schema()
    if pretty:
        typer.echo(json.dumps(schema, indent=2, sort_keys=True))
    else:
        typer.echo(orjson.dumps(schema, option=orjson.OPT_SORT_KEYS).decode())


@app.command("check-config")
def check_config() -> None:
    """Load .env via MaterialsConfig and validate. Prints cutover blockers."""
    try:
        cfg = MaterialsConfig.from_env()
    except Exception as exc:  # noqa: BLE001 — surface to user
        console.print(f"[red]Config load failed: {exc}[/red]")
        raise typer.Exit(code=2)
    console.print("[green]Config loaded.[/green]")
    console.print(f"  MATERIALS_MODE = {cfg.MATERIALS_MODE}")
    console.print(f"  ALABOS_MODE    = {cfg.ALABOS_MODE}")
    console.print(f"  ARTIFACT_BACKEND = {cfg.ARTIFACT_BACKEND}")
    console.print(f"  KG_BACKEND       = {cfg.KG_BACKEND}")
    blockers = cfg.validate_for_runpod_cutover()
    if blockers:
        console.print(f"[yellow]Cutover blockers ({len(blockers)}):[/yellow]")
        for b in blockers:
            console.print(f"  - {b}")
    else:
        console.print("[green]No cutover blockers.[/green]")


@app.command("run-falsification-wave")
def run_falsification_wave() -> None:
    """Placeholder for the full falsification wave runner.

    The real implementation lives in :mod:`zer0pa_materials.falsifiers` (built
    by Wave 9). This command exists in A0 so the CLI surface is stable and
    downstream waves can wire real behaviour without renaming.
    """
    console.print("[yellow]falsification wave runner is not implemented in A0[/yellow]")
    console.print("downstream waves: see zer0pa_materials.falsifiers")
    sys.exit(0)


# ----------------------------------------------------------------------------
# Audit subcommands
# ----------------------------------------------------------------------------


audit_app = typer.Typer(help="Audit log family operations (PRD §Audit Trail And KG).")
app.add_typer(audit_app, name="audit")


@audit_app.command("add-source")
def audit_add_source(
    source_manifest_id: Annotated[str, typer.Option(help="URN starting with 'src:'.")],
    source_type: Annotated[str, typer.Option(help="paper|api|doc|model_card|license|dataset|repo|spec")],
    locator: Annotated[str, typer.Option(help="DOI, URL, arXiv ID, etc.")],
    license_spdx: Annotated[str, typer.Option(help="SPDX expression, e.g. 'MIT'.")],
    summary: Annotated[str, typer.Option(help="Short plain-English summary.")],
    decision_impact: Annotated[str, typer.Option(help="Which decision/route this supports.")],
    audit_dir: Annotated[
        Optional[str],
        typer.Option(help="Override audit directory (default: from .env)."),
    ] = None,
    redaction: Annotated[str, typer.Option(help="none|partial|full")] = "none",
    sha256: Annotated[Optional[str], typer.Option(help="sha256:<hex> if locally captured")] = None,
) -> None:
    """Append a SourceManifest to ``sources.jsonl``."""
    cfg = MaterialsConfig.from_env()
    target_dir = Path(audit_dir) if audit_dir else cfg.runtime_paths()["audit_dir"]
    log = AuditLog(target_dir)
    manifest = SourceManifest(
        source_manifest_id=source_manifest_id,
        source_type=source_type,  # type: ignore[arg-type]
        locator=locator,
        retrieval_date=_dt.datetime.now(tz=_dt.timezone.utc).isoformat(timespec="microseconds"),
        license_spdx=license_spdx,
        summary=summary,
        decision_impact=decision_impact,
        hash=sha256,
        redaction=redaction,  # type: ignore[arg-type]
    )
    row = log.append_event("sources", manifest.model_dump(mode="json"))
    console.print(f"[green]appended sources row[/green] event_hash={row.event_hash}")


@audit_app.command("add-blocked-source")
def audit_add_blocked_source(
    source_manifest_id: Annotated[str, typer.Option(help="URN starting with 'src:'.")],
    attempted_locator: Annotated[str, typer.Option(help="What we tried to fetch.")],
    blocker_reason: Annotated[
        str,
        typer.Option(
            help="unavailable_credentials|license_unverified|unreachable|rate_limited|policy|other"
        ),
    ],
    blocker_detail: Annotated[str, typer.Option(help="Human-readable diagnostic.")],
    retry_strategy: Annotated[str, typer.Option(help="Concrete next step for operator.")],
    audit_dir: Annotated[
        Optional[str],
        typer.Option(help="Override audit directory (default: from .env)."),
    ] = None,
) -> None:
    """Append a BlockedSourceManifest to ``sources.jsonl``."""
    cfg = MaterialsConfig.from_env()
    target_dir = Path(audit_dir) if audit_dir else cfg.runtime_paths()["audit_dir"]
    log = AuditLog(target_dir)
    blocked = BlockedSourceManifest(
        source_manifest_id=source_manifest_id,
        attempted_locator=attempted_locator,
        blocker_reason=blocker_reason,  # type: ignore[arg-type]
        blocker_detail=blocker_detail,
        retry_strategy=retry_strategy,
    )
    payload = blocked.model_dump(mode="json")
    payload["__blocked__"] = True
    row = log.append_event("sources", payload)
    console.print(f"[yellow]appended blocked sources row[/yellow] event_hash={row.event_hash}")


@audit_app.command("validate-chain")
def audit_validate_chain(
    category: Annotated[
        str, typer.Argument(help=f"One of: {', '.join(AUDIT_CATEGORIES)}.")
    ],
    audit_dir: Annotated[
        Optional[str],
        typer.Option(help="Override audit directory (default: from .env)."),
    ] = None,
) -> None:
    """Validate the hash chain for one audit category."""
    if category not in AUDIT_CATEGORIES:
        raise typer.BadParameter(
            f"unknown category {category!r}; valid: {', '.join(AUDIT_CATEGORIES)}"
        )
    cfg = MaterialsConfig.from_env()
    target_dir = Path(audit_dir) if audit_dir else cfg.runtime_paths()["audit_dir"]
    log = AuditLog(target_dir)
    result = log.validate_chain(category)  # type: ignore[arg-type]
    if result.ok:
        console.print(
            f"[green]chain OK[/green] category={category} rows={result.checked_rows}"
        )
    else:
        console.print(
            f"[red]chain BAD[/red] category={category} rows={result.checked_rows} "
            f"first_bad_index={result.first_bad_index}"
        )
        for err in result.errors:
            console.print(f"  - {err}")
        sys.exit(2)


@audit_app.command("reconstruct")
def audit_reconstruct(
    repo_root: Annotated[
        Optional[str],
        typer.Argument(help="Repository root (default: cwd)."),
    ] = None,
) -> None:
    """Reconstruct campaign state from repo (PRD §Brain-functionality)."""
    root = Path(repo_root) if repo_root else Path.cwd()
    state = reconstruct_from_repo(root)
    typer.echo(json.dumps(state.model_dump(mode="json"), indent=2, sort_keys=True))


app.add_typer(phase0_app, name="phase0")
app.add_typer(l6_app, name="l6")
app.add_typer(ionic_app, name="ionic")
app.add_typer(l3_app, name="l3")
app.add_typer(l4_app, name="l4")

# Allow ``python -m zer0pa_materials.cli.main`` invocation.
if __name__ == "__main__":  # pragma: no cover
    app()
