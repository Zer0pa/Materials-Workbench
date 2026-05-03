"""Test the Campaign state machine + audit-log resume protocol."""

from __future__ import annotations

from pathlib import Path

import pytest

from zer0pa_materials_workbench.audit.kg import KGNodeType, MaterialsKG
from zer0pa_materials_workbench.audit.log import AuditLog
from zer0pa_materials_workbench.orchestration import Campaign, CampaignSpec


@pytest.fixture
def fresh_kg_and_audit(tmp_path: Path) -> tuple[AuditLog, MaterialsKG]:
    return (AuditLog(tmp_path / "audit"), MaterialsKG(tmp_path / "kg.sqlite"))


def _spec() -> CampaignSpec:
    return CampaignSpec(
        campaign_id="campaign:test/mvp",
        tenant="test",
        objective="Li-ion conductivity > 1e-3 S/cm",
        chemical_system="Li-La-Zr-O",
    )


def test_create_writes_run_row_and_kg_nodes(fresh_kg_and_audit):
    audit, kg = fresh_kg_and_audit
    camp = Campaign.create(_spec(), audit, kg)
    rows = list(audit.iter_rows("runs"))
    assert any(r.payload.get("campaign_id") == camp.campaign_id for r in rows)
    # KG: tenant + campaign + acceptance gate placeholder
    assert kg.get_node(camp.campaign_id) is not None
    assert kg.get_node("tenant:test") is not None
    assert kg.get_node(f"gate:{camp.campaign_id}:promotion") is not None


def test_transition_writes_decision_row(fresh_kg_and_audit):
    audit, kg = fresh_kg_and_audit
    camp = Campaign.create(_spec(), audit, kg)
    decisions_before = sum(1 for _ in audit.iter_rows("decisions"))
    camp.transition_to("hypothesising", rationale="ready")
    decisions_after = sum(1 for _ in audit.iter_rows("decisions"))
    assert decisions_after == decisions_before + 1
    # Last decision is a campaign_transition.
    last = list(audit.iter_rows("decisions"))[-1]
    assert last.payload["kind"] == "campaign_transition"
    assert last.payload["from_status"] == "created"
    assert last.payload["to_status"] == "hypothesising"


def test_illegal_transition_raises(fresh_kg_and_audit):
    audit, kg = fresh_kg_and_audit
    camp = Campaign.create(_spec(), audit, kg)
    with pytest.raises(ValueError, match="illegal campaign transition"):
        camp.transition_to("packet_assembly")


def test_register_candidate_emits_kg_nodes(fresh_kg_and_audit):
    audit, kg = fresh_kg_and_audit
    camp = Campaign.create(_spec(), audit, kg)
    cid = "candidate:test/c1"
    camp.register_candidate(cid, structure_hash="sha256:" + "a" * 64)
    assert kg.get_node(cid) is not None
    assert kg.get_node(f"hypothesis:{cid}") is not None


def test_candidate_transition_writes_decision(fresh_kg_and_audit):
    audit, kg = fresh_kg_and_audit
    camp = Campaign.create(_spec(), audit, kg)
    cid = "candidate:test/c1"
    camp.register_candidate(cid)
    camp.transition_candidate(cid, "screened", rationale="L2 promote")
    last = list(audit.iter_rows("decisions"))[-1]
    assert last.payload["kind"] == "candidate_transition"
    assert last.payload["candidate_id"] == cid
    assert last.payload["to_status"] == "screened"


def test_candidate_illegal_transition_raises(fresh_kg_and_audit):
    audit, kg = fresh_kg_and_audit
    camp = Campaign.create(_spec(), audit, kg)
    cid = "candidate:test/c1"
    camp.register_candidate(cid)
    with pytest.raises(ValueError, match="illegal candidate transition"):
        camp.transition_candidate(cid, "promoted")


def test_rejected_candidate_added_to_rejection_set(fresh_kg_and_audit):
    audit, kg = fresh_kg_and_audit
    camp = Campaign.create(_spec(), audit, kg)
    cid = "candidate:test/c1"
    sh = "sha256:" + "a" * 64
    camp.register_candidate(cid, structure_hash=sh)
    camp.transition_candidate(cid, "rejected", rejection_reason="hard_reject_at_L2")
    assert cid in camp.rejected_set()
    assert sh in camp.rejected_hash_set()


def test_resume_from_audit_reconstructs_campaign(fresh_kg_and_audit, tmp_path: Path):
    audit, kg = fresh_kg_and_audit
    camp = Campaign.create(_spec(), audit, kg)
    camp.transition_to("hypothesising", rationale="test")
    camp.transition_to("generating", rationale="ok")
    cid = "candidate:test/c1"
    camp.register_candidate(cid, structure_hash="sha256:" + "b" * 64)
    camp.transition_candidate(cid, "screened", rationale="L2 promote")
    # Reopen audit + KG.
    audit2 = AuditLog(tmp_path / "audit")
    kg2 = MaterialsKG(tmp_path / "kg.sqlite")
    camp2 = Campaign.resume_from_audit(camp.campaign_id, audit2, kg2)
    assert camp2.status == "generating"
    assert camp2.candidate(cid).status == "screened"


def test_resume_from_audit_missing_campaign_raises(fresh_kg_and_audit):
    audit, kg = fresh_kg_and_audit
    with pytest.raises(KeyError, match="no campaign spec"):
        Campaign.resume_from_audit("campaign:does-not-exist", audit, kg)


def test_attach_envelope_records_layer_audit_ref(fresh_kg_and_audit):
    """Attaching an envelope writes an events.jsonl row and updates the candidate."""
    from zer0pa_materials_workbench.adapters.l7 import PrefectCampaignAdapter
    from zer0pa_materials_workbench.adapters.l7.base import L7CampaignParams

    audit, kg = fresh_kg_and_audit
    camp = Campaign.create(_spec(), audit, kg)
    cid = "candidate:test/c1"
    camp.register_candidate(cid)
    adapter = PrefectCampaignAdapter()
    params = L7CampaignParams(campaign_id=camp.campaign_id, candidate_id=cid)
    env = adapter.execute(params)
    camp.attach_envelope(env)
    rec = camp.candidate(cid)
    assert "L7" in rec.layer_audit_refs
    # Reconstruct.
    camp2 = Campaign.resume_from_audit(camp.campaign_id, audit, kg)
    assert "L7" in camp2.candidate(cid).layer_audit_refs


def test_decision_kg_nodes_routed_to(fresh_kg_and_audit):
    audit, kg = fresh_kg_and_audit
    camp = Campaign.create(_spec(), audit, kg)
    camp.transition_to("hypothesising", rationale="test")
    # Find the latest Decision node.
    decision_nodes = [n for n in kg.iter_nodes() if n.node_type == KGNodeType.Decision]
    assert len(decision_nodes) >= 2  # bootstrap + transition
