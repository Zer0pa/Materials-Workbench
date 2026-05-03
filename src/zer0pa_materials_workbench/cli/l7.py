"""L7 orchestration CLI subcommands.

Registered as ``zer0pa-materials-workbench l7 <subcommand>``.

Subcommands:
    l7 create-campaign <campaign-id> --tenant ... --objective ...
    l7 dispatch <campaign-id> --candidates ...
    l7 acquire <campaign-id>
    l7 promote <campaign-id> <candidate-id>
    l7 resume <campaign-id>
    l7 state <campaign-id>
    l7 alabos-compile <candidate-id>
    l7 blocked
    l7 healthz
"""

from __future__ import annotations

import json
from typing import Annotated

import typer
from rich.console import Console

from zer0pa_materials_workbench.adapters.l7 import (
    AlabosExecutableInRecipeOnlyError,
    AlabOSProtocolCompilerStub,
    BoTorchAcquisitionAdapter,
    PrefectCampaignAdapter,
)
from zer0pa_materials_workbench.adapters.l7.base import L7CampaignParams
from zer0pa_materials_workbench.adapters.l7.botorch_acquisition import (
    AcquisitionInput,
    ForbiddenAcquisitionError,
)
from zer0pa_materials_workbench.audit.kg import MaterialsKG
from zer0pa_materials_workbench.audit.log import AuditLog
from zer0pa_materials_workbench.boundary import RESEARCH_BOUNDARY
from zer0pa_materials_workbench.envelope.config import MaterialsConfig
from zer0pa_materials_workbench.orchestration.campaign import Campaign, CampaignSpec
from zer0pa_materials_workbench.services.l7_service import BLOCKED_SOURCES

l7_app = typer.Typer(
    name="l7",
    help="L7 — orchestration / active-learning loop commands.",
    no_args_is_help=True,
)
console = Console()


def _resolve_paths(audit_dir: str | None, kg_path: str | None) -> tuple[AuditLog, MaterialsKG]:
    cfg = MaterialsConfig.from_env()
    paths = cfg.runtime_paths()
    log = AuditLog(audit_dir or paths["audit_dir"])
    kg = MaterialsKG(kg_path or paths["kg_db_path"])
    return log, kg


@l7_app.command("create-campaign")
def create_campaign(
    campaign_id: Annotated[str, typer.Argument(help="URN starting with 'campaign:'.")],
    tenant: Annotated[str, typer.Option(help="Tenant identifier.")] = "demo",
    objective: Annotated[str, typer.Option(help="Property target.")] = "Li-ion conductivity > 1e-3 S/cm",
    chemical_system: Annotated[str, typer.Option(help="Chemical system.")] = "Li-La-Zr-O",
    rights_claim_id: Annotated[str, typer.Option(help="rights:<id>.")] = "rights:default",
    reuse_scope: Annotated[str, typer.Option(help="tenant_only|shared_learning|open_science")] = "tenant_only",
    audit_dir: Annotated[str | None, typer.Option(help="Override audit dir.")] = None,
    kg_path: Annotated[str | None, typer.Option(help="Override KG sqlite path.")] = None,
) -> None:
    """Create a new campaign and emit the bootstrap envelope."""
    log, kg = _resolve_paths(audit_dir, kg_path)
    spec = CampaignSpec(
        campaign_id=campaign_id,
        tenant=tenant,
        objective=objective,
        chemical_system=chemical_system,
        rights_claim_id=rights_claim_id,
        reuse_scope=reuse_scope,
    )
    camp = Campaign.create(spec=spec, audit_log=log, kg=kg)
    adapter = PrefectCampaignAdapter()
    params = L7CampaignParams(
        campaign_id=campaign_id,
        candidate_id=f"candidate:{tenant}/bootstrap",
        tenant=tenant,
        objective=objective,
        rights_claim_id=rights_claim_id,
        reuse_scope=reuse_scope,
    )
    env = adapter.execute(params)
    camp.attach_envelope(env)
    console.print(f"[green]campaign created[/green] id={campaign_id} status={camp.status}")
    console.print(f"  bootstrap envelope: audit={env.audit.audit_record_id}")


