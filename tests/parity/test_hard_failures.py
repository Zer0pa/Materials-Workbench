"""Unit tests for all 10 HardFailureDetector methods (Wave 5c).

Each detector is tested for both the pass case and the fail case.
Adversarial inputs ensure the detector actually fires.

Boundary (verbatim)
-------------------
Research infrastructure for in silico materials science discovery.
Outputs are research artifacts. No regulatory certification claims.
No clinical or human-subject use. ITAR / weapons applications are
out of scope (Meta UMA Acceptable Use Policy and operator policy).
"""

from __future__ import annotations

import pytest

from zer0pa_materials_workbench.boundary import RESEARCH_BOUNDARY
from zer0pa_materials_workbench.runpod.hard_failures import HardFailureDetector
from zer0pa_materials_workbench.runpod.mock_backends import build_runpod_mock_envelope


@pytest.fixture
def detector() -> HardFailureDetector:
    return HardFailureDetector()


@pytest.fixture
def good_env() -> dict:
    inp = {"chemical_system": "Li-La-Zr-O", "layer": "L1"}
    return build_runpod_mock_envelope(layer="L1", input_payload=inp)


# ---------------------------------------------------------------------------
# 1. detect_schema_drift
# ---------------------------------------------------------------------------

def test_schema_drift_pass_self_comparison(detector, good_env):
    result = detector.detect_schema_drift(good_env, good_env)
    assert result.passed


def test_schema_drift_fail_missing_key(detector, good_env):
    bad_env = {k: v for k, v in good_env.items() if k != "research_boundary"}
    result = detector.detect_schema_drift(good_env, bad_env)
    assert not result.passed
    assert "research_boundary" in result.evidence


def test_schema_drift_fail_type_change(detector, good_env):
    bad_env = dict(good_env)
    bad_env["confidence"] = "not-a-dict"  # Was a dict
    result = detector.detect_schema_drift(good_env, bad_env)
    assert not result.passed


# ---------------------------------------------------------------------------
# 2. detect_missing_artifact_hashes
# ---------------------------------------------------------------------------

def test_missing_hashes_pass(detector, good_env):
    result = detector.detect_missing_artifact_hashes(good_env)
    assert result.passed


def test_missing_hashes_fail_absent(detector, good_env):
    bad = dict(good_env)
    bad["audit"] = {"audit_record_id": good_env["audit"]["audit_record_id"]}
    result = detector.detect_missing_artifact_hashes(bad)
    assert not result.passed
    assert "input_hash" in result.evidence or "output_hash" in result.evidence


def test_missing_hashes_fail_malformed(detector, good_env):
    bad = dict(good_env)
    bad["audit"] = dict(good_env["audit"])
    bad["audit"]["input_hash"] = "not-a-sha256-hash"
    result = detector.detect_missing_artifact_hashes(bad)
    assert not result.passed


# ---------------------------------------------------------------------------
# 3. detect_missing_boundary_block
# ---------------------------------------------------------------------------

def test_boundary_pass(detector, good_env):
    result = detector.detect_missing_boundary_block(good_env)
    assert result.passed


def test_boundary_fail_absent(detector):
    env = {"layer": "L1", "tool_adapter": {"backend": "runpod_mock"}}
    result = detector.detect_missing_boundary_block(env)
    assert not result.passed


def test_boundary_fail_wrong_text(detector, good_env):
    bad = dict(good_env)
    bad["research_boundary"] = "wrong boundary text"
    result = detector.detect_missing_boundary_block(bad)
    assert not result.passed


def test_boundary_fail_truncated(detector, good_env):
    bad = dict(good_env)
    bad["research_boundary"] = RESEARCH_BOUNDARY[:20]
    result = detector.detect_missing_boundary_block(bad)
    assert not result.passed


# ---------------------------------------------------------------------------
# 4. detect_missing_resource_metrics
# ---------------------------------------------------------------------------

def test_resource_metrics_pass_runpod_mock(detector, good_env):
    result = detector.detect_missing_resource_metrics(good_env)
    assert result.passed


def test_resource_metrics_pass_local_stub(detector, good_env):
    stub_env = dict(good_env)
    stub_env["tool_adapter"] = {**good_env["tool_adapter"], "backend": "stub"}
    result = detector.detect_missing_resource_metrics(stub_env)
    assert result.passed  # local_stub is exempt


def test_resource_metrics_fail_runpod_missing(detector, good_env):
    bad = dict(good_env)
    bad["output"] = {"no_resource_metrics_here": True}
    result = detector.detect_missing_resource_metrics(bad)
    assert not result.passed


def test_resource_metrics_fail_partial(detector, good_env):
    bad = dict(good_env)
    bad["output"] = {"resource_metrics": {"gpu_seconds": 10.0}}  # missing vram_mb
    result = detector.detect_missing_resource_metrics(bad)
    assert not result.passed


