"""MVP Evidence Packet REST service (Wave 5a).

Endpoints
---------

* ``POST /v1/packets/assemble/battery``        — assemble a battery packet for a fixture.
* ``POST /v1/packets/assemble/thermoelectric`` — assemble a thermoelectric packet.
* ``POST /v1/packets/validate``                — run packet validators.
* ``POST /v1/packets/export-ro-crate``         — write the packet to an RO-Crate dir.
* ``GET  /v1/packets/healthz``                 — liveness probe.

The service is the wire-level surface; the actual business logic lives
in :mod:`zer0pa_materials_workbench.packets`.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from zer0pa_materials_workbench.packets.battery_packet import (
    BATTERY_FIXTURE_SPECS,
    assemble_battery_packet,
)
from zer0pa_materials_workbench.packets.evidence_packet import (
    EvidencePacket,
)
from zer0pa_materials_workbench.packets.ro_crate_export import (
    export_packet_to_ro_crate,
)
from zer0pa_materials_workbench.packets.thermoelectric_packet import (
    THERMOELECTRIC_FIXTURE_SPECS,
    assemble_thermoelectric_packet,
)
from zer0pa_materials_workbench.packets.validators import (
    ValidationReport,
    validate_evidence_packet,
)

__all__ = [
    "PACKETS_SERVICE_NAME",
    "PACKETS_SERVICE_VERSION",
    "AssembleBatteryRequest",
    "AssembleThermoelectricRequest",
    "ExportRequest",
    "ExportResponse",
    "ValidateRequest",
    "create_packets_app",
    "packets_app",
]


PACKETS_SERVICE_NAME: str = "MvpEvidencePacketService"
PACKETS_SERVICE_VERSION: str = "0.1.0"


class AssembleBatteryRequest(BaseModel):
    """Request body for ``POST /v1/packets/assemble/battery``."""

    model_config = ConfigDict(extra="forbid")

    fixture_key: Literal["LLZO", "Li6PS5Cl", "Li-Mg-Zr-Cl-seed"]
    interface_mode: Literal["li_metal", "cathode_facing", "coating_interlayer"] = (
        "li_metal"
    )
    candidate_id: str | None = Field(default=None)
    campaign_id: str | None = Field(default=None)
    rights_claim_id: str = Field(default="rights:battery:default")
    reuse_scope: Literal["tenant_only", "shared_learning", "open_science"] = (
        "tenant_only"
    )
    cathode_chemistry: str = Field(default="NMC811")


class AssembleThermoelectricRequest(BaseModel):
    """Request body for ``POST /v1/packets/assemble/thermoelectric``."""

    model_config = ConfigDict(extra="forbid")

    fixture_key: Literal["Si", "Bi2Te3", "PbTe", "SnSe"]
    candidate_id: str | None = Field(default=None)
    campaign_id: str | None = Field(default=None)
    rights_claim_id: str = Field(default="rights:thermoelectric:default")
    reuse_scope: Literal["tenant_only", "shared_learning", "open_science"] = (
        "tenant_only"
    )


class ValidateRequest(BaseModel):
    """Request body for ``POST /v1/packets/validate``."""

    model_config = ConfigDict(extra="allow")

    packet: dict[str, Any] = Field(..., description="EvidencePacket dict.")


class ExportRequest(BaseModel):
    """Request body for ``POST /v1/packets/export-ro-crate``."""

    model_config = ConfigDict(extra="forbid")

    packet: dict[str, Any] = Field(..., description="EvidencePacket dict.")
    out_dir: str | None = Field(
        default=None,
        description=(
            "Optional output directory. If absent, a system temp directory "
            "is used and the response carries the path."
        ),
    )


class ExportResponse(BaseModel):
    """Response body for ``POST /v1/packets/export-ro-crate``."""

    model_config = ConfigDict(extra="forbid")

    crate_root: str
    metadata_path: str
    packet_path: str
    section_count: int
    entry_count: int
    sections: dict[str, str]


def create_packets_app() -> FastAPI:
    """Create the FastAPI app for the MVP Evidence Packet Service."""
    app = FastAPI(
        title=PACKETS_SERVICE_NAME,
        version=PACKETS_SERVICE_VERSION,
        description=(
            "MVP Evidence Packet generator service (PRD §Final Output Required #9 + #10). "
            "Assembles publishable-paper packets for battery and thermoelectric fixtures."
        ),
    )

    @app.get("/v1/packets/healthz")
    async def healthz() -> dict[str, str]:
        return {
            "status": "ok",
            "service": PACKETS_SERVICE_NAME,
            "version": PACKETS_SERVICE_VERSION,
        }

    @app.get("/v1/packets/fixtures/battery")
    async def list_battery_fixtures() -> dict[str, Any]:
        return {
            "fixtures": sorted(BATTERY_FIXTURE_SPECS.keys()),
            "count": len(BATTERY_FIXTURE_SPECS),
        }

    @app.get("/v1/packets/fixtures/thermoelectric")
    async def list_thermoelectric_fixtures() -> dict[str, Any]:
        return {
            "fixtures": sorted(THERMOELECTRIC_FIXTURE_SPECS.keys()),
            "count": len(THERMOELECTRIC_FIXTURE_SPECS),
        }

    @app.post("/v1/packets/assemble/battery")
    async def assemble_battery(req: AssembleBatteryRequest) -> dict[str, Any]:
        try:
            packet = assemble_battery_packet(
                req.fixture_key,
                interface_mode=req.interface_mode,
                candidate_id=req.candidate_id,
                campaign_id=req.campaign_id,
                rights_claim_id=req.rights_claim_id,
                reuse_scope=req.reuse_scope,
                cathode_chemistry=req.cathode_chemistry,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return packet.model_dump(mode="json")

    @app.post("/v1/packets/assemble/thermoelectric")
    async def assemble_thermoelectric(
        req: AssembleThermoelectricRequest,
    ) -> dict[str, Any]:
        try:
            packet = assemble_thermoelectric_packet(
                req.fixture_key,
                candidate_id=req.candidate_id,
                campaign_id=req.campaign_id,
                rights_claim_id=req.rights_claim_id,
                reuse_scope=req.reuse_scope,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return packet.model_dump(mode="json")

    @app.post("/v1/packets/validate")
    async def validate(req: ValidateRequest) -> dict[str, Any]:
        try:
            packet = EvidencePacket.model_validate(req.packet)
        except Exception as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        report: ValidationReport = validate_evidence_packet(packet)
        return report.model_dump(mode="json")

    @app.post("/v1/packets/export-ro-crate")
    async def export_ro_crate(req: ExportRequest) -> ExportResponse:
        try:
            packet = EvidencePacket.model_validate(req.packet)
        except Exception as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        if req.out_dir:
            out_root = Path(req.out_dir)
        else:
            out_root = Path(tempfile.mkdtemp(prefix="zer0pa-packet-"))
        try:
            bundle = export_packet_to_ro_crate(packet, out_root)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return ExportResponse(
            crate_root=str(bundle.crate_root),
            metadata_path=str(bundle.metadata_path),
            packet_path=str(bundle.packet_path),
            section_count=len(bundle.section_paths),
            entry_count=len(bundle.entries),
            sections={k: str(v) for k, v in bundle.section_paths.items()},
        )

    return app


# Module-level singleton for ``uvicorn zer0pa_materials_workbench.services:packets_app``.
packets_app: FastAPI = create_packets_app()
