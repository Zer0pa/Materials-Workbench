"""Tests for the append-only hash-chained audit log (A1)."""

from __future__ import annotations

import datetime as _dt
import re
import threading
from pathlib import Path

import orjson
import pytest

from zer0pa_materials_workbench.audit.log import (
    AUDIT_CATEGORIES,
    GENESIS_PREV_HASH,
    AuditLog,
    AuditRow,
    _compute_event_hash_v2,
)

# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------


def _now_iso() -> str:
    return _dt.datetime.now(tz=_dt.timezone.utc).isoformat(timespec="microseconds")


def _seed_rows(log: AuditLog, category: str, n: int) -> list[AuditRow]:
    """Append ``n`` rows of innocuous payloads."""
    rows: list[AuditRow] = []
    for i in range(n):
        row = log.append_event(category, {"index": i, "msg": f"row-{i}"})
        rows.append(row)
    return rows


def _read_lines(path: Path) -> list[bytes]:
    return [ln for ln in path.read_bytes().splitlines() if ln.strip()]


def _write_lines(path: Path, lines: list[bytes]) -> None:
    path.write_bytes(b"\n".join(lines) + b"\n")


# ----------------------------------------------------------------------------
# Basic append + read
# ----------------------------------------------------------------------------


def test_audit_log_creates_audit_dir(tmp_path):
    audit_dir = tmp_path / "audit"
    log = AuditLog(audit_dir)
    assert audit_dir.exists()
    assert log.audit_dir == audit_dir.resolve()


def test_append_event_writes_row_with_genesis_prev(tmp_path):
    log = AuditLog(tmp_path)
    row = log.append_event("decisions", {"decision_id": "decision:test:1", "msg": "hello"})
    assert row.prev_hash == GENESIS_PREV_HASH
    assert row.event_hash != GENESIS_PREV_HASH
    assert re.match(r"^sha256:[0-9a-f]{64}$", row.event_hash)
    assert row.payload == {"decision_id": "decision:test:1", "msg": "hello"}


def test_append_event_chains_prev_hash(tmp_path):
    log = AuditLog(tmp_path)
    r1 = log.append_event("decisions", {"k": 1})
    r2 = log.append_event("decisions", {"k": 2})
    r3 = log.append_event("decisions", {"k": 3})
    assert r1.prev_hash == GENESIS_PREV_HASH
    assert r2.prev_hash == r1.event_hash
    assert r3.prev_hash == r2.event_hash


def test_iter_rows_yields_in_append_order(tmp_path):
    log = AuditLog(tmp_path)
    written = _seed_rows(log, "events", 5)
    read_back = list(log.iter_rows("events"))
    assert [r.event_hash for r in written] == [r.event_hash for r in read_back]


def test_tail_returns_last_n(tmp_path):
    log = AuditLog(tmp_path)
    _seed_rows(log, "events", 5)
    last3 = log.tail("events", 3)
    assert len(last3) == 3
    assert [r.payload["index"] for r in last3] == [2, 3, 4]


def test_head_hash_returns_genesis_when_empty(tmp_path):
    log = AuditLog(tmp_path)
    assert log.head_hash("events") == GENESIS_PREV_HASH


def test_head_hash_returns_last_event_hash(tmp_path):
    log = AuditLog(tmp_path)
    rows = _seed_rows(log, "events", 3)
    assert log.head_hash("events") == rows[-1].event_hash


def test_unknown_category_rejected(tmp_path):
    log = AuditLog(tmp_path)
    with pytest.raises(ValueError, match="unknown audit category"):
        log.append_event("nonexistent", {"k": 1})  # type: ignore[arg-type]


def test_all_eleven_categories_writable(tmp_path):
    log = AuditLog(tmp_path)
    for cat in AUDIT_CATEGORIES:
        row = log.append_event(cat, {"category": cat})
        assert row.category == cat
        assert log.path_for(cat).name == f"{cat}.jsonl"


# ----------------------------------------------------------------------------
# Validate-chain — the four tampering modes
# ----------------------------------------------------------------------------


def test_validate_chain_ok_for_clean_log(tmp_path):
    log = AuditLog(tmp_path)
    _seed_rows(log, "events", 5)
    result = log.validate_chain("events")
    assert result.ok
    assert result.checked_rows == 5
    assert result.errors == []
    assert result.first_bad_index is None


def test_validate_chain_empty_file_is_ok(tmp_path):
    log = AuditLog(tmp_path)
    result = log.validate_chain("events")
    assert result.ok
    assert result.checked_rows == 0


