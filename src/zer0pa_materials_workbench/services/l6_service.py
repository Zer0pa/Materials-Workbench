"""L6 generative discovery REST stub service (FastAPI).

Endpoints:
    POST /v1/l6/generate    L6GenerateRequest -> list[Envelope]
    GET  /v1/l6/healthz

The generate endpoint dispatches to all three generator adapters (MatterGen,
DiffCSP, CrystaLLM) in stub mode and returns a list of Envelope dicts.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from zer0pa_materials_workbench.adapters.l6.crystallm import CrystaLlmCifGeneratorAdapter
from zer0pa_materials_workbench.adapters.l6.diffcsp import DiffCspGeneratorAdapter
from zer0pa_materials_workbench.adapters.l6.mattergen import MatterGenGeneratorAdapter
from zer0pa_materials_workbench.boundary import RESEARCH_BOUNDARY
from zer0pa_materials_workbench.envelope.config import MaterialsConfig

app = FastAPI(
    title="Zer0pa Materials Workbench — L6 Generative Discovery Service",
    description=(
        "REST stub for L6 crystal structure generation. "
        "Research infrastructure for in silico materials science discovery. "
        "Outputs are research artifacts. No regulatory certification claims."
    ),
    version="0.1.0",
)


# ---------------------------------------------------------------------------
# Request model
# ---------------------------------------------------------------------------


class L6GenerateRequest(BaseModel):
    """Request body for POST /v1/l6/generate."""

    chemical_system: str = Field(
        default="Li-La-Zr-O",
        description="Chemical system constraint (e.g. 'Li-La-Zr-O', 'Li-P-S-Cl').",
    )
    target_conductivity_S_per_cm: float = Field(
        default=1e-3,
        description="Target ionic conductivity in S/cm.",
    )
    n_candidates: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Number of candidates to generate per adapter.",
    )
    adapters: list[str] = Field(
        default_factory=lambda: ["mattergen", "diffcsp", "crystallm"],
        description="Which generator adapters to invoke.",
    )
    prompt: str = Field(
        default="",
        description="Text prompt for CrystaLLM (optional).",
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/v1/l6/healthz")
async def healthz() -> dict[str, str]:
    """Health check."""
    return {
        "status": "ok",
        "layer": "L6",
        "research_boundary": RESEARCH_BOUNDARY,
    }


@app.post("/v1/l6/generate")
async def generate(request: L6GenerateRequest) -> list[dict[str, Any]]:
    """Generate crystal structure candidates via stub adapters.

    Returns:
        List of Envelope dicts (one per candidate) with layer="L6".
        novelty_status is always "pending" — promoted to "novel" only after
        L1 + ionic + L2 falsifiers pass downstream.
    """
    config = MaterialsConfig()
    constraints: dict[str, Any] = {
        "chemical_system": request.chemical_system,
        "target_conductivity_S_per_cm": request.target_conductivity_S_per_cm,
        "prompt": request.prompt,
    }

    all_envelopes = []
    adapter_set = set(request.adapters)

    try:
        if "mattergen" in adapter_set:
            mg = MatterGenGeneratorAdapter(config=config, n_candidates=request.n_candidates)
            all_envelopes.extend(mg.generate(constraints))

        if "diffcsp" in adapter_set:
            dc = DiffCspGeneratorAdapter(config=config, n_candidates=request.n_candidates)
            all_envelopes.extend(dc.generate(constraints))

        if "crystallm" in adapter_set:
            cl = CrystaLlmCifGeneratorAdapter(config=config)
            all_envelopes.extend(cl.generate(constraints))

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return [env.model_dump(mode="json") for env in all_envelopes]
