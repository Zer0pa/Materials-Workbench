"""L6 generative discovery CLI subcommands.

Registered as ``zer0pa-materials l6 <subcommand>``.

Subcommands:
    l6 generate <chemical-system>   Run L6 stub generators and print Envelopes.
    l6 evaluate                     Run LeMat-GenBench U+N evaluation on a batch.
"""

from __future__ import annotations

import json
from typing import Annotated

import typer
from rich.console import Console

from zer0pa_materials_workbench.adapters.l6.crystallm import CrystaLlmCifGeneratorAdapter
from zer0pa_materials_workbench.adapters.l6.diffcsp import DiffCspGeneratorAdapter
from zer0pa_materials_workbench.adapters.l6.lematgen_eval import LeMatGenBenchEvaluatorAdapter
from zer0pa_materials_workbench.adapters.l6.mattergen import MatterGenGeneratorAdapter
from zer0pa_materials_workbench.envelope.config import MaterialsConfig

l6_app = typer.Typer(
    help="L6 — generative discovery commands.",
    no_args_is_help=True,
)
console = Console()


@l6_app.command("generate")
def generate(
    chemical_system: Annotated[
        str,
        typer.Argument(help="Chemical system (e.g. 'Li-La-Zr-O', 'Li-P-S-Cl')."),
    ] = "Li-La-Zr-O",
    n_candidates: Annotated[
        int,
        typer.Option("--n", help="Candidates per adapter (max 5)."),
    ] = 2,
    adapters: Annotated[
        str,
        typer.Option("--adapters", help="Comma-separated: mattergen,diffcsp,crystallm."),
    ] = "mattergen,diffcsp,crystallm",
    pretty: Annotated[bool, typer.Option("--pretty/--compact")] = True,
) -> None:
    """Run L6 stub generators and print Envelopes (novelty_status=pending)."""
    config = MaterialsConfig.from_env()
    constraints = {
        "chemical_system": chemical_system,
        "target_conductivity_S_per_cm": 1e-3,
    }
    adapter_set = {a.strip().lower() for a in adapters.split(",")}
    all_envelopes = []

    if "mattergen" in adapter_set:
        mg = MatterGenGeneratorAdapter(config=config, n_candidates=n_candidates)
        envs = mg.generate(constraints)
        all_envelopes.extend(envs)
        console.print(f"[cyan]MatterGen:[/cyan] {len(envs)} candidates")

    if "diffcsp" in adapter_set:
        dc = DiffCspGeneratorAdapter(config=config, n_candidates=n_candidates)
        envs = dc.generate(constraints)
        all_envelopes.extend(envs)
        console.print(f"[cyan]DiffCSP:[/cyan] {len(envs)} candidates")

    if "crystallm" in adapter_set:
        cl = CrystaLlmCifGeneratorAdapter(config=config)
        envs = cl.generate(constraints)
        all_envelopes.extend(envs)
        console.print(f"[cyan]CrystaLLM:[/cyan] {len(envs)} candidates")

    out = [e.model_dump(mode="json") for e in all_envelopes]
    if pretty:
        typer.echo(json.dumps(out, indent=2, sort_keys=True))
    else:
        import orjson
        typer.echo(orjson.dumps(out, option=orjson.OPT_SORT_KEYS).decode())


@l6_app.command("evaluate")
def evaluate_batch(
    chemical_system: Annotated[
        str,
        typer.Argument(help="Chemical system to generate and evaluate."),
    ] = "Li-La-Zr-O",
    n_candidates: Annotated[
        int,
        typer.Option("--n", help="Candidates per adapter."),
    ] = 2,
) -> None:
    """Generate candidates and run LeMat-GenBench U+N evaluation."""
    config = MaterialsConfig.from_env()
    constraints = {"chemical_system": chemical_system, "target_conductivity_S_per_cm": 1e-3}

    all_envelopes = []
    for AdapterClass, name in [
        (MatterGenGeneratorAdapter, "MatterGen"),
        (DiffCspGeneratorAdapter, "DiffCSP"),
        (CrystaLlmCifGeneratorAdapter, "CrystaLLM"),
    ]:
        try:
            if name in ("MatterGen", "DiffCSP"):
                adapter = AdapterClass(config=config, n_candidates=n_candidates)
            else:
                adapter = AdapterClass(config=config)
            envs = adapter.generate(constraints)
            all_envelopes.extend(envs)
        except Exception as exc:
            console.print(f"[yellow]{name} skipped: {exc}[/yellow]")

    evaluator = LeMatGenBenchEvaluatorAdapter()
    result = evaluator.evaluate(all_envelopes)

    console.print("[bold]LeMat-GenBench S.U.N. Results[/bold]")
    console.print(f"  Total candidates : {result.n_total}")
    console.print(f"  Unique (U)       : {result.n_unique} / {result.n_total} [{result.u_score:.2f}]")
    console.print(f"  Novel (N)        : {result.n_novel} / {result.n_total} [{result.n_score:.2f}]")
    console.print("  Stable (S)       : None — deferred to L1 DFT validation")
