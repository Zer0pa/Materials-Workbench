"""L15PhononAdapter — abstract base class for every L1.5 adapter.

Every concrete L1.5 adapter (Phonopy harmonic, Phono3py BTE, HiPhive FC fit,
BoltzTraP2 transport, AMSET transport, ZT assembler) subclasses this base so
the L1.5 service can dispatch by adapter name and the audit ledger sees a
uniform envelope shape.

Key invariants
--------------
1. ``layer="L1.5"`` on every emitted envelope.
2. ``output`` validated against :class:`L15PhononOutput`.
3. ``falsifier.items`` always includes ``l15.phonon_does_not_substitute_for_ionic``
   with a hardcoded ``pass`` status — L1.5 envelopes MUST NEVER claim
   ``ionic_conductivity_S_per_cm`` (PRD §L1.5 Boundary).
4. ``audit.input_hash`` / ``output_hash`` via sha256 of canonical JSON.
5. ``boundary`` block carries verbatim RESEARCH_BOUNDARY.
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
    L15PhononOutput,
    RightsBlock,
    ToolAdapter,
    canonical_json_bytes,
    sha256_of,
)

__all__ = [
    "L15PhononAdapter",
    "L15JobParams",
    "make_l15_envelope",
    "rollup_falsifier_status",
    "L15_SERVICE_REF",
]

# Canonical service reference baked into every envelope this layer emits.
L15_SERVICE_REF: str = "service:l1-5-phonon-service:v1"

# Hardcoded phonon boundary falsifier — non-negotiable.
_PHONON_NOT_IONIC_ITEM = FalsifierItem(
    name="l15.phonon_does_not_substitute_for_ionic",
    threshold="envelope MUST NOT contain ionic_conductivity_S_per_cm",
    actual="field_absent",
    status="pass",
    rationale=(
        "PRD §L1.5 Boundary: 'Phonon does NOT substitute for ionic conductivity.' "
        "The L1.5 layer is forbidden from claiming Li-ion conductivity; that is "
        "exclusively the IonicTransportService's domain."
    ),
)


class L15JobParams(BaseModel):
    """Canonical input parameters for an L1.5 phonon/transport job."""

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
            "for adapters that do not consume a structure directly)."
        ),
    )
    fixture_id: str | None = Field(
        default=None,
        description=(
            "Stable fixture identifier when running calibrated fixtures "
            "(e.g. 'fixture:Bi2Te3:ae87f3b2'). Used by stub adapters "
            "to route to literature-canonical values."
        ),
    )
    material_id: str | None = Field(
        default=None,
        description="Material label: 'Si', 'Bi2Te3', 'PbTe', 'SnSe', 'NaCl', etc.",
    )
    temperature_K: float = Field(
        default=300.0,
        gt=0.0,
        description="Target temperature for transport properties (K).",
    )
    q_mesh: list[int] = Field(
        default_factory=lambda: [6, 6, 6],
        min_length=3,
        max_length=3,
        description="Phonon q-point mesh [n1, n2, n3].",
    )
    force_backend: str = Field(
        default="stub",
        description=(
            "Force constant backend: 'stub' (synthetic) or 'runpod_rest' "
            "(real DFT via Runpod; gated behind L15_FORCE_BACKEND env var)."
        ),
    )
    band_backend: str = Field(
        default="stub",
        description=(
            "Band structure backend: 'stub' (synthetic) or 'runpod_rest' "
            "(real DFT; gated behind L15_BAND_BACKEND env var)."
        ),
    )
    carrier_type: str = Field(
        default="p",
        description="Carrier type: 'p' (holes) or 'n' (electrons) for transport.",
    )
    doping_per_cm3: float = Field(
        default=1.0e19,
        gt=0.0,
        description="Carrier concentration (per cm³) for transport calculations.",
    )
    campaign_id: str = Field(default="campaign:l1-5-default")
    candidate_id: str = Field(default="candidate:l1-5-default")
    run_id: str | None = Field(default=None, description="If None, auto-generated.")
    rights_claim_id: str = Field(default="rights:l1-5:default")
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


def make_l15_envelope(
    output: L15PhononOutput,
    params: L15JobParams,
    adapter_name: str,
    adapter_version: str,
    backend: str,
    engine: str,
    extra_falsifier_items: list[FalsifierItem] | None = None,
    extra_input: dict[str, Any] | None = None,
) -> Envelope:
    """Wrap an :class:`L15PhononOutput` in a fully populated L1.5 envelope.

    * ``layer="L1.5"``.
    * ``input_refs`` includes the canonical L15 service URN.
    * Hardcoded ``phonon_does_not_substitute_for_ionic`` falsifier is always
      prepended.
    * ``audit.input_hash`` is sha256 of canonical JSON of key inputs.
    """
    run_id = params.run_id or f"run:l1-5:{uuid.uuid4().hex[:12]}"
    out_dict = output.model_dump(mode="json")

    canonical_input: dict[str, Any] = {
        "structure_hash": params.structure_hash,
        "temperature_K": params.temperature_K,
        "fixture_id": params.fixture_id,
        "material_id": params.material_id,
        "q_mesh": params.q_mesh,
        "service_ref": L15_SERVICE_REF,
    }
    if extra_input:
        canonical_input.update(extra_input)

    in_bytes = canonical_json_bytes(canonical_input)
    out_bytes = canonical_json_bytes(out_dict)
    audit_id = f"audit:l1-5:{uuid.uuid4().hex[:12]}"

    # Hardcoded boundary falsifier is always first.
    items: list[FalsifierItem] = [_PHONON_NOT_IONIC_ITEM]
    items.extend(output.falsifier_items())
    if extra_falsifier_items:
        items.extend(extra_falsifier_items)

    # Assert the output does NOT claim ionic conductivity.
    assert not hasattr(output, "ionic_conductivity_S_per_cm") or getattr(
        output, "ionic_conductivity_S_per_cm", None
    ) is None, (
        "L1.5 envelope MUST NOT claim ionic_conductivity_S_per_cm. "
        "PRD §L1.5 Boundary: phonons do not substitute for ionic transport."
    )

    envelope = Envelope(
        research_boundary=RESEARCH_BOUNDARY,
        run_id=run_id,
        campaign_id=params.campaign_id,
        candidate_id=params.candidate_id,
        layer="L1.5",
        tool_adapter=ToolAdapter(
            name=adapter_name,
            version=adapter_version,
            backend=backend,  # type: ignore[arg-type]
            engine=engine,
        ),
        input_refs=[L15_SERVICE_REF],
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


class L15PhononAdapter(abc.ABC):
    """Abstract base for L1.5 phonon/transport adapters.

    Each concrete adapter computes one layer of the phonon-ZT evidence
    chain. The :class:`ThermoelectricZtAssembler` orchestrates the full
    chain for a thermoelectric candidate.
    """

    ADAPTER_NAME: str = "L15PhononAdapter"
    ADAPTER_VERSION: str = "0.1.0"
    BACKEND: str = "stub"
    ENGINE: str = "l1-5-stub"

    @abc.abstractmethod
    def compute(self, params: L15JobParams) -> Envelope:
        """Run the adapter and return a fully wrapped Envelope."""

    def make_envelope(
        self,
        output: L15PhononOutput,
        params: L15JobParams,
        extra_falsifier_items: list[FalsifierItem] | None = None,
        extra_input: dict[str, Any] | None = None,
    ) -> Envelope:
        return make_l15_envelope(
            output=output,
            params=params,
            adapter_name=self.ADAPTER_NAME,
            adapter_version=self.ADAPTER_VERSION,
            backend=self.BACKEND,
            engine=self.ENGINE,
            extra_falsifier_items=extra_falsifier_items,
            extra_input=extra_input,
        )

    @staticmethod
    def _utc_now() -> str:
        return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="microseconds")
