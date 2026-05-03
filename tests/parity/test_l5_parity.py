"""L5 FEM/CFD parity tests — local_stub vs runpod_mock (Wave 5c).

Covers FEniCSx / deal.II / OpenFOAM at production mesh vs runpod_mock.

Boundary (verbatim)
-------------------
Research infrastructure for in silico materials science discovery.
Outputs are research artifacts. No regulatory certification claims.
No clinical or human-subject use. ITAR / weapons applications are
out of scope (Meta UMA Acceptable Use Policy and operator policy).
"""

from __future__ import annotations

import pytest

from tests.parity.conftest import SEED_INPUTS, assert_envelope_schema_invariants
from zer0pa_materials_workbench.boundary import RESEARCH_BOUNDARY
from zer0pa_materials_workbench.envelope.hashing import HASH_REGEX
from zer0pa_materials_workbench.runpod.mock_backends import build_runpod_mock_envelope

LAYER = "L5"


@pytest.fixture(params=list(SEED_INPUTS.keys()))
def l5_input(request) -> dict:
    return {**SEED_INPUTS[request.param], "layer": LAYER}


@pytest.fixture
def l5_mock_env(l5_input) -> dict:
    return build_runpod_mock_envelope(
        layer=LAYER,
        input_payload=l5_input,
        output_payload={
            "von_mises_stress_MPa": 148.0,
            "displacement_max_um": 0.34,
            "converged": True,
        },
    )


def test_l5_schema_invariants(l5_mock_env):
    assert_envelope_schema_invariants(l5_mock_env, backend="runpod_mock")


def test_l5_boundary(l5_mock_env):
    assert l5_mock_env["research_boundary"] == RESEARCH_BOUNDARY


def test_l5_resource_metrics(l5_mock_env):
    rm = l5_mock_env["output"]["resource_metrics"]
    for k in ("gpu_seconds", "vram_mb", "wallclock_seconds"):
        assert k in rm and rm[k] > 0


def test_l5_disagreement_metrics(l5_mock_env):
    metrics = l5_mock_env["disagreement"]["metrics"]
    assert len(metrics) >= 1
    names = [m["name"] for m in metrics]
    assert any("fem" in n or "cfd" in n or "l5" in n or "stress" in n or "solver" in n for n in names)


def test_l5_deterministic_hash(l5_input):
    env1 = build_runpod_mock_envelope(layer=LAYER, input_payload=l5_input)
    env2 = build_runpod_mock_envelope(layer=LAYER, input_payload=l5_input)
    assert env1["audit"]["input_hash"] == env2["audit"]["input_hash"]


def test_l5_layer_field(l5_mock_env):
    assert l5_mock_env["layer"] == LAYER


def test_l5_backend(l5_mock_env):
    assert l5_mock_env["tool_adapter"]["backend"] == "runpod_mock"


def test_l5_hashes_well_formed(l5_mock_env):
    assert HASH_REGEX.match(l5_mock_env["audit"]["input_hash"])
    assert HASH_REGEX.match(l5_mock_env["audit"]["output_hash"])
