"""Audit hash-chain end-to-end integration test (Wave 4c).

Boundary: Research infrastructure for in silico materials science discovery.
Outputs are research artifacts. No regulatory certification claims. No
clinical or human-subject use. ITAR / weapons applications are out of scope
(Meta UMA Acceptable Use Policy and operator policy).

After running a battery campaign:
  - runs/events/decisions/disagreement/falsifiers/rights/models/parameters/
    sources/artifacts/reasoner_tuples all validate
  - Tampering detection: edit one row → must fail
  - Insertion detection: add a row → must fail
  - Deletion detection: remove a row → must fail
  - Reorder detection: swap two rows → must fail
"""

from __future__ import annotations

from pathlib import Path

import orjson

from zer0pa_materials_workbench.audit.kg import MaterialsKG
from zer0pa_materials_workbench.audit.log import (
    AUDIT_CATEGORIES,
    GENESIS_PREV_HASH,
    AuditLog,
    _compute_event_hash_v2,
)
from zer0pa_materials_workbench.orchestration import Campaign, CampaignSpec

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_audit_kg(tmp_path: Path) -> tuple[AuditLog, MaterialsKG]:
    return AuditLog(tmp_path / "audit"), MaterialsKG(tmp_path / "kg.sqlite")


def _read_lines(path: Path) -> list[bytes]:
    return [line for line in path.read_bytes().split(b"\n") if line.strip()]


def _write_lines(path: Path, lines: list[bytes]) -> None:
    path.write_bytes(b"\n".join(lines) + b"\n")


def _seed_campaign(audit: AuditLog, kg: MaterialsKG) -> Campaign:
    """Run a minimal battery campaign that touches all audit categories."""
    spec = CampaignSpec(
        campaign_id="campaign:audit-chain-test/battery",
        tenant="audit-test",
        objective="Li-ion conductivity > 1e-3 S/cm",
        chemical_system="Li-La-Zr-O",
    )
    camp = Campaign.create(spec, audit, kg)
    camp.transition_to("hypothesising", rationale="testing audit chain")
    camp.transition_to("generating", rationale="generating candidates")
    camp.transition_to("screening_l2", rationale="L2 screening")

    for i in range(3):
        cid = f"candidate:LLZO-audit-chain:{i:03d}"
        sh = "sha256:" + f"{i:x}" * 64
        camp.register_candidate(cid, structure_hash="sha256:" + "a" * 64)
        camp.transition_candidate(cid, "screened", rationale=f"L2 promote for {i}")

    # Write a second run row so 'runs' has >= 2 rows for deletion/tampering tests.
    audit.append_event("runs", {
        "campaign_id": "campaign:audit-chain-test/battery",
        "kind": "run_resumed",
        "tenant": "audit-test",
        "spec_kind": "campaign",
    })

    # Write explicitly to events (normally done by Campaign.attach_envelope).
    audit.append_event("events", {
        "kind": "envelope_attached",
        "campaign_id": "campaign:audit-chain-test/battery",
        "candidate_id": "candidate:LLZO-audit-chain:000",
        "layer": "L2",
        "audit_record_id": "audit:test:l2:001",
        "structure_hash": "sha256:" + "a" * 64,
    })
    audit.append_event("events", {
        "kind": "envelope_attached",
        "campaign_id": "campaign:audit-chain-test/battery",
        "candidate_id": "candidate:LLZO-audit-chain:001",
        "layer": "L1",
        "audit_record_id": "audit:test:l1:001",
        "structure_hash": "sha256:" + "a" * 64,
    })
    audit.append_event("events", {
        "kind": "envelope_attached",
        "campaign_id": "campaign:audit-chain-test/battery",
        "candidate_id": "candidate:LLZO-audit-chain:002",
        "layer": "ionic",
        "audit_record_id": "audit:test:ionic:001",
        "structure_hash": "sha256:" + "a" * 64,
    })
    audit.append_event("events", {
        "kind": "envelope_attached",
        "campaign_id": "campaign:audit-chain-test/battery",
        "candidate_id": "candidate:LLZO-audit-chain:000",
        "layer": "L1.5",
        "audit_record_id": "audit:test:l1-5:001",
        "structure_hash": "sha256:" + "a" * 64,
    })

    # Also write into additional audit categories.
    audit.append_event("disagreement", {
        "kind": "cross_layer_disagreement",
        "layer": "L2",
        "metric": "energy_disagreement_meV_per_atom",
        "value": 5.0,
        "campaign_id": "campaign:audit-chain-test/battery",
    })
    audit.append_event("falsifiers", {
        "kind": "falsifier_result",
        "name": "test_falsifier",
        "status": "pass",
        "campaign_id": "campaign:audit-chain-test/battery",
    })
    audit.append_event("rights", {
        "kind": "rights_claim",
        "tenant": "audit-test",
        "reuse_scope": "tenant_only",
    })
    audit.append_event("models", {
        "kind": "model_version",
        "adapter": "TestAdapter",
        "version": "0.1.0",
    })
    audit.append_event("parameters", {
        "kind": "parameter_set",
        "temperature_K": 300.0,
        "structure_hash": "sha256:" + "a" * 64,
    })
    audit.append_event("sources", {
        "kind": "literature_source",
        "doi": "10.1234/test",
        "title": "Test Source",
    })
    audit.append_event("artifacts", {
        "kind": "artifact_manifest",
        "artifact_hash": "sha256:" + "b" * 64,
        "uri": "file://test/artifact.json",
    })
    audit.append_event("reasoner_tuples", {
        "kind": "reasoner_tuple",
        "tuple_id": "rtuple:test:001",
        "decision": "promote",
        "candidate_id": "candidate:LLZO-audit-chain:000",
    })
    return camp


