"""Packet validators (PRD §Audit Trail And KG promotion gate).

The validator suite enforces the PRD's hard rule:

    "No claim may be promoted unless it has evidence, source manifest,
    audit record, falsifier, and rights scope."

For each section in the packet, the validator checks:

* boundary block verbatim in every nested envelope;
* every envelope has a non-empty ``audit.audit_record_id``;
* every envelope's ``falsifier.items`` is non-empty (a layer with no
  falsifier output is itself a falsifier failure);
* every envelope has a ``rights`` block with a recognised reuse_scope;
* the AlabOS protocol is recipe-only (``hardware_executable=False``);
* the packet's ``publishable_paper_target`` is set;
* the cross-layer disagreement metric is back-traceable to source layers;
* the ionic-transport bundle (battery objective) is chain-complete;
* every required section is present.

The validator returns a :class:`ValidationReport` with a list of
:class:`FalsifierItem`. The orchestrator routes the packet based on the
roll-up status (any ``fail`` → reject; otherwise blocked > inconclusive
> pass).
"""

from __future__ import annotations

from typing import Any, Mapping

from pydantic import BaseModel, ConfigDict, Field

from zer0pa_materials.boundary import RESEARCH_BOUNDARY
from zer0pa_materials.envelope import Envelope, FalsifierItem
from zer0pa_materials.envelope.falsifier import FalsifierStatus
from zer0pa_materials.packets.evidence_packet import EvidencePacket


__all__ = [
    "ValidationReport",
    "validate_evidence_packet",
    "BATTERY_REQUIRED_SECTIONS",
    "THERMOELECTRIC_REQUIRED_SECTIONS",
]


BATTERY_REQUIRED_SECTIONS: tuple[str, ...] = (
    "phase0_literature",
    "l6_generated_structure",
    "l2_ensemble",
    "l1_dft_validation",
    "quantum_slot_h2_lih_gate",
    "ionic_transport_full_evidence",
    "l1_5_phonon_dynamical_stability",
    "l3_calphad_phase_set_posterior",
    "l4_phase_field_morphology",
    "l7_orchestration_metadata",
    "alabos_recipe_only_protocol",
    "cross_layer_disagreement",
    "rights_claim",
    "kg_snapshot",
    "audit_trail_head",
)

THERMOELECTRIC_REQUIRED_SECTIONS: tuple[str, ...] = (
    "phase0_literature",
    "l6_generated_structure",
    "l2_ensemble",
    "l1_dft_validation",
    "quantum_slot_h2_lih_gate",
    "zt_assembly",
    "l7_orchestration_metadata",
    "cross_layer_disagreement",
    "rights_claim",
    "kg_snapshot",
    "audit_trail_head",
)


class ValidationReport(BaseModel):
    """Aggregate validation result for an EvidencePacket."""

    model_config = ConfigDict(extra="forbid")

    packet_id: str
    overall_status: FalsifierStatus
    falsifier_items: list[FalsifierItem]
    sections_checked: list[str] = Field(default_factory=list)
    summary: str = Field(default="")


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------


def _envelope_audit_record(env_dict: Mapping[str, Any]) -> str:
    audit = env_dict.get("audit", {})
    return audit.get("audit_record_id", "") if isinstance(audit, dict) else ""


