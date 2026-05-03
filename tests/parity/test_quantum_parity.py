"""Quantum layer parity tests — local_stub vs runpod_mock (Wave 5c).

Covers PennyLane real-hardware (parked) vs runpod_mock backend.

Boundary (verbatim)
-------------------
Research infrastructure for in silico materials science discovery.
Outputs are research artifacts. No regulatory certification claims.
No clinical or human-subject use. ITAR / weapons applications are
out of scope (Meta UMA Acceptable Use Policy and operator policy).
"""

from __future__ import annotations

import pytest

from tests.parity.conftest import assert_envelope_schema_invariants
from zer0pa_materials_workbench.boundary import RESEARCH_BOUNDARY
from zer0pa_materials_workbench.runpod.mock_backends import build_runpod_mock_envelope

LAYER = "quantum"

QUANTUM_INPUTS = {
    "H2": {"molecule": "H2", "basis": "sto-3g", "n_electrons": 2},
    "LiH": {"molecule": "LiH", "basis": "sto-3g", "n_electrons": 4},
}


@pytest.fixture(params=list(QUANTUM_INPUTS.keys()))
def q_input(request) -> dict:
    return {**QUANTUM_INPUTS[request.param], "layer": LAYER}


@pytest.fixture
def q_mock_env(q_input) -> dict:
    return build_runpod_mock_envelope(
        layer=LAYER,
        input_payload=q_input,
        output_payload={
            "ground_state_energy_Ha": -1.8,
            "vqe_iterations": 250,
            "converged": True,
        },
    )


def test_quantum_schema_invariants(q_mock_env):
    assert_envelope_schema_invariants(q_mock_env, backend="runpod_mock")


def test_quantum_boundary(q_mock_env):
    assert q_mock_env["research_boundary"] == RESEARCH_BOUNDARY


def test_quantum_resource_metrics(q_mock_env):
    rm = q_mock_env["output"]["resource_metrics"]
    for key in ("gpu_seconds", "vram_mb", "wallclock_seconds"):
        assert key in rm and rm[key] > 0


def test_quantum_disagreement_metrics(q_mock_env):
    """Quantum layer must carry VQE-FCI disagreement metric."""
    metrics = q_mock_env["disagreement"]["metrics"]
    assert len(metrics) >= 1
    names = [m["name"] for m in metrics]
    assert any("vqe" in n or "fci" in n or "quantum" in n for n in names)


def test_quantum_deterministic_hash(q_input):
    env1 = build_runpod_mock_envelope(layer=LAYER, input_payload=q_input)
    env2 = build_runpod_mock_envelope(layer=LAYER, input_payload=q_input)
    assert env1["audit"]["input_hash"] == env2["audit"]["input_hash"]


def test_quantum_layer_field(q_mock_env):
    assert q_mock_env["layer"] == LAYER


def test_quantum_backend_literal(q_mock_env):
    assert q_mock_env["tool_adapter"]["backend"] == "runpod_mock"
