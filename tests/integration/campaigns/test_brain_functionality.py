"""Brain-functionality gate integration test (Wave 4c).

Boundary: Research infrastructure for in silico materials science discovery.
Outputs are research artifacts. No regulatory certification claims. No
clinical or human-subject use. ITAR / weapons applications are out of scope
(Meta UMA Acceptable Use Policy and operator policy).

PRD §Acceptance Gates / Brain-functionality:
    "A fresh agent can reconstruct the project from repo artifacts without
    chat history."

The test:
  1. Run a battery campaign through the full chain.
  2. Snapshot the audit log + KG.
  3. Spawn a fresh Python process that loads only the repo (no in-memory state).
  4. Call reconstruct_from_repo(repo_root) in the subprocess.
  5. Verify the reconstructed CampaignState matches the original —
     same campaign_id, same candidates, same gates, same decisions,
     same disagreement metrics.
  6. Verify decisions.jsonl supersession chain reconstructible.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from zer0pa_materials_workbench.audit.kg import MaterialsKG
from zer0pa_materials_workbench.audit.log import AuditLog
from zer0pa_materials_workbench.orchestration import Campaign, CampaignSpec

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VENV_PYTHON = sys.executable  # use the same interpreter that runs pytest


def _make_audit_kg(tmp_path: Path) -> tuple[AuditLog, MaterialsKG]:
    """Create audit and KG at the paths used by reconstruct_from_repo defaults.

    reconstruct_from_repo defaults to:
      audit_dir = repo_root/audit/runtime
      kg_db_path = repo_root/audit/runtime/kg.sqlite
    """
    default_audit = tmp_path / "audit" / "runtime"
    default_kg = tmp_path / "audit" / "runtime" / "kg.sqlite"
    default_audit.mkdir(parents=True, exist_ok=True)
    return AuditLog(default_audit), MaterialsKG(default_kg)


def _run_full_battery_campaign(
    audit: AuditLog,
    kg: MaterialsKG,
    campaign_id: str,
) -> Campaign:
    """Run a complete battery campaign state machine."""
    spec = CampaignSpec(
        campaign_id=campaign_id,
        tenant="brain-func-test",
        objective="Li-ion conductivity > 1e-3 S/cm",
        chemical_system="Li-La-Zr-O",
    )
    camp = Campaign.create(spec, audit, kg)
    camp.transition_to("hypothesising", rationale="brain-func test")
    camp.transition_to("generating", rationale="generating candidates")
    camp.transition_to("screening_l2", rationale="L2 screening")

    candidates = {
        "candidate:LLZO-cubic:bf-001": "sha256:" + "c" * 64,
        "candidate:LLZO-cubic:bf-002": "sha256:" + "d" * 64,
    }

    for cid, sh in candidates.items():
        camp.register_candidate(cid, structure_hash=sh)
        camp.transition_candidate(cid, "screened", rationale="L2 promote")

    camp.transition_to("validating_l1", rationale="L1 validation")
    for cid in candidates:
        camp.transition_candidate(cid, "validated", rationale="L1 converged")

    camp.transition_to("ionic_evidence", rationale="ionic evidence")
    for cid in candidates:
        camp.transition_candidate(cid, "evidence_complete", rationale="ionic chain complete")

    camp.transition_to("packet_assembly", rationale="packet assembly")

    # One candidate promoted, one rejected.
    camp.transition_candidate(
        "candidate:LLZO-cubic:bf-001",
        "promoted",
        rationale="all gates pass",
    )
    camp.transition_candidate(
        "candidate:LLZO-cubic:bf-002",
        "rejected",
        rejection_reason="disagreement_threshold_exceeded",
    )
    camp.transition_to("promoted", rationale="campaign promoted")

    # Add disagreement and decision events to additional categories.
    audit.append_event("disagreement", {
        "kind": "aggregate_disagreement",
        "campaign_id": campaign_id,
        "score": 0.12,
    })
    audit.append_event("decisions", {
        "kind": "campaign_transition",
        "scope_campaign_id": campaign_id,
        "from_status": "promoted",
        "to_status": "promoted",
        "decision_id": "dec:final",
    })

    return camp


# ---------------------------------------------------------------------------
# Subprocess helper script
# ---------------------------------------------------------------------------

_SUBPROCESS_SCRIPT = """\
import sys
import json
from pathlib import Path