# ---------------------------------------------------------------------------
# 5. detect_caller_changes
# ---------------------------------------------------------------------------

def test_caller_changes_pass_empty(detector):
    result = detector.detect_caller_changes("")
    assert result.passed


def test_caller_changes_pass_allowed_dirs(detector):
    git_status = "M services/l1_service.py\nA runpod/new_file.py"
    result = detector.detect_caller_changes(git_status)
    assert result.passed


def test_caller_changes_fail_forbidden_dir(detector):
    git_status = "M src/zer0pa_materials_workbench/adapters/l1/pyscf.py"
    result = detector.detect_caller_changes(git_status)
    assert not result.passed
    assert "pyscf.py" in result.evidence or "src" in result.evidence


def test_caller_changes_fail_multiple(detector):
    git_status = "M envelope/envelope.py\nM adapters/l2/mace.py"
    result = detector.detect_caller_changes(git_status)
    assert not result.passed


# ---------------------------------------------------------------------------
# 6. detect_lost_audit_provenance
# ---------------------------------------------------------------------------

def test_audit_provenance_pass(detector, good_env):
    result = detector.detect_lost_audit_provenance(good_env)
    assert result.passed


def test_audit_provenance_fail_no_id(detector, good_env):
    bad = dict(good_env)
    bad["audit"] = {k: v for k, v in good_env["audit"].items() if k != "audit_record_id"}
    result = detector.detect_lost_audit_provenance(bad)
    assert not result.passed


def test_audit_provenance_fail_malformed_id(detector, good_env):
    bad = dict(good_env)
    bad["audit"] = dict(good_env["audit"])
    bad["audit"]["audit_record_id"] = "wrong-prefix:l1:abc"
    result = detector.detect_lost_audit_provenance(bad)
    assert not result.passed


def test_audit_provenance_fail_not_in_log(detector, good_env):
    log = [{"audit_record_id": "audit:other:abc"}]
    result = detector.detect_lost_audit_provenance(good_env, audit_log=log)
    assert not result.passed


def test_audit_provenance_pass_in_log(detector, good_env):
    log = [{"audit_record_id": good_env["audit"]["audit_record_id"]}]
    result = detector.detect_lost_audit_provenance(good_env, audit_log=log)
    assert result.passed


# ---------------------------------------------------------------------------
# 7. detect_model_response_without_disagreement
# ---------------------------------------------------------------------------

def test_disagreement_pass_l1_has_metrics(detector, good_env):
    result = detector.detect_model_response_without_disagreement(good_env)
    assert result.passed


def test_disagreement_pass_l6_not_required(detector):
    inp = {"chemical_system": "Li-La-Zr-O", "layer": "L6"}
    env = build_runpod_mock_envelope(layer="L6", input_payload=inp)
    # L6 is not in the required set for this detector, so it should pass even with metrics.
    result = detector.detect_model_response_without_disagreement(env)
    assert result.passed


def test_disagreement_fail_l1_no_metrics(detector, good_env):
    bad = dict(good_env)
    bad["disagreement"] = {"metrics": []}
    result = detector.detect_model_response_without_disagreement(bad)
    assert not result.passed


def test_disagreement_fail_l2_no_metrics(detector):
    inp = {"chemical_system": "Li-La-Zr-O", "layer": "L2"}
    env = build_runpod_mock_envelope(layer="L2", input_payload=inp)
    bad = dict(env)
    bad["disagreement"] = {"metrics": []}
    result = detector.detect_model_response_without_disagreement(bad)
    assert not result.passed


def test_disagreement_fail_no_numeric_value(detector, good_env):
    bad = dict(good_env)
    bad["disagreement"] = {"metrics": [{"name": "test", "value": None}]}
    result = detector.detect_model_response_without_disagreement(bad)
    assert not result.passed


# ---------------------------------------------------------------------------
# 8. detect_uma_without_hf_aup_gate
# ---------------------------------------------------------------------------

def test_uma_pass_non_uma_engine(detector, good_env):
    result = detector.detect_uma_without_hf_aup_gate(good_env, hf_org=None, hf_token=None)
    # L1 engine is not UMA.
    assert result.passed


def test_uma_pass_with_hf_credentials(detector, good_env):
    bad = dict(good_env)
    bad["tool_adapter"] = {**good_env["tool_adapter"], "engine": "UMA/FAIR-Chemistry"}
    result = detector.detect_uma_without_hf_aup_gate(bad, hf_org="MyOrg", hf_token="hf_abc123")
    assert result.passed


