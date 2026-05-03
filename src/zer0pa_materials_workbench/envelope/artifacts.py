"""Artifact manifest model and IO (PRD §Audit Trail And KG: ``artifacts.jsonl``).

An artifact manifest records the URI, hash, size, schema reference, and
provenance of every binary or structured file the pipeline produces. The
PRD requires (§Audit Trail And KG):

    artifacts.jsonl: artifact URI, hash, size, schema, offload refs

This module owns the manifest's wire format and the read/write helpers
used by the audit subsystem.
"""

from __future__ import annotations

import datetime as _dt
import re
from collections.abc import Iterable
from pathlib import Path

import orjson
from pydantic import BaseModel, ConfigDict, Field, field_validator

from zer0pa_materials_workbench.envelope.hashing import HASH_REGEX

__all__ = [
    "ArtifactManifest",
    "append_artifact_manifest_jsonl",
    "iter_artifact_manifest_jsonl",
    "read_artifact_manifest",
    "write_artifact_manifest",
]


_ARTIFACT_ID_RE = re.compile(r"^artifact:[A-Za-z0-9._\-:/]+$")
_RUN_ID_RE = re.compile(r"^run:[A-Za-z0-9._\-:/]+$")


class ArtifactManifest(BaseModel):
    """One entry in ``artifacts.jsonl``."""

    model_config = ConfigDict(extra="forbid")

    artifact_id: str = Field(..., description="URN starting with 'artifact:'.")
    uri: str = Field(..., min_length=1, description="Storage URI (file://, s3://, runpod://, ...).")
    hash: str = Field(..., description="sha256:<hex>")
    size_bytes: int = Field(..., ge=0)
    schema_ref: str = Field(
        ..., min_length=1, description="Schema URN, e.g. 'zer0pa.materials.cif.v1'."
    )
    offload_refs: list[str] = Field(
        default_factory=list,
        description="Mirror/offload URIs (cold storage, runpod cache, etc).",
    )
    created_at: str = Field(..., description="ISO-8601 UTC timestamp with offset, e.g. '2026-04-30T01:23:45+00:00'.")
    created_by_run_id: str = Field(..., description="URN of the run that generated this artifact.")

    @field_validator("artifact_id")
    @classmethod
    def _v_aid(cls, v: str) -> str:
        if not _ARTIFACT_ID_RE.match(v):
            raise ValueError(f"artifact_id must match {_ARTIFACT_ID_RE.pattern!r}; got {v!r}")
        return v

    @field_validator("hash")
    @classmethod
    def _v_hash(cls, v: str) -> str:
        if not HASH_REGEX.match(v):
            raise ValueError(f"hash must be sha256:<hex>; got {v!r}")
        return v

    @field_validator("created_by_run_id")
    @classmethod
    def _v_run(cls, v: str) -> str:
        if not _RUN_ID_RE.match(v):
            raise ValueError(f"created_by_run_id must match {_RUN_ID_RE.pattern!r}; got {v!r}")
        return v

    @field_validator("created_at")
    @classmethod
    def _v_iso(cls, v: str) -> str:
        try:
            parsed = _dt.datetime.fromisoformat(v)
        except ValueError as exc:
            raise ValueError(f"created_at must be ISO-8601: {exc}") from exc
        if parsed.tzinfo is None:
            raise ValueError("created_at must include a timezone offset (UTC preferred).")
        return v


# ----------------------------------------------------------------------------
# IO helpers
# ----------------------------------------------------------------------------


def write_artifact_manifest(path: str | Path, manifest: ArtifactManifest) -> Path:
    """Write a single manifest JSON file at ``path`` (overwrites existing)."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(orjson.dumps(manifest.model_dump(mode="json"), option=orjson.OPT_SORT_KEYS))
    return target


def read_artifact_manifest(path: str | Path) -> ArtifactManifest:
    """Read a single manifest JSON file."""
    raw = Path(path).read_bytes()
    return ArtifactManifest.model_validate_json(raw)


def append_artifact_manifest_jsonl(path: str | Path, manifest: ArtifactManifest) -> Path:
    """Append a manifest entry to a JSONL ledger (one record per line)."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    line = orjson.dumps(manifest.model_dump(mode="json"), option=orjson.OPT_SORT_KEYS)
    with target.open("ab") as f:
        f.write(line)
        f.write(b"\n")
    return target


def iter_artifact_manifest_jsonl(path: str | Path) -> Iterable[ArtifactManifest]:
    """Iterate manifests from a JSONL ledger; yields validated models."""
    src = Path(path)
    if not src.exists():
        return
    with src.open("rb") as f:
        for raw in f:
            raw = raw.strip()
            if not raw:
                continue
            yield ArtifactManifest.model_validate_json(raw)