@l7_app.command("dispatch")
def dispatch(
    campaign_id: Annotated[str, typer.Argument()],
    candidates: Annotated[str, typer.Option("--candidates", help="Comma-separated candidate URNs.")] = "candidate:demo/c1",
    fidelity: Annotated[str, typer.Option(help="Fidelity name.")] = "L2_stub",
    audit_dir: Annotated[str | None, typer.Option()] = None,
    kg_path: Annotated[str | None, typer.Option()] = None,
) -> None:
    """Fan out N candidates across the parsl-shaped fanout adapter."""
    from zer0pa_materials_workbench.adapters.l7 import ParslFanoutAdapter

    log, kg = _resolve_paths(audit_dir, kg_path)
    try:
        camp = Campaign.resume_from_audit(campaign_id, log, kg)
    except KeyError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=2)
    parent_ref = f"audit:l7:campaign:{campaign_id}:bootstrap"
    cids = [c.strip() for c in candidates.split(",") if c.strip()]
    adapter = ParslFanoutAdapter()
    params = L7CampaignParams(
        campaign_id=campaign_id,
        candidate_id=cids[0],
        fidelity=fidelity,
    )
    envs = adapter.fan_out(params, cids, parent_audit_ref=parent_ref)
    for env in envs:
        camp.register_candidate(env.candidate_id)
        camp.attach_envelope(env)
    if camp.status == "created":
        camp.transition_to("hypothesising", rationale="dispatch")
    if camp.status == "hypothesising":
        camp.transition_to("generating", rationale="dispatch fan-out")
    console.print(f"[green]dispatched {len(envs)} candidates[/green] status={camp.status}")


@l7_app.command("acquire")
def acquire(
    campaign_id: Annotated[str, typer.Argument()],
    candidate_ids: Annotated[str, typer.Option("--candidates", help="Comma-separated.")] = "candidate:demo/c1",
    fidelity: Annotated[str, typer.Option()] = "L2_stub",
    allow_legacy_qei: Annotated[bool, typer.Option()] = False,
) -> None:
    """Run one BoTorch-style acquisition step."""
    cids = [c.strip() for c in candidate_ids.split(",") if c.strip()]
    inputs = [
        AcquisitionInput(
            candidate_id=c,
            predicted_value=0.0,
            posterior_variance=0.05,
            fidelity_options={fidelity: 1.0, "L1_DFT_PBE": 10.0},
        )
        for c in cids
    ]
    adapter = BoTorchAcquisitionAdapter(allow_legacy_qei=allow_legacy_qei)
    try:
        result = adapter.acquire(inputs)
    except ForbiddenAcquisitionError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=2)
    typer.echo(json.dumps(result.model_dump(mode="json"), indent=2, sort_keys=True))


@l7_app.command("promote")
def promote(
    campaign_id: Annotated[str, typer.Argument()],
    candidate_id: Annotated[str, typer.Argument()],
    audit_dir: Annotated[str | None, typer.Option()] = None,
    kg_path: Annotated[str | None, typer.Option()] = None,
) -> None:
    """Run the acceptance gate and promote/reject the candidate.

    This minimal CLI surface skips most envelope details; the REST stub
    service is the place to wire full evidence into the gate.
    """
    log, kg = _resolve_paths(audit_dir, kg_path)
    try:
        camp = Campaign.resume_from_audit(campaign_id, log, kg)
    except KeyError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=2)
    if candidate_id not in camp.state.candidates:
        console.print(f"[red]unknown candidate {candidate_id!r} in campaign[/red]")
        raise typer.Exit(code=2)
    cur = camp.candidate(candidate_id)
    if cur.status != "evidence_complete":
        console.print(
            f"[yellow]candidate {candidate_id} status={cur.status}; advance to evidence_complete first[/yellow]"
        )
        raise typer.Exit(code=2)
    # No real evidence available at the CLI; reject with reason.
    camp.transition_candidate(
        candidate_id,
        "rejected",
        rationale="CLI promote called without layer envelopes — gate would block",
        rejection_reason="missing_layer_envelopes",
    )
    console.print("[yellow]candidate rejected — CLI promote requires evidence; use REST service[/yellow]")


