"""Packet falsifier suite — every falsifier triggers correctly.

Boundary
--------
Research infrastructure for in silico materials science discovery. Outputs are
research artifacts. No regulatory certification claims. No clinical or
human-subject use. ITAR / weapons applications are out of scope (Meta UMA
Acceptable Use Policy and operator policy).
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from zer0pa_materials_workbench.falsifiers.packet_falsifiers import (
    packet_alabos_recipe_only_section,
    packet_boundary_carriage,
    packet_completeness,
    packet_promotion_gate,
    packet_provenance_chain,
    packet_publishable_paper_target_set,
    packet_ro_crate_round_trip,
)
from zer0pa_materials_workbench.packets import assemble_battery_packet
from zer0pa_materials_workbench.packets.evidence_packet import (
    EvidencePacket,
)


@pytest.fixture()
def llzo_packet() -> EvidencePacket:
    return assemble_battery_packet("LLZO")


def test_packet_completeness_pass(llzo_packet: EvidencePacket) -> None:
    item = packet_completeness(llzo_packet)
    assert item.status == "pass"


def test_packet_completeness_fail_when_section_missing(llzo_packet: EvidencePacket) -> None:
    """Removing a required section must trigger a fail."""
    # Build a copy with a section deleted (use model_copy + dict manipulation).
    sections_dump = {
        k: v.model_dump(mode="json") for k, v in llzo_packet.bundle.sections.items()
    }
    sections_dump.pop("alabos_recipe_only_protocol")
    # Recreate the packet with the section removed.
    payload = llzo_packet.model_dump(mode="json")
    payload["bundle"]["sections"] = sections_dump
    crippled = EvidencePacket.model_validate(payload)
    item = packet_completeness(crippled)
    assert item.status == "fail"
    assert "alabos_recipe_only_protocol" in item.actual["missing"]


def test_packet_provenance_chain_pass_without_audit_log(llzo_packet: EvidencePacket) -> None:
    item = packet_provenance_chain(llzo_packet)
    assert item.status == "pass"


def test_packet_provenance_chain_fail_when_audit_record_id_blanked(
    llzo_packet: EvidencePacket,
) -> None:
    """Stripping audit_record_id from any envelope must trigger fail."""
    payload = llzo_packet.model_dump(mode="json")
    # Find a non-empty section, blank one envelope's audit_record_id.
    for section in payload["bundle"]["sections"].values():
        if section["envelopes"]:
            section["envelopes"][0]["audit"]["audit_record_id"] = ""
            break
    # The packet model itself round-trips OK because Envelope still validates
    # (audit_record_id is required by AuditBlock to match `^audit:..`); we cannot
    # actually serialise an empty audit_record_id through the model.
    # So instead we mutate the dict-form bundle directly and call the falsifier
    # on the Pydantic packet that exposes ``all_audit_record_ids`` via the
    # packet's bundle.sections envelope dicts.
    # Build a manual packet-like object whose bundle exposes a stripped envelope.
    pkt_dict = llzo_packet.model_dump(mode="json")
    # Replace one envelope's audit.audit_record_id with the empty string in the
    # ALREADY-VALIDATED packet payload, then construct a "shadow" view by
    # walking via the packet's sections directly. This dodges the Envelope
    # round-trip validator.
    target_section_name = next(
        name
        for name, sec in llzo_packet.bundle.sections.items()
        if sec.envelopes
    )
    section = llzo_packet.bundle.section(target_section_name)
    assert section is not None
    # Replace the section's envelopes via a shallow-mutation packet-like object.
    new_envs = copy.deepcopy(section.envelopes)
    new_envs[0]["audit"]["audit_record_id"] = ""
    # Build a manually-constructed PacketSection that bypasses Envelope.model_validate.
    # We mutate the in-memory section's envelopes list directly (PacketSection's
    # envelopes are a plain list[dict[str, Any]]; the EvidencePacket validator
    # already ran when the original was assembled, so this dodges it).
    object.__setattr__(section, "envelopes", new_envs)

    item = packet_provenance_chain(llzo_packet)
    assert item.status == "fail"
    assert target_section_name in item.actual["missing"]


def test_packet_boundary_carriage_pass(llzo_packet: EvidencePacket) -> None:
    item = packet_boundary_carriage(llzo_packet)
    assert item.status == "pass"


def test_packet_boundary_carriage_fail_on_top_level_change() -> None:
    """A packet with a non-verbatim top-level boundary fails the falsifier."""
    packet = assemble_battery_packet("LLZO")
    # We cannot mutate research_boundary through pydantic (it's validated);
    # but we CAN swap the in-memory attribute through __dict__ manipulation,
    # which is what an adversary modifying a serialised packet would look like.
    object.__setattr__(packet, "research_boundary", "NOT THE BOUNDARY")
    item = packet_boundary_carriage(packet)
    assert item.status == "fail"


def test_packet_promotion_gate_pass_battery(llzo_packet: EvidencePacket) -> None:
    item = packet_promotion_gate(llzo_packet)
    assert item.status == "pass"


def test_packet_promotion_gate_fail_when_ionic_section_truncated(
    llzo_packet: EvidencePacket,
) -> None:
    """Removing some ionic envelopes makes the gate fail (n != 6)."""
    section = llzo_packet.bundle.section("ionic_transport_full_evidence")
    assert section is not None
    object.__setattr__(section, "envelopes", section.envelopes[:3])
    item = packet_promotion_gate(llzo_packet)
    assert item.status == "fail"


def test_packet_ro_crate_round_trip_pass(llzo_packet: EvidencePacket, tmp_path: Path) -> None:
    item = packet_ro_crate_round_trip(llzo_packet, crate_dir=tmp_path)
    assert item.status == "pass"


def test_packet_publishable_target_pass(llzo_packet: EvidencePacket) -> None:
    item = packet_publishable_paper_target_set(llzo_packet)
    assert item.status == "pass"


def test_packet_alabos_recipe_only_section_pass(llzo_packet: EvidencePacket) -> None:
    item = packet_alabos_recipe_only_section(llzo_packet)
    assert item.status == "pass"


def test_packet_alabos_recipe_only_section_fail_on_hardware_executable(
    llzo_packet: EvidencePacket,
) -> None:
    """Mutate the AlabOS section to claim hardware_executable=True; falsifier fires."""
    section = llzo_packet.bundle.section("alabos_recipe_only_protocol")
    assert section is not None
    bad_payload = dict(section.raw_payload)
    bad_payload["hardware_executable"] = True
    object.__setattr__(section, "raw_payload", bad_payload)
    item = packet_alabos_recipe_only_section(llzo_packet)
    assert item.status == "fail"


def test_packet_alabos_recipe_only_section_vacuous_pass_for_thermoelectric() -> None:
    """Thermoelectric packets have no AlabOS section; falsifier vacuously passes."""
    from zer0pa_materials_workbench.packets import assemble_thermoelectric_packet

    p = assemble_thermoelectric_packet("Bi2Te3")
    item = packet_alabos_recipe_only_section(p)
    assert item.status == "pass"
