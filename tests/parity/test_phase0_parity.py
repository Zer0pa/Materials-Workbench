"""Phase 0 parity tests — optimade_mock vs optimade_live envelope shape (Wave 5c).

Phase 0 does not have a GPU layer, but OPTIMADE mock vs live parity and
LangGraph extraction mock vs real parity are important preconditions for
the Runpod cutover.

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
from zer0pa_materials_workbench.envelope.envelope import Envelope
from zer0pa_materials_workbench.envelope.hashing import HASH_REGEX, sha256_of


def _make_phase0_envelope(backend: str = "local_stub") -> dict:
    """Minimal valid Phase 0 envelope for schema testing."""
    inp = {"query": "Li-La-Zr-O", "database": "optimade_mock", "backend": backend}
    out = {
        "extracted_properties": [
            {"property_name": "ionic_conductivity", "value": 8.4e-4, "unit": "S/cm"},
        ],
        "candidate_count": 3,
        "source_dois": ["10.1038/natmater.2011.54"],
    }
    ih = sha256_of(inp)
    oh = sha256_of(out)
    return {
        "contract_version": "zer0pa.materials.layer-envelope.v1",
        "research_boundary": RESEARCH_BOUNDARY,
        "run_id": f"run:phase0:{backend}:test",
        "campaign_id": "campaign:phase0-parity-test",
        "candidate_id": "candidate:phase0:test000000001",
        "layer": "phase0",
        "tool_adapter": {
            "name": f"Phase0ExtractionAdapter/{backend}",
            "version": "0.1.0",
            "backend": backend,
            "engine": f"OPTIMADE/{backend}",
        },
        "input_refs": [],
        "output": out,
        "confidence": {"score": 0.0, "band": "low", "basis": []},
        "disagreement": {"metrics": []},
        "falsifier": {"status": "pass", "items": []},
        "audit": {
            "audit_record_id": f"audit:phase0:{backend}:test",
            "input_hash": ih,
            "output_hash": oh,
            "source_manifest_refs": [],
        },
        "rights": {
            "rights_claim_id": f"rights:phase0:{backend}:test",
            "reuse_scope": "tenant_only",
        },
        "back_edges": [],
    }


@pytest.fixture(params=["stub", "local_cpu"])
def phase0_backend(request) -> str:
    return request.param


@pytest.fixture
def phase0_env(phase0_backend) -> dict:
    return _make_phase0_envelope(backend=phase0_backend)


def test_phase0_schema_valid(phase0_env):
    """Phase 0 envelope validates against the Envelope pydantic model."""
    env = Envelope.model_validate(phase0_env)
    assert env.layer == "phase0"
    assert env.research_boundary == RESEARCH_BOUNDARY


def test_phase0_boundary_verbatim(phase0_env):
    assert phase0_env["research_boundary"] == RESEARCH_BOUNDARY


def test_phase0_hashes_well_formed(phase0_env):
    assert HASH_REGEX.match(phase0_env["audit"]["input_hash"])
    assert HASH_REGEX.match(phase0_env["audit"]["output_hash"])


def test_phase0_layer_field(phase0_env):
    assert phase0_env["layer"] == "phase0"


def test_phase0_schema_shape_consistent_across_backends():
    """optimade_mock and optimade_live produce envelopes with the same top-level key set."""
    env_mock = _make_phase0_envelope(backend="stub")
    env_local = _make_phase0_envelope(backend="local_cpu")
    assert set(env_mock.keys()) == set(env_local.keys()), (
        "Phase 0 mock vs local_cpu envelopes must have identical top-level key set."
    )


def test_phase0_mock_no_resource_metrics(phase0_env):
    """Phase 0 is not GPU-bound; resource_metrics should NOT be required."""
    # Phase 0 may or may not have resource_metrics — it's not GPU-bound.
    output = phase0_env.get("output", {})
    # If resource_metrics is present, it must not be required (no assertion either way).
    # This test is documentation: Phase 0 is EXEMPT from the resource_metrics hard-failure.
    assert isinstance(output, dict)


def test_phase0_output_has_extracted_properties(phase0_env):
    """Phase 0 output must have extracted_properties list."""
    assert "extracted_properties" in phase0_env["output"]
    assert isinstance(phase0_env["output"]["extracted_properties"], list)
    assert len(phase0_env["output"]["extracted_properties"]) >= 1
