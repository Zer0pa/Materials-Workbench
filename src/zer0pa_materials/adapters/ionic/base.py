"""IonicTransportAdapter — abstract base class for every ionic adapter.

Every concrete ionic adapter (NEB barrier, MLIP-MD/AIMD diffusion,
Arrhenius fit, electrochemical window, interface stability) subclasses
this base so the IonicTransportService can dispatch by adapter name.

The envelope construction is centralised in :func:`make_ionic_envelope`
so every ionic adapter emits envelopes with:

* ``layer="ionic"`` (PRD §Architecture Invariant — ionic is its own slot).
* ``output`` validated against :class:`IonicTransportOutput` (registry).
* ``falsifier.items`` populated from ``output.falsifier_items()``.
* ``audit`` carrying canonical input/output hashes.
* ``rights`` carrying the operator default reuse scope.

PRD §Ionic Transport mandates that battery MVP claims of ionic
conductivity originate from this service; the falsifier
``requires_ionic_transport_service`` (in
:mod:`zer0pa_materials.falsifiers.ionic_falsifiers`) tags every envelope
emitted from here with the service reference so downstream layers can
prove the claim has the right provenance.
"""

from __future__ import annotations

import abc
import datetime
import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from zer0pa_materials.boundary import RESEARCH_BOUNDARY
from zer0pa_materials.envelope import (
    AuditBlock,
    Envelope,
    FalsifierItem,
    FalsifierStatus,
    IonicTransportOutput,
    RightsBlock,
    ToolAdapter,
    canonical_json_bytes,
    sha256_of,
)

__all__ = [
    "IonicTransportAdapter",
    "IonicJobParams",
    "make_ionic_envelope",
    "rollup_falsifier_status",
    "IONIC_TRANSPORT_SERVICE_REF",
]

# Canonical service reference baked into every envelope this layer emits.
# PRD §Ionic Transport: "Battery MVP claims require an explicit
# IonicTransportService". The string is stable so the
# ``requires_ionic_transport_service`` falsifier can recognise it.
IONIC_TRANSPORT_SERVICE_REF: str = "service:ionic-transport-service:v1"


class IonicJobParams(BaseModel):
    """Canonical input parameters for an ionic transport job."""

    model_config = ConfigDict(extra="allow")

    structure_cif: str | None = Field(
        default=None,
        description="CIF text of the input structure; optional for derived adapters.",
    )
    structure_hash: str = Field(
        ...,
        min_length=8,
        description=(
            "sha256: hash of the canonicalised structure (or 'sha256:none' "
            "for adapters that do not consume a structure directly, e.g. "
            "an Arrhenius fit over a series of conductivity measurements)."
        ),
    )
    fixture_id: str | None = Field(
        default=None,
        description=(
            "Stable fixture identifier when running calibrated fixtures "
            "(e.g. 'fixture:LLZO_cubic:d45cb2bf'). Used by stub adapters "
            "to route to literature-canonical values."
        ),
    )
    temperature_K: float = Field(
        default=300.0,
        gt=0.0,
        description="Temperature for room-temperature properties (K).",
    )
    li_carrier_concentration_per_cm3: float = Field(
        default=2.0e22,
        gt=0.0,
        description=(
            "Li-ion carrier number density (per cm³). Typical solid "
            "electrolyte order of magnitude is 1e22 to 5e22 /cm³."
        ),
    )
    haven_ratio: float = Field(
        default=1.0,
        gt=0.0,
        description=(
            "Haven ratio H_R = sigma_NE / sigma_measured. Default 1.0 means "
            "we assume Nernst-Einstein conductivity equals the measured "
            "tracer-derived conductivity. Real systems show H_R < 1."
        ),
    )
    image_count: int = Field(default=7, ge=3, description="NEB image count (default 7).")
    force_tolerance_eV_per_angstrom: float = Field(
        default=0.05,
        gt=0.0,
        description="NEB force convergence threshold (eV/Å).",
    )
    md_trajectory_length_ps: float = Field(
        default=10.0,
        gt=0.0,
        description="MD trajectory length (ps) used for MSD fitting.",
    )
    n_md_steps: int = Field(
        default=10000,
        ge=100,
        description="Number of MD steps recorded in the synthetic trajectory.",
    )
    interface_mode: str = Field(
        default="li_metal",
        description=(
            "Interface stability target: 'li_metal' for Li-metal anode, "
            "'cathode_facing' for cathode-facing use, 'coating_interlayer' "
            "for coated/interlayer routing (allows reduction instability)."
        ),
    )
    cathode_chemistry: str = Field(
        default="NMC811",
        description="Cathode placeholder for interface adapter (e.g. 'NMC811').",
    )
    campaign_id: str = Field(default="campaign:ionic-default")
    candidate_id: str = Field(default="candidate:ionic-default")
    run_id: str | None = Field(default=None, description="If None, auto-generated.")
    path_id: str | None = Field(
        default=None,
        description="NEB endpoint pair label, e.g. '24c-48g'.",
    )
    rights_claim_id: str = Field(default="rights:ionic:default")
    reuse_scope: str = Field(default="tenant_only")


