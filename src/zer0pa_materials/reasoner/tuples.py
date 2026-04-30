"""Self-bootstrapping reasoner tuple queue (PRD §Self-Bootstrapping Reasoner).

Every campaign emits tuples of the form::

    (input, proposed_action, simulation_or_experiment, output,
     falsifier, ground_truth, decision, audit_ref)

Tuples are written into ``reasoner_tuples.jsonl`` via
:meth:`zer0pa_materials.audit.log.AuditLog.append_event` so they're chained
into the audit ledger like everything else.

Reuse scope discipline
----------------------

The PRD §Self-Bootstrapping Reasoner says:

    If rights are unresolved, tuple ``reuse_scope`` is ``tenant_only``.

And §Falsification wave includes "private tuple reuse outside ``reuse_scope``".
:func:`enforce_reuse_scope_export` is the gate the falsification wave
exercises. It raises if a tuple is requested for export at a scope wider
than the tuple's own ``reuse_scope`` (e.g. asking for a ``tenant_only``
tuple in a ``shared_learning`` corpus).
"""

from __future__ import annotations

import datetime as _dt
import re
from typing import Any, Iterable, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from zer0pa_materials.audit.rights import (
    ReuseScope,
    RightsViolationError,
    is_reuse_scope_compatible,
)

__all__ = [
    "REASONER_TUPLE_ID_RE",
    "ProposedAction",
    "ReasonerTupleDecision",
    "ReasonerTuple",
    "enforce_reuse_scope_export",
    "is_reasoner_tuple_exportable",
]


REASONER_TUPLE_ID_RE = re.compile(r"^tuple:[A-Za-z0-9._\-:/]+$")
_CAMPAIGN_ID_RE = re.compile(r"^campaign:[A-Za-z0-9._\-:/]+$")
_CANDIDATE_ID_RE = re.compile(r"^candidate:[A-Za-z0-9._\-:/]+$")
_AUDIT_HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


ProposedAction = Literal[
    "run_l2",
    "run_dft",
    "run_neb",
    "run_md",
    "run_aimd",
    "fit_calphad",
    "compile_protocol",
    "reject",
    "queue_higher_fidelity",
    "promote",
    "hold",
]
ReasonerTupleDecision = Literal["promote", "queue_higher_fidelity", "reject", "hold"]


def _utc_now() -> str:
    return _dt.datetime.now(tz=_dt.timezone.utc).isoformat(timespec="microseconds")


class ReasonerTuple(BaseModel):
    """One row in ``reasoner_tuples.jsonl``."""

    model_config = ConfigDict(extra="forbid")

    tuple_id: str = Field(..., description="URN starting with 'tuple:'.")
    campaign_id: str = Field(..., description="URN starting with 'campaign:'.")
    candidate_id: str = Field(..., description="URN starting with 'candidate:'.")
    input: dict[str, Any] = Field(
        ..., description="Structure, composition, target property, prior context."
    )
    proposed_action: ProposedAction
    simulation_or_experiment: dict[str, Any] = Field(
        ..., description="Layer + adapter that ran (or will run) the action."
    )
    output: dict[str, Any] = Field(
        default_factory=dict,
        description="Property prediction, posterior, disagreement, artifact refs.",
    )
    falsifier: dict[str, Any] = Field(
        default_factory=dict, description="Falsifier status + items."
    )
    ground_truth: dict[str, Any] | None = Field(
        default=None, description="Filled at L1/lab-characterization time."
    )
    decision: ReasonerTupleDecision
    audit_ref: str = Field(
        ..., description="event_hash anchor in the audit ledger (sha256:<hex>)."
    )
    reuse_scope: ReuseScope = Field(
        default="tenant_only",
        description=(
            "Per PRD §Self-Bootstrapping Reasoner: 'If rights are unresolved, "
            "tuple reuse_scope is tenant_only.'"
        ),
    )
    recorded_at: str = Field(default_factory=_utc_now)

    @field_validator("tuple_id")
    @classmethod
    def _v_id(cls, v: str) -> str:
        if not REASONER_TUPLE_ID_RE.match(v):
            raise ValueError(f"tuple_id must match {REASONER_TUPLE_ID_RE.pattern!r}; got {v!r}")
        return v

    @field_validator("campaign_id")
    @classmethod
    def _v_campaign(cls, v: str) -> str:
        if not _CAMPAIGN_ID_RE.match(v):
            raise ValueError(f"campaign_id must match {_CAMPAIGN_ID_RE.pattern!r}; got {v!r}")
        return v

    @field_validator("candidate_id")
    @classmethod
    def _v_candidate(cls, v: str) -> str:
        if not _CANDIDATE_ID_RE.match(v):
            raise ValueError(f"candidate_id must match {_CANDIDATE_ID_RE.pattern!r}; got {v!r}")
        return v

    @field_validator("audit_ref")
    @classmethod
    def _v_audit_ref(cls, v: str) -> str:
        if not _AUDIT_HASH_RE.match(v):
            raise ValueError(f"audit_ref must be sha256:<hex>; got {v!r}")
        return v

    @field_validator("recorded_at")
    @classmethod
    def _v_recorded(cls, v: str) -> str:
        try:
            parsed = _dt.datetime.fromisoformat(v)
        except ValueError as exc:
            raise ValueError(f"recorded_at must be ISO-8601: {exc}") from exc
        if parsed.tzinfo is None:
            raise ValueError("recorded_at must include a timezone offset (UTC preferred).")
        return v


# ----------------------------------------------------------------------------
# Reuse-scope export enforcement
# ----------------------------------------------------------------------------


def is_reasoner_tuple_exportable(
    tup: ReasonerTuple,
    target_scope: ReuseScope,
) -> bool:
    """Return True if this tuple may be exported into a corpus at ``target_scope``.

    The rule from PRD §Self-Bootstrapping Reasoner:

    * tenant_only tuples → must remain tenant_only.
    * shared_learning tuples → may be in shared_learning or open_science
      corpora (but only if rights claim allows; we default to no).
    * open_science tuples → may be exported anywhere.

    Concretely: the tuple's own scope must be ``>=`` (in the lattice
    tenant_only < shared_learning < open_science) the corpus scope. We
    enforce ``tuple.reuse_scope == target_scope`` which is the strictest
    interpretation; a future opt-in can widen the rule via
    :func:`zer0pa_materials.audit.rights.is_reuse_scope_compatible`.
    """
    if tup.reuse_scope == "tenant_only":
        return target_scope == "tenant_only"
    if tup.reuse_scope == "shared_learning":
        return target_scope in ("shared_learning", "tenant_only")
    if tup.reuse_scope == "open_science":
        return True
    return False


def enforce_reuse_scope_export(
    tup: ReasonerTuple,
    target_scope: ReuseScope,
) -> None:
    """Raise :class:`RightsViolationError` if the tuple cannot be exported at the target scope.

    This is the falsification-wave gate "private tuple reuse outside
    ``reuse_scope``" (PRD §Falsification wave).
    """
    if not is_reasoner_tuple_exportable(tup, target_scope):
        raise RightsViolationError(
            f"reasoner tuple {tup.tuple_id} has reuse_scope={tup.reuse_scope!r}; "
            f"cannot be exported at target scope {target_scope!r}",
            envelope_scope=tup.reuse_scope,
        )


def filter_exportable_tuples(
    tuples: Iterable[ReasonerTuple],
    target_scope: ReuseScope,
) -> list[ReasonerTuple]:
    """Filter a stream of tuples to only those exportable at ``target_scope``."""
    return [t for t in tuples if is_reasoner_tuple_exportable(t, target_scope)]
