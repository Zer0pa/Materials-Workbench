"""L3 CALPHAD REST service — FastAPI application (PRD §REST Stub Surface).

Endpoints:
    POST /v1/l3/equilibrium                  Run pycalphad equilibrium
    POST /v1/l3/fit-tdb                      Run ESPEI Bayesian TDB fit
    POST /v1/l3/sovereign-pipeline           DFT/MLIP -> prior -> ESPEI -> pycalphad
    POST /v1/l3/quarantine-thermocalc-read   Commercial TDB read under license
    GET  /v1/l3/healthz                      Liveness check

The service is started with uvicorn:
    uvicorn zer0pa_materials_workbench.services.l3_service:app --port 8043

Sovereign pipeline is the L7-orchestrator-facing endpoint: novel quaternary
systems (PRD §Scope) flow through ``/sovereign-pipeline``. The endpoint
returns a list of envelopes (DFT/MLIP, prior, ESPEI posterior, equilibrium
at battery-relevant temperatures, summary).
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
    HTTPException = Exception  # type: ignore[assignment]
    BaseModel = object  # type: ignore[misc, assignment]
    Field = lambda *a, **kw: None  # type: ignore[misc]

from zer0pa_materials_workbench.adapters.l3 import (
    CommercialTdbQuarantineError,
    EspeiBayesianFitAdapter,
    L3CalphadRequest,
    PyCalphadEquilibriumAdapter,
    SovereignCalphadPipeline,
    ThermoCalcTdbReadOnlyAdapter,
)
from zer0pa_materials_workbench.boundary import RESEARCH_BOUNDARY

# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

if _FASTAPI_AVAILABLE:
    from pydantic import BaseModel as _PydanticBase

    class L3BaseRequestPayload(_PydanticBase):
        """Common L3 request envelope."""

        run_id: str = Field(..., description="URN run identifier, e.g. 'run:l3/20260430/cu-mg'.")
        candidate_id: str = Field(..., description="URN candidate identifier.")
        campaign_id: str = Field(..., description="URN campaign identifier.")
        rights_claim_id: str = Field(..., description="URN rights claim identifier.")

    class L3EquilibriumRequestPayload(L3BaseRequestPayload):
        """Body for POST /v1/l3/equilibrium."""

        tdb_path: str | None = Field(
            None,
            description="Path to a TDB file (sovereign open). Optional for stub backend.",
        )
        components: list[str] | None = Field(
            None,
            description="Element symbols (e.g. ['CU', 'MG']). Optional.",
        )
        temperature_K: float = Field(
            1000.0, ge=0.0, description="Equilibrium temperature in Kelvin."
        )
        composition: dict[str, float] | None = Field(
            None,
            description="Element mole fraction composition dict (e.g. {'CU': 0.7, 'MG': 0.3}).",
        )

    class L3FitTdbRequestPayload(L3BaseRequestPayload):
        """Body for POST /v1/l3/fit-tdb."""

        tdb_path: str | None = Field(
            None, description="Optional path to a starting TDB file."
        )
        components: list[str] | None = Field(
            None, description="Element symbols."
        )
        n_walkers: int = Field(16, ge=4, le=128, description="Number of MCMC walkers.")
        n_steps: int = Field(200, ge=50, le=10000, description="MCMC steps per walker.")
        n_burn_in: int = Field(50, ge=0, le=5000, description="Burn-in steps to drop.")

    class L3SovereignPipelineRequestPayload(L3BaseRequestPayload):
        """Body for POST /v1/l3/sovereign-pipeline."""

        tdb_path: str | None = Field(
            None, description="Optional starting TDB path (for the equilibrium step)."
        )
        components: list[str] | None = Field(
            None, description="Element symbols (4-element quaternary supported)."
        )
        temperature_grid_K: list[float] | None = Field(
            None,
            description="List of temperatures (K) for the equilibrium step. "
            "Default: [300.0, 700.0] (battery-relevant grid).",
        )

    class L3QuarantineThermoCalcReadRequestPayload(L3BaseRequestPayload):
        """Body for POST /v1/l3/quarantine-thermocalc-read.

        Per PRD §L3 quarantine policy: this endpoint REQUIRES customer
        license proof. The body's ``customer_id`` must be a URN starting
        with ``customer:``.
        """

        tdb_path: str = Field(..., description="Absolute path to the customer-supplied TDB.")
        customer_id: str = Field(
            ...,
            description="URN starting with 'customer:' identifying the licensed customer.",
        )
        license_proof_uri: str = Field(
            ...,
            description="URI of the license proof (must be hosted OUTSIDE this repo).",
        )


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

def _make_app() -> FastAPI:  # type: ignore[return]
    if not _FASTAPI_AVAILABLE:
        raise ImportError(
            "fastapi is required for the L3 service. "
            "Install it: pip install fastapi uvicorn"
        )

    app = FastAPI(
        title="Zer0pa L3 CALPHAD Service",
        description=(
            "Sovereign pycalphad/ESPEI CALPHAD service. PRD §L3: open path "
            "(pycalphad/ESPEI/PhaseForgePlus) by default; commercial Thermo-"
            "Calc TDBs allowed only as quarantined per-customer reads."
        ),
        version="0.1.0",
    )

    @app.get("/v1/l3/healthz")
    def healthz() -> dict[str, Any]:
        from zer0pa_materials_workbench.adapters.l3.espei_fit import ESPEI_AVAILABLE
        from zer0pa_materials_workbench.adapters.l3.pycalphad_equilibrium import PYCALPHAD_AVAILABLE

        return {
            "status": "ok",
            "service": "l3_calphad",
            "version": "0.1.0",
            "backend": "stub" if not (PYCALPHAD_AVAILABLE and ESPEI_AVAILABLE) else "local_cpu",
            "pycalphad_available": PYCALPHAD_AVAILABLE,
            "espei_available": ESPEI_AVAILABLE,
            "research_boundary": RESEARCH_BOUNDARY,
            "timestamp": _dt.datetime.now(tz=_dt.timezone.utc).isoformat(timespec="seconds"),
        }

    @app.post("/v1/l3/equilibrium")
    def equilibrium(body: L3EquilibriumRequestPayload) -> dict[str, Any]:  # type: ignore[name-defined]
        adapter = PyCalphadEquilibriumAdapter()
        req = L3CalphadRequest(
            run_id=body.run_id,
            candidate_id=body.candidate_id,
            campaign_id=body.campaign_id,
            rights_claim_id=body.rights_claim_id,
            tdb_path=body.tdb_path,
            components=body.components,
            extra={
                "temperature_K": body.temperature_K,
                "composition": body.composition or {},
            },
        )
        envelope = adapter.run(req)
        return {"envelope": envelope, "research_boundary": RESEARCH_BOUNDARY}

    @app.post("/v1/l3/fit-tdb")
    def fit_tdb(body: L3FitTdbRequestPayload) -> dict[str, Any]:  # type: ignore[name-defined]
        adapter = EspeiBayesianFitAdapter(
            n_walkers=body.n_walkers,
            n_steps=body.n_steps,
            n_burn_in=body.n_burn_in,
        )
        req = L3CalphadRequest(
            run_id=body.run_id,
            candidate_id=body.candidate_id,
            campaign_id=body.campaign_id,
            rights_claim_id=body.rights_claim_id,
            tdb_path=body.tdb_path,
            components=body.components,
        )
        envelope = adapter.run(req)
        return {"envelope": envelope, "research_boundary": RESEARCH_BOUNDARY}

    @app.post("/v1/l3/sovereign-pipeline")
    def sovereign_pipeline(
        body: L3SovereignPipelineRequestPayload,  # type: ignore[name-defined]
    ) -> dict[str, Any]:
        grid: tuple[float, ...] = (
            tuple(body.temperature_grid_K) if body.temperature_grid_K else (300.0, 700.0)
        )
        pipeline = SovereignCalphadPipeline(temperature_grid_K=grid)
        req = L3CalphadRequest(
            run_id=body.run_id,
            candidate_id=body.candidate_id,
            campaign_id=body.campaign_id,
            rights_claim_id=body.rights_claim_id,
            tdb_path=body.tdb_path,
            components=body.components,
        )
        envelopes = pipeline.run_with_chain(req)
        return {
            "envelopes": envelopes,
            "summary_envelope": envelopes[-1],
            "n_steps": len(envelopes),
            "research_boundary": RESEARCH_BOUNDARY,
        }

    @app.post("/v1/l3/quarantine-thermocalc-read")
    def quarantine_thermocalc_read(
        body: L3QuarantineThermoCalcReadRequestPayload,  # type: ignore[name-defined]
    ) -> dict[str, Any]:
        adapter = ThermoCalcTdbReadOnlyAdapter()
        try:
            adapter.enable_with_customer_license(
                customer_id=body.customer_id,
                license_proof_uri=body.license_proof_uri,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        req = L3CalphadRequest(
            run_id=body.run_id,
            candidate_id=body.candidate_id,
            campaign_id=body.campaign_id,
            rights_claim_id=body.rights_claim_id,
            tdb_path=body.tdb_path,
        )
        try:
            envelope = adapter.run(req)
        except CommercialTdbQuarantineError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        return {"envelope": envelope, "research_boundary": RESEARCH_BOUNDARY}

    return app


# Instantiate at import time so ``uvicorn l3_service:app`` works.
if _FASTAPI_AVAILABLE:
    app = _make_app()
else:
    app = None  # type: ignore[assignment]
