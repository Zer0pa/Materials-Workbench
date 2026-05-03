"""Falsifier item model — the unit row of the envelope's ``falsifier.items``.

A falsifier is a *named threshold check* with a recorded actual value, a
status, and a back-reference to the artifact / event / source that supplies
evidence. The PRD's per-layer gate sections (§Layer-Specific Falsifiers And
Gates) enumerate the canonical thresholds; layer-output schemas in
``layer_outputs.py`` produce the items at the moment they are computed.

Status semantics:

* ``pass`` — the actual value satisfies the threshold; the gate let the
  candidate through.
* ``fail`` — actual value violated the threshold; the candidate is rejected
  unless an explicit override is logged.
* ``blocked`` — the check could not run (e.g., dependency unavailable,
  credentials missing, source manifest gated). The PRD requires structured
  blocked results, never silent skips (§Acceptance Gates / Engineering).
* ``inconclusive`` — the check ran but the evidence did not resolve the
  threshold either way (e.g., posterior straddles the cutoff). The
  reasoner/L7 layer is responsible for resolving this state.

We intentionally do NOT promote ``fail`` to an exception here — rejecting
on falsifier failure is a routing decision owned by the orchestration layer
(L7 §Layer Contracts). This module's only job is to model the row.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

__all__ = ["FalsifierItem", "FalsifierStatus"]

FalsifierStatus = Literal["pass", "fail", "blocked", "inconclusive"]


class FalsifierItem(BaseModel):
    """One row in ``Envelope.falsifier.items``.

    Required identification:

    * ``name`` — stable identifier of the gate, e.g.
      ``"l2.energy_disagreement_promote"``. Names are stable across runs
      so the audit ledger can group equivalent failures.

    Required evidence:

    * ``threshold`` — the value to compare against. A string captures the
      relational form (``"<= 25 meV/atom"``) without coupling the model to
      a specific numeric type.
    * ``actual`` — the measured value, of any JSON-serialisable type.
    * ``status`` — pass/fail/blocked/inconclusive.

    Optional context:

    * ``evidence_ref`` — URN or URI pointing to the artifact / event / log
      line that records the evidence.
    * ``rationale`` — short string explaining why a check returned
      ``inconclusive`` or ``blocked``. Required for non-pass-non-fail
      statuses by the audit gate (enforced upstream, not here).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(
        ...,
        min_length=1,
        description="Stable identifier of the falsifier gate (e.g. 'l1.h2_vqe_vs_fci').",
    )
    threshold: str = Field(
        ...,
        description="Threshold expression, e.g. '<= 1e-3 Ha' or '> 0.05 eV/Å'.",
    )
    actual: Any = Field(
        ...,
        description="Measured value; JSON-serialisable scalar/list/object.",
    )
    status: FalsifierStatus = Field(
        ...,
        description="Outcome of comparing actual against threshold.",
    )
    evidence_ref: str | None = Field(
        None,
        description="URN/URI to artifact, event, or source manifest that supports the result.",
    )
    rationale: str | None = Field(
        None,
        description="Short rationale; required for blocked/inconclusive (enforced upstream).",
    )
