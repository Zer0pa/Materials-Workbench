"""L7 orchestration REST stub service (FastAPI).

Endpoints:

* ``POST /v1/l7/campaigns``                        — CreateCampaignRequest -> EnvelopeL7
* ``POST /v1/l7/campaigns/{id}/dispatch``          — DispatchRequest -> EnvelopeL7
* ``POST /v1/l7/campaigns/{id}/acquire``           — AcquireRequest -> EnvelopeL7  (BoTorch loop iteration)
* ``POST /v1/l7/campaigns/{id}/promote-candidate`` — PromoteRequest -> EnvelopeL7
* ``POST /v1/l7/campaigns/{id}/resume``            — ResumeRequest  -> EnvelopeL7  (rebuild from audit log)
* ``GET  /v1/l7/campaigns/{id}/state``             — CampaignState snapshot
* ``POST /v1/l7/alabos/compile-protocol``          — CompileProtocolRequest -> EnvelopeL7
* ``GET  /v1/l7/healthz``                          — liveness probe

The service is in-memory: campaign state is held in an
``_ACTIVE_CAMPAIGNS`` dict keyed by ``campaign_id``. The audit log + KG
are file-backed via :class:`MaterialsConfig`. The service is therefore
restart-safe: each request can call :func:`Campaign.resume_from_audit`
to rehydrate.
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from zer0pa_materials_workbench.adapters.l7 import (
    AlabosExecutableInRecipeOnlyError,
    AlabOSProtocolCompilerStub,
    BoTorchAcquisitionAdapter,
    ParslFanoutAdapter,
    PrefectCampaignAdapter,
)
from zer0pa_materials_workbench.adapters.l7.base import L7CampaignParams
from zer0pa_materials_workbench.adapters.l7.botorch_acquisition import (
    AcquisitionFunctionName,
    AcquisitionInput,
    ForbiddenAcquisitionError,
)
from zer0pa_materials_workbench.audit.kg import MaterialsKG
from zer0pa_materials_workbench.audit.log import AuditLog
from zer0pa_materials_workbench.audit.rights import RightsClaim
from zer0pa_materials_workbench.boundary import RESEARCH_BOUNDARY
from zer0pa_materials_workbench.envelope import Envelope
from zer0pa_materials_workbench.envelope.config import MaterialsConfig
from zer0pa_materials_workbench.orchestration.acceptance_gates import (
    AcceptanceGate,
    GateContext,
)
from zer0pa_materials_workbench.orchestration.campaign import Campaign, CampaignSpec

__all__ = [
    "BLOCKED_SOURCES",
    "L7_SERVICE_NAME",
    "L7_SERVICE_VERSION",
    "create_l7_app",
    "l7_app",
]


L7_SERVICE_NAME: str = "L7OrchestrationService"
L7_SERVICE_VERSION: str = "0.1.0"


# Static BlockedSourceManifest entries for L7 orchestration optional deps.
BLOCKED_SOURCES: list[dict[str, str]] = [
    {
        "source_manifest_id": "src:l7:prefect",
        "attempted_locator": "https://github.com/PrefectHQ/prefect",
        "blocker_reason": "license_unverified",
        "blocker_detail": (
            "Prefect Apache-2.0 — verified, but optional under CPU-first build. "
            "Unblock at Runpod cutover by installing prefect>=3.0."
        ),
        "retry_strategy": "pip install prefect>=3.0; restart L7 service",
    },
    {
        "source_manifest_id": "src:l7:parsl",
        "attempted_locator": "https://github.com/Parsl/parsl",
        "blocker_reason": "license_unverified",
        "blocker_detail": (
            "Parsl Apache-2.0 — verified, but optional under CPU-first build."
        ),
        "retry_strategy": "pip install parsl; restart L7 service",
    },
    {
        "source_manifest_id": "src:l7:aiida",
        "attempted_locator": "https://github.com/aiidateam/aiida-core",
        "blocker_reason": "license_unverified",
        "blocker_detail": (
            "AiiDA MIT — verified, but optional under CPU-first build."
        ),
        "retry_strategy": "pip install aiida-core; restart L7 service",
    },
    {
        "source_manifest_id": "src:l7:atomate2",
        "attempted_locator": "https://github.com/materialsproject/atomate2",
        "blocker_reason": "license_unverified",
        "blocker_detail": (
            "atomate2 BSD — verified, but optional under CPU-first build."
        ),
        "retry_strategy": "pip install atomate2; restart L7 service",
    },
    {
        "source_manifest_id": "src:l7:langgraph",
        "attempted_locator": "https://github.com/langchain-ai/langgraph",
        "blocker_reason": "license_unverified",
        "blocker_detail": (
            "LangGraph MIT — verified, but optional under CPU-first build."
        ),
        "retry_strategy": "pip install langgraph; restart L7 service",
    },
    {
        "source_manifest_id": "src:l7:botorch",
        "attempted_locator": "https://github.com/pytorch/botorch",
        "blocker_reason": "license_unverified",
        "blocker_detail": (
            "BoTorch MIT — verified, but optional under CPU-first build. "
            "When unblocked, also expect torch + ax-platform."
        ),
        "retry_strategy": "pip install botorch ax-platform; restart L7 service",
    },
    {
        "source_manifest_id": "src:l7:ax",
        "attempted_locator": "https://github.com/facebook/Ax",
        "blocker_reason": "license_unverified",
        "blocker_detail": "Ax MIT — verified, but optional.",
        "retry_strategy": "pip install ax-platform",
    },
    {
        "source_manifest_id": "src:l7:alabos",
        "attempted_locator": "https://github.com/CederGroupHub/alab_management",
        "blocker_reason": "policy",
        "blocker_detail": (
            "AlabOS MIT (CederGroupHub/alab_management) — Phase 1 is recipe_only. "
            "Hardware closure deferred to Phase 2 (PRD §AlabOS Integration)."
        ),
        "retry_strategy": "Phase 2: install alab_management and unset ALABOS_MODE=recipe_only",
    },
]


# In-memory campaign state.
_ACTIVE_CAMPAIGNS: dict[str, Campaign] = {}


def _get_audit_and_kg(audit_dir: str | None = None, kg_path: str | None = None) -> tuple[AuditLog, MaterialsKG]:
    cfg = MaterialsConfig.from_env()
    paths = cfg.runtime_paths()
    log = AuditLog(audit_dir or paths["audit_dir"])
    kg = MaterialsKG(kg_path or paths["kg_db_path"])
    return log, kg


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class CreateCampaignRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    campaign_id: str = Field(..., description="URN starting with 'campaign:'.")
    tenant: str
    objective: str
    chemical_system: str = ""
    rights_claim_id: str = "rights:default"
    reuse_scope: str = "tenant_only"
    audit_dir: str | None = None
    kg_path: str | None = None


class DispatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    campaign_id: str
    candidate_ids: list[str] = Field(..., min_length=1)
    fidelity: str = "L2_stub"
    audit_dir: str | None = None
    kg_path: str | None = None


class AcquireRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    campaign_id: str
    candidates: list[dict[str, Any]] = Field(..., min_length=1)
    requested_acquisition: AcquisitionFunctionName | None = None
    allow_legacy_qei: bool = False
    audit_dir: str | None = None
    kg_path: str | None = None


class PromoteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    campaign_id: str
    candidate_id: str
    rights_claim_id: str = "rights:default"
    rights_data_class: str = "raw_simulation_output"
    rights_contract_mode: str = "strict_sovereign"
    aggregate_disagreement_score: float | None = None
    layer_envelopes: list[dict[str, Any]] = Field(default_factory=list)
    audit_dir: str | None = None
    kg_path: str | None = None


class ResumeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    campaign_id: str
    audit_dir: str | None = None
    kg_path: str | None = None


class CompileProtocolRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    alabos_mode: Literal["recipe_only", "phase2_hardware"] = "recipe_only"
    recipe: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------


def create_l7_app() -> FastAPI:
    app = FastAPI(
        title="Zer0pa Materials — L7 Orchestration Service",
        description=(
            "REST stub for L7 campaigns and active-learning loop. "
            "Research infrastructure for in silico materials science discovery. "
            "Outputs are research artifacts. No regulatory certification claims."
        ),
        version=L7_SERVICE_VERSION,
    )

    # ----- healthz -----

    @app.get("/v1/l7/healthz")
    async def healthz() -> dict[str, str]:
        return {
            "status": "ok",
            "layer": "L7",
            "research_boundary": RESEARCH_BOUNDARY,
        }

    # ----- create campaign -----

    @app.post("/v1/l7/campaigns")
    async def create_campaign(req: CreateCampaignRequest) -> dict[str, Any]:
        log, kg = _get_audit_and_kg(req.audit_dir, req.kg_path)
        spec = CampaignSpec(
            campaign_id=req.campaign_id,
            tenant=req.tenant,
            objective=req.objective,
            chemical_system=req.chemical_system,
            rights_claim_id=req.rights_claim_id,
            reuse_scope=req.reuse_scope,
        )
        try:
            camp = Campaign.create(spec=spec, audit_log=log, kg=kg)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        _ACTIVE_CAMPAIGNS[req.campaign_id] = camp
        # Run a Prefect-style adapter to emit a campaign-bootstrap envelope.
        adapter = PrefectCampaignAdapter()
        params = L7CampaignParams(
            campaign_id=req.campaign_id,
            candidate_id=f"candidate:{req.tenant}/bootstrap",
            tenant=req.tenant,
            objective=req.objective,
            rights_claim_id=req.rights_claim_id,
            reuse_scope=req.reuse_scope,
        )
        env = adapter.execute(params)
        camp.attach_envelope(env)
        return env.model_dump(mode="json")

    # ----- dispatch -----

    @app.post("/v1/l7/campaigns/dispatch")
    async def dispatch(req: DispatchRequest) -> list[dict[str, Any]]:
        campaign_id = req.campaign_id

        camp = _ACTIVE_CAMPAIGNS.get(campaign_id)
        if camp is None:
            log, kg = _get_audit_and_kg(req.audit_dir, req.kg_path)
            try:
                camp = Campaign.resume_from_audit(campaign_id, log, kg)
            except KeyError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            _ACTIVE_CAMPAIGNS[campaign_id] = camp
        adapter = ParslFanoutAdapter()
        # Use the first decision_id (which is the campaign bootstrap audit)
        # as the parent reference. We rebuild parent_audit_ref from the
        # last_event_hash to keep the back_edges schema valid.
        parent_ref = f"audit:l7:campaign:{campaign_id}:bootstrap"
        params = L7CampaignParams(
            campaign_id=campaign_id,
            candidate_id=req.candidate_ids[0],
            fidelity=req.fidelity,
        )
        envs = adapter.fan_out(params, req.candidate_ids, parent_audit_ref=parent_ref)
        # Register and attach each child envelope.
        for env in envs:
            camp.register_candidate(env.candidate_id)
            camp.attach_envelope(env)
        # Advance campaign state if applicable.
        if camp.status == "created":
            camp.transition_to("hypothesising", rationale="dispatch")
        if camp.status == "hypothesising":
            camp.transition_to("generating", rationale="dispatch fan-out")
        return [e.model_dump(mode="json") for e in envs]

    # ----- acquire -----

    @app.post("/v1/l7/campaigns/acquire")
    async def acquire(req: AcquireRequest) -> dict[str, Any]:
        campaign_id = req.campaign_id
        camp = _ACTIVE_CAMPAIGNS.get(campaign_id)
        if camp is None:
            log, kg = _get_audit_and_kg(req.audit_dir, req.kg_path)
            try:
                camp = Campaign.resume_from_audit(campaign_id, log, kg)
            except KeyError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            _ACTIVE_CAMPAIGNS[campaign_id] = camp
        adapter = BoTorchAcquisitionAdapter(allow_legacy_qei=req.allow_legacy_qei)
        try:
            inputs = [AcquisitionInput.model_validate(c) for c in req.candidates]
            result = adapter.acquire(inputs, requested_acquisition=req.requested_acquisition)
        except ForbiddenAcquisitionError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        # Wrap in an L7 envelope using the top-ranked candidate.
        top = result.ranked_candidates[0]
        params = L7CampaignParams(
            campaign_id=campaign_id,
            candidate_id=top.candidate_id,
            fidelity=top.recommended_fidelity,
        )
        env = adapter.execute(params)
        camp.register_candidate(top.candidate_id)
        camp.attach_envelope(env)
        return {
            "envelope": env.model_dump(mode="json"),
            "acquisition": result.model_dump(mode="json"),
        }

    # ----- promote -----

    @app.post("/v1/l7/campaigns/promote-candidate")
    async def promote(req: PromoteRequest) -> dict[str, Any]:
        campaign_id = req.campaign_id
        camp = _ACTIVE_CAMPAIGNS.get(campaign_id)
        if camp is None:
            log, kg = _get_audit_and_kg(req.audit_dir, req.kg_path)
            try:
                camp = Campaign.resume_from_audit(campaign_id, log, kg)
            except KeyError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            _ACTIVE_CAMPAIGNS[campaign_id] = camp
        # Assemble GateContext.
        rights_claim = RightsClaim(
            rights_claim_id=req.rights_claim_id,
            tenant=camp.state.spec.tenant,
            data_class=req.rights_data_class,  # type: ignore[arg-type]
            ownership="customer",
            reuse_scope=camp.state.spec.reuse_scope,  # type: ignore[arg-type]
            contract_mode=req.rights_contract_mode,  # type: ignore[arg-type]
            rationale="campaign-default",
        )
        layer_envelopes: dict[str, Envelope] = {}
        for raw in req.layer_envelopes:
            env = Envelope.model_validate(raw)
            layer_envelopes[env.layer] = env
        ctx = GateContext(
            candidate_id=req.candidate_id,
            campaign_id=campaign_id,
            layer_envelopes=layer_envelopes,
            rights_claim=rights_claim,
            rejected_candidate_ids=camp.rejected_set(),
            rejected_structure_hashes=camp.rejected_hash_set(),
            aggregate_disagreement_score=req.aggregate_disagreement_score,
        )
        gate = AcceptanceGate(include_ionic_battery_evidence=False)
        verdict = gate.evaluate(ctx)
        # Emit a wrapping L7 envelope with gate verdict.
        from zer0pa_materials_workbench.adapters.l7.base import (
            L7CampaignParams,
            make_l7_envelope,
        )
        from zer0pa_materials_workbench.envelope import L7CampaignOutput

        params = L7CampaignParams(
            campaign_id=campaign_id,
            candidate_id=req.candidate_id,
            rights_claim_id=req.rights_claim_id,
            reuse_scope=camp.state.spec.reuse_scope,
        )
        promotion_decision: Literal["promote", "queue_higher_fidelity", "reject", "hold"] = (
            "promote" if verdict.overall == "pass" else "reject"
        )
        output = L7CampaignOutput(
            candidate_id=req.candidate_id,
            acquisition="qLogExpectedImprovement",
            promotion_decision=promotion_decision,
            audit_provenance_ref=f"audit:l7:promotion:{campaign_id}:{req.candidate_id}",
            gate_verdict=verdict.overall,
        )
        env = make_l7_envelope(
            output=output,
            params=params,
            adapter_name="L7PromotionGate",
            adapter_version="0.1.0",
            backend="stub",
            engine="acceptance-gate",
            extra_falsifier_items=verdict.falsifier_items,
        )
        # If candidate is registered, advance it; otherwise just emit envelope.
        if req.candidate_id in camp.state.candidates:
            cur = camp.candidate(req.candidate_id)
            if cur.status == "evidence_complete":
                if promotion_decision == "promote":
                    camp.transition_candidate(
                        req.candidate_id,
                        "promoted",
                        rationale=verdict.rationale,
                    )
                else:
                    camp.transition_candidate(
                        req.candidate_id,
                        "rejected",
                        rationale=verdict.rationale,
                        rejection_reason=";".join(verdict.failure_reasons) or "gate_failed",
                    )
        return {
            "envelope": env.model_dump(mode="json"),
            "verdict": verdict.model_dump(mode="json"),
        }

    # ----- resume -----

    @app.post("/v1/l7/campaigns/resume")
    async def resume(req: ResumeRequest) -> dict[str, Any]:
        campaign_id = req.campaign_id
        log, kg = _get_audit_and_kg(req.audit_dir, req.kg_path)
        try:
            camp = Campaign.resume_from_audit(campaign_id, log, kg)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        _ACTIVE_CAMPAIGNS[campaign_id] = camp
        return {
            "campaign_id": campaign_id,
            "status": camp.status,
            "candidates": {
                cid: rec.model_dump(mode="json") for cid, rec in camp.state.candidates.items()
            },
            "research_boundary": RESEARCH_BOUNDARY,
        }

    # ----- state -----

    @app.get("/v1/l7/campaigns/state")
    async def state(campaign_id: str) -> dict[str, Any]:
        camp = _ACTIVE_CAMPAIGNS.get(campaign_id)
        if camp is None:
            raise HTTPException(status_code=404, detail=f"campaign {campaign_id!r} not active")
        return {
            "campaign_id": campaign_id,
            "status": camp.status,
            "spec": camp.state.spec.model_dump(mode="json"),
            "candidates": {
                cid: rec.model_dump(mode="json") for cid, rec in camp.state.candidates.items()
            },
            "rejected": list(camp.state.rejected_candidate_ids),
            "promoted": list(camp.state.promoted_candidate_ids),
        }

    # ----- alabos compile -----

    @app.post("/v1/l7/alabos/compile-protocol")
    async def compile_protocol(req: CompileProtocolRequest) -> dict[str, Any]:
        compiler = AlabOSProtocolCompilerStub(alabos_mode=req.alabos_mode)
        try:
            protocol = compiler.compile(req.candidate_id, recipe=req.recipe)
        except AlabosExecutableInRecipeOnlyError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        # Build a wrap envelope.
        params = L7CampaignParams(
            campaign_id="campaign:l7:adhoc",
            candidate_id=req.candidate_id,
        )
        env = compiler.execute(params)
        return {
            "protocol": protocol.model_dump(mode="json"),
            "envelope": env.model_dump(mode="json"),
        }

    return app


# Module-level app for uvicorn discovery.
l7_app = create_l7_app()
