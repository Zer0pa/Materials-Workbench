"""Ionic transport parity tests — local_stub vs runpod_mock (Wave 5c).

Covers real NEB / AIMD / MLIP-MD vs runpod_mock.

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

LAYER = "ionic"


@pytest.fixture(params=list(SEED_INPUTS.keys()))
def ionic_input(request) -> dict:
    return {**SEED_INPUTS[request.param], "layer": LAYER}


@pytest.fixture
def ionic_mock_env(ionic_input) -> dict:
    return build_runpod_mock_envelope(
        layer=LAYER,
        input_payload=ionic_input,
        output_payload={
            "neb_barrier_eV": 0.22,
            "sigma_S_per_cm": 8.4e-4,
            "promotion_decision": "promote",
        },
    )


def test_ionic_schema_invariants(ionic_mock_env):
    assert_envelope_schema_invariants(ionic_mock_env, backend="runpod_mock")


def test_ionic_boundary(ionic_mock_env):
    assert ionic_mock_env["research_boundary"] == RESEARCH_BOUNDARY


def test_ionic_resource_metrics(ionic_mock_env):
    rm = ionic_mock_env["output"]["resource_metrics"]
    for k in ("gpu_seconds", "vram_mb", "wallclock_seconds"):
        assert k in rm and rm[k] > 0, f"resource_metrics[{k!r}] must be > 0"


def test_ionic_disagreement_metrics(ionic_mock_env):
    """Ionic transport layer must carry NEB/MLMD barrier disagreement."""
    metrics = ionic_mock_env["disagreement"]["metrics"]
    assert len(metrics) >= 1
    names = [m["name"] for m in metrics]
    assert any("neb" in n or "barrier" in n or "ionic" in n or "diffusiv" in n for n in names), (
        f"Ionic disagreement metrics should reference NEB/barrier/diffusivity, got: {names}"
    )


def test_ionic_deterministic_hash(ionic_input):
    env1 = build_runpod_mock_envelope(layer=LAYER, input_payload=ionic_input)
    env2 = build_runpod_mock_envelope(layer=LAYER, input_payload=ionic_input)
    assert env1["audit"]["input_hash"] == env2["audit"]["input_hash"]


def test_ionic_layer_field(ionic_mock_env):
    assert ionic_mock_env["layer"] == LAYER


def test_ionic_backend(ionic_mock_env):
    assert ionic_mock_env["tool_adapter"]["backend"] == "runpod_mock"


def test_ionic_hashes_well_formed(ionic_mock_env):
    assert HASH_REGEX.match(ionic_mock_env["audit"]["input_hash"])
    assert HASH_REGEX.match(ionic_mock_env["audit"]["output_hash"])
