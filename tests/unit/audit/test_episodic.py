"""Tests for episodic memory / resume (A1 §Brain-functionality).

PRD: 'A fresh agent can reconstruct the project from repo artifacts without
chat history.'
"""

from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path

import pytest

from zer0pa_materials.audit.episodic import (
    CampaignState,
    StateSnapshot,
    reconstruct_from_repo,
    snapshot_state,
)
from zer0pa_materials.audit.kg import KGNodeType, MaterialsKG
from zer0pa_materials.audit.log import AuditLog


def _now_iso() -> str:
    return _dt.datetime.now(tz=_dt.timezone.utc).isoformat(timespec="microseconds")


# ----------------------------------------------------------------------------
# snapshot_state
# ----------------------------------------------------------------------------


def test_snapshot_empty_audit_dir(tmp_path):
    audit_dir = tmp_path / "audit"
    audit_dir.mkdir()
    kg_path = audit_dir / "kg.sqlite"
    snap = snapshot_state(audit_dir, kg_path)
    assert snap.kg_node_count == 0
    assert snap.kg_edge_count == 0
    assert all(c.row_count == 0 for c in snap.categories)
    assert all(c.chain_ok for c in snap.categories)


def test_snapshot_after_some_events(tmp_path):
    audit_dir = tmp_path / "audit"
    log = AuditLog(audit_dir)
    log.append_event("decisions", {"decision_id": "decision:1", "context": "x"})
    log.append_event("decisions", {"decision_id": "decision:2", "context": "y"})
    log.append_event("falsifiers", {"name": "x", "status": "pass"})
    snap = snapshot_state(audit_dir, audit_dir / "kg.sqlite")
    by_cat = {c.category: c for c in snap.categories}
    assert by_cat["decisions"].row_count == 2
    assert by_cat["falsifiers"].row_count == 1
    assert by_cat["events"].row_count == 0


def test_snapshot_open_falsifiers_includes_fail_and_blocked(tmp_path):
    audit_dir = tmp_path / "audit"
    log = AuditLog(audit_dir)
    log.append_event("falsifiers", {"name": "g1", "status": "pass"})
    log.append_event("falsifiers", {"name": "g2", "status": "fail", "rationale": "exceeded"})
    log.append_event("falsifiers", {"name": "g3", "status": "blocked", "rationale": "no creds"})
    snap = snapshot_state(audit_dir, audit_dir / "kg.sqlite")
    open_names = {f["name"] for f in snap.open_falsifiers}
    assert open_names == {"g2", "g3"}


def test_snapshot_pending_decisions_excludes_superseded(tmp_path):
    audit_dir = tmp_path / "audit"
    log = AuditLog(audit_dir)
    log.append_event(
        "decisions",
        {"decision_id": "decision:1", "context": "first", "supersedes": []},
    )
    log.append_event(
        "decisions",
        {"decision_id": "decision:2", "context": "second", "supersedes": ["decision:1"]},
    )
    snap = snapshot_state(audit_dir, audit_dir / "kg.sqlite")
    pending_ids = {d["decision_id"] for d in snap.pending_decisions}
    assert pending_ids == {"decision:2"}


def test_snapshot_holding_tuples(tmp_path):
    audit_dir = tmp_path / "audit"
    log = AuditLog(audit_dir)
    log.append_event(
        "reasoner_tuples",
        {"tuple_id": "tuple:1", "candidate_id": "candidate:a", "decision": "promote"},
    )
    log.append_event(
        "reasoner_tuples",
        {"tuple_id": "tuple:2", "candidate_id": "candidate:b", "decision": "hold"},
    )
    log.append_event(
        "reasoner_tuples",
        {
            "tuple_id": "tuple:3",
            "candidate_id": "candidate:c",
            "decision": "queue_higher_fidelity",
        },
    )
    snap = snapshot_state(audit_dir, audit_dir / "kg.sqlite")
    holding_ids = {t["tuple_id"] for t in snap.holding_reasoner_tuples}
    assert holding_ids == {"tuple:2", "tuple:3"}


def test_snapshot_records_kg_counts(tmp_path):
    audit_dir = tmp_path / "audit"
    audit_dir.mkdir()
    kg_path = audit_dir / "kg.sqlite"
    kg = MaterialsKG(kg_path)
    try:
        kg.add_node("n1", KGNodeType.CandidateMaterial, run_id="run:t")
        kg.add_node("n2", KGNodeType.SimulationJob, run_id="run:t")
    finally:
        kg.close()
    snap = snapshot_state(audit_dir, kg_path)
    assert snap.kg_node_count == 2
    assert snap.kg_node_count_by_type["CandidateMaterial"] == 1
    assert snap.kg_node_count_by_type["SimulationJob"] == 1


