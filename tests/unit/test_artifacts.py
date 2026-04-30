"""Unit tests for ArtifactManifest IO."""

from __future__ import annotations

import datetime as _dt

import pytest
from pydantic import ValidationError

from zer0pa_materials.envelope import (
    ArtifactManifest,
    append_artifact_manifest_jsonl,
    iter_artifact_manifest_jsonl,
    read_artifact_manifest,
    sha256_of,
    write_artifact_manifest,
)


def _good_manifest(**overrides) -> ArtifactManifest:
    base = dict(
        artifact_id="artifact:test-001",
        uri="file:///tmp/x.cif",
        hash=sha256_of({"x": 1}),
        size_bytes=1024,
        schema_ref="zer0pa.materials.cif.v1",
        offload_refs=[],
        created_at=_dt.datetime.now(_dt.timezone.utc).isoformat(),
        created_by_run_id="run:test",
    )
    base.update(overrides)
    return ArtifactManifest(**base)


def test_artifact_manifest_round_trip(tmp_path):
    m = _good_manifest()
    path = tmp_path / "m.json"
    write_artifact_manifest(path, m)
    rebuilt = read_artifact_manifest(path)
    assert rebuilt.artifact_id == m.artifact_id
    assert rebuilt.hash == m.hash


def test_artifact_manifest_jsonl_append_and_iter(tmp_path):
    path = tmp_path / "manifests.jsonl"
    m1 = _good_manifest(artifact_id="artifact:001")
    m2 = _good_manifest(artifact_id="artifact:002")
    append_artifact_manifest_jsonl(path, m1)
    append_artifact_manifest_jsonl(path, m2)
    items = list(iter_artifact_manifest_jsonl(path))
    assert len(items) == 2
    assert {m.artifact_id for m in items} == {"artifact:001", "artifact:002"}


def test_artifact_manifest_rejects_bad_artifact_id():
    with pytest.raises(ValidationError):
        _good_manifest(artifact_id="not-a-urn")


def test_artifact_manifest_rejects_bad_hash():
    with pytest.raises(ValidationError):
        _good_manifest(hash="md5:abc")


def test_artifact_manifest_requires_timezone_aware_iso():
    with pytest.raises(ValidationError):
        _good_manifest(created_at="2026-04-30T01:23:45")  # naive


def test_artifact_manifest_iter_missing_file_yields_empty(tmp_path):
    items = list(iter_artifact_manifest_jsonl(tmp_path / "does-not-exist.jsonl"))
    assert items == []