# ---------------------------------------------------------------------------
# Baseline: all 11 categories validate
# ---------------------------------------------------------------------------


class TestAllCategoriesValidate:
    """All 11 audit categories must be valid after a campaign run."""

    def test_all_categories_chain_ok(self, tmp_path: Path) -> None:
        audit, kg = _make_audit_kg(tmp_path)
        _seed_campaign(audit, kg)

        # Categories we wrote into: runs, events, decisions + 9 extras
        # Categories that may be empty: they still validate (empty = ok)
        for cat in AUDIT_CATEGORIES:
            result = audit.validate_chain(cat)
            assert result.ok, (
                f"Category {cat!r} chain must be valid after seeded campaign; "
                f"errors: {result.errors}"
            )

    def test_written_categories_have_rows(self, tmp_path: Path) -> None:
        """Categories we explicitly wrote must have at least one row."""
        audit, kg = _make_audit_kg(tmp_path)
        _seed_campaign(audit, kg)

        expected_nonempty = {
            "runs", "events", "decisions", "disagreement", "falsifiers",
            "rights", "models", "parameters", "sources", "artifacts",
            "reasoner_tuples",
        }
        for cat in expected_nonempty:
            rows = list(audit.iter_rows(cat))
            assert len(rows) >= 1, (
                f"Category {cat!r} should have at least one row after seeded campaign"
            )

    def test_all_11_categories_covered(self) -> None:
        assert len(AUDIT_CATEGORIES) == 11, (
            f"Expected 11 audit categories; got {len(AUDIT_CATEGORIES)}: {AUDIT_CATEGORIES}"
        )

    def test_chain_row_counts_positive(self, tmp_path: Path) -> None:
        audit, kg = _make_audit_kg(tmp_path)
        _seed_campaign(audit, kg)
        for cat in ("runs", "events", "decisions"):
            result = audit.validate_chain(cat)
            assert result.checked_rows > 0, (
                f"Category {cat!r} must have > 0 rows in chain after seeded campaign"
            )


# ---------------------------------------------------------------------------
# Tampering detection: edit one row
# ---------------------------------------------------------------------------


