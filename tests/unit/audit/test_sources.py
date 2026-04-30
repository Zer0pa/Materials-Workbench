"""Tests for source manifests and gated stubs (A1 §Deep Research Policy)."""

from __future__ import annotations

import datetime as _dt

import pytest

from zer0pa_materials.audit.log import AuditLog
from zer0pa_materials.audit.sources import (
    BlockedSourceManifest,
    SourceManifest,
)


def _now_iso() -> str:
    return _dt.datetime.now(tz=_dt.timezone.utc).isoformat(timespec="microseconds")


# ----------------------------------------------------------------------------
# SourceManifest
# ----------------------------------------------------------------------------


def test_source_manifest_round_trip():
    sm = SourceManifest(
        source_manifest_id="src:doi:10.1038/s41586-021-03819-2",
        source_type="paper",
        locator="10.1038/s41586-021-03819-2",
        retrieval_date=_now_iso(),
        license_spdx="CC-BY-4.0",
        summary="LLZO ionic conductivity reference",
        decision_impact="LLZO recovery threshold",
    )
    raw = sm.model_dump_json()
    sm2 = SourceManifest.model_validate_json(raw)
    assert sm2.source_manifest_id == sm.source_manifest_id
    assert sm2.redaction == "none"


def test_source_manifest_rejects_bad_id():
    with pytest.raises(ValueError, match="source_manifest_id must match"):
        SourceManifest(
            source_manifest_id="not-a-source-id",
            source_type="paper",
            locator="x",
            retrieval_date=_now_iso(),
            license_spdx="MIT",
            summary="x",
            decision_impact="x",
        )


def test_source_manifest_rejects_naive_timestamp():
    with pytest.raises(ValueError, match="timezone"):
        SourceManifest(
            source_manifest_id="src:test",
            source_type="paper",
            locator="x",
            retrieval_date="2026-04-30T01:23:45",  # naive
            license_spdx="MIT",
            summary="x",
            decision_impact="x",
        )


def test_source_manifest_rejects_bad_hash():
    with pytest.raises(ValueError, match="sha256"):
        SourceManifest(
            source_manifest_id="src:test",
            source_type="paper",
            locator="x",
            retrieval_date=_now_iso(),
            license_spdx="MIT",
            summary="x",
            decision_impact="x",
            hash="not-a-hash",
        )


def test_source_manifest_accepts_optional_hash():
    sm = SourceManifest(
        source_manifest_id="src:test",
        source_type="paper",
        locator="x",
        retrieval_date=_now_iso(),
        license_spdx="MIT",
        summary="x",
        decision_impact="x",
        hash="sha256:" + "a" * 64,
    )
    assert sm.hash == "sha256:" + "a" * 64


def test_source_manifest_requires_minimum_fields():
    """Required fields must be present and non-empty."""
    with pytest.raises(ValueError):
        SourceManifest()  # type: ignore[call-arg]


def test_source_manifest_rejects_extra_fields():
    with pytest.raises(Exception):
        SourceManifest(
            source_manifest_id="src:test",
            source_type="paper",
            locator="x",
            retrieval_date=_now_iso(),
            license_spdx="MIT",
            summary="x",
            decision_impact="x",
            extra_field="bad",  # type: ignore[call-arg]
        )


# ----------------------------------------------------------------------------
# BlockedSourceManifest
# ----------------------------------------------------------------------------


def test_blocked_source_manifest_round_trip():
    bsm = BlockedSourceManifest(
        source_manifest_id="src:thermo-calc:fe-cr-tdb",
        attempted_locator="https://thermocalc.com/products/databases/iron-and-steel/",
        blocker_reason="license_unverified",
        blocker_detail="No active Thermo-Calc license at this site",
        retry_strategy="Customer must provide valid Thermo-Calc license",
    )
    raw = bsm.model_dump_json()
    bsm2 = BlockedSourceManifest.model_validate_json(raw)
    assert bsm2.source_manifest_id == bsm.source_manifest_id
    assert bsm2.blocker_reason == "license_unverified"


def test_blocked_source_manifest_rejects_bad_id():
    with pytest.raises(ValueError, match="source_manifest_id must match"):
        BlockedSourceManifest(
            source_manifest_id="bad-id",
            attempted_locator="x",
            blocker_reason="other",
            blocker_detail="x",
            retry_strategy="x",
        )


def test_blocked_source_manifest_blocked_at_default_is_iso_utc():
    bsm = BlockedSourceManifest(
        source_manifest_id="src:test",
        attempted_locator="x",
        blocker_reason="other",
        blocker_detail="x",
        retry_strategy="x",
    )
    parsed = _dt.datetime.fromisoformat(bsm.blocked_at)
    assert parsed.tzinfo is not None


def test_blocked_source_manifest_rejects_invalid_blocker_reason():
    with pytest.raises(ValueError):
        BlockedSourceManifest(
            source_manifest_id="src:test",
            attempted_locator="x",
            blocker_reason="not-a-real-reason",  # type: ignore[arg-type]
            blocker_detail="x",
            retry_strategy="x",
        )


# ----------------------------------------------------------------------------
# Integration with the AuditLog
# ----------------------------------------------------------------------------


def test_source_manifest_appends_into_sources_jsonl(tmp_path):
    log = AuditLog(tmp_path)
    sm = SourceManifest(
        source_manifest_id="src:doi:10.1038/s41586-021-03819-2",
        source_type="paper",
        locator="10.1038/s41586-021-03819-2",
        retrieval_date=_now_iso(),
        license_spdx="CC-BY-4.0",
        summary="x",
        decision_impact="x",
    )
    row = log.append_event("sources", sm.model_dump(mode="json"))
    assert row.payload["source_manifest_id"] == sm.source_manifest_id
    result = log.validate_chain("sources")
    assert result.ok


def test_blocked_source_appends_into_sources_jsonl_and_chain_holds(tmp_path):
    log = AuditLog(tmp_path)
    bsm = BlockedSourceManifest(
        source_manifest_id="src:test:blocked",
        attempted_locator="x",
        blocker_reason="rate_limited",
        blocker_detail="x",
        retry_strategy="x",
    )
    payload = bsm.model_dump(mode="json")
    payload["__blocked__"] = True
    log.append_event("sources", payload)
    rows = list(log.iter_rows("sources"))
    assert len(rows) == 1
    assert rows[0].payload["__blocked__"] is True
    assert log.validate_chain("sources").ok


def test_mixed_source_and_blocked_in_one_chain(tmp_path):
    log = AuditLog(tmp_path)
    log.append_event(
        "sources",
        SourceManifest(
            source_manifest_id="src:test:1",
            source_type="paper",
            locator="x",
            retrieval_date=_now_iso(),
            license_spdx="MIT",
            summary="x",
            decision_impact="x",
        ).model_dump(mode="json"),
    )
    log.append_event(
        "sources",
        BlockedSourceManifest(
            source_manifest_id="src:test:2",
            attempted_locator="x",
            blocker_reason="other",
            blocker_detail="x",
            retry_strategy="x",
        ).model_dump(mode="json"),
    )
    log.append_event(
        "sources",
        SourceManifest(
            source_manifest_id="src:test:3",
            source_type="paper",
            locator="x",
            retrieval_date=_now_iso(),
            license_spdx="MIT",
            summary="x",
            decision_impact="x",
        ).model_dump(mode="json"),
    )
    rows = list(log.iter_rows("sources"))
    assert len(rows) == 3
    assert log.validate_chain("sources").ok
