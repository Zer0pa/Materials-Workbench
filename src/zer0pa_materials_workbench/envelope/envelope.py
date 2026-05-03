"""Universal Layer Envelope (PRD §Architecture Invariant).

Every layer adapter MUST emit envelopes that conform to this schema. Down-
stream code (orchestration, audit, KG, falsifier ledger, plug-swap tests)
depends only on this contract; tools and engines are referenced by name
only inside ``tool_adapter`` so a swap from ``stub`` -> ``runpod_mock`` ->
``runpod_rest`` does not change the wire shape.

Design notes
------------

* The JSON shape is the PRD's literal (lines 60-100). We match it exactly
  so the schema export in ``runtime/schemas/envelope.v1.schema.json`` can
  be diffed against the PRD blob with zero structural rearrangement.

* ``research_boundary`` is the *value* of :data:`zer0pa_materials_workbench.boundary.RESEARCH_BOUNDARY`
  baked in. We validate it at model_validate time using ``assert_boundary``.

* ``input_hash`` and ``output_hash`` are validated against the
  ``^sha256:[0-9a-f]{64}$`` regex. The hashes are produced by
  :mod:`zer0pa_materials_workbench.envelope.hashing`.

* URN-like IDs (``run_id``, ``campaign_id``, etc.) are validated against
  per-class prefix patterns. ``audit_record_id``/``rights_claim_id`` are
  inside their nested groups but use the same prefix discipline.

* ``canonical_dict`` returns the envelope as a JSON-serialisable dict with
  keys in the exact order shown in the PRD. ``canonical_bytes`` returns the
  deterministic byte stream used for hashing.
"""

from __future__ import annotations

import re
from typing import Any, Literal

import orjson
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from zer0pa_materials_workbench.boundary import RESEARCH_BOUNDARY, assert_boundary
from zer0pa_materials_workbench.envelope.falsifier import FalsifierItem, FalsifierStatus
from zer0pa_materials_workbench.envelope.hashing import HASH_REGEX

__all__ = [
    "ENVELOPE_KEY_ORDER",
    "AuditBlock",
    "BackEdge",
    "Backend",
    "ConfidenceBand",
    "ConfidenceBlock",
    "DisagreementBlock",
    "DisagreementMetric",
    "Envelope",
    "EnvelopeContractVersion",
    "FalsifierBlock",
    "Layer",
    "ReuseScope",
    "RightsBlock",
    "ToolAdapter",
]


# ----------------------------------------------------------------------------
# Type aliases (Literals match PRD §Architecture Invariant)
# ----------------------------------------------------------------------------

EnvelopeContractVersion = Literal["zer0pa.materials.layer-envelope.v1"]
Layer = Literal[
    "phase0", "L1", "L1.5", "ionic", "L2", "L3", "L4", "L5", "L6", "L7"
]
Backend = Literal["stub", "local_cpu", "runpod_mock", "runpod_rest"]
ConfidenceBand = Literal["low", "medium", "high"]
ReuseScope = Literal["tenant_only", "shared_learning", "open_science"]


# ----------------------------------------------------------------------------
# URN-like ID validators
# ----------------------------------------------------------------------------

_RUN_ID_RE = re.compile(r"^run:[A-Za-z0-9._\-:/]+$")
_CAMPAIGN_ID_RE = re.compile(r"^campaign:[A-Za-z0-9._\-:/]+$")
_CANDIDATE_ID_RE = re.compile(r"^candidate:[A-Za-z0-9._\-:/]+$")
_AUDIT_ID_RE = re.compile(r"^audit:[A-Za-z0-9._\-:/]+$")
_RIGHTS_ID_RE = re.compile(r"^rights:[A-Za-z0-9._\-:/]+$")


def _validate_urn(value: str, regex: re.Pattern[str], name: str) -> str:
    if not regex.match(value):
        raise ValueError(f"{name} must match {regex.pattern!r}; got {value!r}")
    return value


# ----------------------------------------------------------------------------
# Nested blocks
# ----------------------------------------------------------------------------


class ToolAdapter(BaseModel):
    """Identification of the tool adapter that produced this envelope."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, description="Adapter name, e.g. 'PyScfMolecularSolver'.")
    version: str = Field(..., min_length=1, description="Adapter version, e.g. '0.1.0'.")
    backend: Backend = Field(..., description="Backend mode the adapter ran under.")
    engine: str = Field(
        ..., min_length=1, description="Tool/model identifier, e.g. 'PySCF', 'DPA-3.1-3M'."
    )


class ConfidenceBlock(BaseModel):
    """The envelope's confidence summary."""

    model_config = ConfigDict(extra="forbid")

    score: float = Field(default=0.0, ge=0.0, le=1.0)
    band: ConfidenceBand = Field(default="low")
    basis: list[str] = Field(default_factory=list, description="References supporting the score.")


class DisagreementMetric(BaseModel):
    """One disagreement metric (cross-model, cross-solver, cross-functional)."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1)
    value: float
    unit: str | None = None
    references: list[str] = Field(default_factory=list)


class DisagreementBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metrics: list[DisagreementMetric] = Field(default_factory=list)


class FalsifierBlock(BaseModel):
    """The envelope's falsifier roll-up."""

    model_config = ConfigDict(extra="forbid")

    status: FalsifierStatus = Field(default="pass")
    items: list[FalsifierItem] = Field(default_factory=list)