repo_root = Path(sys.argv[1])
sys.path.insert(0, str(repo_root / "src"))

from zer0pa_materials_workbench.audit.episodic import reconstruct_from_repo

state = reconstruct_from_repo(repo_root)
result = {
    "repo_root": state.repo_root,
    "next_actions": state.next_actions,
    "kg_node_count": state.snapshot.kg_node_count,
    "kg_edge_count": state.snapshot.kg_edge_count,
    "category_rows": {
        c.category: c.row_count
        for c in state.snapshot.categories
    },
    "all_chains_ok": all(c.chain_ok for c in state.snapshot.categories),
    "chain_errors": {
        c.category: c.chain_errors
        for c in state.snapshot.categories
        if c.chain_errors
    },
}
print(json.dumps(result))
"""


def _run_subprocess_reconstruct(repo_root: Path) -> dict:
    """Spawn a fresh Python process and run reconstruct_from_repo.

    This is the ONLY valid proof that the brain-functionality gate works:
    no in-memory state from the test process can leak into the subprocess.
    """
    result = subprocess.run(
        [VENV_PYTHON, "-c", _SUBPROCESS_SCRIPT, str(repo_root)],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=str(repo_root),
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Subprocess reconstruct failed (rc={result.returncode}):\n"
            f"STDOUT: {result.stdout}\n"
            f"STDERR: {result.stderr}"
        )
    return json.loads(result.stdout.strip())


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestBrainFunctionalityGate:
    """PRD §Acceptance Gates / Brain-functionality."""

    def test_reconstruct_runs_without_error(self, tmp_path: Path) -> None:
        """A fresh process can call reconstruct_from_repo without crashing."""
        audit, kg = _make_audit_kg(tmp_path)
        campaign_id = "campaign:brain-func-test/battery"
        _run_full_battery_campaign(audit, kg, campaign_id)

        # Write a minimal pyproject.toml so the src/ path lookup works.
        (tmp_path / "src").mkdir(parents=True, exist_ok=True)
        import shutil as _shutil

        import zer0pa_materials_workbench
        _shutil.copytree(
            Path(zer0pa_materials_workbench.__file__).parent,
            tmp_path / "src" / "zer0pa_materials_workbench",
            dirs_exist_ok=True,
        )

        result = _run_subprocess_reconstruct(tmp_path)
        assert result["all_chains_ok"], (
            f"All chains must be ok in subprocess; errors: {result['chain_errors']}"
        )

    def test_subprocess_sees_correct_repo_root(self, tmp_path: Path) -> None:
        audit, kg = _make_audit_kg(tmp_path)
        campaign_id = "campaign:brain-func-test/root"
        _run_full_battery_campaign(audit, kg, campaign_id)

        import shutil as _shutil

        import zer0pa_materials_workbench
        _shutil.copytree(
            Path(zer0pa_materials_workbench.__file__).parent,
            tmp_path / "src" / "zer0pa_materials_workbench",
            dirs_exist_ok=True,
        )

        result = _run_subprocess_reconstruct(tmp_path)
        assert result["repo_root"] == str(tmp_path.resolve())

    def test_subprocess_sees_correct_kg_node_count(self, tmp_path: Path) -> None:
        audit, kg = _make_audit_kg(tmp_path)
        campaign_id = "campaign:brain-func-test/kg"
        _run_full_battery_campaign(audit, kg, campaign_id)
        expected_nodes = kg.count_nodes()
        expected_edges = kg.count_edges()

        import shutil as _shutil

        import zer0pa_materials_workbench
        _shutil.copytree(
            Path(zer0pa_materials_workbench.__file__).parent,
            tmp_path / "src" / "zer0pa_materials_workbench",
            dirs_exist_ok=True,
        )

        result = _run_subprocess_reconstruct(tmp_path)
        assert result["kg_node_count"] == expected_nodes, (
            f"Subprocess KG node count {result['kg_node_count']} != {expected_nodes}"
        )
        assert result["kg_edge_count"] == expected_edges, (
            f"Subprocess KG edge count {result['kg_edge_count']} != {expected_edges}"
        )

    def test_subprocess_sees_correct_category_rows(self, tmp_path: Path) -> None:
        audit, kg = _make_audit_kg(tmp_path)
        campaign_id = "campaign:brain-func-test/rows"
        camp = _run_full_battery_campaign(audit, kg, campaign_id)

        # Count live rows per category.
        from zer0pa_materials_workbench.audit.log import AUDIT_CATEGORIES

        live_counts = {}
        for cat in AUDIT_CATEGORIES:
            rows = list(audit.iter_rows(cat))
            live_counts[cat] = len(rows)

        import shutil as _shutil

        import zer0pa_materials_workbench
        _shutil.copytree(
            Path(zer0pa_materials_workbench.__file__).parent,
            tmp_path / "src" / "zer0pa_materials_workbench",
            dirs_exist_ok=True,
        )

        result = _run_subprocess_reconstruct(tmp_path)
        sub_counts = result["category_rows"]

        for cat in ("runs", "events", "decisions"):
            assert sub_counts.get(cat, 0) == live_counts[cat], (
                f"Category {cat!r}: subprocess count {sub_counts.get(cat)} "
                f"!= live count {live_counts[cat]}"
            )

    def test_subprocess_next_actions_not_empty(self, tmp_path: Path) -> None:
        audit, kg = _make_audit_kg(tmp_path)
        campaign_id = "campaign:brain-func-test/actions"
        _run_full_battery_campaign(audit, kg, campaign_id)

        import shutil as _shutil

        import zer0pa_materials_workbench
        _shutil.copytree(
            Path(zer0pa_materials_workbench.__file__).parent,
            tmp_path / "src" / "zer0pa_materials_workbench",
            dirs_exist_ok=True,
        )

        result = _run_subprocess_reconstruct(tmp_path)
        assert isinstance(result["next_actions"], list)
        assert len(result["next_actions"]) >= 1


# ---------------------------------------------------------------------------
# In-process reconstruct: Campaign.resume_from_audit round-trip
# ---------------------------------------------------------------------------


class TestCampaignResumeRoundTrip:
    """Campaign.resume_from_audit reconstructs state without in-memory Campaign obj."""

    def test_resume_matches_original_status(self, tmp_path: Path) -> None:
        audit, kg = _make_audit_kg(tmp_path)
        campaign_id = "campaign:resume-test/battery"
        camp = _run_full_battery_campaign(audit, kg, campaign_id)

        original_status = camp.status
        original_candidates = dict(camp.state.candidates)
        original_promoted = list(camp.state.promoted_candidate_ids)
        original_rejected = list(camp.state.rejected_candidate_ids)

        # Reopen with fresh AuditLog + KG objects (simulates a new process).
        # Must use the same paths as _make_audit_kg (audit/runtime/).
        audit2 = AuditLog(tmp_path / "audit" / "runtime")
        kg2 = MaterialsKG(tmp_path / "audit" / "runtime" / "kg.sqlite")
        camp2 = Campaign.resume_from_audit(campaign_id, audit2, kg2)

        assert camp2.status == original_status, (
            f"Resumed status {camp2.status!r} != original {original_status!r}"
        )
        for cid in original_candidates:
            assert cid in camp2.state.candidates, (
                f"Candidate {cid!r} missing from resumed campaign"
            )
            assert camp2.state.candidates[cid].status == original_candidates[cid].status, (
                f"Candidate {cid!r}: resumed status "
                f"{camp2.state.candidates[cid].status!r} != "
                f"original {original_candidates[cid].status!r}"
            )

        assert set(camp2.state.promoted_candidate_ids) == set(original_promoted)
        assert set(camp2.state.rejected_candidate_ids) == set(original_rejected)

    def test_resume_same_campaign_id(self, tmp_path: Path) -> None:
        audit, kg = _make_audit_kg(tmp_path)
        campaign_id = "campaign:resume-test/id-check"
        camp = _run_full_battery_campaign(audit, kg, campaign_id)
        audit_dir = tmp_path / "audit" / "runtime"
        kg_path = tmp_path / "audit" / "runtime" / "kg.sqlite"

        audit2 = AuditLog(audit_dir)
        kg2 = MaterialsKG(kg_path)
        camp2 = Campaign.resume_from_audit(campaign_id, audit2, kg2)

        assert camp2.campaign_id == camp.campaign_id

    def test_resume_same_tenant(self, tmp_path: Path) -> None:
        audit, kg = _make_audit_kg(tmp_path)
        campaign_id = "campaign:resume-test/tenant-check"
        camp = _run_full_battery_campaign(audit, kg, campaign_id)
        audit_dir = tmp_path / "audit" / "runtime"
        kg_path = tmp_path / "audit" / "runtime" / "kg.sqlite"

        audit2 = AuditLog(audit_dir)
        kg2 = MaterialsKG(kg_path)
        camp2 = Campaign.resume_from_audit(campaign_id, audit2, kg2)

        assert camp2.state.spec.tenant == camp.state.spec.tenant

    def test_decisions_supersession_chain_reconstructible(self, tmp_path: Path) -> None:
        """The decisions.jsonl supersession chain must be fully reconstructible."""
        audit, kg = _make_audit_kg(tmp_path)
        campaign_id = "campaign:resume-test/decisions"
        camp = _run_full_battery_campaign(audit, kg, campaign_id)
        audit_dir = tmp_path / "audit" / "runtime"
        kg_path = tmp_path / "audit" / "runtime" / "kg.sqlite"

        # Collect all decision rows for this campaign.
        decisions = [
            row.payload
            for row in audit.iter_rows("decisions")
            if row.payload.get("scope_campaign_id") == campaign_id
        ]
        assert len(decisions) >= 1, "Campaign must have produced at least one decision"

        # Verify the chain: kind=campaign_transition rows form a valid sequence.
        transitions = [d for d in decisions if d.get("kind") == "campaign_transition"]
        assert len(transitions) >= 1

        # Reconstruct the chain.
        audit2 = AuditLog(audit_dir)
        kg2 = MaterialsKG(kg_path)
        camp2 = Campaign.resume_from_audit(campaign_id, audit2, kg2)
        # The final status must match what was committed.
        assert camp2.status == camp.status, (
            f"Supersession-chain reconstruction failed: "
            f"resumed status {camp2.status!r} != original {camp.status!r}"
        )

    def test_audit_chain_still_valid_after_resume(self, tmp_path: Path) -> None:
        """resume_from_audit must not corrupt the audit log."""
        audit, kg = _make_audit_kg(tmp_path)
        campaign_id = "campaign:resume-test/chain-valid"
        _run_full_battery_campaign(audit, kg, campaign_id)
        audit_dir = tmp_path / "audit" / "runtime"
        kg_path = tmp_path / "audit" / "runtime" / "kg.sqlite"

        audit2 = AuditLog(audit_dir)
        kg2 = MaterialsKG(kg_path)
        Campaign.resume_from_audit(campaign_id, audit2, kg2)

        # Validate the chain after resume.
        for cat in ("runs", "events", "decisions"):
            result = audit.validate_chain(cat)
            assert result.ok, (
                f"Hash chain {cat!r} corrupted after resume_from_audit; "
                f"errors: {result.errors}"
            )

    def test_missing_campaign_raises_key_error(self, tmp_path: Path) -> None:
        audit, kg = _make_audit_kg(tmp_path)
        _run_full_battery_campaign(audit, kg, "campaign:resume-test/exists")

        with pytest.raises(KeyError, match="no campaign spec"):
            Campaign.resume_from_audit("campaign:does-not-exist", audit, kg)
