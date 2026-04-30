"""Quantum VQE REST stub service (PRD §Quantum REST interface).

Routes
------
POST  /v1/l1/quantum/vqe/jobs   — submit a VQE job
GET   /v1/quantum/healthz        — health check

Stub: all jobs run synchronously in-process via PennyLaneVqeSolver.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from zer0pa_materials.adapters.quantum.dispatcher import QuantumProblemDispatcher
from zer0pa_materials.boundary import RESEARCH_BOUNDARY

__all__ = ["app", "VqeJobRequest", "VqeJobStatus"]

app = FastAPI(
    title="Zer0pa Materials — Quantum VQE Stub Service",
    description=(
        "Stub REST layer for quantum VQE jobs. "
        "Classical simulator only; real hardware parked."
    ),
    version="0.1.0",
)

_JOB_STORE: dict[str, dict[str, Any]] = {}


class VqeJobRequest(BaseModel):
    system: str = Field(..., description="Molecular system: 'H2' or 'LiH'.")
    bond_ang: float | None = Field(default=None, description="Bond length in Å.")
    slot: str = Field(default="L1-VQE", description="Quantum slot: 'L1-VQE', 'L4-QAOA', 'L7-QAA'.")
    campaign_id: str = Field(default="campaign:vqe-rest-default")
    candidate_id: str = Field(default="candidate:vqe-rest-default")


class VqeJobStatus(BaseModel):
    job_id: str
    status: str
    message: str | None = None
    envelope: dict[str, Any] | None = None


class QuantumHealthResponse(BaseModel):
    status: str
    research_boundary: str
    backend: str


@app.get("/v1/quantum/healthz", response_model=QuantumHealthResponse)
def healthz() -> QuantumHealthResponse:
    return QuantumHealthResponse(
        status="ok",
        research_boundary=RESEARCH_BOUNDARY,
        backend="classical_simulator_stub",
    )


@app.post("/v1/l1/quantum/vqe/jobs", response_model=VqeJobStatus, status_code=201)
def submit_vqe_job(req: VqeJobRequest) -> VqeJobStatus:
    """Submit a VQE job. Runs synchronously in stub mode."""
    job_id = f"job:vqe:{uuid.uuid4().hex[:12]}"
    try:
        dispatcher = QuantumProblemDispatcher()
        envelope = dispatcher.dispatch(
            slot=req.slot,  # type: ignore[arg-type]
            system=req.system,
            bond_ang=req.bond_ang,
            campaign_id=req.campaign_id,
            candidate_id=req.candidate_id,
        )
        env_dict = envelope.model_dump(mode="json")
        _JOB_STORE[job_id] = {"status": "completed", "envelope": env_dict}
        return VqeJobStatus(job_id=job_id, status="completed", envelope=env_dict)
    except NotImplementedError as exc:
        _JOB_STORE[job_id] = {"status": "blocked", "message": str(exc)}
        return VqeJobStatus(job_id=job_id, status="blocked", message=str(exc))
    except Exception as exc:
        _JOB_STORE[job_id] = {"status": "failed", "message": str(exc)}
        return VqeJobStatus(job_id=job_id, status="failed", message=str(exc))
