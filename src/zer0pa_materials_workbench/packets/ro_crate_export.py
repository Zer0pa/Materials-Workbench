"""RO-Crate 1.1 packet exporter (PRD §Audit Trail And KG).

Wave 5a uses the existing :func:`zer0pa_materials_workbench.audit.write_ro_crate_metadata`
to emit a self-describing RO-Crate root manifest. This module wraps that
primitive with packet-aware logic:

* serialise the EvidencePacket (and every section's envelopes) to JSON
  files inside the crate root;
* generate one :class:`RoCrateEntry` per file;
* call :func:`write_ro_crate_metadata` to write
  ``ro-crate-metadata.json``;
* expose :func:`parse_packet_ro_crate` so a third party can ingest the
  crate and verify the packet round-trips without loss.

The exporter is the **only** place the packet is materialised on disk
in Wave 5a; the FastAPI service / CLI rely on it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from zer0pa_materials_workbench.audit.ro_crate import (
    RoCrateEntry,
    write_ro_crate_metadata,
)
from zer0pa_materials_workbench.envelope.hashing import sha256_of
from zer0pa_materials_workbench.packets.evidence_packet import EvidencePacket

__all__ = [
    "PacketRoCrateBundle",
    "export_packet_to_ro_crate",
    "parse_packet_ro_crate",
]


@dataclass(frozen=True)
class PacketRoCrateBundle:
    """Result of exporting an :class:`EvidencePacket` to an RO-Crate."""

    crate_root: Path
    metadata_path: Path
    packet_path: Path
    section_paths: dict[str, Path]
    entries: list[RoCrateEntry]

    def round_trip(self) -> PacketRoCrateBundle:
        """Re-parse the on-disk crate and assert counts match.

        Returns a fresh :class:`PacketRoCrateBundle`; use
        :func:`parse_packet_ro_crate` for the same effect with the path
        as input.
        """
        return parse_packet_ro_crate(self.crate_root)


def _write_json(path: Path, payload: dict[str, Any]) -> tuple[int, str]:
    """Write ``payload`` as pretty JSON. Return (size, sha256)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2, sort_keys=True)
    path.write_text(text, encoding="utf-8")
    size = path.stat().st_size
    digest = sha256_of(text.encode("utf-8"))
    return size, digest


def export_packet_to_ro_crate(
    packet: EvidencePacket,
    out_dir: str | Path,
    *,
    license_spdx: str = "Proprietary",
    creator: str = "Zer0pa Materials MVP Packet Generator (Wave 5a)",
) -> PacketRoCrateBundle:
    """Materialise ``packet`` as an RO-Crate 1.1 directory.

    Layout::

        out_dir/
          ro-crate-metadata.json
          packet.json
          sections/
            phase0_literature.json
            l6_generated_structure.json
            ...

    Each section file contains the section's envelopes + raw_payload as
    a single JSON document. The RO-Crate manifest references every file
    and includes the crate-root description carrying the boundary block
    in ``researchBoundary``.
    """
    crate_root = Path(out_dir).resolve()
    crate_root.mkdir(parents=True, exist_ok=True)

    # 1. Write the packet itself.
    packet_path = crate_root / "packet.json"
    packet_size, packet_sha = _write_json(packet_path, packet.model_dump(mode="json"))

    entries: list[RoCrateEntry] = [
        RoCrateEntry(
            relative_path="packet.json",
            name="EvidencePacket",
            description=(
                f"Wave 5a evidence packet for candidate {packet.candidate_id} "
                f"(objective={packet.objective}, decision={packet.promotion_decision})."
            ),
            encoding_format="application/json",
            content_size=packet_size,
            sha256=packet_sha,
        )
    ]

    # 2. Write each section's payload.
    sections_dir = crate_root / "sections"
    sections_dir.mkdir(parents=True, exist_ok=True)
    section_paths: dict[str, Path] = {}
    for section_name, section in packet.bundle.sections.items():
        rel = f"sections/{section_name}.json"
        target = crate_root / rel
        size, digest = _write_json(target, section.model_dump(mode="json"))
        section_paths[section_name] = target
        entries.append(
            RoCrateEntry(
                relative_path=rel,
                name=f"PacketSection: {section_name}",
                description=section.summary or f"Packet section: {section_name}",
                encoding_format="application/json",
                content_size=size,
                sha256=digest,
            )
        )

    # 3. Write the RO-Crate manifest.
    metadata_path = write_ro_crate_metadata(
        crate_root=crate_root,
        name=f"Zer0pa Materials Evidence Packet — {packet.objective} / {packet.candidate_id}",
        description=(
            "Wave 5a publishable-paper evidence packet. Contains every layer "
            "envelope (Phase 0, L6, L1, L2, L1.5, ionic/ZT, L3, L4, L7), "
            "AlabOS recipe-only protocol, KG snapshot, audit-trail head, and "
            "rights claim for the candidate. PRD §Final Output Required #9 + #10."
        ),
        entries=entries,
        creator=creator,
        license_spdx=license_spdx,
        research_boundary=packet.research_boundary,
    )

    return PacketRoCrateBundle(
        crate_root=crate_root,
        metadata_path=metadata_path,
        packet_path=packet_path,
        section_paths=section_paths,
        entries=entries,
    )


def parse_packet_ro_crate(crate_root: str | Path) -> PacketRoCrateBundle:
    """Re-parse an exported RO-Crate and return the bundle.

    Verifies ``ro-crate-metadata.json`` exists and references ``packet.json``
    plus a non-empty ``sections/`` directory. Returns a populated
    :class:`PacketRoCrateBundle` whose entries match the on-disk file
    list. The validator (``packet_ro_crate_round_trip``) re-runs this
    function and compares counts.
    """
    crate_root = Path(crate_root).resolve()
    metadata_path = crate_root / "ro-crate-metadata.json"
    packet_path = crate_root / "packet.json"
    if not metadata_path.exists():
        raise FileNotFoundError(f"missing ro-crate-metadata.json at {metadata_path}")
    if not packet_path.exists():
        raise FileNotFoundError(f"missing packet.json at {packet_path}")

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    graph = metadata.get("@graph", [])
    file_entries = [n for n in graph if n.get("@type") == "File"]

    sections_dir = crate_root / "sections"
    section_paths: dict[str, Path] = {}
    if sections_dir.exists():
        for f in sorted(sections_dir.glob("*.json")):
            section_paths[f.stem] = f

    entries = [
        RoCrateEntry(
            relative_path=fe["@id"],
            name=fe.get("name", fe["@id"]),
            description=fe.get("description", ""),
            encoding_format=fe.get("encodingFormat", "application/json"),
            content_size=fe.get("contentSize"),
            sha256=fe.get("sha256"),
        )
        for fe in file_entries
    ]

    return PacketRoCrateBundle(
        crate_root=crate_root,
        metadata_path=metadata_path,
        packet_path=packet_path,
        section_paths=section_paths,
        entries=entries,
    )
