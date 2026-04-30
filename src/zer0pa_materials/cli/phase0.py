"""Phase 0 CLI subcommands.

Registered as ``zer0pa-materials phase0 <subcommand>``.

Subcommands:
    phase0 extract <fixture>       Run LangGraph extraction stub on a fixture.
    phase0 query-optimade <element>  Run OPTIMADE stub query for an element.
"""

from __future__ import annotations

import json
from typing import Annotated, Optional

import typer
from rich.console import Console

from zer0pa_materials.adapters.phase0.langgraph_extraction import LangGraphExtractionWorkflow
from zer0pa_materials.adapters.phase0.optimade import OptimadeFederatedQueryAdapter
from zer0pa_materials.envelope.config import MaterialsConfig

phase0_app = typer.Typer(
    help="Phase 0 — literature mining and OPTIMADE query commands.",
    no_args_is_help=True,
)
console = Console()


@phase0_app.command("extract")
def extract(
    fixture: Annotated[
        str,
        typer.Argument(help="Fixture key: LLZO | Li6PS5Cl | Li-Mg-Zr-Cl-seed."),
    ] = "LLZO",
    doi: Annotated[
        str,
        typer.Option("--doi", help="DOI of the source paper (stub: used for manifest only)."),
    ] = "",
    pretty: Annotated[bool, typer.Option("--pretty/--compact")] = True,
) -> None:
    """Run the LangGraph extraction stub on a fixture and print the Envelope."""
    config = MaterialsConfig.from_env()
    adapter = LangGraphExtractionWorkflow(config=config)
    try:
        envelope = adapter.query({"fixture": fixture, "doi": doi})
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]Extraction failed: {exc}[/red]")
        raise typer.Exit(code=2)

    out = envelope.model_dump(mode="json")
    if pretty:
        typer.echo(json.dumps(out, indent=2, sort_keys=True))
    else:
        import orjson
        typer.echo(orjson.dumps(out, option=orjson.OPT_SORT_KEYS).decode())

    manifest = adapter.get_last_manifest()
    if manifest:
        console.print(
            f"[green]SourceManifest:[/green] {manifest.source_manifest_id}  "
            f"license={manifest.license_spdx}"
        )


@phase0_app.command("query-optimade")
def query_optimade(
    element: Annotated[
        str,
        typer.Argument(help="Element symbol to query (e.g. 'Li', 'La')."),
    ] = "Li",
    filter_str: Annotated[
        str,
        typer.Option("--filter", help="Raw OPTIMADE filter string (advanced)."),
    ] = "",
    pretty: Annotated[bool, typer.Option("--pretty/--compact")] = True,
) -> None:
    """Run the OPTIMADE federated query stub for an element."""
    config = MaterialsConfig.from_env()
    adapter = OptimadeFederatedQueryAdapter(config=config)
    elements = [element] if element else []
    try:
        envelope = adapter.query({"elements": elements, "filter": filter_str})
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]OPTIMADE query failed: {exc}[/red]")
        raise typer.Exit(code=2)

    out = envelope.model_dump(mode="json")
    hits = out.get("output", {}).get("hit_count", 0)
    console.print(f"[cyan]OPTIMADE stub:[/cyan] {hits} hit(s) for element={element!r}")

    if pretty:
        typer.echo(json.dumps(out, indent=2, sort_keys=True))
    else:
        import orjson
        typer.echo(orjson.dumps(out, option=orjson.OPT_SORT_KEYS).decode())
