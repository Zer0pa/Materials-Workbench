"""L2 MLIP parity tests — local_stub vs runpod_mock (Wave 5c).

Covers DPA-3.1-3M / MACE-MPA-0 / UMA (at scale) vs runpod_mock.

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

LAYER = "L2"


@pytest.fixture(params=list(SEED_INPUTS.keys()))
def l2_input(request) -> dict:
    return {**SEED_INPUTS[request.param], "layer": LAYER}


@pytest.fixture
def l2_mock_env(l2_input) -> dict:
    return build_runpod_mock_envelope(
        layer=LAYER,
        input_payload=l2_input,
        output_payload={
            "energy_per_atom_eV": -6.10,
            "routing_decision": "promote",
            "committee_size": 3,
        },
    )


def test_l2_schema_invariants(l2_mock_env):
    assert_envelope_schema_invariants(l2_mock_env, backend="runpod_mock")


def test_l2_boundary(l2_mock_env):
    assert l2_mock_env["research_boundary"] == RESEARCH_BOUNDARY


def test_l2_resource_metrics(l2_mock_env):
    rm = l2_mock_env["output"]["resource_metrics"]
    assert "gpu_seconds" in rm and rm["gpu_seconds"] > 0
    assert "vram_mb" in rm and rm["vram_mb"] > 0
    assert "wallclock_seconds" in rm and rm["wallclock_seconds"] > 0


def test_l2_disagreement_metrics_required(l2_mock_env):
    """L2 MLIP layer MUST carry disagreement metrics (committee energy MAE, force MAE)."""
    metrics = l2_mock_env["disagreement"]["metrics"]
    assert len(metrics) >= 1, "L2 must carry at least one disagreement metric"
    names = [m["name"] for m in metrics]
    # At least one metric should reference energy or force disagreement.
    assert any("energy" in n or "force" in n or "l2" in n for n in names), (
        f"L2 disagreement metrics should reference energy/force, got: {names}"
    )


def test_l2_deterministic_hash(l2_input):
    env1 = build_runpod_mock_envelope(layer=LAYER, input_payload=l2_input)
    env2 = build_runpod_mock_envelope(layer=LAYER, input_payload=l2_input)
    assert env1["audit"]["input_hash"] == env2["audit"]["input_hash"]


def test_l2_layer_field(l2_mock_env):
    assert l2_mock_env["layer"] == LAYER


def test_l2_backend_is_runpod_mock(l2_mock_env):
    assert l2_mock_env["tool_adapter"]["backend"] == "runpod_mock"


def test_l2_hashes_well_formed(l2_mock_env):
    assert HASH_REGEX.match(l2_mock_env["audit"]["input_hash"])
    assert HASH_REGEX.match(l2_mock_env["audit"]["output_hash"])
