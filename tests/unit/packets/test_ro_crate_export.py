"""RO-Crate exporter round-trip tests.

Boundary
--------
Research infrastructure for in silico materials science discovery. Outputs are
research artifacts. No regulatory certification claims. No clinical or
human-subject use. ITAR / weapons applications are out of scope (Meta UMA
Acceptable Use Policy and operator policy).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from zer0pa_materials.boundary import RESEARCH_BOUNDARY
from zer0pa_materials.packets import (
    assemble_battery_packet,
    assemble_thermoelectric_packet,
    export_packet_to_ro_crate,
    parse_packet_ro_crate,
)


def test_battery_packet_round_trip(tmp_path: Path) -> None:
    """Battery packet survives serialise → parse with no count drift."""
    packet = assemble_battery_packet("LLZO")
    bundle = export_packet_to_ro_crate(packet, tmp_path)

    # Manifest exists.
    assert bundle.metadata_path.exists()
    assert bundle.packet_path.exists()
    # 15 sections + 1 packet root => 16 entries.
    assert len(bundle.entries) == len(bundle.section_paths) + 1

    parsed = parse_packet_ro_crate(tmp_path)
    assert len(parsed.entries) == len(bundle.entries)
    assert len(parsed.section_paths) == len(bundle.section_paths)
    # Same section names.
    assert sorted(parsed.section_paths.keys()) == sorted(bundle.section_paths.keys())


def test_thermoelectric_packet_round_trip(tmp_path: Path) -> None:
    """Thermoelectric packet round-trips with the same shape."""
    packet = assemble_thermoelectric_packet("Bi2Te3")
    bundle = export_packet_to_ro_crate(packet, tmp_path)
    parsed = parse_packet_ro_crate(tmp_path)
    assert len(parsed.section_paths) == len(bundle.section_paths)


def test_metadata_carries_research_boundary(tmp_path: Path) -> None:
    """The crate metadata's root entity carries the verbatim boundary."""
    packet = assemble_battery_packet("LLZO")
    bundle = export_packet_to_ro_crate(packet, tmp_path)
    metadata = json.loads(bundle.metadata_path.read_text(encoding="utf-8"))
    graph = metadata["@graph"]
    root = next(n for n in graph if n.get("@id") == "./")
    assert root.get("researchBoundary") == RESEARCH_BOUNDARY


def test_every_section_file_carries_section_payload(tmp_path: Path) -> None:
    """Each section JSON file contains the full PacketSection dump."""
    packet = assemble_battery_packet("LLZO")
    bundle = export_packet_to_ro_crate(packet, tmp_path)
    for section_name, section_path in bundle.section_paths.items():
        payload = json.loads(section_path.read_text(encoding="utf-8"))
        assert payload["section_name"] == section_name
        # Round-trip preserves counts.
        original = packet.bundle.section(section_name)
        assert original is not None
        assert len(payload.get("envelopes", [])) == len(original.envelopes)


def test_parse_missing_metadata_raises(tmp_path: Path) -> None:
    """Parsing an empty directory must raise FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        parse_packet_ro_crate(tmp_path)
