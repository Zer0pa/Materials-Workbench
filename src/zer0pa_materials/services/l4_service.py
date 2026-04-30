"""L4 phase-field / kMC / neural-operator REST service — FastAPI application.

Endpoints (PRD §REST Stub Surface; PRD §L4):
    POST /v1/l4/runs              PhaseFieldRunSpec  -> EnvelopeL4 (ensemble)
    POST /v1/l4/kmc/runs          KmcRunSpec         -> EnvelopeL4 (SPPARKS)
    POST /v1/l4/neural-op/predict NeuralOpPredictRequest -> EnvelopeL4 (advisory)
    GET  /v1/l4/healthz           liveness check

The service starts under uvicorn:
    uvicorn zer0pa_materials.services.l4_service:app --port 8044
"""

from __future__ import annotations

import datetime as _dt
from typing import Any

try:
    from fastapi import FastAPI, HTTPException
    from pydantic import BaseModel, Field
    _FASTAPI_AVAILABLE = True
except ImportError:  # pragma: no cover
    _FASTAPI_AVAILABLE = False
    FastAPI = None  # type: ignore[misc, assignment]
    HTTPException = Exception  # type: ignore[misc, assignment]
    BaseModel = object  # type: ignore[misc, assignment]
    Field = lambda *a, **kw: None  # type: ignore[misc]

from zer0pa_materials.adapters.l4.base import L4PredictRequest
from zer0pa_materials.adapters.l4.contracts import (
    KmcRunSpec,
    NeuralOpPredictRequest,
    PhaseFieldRunSpec,
)
from zer0pa_materials.adapters.l4.ensemble import L4SolverEnsemble
from zer0pa_materials.adapters.l4.neural_operator import NeuralOperatorPhaseFieldAdapter
from zer0pa_materials.adapters.l4.spparks import SpparksKmcAdapter
from zer0pa_materials.boundary import RESEARCH_BOUNDARY


# ---------------------------------------------------------------------------
# Request payloads
# ---------------------------------------------------------------------------

if _FASTAPI_AVAILABLE:
    from pydantic import BaseModel as _PydanticBase

    class L4RunRequestPayload(_PydanticBase):
        """Request body for POST /v1/l4/runs (phase-field ensemble run)."""
        run_id: str = Field(..., description="URN run identifier.")
        candidate_id: str = Field(..., description="URN candidate identifier.")
        campaign_id: str = Field(..., description="URN campaign identifier.")
        rights_claim_id: str = Field(..., description="URN rights claim.")
        spec: PhaseFieldRunSpec = Field(..., description="Phase-field run spec.")

    class L4KmcRequestPayload(_PydanticBase):
        """Request body for POST /v1/l4/kmc/runs (kMC run)."""
        run_id: str = Field(..., description="URN run identifier.")
        candidate_id: str = Field(..., description="URN candidate identifier.")
        campaign_id: str = Field(..., description="URN campaign identifier.")
        rights_claim_id: str = Field(..., description="URN rights claim.")
        spec: KmcRunSpec = Field(..., description="kMC run spec.")

    class L4NeuralOpPredictPayload(_PydanticBase):
        """Request body for POST /v1/l4/neural-op/predict.

        Wraps NeuralOpPredictRequest with the same fields. We re-declare
        here so FastAPI can build the OpenAPI schema cleanly.
        """
        run_id: str = Field(..., description="URN run identifier.")
        candidate_id: str = Field(..., description="URN candidate identifier.")
        campaign_id: str = Field(..., description="URN campaign identifier.")
        rights_claim_id: str = Field(..., description="URN rights claim.")
        spec: PhaseFieldRunSpec = Field(..., description="Phase-field run spec.")
        architecture: str = Field(
            default="u_afno",
            description="Neural operator architecture: 'u_afno' or 'deeponet'.",
        )


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------


def _make_app() -> "FastAPI":  # type: ignore[return]
    if not _FASTAPI_AVAILABLE:
        raise ImportError(
            "fastapi is required for the L4 service. "
            "Install it: pip install fastapi uvicorn"
        )

    app = FastAPI(
        title="Zer0pa L4 Phase-Field / kMC / Neural-Operator Service",
        description=(
            "L4 solver-ensemble REST surface: PRISMS-PF + MOOSE phase field, "
            "SPPARKS kMC, and U-AFNO neural-operator surrogate (advisory)."
        ),
        version="0.1.0",
    )
    _ensemble = L4SolverEnsemble()
    _spparks = SpparksKmcAdapter()
    _neural_op = NeuralOperatorPhaseFieldAdapter(architecture="u_afno")

    @app.get("/v1/l4/healthz")
    def healthz() -> dict[str, Any]:
        return {
            "status": "ok",
            "service": "l4_phase_field",
            "version": "0.1.0",
            "backend": "stub",
            "research_boundary": RESEARCH_BOUNDARY,
            "timestamp": _dt.datetime.now(tz=_dt.timezone.utc).isoformat(timespec="seconds"),
            "adapters": {
                "phase_field_ensemble": _ensemble.NAME,
                "kmc": _spparks.NAME,
                "neural_op": _neural_op.NAME,
            },
        }

    @app.post("/v1/l4/runs")
    def runs(body: L4RunRequestPayload) -> dict[str, Any]:  # type: ignore[name-defined]
        """Run the phase-field ensemble (PRISMS-PF + MOOSE) on a spec."""
        req = L4PredictRequest(
            run_id=body.run_id,
            candidate_id=body.candidate_id,
            campaign_id=body.campaign_id,
            rights_claim_id=body.rights_claim_id,
        )
        try:
            envelope = _ensemble.run(body.spec, req)
        except (ValueError, TypeError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"envelope": envelope, "research_boundary": RESEARCH_BOUNDARY}

    @app.post("/v1/l4/kmc/runs")
    def kmc_runs(body: L4KmcRequestPayload) -> dict[str, Any]:  # type: ignore[name-defined]
        """Run SPPARKS kMC on a spec."""
        req = L4PredictRequest(
            run_id=body.run_id,
            candidate_id=body.candidate_id,
            campaign_id=body.campaign_id,
            rights_claim_id=body.rights_claim_id,
        )
        try:
            envelope = _spparks.run(body.spec, req)
        except (ValueError, TypeError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"envelope": envelope, "research_boundary": RESEARCH_BOUNDARY}

    @app.post("/v1/l4/neural-op/predict")
    def neural_op_predict(
        body: L4NeuralOpPredictPayload,  # type: ignore[name-defined]
    ) -> dict[str, Any]:
        """Predict a microstructure trajectory with the neural operator."""
        if body.architecture not in ("u_afno", "deeponet"):
            raise HTTPException(
                status_code=400,
                detail=f"architecture must be 'u_afno' or 'deeponet'; got {body.architecture!r}",
            )
        req = L4PredictRequest(
            run_id=body.run_id,
            candidate_id=body.candidate_id,
            campaign_id=body.campaign_id,
            rights_claim_id=body.rights_claim_id,
        )
        adapter = NeuralOperatorPhaseFieldAdapter(architecture=body.architecture)  # type: ignore[arg-type]
        try:
            envelope = adapter.run(body.spec, req)
        except (ValueError, TypeError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"envelope": envelope, "research_boundary": RESEARCH_BOUNDARY}

    return app


if _FASTAPI_AVAILABLE:
    app = _make_app()
else:  # pragma: no cover
    app = None  # type: ignore[assignment]
