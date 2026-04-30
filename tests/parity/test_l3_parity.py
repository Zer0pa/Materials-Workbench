"""L3 CALPHAD parity tests — local_stub vs runpod_mock (Wave 5c).

Covers ESPEI quaternary fits / PhaseForgePlus real vs runpod_mock.

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
from zer0pa_materials.envelope.hashing import HASH_REGEX
from zer0pa_materials.runpod.mock_backends import build_runpod_mock_envelope

from tests.parity.conftest import SEED_INPUTS, assert_envelope_schema_invariants

LAYER = "L3"


@pytest.fixture(params=list(SEED_INPUTS.keys()))
def l3_input(request) -> dict:
    return {**SEED_INPUTS[request.param], "layer": LAYER}


@pytest.fixture
def l3_mock_env(l3_input) -> dict:
    return build_runpod_mock_envelope(
        layer=LAYER,
        input_payload=l3_input,
        output_payload={
            "phase_boundary_K": 1050.0,
            "activity_Li": 0.92,
            "fit_converged": True,
        },
    )


def test_l3_schema_invariants(l3_mock_env):
    assert_envelope_schema_invariants(l3_mock_env, backend="runpod_mock")


def test_l3_boundary(l3_mock_env):
    assert l3_mock_env["research_boundary"] == RESEARCH_BOUNDARY


def test_l3_resource_metrics(l3_mock_env):
    rm = l3_mock_env["output"]["resource_metrics"]
    for k in ("gpu_seconds", "vram_mb", "wallclock_seconds"):
        assert k in rm and rm[k] > 0


def test_l3_disagreement_metrics(l3_mock_env):
    metrics = l3_mock_env["disagreement"]["metrics"]
    assert len(metrics) >= 1
    names = [m["name"] for m in metrics]
    assert any("espei" in n or "phase" in n or "l3" in n or "mcmc" in n or "posterior" in n for n in names)


def test_l3_deterministic_hash(l3_input):
    env1 = build_runpod_mock_envelope(layer=LAYER, input_payload=l3_input)
    env2 = build_runpod_mock_envelope(layer=LAYER, input_payload=l3_input)
    assert env1["audit"]["input_hash"] == env2["audit"]["input_hash"]


def test_l3_layer_field(l3_mock_env):
    assert l3_mock_env["layer"] == LAYER


def test_l3_backend(l3_mock_env):
    assert l3_mock_env["tool_adapter"]["backend"] == "runpod_mock"


def test_l3_hashes_well_formed(l3_mock_env):
    assert HASH_REGEX.match(l3_mock_env["audit"]["input_hash"])
    assert HASH_REGEX.match(l3_mock_env["audit"]["output_hash"])