class AuditBlock(BaseModel):
    """Audit grounding for the envelope (PRD §Audit Trail And KG)."""

    model_config = ConfigDict(extra="forbid")

    audit_record_id: str = Field(..., description="URN starting with 'audit:'.")
    input_hash: str = Field(..., description="sha256:<hex>")
    output_hash: str = Field(..., description="sha256:<hex>")
    source_manifest_refs: list[str] = Field(default_factory=list)

    @field_validator("audit_record_id")
    @classmethod
    def _validate_audit_id(cls, v: str) -> str:
        return _validate_urn(v, _AUDIT_ID_RE, "audit_record_id")

    @field_validator("input_hash", "output_hash")
    @classmethod
    def _validate_hash(cls, v: str) -> str:
        if not HASH_REGEX.match(v):
            raise ValueError(f"hash must match ^sha256:[0-9a-f]{{64}}$; got {v!r}")
        return v


class RightsBlock(BaseModel):
    """Data rights / reuse scope (PRD §Data Sovereignty)."""

    model_config = ConfigDict(extra="forbid")

    rights_claim_id: str
    reuse_scope: ReuseScope

    @field_validator("rights_claim_id")
    @classmethod
    def _validate_rights_id(cls, v: str) -> str:
        return _validate_urn(v, _RIGHTS_ID_RE, "rights_claim_id")


class BackEdge(BaseModel):
    """Reference to an upstream envelope in the candidate's history."""

    model_config = ConfigDict(extra="forbid")

    layer: Layer
    audit_record_id: str
    relation: str = Field(
        default="DERIVED_FROM",
        description="KG edge label (PRD §Audit Trail And KG: KG edges).",
    )

    @field_validator("audit_record_id")
    @classmethod
    def _v(cls, v: str) -> str:
        return _validate_urn(v, _AUDIT_ID_RE, "audit_record_id")


# ----------------------------------------------------------------------------
# The envelope itself
# ----------------------------------------------------------------------------


# Canonical key order, matching the PRD JSON literal.
ENVELOPE_KEY_ORDER: tuple[str, ...] = (
    "contract_version",
    "research_boundary",
    "run_id",
    "campaign_id",
    "candidate_id",
    "layer",
    "tool_adapter",
    "input_refs",
    "output",
    "confidence",
    "disagreement",
    "falsifier",
    "audit",
    "rights",
    "back_edges",
)


class Envelope(BaseModel):
    """Universal layer envelope (PRD §Architecture Invariant)."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    contract_version: EnvelopeContractVersion = Field(
        default="zer0pa.materials.layer-envelope.v1"
    )
    research_boundary: str = Field(
        ...,
        description="Verbatim copy of zer0pa_materials_workbench.boundary.RESEARCH_BOUNDARY.",
    )
    run_id: str
    campaign_id: str
    candidate_id: str
    layer: Layer
    tool_adapter: ToolAdapter
    input_refs: list[str] = Field(default_factory=list)
    output: dict[str, Any] = Field(default_factory=dict)
    confidence: ConfidenceBlock = Field(default_factory=ConfidenceBlock)
    disagreement: DisagreementBlock = Field(default_factory=DisagreementBlock)
    falsifier: FalsifierBlock = Field(default_factory=FalsifierBlock)
    audit: AuditBlock
    rights: RightsBlock
    back_edges: list[BackEdge] = Field(default_factory=list)

    # ---- ID validators -----------------------------------------------------

    @field_validator("run_id")
    @classmethod
    def _vr(cls, v: str) -> str:
        return _validate_urn(v, _RUN_ID_RE, "run_id")

    @field_validator("campaign_id")
    @classmethod
    def _vc(cls, v: str) -> str:
        return _validate_urn(v, _CAMPAIGN_ID_RE, "campaign_id")

    @field_validator("candidate_id")
    @classmethod
    def _vd(cls, v: str) -> str:
        return _validate_urn(v, _CANDIDATE_ID_RE, "candidate_id")

    @field_validator("research_boundary")
    @classmethod
    def _vboundary(cls, v: str) -> str:
        if v != RESEARCH_BOUNDARY:
            raise ValueError(
                "research_boundary must equal RESEARCH_BOUNDARY exactly "
                "(see zer0pa_materials_workbench.boundary)."
            )
        return v

    @model_validator(mode="after")
    def _enforce_boundary(self) -> Envelope:
        """Run the boundary checker on the dict form before returning.

        ``assert_boundary`` walks every string in the artifact and rejects
        forbidden phrases (regulatory / clinical / ITAR). The PRD §Falsification
        wave includes "missing boundary block" — this validator triggers
        BoundaryError on that exact case via the dict serialisation.
        """
        # Use ``mode='json'`` so nested models flatten to plain dicts/lists/strs
        # — assert_boundary's walker is JSON-shape-aware only.
        as_dict = self.model_dump(mode="json")
        assert_boundary(as_dict)
        return self

    # ---- Canonicalisation --------------------------------------------------

    def canonical_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable dict with keys in the canonical order.

        The output's top-level keys appear in :data:`ENVELOPE_KEY_ORDER`
        order. Nested dicts are NOT re-ordered (their keys are validated by
        their own pydantic models and the canonical-bytes path uses
        ``OPT_SORT_KEYS`` which sorts at every level).
        """
        full = self.model_dump(mode="json")
        ordered: dict[str, Any] = {}
        for key in ENVELOPE_KEY_ORDER:
            if key in full:
                ordered[key] = full[key]
        # Tolerate extra keys we don't know about by trailing them, though
        # extra='forbid' means this branch is unreachable today.
        for key in full:
            if key not in ordered:
                ordered[key] = full[key]
        return ordered

    def canonical_bytes(self) -> bytes:
        """Return deterministic bytes for hashing (sorted keys, no whitespace)."""
        return orjson.dumps(self.canonical_dict(), option=orjson.OPT_SORT_KEYS)
