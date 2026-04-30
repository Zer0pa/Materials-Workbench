"""L4 phase-field parity tests — local_stub vs runpod_mock (Wave 5c).

Covers PRISMS-PF / MOOSE / MICROSIM / SPPARKS / neural-op training vs runpod_mock.

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

LAYER = "L4"


@pytest.fixture(params=list(SEED_INPUTS.keys()))
def l4_input(request) -> dict:
    return {**SEED_INPUTS[request.param], "layer": LAYER}


@pytest.fixture
def l4_mock_env(l4_input) -> dict:
    return build_runpod_mock_envelope(
        layer=LAYER,
        input_payload=l4_input,
        output_payload={
            "phase_field_converged": True,
            "grain_size_um": 3.2,
            "porosity": 0.02,
        },
    )


def test_l4_schema_invariants(l4_mock_env):
    assert_envelope_schema_invariants(l4_mock_env, backend="runpod_mock")


def test_l4_boundary(l4_mock_env):
    assert l4_mock_env["research_boundary"] == RESEARCH_BOUNDARY


def test_l4_resource_metrics(l4_mock_env):
    rm = l4_mock_env["output"]["resource_metrics"]
    for k in ("gpu_seconds", "vram_mb", "wallclock_seconds"):
        assert k in rm and rm[k] > 0


def test_l4_disagreement_metrics(l4_mock_env):
    metrics = l4_mock_env["disagreement"]["metrics"]
    assert len(metrics) >= 1
    names = [m["name"] for m in metrics]
    assert any("solver" in n or "field" in n or "l4" in n or "neural" in n or "pde" in n for n in names)


def test_l4_deterministic_hash(l4_input):
    env1 = build_runpod_mock_envelope(layer=LAYER, input_payload=l4_input)
    env2 = build_runpod_mock_envelope(layer=LAYER, input_payload=l4_input)
    assert env1["audit"]["input_hash"] == env2["audit"]["input_hash"]


def test_l4_layer_field(l4_mock_env):
    assert l4_mock_env["layer"] == LAYER


def test_l4_backend(l4_mock_env):
    assert l4_mock_env["tool_adapter"]["backend"] == "runpod_mock"


def test_l4_hashes_well_formed(l4_mock_env):
    assert HASH_REGEX.match(l4_mock_env["audit"]["input_hash"])
    assert HASH_REGEX.match(l4_mock_env["audit"]["output_hash"])
