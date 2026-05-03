"""L5 continuum REST service — FastAPI application.

Endpoints:
    POST /v1/l5/continuum-runs   Run FEniCSx + deal.II + OpenFOAM on a request
    POST /v1/l5/homogenise       Homogenise a microstructure trajectory (L4→L5)
    GET  /v1/l5/healthz          Liveness check

The service aggregates outputs from all three L5 adapters (FEniCSx, deal.II,
OpenFOAM) and the HomogenisationOperator.  The FEniCSx vs deal.II strain
energy disagreement metric is computed here and attached to the response.

Start with:
    uvicorn zer0pa_materials_workbench.services.l5_service:app --port 8045
"""

from __future__ import annotations

import datetime as _dt
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

from zer0pa_materials_workbench.adapters.l5.base import L5ContinuumRequest
from zer0pa_materials_workbench.adapters.l5.dealii import DealIIStructuralAdapter
from zer0pa_materials_workbench.adapters.l5.fenicsx import FEniCSxContinuumAdapter
from zer0pa_materials_workbench.adapters.l5.homogenisation import HomogenisationOperator
from zer0pa_materials_workbench.adapters.l5.openfoam import OpenFOAMProcessAdapter
from zer0pa_materials_workbench.boundary import RESEARCH_BOUNDARY

# ---------------------------------------------------------------------------
# Request / Response models (FastAPI Pydantic)
# ---------------------------------------------------------------------------

if _FASTAPI_AVAILABLE:
    from pydantic import BaseModel as _PydanticBase

    class ContinuumRunRequest(_PydanticBase):
        """Request body for POST /v1/l5/continuum-runs."""

        run_id: str = Field(
            ...,
            description="URN run identifier, e.g. 'run:l5/20260430/Si'.",
        )
        candidate_id: str = Field(
            ...,
            description="URN candidate identifier, e.g. 'candidate:Si:abc123'.",
        )
        campaign_id: str = Field(
            ...,
            description="URN campaign identifier, e.g. 'campaign:sse/001'.",
        )
        rights_claim_id: str = Field(
            ...,
            description="URN rights claim, e.g. 'rights:sse/001'.",
        )
        n_heat_elements: int = Field(
            default=10,
            ge=2,
            description="Number of 1D elements for heat slab (default 10).",
        )
        n_patch_elements: int = Field(
            default=4,
            ge=2,
            description="Number of elements per side for elasticity patch (default 4).",
        )
        E_GPa: float = Field(
            default=200.0,
            gt=0.0,
            description="Young's modulus in GPa (default 200.0).",
        )
        nu: float = Field(
            default=0.3,
            gt=0.0,
            lt=0.5,
            description="Poisson's ratio (default 0.3).",
        )
        kappa_W_per_mK: float = Field(
            default=10.0,
            gt=0.0,
            description="Isotropic thermal conductivity W/(m·K) (default 10.0).",
        )

    class HomogeniseRequest(_PydanticBase):
        """Request body for POST /v1/l5/homogenise.

        ``trajectory`` is a list of snapshot entries from an L4 microstructure:
        each entry has ``phase``, ``volume_fraction``, and ``time_step``.
        """

        run_id: str = Field(..., description="URN run identifier.")
        candidate_id: str = Field(..., description="URN candidate identifier.")
        campaign_id: str = Field(..., description="URN campaign identifier.")
        rights_claim_id: str = Field(..., description="URN rights claim.")
        trajectory: list[dict[str, Any]] = Field(
            ...,
            min_length=1,
            description=(
                "Microstructure trajectory from L4. "
                "Each entry: {phase: str, volume_fraction: float, time_step: int}."
            ),
        )
        material_library: dict[str, dict[str, float]] | None = Field(
            default=None,
            description=(
                "Optional per-phase material data override. "
                "Keys: phase label. Values: {E_GPa, nu, kappa_W_per_mK}."
            ),
        )


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

