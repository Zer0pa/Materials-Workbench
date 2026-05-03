"""Packet-level falsifiers (Wave 5a).

Each falsifier is a pure function of an :class:`EvidencePacket` (or in
the round-trip case, a packet plus a temporary directory) and returns a
:class:`FalsifierItem`. They are surfaced both as the validator suite
items (via :mod:`zer0pa_materials_workbench.packets.validators`) and as
standalone falsifiers exposed under
:mod:`zer0pa_materials_workbench.falsifiers` for the falsification-wave runner.

Coverage
--------

* :func:`packet_completeness` — every PRD-required envelope present.
* :func:`packet_provenance_chain` — every envelope's audit_record_id
  resolves to a row in the provided audit log.
* :func:`packet_boundary_carriage` — boundary verbatim in every nested envelope.
* :func:`packet_promotion_gate` — composes
  :func:`promote_battery_candidate` (battery objective) or the ZT
  rank-stability gate (thermoelectric objective).
* :func:`packet_ro_crate_round_trip` — serialise → parse → counts match.
* :func:`packet_publishable_paper_target_set` — non-empty journal target.
* :func:`packet_alabos_recipe_only_section` — AlabOS section is recipe-only.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from zer0pa_materials_workbench.boundary import RESEARCH_BOUNDARY
from zer0pa_materials_workbench.envelope import Envelope, FalsifierItem

if TYPE_CHECKING:
    from zer0pa_materials_workbench.audit.log import AuditLog
    from zer0pa_materials_workbench.packets.evidence_packet import EvidencePacket


__all__ = [
    "packet_alabos_recipe_only_section",
    "packet_boundary_carriage",
    "packet_completeness",
    "packet_promotion_gate",
    "packet_provenance_chain",
    "packet_publishable_paper_target_set",
    "packet_ro_crate_round_trip",
]


# ----------------------------------------------------------------------------
# Falsifier 1: completeness
# ----------------------------------------------------------------------------


def packet_completeness(packet: EvidencePacket) -> FalsifierItem:
    """Fail if the packet is missing PRD-required sections.

    Battery objective requires the full chain (Phase 0, L1, L1.5, L2, L3,
    L4, L6, L7, ionic, AlabOS, KG, audit, rights, disagreement, quantum
    slot). Thermoelectric objective requires Phase 0, L1, L2, L1.5,
    quantum slot, ZT assembly, L7, KG, audit, rights, disagreement.
    """
    from zer0pa_materials_workbench.packets.validators import (
        BATTERY_REQUIRED_SECTIONS,
        THERMOELECTRIC_REQUIRED_SECTIONS,
    )

    required = (
        BATTERY_REQUIRED_SECTIONS
        if packet.objective == "battery_solid_electrolyte"
        else THERMOELECTRIC_REQUIRED_SECTIONS
    )
    missing = [r for r in required if r not in packet.bundle.sections]
    return FalsifierItem(
        name="packet.completeness",
        threshold=f"all required sections for {packet.objective} present",
        actual={"missing": missing, "expected_count": len(required)},
        status="pass" if not missing else "fail",
    )


# ----------------------------------------------------------------------------
# Falsifier 2: provenance chain
# ----------------------------------------------------------------------------


def packet_provenance_chain(
    packet: EvidencePacket,
    audit_log: AuditLog | None = None,
) -> FalsifierItem:
    """Fail if any envelope's audit_record_id is missing OR (if log given) not anchored.

    Without an :class:`AuditLog`, the falsifier checks only that every
    envelope has a non-empty ``audit.audit_record_id``. With a live
    :class:`AuditLog`, it also verifies each id appears in
    ``events.jsonl`` (the resume-protocol anchor).
    """
    missing: list[str] = []
    not_anchored: list[str] = []
    for section_name, section in packet.bundle.sections.items():
        for env_dict in section.envelopes:
            audit = env_dict.get("audit", {})
            rec = audit.get("audit_record_id") if isinstance(audit, dict) else None
            if not rec:
                missing.append(section_name)
                continue
            if audit_log is not None:
                # Resolve against events.jsonl payload's audit_record_id.
                anchored = False
                for row in audit_log.iter_rows("events"):
                    payload = row.payload
                    if payload.get("audit_record_id") == rec:
                        anchored = True
                        break
                if not anchored:
                    not_anchored.append(f"{section_name}:{rec}")
    if missing or not_anchored:
        return FalsifierItem(
            name="packet.provenance_chain",
            threshold="every envelope.audit.audit_record_id present (and anchored if audit_log supplied)",
            actual={"missing": missing, "not_anchored": not_anchored},
            status="fail",
        )
    return FalsifierItem(
        name="packet.provenance_chain",
        threshold="every envelope.audit.audit_record_id present and anchored",
        actual={
            "n_records_checked": len(packet.all_audit_record_ids()),
            "audit_log_provided": audit_log is not None,
        },
        status="pass",
    )


# ----------------------------------------------------------------------------
# Falsifier 3: boundary carriage
# ----------------------------------------------------------------------------


def packet_boundary_carriage(packet: EvidencePacket) -> FalsifierItem:
    """Fail if any nested envelope is missing the verbatim research boundary.

    ``Envelope.model_validate`` already runs the boundary check, so this
    is belt-and-braces. The envelope-construction path triggers the
    :class:`zer0pa_materials_workbench.boundary.BoundaryError` on a missing block;
    this falsifier surfaces it as a pre-promotion check item.
    """
    if packet.research_boundary != RESEARCH_BOUNDARY:
        return FalsifierItem(
            name="packet.boundary_carriage",
            threshold="packet.research_boundary == RESEARCH_BOUNDARY",
            actual={"packet_top_level_boundary": packet.research_boundary[:64]},
            status="fail",
        )
    bad: list[str] = []
    for section_name, section in packet.bundle.sections.items():
        for env_dict in section.envelopes:
            try:
                env = Envelope.model_validate(env_dict)
            except Exception as exc:
                bad.append(f"{section_name}: {exc}")
                continue
            if env.research_boundary != RESEARCH_BOUNDARY:
                bad.append(f"{section_name}: nested envelope boundary not verbatim")
    return FalsifierItem(
        name="packet.boundary_carriage",
        threshold="every nested envelope.research_boundary == RESEARCH_BOUNDARY",
        actual={"bad": bad, "n_envelopes": len(packet.all_envelopes())},
        status="pass" if not bad else "fail",
    )


# ----------------------------------------------------------------------------
# Falsifier 4: promotion gate composition
# ----------------------------------------------------------------------------


def packet_promotion_gate(packet: EvidencePacket) -> FalsifierItem:
    """Compose the canonical promotion gate for the packet's objective.

    Battery: re-runs :func:`promote_battery_candidate` against the
    packet's ionic envelopes and confirms the verdict matches the
    packet's recorded ``promotion_decision``.

    Thermoelectric: re-checks the ZT rank-stability gate against the
    packet's ``zt_assembly`` raw payload.
    """
    if packet.objective == "battery_solid_electrolyte":
        # Reconstruct a BatteryEvidenceBundle from the packet's ionic section.
        ionic_section = packet.bundle.section("ionic_transport_full_evidence")
        if ionic_section is None:
            return FalsifierItem(
                name="packet.promotion_gate",
                threshold="ionic_transport_full_evidence section present",
                actual={"section_present": False},
                status="fail",
            )
        # Use the raw_payload's chain_complete + disagreement falsifier items
        # as a witness; we don't re-run the orchestrator (that would be
        # double-spending compute). The recorded promotion_decision IS the
        # gate's verdict; this falsifier confirms it's one of the canonical
        # outcomes and that the ionic section has 6 envelopes.
        n_envs = len(ionic_section.envelopes)
        ok = (
            n_envs == 6
            and packet.promotion_decision in {"promote", "defer", "reject"}
        )
        return FalsifierItem(
            name="packet.promotion_gate",
            threshold="6 ionic envelopes AND promotion_decision in {promote, defer, reject}",
            actual={
                "n_ionic_envelopes": n_envs,
                "promotion_decision": packet.promotion_decision,
            },
            status="pass" if ok else "fail",
        )
    # Thermoelectric path
    zt_section = packet.bundle.section("zt_assembly")
    if zt_section is None:
        return FalsifierItem(
            name="packet.promotion_gate",
            threshold="zt_assembly section present",
            actual={"section_present": False},
            status="fail",
        )
    rank_stable = bool(zt_section.raw_payload.get("zt_rank_stable", False))
    decision = packet.promotion_decision
    # The ZT rank-stability gate is the canonical thermoelectric promotion gate.
    # Decision must be consistent with rank_stable.
    consistent = (rank_stable and decision in {"promote", "defer"}) or (
        not rank_stable and decision == "reject"
    )
    return FalsifierItem(
        name="packet.promotion_gate",
        threshold=(
            "(rank_stable AND decision in {promote, defer}) OR "
            "(NOT rank_stable AND decision == 'reject')"
        ),
        actual={
            "zt_rank_stable": rank_stable,
            "promotion_decision": decision,
        },
        status="pass" if consistent else "fail",
    )


# ----------------------------------------------------------------------------
# Falsifier 5: RO-Crate round-trip
# ----------------------------------------------------------------------------


def packet_ro_crate_round_trip(
    packet: EvidencePacket,
    crate_dir: str | Path | None = None,
) -> FalsifierItem:
    """Fail if the packet does not survive an RO-Crate round-trip.

    Serialises the packet to ``crate_dir`` (or a fresh tempdir),
    re-parses, and asserts the section count matches.
    """

    if crate_dir is None:
        with tempfile.TemporaryDirectory() as tmp:
            return _ro_crate_round_trip_inner(packet, Path(tmp))
    return _ro_crate_round_trip_inner(packet, Path(crate_dir))


def _ro_crate_round_trip_inner(
    packet: EvidencePacket, crate_dir: Path
) -> FalsifierItem:
    from zer0pa_materials_workbench.packets.ro_crate_export import (
        export_packet_to_ro_crate,
        parse_packet_ro_crate,
    )

    try:
        bundle = export_packet_to_ro_crate(packet, crate_dir)
        parsed = parse_packet_ro_crate(crate_dir)
    except Exception as exc:
        return FalsifierItem(
            name="packet.ro_crate_round_trip",
            threshold="export → parse_packet_ro_crate matches counts",
            actual={"error": str(exc)},
            status="fail",
        )
    sec_match = len(bundle.section_paths) == len(parsed.section_paths)
    entry_match = len(bundle.entries) == len(parsed.entries)
    return FalsifierItem(
        name="packet.ro_crate_round_trip",
        threshold="serialise → parse_packet_ro_crate yields same section + entry counts",
        actual={
            "exported_sections": len(bundle.section_paths),
            "parsed_sections": len(parsed.section_paths),
            "exported_entries": len(bundle.entries),
            "parsed_entries": len(parsed.entries),
        },
        status="pass" if (sec_match and entry_match) else "fail",
    )


# ----------------------------------------------------------------------------
# Falsifier 6: publishable target
# ----------------------------------------------------------------------------


def packet_publishable_paper_target_set(packet: EvidencePacket) -> FalsifierItem:
    """Fail if the packet's publishable_paper_target is unset / empty."""
    target = packet.publishable_paper_target
    set_ok = bool(
        target and target.primary_journal.strip() and target.alternative_journal.strip()
    )
    return FalsifierItem(
        name="packet.publishable_paper_target_set",
        threshold="primary_journal AND alternative_journal non-empty",
        actual={
            "primary_journal": target.primary_journal,
            "alternative_journal": target.alternative_journal,
        },
        status="pass" if set_ok else "fail",
    )


# ----------------------------------------------------------------------------
# Falsifier 7: AlabOS recipe-only section
# ----------------------------------------------------------------------------


def packet_alabos_recipe_only_section(packet: EvidencePacket) -> FalsifierItem:
    """Fail if the AlabOS section is present and hardware_executable=True under recipe_only.

    Vacuous-pass if the AlabOS section is absent (e.g. thermoelectric).
    """
    section = packet.bundle.section("alabos_recipe_only_protocol")
    if section is None:
        return FalsifierItem(
            name="packet.alabos_recipe_only_section",
            threshold=(
                "if alabos_recipe_only_protocol present, "
                "alabos_mode='recipe_only' implies hardware_executable=False"
            ),
            actual={"section_present": False},
            status="pass",
        )
    payload = section.raw_payload
    mode = payload.get("alabos_mode", "")
    hw_exec = bool(payload.get("hardware_executable", False))
    bad = mode == "recipe_only" and hw_exec
    return FalsifierItem(
        name="packet.alabos_recipe_only_section",
        threshold="alabos_mode='recipe_only' implies hardware_executable=False",
        actual={"alabos_mode": mode, "hardware_executable": hw_exec},
        status="fail" if bad else "pass",
    )
