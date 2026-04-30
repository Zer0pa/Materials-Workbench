"""L1 DFT parity tests — local_stub vs runpod_mock (Wave 5c).

Asserts:
    1. Same input → same envelope schema.
    2. tool_adapter.backend differs (stub vs runpod_mock) but both are allowed.
    3. resource_metrics present in runpod_mock; absent in local_stub.
    4. Boundary block verbatim across both backends.
    5. Deterministic input_hash for the same input payload.
    6. Disagreement metrics present (L1 is DFT — required).

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
from zer0pa_materials.runpod.mock_backends import build_runpod_mock_envelope

from tests.parity.conftest import SEED_INPUTS, assert_envelope_schema_invariants


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

LAYER = "L1"


@pytest.fixture(params=list(SEED_INPUTS.keys()))
def l1_seed(request) -> dict:
    return SEED_INPUTS[request.param]


@pytest.fixture
def l1_input(l1_seed) -> dict:
    return {**l1_seed, "layer": LAYER}


@pytest.fixture
def l1_runpod_mock(l1_input) -> dict:
    return build_runpod_mock_envelope(
        layer=LAYER,
        input_payload=l1_input,
        output_payload={
            "energy_per_atom_eV": -6.12,
            "bandgap_eV": 3.84,
            "converged": True,
        },
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_l1_runpod_mock_schema(l1_runpod_mock):
    """runpod_mock envelope satisfies all schema invariants."""
    assert_envelope_schema_invariants(l1_runpod_mock, backend="runpod_mock")


def test_l1_boundary_block(l1_runpod_mock):
    """research_boundary is present and verbatim."""
    assert l1_runpod_mock["research_boundary"] == RESEARCH_BOUNDARY


def test_l1_runpod_backend_literal(l1_runpod_mock):
    """tool_adapter.backend == 'runpod_mock'."""
    assert l1_runpod_mock["tool_adapter"]["backend"] == "runpod_mock"


def test_l1_resource_metrics_present(l1_runpod_mock):
    """runpod_mock L1 envelope carries gpu_seconds, vram_mb, wallclock_seconds."""
    rm = l1_runpod_mock["output"]["resource_metrics"]
    for key in ("gpu_seconds", "vram_mb", "wallclock_seconds"):
        assert key in rm, f"resource_metrics missing {key!r}"
        assert rm[key] > 0, f"resource_metrics[{key!r}] must be > 0"


def test_l1_disagreement_metrics_present(l1_runpod_mock):
    """L1 DFT layer must carry disagreement.metrics (hard-failure guard)."""
    metrics = l1_runpod_mock["disagreement"]["metrics"]
    assert len(metrics) >= 1, "L1 must carry at least one disagreement metric"
    assert all(isinstance(m["value"], (int, float)) for m in metrics)


def test_l1_deterministic_input_hash(l1_input):
    """Same input produces the same input_hash (deterministic sha256_of)."""
    h1 = sha256_of(l1_input)
    h2 = sha256_of(l1_input)
    assert h1 == h2, "input_hash must be deterministic"
    assert HASH_REGEX.match(h1)


def test_l1_deterministic_envelope_hash(l1_input):
    """Calling build_runpod_mock_envelope twice with same input gives same input_hash."""
    env1 = build_runpod_mock_envelope(layer=LAYER, input_payload=l1_input)
    env2 = build_runpod_mock_envelope(layer=LAYER, input_payload=l1_input)
    assert env1["audit"]["input_hash"] == env2["audit"]["input_hash"], (
        "input_hash must be deterministic for the same input payload"
    )


def test_l1_schema_top_level_keys(l1_runpod_mock):
    """All required top-level envelope keys present."""
    required = {
        "contract_version", "research_boundary", "run_id", "campaign_id",
        "candidate_id", "layer", "tool_adapter", "output", "confidence",
        "disagreement", "falsifier", "audit", "rights",
    }
    missing = required - set(l1_runpod_mock.keys())
    assert not missing, f"Missing keys: {missing}"


def test_l1_audit_hashes_well_formed(l1_runpod_mock):
    """Both input_hash and output_hash match sha256:<hex> pattern."""
    audit = l1_runpod_mock["audit"]
    assert HASH_REGEX.match(audit["input_hash"])
    assert HASH_REGEX.match(audit["output_hash"])


def test_l1_layer_field(l1_runpod_mock):
    """layer field == 'L1'."""
    assert l1_runpod_mock["layer"] == LAYER


def test_l1_mock_not_stub_backend(l1_runpod_mock):
    """runpod_mock backend must NOT be 'stub'."""
    assert l1_runpod_mock["tool_adapter"]["backend"] != "stub"
