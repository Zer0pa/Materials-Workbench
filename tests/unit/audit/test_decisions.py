"""Tests for the decision log (A1 §Audit Trail And KG)."""

from __future__ import annotations

import datetime as _dt

import pytest

from zer0pa_materials_workbench.audit.decisions import (
    Decision,
    reconstruct_supersession_chain,
)
from zer0pa_materials_workbench.audit.log import AuditLog


def _now_iso() -> str:
    return _dt.datetime.now(tz=_dt.timezone.utc).isoformat(timespec="microseconds")


# ----------------------------------------------------------------------------
# Decision model
# ----------------------------------------------------------------------------


def test_decision_round_trip():
    d = Decision(
        decision_id="decision:l4-solver-default",
        made_by="lead",
        context="Pick default L4 phase-field solver",
        options_considered=["prisms_pf", "moose", "stub"],
        chosen="stub",
        rationale="No GPU available; emit schema-only stub.",
    )
    raw = d.model_dump_json()
    d2 = Decision.model_validate_json(raw)
    assert d2.chosen == "stub"
    assert d2.supersedes == []


def test_decision_rejects_bad_id():
    with pytest.raises(ValueError, match="decision_id must match"):
        Decision(
            decision_id="bad",
            made_by="lead",
            context="x",
            options_considered=["a"],
            chosen="a",
            rationale="x",
        )


def test_decision_rejects_empty_options():
    with pytest.raises(ValueError):
        Decision(
            decision_id="decision:test",
            made_by="lead",
            context="x",
            options_considered=[],  # min_length=1
            chosen="a",
            rationale="x",
        )


def test_decision_rejects_bad_supersedes_id():
    with pytest.raises(ValueError, match="supersedes entry"):
        Decision(
            decision_id="decision:test",
            made_by="lead",
            context="x",
            options_considered=["a"],
            chosen="a",
            rationale="x",
            supersedes=["not-a-decision-urn"],
        )


def test_decision_accepts_proper_supersedes():
    d = Decision(
        decision_id="decision:replacement",
        made_by="lead",
        context="x",
        options_considered=["a"],
        chosen="a",
        rationale="x",
        supersedes=["decision:original"],
    )
    assert d.supersedes == ["decision:original"]


def test_decision_back_edges_default_empty():
    d = Decision(
        decision_id="decision:test",
        made_by="lead",
        context="x",
        options_considered=["a"],
        chosen="a",
        rationale="x",
    )
    assert d.back_edges == []


def test_decision_made_by_must_be_canonical():
    with pytest.raises(ValueError):
        Decision(
            decision_id="decision:test",
            made_by="not-a-role",  # type: ignore[arg-type]
            context="x",
            options_considered=["a"],
            chosen="a",
            rationale="x",
        )


# ----------------------------------------------------------------------------
# Supersession chain reconstruction
# ----------------------------------------------------------------------------


def _make_decision(decision_id: str, supersedes: list[str], made_at: str) -> Decision:
    return Decision(
        decision_id=decision_id,
        made_by="lead",
        context="ctx",
        options_considered=["a", "b"],
        chosen="a",
        rationale="r",
        supersedes=supersedes,
        made_at=made_at,
    )


def test_supersession_chain_three_step():
    """A → B → C: starting at any of them recovers [A, B, C]."""
    t0 = "2026-04-30T01:00:00.000000+00:00"
    t1 = "2026-04-30T02:00:00.000000+00:00"
    t2 = "2026-04-30T03:00:00.000000+00:00"
    a = _make_decision("decision:a", [], t0)
    b = _make_decision("decision:b", ["decision:a"], t1)
    c = _make_decision("decision:c", ["decision:b"], t2)
    chain = reconstruct_supersession_chain([a, b, c], "decision:c")
    assert [d.decision_id for d in chain] == ["decision:a", "decision:b", "decision:c"]
    chain_from_b = reconstruct_supersession_chain([a, b, c], "decision:b")
    assert [d.decision_id for d in chain_from_b] == ["decision:a", "decision:b", "decision:c"]
    chain_from_a = reconstruct_supersession_chain([a, b, c], "decision:a")
    assert [d.decision_id for d in chain_from_a] == ["decision:a", "decision:b", "decision:c"]


def test_supersession_chain_singleton():
    t0 = "2026-04-30T01:00:00.000000+00:00"
    a = _make_decision("decision:lonely", [], t0)
    chain = reconstruct_supersession_chain([a], "decision:lonely")
    assert [d.decision_id for d in chain] == ["decision:lonely"]


def test_supersession_chain_unknown_starting_id():
    a = _make_decision("decision:a", [], "2026-04-30T01:00:00.000000+00:00")
    with pytest.raises(KeyError, match="unknown decision_id"):
        reconstruct_supersession_chain([a], "decision:does-not-exist")


def test_supersession_chain_with_orphan_supersedes_reference():
    """Tolerate a supersedes reference that is not in our index."""
    t0 = "2026-04-30T01:00:00.000000+00:00"
    a = _make_decision("decision:a", ["decision:from-other-corpus"], t0)
    chain = reconstruct_supersession_chain([a], "decision:a")
    # Should treat ``a`` as the oldest known and return it alone.
    assert [d.decision_id for d in chain] == ["decision:a"]


# ----------------------------------------------------------------------------
# Integration: decisions append into decisions.jsonl with chain integrity
# ----------------------------------------------------------------------------


def test_decision_appends_into_decisions_jsonl(tmp_path):
    log = AuditLog(tmp_path)
    d = Decision(
        decision_id="decision:test:integrate",
        made_by="lead",
        context="integration test",
        options_considered=["a"],
        chosen="a",
        rationale="r",
    )
    row = log.append_event("decisions", d.model_dump(mode="json"))
    assert row.payload["decision_id"] == d.decision_id
    assert log.validate_chain("decisions").ok


def test_supersession_via_audit_log(tmp_path):
    log = AuditLog(tmp_path)
    d1 = Decision(
        decision_id="decision:1",
        made_by="lead",
        context="initial",
        options_considered=["a"],
        chosen="a",
        rationale="r",
    )
    log.append_event("decisions", d1.model_dump(mode="json"))
    d2 = Decision(
        decision_id="decision:2",
        made_by="lead",
        context="revised",
        options_considered=["a", "b"],
        chosen="b",
        rationale="r",
        supersedes=["decision:1"],
    )
    log.append_event("decisions", d2.model_dump(mode="json"))
    rows = list(log.iter_rows("decisions"))
    decisions = [Decision.model_validate(r.payload) for r in rows]
    chain = reconstruct_supersession_chain(decisions, "decision:2")
    assert [d.decision_id for d in chain] == ["decision:1", "decision:2"]
