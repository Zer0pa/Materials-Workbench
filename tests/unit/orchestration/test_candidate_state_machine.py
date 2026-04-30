"""Test the per-candidate state machine."""

from __future__ import annotations

import pytest

from zer0pa_materials.orchestration.candidate_state import (
    CANDIDATE_TRANSITIONS,
    CandidateRecord,
    is_terminal_status,
)


def _rec() -> CandidateRecord:
    return CandidateRecord(candidate_id="candidate:test/c1")


def test_initial_status_is_proposed():
    assert _rec().status == "proposed"


def test_legal_transitions():
    for from_s, to_s in CANDIDATE_TRANSITIONS:
        rec = CandidateRecord(candidate_id="candidate:test/x", status=from_s)
        new = rec.transition_to(to_s)
        assert new.status == to_s


def test_illegal_transition_raises():
    rec = _rec()
    with pytest.raises(ValueError, match="illegal candidate transition"):
        rec.transition_to("promoted")


def test_terminal_status():
    for s in ("promoted", "rejected"):
        assert is_terminal_status(s)
    for s in ("proposed", "screened", "validated"):
        assert not is_terminal_status(s)


def test_attach_layer_envelope():
    rec = _rec()
    new = rec.attach_layer_envelope("L2", "audit:abc123")
    assert new.layer_audit_refs["L2"] == "audit:abc123"
    # Multiple layers stack.
    new2 = new.attach_layer_envelope("L1", "audit:def456")
    assert new2.layer_audit_refs["L2"] == "audit:abc123"
    assert new2.layer_audit_refs["L1"] == "audit:def456"


def test_rejection_records_reason():
    rec = _rec()
    rejected = rec.transition_to("rejected", rejection_reason="L2 hard_reject")
    assert rejected.status == "rejected"
    assert rejected.rejection_reason == "L2 hard_reject"


def test_higher_fidelity_request_records():
    rec = _rec().transition_to("screened")
    queued = rec.transition_to("queued_higher_fidelity", higher_fidelity_request="L1@HSE06")
    assert queued.higher_fidelity_request == "L1@HSE06"
    # Subsequent transition clears it.
    re_screened = queued.transition_to("screened")
    assert re_screened.higher_fidelity_request is None


def test_candidate_id_validation():
    with pytest.raises(ValueError):
        CandidateRecord(candidate_id="not-a-urn")


def test_terminal_status_on_promoted_record():
    rec = _rec().transition_to("screened").transition_to("validated").transition_to(
        "evidence_complete"
    ).transition_to("promoted")
    assert rec.is_terminal