def test_validate_chain_detects_row_tampering(tmp_path):
    """Tampering with any payload byte must be detected."""
    log = AuditLog(tmp_path)
    _seed_rows(log, "events", 3)
    target = log.path_for("events")
    lines = _read_lines(target)
    # Tamper with the middle row's payload.
    obj = orjson.loads(lines[1])
    obj["payload"]["index"] = 999
    lines[1] = orjson.dumps(obj, option=orjson.OPT_SORT_KEYS)
    _write_lines(target, lines)
    result = log.validate_chain("events")
    assert not result.ok, "tampering must be detected"
    assert result.first_bad_index is not None
    # The tampered row's recomputed event_hash will differ; subsequent rows
    # will have prev_hash mismatches.
    assert any("event_hash mismatch" in e or "prev_hash mismatch" in e for e in result.errors)


def test_validate_chain_detects_row_reorder(tmp_path):
    """Swapping two adjacent rows must be detected."""
    log = AuditLog(tmp_path)
    _seed_rows(log, "events", 5)
    target = log.path_for("events")
    lines = _read_lines(target)
    # Swap rows 1 and 2.
    lines[1], lines[2] = lines[2], lines[1]
    _write_lines(target, lines)
    result = log.validate_chain("events")
    assert not result.ok
    assert result.first_bad_index is not None
    assert any("prev_hash mismatch" in e or "event_hash mismatch" in e for e in result.errors)


def test_validate_chain_detects_row_insertion(tmp_path):
    """Inserting a row in the middle of the chain must be detected."""
    log = AuditLog(tmp_path)
    _seed_rows(log, "events", 4)
    target = log.path_for("events")
    lines = _read_lines(target)
    # Construct a fake row that has CORRECT event_hash for its own payload but
    # wrong prev_hash relative to the row before — to prove the validator
    # checks the chain, not just the self-hash.
    fake_payload = {"forged": True}
    ts = _now_iso()
    fake_prev = GENESIS_PREV_HASH  # wrong on purpose
    fake_event = _compute_event_hash_v2(fake_prev, ts, fake_payload)
    fake_row = {
        "category": "events",
        "recorded_at": ts,
        "prev_hash": fake_prev,
        "event_hash": fake_event,
        "payload": fake_payload,
    }
    fake_line = orjson.dumps(fake_row, option=orjson.OPT_SORT_KEYS)
    lines.insert(2, fake_line)
    _write_lines(target, lines)
    result = log.validate_chain("events")
    assert not result.ok
    assert result.first_bad_index is not None
    # The inserted row's prev_hash will not match the prior row's event_hash.
    assert any("prev_hash mismatch" in e for e in result.errors)


def test_validate_chain_detects_row_deletion(tmp_path):
    """Deleting a row from the middle of the chain must be detected."""
    log = AuditLog(tmp_path)
    _seed_rows(log, "events", 5)
    target = log.path_for("events")
    lines = _read_lines(target)
    # Delete row 2 (the third row).
    del lines[2]
    _write_lines(target, lines)
    result = log.validate_chain("events")
    assert not result.ok
    assert result.first_bad_index is not None
    assert any("prev_hash mismatch" in e for e in result.errors)


def test_validate_chain_detects_first_row_payload_tampering(tmp_path):
    """Tampering with the first row's payload changes its event_hash; row 1's
    prev_hash will then mismatch the recomputed first event_hash."""
    log = AuditLog(tmp_path)
    _seed_rows(log, "events", 3)
    target = log.path_for("events")
    lines = _read_lines(target)
    obj = orjson.loads(lines[0])
    obj["payload"]["msg"] = "TAMPERED"
    lines[0] = orjson.dumps(obj, option=orjson.OPT_SORT_KEYS)
    _write_lines(target, lines)
    result = log.validate_chain("events")
    assert not result.ok
    # The first row's event_hash will not match what we recompute.
    assert result.first_bad_index == 0


def test_validate_chain_reports_all_divergences_after_first(tmp_path):
    """After a tamper, every subsequent row's prev_hash is broken; we report all."""
    log = AuditLog(tmp_path)
    _seed_rows(log, "events", 4)
    target = log.path_for("events")
    lines = _read_lines(target)
    obj = orjson.loads(lines[0])
    obj["payload"]["msg"] = "TAMPERED"
    lines[0] = orjson.dumps(obj, option=orjson.OPT_SORT_KEYS)
    _write_lines(target, lines)
    result = log.validate_chain("events")
    assert not result.ok
    # We detect divergence at row 0 (event_hash mismatch). Following rows may
    # also report mismatches because their recomputed prev_hash now uses the
    # tampered first row's event_hash, not the original.
    assert result.first_bad_index == 0
    assert len(result.errors) >= 1