def rollup_falsifier_status(items: list[FalsifierItem]) -> FalsifierStatus:
    """Roll up a list of FalsifierItems into a single status."""
    if any(fi.status == "fail" for fi in items):
        return "fail"
    if any(fi.status == "blocked" for fi in items):
        return "blocked"
    if any(fi.status == "inconclusive" for fi in items):
        return "inconclusive"
    return "pass"


def make_ionic_envelope(
    output: IonicTransportOutput,
    params: IonicJobParams,
    adapter_name: str,
    adapter_version: str,
    backend: str,
    engine: str,
    extra_falsifier_items: list[FalsifierItem] | None = None,
    extra_input: dict[str, Any] | None = None,
) -> Envelope:
    """Wrap an :class:`IonicTransportOutput` in a fully populated envelope.

    * ``layer="ionic"``.
    * ``input_refs`` includes the canonical IonicTransportService URN so
      the ``requires_ionic_transport_service`` falsifier always finds it.
    * ``audit.input_hash`` is the sha256 of the canonical-JSON of
      ``{structure_hash, temperature_K, ...extra_input}``.
    """
    run_id = params.run_id or f"run:ionic:{uuid.uuid4().hex[:12]}"
    out_dict = output.model_dump(mode="json")

    canonical_input: dict[str, Any] = {
        "structure_hash": params.structure_hash,
        "temperature_K": params.temperature_K,
        "fixture_id": params.fixture_id,
        "li_carrier_concentration_per_cm3": params.li_carrier_concentration_per_cm3,
        "haven_ratio": params.haven_ratio,
        "interface_mode": params.interface_mode,
        "cathode_chemistry": params.cathode_chemistry,
        "service_ref": IONIC_TRANSPORT_SERVICE_REF,
    }
    if extra_input:
        canonical_input.update(extra_input)

    in_bytes = canonical_json_bytes(canonical_input)
    out_bytes = canonical_json_bytes(out_dict)
    audit_id = f"audit:ionic:{uuid.uuid4().hex[:12]}"

    items = list(output.falsifier_items())
    if extra_falsifier_items:
        items.extend(extra_falsifier_items)

    envelope = Envelope(
        research_boundary=RESEARCH_BOUNDARY,
        run_id=run_id,
        campaign_id=params.campaign_id,
        candidate_id=params.candidate_id,
        layer="ionic",
        tool_adapter=ToolAdapter(
            name=adapter_name,
            version=adapter_version,
            backend=backend,  # type: ignore[arg-type]
            engine=engine,
        ),
        input_refs=[IONIC_TRANSPORT_SERVICE_REF],
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
    )
    return envelope


class IonicTransportAdapter(abc.ABC):
    """Abstract base for ionic transport adapters.

    The class hierarchy is intentionally flat — each ionic adapter
    computes one of the six PRD-required quantities, all of which are
    eventually merged by the :class:`IonicTransportService` into the
    full battery evidence chain.
    """

    ADAPTER_NAME: str = "IonicTransportAdapter"
    ADAPTER_VERSION: str = "0.1.0"
    BACKEND: str = "stub"
    ENGINE: str = "ionic-stub"

    @abc.abstractmethod
    def compute(self, params: IonicJobParams) -> Envelope:
        """Run the adapter and return a fully wrapped Envelope."""

    # Convenience helper so concrete adapters can build envelopes
    # without re-importing make_ionic_envelope.
    def make_envelope(
        self,
        output: IonicTransportOutput,
        params: IonicJobParams,
        extra_falsifier_items: list[FalsifierItem] | None = None,
        extra_input: dict[str, Any] | None = None,
    ) -> Envelope:
        return make_ionic_envelope(
            output=output,
            params=params,
            adapter_name=self.ADAPTER_NAME,
            adapter_version=self.ADAPTER_VERSION,
            backend=self.BACKEND,
            engine=self.ENGINE,
            extra_falsifier_items=extra_falsifier_items,
            extra_input=extra_input,
        )

    # Datestamp helper kept here so the audit logger sees identical
    # timestamps when multiple adapters run inside the same service call.
    @staticmethod
    def _utc_now() -> str:
        return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="microseconds")
