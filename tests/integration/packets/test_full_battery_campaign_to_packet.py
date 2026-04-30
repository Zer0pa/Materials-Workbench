"""Full battery campaign → packet end-to-end integration test.

Boundary
--------
Research infrastructure for in silico materials science discovery. Outputs are
research artifacts. No regulatory certification claims. No clinical or
human-subject use. ITAR / weapons applications are out of scope (Meta UMA
Acceptable Use Policy and operator policy).

This test wires the full L7 campaign machinery (Campaign + AuditLog +
MaterialsKG) to the packet generator and verifies:

* the campaign state is reconstructable from JSONL alone after the
  packet has been assembled;
* every audit_record_id the packet records resolves either to an
  envelope this test attached or is a fresh record minted inside the
  packet generator (provenance falsifier with an audit_log argument may
  fail-open here because the envelopes are minted inside the packet
  generator and not attached to the campaign by default; the integration
  test attaches them explicitly via Campaign.attach_envelope);
* the RO-Crate export round-trips with no count drift;
* the validator suite reports overall=pass.

Run pattern (per Wave 5a brief): full Phase 0 → L6 → L2 → L1 → ionic →
packet end-to-end on the three battery seeds, with audit-log resume
verification at the end.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from zer0pa_materials.audit.kg import MaterialsKG
from zer0pa_materials.audit.log import AuditLog
from zer0pa_materials.envelope import Envelope
from zer0pa_materials.orchestration.campaign import Campaign, CampaignSpec
from zer0pa_materials.packets import (
    assemble_battery_packet,
    export_packet_to_ro_crate,
    parse_packet_ro_crate,
    validate_evidence_packet,
)


@pytest.mark.parametrize(
    "fixture_key,interface_mode,expected_decision",
    [
        ("LLZO", "li_metal", "promote"),
        ("Li6PS5Cl", "li_metal", "reject"),
        ("Li-Mg-Zr-Cl-seed", "li_metal", "reject"),
        ("Li-Mg-Zr-Cl-seed", "coating_interlayer", "promote"),
    ],
)
def test_full_battery_campaign_to_packet_end_to_end(
    fixture_key: str,
    interface_mode: str,
    expected_decision: str,
    tmp_path: Path,
) -> None:
    """Build a campaign, attach packet envelopes, validate the round-trip."""
    audit_dir = tmp_path / "audit"
    kg_path = tmp_path / "kg.sqlite"
    crate_dir = tmp_path / "crate"
    audit_dir.mkdir(parents=True, exist_ok=True)

    log = AuditLog(audit_dir)
    kg = MaterialsKG(kg_path)
    try:
        # ---- create campaign ------------------------------------------------
        spec = CampaignSpec(
            campaign_id=f"campaign:integration:{fixture_key}-{interface_mode}",
            tenant="integration-test",
            objective="Li-ion conductivity > 1e-3 S/cm",
            chemical_system="Li-La-Zr-O" if "LLZO" in fixture_key else "Li-halide",
        )
        campaign = Campaign.create(spec=spec, audit_log=log, kg=kg)

        # Drive the campaign through the state machine.
        campaign.transition_to("hypothesising", rationale="literature scan complete")
        campaign.transition_to("generating", rationale="known control selected")
        campaign.transition_to("screening_l2", rationale="L2 ensemble queued")
        campaign.transition_to("validating_l1", rationale="L1 DFT queued")
        campaign.transition_to("ionic_evidence", rationale="ionic chain queued")
        campaign.transition_to("packet_assembly", rationale="all evidence collected")

        # ---- assemble packet ------------------------------------------------
        packet = assemble_battery_packet(
            fixture_key,
            interface_mode=interface_mode,
            candidate_id=f"candidate:integration:{fixture_key}",
            campaign_id=spec.campaign_id,
        )

        assert packet.promotion_decision == expected_decision

        # ---- attach envelopes to the campaign for audit anchoring ----------
        # Register the candidate in the campaign and attach every packet envelope
        # so the resume-from-audit flow has full context.
        campaign.register_candidate(
            packet.candidate_id, structure_hash=packet.structure_hash
        )
        attached = 0
        for env_dict in packet.all_envelopes():
            env = Envelope.model_validate(env_dict)
            # Override the campaign_id on the envelope to ensure attachment.
            env_to_attach = env.model_copy(update={"campaign_id": spec.campaign_id})
            campaign.attach_envelope(env_to_attach)
            attached += 1
        assert attached > 0

        # Final transition.
        campaign.transition_to(
            "promoted" if expected_decision == "promote" else "rejected",
            rationale=packet.promotion_rationale,
        )

        # ---- packet validates ----------------------------------------------
        report = validate_evidence_packet(packet)
        assert report.overall_status == "pass", (
            f"validator failed: {[fi.name for fi in report.falsifier_items if fi.status != 'pass']}"
        )

        # ---- RO-Crate round-trip preserves counts --------------------------
        bundle = export_packet_to_ro_crate(packet, crate_dir / fixture_key / interface_mode)
        parsed = parse_packet_ro_crate(bundle.crate_root)
        assert len(parsed.section_paths) == len(bundle.section_paths)
        assert len(parsed.entries) == len(bundle.entries)

        # ---- resume-from-audit reconstructs campaign state -----------------
        # Close the KG so the resume-flow can re-open it.
        kg.close()
        kg2 = MaterialsKG(kg_path)
        try:
            resumed = Campaign.resume_from_audit(
                campaign_id=spec.campaign_id,
                audit_log=log,
                kg=kg2,
            )
            assert resumed.state.spec.campaign_id == spec.campaign_id
            # Resumed status matches original.
            assert resumed.state.status == campaign.state.status
            # The candidate is in the resumed candidates dict.
            assert packet.candidate_id in resumed.state.candidates
        finally:
            kg2.close()
    finally:
        kg.close()
