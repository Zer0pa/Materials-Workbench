"""Per-candidate state machine.

Each candidate produced by L6 traverses a state machine that mirrors the
PRD §Layer Contracts dependency order:

    proposed → screened → validated → evidence_complete → {promoted | rejected | queued_higher_fidelity}

Transitions:

* ``proposed`` → ``screened``: L2 ensemble emitted a routing decision of
  ``promote`` or ``queue_dft``. ``hard_reject`` jumps to ``rejected``.
* ``screened`` → ``validated``: L1 DFT validation completed within publication
  convergence (≤ 5 meV/atom convergence delta) or screening (< 50 meV/atom).
* ``validated`` → ``evidence_complete``: ionic-transport service produced the
  full battery evidence chain (or thermoelectric sidecar produced ZT).
* ``evidence_complete`` → ``promoted``: AcceptanceGate clears.
* Any state may transition to ``rejected`` if a hard-reject falsifier triggers.
* ``queued_higher_fidelity`` is reachable from ``screened`` or ``validated``
  when disagreement gates require an additional fidelity (e.g. AIMD vs MLIP-MD
  disagreement > 0.5 dex).

The record itself is immutable from the campaign's point of view; transitions
write a new ``CandidateRecord`` and the campaign keeps the latest by
``candidate_id``. Full history lives in the audit log (one ``decisions.jsonl``
row per transition).
"""

from __future__ import annotations

import datetime as _dt
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

__all__ = [
    "CandidateStatus",
    "CandidateRecord",
    "CANDIDATE_TRANSITIONS",
    "is_terminal_status",
]


CandidateStatus = Literal[
    "proposed",
    "screened",
    "validated",
    "evidence_complete",
    "promoted",
    "rejected",
    "queued_higher_fidelity",
]


# Allowed transitions. Each tuple is (from_status, to_status).
CANDIDATE_TRANSITIONS: frozenset[tuple[CandidateStatus, CandidateStatus]] = frozenset(
    {
        ("proposed", "screened"),
        ("proposed", "rejected"),
        ("screened", "validated"),
        ("screened", "rejected"),
        ("screened", "queued_higher_fidelity"),
        ("validated", "evidence_complete"),
        ("validated", "rejected"),
        ("validated", "queued_higher_fidelity"),
        ("evidence_complete", "promoted"),
        ("evidence_complete", "rejected"),
        ("queued_higher_fidelity", "screened"),
        ("queued_higher_fidelity", "validated"),
        ("queued_higher_fidelity", "rejected"),
    }
)


_TERMINAL: frozenset[CandidateStatus] = frozenset({"promoted", "rejected"})


def is_terminal_status(status: CandidateStatus) -> bool:
    """Return True if ``status`` is terminal (no further transitions allowed)."""
    return status in _TERMINAL


_CANDIDATE_ID_RE = re.compile(r"^candidate:[A-Za-z0-9._\-:/]+$")


def _utc_now() -> str:
    return _dt.datetime.now(tz=_dt.timezone.utc).isoformat(timespec="microseconds")


class CandidateRecord(BaseModel):
    """One candidate's current state inside a campaign.

    The record carries the audit-record IDs that produced the latest envelope
    at each layer so the AcceptanceGate can verify provenance from the audit
    log. ``layer_audit_refs`` keys are layer names (``"L6"``, ``"L2"``,
    ``"L1"``, ``"L1.5"``, ``"ionic"``, etc.).
    """

    model_config = ConfigDict(extra="forbid")

    candidate_id: str = Field(..., description="URN starting with 'candidate:'.")
    status: CandidateStatus = Field(default="proposed")
    structure_hash: str = Field(
        default="sha256:none",
        description=(
            "sha256:<hex> of the canonical structure. 'sha256:none' for pre-structure "
            "candidates whose structure is not yet realised."
        ),
    )
    proposed_action: str = Field(
        default="propose_candidate",
        description="Most recent reasoner-tuple proposed_action.",
    )
    layer_audit_refs: dict[str, str] = Field(
        default_factory=dict,
        description="Map of layer name -> audit_record_id for the latest envelope at that layer.",
    )
    last_decision_id: str | None = Field(
        default=None,
        description="decision_id of the most-recent transition (or None at proposal).",
    )
    rejection_reason: str | None = Field(
        default=None,
        description="If status == 'rejected', the human-readable reason.",
    )
    higher_fidelity_request: str | None = Field(
        default=None,
        description=(
            "If status == 'queued_higher_fidelity', the layer/fidelity requested "
            "(e.g. 'L1@hybrid_functional', 'ionic@aimd')."
        ),
    )
    updated_at: str = Field(default_factory=_utc_now)

    @field_validator("candidate_id")
    @classmethod
    def _v_candidate(cls, v: str) -> str:
        if not _CANDIDATE_ID_RE.match(v):
            raise ValueError(
                f"candidate_id must match {_CANDIDATE_ID_RE.pattern!r}; got {v!r}"
            )
        return v

    def transition_to(
        self,
        next_status: CandidateStatus,
        *,
        decision_id: str | None = None,
        rejection_reason: str | None = None,
        higher_fidelity_request: str | None = None,
    ) -> "CandidateRecord":
        """Return a new record advanced to ``next_status``.

        Raises ``ValueError`` if the transition is not in
        :data:`CANDIDATE_TRANSITIONS`.
        """
        edge: tuple[CandidateStatus, CandidateStatus] = (self.status, next_status)
        if edge not in CANDIDATE_TRANSITIONS:
            raise ValueError(
                f"illegal candidate transition {self.status!r} -> {next_status!r}"
            )
        return self.model_copy(
            update={
                "status": next_status,
                "last_decision_id": decision_id,
                "rejection_reason": rejection_reason if next_status == "rejected" else self.rejection_reason,
                "higher_fidelity_request": higher_fidelity_request
                if next_status == "queued_higher_fidelity"
                else None,
                "updated_at": _utc_now(),
            }
        )

    def attach_layer_envelope(
        self,
        layer: str,
        audit_record_id: str,
    ) -> "CandidateRecord":
        """Return a new record with the layer's audit_record_id pinned."""
        new_refs = dict(self.layer_audit_refs)
        new_refs[layer] = audit_record_id
        return self.model_copy(update={"layer_audit_refs": new_refs, "updated_at": _utc_now()})

    @property
    def is_terminal(self) -> bool:
        return is_terminal_status(self.status)
