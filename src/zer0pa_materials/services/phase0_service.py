"""Phase 0 REST stub service (FastAPI).

Endpoints:
    POST /v1/phase0/extract           Phase0ExtractRequest  -> Envelope
    POST /v1/phase0/optimade/query    OptimadeQueryRequest  -> Envelope
    GET  /v1/phase0/healthz

All endpoints call assert_boundary on every emitted envelope and return
the raw Envelope dict. The service is a stub — real LLM and OPTIMADE
backends are parked behind config flags.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from zer0pa_materials.adapters.phase0.langgraph_extraction import LangGraphExtractionWorkflow
from zer0pa_materials.adapters.phase0.optimade import OptimadeFederatedQueryAdapter
from zer0pa_materials.boundary import RESEARCH_BOUNDARY
from zer0pa_materials.envelope.config import MaterialsConfig

app = FastAPI(
    title="Zer0pa Materials — Phase 0 Service",
    description=(
        "REST stub for Phase 0 literature mining and OPTIMADE structure queries. "
        "Research infrastructure for in silico materials science discovery. "
        "Outputs are research artifacts. No regulatory certification claims."
    ),
    version="0.1.0",
)


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class Phase0ExtractRequest(BaseModel):
    """Request body for POST /v1/phase0/extract."""

    fixture: str = Field(
        default="LLZO",
        description="Fixture key: one of LLZO, Li6PS5Cl, Li-Mg-Zr-Cl-seed.",
    )
    doi: str = Field(default="", description="DOI of the paper to extract from (stub: unused).")
    material: str = Field(default="", description="Material formula (for record-keeping).")


class OptimadeQueryRequest(BaseModel):
    """Request body for POST /v1/phase0/optimade/query."""

    elements: list[str] = Field(
        default_factory=list,
        description="List of elements to filter by (OPTIMADE filter syntax).",
    )
    filter: str = Field(
        default="",
        description="Raw OPTIMADE filter string (advanced usage; overrides elements if set).",
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/v1/phase0/healthz")
async def healthz() -> dict[str, str]:
    """Health check."""
    return {
        "status": "ok",
        "layer": "phase0",
        "research_boundary": RESEARCH_BOUNDARY,
    }


@app.post("/v1/phase0/extract")
async def extract(request: Phase0ExtractRequest) -> dict[str, Any]:
    """Extract properties from a paper/fixture via the LangGraph workflow stub.

    Returns:
        The full Envelope dict with layer="phase0".
    """
    config = MaterialsConfig()
    adapter = LangGraphExtractionWorkflow(config=config)
    try:
        envelope = adapter.query(
            {
                "fixture": request.fixture,
                "doi": request.doi,
                "material": request.material,
            }
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return envelope.model_dump(mode="json")


@app.post("/v1/phase0/optimade/query")
async def optimade_query(request: OptimadeQueryRequest) -> dict[str, Any]:
    """Federated OPTIMADE v1.3 structure query (stub backend).

    Returns:
        The full Envelope dict with layer="phase0".
    """
    config = MaterialsConfig()
    adapter = OptimadeFederatedQueryAdapter(config=config)
    try:
        envelope = adapter.query(
            {
                "elements": request.elements,
                "filter": request.filter,
            }
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return envelope.model_dump(mode="json")
