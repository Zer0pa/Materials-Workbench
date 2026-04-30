"""L7Adapter abstract base + envelope helper.

Every L7 adapter emits :class:`zer0pa_materials.envelope.Envelope` with
``layer="L7"`` and ``output`` validated against
:class:`zer0pa_materials.envelope.L7CampaignOutput`.

Boundary discipline:

* The boundary block is baked in via :data:`zer0pa_materials.boundary.RESEARCH_BOUNDARY`.
* Every envelope carries the campaign's ``campaign_id`` and the candidate's
  ``candidate_id``.
* Every envelope's ``audit.audit_record_id`` is generated here so the
  acceptance gate can verify provenance.
"""

from __future__ import annotations

import abc
import datetime as _dt
import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from zer0pa_materials.boundary import RESEARCH_BOUNDARY
from zer0pa_materials.envelope import (
    AuditBlock,
    BackEdge,
    Envelope,
    FalsifierItem,
    FalsifierStatus,
    L7CampaignOutput,
    RightsBlock,
    ToolAdapter,
    canonical_json_bytes,
    sha256_of,
)

__all__ = [
    "L7_SERVICE_REF",
    "L7CampaignParams",
    "L7Adapter",
    "make_l7_envelope",
    "rollup_falsifier_status",
]

L7_SERVICE_REF: str = "service:l7-orchestrator:v1"


class L7CampaignParams(BaseModel):
    """Canonical input parameters for an L7 adapter call."""

    model_config = ConfigDict(extra="allow")

    campaign_id: str = Field(default="campaign:l7-default")
    candidate_id: str = Field(default="candidate:l7-default")
    run_id: str | None = Field(default=None)
    rights_claim_id: str = Field(default="rights:l7:default")
    reuse_scope: str = Field(default="tenant_only")
    objective: str = Field(default="undefined")
    n_candidates: int = Field(default=1, ge=1, le=64)
    fidelity: str = Field(
        default="L2_stub",
        description=(
            "Identifier for the fidelity class (e.g. 'L2_stub', 'L1_DFT_PBE', "
            "'L1_DFT_HSE06'). Used by the BoTorch multi-fidelity routing."
        ),
    )
    backend: str = Field(default="stub")
    tenant: str = Field(default="demo")


def rollup_falsifier_status(items: list[FalsifierItem]) -> FalsifierStatus:
    if any(fi.status == "fail" for fi in items):
        return "fail"
    if any(fi.status == "blocked" for fi in items):
        return "blocked"
    if any(fi.status == "inconclusive" for fi in items):
        return "inconclusive"
    return "pass"


def make_l7_envelope(
    output: L7CampaignOutput,
    params: L7CampaignParams,
    adapter_name: str,
    adapter_version: str,
    backend: str,
    engine: str,
    extra_falsifier_items: list[FalsifierItem] | None = None,
    extra_input: dict[str, Any] | None = None,
    back_edges: list[BackEdge] | None = None,
) -> Envelope:
    """Wrap an :class:`L7CampaignOutput` in a fully populated envelope."""
    run_id = params.run_id or f"run:l7:{uuid.uuid4().hex[:12]}"
    out_dict = output.model_dump(mode="json")

    canonical_input: dict[str, Any] = {
        "campaign_id": params.campaign_id,
        "candidate_id": params.candidate_id,
        "objective": params.objective,
        "n_candidates": params.n_candidates,
        "fidelity": params.fidelity,
        "service_ref": L7_SERVICE_REF,
    }
    if extra_input:
        canonical_input.update(extra_input)

    in_bytes = canonical_json_bytes(canonical_input)
    out_bytes = canonical_json_bytes(out_dict)
    audit_id = f"audit:l7:{uuid.uuid4().hex[:12]}"

    items = list(output.falsifier_items())
    if extra_falsifier_items:
        items.extend(extra_falsifier_items)

    envelope = Envelope(
        research_boundary=RESEARCH_BOUNDARY,
        run_id=run_id,
        campaign_id=params.campaign_id,
        candidate_id=params.candidate_id,
        layer="L7",
        tool_adapter=ToolAdapter(
            name=adapter_name,
            version=adapter_version,
            backend=backend,  # type: ignore[arg-type]
            engine=engine,
        ),
        input_refs=[L7_SERVICE_REF],
        output=out_dict,
        falsifier={
            "status": rollup_falsifier_status(items),
            "items": [fi.model_dump(mode="json") for fi in items],
        },
        audit=AuditBlock(
            audit_record_id=audit_id,
            input_hash=sha256_of(in_bytes),
            output_hash=sha256_of(out_bytes),
        ),
        rights=RightsBlock(
            rights_claim_id=params.rights_claim_id,
            reuse_scope=params.reuse_scope,  # type: ignore[arg-type]
        ),
        back_edges=back_edges or [],
    )
    return envelope


class L7Adapter(abc.ABC):
    """Abstract base for L7 adapters."""

    ADAPTER_NAME: str = "L7Adapter"
    ADAPTER_VERSION: str = "0.1.0"
    BACKEND: str = "stub"
    ENGINE: str = "l7-stub"

    @abc.abstractmethod
    def execute(self, params: L7CampaignParams) -> Envelope:
        """Run the adapter and return a fully wrapped Envelope."""

    def make_envelope(
        self,
        output: L7CampaignOutput,
        params: L7CampaignParams,
        extra_falsifier_items: list[FalsifierItem] | None = None,
        extra_input: dict[str, Any] | None = None,
        back_edges: list[BackEdge] | None = None,
    ) -> Envelope:
        return make_l7_envelope(
            output=output,
            params=params,
            adapter_name=self.ADAPTER_NAME,
            adapter_version=self.ADAPTER_VERSION,
            backend=self.BACKEND,
            engine=self.ENGINE,
            extra_falsifier_items=extra_falsifier_items,
            extra_input=extra_input,
            back_edges=back_edges,
        )

    @staticmethod
    def _utc_now() -> str:
        return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="microseconds")