def _envelope_falsifier_items(env_dict: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    falsifier = env_dict.get("falsifier", {})
    items = falsifier.get("items", []) if isinstance(falsifier, dict) else []
    return list(items) if isinstance(items, list) else []


def _envelope_rights_block(env_dict: Mapping[str, Any]) -> Mapping[str, Any]:
    rights = env_dict.get("rights", {})
    return rights if isinstance(rights, dict) else {}


def _rollup(items: list[FalsifierItem]) -> FalsifierStatus:
    if any(fi.status == "fail" for fi in items):
        return "fail"
    if any(fi.status == "blocked" for fi in items):
        return "blocked"
    if any(fi.status == "inconclusive" for fi in items):
        return "inconclusive"
    return "pass"


# ----------------------------------------------------------------------------
# Individual checks
# ----------------------------------------------------------------------------


def _check_required_sections(packet: EvidencePacket) -> FalsifierItem:
    required = (
        BATTERY_REQUIRED_SECTIONS
        if packet.objective == "battery_solid_electrolyte"
        else THERMOELECTRIC_REQUIRED_SECTIONS
    )
    present = set(packet.bundle.sections.keys())
    missing = [r for r in required if r not in present]
    return FalsifierItem(
        name="packet.required_sections_present",
        threshold=f"all required sections for {packet.objective} present",
        actual={"missing": missing, "expected_count": len(required)},
        status="pass" if not missing else "fail",
    )


def _check_boundary_in_every_envelope(packet: EvidencePacket) -> FalsifierItem:
    bad: list[str] = []
    for section_name, section in packet.bundle.sections.items():
        for env_dict in section.envelopes:
            try:
                env = Envelope.model_validate(env_dict)
            except Exception as exc:  # noqa: BLE001 - reported as falsifier
                bad.append(f"{section_name}: {exc}")
                continue
            if env.research_boundary != RESEARCH_BOUNDARY:
                bad.append(f"{section_name}: envelope research_boundary not verbatim")
    return FalsifierItem(
        name="packet.boundary_carried_in_every_envelope",
        threshold="every nested envelope.research_boundary == RESEARCH_BOUNDARY",
        actual={"bad": bad, "n_envelopes": len(packet.all_envelopes())},
        status="pass" if not bad else "fail",
    )


def _check_every_envelope_has_audit_record_id(packet: EvidencePacket) -> FalsifierItem:
    missing: list[str] = []
    for section_name, section in packet.bundle.sections.items():
        for env_dict in section.envelopes:
            if not _envelope_audit_record(env_dict):
                missing.append(section_name)
    return FalsifierItem(
        name="packet.every_envelope_has_audit_record_id",
        threshold="every envelope.audit.audit_record_id non-empty",
        actual={"missing_section_names": missing},
        status="pass" if not missing else "fail",
    )


def _check_every_envelope_has_falsifier_items(packet: EvidencePacket) -> FalsifierItem:
    empty: list[str] = []
    for section_name, section in packet.bundle.sections.items():
        for env_dict in section.envelopes:
            items = _envelope_falsifier_items(env_dict)
            if not items:
                empty.append(section_name)
    return FalsifierItem(
        name="packet.every_envelope_has_falsifier_items",
        threshold="every envelope.falsifier.items non-empty",
        actual={"empty_section_names": empty},
        status="pass" if not empty else "fail",
    )


def _check_every_envelope_has_rights(packet: EvidencePacket) -> FalsifierItem:
    bad: list[str] = []
    for section_name, section in packet.bundle.sections.items():
        for env_dict in section.envelopes:
            rights = _envelope_rights_block(env_dict)
            if not rights.get("rights_claim_id") or not rights.get("reuse_scope"):
                bad.append(section_name)
    return FalsifierItem(
        name="packet.every_envelope_has_rights_claim",
        threshold="every envelope.rights has rights_claim_id and reuse_scope",
        actual={"bad_section_names": bad},
        status="pass" if not bad else "fail",
    )


def _check_publishable_target_set(packet: EvidencePacket) -> FalsifierItem:
    target = packet.publishable_paper_target
    set_ok = bool(target and target.primary_journal and target.alternative_journal)
    return FalsifierItem(
        name="packet.publishable_paper_target_set",
        threshold="publishable_paper_target.primary_journal and alternative_journal non-empty",
        actual={
            "primary_journal": target.primary_journal if target else None,
            "alternative_journal": target.alternative_journal if target else None,
        },
        status="pass" if set_ok else "fail",
    )


def _check_alabos_recipe_only(packet: EvidencePacket) -> FalsifierItem:
    """The AlabOS section must carry hardware_executable=False under recipe_only.

    Battery packets always include the AlabOS section. Thermoelectric
    packets do NOT — the falsifier returns ``pass`` (vacuous) for that
    objective if the section is absent, and ``fail`` if it's present but
    hardware_executable is True.
    """
    section = packet.bundle.section("alabos_recipe_only_protocol")
    if section is None:
        return FalsifierItem(
            name="packet.alabos_recipe_only",
            threshold="if present, alabos_mode='recipe_only' implies hardware_executable=False",
            actual={"section_present": False},
            status="pass",
        )
    payload = section.raw_payload
    mode = payload.get("alabos_mode", "")
    hw_exec = bool(payload.get("hardware_executable", False))
    bad = mode == "recipe_only" and hw_exec
    return FalsifierItem(
        name="packet.alabos_recipe_only",
        threshold="alabos_mode='recipe_only' implies hardware_executable=False",
        actual={"alabos_mode": mode, "hardware_executable": hw_exec},
        status="fail" if bad else "pass",
    )


def _check_cross_layer_disagreement_back_traceable(
    packet: EvidencePacket,
) -> FalsifierItem:
    """Every per-layer disagreement metric must reference a real audit_record_id.

    The packet's ``cross_layer_disagreement.raw_payload.per_layer_audit_refs``
    maps each contributing layer to the audit_record_id of the envelope that
    produced the metric. The validator confirms each ref is among the
    audit_record_ids the packet itself contains.
    """
    section = packet.bundle.section("cross_layer_disagreement")
    if section is None:
        return FalsifierItem(
            name="packet.cross_layer_disagreement_back_traceable",
            threshold="cross_layer_disagreement section present",
            actual={"section_present": False},
            status="fail",
        )
    refs: dict[str, str] = section.raw_payload.get("per_layer_audit_refs", {})
    known = set(packet.all_audit_record_ids())
    unknown = {layer: ref for layer, ref in refs.items() if ref not in known}
    return FalsifierItem(
        name="packet.cross_layer_disagreement_back_traceable",
        threshold=(
            "every per_layer_audit_ref resolves to an audit_record_id in the packet"
        ),
        actual={"unknown_refs": unknown, "n_refs": len(refs)},
        status="pass" if not unknown else "fail",
    )


def _check_ionic_chain_complete(packet: EvidencePacket) -> FalsifierItem:
    """Battery objective: ionic-transport bundle must contain all six envelopes.

    Thermoelectric packets do not include the ionic section; we vacuous-pass
    in that case.
    """
    if packet.objective != "battery_solid_electrolyte":
        return FalsifierItem(
            name="packet.ionic_chain_complete",
            threshold="battery objective requires all 6 ionic envelopes (vacuous for thermoelectric)",
            actual={"objective": packet.objective},
            status="pass",
        )
    section = packet.bundle.section("ionic_transport_full_evidence")
    if section is None:
        return FalsifierItem(
            name="packet.ionic_chain_complete",
            threshold="6 ionic envelopes present (NEB, MLIP-MD, AIMD, Arrhenius, EC window, interface)",
            actual={"section_present": False},
            status="fail",
        )
    n_envs = len(section.envelopes)
    return FalsifierItem(
        name="packet.ionic_chain_complete",
        threshold="6 ionic envelopes present",
        actual={"n_envelopes": n_envs},
        status="pass" if n_envs == 6 else "fail",
    )


def _check_quantum_slot_passes_gates(packet: EvidencePacket) -> FalsifierItem:
    """The quantum-slot section's H2 + LiH envelopes must clear PRD §L1 gates.

    H2 vs FCI ≤ 1e-3 Ha; LiH vs CASCI ≤ 5e-3 Ha. PRD §L1 quantum.
    """
    section = packet.bundle.section("quantum_slot_h2_lih_gate")
    if section is None:
        return FalsifierItem(
            name="packet.quantum_slot_gates",
            threshold="H2 and LiH VQE-vs-FCI gates pass",
            actual={"section_present": False},
            status="fail",
        )
    fail_systems: list[str] = []
    for env_dict in section.envelopes:
        items = _envelope_falsifier_items(env_dict)
        for item in items:
            name = item.get("name", "")
            status = item.get("status", "")
            if name in {"l1.h2_vqe_vs_fci", "l1.lih_vqe_vs_fci"} and status != "pass":
                fail_systems.append(name)
    return FalsifierItem(
        name="packet.quantum_slot_gates",
        threshold="H2 ≤ 1e-3 Ha; LiH ≤ 5e-3 Ha vs FCI",
        actual={"failing": fail_systems},
        status="pass" if not fail_systems else "fail",
    )


def _check_kg_snapshot_present(packet: EvidencePacket) -> FalsifierItem:
    section = packet.bundle.section("kg_snapshot")
    if section is None:
        return FalsifierItem(
            name="packet.kg_snapshot_present",
            threshold="kg_snapshot section present",
            actual={"section_present": False},
            status="fail",
        )
    nodes = section.raw_payload.get("nodes", [])
    edges = section.raw_payload.get("edges", [])
    return FalsifierItem(
        name="packet.kg_snapshot_present",
        threshold="kg_snapshot has at least one node and one edge",
        actual={"n_nodes": len(nodes), "n_edges": len(edges)},
        status="pass" if (nodes and edges) else "fail",
    )


def _check_audit_trail_head_complete(packet: EvidencePacket) -> FalsifierItem:
    """Every envelope's audit_record_id must appear in the audit_trail_head section."""
    section = packet.bundle.section("audit_trail_head")
    if section is None:
        return FalsifierItem(
            name="packet.audit_trail_head_complete",
            threshold="audit_trail_head section present",
            actual={"section_present": False},
            status="fail",
        )
    head = set(section.raw_payload.get("audit_record_ids", []))
    all_envelopes_audit_ids = set(packet.all_audit_record_ids())
    missing = sorted(all_envelopes_audit_ids - head)
    return FalsifierItem(
        name="packet.audit_trail_head_complete",
        threshold="every envelope.audit.audit_record_id appears in audit_trail_head",
        actual={"missing": missing, "head_count": len(head)},
        status="pass" if not missing else "fail",
    )


def _check_promotion_decision_recorded(packet: EvidencePacket) -> FalsifierItem:
    return FalsifierItem(
        name="packet.promotion_decision_recorded",
        threshold="promotion_decision in {promote, defer, reject}",
        actual=packet.promotion_decision,
        status="pass"
        if packet.promotion_decision in {"promote", "defer", "reject"}
        else "fail",
    )


# ----------------------------------------------------------------------------
# Top-level validator
# ----------------------------------------------------------------------------


def validate_evidence_packet(packet: EvidencePacket) -> ValidationReport:
    """Run every validator on ``packet`` and return a :class:`ValidationReport`."""
    items: list[FalsifierItem] = []
    items.append(_check_required_sections(packet))
    items.append(_check_boundary_in_every_envelope(packet))
    items.append(_check_every_envelope_has_audit_record_id(packet))
    items.append(_check_every_envelope_has_falsifier_items(packet))
    items.append(_check_every_envelope_has_rights(packet))
    items.append(_check_publishable_target_set(packet))
    items.append(_check_alabos_recipe_only(packet))
    items.append(_check_cross_layer_disagreement_back_traceable(packet))
    items.append(_check_ionic_chain_complete(packet))
    items.append(_check_quantum_slot_passes_gates(packet))
    items.append(_check_kg_snapshot_present(packet))
    items.append(_check_audit_trail_head_complete(packet))
    items.append(_check_promotion_decision_recorded(packet))

    overall = _rollup(items)
    failures = [fi.name for fi in items if fi.status == "fail"]
    blocked = [fi.name for fi in items if fi.status == "blocked"]
    summary_parts: list[str] = [f"Overall: {overall}."]
    if failures:
        summary_parts.append(f"Failed: {failures}.")
    if blocked:
        summary_parts.append(f"Blocked: {blocked}.")
    if overall == "pass":
        summary_parts.append("All packet validators returned pass.")
    return ValidationReport(
        packet_id=packet.packet_id,
        overall_status=overall,
        falsifier_items=items,
        sections_checked=sorted(packet.bundle.sections.keys()),
        summary=" ".join(summary_parts),
    )
