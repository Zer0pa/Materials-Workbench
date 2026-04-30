"""LLZO cubic battery packet — assembles, promotes, hashes valid.

Boundary
--------
Research infrastructure for in silico materials science discovery. Outputs are
research artifacts. No regulatory certification claims. No clinical or
human-subject use. ITAR / weapons applications are out of scope (Meta UMA
Acceptable Use Policy and operator policy).
"""

from __future__ import annotations

from zer0pa_materials.boundary import RESEARCH_BOUNDARY
from zer0pa_materials.envelope import Envelope
from zer0pa_materials.packets import (
    EvidencePacket,
    assemble_battery_packet,
    validate_evidence_packet,
)
from zer0pa_materials.packets.validators import BATTERY_REQUIRED_SECTIONS


def test_llzo_packet_assembles() -> None:
    """LLZO cubic packet is constructable and has the expected fixture id."""
    packet = assemble_battery_packet("LLZO")
    assert isinstance(packet, EvidencePacket)
    assert packet.objective == "battery_solid_electrolyte"
    assert packet.fixture_id == "fixture:LLZO_cubic:d45cb2bf"
    assert packet.structure_hash.startswith("sha256:")


def test_llzo_packet_promotes_in_li_metal_mode() -> None:
    """LLZO is the canonical Li-metal-stable control: promotes in default mode."""
    packet = assemble_battery_packet("LLZO", interface_mode="li_metal")
    assert packet.promotion_decision == "promote"
    assert "All PRD §Ionic Transport gates pass" in packet.promotion_rationale


def test_llzo_packet_carries_research_boundary() -> None:
    """The packet's top-level boundary AND every nested envelope carry it verbatim."""
    packet = assemble_battery_packet("LLZO")
    assert packet.research_boundary == RESEARCH_BOUNDARY
    n = 0
    for env_dict in packet.all_envelopes():
        env = Envelope.model_validate(env_dict)
        assert env.research_boundary == RESEARCH_BOUNDARY
        n += 1
    assert n > 0, "expected at least one nested envelope"


def test_llzo_packet_has_every_required_section() -> None:
    """Every PRD-required battery section is present."""
    packet = assemble_battery_packet("LLZO")
    for required in BATTERY_REQUIRED_SECTIONS:
        assert required in packet.bundle.sections, f"missing section: {required}"


def test_llzo_packet_validation_passes() -> None:
    """The validator suite reports overall=pass on LLZO."""
    packet = assemble_battery_packet("LLZO")
    report = validate_evidence_packet(packet)
    assert report.overall_status == "pass", (
        f"validator failed: {[fi.name for fi in report.falsifier_items if fi.status != 'pass']}"
    )


def test_llzo_packet_audit_chain_complete() -> None:
    """Every envelope's audit_record_id appears in audit_trail_head."""
    packet = assemble_battery_packet("LLZO")
    head_ids = set(
        packet.bundle.section("audit_trail_head").raw_payload["audit_record_ids"]
    )
    for env_dict in packet.all_envelopes():
        rec = env_dict["audit"]["audit_record_id"]
        assert rec in head_ids, f"envelope audit_record_id {rec} not in head"


def test_llzo_packet_publishable_target_set() -> None:
    """Primary and alternative journals are real names."""
    packet = assemble_battery_packet("LLZO")
    target = packet.publishable_paper_target
    assert target.primary_journal == "npj Computational Materials"
    assert target.alternative_journal == "J. Mater. Chem. A"
    assert target.target_paper_kind == "research_article"
