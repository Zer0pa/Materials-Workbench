"""L2 MLIP REST service — FastAPI application.

Endpoints:
    POST /v1/l2/predict       Run DPA-3 + MACE ensemble on a structure
    POST /v1/l2/relax         Relax structure with DPA-3 + MACE
    POST /v1/l2/finetune      Schema-real, execution-stubbed fine-tune request
    GET  /v1/l2/healthz       Liveness check

Fine-tune economics (PRD Brief #2 Gap F):
    100–500 DFT configurations + 1–4 GPU-hours on A100 per system.
    Fine-tune endpoint is schema-real (request/response validated) but the
    execution is stubbed — no real weights are loaded or trained here.

The service is started with uvicorn:
    uvicorn zer0pa_materials_workbench.services.l2_service:app --port 8042
"""

from __future__ import annotations

import datetime as _dt
import uuid
from typing import Any

try:
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    from pydantic import BaseModel, Field
    _FASTAPI_AVAILABLE = True
except ImportError:  # pragma: no cover
    _FASTAPI_AVAILABLE = False
    FastAPI = None  # type: ignore[misc, assignment]
    BaseModel = object  # type: ignore[misc, assignment]
    Field = lambda *a, **kw: None  # type: ignore[misc]

from zer0pa_materials_workbench.adapters.l2.base import L2PredictRequest
from zer0pa_materials_workbench.adapters.l2.ensemble import L2EnsembleRunner
from zer0pa_materials_workbench.boundary import RESEARCH_BOUNDARY

# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

if _FASTAPI_AVAILABLE:
    from pydantic import BaseModel as _PydanticBase

    class StructurePayload(_PydanticBase):
        """Minimal crystal structure payload (OPTIMADE-style keys)."""
        lattice_vectors: list[list[float]] = Field(..., description="3x3 lattice vectors in Angstrom.")
        species: list[str] = Field(..., description="Element symbols, one per atom.")
        fractional_coords: list[list[float]] = Field(
            ..., description="Fractional coordinates, one per atom."
        )

    class L2PredictRequestPayload(_PydanticBase):
        """Request body for POST /v1/l2/predict and /v1/l2/relax."""
        run_id: str = Field(..., description="URN run identifier, e.g. 'run:l2/20260430/Si'.")
        candidate_id: str = Field(
            ..., description="URN candidate identifier, e.g. 'candidate:Si:abc123'."
        )
        campaign_id: str = Field(
            ..., description="URN campaign identifier, e.g. 'campaign:sse/001'."
        )
        rights_claim_id: str = Field(
            ..., description="URN rights claim, e.g. 'rights:sse/001'."
        )
        structure: StructurePayload

    class L2FinetuneRequestPayload(_PydanticBase):
        """Request body for POST /v1/l2/finetune.

        Schema is real (validated); execution is stubbed.
        Economics: 100–500 DFT configs + 1–4 GPU-h on A100 per system.
        """
        run_id: str = Field(..., description="URN run identifier for fine-tune job.")
        campaign_id: str = Field(..., description="URN campaign identifier.")
        rights_claim_id: str = Field(..., description="URN rights claim.")
        base_model: str = Field(
            default="DPA-3.1-3M",
            description="Base model to fine-tune (DPA-3.1-3M or MACE-MPA-0).",
        )
        dft_configs: list[dict[str, Any]] = Field(
            ...,
            min_length=1,
            description="List of DFT configuration dicts (energy + forces). 100–500 expected.",
        )
        target_property: str = Field(
            default="general",
            description="Property to optimise: 'general', 'ionic_conductivity', 'elasticity', ...",
        )
        gpu_budget_hours: float = Field(
            default=2.0,
            gt=0.0,
            le=4.0,
            description="GPU-hours budget on A100 (max 4 per Brief #2 Gap F).",
        )


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