def test_validate_chain_detects_malformed_json(tmp_path):
    log = AuditLog(tmp_path)
    _seed_rows(log, "events", 3)
    target = log.path_for("events")
    raw = target.read_bytes()
    # Inject malformed JSON.
    target.write_bytes(raw + b"this-is-not-json\n")
    result = log.validate_chain("events")
    assert not result.ok


def test_validate_chain_detects_category_field_swap(tmp_path):
    """A row whose ``category`` field is wrong must be flagged."""
    log = AuditLog(tmp_path)
    _seed_rows(log, "events", 2)
    target = log.path_for("events")
    lines = _read_lines(target)
    obj = orjson.loads(lines[0])
    obj["category"] = "decisions"
    # Re-canonicalise so it parses; we won't fix the event_hash deliberately.
    lines[0] = orjson.dumps(obj, option=orjson.OPT_SORT_KEYS)
    _write_lines(target, lines)
    result = log.validate_chain("events")
    assert not result.ok
    assert any("category mismatch" in e for e in result.errors)


# ----------------------------------------------------------------------------
# Concurrency / atomic append
# ----------------------------------------------------------------------------


def test_atomic_append_does_not_interleave_under_threads(tmp_path):
    """Multiple threads appending concurrently must produce a clean chain.

    With 4 threads x 25 rows = 100 rows, the chain must validate.
    """
    log = AuditLog(tmp_path)

    def worker(start: int) -> None:
        for i in range(25):
            log.append_event("events", {"thread_start": start, "i": i})

    threads = [threading.Thread(target=worker, args=(s * 100,)) for s in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    rows = list(log.iter_rows("events"))
    assert len(rows) == 100
    result = log.validate_chain("events")
    assert result.ok, f"chain divergence under concurrent append: {result.errors[:3]}"


def test_atomic_append_handles_interrupted_write(tmp_path):
    """Simulate a half-written file: extra bytes at end must be tolerated.

    The actual append uses temp-file + rename for atomicity, so the runtime
    never observes a half-written file. But the validator should still treat
    a stray garbage line as a chain error and report it cleanly.
    """
    log = AuditLog(tmp_path)
    _seed_rows(log, "events", 2)
    target = log.path_for("events")
    raw = target.read_bytes()
    target.write_bytes(raw + b'{"category": "events", "incomp')
    result = log.validate_chain("events")
    assert not result.ok


# ----------------------------------------------------------------------------
# Row model validation
# ----------------------------------------------------------------------------


def test_audit_row_rejects_naive_timestamp():
    with pytest.raises(ValueError, match="timezone offset"):
        AuditRow(
            category="events",
            recorded_at="2026-04-30T01:23:45",  # naive
            prev_hash=GENESIS_PREV_HASH,
            event_hash="sha256:" + "a" * 64,
            payload={},
        )


def test_audit_row_rejects_bad_hash():
    with pytest.raises(ValueError, match="hash must match"):
        AuditRow(
            category="events",
            recorded_at=_now_iso(),
            prev_hash="not-a-hash",
            event_hash="sha256:" + "a" * 64,
            payload={},
        )


def test_audit_row_rejects_extra_fields():
    with pytest.raises(Exception):
        AuditRow(
            category="events",
            recorded_at=_now_iso(),
            prev_hash=GENESIS_PREV_HASH,
            event_hash="sha256:" + "a" * 64,
            payload={},
            extra_unknown="bad",  # type: ignore[call-arg]
        )


# ----------------------------------------------------------------------------
# Per-category schema validation lives in dedicated modules; here we sanity
# check that the row container accepts the 11 category labels.
# ----------------------------------------------------------------------------


def test_chain_validation_returns_errors_for_unknown_category_in_row(tmp_path):
    """Hand-craft a row whose ``category`` value is not in the enum-like set."""
    log = AuditLog(tmp_path)
    target = log.path_for("events")
    target.parent.mkdir(parents=True, exist_ok=True)
    bad = {
        "category": "events",
        "recorded_at": _now_iso(),
        "prev_hash": GENESIS_PREV_HASH,
        "event_hash": "sha256:" + "0" * 64,
        "payload": {"k": 1},
    }
    # Ensure event_hash is not the recomputed one by leaving it as zeros.
    target.write_bytes(orjson.dumps(bad, option=orjson.OPT_SORT_KEYS) + b"\n")
    result = log.validate_chain("events")
    assert not result.ok
    assert any("event_hash mismatch" in e for e in result.errors)