def test_uma_fail_missing_org(detector, good_env):
    bad = dict(good_env)
    bad["tool_adapter"] = {**good_env["tool_adapter"], "engine": "UMA/FAIR-Chemistry"}
    result = detector.detect_uma_without_hf_aup_gate(bad, hf_org=None, hf_token="hf_abc123")
    assert not result.passed
    assert "UMA_HF_ORG" in result.evidence


def test_uma_fail_missing_token(detector, good_env):
    bad = dict(good_env)
    bad["tool_adapter"] = {**good_env["tool_adapter"], "engine": "UMA/FAIR-Chemistry"}
    result = detector.detect_uma_without_hf_aup_gate(bad, hf_org="MyOrg", hf_token=None)
    assert not result.passed
    assert "UMA_HF_TOKEN" in result.evidence


def test_uma_fail_both_missing(detector, good_env):
    bad = dict(good_env)
    bad["tool_adapter"] = {**good_env["tool_adapter"], "engine": "UMA/FAIR-Chemistry"}
    result = detector.detect_uma_without_hf_aup_gate(bad, hf_org=None, hf_token=None)
    assert not result.passed


# ---------------------------------------------------------------------------
# 9. detect_bulk_datasets_locally
# ---------------------------------------------------------------------------

def test_bulk_datasets_pass_empty_dir(detector, tmp_path):
    result = detector.detect_bulk_datasets_locally(tmp_path)
    assert result.passed


def test_bulk_datasets_pass_small_files(detector, tmp_path):
    (tmp_path / "small.py").write_text("x = 1", encoding="utf-8")
    result = detector.detect_bulk_datasets_locally(tmp_path)
    assert result.passed


def test_bulk_datasets_fail_large_file(detector, tmp_path):
    # Write a 6 MB file (above the 5 MB threshold).
    (tmp_path / "big.npy").write_bytes(b"0" * (6 * 1024 * 1024))
    result = detector.detect_bulk_datasets_locally(tmp_path)
    assert not result.passed
    assert "big.npy" in result.evidence


def test_bulk_datasets_pass_in_fixtures_dir(detector, tmp_path):
    # Files under fixtures/ are exempt.
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    (fixtures / "big.cif").write_bytes(b"0" * (6 * 1024 * 1024))
    result = detector.detect_bulk_datasets_locally(tmp_path)
    assert result.passed


# ---------------------------------------------------------------------------
# 10. detect_falsifier_bypass
# ---------------------------------------------------------------------------

def test_falsifier_bypass_pass_pre_gate_layer(detector, good_env):
    """L1 is pre-gate; bypass check is skipped."""
    result = detector.detect_falsifier_bypass(good_env)
    assert result.passed


def test_falsifier_bypass_pass_l3_with_back_edges(detector):
    inp = {"chemical_system": "Li-La-Zr-O", "layer": "L3"}
    env = build_runpod_mock_envelope(layer="L3", input_payload=inp)
    # Add back_edges for all required layers.
    env["back_edges"] = [
        {"layer": "L1", "audit_record_id": "audit:l1:abc", "relation": "DERIVED_FROM"},
        {"layer": "L2", "audit_record_id": "audit:l2:abc", "relation": "DERIVED_FROM"},
        {"layer": "ionic", "audit_record_id": "audit:ionic:abc", "relation": "DERIVED_FROM"},
    ]
    result = detector.detect_falsifier_bypass(env)
    assert result.passed


def test_falsifier_bypass_fail_l3_no_back_edges(detector):
    inp = {"chemical_system": "Li-La-Zr-O", "layer": "L3"}
    env = build_runpod_mock_envelope(layer="L3", input_payload=inp)
    # No back_edges → bypass detected.
    env["back_edges"] = []
    result = detector.detect_falsifier_bypass(env)
    assert not result.passed
    assert "L1" in result.evidence or "L2" in result.evidence or "ionic" in result.evidence


def test_falsifier_bypass_pass_l3_with_kg(detector):
    inp = {"chemical_system": "Li-La-Zr-O", "layer": "L3"}
    env = build_runpod_mock_envelope(layer="L3", input_payload=inp)
    env["back_edges"] = []
    candidate_id = env["candidate_id"]
    kg = {candidate_id: {"completed_layers": ["L1", "L2", "ionic"]}}
    result = detector.detect_falsifier_bypass(env, kg=kg)
    assert result.passed


def test_falsifier_bypass_pass_rejected_candidate(detector):
    """A rejected candidate (falsifier.status != 'pass') skips bypass check."""
    inp = {"chemical_system": "Li-La-Zr-O", "layer": "L3"}
    env = build_runpod_mock_envelope(layer="L3", input_payload=inp)
    env["falsifier"] = {"status": "fail", "items": []}
    env["back_edges"] = []  # Would normally trigger bypass
    result = detector.detect_falsifier_bypass(env)
    assert result.passed  # Not promoted, so bypass doesn't apply