class TestTamperingDetection:
    """Editing any byte in a row's payload must be detected."""

    def test_edit_middle_row_payload_detected(self, tmp_path: Path) -> None:
        audit, kg = _make_audit_kg(tmp_path)
        _seed_campaign(audit, kg)
        target = audit.path_for("events")
        lines = _read_lines(target)
        assert len(lines) >= 2, "Need at least 2 events rows for tampering test"

        # Tamper the middle row.
        mid = len(lines) // 2
        obj = orjson.loads(lines[mid])
        obj["payload"]["_tampered"] = True
        lines[mid] = orjson.dumps(obj, option=orjson.OPT_SORT_KEYS)
        _write_lines(target, lines)

        result = audit.validate_chain("events")
        assert not result.ok, "Tampering with a payload byte must be detected"
        assert result.first_bad_index is not None
        assert any(
            "event_hash mismatch" in e or "prev_hash mismatch" in e
            for e in result.errors
        ), f"Expected hash mismatch in errors; got: {result.errors}"

    def test_edit_first_row_payload_detected(self, tmp_path: Path) -> None:
        audit, kg = _make_audit_kg(tmp_path)
        _seed_campaign(audit, kg)
        target = audit.path_for("decisions")
        lines = _read_lines(target)
        assert len(lines) >= 1

        obj = orjson.loads(lines[0])
        obj["payload"]["kind"] = "FORGED"
        lines[0] = orjson.dumps(obj, option=orjson.OPT_SORT_KEYS)
        _write_lines(target, lines)

        result = audit.validate_chain("decisions")
        assert not result.ok
        assert result.first_bad_index == 0

    def test_edit_last_row_payload_detected(self, tmp_path: Path) -> None:
        audit, kg = _make_audit_kg(tmp_path)
        _seed_campaign(audit, kg)
        target = audit.path_for("events")
        lines = _read_lines(target)
        assert len(lines) >= 1

        obj = orjson.loads(lines[-1])
        obj["payload"]["_tampered"] = "last"
        lines[-1] = orjson.dumps(obj, option=orjson.OPT_SORT_KEYS)
        _write_lines(target, lines)

        result = audit.validate_chain("events")
        assert not result.ok


# ---------------------------------------------------------------------------
# Insertion detection: add a spurious row
# ---------------------------------------------------------------------------


class TestInsertionDetection:
    """Inserting a row in the middle of the chain must be detected."""

    def test_insertion_in_events_detected(self, tmp_path: Path) -> None:
        audit, kg = _make_audit_kg(tmp_path)
        _seed_campaign(audit, kg)
        target = audit.path_for("events")
        lines = _read_lines(target)
        assert len(lines) >= 2

        import datetime as _dt
        ts = _dt.datetime.now(tz=_dt.timezone.utc).isoformat(timespec="microseconds")
        # Build a fake row with a wrong prev_hash (genesis) — this is the canonical
        # insertion test pattern from test_audit_log.py.
        fake_payload = {"kind": "forged_insertion", "_test": True}
        fake_event = _compute_event_hash_v2(GENESIS_PREV_HASH, ts, fake_payload)
        fake_row = {
            "category": "events",
            "recorded_at": ts,
            "prev_hash": GENESIS_PREV_HASH,  # wrong — breaks chain
            "event_hash": fake_event,
            "payload": fake_payload,
        }
        fake_line = orjson.dumps(fake_row, option=orjson.OPT_SORT_KEYS)
        # Insert after the first row.
        lines.insert(1, fake_line)
        _write_lines(target, lines)

        result = audit.validate_chain("events")
        assert not result.ok, "Inserted row must be detected"
        assert any("prev_hash mismatch" in e for e in result.errors), (
            f"Expected prev_hash mismatch; got: {result.errors}"
        )

    def test_insertion_in_decisions_detected(self, tmp_path: Path) -> None:
        audit, kg = _make_audit_kg(tmp_path)
        _seed_campaign(audit, kg)
        target = audit.path_for("decisions")
        lines = _read_lines(target)
        assert len(lines) >= 2

        import datetime as _dt
        ts = _dt.datetime.now(tz=_dt.timezone.utc).isoformat(timespec="microseconds")
        fake_payload = {"kind": "forged_decision"}
        fake_event = _compute_event_hash_v2(GENESIS_PREV_HASH, ts, fake_payload)
        fake_row = {
            "category": "decisions",
            "recorded_at": ts,
            "prev_hash": GENESIS_PREV_HASH,
            "event_hash": fake_event,
            "payload": fake_payload,
        }
        lines.insert(1, orjson.dumps(fake_row, option=orjson.OPT_SORT_KEYS))
        _write_lines(target, lines)

        result = audit.validate_chain("decisions")
        assert not result.ok


