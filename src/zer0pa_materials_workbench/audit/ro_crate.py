"""RO-Crate 1.1 manifest writer (PRD §Audit Trail And KG).

The MVP packet generator (Wave 5) populates a campaign's evidence directory
with:

* the audit JSONL files
* the RDF Turtle export
* the source manifests
* the falsifier ledger
* the KG SQLite (or a Turtle export of it)
* selected artifacts

This module emits ``ro-crate-metadata.json`` describing those entities so a
third party can ingest the directory as a self-describing dataset. We
implement just the manifest writer here; Wave 5 supplies the artifact list.

Spec reference: https://www.researchobject.org/ro-crate/1.1/
"""

from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "RoCrateEntry",
    "write_ro_crate_metadata",
]


_RO_CRATE_CONFORMS_TO = "https://w3id.org/ro/crate/1.1"
_RO_CRATE_CONTEXT = "https://w3id.org/ro/crate/1.1/context"


class RoCrateEntry(BaseModel):
    """One file/dataset entry to include in the RO-Crate."""

    model_config = ConfigDict(extra="forbid")

    relative_path: str = Field(
        ..., description="Path relative to the crate root, e.g. 'audit/events.jsonl'."
    )
    name: str = Field(..., description="Short human-readable name.")
    description: str = Field(..., description="One-line description.")
    encoding_format: str = Field(
        default="application/json",
        description="MIME type, e.g. 'application/json', 'text/turtle'.",
    )
    content_size: int | None = Field(
        default=None, description="File size in bytes (optional)."
    )
    sha256: str | None = Field(
        default=None, description="sha256:<hex> of the file (optional)."
    )


def _utc_now() -> str:
    return _dt.datetime.now(tz=_dt.timezone.utc).isoformat(timespec="microseconds")


def write_ro_crate_metadata(
    crate_root: str | Path,
    name: str,
    description: str,
    entries: list[RoCrateEntry],
    creator: str = "Zer0pa Materials Workbench Overnight Executor",
    license_spdx: str = "Proprietary",
    research_boundary: str | None = None,
) -> Path:
    """Write ``ro-crate-metadata.json`` at ``crate_root``.

    Returns the path of the written manifest.
    """
    root = Path(crate_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    target = root / "ro-crate-metadata.json"

    graph: list[dict[str, Any]] = []

    # Required: the metadata file itself.
    graph.append(
        {
            "@type": "CreativeWork",
            "@id": "ro-crate-metadata.json",
            "conformsTo": {"@id": _RO_CRATE_CONFORMS_TO},
            "about": {"@id": "./"},
        }
    )

    # Required: the root data entity.
    root_entity: dict[str, Any] = {
        "@type": "Dataset",
        "@id": "./",
        "name": name,
        "description": description,
        "datePublished": _utc_now(),
        "creator": {"@type": "Organization", "name": creator},
        "license": license_spdx,
        "hasPart": [{"@id": e.relative_path} for e in entries],
    }
    if research_boundary is not None:
        root_entity["researchBoundary"] = research_boundary
    graph.append(root_entity)

    # Each entry.
    for e in entries:
        block: dict[str, Any] = {
            "@type": "File",
            "@id": e.relative_path,
            "name": e.name,
            "description": e.description,
            "encodingFormat": e.encoding_format,
        }
        if e.content_size is not None:
            block["contentSize"] = e.content_size
        if e.sha256 is not None:
            block["sha256"] = e.sha256
        graph.append(block)

    document: dict[str, Any] = {
        "@context": _RO_CRATE_CONTEXT,
        "@graph": graph,
    }

    target.write_text(json.dumps(document, indent=2, sort_keys=True), encoding="utf-8")
    return target