def _make_app() -> FastAPI:  # type: ignore[return]
    if not _FASTAPI_AVAILABLE:
        raise ImportError(
            "fastapi is required for the L5 service. "
            "Install: pip install fastapi uvicorn"
        )

    app = FastAPI(
        title="Zer0pa L5 Continuum Service",
        description=(
            "FEniCSx / deal.II / OpenFOAM continuum and process adapter REST service. "
            "All endpoints are stub-backed until real solvers are installed."
        ),
        version="0.1.0",
    )

    # Shared adapter instances (thread-safe stubs).
    _fenicsx = FEniCSxContinuumAdapter()
    _dealii = DealIIStructuralAdapter()
    _openfoam = OpenFOAMProcessAdapter()
    _homogeniser = HomogenisationOperator()

    @app.get("/v1/l5/healthz")
    def healthz() -> dict[str, Any]:
        return {
            "status": "ok",
            "service": "l5_continuum",
            "version": "0.1.0",
            "backend": "stub",
            "research_boundary": RESEARCH_BOUNDARY,
            "timestamp": _dt.datetime.now(tz=_dt.timezone.utc).isoformat(timespec="seconds"),
        }

    @app.post("/v1/l5/continuum-runs")
    def continuum_runs(body: ContinuumRunRequest) -> dict[str, Any]:  # type: ignore[name-defined]
        """Run FEniCSx + deal.II + OpenFOAM; return combined L5 envelope."""
        req = L5ContinuumRequest(
            run_id=body.run_id,
            candidate_id=body.candidate_id,
            campaign_id=body.campaign_id,
            rights_claim_id=body.rights_claim_id,
        )

        # Override adapter parameters from request.
        fenicsx_adapter = FEniCSxContinuumAdapter(
            n_heat_elements=body.n_heat_elements,
            n_patch_elements=body.n_patch_elements,
            E_GPa=body.E_GPa,
            nu=body.nu,
            kappa_W_per_mK=body.kappa_W_per_mK,
        )
        dealii_adapter = DealIIStructuralAdapter(E_GPa=body.E_GPa, nu=body.nu)
        openfoam_adapter = OpenFOAMProcessAdapter()

        env_fenicsx = fenicsx_adapter.run(req)
        env_dealii = dealii_adapter.run(req)
        env_openfoam = openfoam_adapter.run(req)

        # Attach cross-adapter disagreement to the FEniCSx envelope.
        dealii_disagree = env_dealii.get("output", {}).get(
            "fenicsx_vs_dealii_strain_energy_disagreement_pct"
        )
        env_fenicsx["output"]["fenicsx_vs_dealii_strain_energy_disagreement_pct"] = dealii_disagree

        # Attach OpenFOAM CFD metrics to the FEniCSx envelope.
        openfoam_out = env_openfoam.get("output", {})
        env_fenicsx["output"]["openfoam_poiseuille_error_pct"] = openfoam_out.get(
            "openfoam_poiseuille_error_pct"
        )
        env_fenicsx["output"]["cfd_mass_balance_error"] = openfoam_out.get("cfd_mass_balance_error")
        env_fenicsx["output"]["cfd_heat_balance_error"] = openfoam_out.get("cfd_heat_balance_error")

        blocked = (
            fenicsx_adapter.blocked_manifests()
            + dealii_adapter.blocked_manifests()
            + openfoam_adapter.blocked_manifests()
        )

        return {
            "envelope": env_fenicsx,
            "dealii_envelope": env_dealii,
            "openfoam_envelope": env_openfoam,
            "blocked_manifests": blocked,
            "research_boundary": RESEARCH_BOUNDARY,
        }

    @app.post("/v1/l5/homogenise")
    def homogenise(body: HomogeniseRequest) -> dict[str, Any]:  # type: ignore[name-defined]
        """Homogenise a microstructure trajectory from L4; return L5 effective properties."""
        operator = HomogenisationOperator(
            material_library=body.material_library or None,
        )
        try:
            result = operator.homogenise(body.trajectory)
        except ValueError as exc:
            return JSONResponse(
                status_code=422,
                content={"error": str(exc), "research_boundary": RESEARCH_BOUNDARY},
            )

        return {
            "run_id": body.run_id,
            "candidate_id": body.candidate_id,
            "campaign_id": body.campaign_id,
            "effective_properties": result,
            "research_boundary": RESEARCH_BOUNDARY,
            "backend": "stub",
        }

    return app


# Instantiate at import time so ``uvicorn l5_service:app`` works.
if _FASTAPI_AVAILABLE:
    app = _make_app()
else:
    app = None  # type: ignore[assignment]
