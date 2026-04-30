"""Source manifests and gated stubs (PRD §Deep Research Policy).

Every strategic lookup MUST emit a :class:`SourceManifest` recording where
the evidence came from and how it ties to a downstream decision. If the
lookup cannot complete (rate-limited, unverified license, missing creds),
the system MUST emit a :class:`BlockedSourceManifest` instead — the PRD
requires structured blocked results, never silent skips.

Both manifest types serialize into ``sources.jsonl`` via
:meth:`zer0pa_materials.audit.log.AuditLog.append_event`. Each row in the
JSONL ledger carries the chain wrapper (``prev_hash``, ``event_hash``,
``recorded_at``); the manifest payload is the row's ``payload`` dict.
"""

from __future__ import annotations

import datetime as _dt
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

__all__ = [
    "SourceManifest",
    "BlockedSourceManifest",
    "SourceType",
    "Redaction",
    "BlockerReason",
    "SOURCE_MANIFEST_ID_RE",
]


SourceType = Literal[
    "paper",
    "api",
    "doc",
    "model_card",
    "license",
    "dataset",
    "repo",
    "spec",
]
Redaction = Literal["none", "partial", "full"]
BlockerReason = Literal[
    "unavailable_credentials",
    "license_unverified",
    "unreachable",
    "rate_limited",
    "policy",
    "other",
]


SOURCE_MANIFEST_ID_RE = re.compile(r"^src:[A-Za-z0-9._\-:/]+$")


def _validate_source_id(v: str) -> str:
    if not SOURCE_MANIFEST_ID_RE.match(v):
        raise ValueError(
            f"source_manifest_id must match {SOURCE_MANIFEST_ID_RE.pattern!r}; got {v!r}"
        )
    return v


def _validate_iso_utc(v: str | _dt.datetime) -> str:
    if isinstance(v, _dt.datetime):
        if v.tzinfo is None:
            raise ValueError("datetime must include a timezone offset (UTC preferred).")
        return v.isoformat(timespec="microseconds")
    try:
        parsed = _dt.datetime.fromisoformat(v)
    except ValueError as exc:
        raise ValueError(f"timestamp must be ISO-8601: {exc}") from exc
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include a timezone offset (UTC preferred).")
    return v


class SourceManifest(BaseModel):
    """Source manifest for a successful lookup."""

    model_config = ConfigDict(extra="forbid")

    source_manifest_id: str = Field(..., description="URN starting with 'src:'.")
    source_type: SourceType = Field(..., description="Kind of source.")
    locator: str = Field(
        ..., min_length=1, description="DOI, URL, arXiv ID, HF repo, etc."
    )
    retrieval_date: str = Field(
        ..., description="ISO-8601 UTC timestamp with offset of when the source was retrieved."
    )
    license_spdx: str = Field(
        ...,
        min_length=1,
        description="SPDX expression, e.g. 'MIT', 'CC-BY-4.0', 'Apache-2.0 WITH LLVM-exception'.",
    )
    summary: str = Field(..., min_length=1, description="Short plain-English summary.")
    decision_impact: str = Field(
        ...,
        min_length=1,
        description="Which downstream decision/route this source supports.",
    )
    hash: str | None = Field(
        None,
        description="sha256:<hex> of canonical content if locally captured; None if remote-only.",
    )
    redaction: Redaction = Field(
        default="none",
        description="Redaction posture for cross-customer reuse.",
    )

    @field_validator("source_manifest_id")
    @classmethod
    def _v_id(cls, v: str) -> str:
        return _validate_source_id(v)

    @field_validator("retrieval_date")
    @classmethod
    def _v_retrieval(cls, v: str) -> str:
        return _validate_iso_utc(v)

    @field_validator("hash")
    @classmethod
    def _v_hash(cls, v: str | None) -> str | None:
        if v is None:
            return None
        if not re.match(r"^sha256:[0-9a-f]{64}$", v):
            raise ValueError(f"hash must be sha256:<hex>; got {v!r}")
        return v


class BlockedSourceManifest(BaseModel):
    """Source manifest for a blocked / failed lookup.

    PRD §Deep Research Policy: "If a lookup cannot be completed, implement
    a gated stub and record a blocked source manifest. Do not silently
    assume."
    """

    model_config = ConfigDict(extra="forbid")

    source_manifest_id: str = Field(..., description="URN starting with 'src:'.")
    attempted_locator: str = Field(
        ..., min_length=1, description="What we tried to fetch (DOI, URL, etc)."
    )
    blocker_reason: BlockerReason = Field(..., description="Why we couldn't complete.")
    blocker_detail: str = Field(
        ..., min_length=1, description="Human-readable diagnostic; pinned to operator."
    )
    retry_strategy: str = Field(
        ...,
        min_length=1,
        description=(
            "Concrete next step for the operator: 'request UMA HF org access', "
            "'add Thermo-Calc license', 'wait 1h for arXiv rate limit'."
        ),
    )
    blocked_at: str = Field(
        default_factory=lambda: _dt.datetime.now(tz=_dt.timezone.utc).isoformat(
            timespec="microseconds"
        ),
        description="ISO-8601 UTC timestamp with offset for when blocking was recorded.",
    )

    @field_validator("source_manifest_id")
    @classmethod
    def _v_id(cls, v: str) -> str:
        return _validate_source_id(v)

    @field_validator("blocked_at")
    @classmethod
    def _v_blocked_at(cls, v: str) -> str:
        return _validate_iso_utc(v)