# ---------------------------------------------------------------------------
# Deletion detection: remove a row
# ---------------------------------------------------------------------------


class TestDeletionDetection:
    """Deleting a row from the chain must be detected."""

    def test_deletion_from_events_detected(self, tmp_path: Path) -> None:
        audit, kg = _make_audit_kg(tmp_path)
        _seed_campaign(audit, kg)
        target = audit.path_for("events")
        lines = _read_lines(target)
        assert len(lines) >= 3, f"Need >= 3 events rows; got {len(lines)}"

        # Delete a middle row.
        del lines[len(lines) // 2]
        _write_lines(target, lines)

        result = audit.validate_chain("events")
        assert not result.ok, "Deleting a row must be detected"
        assert any("prev_hash mismatch" in e for e in result.errors), (
            f"Expected prev_hash mismatch; got: {result.errors}"
        )

    def test_deletion_from_decisions_detected(self, tmp_path: Path) -> None:
        audit, kg = _make_audit_kg(tmp_path)
        _seed_campaign(audit, kg)
        target = audit.path_for("decisions")
        lines = _read_lines(target)
        assert len(lines) >= 2

        del lines[1]
        _write_lines(target, lines)

        result = audit.validate_chain("decisions")
        assert not result.ok

    def test_deletion_of_first_row_detected(self, tmp_path: Path) -> None:
        audit, kg = _make_audit_kg(tmp_path)
        _seed_campaign(audit, kg)
        target = audit.path_for("runs")
        lines = _read_lines(target)
        assert len(lines) >= 2

        # Delete first row — second row's prev_hash no longer matches genesis.
        del lines[0]
        _write_lines(target, lines)

        result = audit.validate_chain("runs")
        assert not result.ok


# ---------------------------------------------------------------------------
# Reorder detection: swap two rows
# ---------------------------------------------------------------------------


class TestReorderDetection:
    """Swapping two rows must be detected."""

    def test_swap_adjacent_rows_in_events_detected(self, tmp_path: Path) -> None:
        audit, kg = _make_audit_kg(tmp_path)
        _seed_campaign(audit, kg)
        target = audit.path_for("events")
        lines = _read_lines(target)
        assert len(lines) >= 3, f"Need >= 3 events rows; got {len(lines)}"

        # Swap rows 0 and 1.
        lines[0], lines[1] = lines[1], lines[0]
        _write_lines(target, lines)

        result = audit.validate_chain("events")
        assert not result.ok, "Reordering rows must be detected"
        assert result.first_bad_index is not None
        assert any(
            "prev_hash mismatch" in e or "event_hash mismatch" in e
            for e in result.errors
        ), f"Expected hash mismatch; got: {result.errors}"

    def test_swap_non_adjacent_rows_in_decisions_detected(self, tmp_path: Path) -> None:
        audit, kg = _make_audit_kg(tmp_path)
        _seed_campaign(audit, kg)
        target = audit.path_for("decisions")
        lines = _read_lines(target)
        assert len(lines) >= 3, f"Need >= 3 decisions rows; got {len(lines)}"

        # Swap first and last.
        lines[0], lines[-1] = lines[-1], lines[0]
        _write_lines(target, lines)

        result = audit.validate_chain("decisions")
        assert not result.ok

    def test_swap_in_runs_detected(self, tmp_path: Path) -> None:
        audit, kg = _make_audit_kg(tmp_path)
        # Write two runs rows.
        audit.append_event("runs", {"campaign_id": "c1", "spec_kind": "campaign"})
        audit.append_event("runs", {"campaign_id": "c2", "spec_kind": "campaign"})
        target = audit.path_for("runs")
        lines = _read_lines(target)
        assert len(lines) == 2

        lines[0], lines[1] = lines[1], lines[0]
        _write_lines(target, lines)

        result = audit.validate_chain("runs")
        assert not result.ok


# ---------------------------------------------------------------------------
# Summary: all four tampering modes confirmed
# ---------------------------------------------------------------------------


class TestAllFourTamperingModes:
    """Single test that confirms all four modes are detected in one run."""

    def test_all_four_modes_detected(self, tmp_path: Path) -> None:
        """
        Run all four tampering modes against the same seeded campaign log
        and confirm that each is detected. This is the canonical 4-mode test
        required by the Wave 4c brief.
        """
        import shutil

        # Seed once.
        audit0, kg0 = _make_audit_kg(tmp_path / "seed")
        _seed_campaign(audit0, kg0)

        category = "events"
        original_path = audit0.path_for(category)
        original_lines = _read_lines(original_path)
        assert len(original_lines) >= 4, (
            f"Need >= 4 rows for all four modes; got {len(original_lines)}"
        )

        results: dict[str, bool] = {}

        # --- Mode 1: Tampering ---
        lines = list(original_lines)
        mid = len(lines) // 2
        obj = orjson.loads(lines[mid])
        obj["payload"]["_tampered"] = True
        lines[mid] = orjson.dumps(obj, option=orjson.OPT_SORT_KEYS)
        tamp_dir = tmp_path / "tamp"
        tamp_dir.mkdir()
        shutil.copytree(tmp_path / "seed" / "audit", tamp_dir / "audit")
        AuditLog(tamp_dir / "audit").path_for(category).parent.mkdir(parents=True, exist_ok=True)
        (tamp_dir / "audit" / f"{category}.jsonl").write_bytes(
            b"\n".join(lines) + b"\n"
        )
        results["tampering"] = not AuditLog(tamp_dir / "audit").validate_chain(category).ok

        # --- Mode 2: Insertion ---
        import datetime as _dt
        lines = list(original_lines)
        ts = _dt.datetime.now(tz=_dt.timezone.utc).isoformat(timespec="microseconds")
        fake_payload = {"kind": "forged_insertion"}
        fake_ev = _compute_event_hash_v2(GENESIS_PREV_HASH, ts, fake_payload)
        fake_row = orjson.dumps({
            "category": category,
            "recorded_at": ts,
            "prev_hash": GENESIS_PREV_HASH,
            "event_hash": fake_ev,
            "payload": fake_payload,
        }, option=orjson.OPT_SORT_KEYS)
        lines.insert(2, fake_row)
        ins_dir = tmp_path / "ins"
        ins_dir.mkdir()
        shutil.copytree(tmp_path / "seed" / "audit", ins_dir / "audit")
        (ins_dir / "audit" / f"{category}.jsonl").write_bytes(
            b"\n".join(lines) + b"\n"
        )
        results["insertion"] = not AuditLog(ins_dir / "audit").validate_chain(category).ok

        # --- Mode 3: Deletion ---
        lines = list(original_lines)
        del lines[len(lines) // 2]
        del_dir = tmp_path / "del"
        del_dir.mkdir()
        shutil.copytree(tmp_path / "seed" / "audit", del_dir / "audit")
        (del_dir / "audit" / f"{category}.jsonl").write_bytes(
            b"\n".join(lines) + b"\n"
        )
        results["deletion"] = not AuditLog(del_dir / "audit").validate_chain(category).ok

        # --- Mode 4: Reorder ---
        lines = list(original_lines)
        lines[0], lines[1] = lines[1], lines[0]
        reord_dir = tmp_path / "reord"
        reord_dir.mkdir()
        shutil.copytree(tmp_path / "seed" / "audit", reord_dir / "audit")
        (reord_dir / "audit" / f"{category}.jsonl").write_bytes(
            b"\n".join(lines) + b"\n"
        )
        results["reorder"] = not AuditLog(reord_dir / "audit").validate_chain(category).ok

        # All four must be detected.
        for mode, detected in results.items():
            assert detected, (
                f"Mode '{mode}' tampering was NOT detected — this is a critical security failure"
            )
