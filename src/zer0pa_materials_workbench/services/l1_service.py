"""L1 DFT REST stub service (PRD §L1 REST interface).

Routes
------
POST  /v1/l1/dft/jobs          — submit a DFT job
GET   /v1/jobs/{job_id}        — poll job status
GET   /v1/jobs/{job_id}/artifacts — list artifacts for a job
POST  /v1/jobs/{job_id}/cancel — cancel a job
GET   /v1/l1/healthz           — health check

This is a stub that runs the PyScfMolecularSolver (or whichever backend is
configured via ``MATERIALS_L1_BACKEND``) in-process and returns the result
immediately. There is no real async queue — all jobs complete synchronously
in the stub.

The REST layer exists so the runpod_rest backend path can be tested via
FastAPI TestClient without touching a real Runpod instance.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from zer0pa_materials_workbench.adapters.l1 import get_l1_adapter
from zer0pa_materials_workbench.adapters.l1.base import L1JobParams
from zer0pa_materials_workbench.boundary import RESEARCH_BOUNDARY

__all__ = ["JobArtifact", "JobRequest", "JobStatus", "app"]

app = FastAPI(
    title="Zer0pa Materials — L1 DFT Stub Service",
    description=(
        "Stub REST layer for L1 DFT jobs. "
        "All jobs run synchronously in-process. "
        "Real async execution via Runpod is parked behind MATERIALS_L1_BACKEND=runpod_rest."
    ),
    version="0.1.0",
)

# ---------------------------------------------------------------------------
# In-memory job store (stub only — not for production)
# ---------------------------------------------------------------------------

_JOB_STORE: dict[str, dict[str, Any]] = {}


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class JobRequest(BaseModel):
    """POST /v1/l1/dft/jobs request body."""

    structure_cif: str = Field(..., description="CIF text of the input structure.")
    structure_hash: str = Field(..., description="sha256:<hex> of the canonicalised structure.")
    functional: str = Field(default="PBE")
    kpoint_mesh: list[int] = Field(default_factory=lambda: [1, 1, 1])
    basis_set: str | None = None
    cutoff_Ry: float | None = None
    max_scf_cycles: int = Field(default=200, ge=1)
    convergence_threshold: float = Field(default=1e-6, gt=0.0)
    campaign_id: str = Field(default="campaign:l1-rest-default")
    candidate_id: str = Field(default="candidate:l1-rest-default")


class JobStatus(BaseModel):
    """Response for GET /v1/jobs/{job_id}."""

    job_id: str
    status: str  # "queued" | "running" | "completed" | "failed" | "cancelled"
    message: str | None = None
    envelope: dict[str, Any] | None = None


class JobArtifact(BaseModel):
    """One artifact entry from GET /v1/jobs/{job_id}/artifacts."""

    artifact_id: str
    kind: str
    uri: str
    size_bytes: int | None = None


class HealthResponse(BaseModel):
    status: str
    research_boundary: str
    backend: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/v1/l1/healthz", response_model=HealthResponse)
def healthz() -> HealthResponse:
    """Return service health and boundary declaration."""
    import os
    backend = os.environ.get("MATERIALS_L1_BACKEND", "pyscf")
    return HealthResponse(
        status="ok",
        research_boundary=RESEARCH_BOUNDARY,
        backend=backend,
    )


@app.post("/v1/l1/dft/jobs", response_model=JobStatus, status_code=201)
def submit_job(req: JobRequest) -> JobStatus:
    """Submit a DFT job. Runs synchronously in stub mode."""
    job_id = f"job:l1:{uuid.uuid4().hex[:12]}"
    try:
        adapter = get_l1_adapter()
        params = L1JobParams(
            structure_cif=req.structure_cif,
            structure_hash=req.structure_hash,
            functional=req.functional,
            kpoint_mesh=req.kpoint_mesh,
            basis_set=req.basis_set,
            cutoff_Ry=req.cutoff_Ry,
            max_scf_cycles=req.max_scf_cycles,
            convergence_threshold=req.convergence_threshold,
            campaign_id=req.campaign_id,
            candidate_id=req.candidate_id,
            run_id=f"run:{job_id}",
        )
        envelope = adapter.submit_job(req.structure_cif, params)
        env_dict = envelope.model_dump(mode="json")
        _JOB_STORE[job_id] = {
            "status": "completed",
            "envelope": env_dict,
            "artifacts": [
                {
                    "artifact_id": f"artifact:{job_id}:envelope",
                    "kind": "envelope",
                    "uri": f"memory://{job_id}/envelope.json",
                    "size_bytes": len(str(env_dict)),
                }
            ],
        }
        return JobStatus(
            job_id=job_id,
            status="completed",
            envelope=env_dict,
        )
    except Exception as exc:
        _JOB_STORE[job_id] = {"status": "failed", "message": str(exc)}
        return JobStatus(job_id=job_id, status="failed", message=str(exc))


@app.get("/v1/jobs/{job_id}", response_model=JobStatus)
def get_job(job_id: str) -> JobStatus:
    """Poll job status."""
    entry = _JOB_STORE.get(job_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id!r} not found.")
    return JobStatus(
        job_id=job_id,
        status=entry["status"],
        message=entry.get("message"),
        envelope=entry.get("envelope"),
    )


@app.get("/v1/jobs/{job_id}/artifacts", response_model=list[JobArtifact])
def get_artifacts(job_id: str) -> list[JobArtifact]:
    """List artifacts for a job."""
    entry = _JOB_STORE.get(job_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id!r} not found.")
    return [JobArtifact(**a) for a in entry.get("artifacts", [])]


@app.post("/v1/jobs/{job_id}/cancel", response_model=JobStatus)
def cancel_job(job_id: str) -> JobStatus:
    """Cancel a job. In stub mode, marks completed jobs as cancelled."""
    entry = _JOB_STORE.get(job_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id!r} not found.")
    if entry["status"] == "completed":
        # Cannot cancel an already-completed stub job; return 409.
        raise HTTPException(status_code=409, detail="Job already completed; cannot cancel.")
    entry["status"] = "cancelled"
    return JobStatus(job_id=job_id, status="cancelled")
