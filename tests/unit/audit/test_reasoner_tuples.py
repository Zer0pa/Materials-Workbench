"""Tests for the self-bootstrapping reasoner tuple queue (A1 §Self-Bootstrapping Reasoner)."""

from __future__ import annotations

import pytest

from zer0pa_materials_workbench.audit.log import AuditLog
from zer0pa_materials_workbench.audit.rights import RightsViolationError
from zer0pa_materials_workbench.reasoner.tuples import (
    ReasonerTuple,
    enforce_reuse_scope_export,
    filter_exportable_tuples,
    is_reasoner_tuple_exportable,
)


def _make_tuple(
    tuple_id: str,
    reuse_scope: str = "tenant_only",
    decision: str = "queue_higher_fidelity",
) -> ReasonerTuple:
    return ReasonerTuple(
        tuple_id=tuple_id,
        campaign_id="campaign:test",
        candidate_id="candidate:test",
        input={"formula": "LiBO2"},
        proposed_action="run_l2",
        simulation_or_experiment={"layer": "L2", "adapter": "MaceMpCalculatorAdapter"},
        output={},
        falsifier={"status": "pass", "items": []},
        decision=decision,  # type: ignore[arg-type]
        audit_ref="sha256:" + "a" * 64,
        reuse_scope=reuse_scope,  # type: ignore[arg-type]
    )


# ----------------------------------------------------------------------------
# Model
# ----------------------------------------------------------------------------


def test_reasoner_tuple_round_trip():
    tup = _make_tuple("tuple:r1")
    raw = tup.model_dump_json()
    tup2 = ReasonerTuple.model_validate_json(raw)
    assert tup2.tuple_id == "tuple:r1"
    assert tup2.reuse_scope == "tenant_only"


def test_reasoner_tuple_rejects_bad_id():
    with pytest.raises(ValueError, match="tuple_id must match"):
        _make_tuple("not-a-urn")


def test_reasoner_tuple_rejects_bad_audit_ref():
    with pytest.raises(ValueError, match="audit_ref"):
        ReasonerTuple(
            tuple_id="tuple:r1",
            campaign_id="campaign:t",
            candidate_id="candidate:t",
            input={},
            proposed_action="run_l2",
            simulation_or_experiment={},
            decision="hold",
            audit_ref="bad-ref",
        )


def test_reasoner_tuple_default_reuse_scope_is_tenant_only():
    """Per PRD: 'If rights are unresolved, tuple reuse_scope is tenant_only.'"""
    tup = ReasonerTuple(
        tuple_id="tuple:default-scope",
        campaign_id="campaign:t",
        candidate_id="candidate:t",
        input={},
        proposed_action="run_l2",
        simulation_or_experiment={},
        decision="hold",
        audit_ref="sha256:" + "a" * 64,
    )
    assert tup.reuse_scope == "tenant_only"


def test_reasoner_tuple_rejects_invalid_proposed_action():
    with pytest.raises(ValueError):
        ReasonerTuple(
            tuple_id="tuple:t",
            campaign_id="campaign:t",
            candidate_id="candidate:t",
            input={},
            proposed_action="not-an-action",  # type: ignore[arg-type]
            simulation_or_experiment={},
            decision="hold",
            audit_ref="sha256:" + "a" * 64,
        )


# ----------------------------------------------------------------------------
# is_reasoner_tuple_exportable
# ----------------------------------------------------------------------------


def test_tenant_only_tuple_only_exports_to_tenant_only():
    tup = _make_tuple("tuple:t1", reuse_scope="tenant_only")
    assert is_reasoner_tuple_exportable(tup, "tenant_only")
    assert not is_reasoner_tuple_exportable(tup, "shared_learning")
    assert not is_reasoner_tuple_exportable(tup, "open_science")


def test_shared_learning_tuple_exports_to_shared_or_tenant():
    tup = _make_tuple("tuple:s1", reuse_scope="shared_learning")
    assert is_reasoner_tuple_exportable(tup, "shared_learning")
    assert is_reasoner_tuple_exportable(tup, "tenant_only")
    assert not is_reasoner_tuple_exportable(tup, "open_science")


