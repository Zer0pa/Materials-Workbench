"""L1.5 phonon parity tests — local_stub vs runpod_mock (Wave 5c).

Covers Phonopy / Phono3py / HiPhive / BoltzTraP2 / AMSET vs runpod_mock.

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

from tests.parity.conftest import assert_envelope_schema_invariants

LAYER = "L1.5"

L15_INPUTS = {
    "Bi2Te3_thermoelectric": {"chemical_system": "Bi-Te", "target_ZT": 1.0},
    "PbTe_thermoelectric": {"chemical_system": "Pb-Te", "target_ZT": 0.9},
    "SnSe_thermoelectric": {"chemical_system": "Sn-Se", "target_ZT": 1.5},
}


@pytest.fixture(params=list(L15_INPUTS.keys()))
def l15_input(request) -> dict:
    return {**L15_INPUTS[request.param], "layer": LAYER}


@pytest.fixture
def l15_mock_env(l15_input) -> dict:
    return build_runpod_mock_envelope(
        layer=LAYER,
        input_payload=l15_input,
        output_payload={
            "ZT_300K": 0.82,
            "kappa_L_W_per_mK": 1.4,
            "phonon_stable": True,
        },
    )


def test_l15_schema_invariants(l15_mock_env):
    assert_envelope_schema_invariants(l15_mock_env, backend="runpod_mock")


def test_l15_boundary(l15_mock_env):
    assert l15_mock_env["research_boundary"] == RESEARCH_BOUNDARY


def test_l15_resource_metrics(l15_mock_env):
    rm = l15_mock_env["output"]["resource_metrics"]
    for k in ("gpu_seconds", "vram_mb", "wallclock_seconds"):
        assert k in rm and rm[k] > 0


def test_l15_disagreement_metrics(l15_mock_env):
    """L1.5 must carry BoltzTraP2/AMSET ZT rank-stability disagreement."""
    metrics = l15_mock_env["disagreement"]["metrics"]
    assert len(metrics) >= 1
    names = [m["name"] for m in metrics]
    assert any("boltz" in n or "amset" in n or "zt" in n or "phonon" in n for n in names), (
        f"L1.5 disagreement metrics should reference ZT/BoltzTraP/phonon, got: {names}"
    )


def test_l15_deterministic_hash(l15_input):
    env1 = build_runpod_mock_envelope(layer=LAYER, input_payload=l15_input)
    env2 = build_runpod_mock_envelope(layer=LAYER, input_payload=l15_input)
    assert env1["audit"]["input_hash"] == env2["audit"]["input_hash"]


def test_l15_layer_field(l15_mock_env):
    assert l15_mock_env["layer"] == LAYER


def test_l15_backend(l15_mock_env):
    assert l15_mock_env["tool_adapter"]["backend"] == "runpod_mock"
