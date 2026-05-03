"""L1.5 phonon and thermoelectric transport service.

Endpoints
---------

* ``POST /v1/l15/force-batches``        — Phonopy displacement-force batch request
* ``POST /v1/l15/bands/uniform``        — Uniform band-structure request
* ``POST /v1/l15/phonopy-harmonic``     — Harmonic phonon spectrum
* ``POST /v1/l15/phono3py-bte``         — Lattice thermal conductivity via BTE
* ``POST /v1/l15/hiphive-fit``          — Force constant fit from MLIP-MD data
* ``POST /v1/l15/boltztrap2-transport`` — Electronic transport (rigid-band)
* ``POST /v1/l15/amset-transport``      — Electronic transport (scattering)
* ``POST /v1/l15/zt-assemble``          — Full ZT chain assembler
* ``GET  /v1/l15/healthz``              — Liveness probe

PRD §L1.5: ``POST /v1/l15/zt-assemble`` orchestrates the full thermoelectric
chain for a candidate. Returns the assembled envelope with both BoltzTraP2
and AMSET branches.

Architectural decisions
-----------------------
1. Service is the sole L1.5 envelope producer. Every adapter sets
   ``input_refs=[L15_SERVICE_REF]`` so provenance is traceable.

2. ``zt-assemble`` is the primary user-facing endpoint. It calls Phono3py BTE
   → κ_L, BoltzTraP2 → transport (rigid-band), AMSET → transport (scattering),
   then assembles ZT from both branches and checks rank stability.

3. Phonon DOES NOT substitute for ionic conductivity. The ``phonon_does_not_
   substitute_for_ionic`` falsifier is hardcoded in every envelope; the service
   NEVER populates ``ionic_conductivity_S_per_cm``.

4. Real force/band backends are gated behind environment variables:
   ``L15_FORCE_BACKEND=runpod_rest`` and ``L15_BAND_BACKEND=runpod_rest``.

5. ZT rank stability across transport assumptions is THE sidecar gate.
   The ``zt-assemble`` endpoint returns ``fail`` if |ZT_BT2 - ZT_AMSET| / ZT_BT2
   > 15%, flagging candidates that require further DFT validation.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from zer0pa_materials_workbench.adapters.l1_5.amset import AmsetScatteringTransportAdapter
from zer0pa_materials_workbench.adapters.l1_5.base import (
    L15_SERVICE_REF,
    L15JobParams,
)
from zer0pa_materials_workbench.adapters.l1_5.boltztrap2 import BoltzTraP2RigidBandTransportAdapter
from zer0pa_materials_workbench.adapters.l1_5.hiphive_fit import HiPhiveForceConstantFitAdapter
from zer0pa_materials_workbench.adapters.l1_5.phono3py_bte import Phono3pyAnharmonicBTEAdapter
from zer0pa_materials_workbench.adapters.l1_5.phonopy_harmonic import PhonopyHarmonicAdapter
from zer0pa_materials_workbench.adapters.l1_5.zt_assembler import ThermoelectricZtAssembler
from zer0pa_materials_workbench.envelope import Envelope

__all__ = [
    "L15_SERVICE_NAME",
    "L15_SERVICE_VERSION",
    "create_l15_app",
    "l15_app",
    "run_zt_assembly",
]

L15_SERVICE_NAME = "L15PhononThermoelectricService"
L15_SERVICE_VERSION = "0.1.0"


class L15Request(BaseModel):
    """Canonical request body for L1.5 endpoints."""

    model_config = ConfigDict(extra="allow")

    structure_hash: str = Field(
        ..., min_length=8, description="sha256: hash of the canonicalised structure."
    )
    fixture_id: str | None = Field(default=None)
    material_id: str | None = Field(default=None)
    structure_cif: str | None = Field(default=None)
    temperature_K: float = Field(default=300.0, gt=0.0)
    q_mesh: list[int] = Field(default_factory=lambda: [6, 6, 6])
    carrier_type: str = Field(default="p")
    doping_per_cm3: float = Field(default=1.0e19, gt=0.0)
    campaign_id: str = Field(default="campaign:l1-5-default")
    candidate_id: str = Field(default="candidate:l1-5-default")
    run_id: str | None = Field(default=None)
    force_backend: str = Field(default="stub")
    band_backend: str = Field(default="stub")
    rights_claim_id: str = Field(default="rights:l1-5:default")
    reuse_scope: str = Field(default="tenant_only")


def _req_to_params(req: L15Request) -> L15JobParams:
    return L15JobParams(
        structure_hash=req.structure_hash,
        fixture_id=req.fixture_id,
        material_id=req.material_id,
        structure_cif=req.structure_cif,
        temperature_K=req.temperature_K,
        q_mesh=req.q_mesh,
        carrier_type=req.carrier_type,
        doping_per_cm3=req.doping_per_cm3,
        campaign_id=req.campaign_id,
        candidate_id=req.candidate_id,
        run_id=req.run_id,
        force_backend=req.force_backend,
        band_backend=req.band_backend,
        rights_claim_id=req.rights_claim_id,
        reuse_scope=req.reuse_scope,
    )


def run_zt_assembly(params: L15JobParams) -> Envelope:
    """Orchestrate the full thermoelectric ZT chain for a candidate.

    Returns an envelope with both BoltzTraP2 and AMSET ZT branches and the
    rank stability falsifier result.
    """
    assembler = ThermoelectricZtAssembler()
    return assembler.compute(params)


def create_l15_app() -> FastAPI:
    """Create and return the L1.5 FastAPI application."""
    app = FastAPI(
        title=L15_SERVICE_NAME,
        version=L15_SERVICE_VERSION,
        description=(
            "L1.5 phonon and thermoelectric transport service. "
            "PRD §L1.5: phonon does NOT substitute for ionic conductivity."
        ),
    )

    @app.get("/v1/l15/healthz")
    async def healthz() -> dict[str, str]:
        return {
            "status": "ok",
            "service": L15_SERVICE_NAME,
            "version": L15_SERVICE_VERSION,
            "service_ref": L15_SERVICE_REF,
        }

    @app.post("/v1/l15/force-batches")
    async def force_batches(req: L15Request) -> dict[str, Any]:
        """Request Phonopy displacement-force batch (stub: returns request metadata)."""
        params = _req_to_params(req)
        return {
            "status": "queued",
            "batch_id": f"batch:force:{params.structure_hash[:12]}",
            "material_id": params.material_id,
            "backend": params.force_backend,
            "message": (
                "Force batch request queued. "
                "Set L15_FORCE_BACKEND=runpod_rest for real DFT force calculations."
            ),
        }

    @app.post("/v1/l15/bands/uniform")
    async def bands_uniform(req: L15Request) -> dict[str, Any]:
        """Request uniform band-structure (stub: returns request metadata)."""
        params = _req_to_params(req)
        return {
            "status": "queued",
            "batch_id": f"batch:bands:{params.structure_hash[:12]}",
            "material_id": params.material_id,
            "backend": params.band_backend,
            "message": (
                "Band structure request queued. "
                "Set L15_BAND_BACKEND=runpod_rest for real DFT band calculations."
            ),
        }

    @app.post("/v1/l15/phonopy-harmonic")
    async def phonopy_harmonic(req: L15Request) -> dict[str, Any]:
        params = _req_to_params(req)
        adapter = PhonopyHarmonicAdapter()
        try:
            env = adapter.compute(params)
            return env.model_dump(mode="json")
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post("/v1/l15/phono3py-bte")
    async def phono3py_bte(req: L15Request) -> dict[str, Any]:
        params = _req_to_params(req)
        adapter = Phono3pyAnharmonicBTEAdapter()
        try:
            env = adapter.compute(params)
            return env.model_dump(mode="json")
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post("/v1/l15/hiphive-fit")
    async def hiphive_fit(req: L15Request) -> dict[str, Any]:
        params = _req_to_params(req)
        adapter = HiPhiveForceConstantFitAdapter()
        try:
            env = adapter.compute(params)
            return env.model_dump(mode="json")
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post("/v1/l15/boltztrap2-transport")
    async def boltztrap2_transport(req: L15Request) -> dict[str, Any]:
        params = _req_to_params(req)
        adapter = BoltzTraP2RigidBandTransportAdapter()
        try:
            env = adapter.compute(params)
            return env.model_dump(mode="json")
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post("/v1/l15/amset-transport")
    async def amset_transport(req: L15Request) -> dict[str, Any]:
        params = _req_to_params(req)
        adapter = AmsetScatteringTransportAdapter()
        try:
            env = adapter.compute(params)
            return env.model_dump(mode="json")
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post("/v1/l15/zt-assemble")
    async def zt_assemble(req: L15Request) -> dict[str, Any]:
        """Orchestrate the full thermoelectric ZT chain for a candidate.

        Returns the assembled envelope with both BoltzTraP2 and AMSET branches.
        """
        params = _req_to_params(req)
        try:
            env = run_zt_assembly(params)
            return env.model_dump(mode="json")
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    return app


# Module-level singleton for import convenience
l15_app: FastAPI = create_l15_app()
