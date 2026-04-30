"""Decision log (PRD §Audit Trail And KG: ``decisions.jsonl``).

Each routing or architecture decision is recorded as a :class:`Decision`
row. Supersession is explicit: a new decision lists the IDs of the
decisions it supersedes, and ``back_edges`` lists the event_hashes that
motivated it. PRD §Acceptance Gates / Brain-functionality says:

    Decisions are recorded with rationale and supersession path.

Reading the supersession chain from any leaf decision gives the operator
the full history. :func:`reconstruct_supersession_chain` walks the chain
both forward and backward from any starting decision.
"""

from __future__ import annotations

import datetime as _dt
import re
from typing import Iterable, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

__all__ = [
    "DecisionMaker",
    "Decision",
    "reconstruct_supersession_chain",
    "DECISION_ID_RE",
]


DECISION_ID_RE = re.compile(r"^decision:[A-Za-z0-9._\-:/]+$")


DecisionMaker = Literal["lead", "subagent", "policy", "user"]


def _utc_now() -> str:
    return _dt.datetime.now(tz=_dt.timezone.utc).isoformat(timespec="microseconds")


class Decision(BaseModel):
    """A recorded routing / architecture decision."""

    model_config = ConfigDict(extra="forbid")

    decision_id: str = Field(..., description="URN starting with 'decision:'.")
    made_by: DecisionMaker = Field(..., description="Who made the decision.")
    context: str = Field(
        ..., min_length=1, description="Short description of the situation that prompted the decision."
    )
    options_considered: list[str] = Field(
        ..., min_length=1, description="The alternatives that were evaluated."
    )
    chosen: str = Field(..., min_length=1, description="The option selected.")
    rationale: str = Field(
        ..., min_length=1, description="Why ``chosen`` was selected over the alternatives."
    )
    supersedes: list[str] = Field(
        default_factory=list,
        description="Prior decision_ids this decision overrides.",
    )
    back_edges: list[str] = Field(
        default_factory=list,
        description="Audit event_hashes (from any audit category) that motivated this decision.",
    )
    made_at: str = Field(default_factory=_utc_now)

    @field_validator("decision_id")
    @classmethod
    def _v_id(cls, v: str) -> str:
        if not DECISION_ID_RE.match(v):
            raise ValueError(f"decision_id must match {DECISION_ID_RE.pattern!r}; got {v!r}")
        return v

    @field_validator("supersedes")
    @classmethod
    def _v_supersedes(cls, v: list[str]) -> list[str]:
        for ref in v:
            if not DECISION_ID_RE.match(ref):
                raise ValueError(
                    f"supersedes entry must match {DECISION_ID_RE.pattern!r}; got {ref!r}"
                )
        return v

    @field_validator("made_at")
    @classmethod
    def _v_made_at(cls, v: str) -> str:
        try:
            parsed = _dt.datetime.fromisoformat(v)
        except ValueError as exc:
            raise ValueError(f"made_at must be ISO-8601: {exc}") from exc
        if parsed.tzinfo is None:
            raise ValueError("made_at must include a timezone offset (UTC preferred).")
        return v


def reconstruct_supersession_chain(
    decisions: Iterable[Decision], starting_id: str
) -> list[Decision]:
    """Reconstruct the full supersession chain (oldest → newest) from a starting id.

    The starting id may be any member of the chain. The function walks
    backwards through ``supersedes`` edges to find the oldest member, then
    forward through reverse-``supersedes`` to the newest. Returns the chain
    in chronological order.

    If the starting id is not present, raises ``KeyError``.
    """
    by_id: dict[str, Decision] = {d.decision_id: d for d in decisions}
    if starting_id not in by_id:
        raise KeyError(f"unknown decision_id: {starting_id!r}")

    # Walk backwards through ``supersedes`` to find the oldest ancestor that
    # *is* in our index (we tolerate missing references — the chain may
    # cross boundaries).
    oldest_id = starting_id
    while True:
        cur = by_id[oldest_id]
        if not cur.supersedes:
            break
        # Walk to the first known supersedes entry.
        next_id = None
        for s in cur.supersedes:
            if s in by_id:
                next_id = s
                break
        if next_id is None:
            break
        oldest_id = next_id

    # Walk forward: find decisions whose ``supersedes`` lists include the
    # current id.
    chain: list[Decision] = [by_id[oldest_id]]
    while True:
        cur_id = chain[-1].decision_id
        successors = [
            d for d in by_id.values() if cur_id in d.supersedes
        ]
        if not successors:
            break
        # Pick the earliest successor by made_at.
        successors.sort(key=lambda d: d.made_at)
        chain.append(successors[0])

    return chain
