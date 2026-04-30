"""Full thermoelectric campaign → packet end-to-end integration test.

Boundary
--------
Research infrastructure for in silico materials science discovery. Outputs are
research artifacts. No regulatory certification claims. No clinical or
human-subject use. ITAR / weapons applications are out of scope (Meta UMA
Acceptable Use Policy and operator policy).

Same shape as the battery integration test, but for the thermoelectric
sidecar. The PRD §L1.5 ZT rank-stability gate fires (stub mode), so the
verdict is reject; the integration verifies the packet still makes it
through the validator suite and that the campaign state resumes from the
audit log alone.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from zer0pa_materials.audit.kg import MaterialsKG
from zer0pa_materials.audit.log import AuditLog
from zer0pa_materials.envelope import Envelope
from zer0pa_materials.orchestration.campaign import Campaign, CampaignSpec
from zer0pa_materials.packets import (
    assemble_thermoelectric_packet,
    export_packet_to_ro_crate,
    parse_packet_ro_crate,
    validate_evidence_packet,
)


@pytest.mark.parametrize("fixture_key", ["Si", "Bi2Te3", "PbTe", "SnSe"])
def test_full_thermoelectric_campaign_to_packet_end_to_end(
    fixture_key: str, tmp_path: Path
) -> None:
    audit_dir = tmp_path / "audit"
    kg_path = tmp_path / "kg.sqlite"
    crate_dir = tmp_path / "crate"
    audit_dir.mkdir(parents=True, exist_ok=True)

    log = AuditLog(audit_dir)
    kg = MaterialsKG(kg_path)
    try:
        spec = CampaignSpec(
            campaign_id=f"campaign:integration:thermoelectric:{fixture_key}",
            tenant="integration-test",
            objective="thermoelectric ZT > 1.5 at operating temperature",
            chemical_system="thermoelectric",
        )
        campaign = Campaign.create(spec=spec, audit_log=log, kg=kg)

        # Walk the campaign state machine.
        campaign.transition_to("hypothesising", rationale="literature scan")
        campaign.transition_to("generating", rationale="control selected")
        campaign.transition_to("screening_l2", rationale="L2 ensemble queued")
        campaign.transition_to("validating_l1", rationale="L1 DFT queued")
        # No ionic_evidence step for thermoelectric — go straight to packet_assembly.
        campaign.transition_to(
            "ionic_evidence", rationale="L1.5 ZT chain stands in for ionic"
        )
        campaign.transition_to("packet_assembly", rationale="ZT bundle complete")

        packet = assemble_thermoelectric_packet(
            fixture_key,
            candidate_id=f"candidate:integration:{fixture_key}",
            campaign_id=spec.campaign_id,
        )

        # Stub mode: rank stability fails -> reject (per L1.5 phase report).
        assert packet.promotion_decision == "reject"

        campaign.register_candidate(
            packet.candidate_id, structure_hash=packet.structure_hash
        )
        attached = 0
        for env_dict in packet.all_envelopes():
            env = Envelope.model_validate(env_dict)
            env_to_attach = env.model_copy(update={"campaign_id": spec.campaign_id})
            campaign.attach_envelope(env_to_attach)
            attached += 1
        assert attached > 0

        campaign.transition_to("rejected", rationale=packet.promotion_rationale)

        report = validate_evidence_packet(packet)
        assert report.overall_status == "pass"

        bundle = export_packet_to_ro_crate(packet, crate_dir / fixture_key)
        parsed = parse_packet_ro_crate(bundle.crate_root)
        assert len(parsed.section_paths) == len(bundle.section_paths)

        # Resume the campaign from the audit log alone.
        kg.close()
        kg2 = MaterialsKG(kg_path)
        try:
            resumed = Campaign.resume_from_audit(
                campaign_id=spec.campaign_id,
                audit_log=log,
                kg=kg2,
            )
            assert resumed.state.status == "rejected"
            assert packet.candidate_id in resumed.state.candidates
        finally:
            kg2.close()
    finally:
        kg.close()