@l7_app.command("resume")
def resume(
    campaign_id: Annotated[str, typer.Argument()],
    audit_dir: Annotated[str | None, typer.Option()] = None,
    kg_path: Annotated[str | None, typer.Option()] = None,
) -> None:
    """Reconstruct a campaign from runs.jsonl + decisions.jsonl + events.jsonl."""
    log, kg = _resolve_paths(audit_dir, kg_path)
    try:
        camp = Campaign.resume_from_audit(campaign_id, log, kg)
    except KeyError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=2)
    console.print(f"[green]resumed[/green] campaign={campaign_id} status={camp.status}")
    console.print(f"  candidates: {len(camp.state.candidates)}")


@l7_app.command("state")
def state(
    campaign_id: Annotated[str, typer.Argument()],
    audit_dir: Annotated[str | None, typer.Option()] = None,
    kg_path: Annotated[str | None, typer.Option()] = None,
) -> None:
    """Show the current state snapshot of a campaign."""
    log, kg = _resolve_paths(audit_dir, kg_path)
    try:
        camp = Campaign.resume_from_audit(campaign_id, log, kg)
    except KeyError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=2)
    snapshot = {
        "campaign_id": campaign_id,
        "status": camp.status,
        "spec": camp.state.spec.model_dump(mode="json"),
        "candidate_count": len(camp.state.candidates),
        "candidates_by_status": {},
        "rejected": list(camp.state.rejected_candidate_ids),
        "promoted": list(camp.state.promoted_candidate_ids),
    }
    by_status: dict[str, int] = {}
    for rec in camp.state.candidates.values():
        by_status[rec.status] = by_status.get(rec.status, 0) + 1
    snapshot["candidates_by_status"] = by_status
    typer.echo(json.dumps(snapshot, indent=2, sort_keys=True))


@l7_app.command("alabos-compile")
def alabos_compile(
    candidate_id: Annotated[str, typer.Argument()],
    alabos_mode: Annotated[str, typer.Option(help="recipe_only|phase2_hardware")] = "recipe_only",
) -> None:
    """Compile a synthesis recipe into a recipe-only AlabOS protocol candidate."""
    compiler = AlabOSProtocolCompilerStub(alabos_mode=alabos_mode)  # type: ignore[arg-type]
    try:
        protocol = compiler.compile(candidate_id, recipe={})
    except AlabosExecutableInRecipeOnlyError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=2)
    typer.echo(json.dumps(protocol.model_dump(mode="json"), indent=2, sort_keys=True))


@l7_app.command("blocked")
def blocked() -> None:
    """Print the static BlockedSourceManifest entries for L7 optional deps."""
    typer.echo(json.dumps(BLOCKED_SOURCES, indent=2, sort_keys=True))


@l7_app.command("healthz")
def healthz() -> None:
    """Print L7 health info."""
    cfg = MaterialsConfig.from_env()
    payload = {
        "status": "ok",
        "layer": "L7",
        "research_boundary": RESEARCH_BOUNDARY,
        "L7_ORCHESTRATOR_BACKEND": cfg.L7_ORCHESTRATOR_BACKEND,
        "ALABOS_MODE": cfg.ALABOS_MODE,
        "allow_legacy_qei": cfg.allow_legacy_qei,
        "available_backends": {
            "prefect": PrefectCampaignAdapter.is_real_backend(),
            "parsl": False,  # set lazily; module probes once
            "aiida": False,
            "atomate2": False,
            "langgraph": False,
            "botorch": BoTorchAcquisitionAdapter.is_real_backend(),
        },
    }
    typer.echo(json.dumps(payload, indent=2, sort_keys=True))