def test_snapshot_detects_chain_corruption(tmp_path):
    audit_dir = tmp_path / "audit"
    log = AuditLog(audit_dir)
    log.append_event("events", {"i": 1})
    log.append_event("events", {"i": 2})
    target = log.path_for("events")
    raw = target.read_bytes().splitlines()
    # Tamper with first row.
    import orjson
    obj = orjson.loads(raw[0])
    obj["payload"]["i"] = 999
    raw[0] = orjson.dumps(obj, option=orjson.OPT_SORT_KEYS)
    target.write_bytes(b"\n".join(raw) + b"\n")
    snap = snapshot_state(audit_dir, audit_dir / "kg.sqlite")
    by_cat = {c.category: c for c in snap.categories}
    assert not by_cat["events"].chain_ok
    assert len(by_cat["events"].chain_errors) >= 1


# ----------------------------------------------------------------------------
# reconstruct_from_repo
# ----------------------------------------------------------------------------


def test_reconstruct_clean_state(tmp_path):
    """A clean state should yield 'all clean' next_actions."""
    repo = tmp_path / "repo"
    audit = repo / "audit" / "runtime"
    audit.mkdir(parents=True)
    state = reconstruct_from_repo(repo)
    assert isinstance(state, CampaignState)
    assert state.snapshot.kg_node_count == 0
    assert any("All chains valid" in a for a in state.next_actions)


def test_reconstruct_surfaces_open_falsifiers(tmp_path):
    """Drop a synthetic event sequence and reconstruct without chat history."""
    repo = tmp_path / "repo"
    audit = repo / "audit" / "runtime"
    audit.mkdir(parents=True)
    log = AuditLog(audit)
    log.append_event(
        "falsifiers",
        {
            "name": "l2.energy_disagreement_promote",
            "status": "fail",
            "rationale": "DPA/MACE differ by 80 meV/atom",
        },
    )
    state = reconstruct_from_repo(repo)
    assert any(
        "OPEN FALSIFIER" in a and "l2.energy_disagreement_promote" in a
        for a in state.next_actions
    )


def test_reconstruct_surfaces_pending_decisions(tmp_path):
    repo = tmp_path / "repo"
    audit = repo / "audit" / "runtime"
    audit.mkdir(parents=True)
    log = AuditLog(audit)
    log.append_event(
        "decisions",
        {
            "decision_id": "decision:l2-routing",
            "context": "Pick model after DPA/MACE disagreement",
            "supersedes": [],
        },
    )
    state = reconstruct_from_repo(repo)
    assert any(
        "PENDING DECISION" in a and "decision:l2-routing" in a
        for a in state.next_actions
    )


def test_reconstruct_surfaces_chain_integrity_problems(tmp_path):
    """A corrupt chain must be flagged as the first thing to fix."""
    repo = tmp_path / "repo"
    audit = repo / "audit" / "runtime"
    audit.mkdir(parents=True)
    log = AuditLog(audit)
    log.append_event("events", {"i": 1})
    log.append_event("events", {"i": 2})
    target = log.path_for("events")
    import orjson
    raw = target.read_bytes().splitlines()
    obj = orjson.loads(raw[0])
    obj["payload"]["i"] = 999
    raw[0] = orjson.dumps(obj, option=orjson.OPT_SORT_KEYS)
    target.write_bytes(b"\n".join(raw) + b"\n")
    state = reconstruct_from_repo(repo)
    assert any("AUDIT CHAIN INTEGRITY" in a for a in state.next_actions)


def test_reconstruct_does_not_require_chat_history(tmp_path):
    """The brain-functionality gate. A bare repo + audit dir is enough."""
    repo = tmp_path / "repo"
    audit = repo / "audit" / "runtime"
    audit.mkdir(parents=True)
    log = AuditLog(audit)
    log.append_event("events", {"phase": "A0"})
    log.append_event("events", {"phase": "A1"})
    log.append_event(
        "decisions",
        {
            "decision_id": "decision:k",
            "context": "x",
            "supersedes": [],
        },
    )
    log.append_event(
        "reasoner_tuples",
        {
            "tuple_id": "tuple:queued",
            "candidate_id": "candidate:llzo",
            "decision": "queue_higher_fidelity",
        },
    )
    # Now reconstruct from JUST the repo path.
    state = reconstruct_from_repo(repo)
    serialised = state.model_dump_json()
    # A fresh agent can read this JSON and pick up:
    parsed = json.loads(serialised)
    assert "next_actions" in parsed
    assert "snapshot" in parsed
    assert parsed["snapshot"]["kg_node_count"] == 0
    # The actions list contains the pending decision and the holding tuple.
    actions_text = " ".join(parsed["next_actions"])
    assert "decision:k" in actions_text
    assert "tuple:queued" in actions_text


def test_reconstruct_tolerates_missing_kg_db(tmp_path):
    """Should NOT crash if the KG SQLite file isn't present."""
    repo = tmp_path / "repo"
    audit = repo / "audit" / "runtime"
    audit.mkdir(parents=True)
    state = reconstruct_from_repo(repo)
    assert state.snapshot.kg_node_count == 0