def _make_app() -> FastAPI:  # type: ignore[return]
    if not _FASTAPI_AVAILABLE:
        raise ImportError(
            "fastapi is required for the L2 service. "
            "Install it: pip install fastapi uvicorn"
        )

    app = FastAPI(
        title="Zer0pa L2 MLIP Service",
        description="DPA-3 + MACE ensemble MLIP REST service.",
        version="0.1.0",
    )
    _runner = L2EnsembleRunner()

    @app.get("/v1/l2/healthz")
    def healthz() -> dict[str, Any]:
        return {
            "status": "ok",
            "service": "l2_mlip",
            "version": "0.1.0",
            "backend": "stub",
            "research_boundary": RESEARCH_BOUNDARY,
            "timestamp": _dt.datetime.now(tz=_dt.timezone.utc).isoformat(timespec="seconds"),
        }

    @app.post("/v1/l2/predict")
    def predict(body: L2PredictRequestPayload) -> dict[str, Any]:  # type: ignore[name-defined]
        structure = {
            "lattice_vectors": body.structure.lattice_vectors,
            "species": body.structure.species,
            "fractional_coords": body.structure.fractional_coords,
        }
        req = L2PredictRequest(
            run_id=body.run_id,
            candidate_id=body.candidate_id,
            campaign_id=body.campaign_id,
            rights_claim_id=body.rights_claim_id,
        )
        envelope = _runner.run(structure, req)
        return {"envelope": envelope, "research_boundary": RESEARCH_BOUNDARY}

    @app.post("/v1/l2/relax")
    def relax(body: L2PredictRequestPayload) -> dict[str, Any]:  # type: ignore[name-defined]
        """Relax structure with DPA-3 + MACE ensemble.

        In stub mode: returns predict output with relaxation metadata added.
        Real relax: runs ASE BFGS optimiser with each MLIP; compares final
        geometries for volume drift and space-group agreement.
        """
        structure = {
            "lattice_vectors": body.structure.lattice_vectors,
            "species": body.structure.species,
            "fractional_coords": body.structure.fractional_coords,
        }
        req = L2PredictRequest(
            run_id=body.run_id,
            candidate_id=body.candidate_id,
            campaign_id=body.campaign_id,
            rights_claim_id=body.rights_claim_id,
        )
        envelope = _runner.run(structure, req)
        # Add stub relaxation metadata.
        envelope.setdefault("_ensemble_meta", {}).update(
            {
                "relaxation": "stub",
                "volume_drift_pct": 0.0,
                "coord_drift_ang_per_atom": 0.0,
                "space_group_agrees": True,
                "fmax_eV_Ang": 0.05,
                "steps": 0,
            }
        )
        return {"envelope": envelope, "research_boundary": RESEARCH_BOUNDARY}

    @app.post("/v1/l2/finetune")
    def finetune(body: L2FinetuneRequestPayload) -> dict[str, Any]:  # type: ignore[name-defined]
        """Submit a fine-tune job (schema-real, execution-stubbed).

        Real execution: 100–500 DFT configs + 1–4 GPU-hours on A100.
        Returns a job ID and status for polling.
        """
        job_id = f"finetune:{body.run_id}/{uuid.uuid4().hex[:8]}"
        return {
            "job_id": job_id,
            "status": "queued",
            "base_model": body.base_model,
            "n_dft_configs": len(body.dft_configs),
            "gpu_budget_hours": body.gpu_budget_hours,
            "target_property": body.target_property,
            "estimated_gpu_hours": min(
                body.gpu_budget_hours,
                len(body.dft_configs) / 100.0 * 1.0,
            ),
            "backend": "stub",
            "research_boundary": RESEARCH_BOUNDARY,
            "note": (
                "Execution stubbed. Real backend: "
                "100–500 DFT configs + 1–4 GPU-h on A100. "
                "Set L2_BACKEND=runpod_rest to enable real fine-tuning."
            ),
            "blocked_manifests": _runner.blocked_manifests(),
        }

    return app


# Instantiate at import time so ``uvicorn l2_service:app`` works.
if _FASTAPI_AVAILABLE:
    app = _make_app()
else:
    app = None  # type: ignore[assignment]
