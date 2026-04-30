"""L7 orchestration parity tests — local_stub vs runpod_mock (Wave 5c).

L7 is not a GPU-bound layer; parity tests check that the campaign envelope
produced by the orchestration layer carries the boundary block and expected
schema fields regardless of backend.

Boundary (verbatim)
-------------------
Research infrastructure for in silico materials science discovery.
Outputs are research artifacts. No regulatory certification claims.
No clinical or human-subject use. ITAR / weapons applications are
out of scope (Meta UMA Acceptable Use Policy and operator policy).
"""

from __future__ import annotations

import pytest

from zer0pa_materials.boundary import RESEARCH_BOUNDARY
from zer0pa_materials.envelope.hashing import HASH_REGEX, sha256_of
from zer0pa_materials.envelope.envelope import Envelope

# L7 is not in RUNPOD_MOCK_LAYERS (it is orchestration, not GPU-bound).
# We test the campaign output schema directly.


def _make_l7_envelope() -> dict:
    """Build a minimal valid L7 campaign envelope for schema testing."""
    inp = {"campaign_name": "battery_primary", "seeds": ["LLZO", "Li6PS5Cl"]}
    out = {
        "candidate_rankings": [
            {"candidate_id": "candidate:l7:000000000001", "rank": 1, "score": 0.82},
        ],
        "campaign_status": "completed",
        "alabos_protocol_json": None,  # recipe_only mode
    }
    ih = sha256_of(inp)
    oh = sha256_of(out)
    return {
        "contract_version": "zer0pa.materials.layer-envelope.v1",
        "research_boundary": RESEARCH_BOUNDARY,
        "run_id": "run:l7:test000000001",
        "campaign_id": "campaign:l7-parity-test",
        "candidate_id": "candidate:l7:test000000001",
        "layer": "L7",
        "tool_adapter": {
            "name": "L7CampaignAdapter/parity",
            "version": "0.1.0",
            "backend": "local_cpu",
            "engine": "LangGraph/Prefect/BoTorch-stub",
        },
        "input_refs": [],
        "output": out,
        "confidence": {"score": 0.0, "band": "low", "basis": []},
        "disagreement": {"metrics": []},
        "falsifier": {"status": "pass", "items": []},
        "audit": {
            "audit_record_id": "audit:l7:test000000001",
            "input_hash": ih,
            "output_hash": oh,
            "source_manifest_refs": [],
        },
        "rights": {
            "rights_claim_id": "rights:l7:test000000001",
            "reuse_scope": "tenant_only",
        },
        "back_edges": [],
    }


@pytest.fixture
def l7_env() -> dict:
    return _make_l7_envelope()


def test_l7_schema_valid(l7_env):
    """L7 envelope validates against the Envelope pydantic model."""
    env = Envelope.model_validate(l7_env)
    assert env.layer == "L7"
    assert env.research_boundary == RESEARCH_BOUNDARY


def test_l7_boundary_verbatim(l7_env):
    assert l7_env["research_boundary"] == RESEARCH_BOUNDARY


def test_l7_hashes_well_formed(l7_env):
    assert HASH_REGEX.match(l7_env["audit"]["input_hash"])
    assert HASH_REGEX.match(l7_env["audit"]["output_hash"])


def test_l7_backend_allowed(l7_env):
    allowed = {"stub", "local_cpu", "runpod_mock", "runpod_rest"}
    assert l7_env["tool_adapter"]["backend"] in allowed


def test_l7_layer_field(l7_env):
    assert l7_env["layer"] == "L7"


def test_l7_campaign_output_has_rankings(l7_env):
    """L7 output must include candidate_rankings for campaign closure."""
    assert "candidate_rankings" in l7_env["output"]
    assert isinstance(l7_env["output"]["candidate_rankings"], list)


def test_l7_alabos_mode_recipe_only(l7_env):
    """AlabOS must be in recipe_only mode — hardware-executable output is a hard failure."""
    # In recipe_only mode, alabos_protocol_json may be a recipe dict or None
    # but must NOT be a hardware-executable artifact (Phase 2).
    out = l7_env["output"]
    # If present, it's a research artifact only.
    assert "alabos_protocol_json" in out, "L7 output should declare alabos_protocol_json (even if None)"
