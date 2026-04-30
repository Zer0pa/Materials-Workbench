"""Falsification wave: promotion without audit provenance must fail the gate."""

from __future__ import annotations

import pytest

from zer0pa_materials.falsifiers.l7_falsifiers import candidate_promotion_provenance


def test_missing_audit_record_id_triggers_falsifier():
    env_dict = {
        "candidate_id": "candidate:test/x",
        "research_boundary": "_ignored_",
        "audit": {"audit_record_id": ""},  # missing
        "output": {"promotion_decision": "promote", "structure_hash": "sha256:" + "a" * 64},
        "falsifier": {"items": []},
        "disagreement": {"metrics": []},
    }
    item = candidate_promotion_provenance(
        env_dict,
        rejected_candidate_ids=set(),
        rejected_structure_hashes=set(),
        expected_disagreement_present=True,
        rights_compatible=True,
    )
    assert item.status == "fail"
    assert "missing_audit_record_id" in item.actual["failures"]


def test_audit_record_not_anchored_in_chain_fails():
    env_dict = {
        "candidate_id": "candidate:test/x",
        "research_boundary": "_ignored_",
        "audit": {"audit_record_id": "audit:test:loose"},
        "output": {"promotion_decision": "promote"},
        "falsifier": {"items": []},
        "disagreement": {"metrics": []},
    }
    # Provide a non-empty chain that does NOT include the record.
    item = candidate_promotion_provenance(
        env_dict,
        rejected_candidate_ids=set(),
        audit_provenance_chain={"audit:test:other"},
        expected_disagreement_present=True,
        rights_compatible=True,
    )
    assert item.status == "fail"
    assert "audit_record_id_not_anchored" in item.actual["failures"]