def test_open_science_tuple_exports_anywhere():
    tup = _make_tuple("tuple:os1", reuse_scope="open_science")
    assert is_reasoner_tuple_exportable(tup, "tenant_only")
    assert is_reasoner_tuple_exportable(tup, "shared_learning")
    assert is_reasoner_tuple_exportable(tup, "open_science")


# ----------------------------------------------------------------------------
# enforce_reuse_scope_export — the falsification gate
# ----------------------------------------------------------------------------


def test_enforce_passes_when_compatible():
    tup = _make_tuple("tuple:passes", reuse_scope="tenant_only")
    enforce_reuse_scope_export(tup, "tenant_only")  # no raise


def test_enforce_raises_for_private_tuple_in_open_corpus():
    """PRD §Falsification wave: 'private tuple reuse outside reuse_scope'."""
    tup = _make_tuple("tuple:private", reuse_scope="tenant_only")
    with pytest.raises(RightsViolationError, match="cannot be exported"):
        enforce_reuse_scope_export(tup, "open_science")


def test_enforce_raises_for_shared_tuple_in_open_corpus():
    tup = _make_tuple("tuple:shared", reuse_scope="shared_learning")
    with pytest.raises(RightsViolationError):
        enforce_reuse_scope_export(tup, "open_science")


# ----------------------------------------------------------------------------
# filter_exportable_tuples
# ----------------------------------------------------------------------------


def test_filter_exportable_tuples_with_mixed_scopes():
    a = _make_tuple("tuple:a", reuse_scope="tenant_only")
    b = _make_tuple("tuple:b", reuse_scope="shared_learning")
    c = _make_tuple("tuple:c", reuse_scope="open_science")
    survivors = filter_exportable_tuples([a, b, c], "shared_learning")
    survivor_ids = {t.tuple_id for t in survivors}
    assert survivor_ids == {"tuple:b", "tuple:c"}


# ----------------------------------------------------------------------------
# Integration: tuples appended into reasoner_tuples.jsonl
# ----------------------------------------------------------------------------


def test_reasoner_tuple_appends_into_jsonl(tmp_path):
    log = AuditLog(tmp_path)
    tup = _make_tuple("tuple:integrate")
    log.append_event("reasoner_tuples", tup.model_dump(mode="json"))
    rows = list(log.iter_rows("reasoner_tuples"))
    assert len(rows) == 1
    assert rows[0].payload["tuple_id"] == "tuple:integrate"
    assert log.validate_chain("reasoner_tuples").ok


def test_export_time_enforcement_filters_tenant_only(tmp_path):
    """Round-trip: write tuples into the chain, then enforce export gate."""
    log = AuditLog(tmp_path)
    log.append_event(
        "reasoner_tuples",
        _make_tuple("tuple:tenant", reuse_scope="tenant_only").model_dump(mode="json"),
    )
    log.append_event(
        "reasoner_tuples",
        _make_tuple("tuple:shared", reuse_scope="shared_learning").model_dump(mode="json"),
    )
    rows = list(log.iter_rows("reasoner_tuples"))
    tuples = [ReasonerTuple.model_validate(r.payload) for r in rows]
    # Try to export at open_science: tenant tuple must raise; shared must raise too.
    for tup in tuples:
        with pytest.raises(RightsViolationError):
            enforce_reuse_scope_export(tup, "open_science")


def test_write_time_check_via_default_scope():
    """The default scope is tenant_only, so a tuple constructed without an
    explicit scope is a private tuple. Exporting it to anywhere but tenant_only
    must raise."""
    tup = ReasonerTuple(
        tuple_id="tuple:default",
        campaign_id="campaign:t",
        candidate_id="candidate:t",
        input={},
        proposed_action="run_l2",
        simulation_or_experiment={},
        decision="hold",
        audit_ref="sha256:" + "a" * 64,
        # reuse_scope omitted — defaults to tenant_only
    )
    with pytest.raises(RightsViolationError):
        enforce_reuse_scope_export(tup, "shared_learning")
