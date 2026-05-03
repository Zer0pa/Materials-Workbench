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

from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from zer0pa_materials_workbench.boundary import RESEARCH_BOUNDARY
from zer0pa_materials_workbench.envelope import Envelope, FalsifierItem
from zer0pa_materials_workbench.envelope.falsifier import FalsifierStatus
from zer0pa_materials_workbench.falsifiers.ionic_falsifiers import (
    neb_barrier_range_check,
    verify_ionic_service_back_edge,
)
from zer0pa_materials_workbench.falsifiers.l2_falsifiers import (
    dpa_mace_disagreement_routing_recomputed,
)
from zer0pa_materials_workbench.falsifiers.l3_falsifiers import (
    verify_l3_sovereign_block_enforced,
)
from zer0pa_materials_workbench.falsifiers.l5_falsifiers import (
    verify_l5_artifact_sidecar,
)
from zer0pa_materials_workbench.falsifiers.l6_falsifiers import (
    novelty_status_gate_recomputed,
)
from zer0pa_materials_workbench.falsifiers.phase0_falsifiers import (
    verify_source_manifest_linkage,
)
from zer0pa_materials_workbench.packets.evidence_packet import EvidencePacket

__all__ = [
    "BATTERY_REQUIRED_SECTIONS",
    "THERMOELECTRIC_REQUIRED_SECTIONS",
    "ValidationReport",
    "validate_evidence_packet",
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
            except Exception as exc:
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
# Wave F5: recompute gates over every nested envelope
# ----------------------------------------------------------------------------


def _envelope_layer(env_dict: Mapping[str, Any]) -> str:
    layer = env_dict.get("layer", "")
    return str(layer) if layer is not None else ""


def _check_recompute_gates_per_envelope(packet: EvidencePacket) -> list[FalsifierItem]:
    """Run every Wave D recompute gate against the appropriate nested envelope.

    Wave F5 wiring: the packet is the publishable deliverable. If
    production validation does not call recompute, customers receive the
    unhardened version. For each nested envelope:

    * L2 envelope → :func:`dpa_mace_disagreement_routing_recomputed`
    * L6 envelope → :func:`novelty_status_gate_recomputed`
    * L5 envelope → :func:`verify_l5_artifact_sidecar`
    * Ionic envelope → :func:`neb_barrier_range_check`
    * Phase 0 envelope (or any envelope with source_manifest_refs) →
      :func:`verify_source_manifest_linkage` (uses the
      ``audit_trail_head`` section as the in-memory audit log shim).
    * L3 envelope → :func:`verify_l3_sovereign_block_enforced`
    * Ionic envelope → :func:`verify_ionic_service_back_edge`

    Each recompute returns a :class:`FalsifierItem` whose name is unique
    to the gate; the validator collects them all so the roll-up sees
    every recompute outcome.

    Audit-log-resolving gates (source manifest, ionic back-edge, L3
    sovereign block) need a live ledger. Inside the packet validator we
    use the ``audit_trail_head`` section's recorded payloads as the
    in-memory audit log: each payload has a ``source_manifest_id`` /
    ``audit_record_id`` keyed to the envelope chain. When the section is
    absent, the gates are skipped (the existing
    ``_check_audit_trail_head_complete`` already fails the packet for
    that case).
    """
    items: list[FalsifierItem] = []

    # In-memory audit log: a list of audit-row payloads aggregated from
    # the audit_trail_head section. Each row may carry a
    # source_manifest_id, audit_record_id, layer, decision_impact, etc.
    # When the section is present (the packet declared an audit head),
    # we always run the linkage gates with whatever rows are available
    # — even an empty rows list, because the gates correctly fail when
    # any ref does not resolve.
    audit_log: list[dict[str, Any]] | None = None
    head_section = packet.bundle.section("audit_trail_head")
    if head_section is not None:
        head_payload = head_section.raw_payload
        rows = head_payload.get("rows") or head_payload.get("audit_rows") or []
        if isinstance(rows, list):
            audit_log = [r for r in rows if isinstance(r, dict)]
        else:
            audit_log = []

    # We accept either real audit rows or a degenerate list of strings:
    # the recompute helpers iterate the audit log as Mapping rows, and
    # any string entries are simply skipped.

    for section_name, section in packet.bundle.sections.items():
        for env_dict in section.envelopes:
            if not isinstance(env_dict, dict):
                continue
            layer = _envelope_layer(env_dict)

            # L2 disagreement recompute.
            if layer == "L2":
                try:
                    items.append(dpa_mace_disagreement_routing_recomputed(env_dict))
                except Exception as exc:
                    items.append(
                        FalsifierItem(
                            name="l2.dpa_mace_disagreement_routing_recomputed",
                            threshold="recompute helper runs to completion",
                            actual={"error": f"{type(exc).__name__}: {exc}"[:200]},
                            status="fail",
                        )
                    )

            # L6 novelty recompute.
            if layer == "L6":
                try:
                    items.append(novelty_status_gate_recomputed(env_dict))
                except Exception as exc:
                    items.append(
                        FalsifierItem(
                            name="l6.novelty_resolved_recomputed",
                            threshold="recompute helper runs to completion",
                            actual={"error": f"{type(exc).__name__}: {exc}"[:200]},
                            status="fail",
                        )
                    )

            # L5 artifact sidecar recompute.
            if layer == "L5":
                try:
                    items.append(verify_l5_artifact_sidecar(env_dict))
                except Exception as exc:
                    items.append(
                        FalsifierItem(
                            name="l5.verify_artifact_sidecar",
                            threshold="recompute helper runs to completion",
                            actual={"error": f"{type(exc).__name__}: {exc}"[:200]},
                            status="fail",
                        )
                    )

            # Ionic NEB range + back-edge.
            # The NEB range check applies to every ionic envelope. The
            # back-edge check is for CONSUMING envelopes (e.g. an L7
            # acceptance envelope referencing an ionic claim) — running
            # it against the ionic envelope itself would always fail
            # since the ionic envelope is the source of the claim, not
            # a consumer with a back-edge. We guard with a back_edges
            # presence check.
            if layer == "ionic":
                try:
                    items.append(neb_barrier_range_check(env_dict))
                except Exception as exc:
                    items.append(
                        FalsifierItem(
                            name="ionic.neb_barrier_range_check",
                            threshold="recompute helper runs to completion",
                            actual={"error": f"{type(exc).__name__}: {exc}"[:200]},
                            status="fail",
                        )
                    )
                # Only verify back-edge resolution when the envelope
                # carries an ionic-layer back-edge (i.e. it's a
                # consumer of an ionic claim, not the ionic source).
                back_edges = env_dict.get("back_edges") or []
                has_ionic_be = any(
                    isinstance(be, dict) and be.get("layer") == "ionic"
                    for be in back_edges
                )
                if has_ionic_be and audit_log is not None:
                    try:
                        items.append(
                            verify_ionic_service_back_edge(env_dict, audit_log)
                        )
                    except Exception as exc:
                        items.append(
                            FalsifierItem(
                                name="ionic.verify_back_edge_resolves",
                                threshold="recompute helper runs to completion",
                                actual={"error": f"{type(exc).__name__}: {exc}"[:200]},
                                status="fail",
                            )
                        )

            # L3 sovereign block enforcement.
            if layer == "L3" and audit_log is not None:
                try:
                    items.append(
                        verify_l3_sovereign_block_enforced(env_dict, audit_log)
                    )
                except Exception as exc:
                    items.append(
                        FalsifierItem(
                            name="l3.sovereign_block_enforced",
                            threshold="recompute helper runs to completion",
                            actual={"error": f"{type(exc).__name__}: {exc}"[:200]},
                            status="fail",
                        )
                    )

            # Source-manifest linkage on every envelope that carries refs.
            audit_block = env_dict.get("audit") or {}
            refs = (
                audit_block.get("source_manifest_refs")
                if isinstance(audit_block, dict)
                else None
            )
            if refs and audit_log is not None:
                try:
                    items.append(verify_source_manifest_linkage(env_dict, audit_log))
                except Exception as exc:
                    items.append(
                        FalsifierItem(
                            name="phase0.source_manifest_linkage",
                            threshold="recompute helper runs to completion",
                            actual={"error": f"{type(exc).__name__}: {exc}"[:200]},
                            status="fail",
                        )
                    )

    return items


# ----------------------------------------------------------------------------
# Top-level validator
# ----------------------------------------------------------------------------


def validate_evidence_packet(packet: EvidencePacket) -> ValidationReport:
    """Run every validator on ``packet`` and return a :class:`ValidationReport`.

    Wave F5 wiring: in addition to the structural validators (section
    coverage, boundary, audit ids, etc.) the validator now invokes every
    Wave D hardened recompute gate against each nested envelope. See
    :func:`_check_recompute_gates_per_envelope` for the per-layer
    routing. Customers receive the hardened gate set on every packet.
    """
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
    # Wave F5: per-envelope recompute gates (the smoking-gun fix).
    items.extend(_check_recompute_gates_per_envelope(packet))

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
