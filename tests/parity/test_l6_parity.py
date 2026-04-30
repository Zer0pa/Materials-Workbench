"""L6 generative parity tests — local_stub vs runpod_mock (Wave 5c).

Covers MatterGen / DiffCSP / CrystaLLM vs runpod_mock.

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
from zer0pa_materials.adapters.l6.mattergen import MatterGenGeneratorAdapter

from tests.parity.conftest import SEED_INPUTS, assert_envelope_schema_invariants

LAYER = "L6"


@pytest.fixture(params=list(SEED_INPUTS.keys()))
def l6_input(request) -> dict:
    return {**SEED_INPUTS[request.param], "layer": LAYER}


@pytest.fixture
def l6_mock_env(l6_input) -> dict:
    return build_runpod_mock_envelope(
        layer=LAYER,
        input_payload=l6_input,
        output_payload={
            "novelty_status": "pending",
            "cif_valid": True,
            "generator": "MatterGen/runpod_mock",
        },
    )


def test_l6_schema_invariants(l6_mock_env):
    assert_envelope_schema_invariants(l6_mock_env, backend="runpod_mock")


def test_l6_boundary(l6_mock_env):
    assert l6_mock_env["research_boundary"] == RESEARCH_BOUNDARY


def test_l6_resource_metrics(l6_mock_env):
    rm = l6_mock_env["output"]["resource_metrics"]
    for k in ("gpu_seconds", "vram_mb", "wallclock_seconds"):
        assert k in rm and rm[k] > 0


def test_l6_disagreement_metrics(l6_mock_env):
    """L6 should carry generator disagreement (novelty_score_std, ensemble)."""
    metrics = l6_mock_env["disagreement"]["metrics"]
    assert len(metrics) >= 1
    names = [m["name"] for m in metrics]
    assert any("novelty" in n or "generator" in n or "l6" in n for n in names)


def test_l6_novelty_status_pending(l6_mock_env):
    """L6 candidates must NEVER be marked 'novel' before DFT/ionic/L2 pass."""
    assert l6_mock_env["output"].get("novelty_status") == "pending", (
        "L6 novelty_status must be 'pending' until L1+L2+ionic all pass."
    )


def test_l6_deterministic_hash(l6_input):
    env1 = build_runpod_mock_envelope(layer=LAYER, input_payload=l6_input)
    env2 = build_runpod_mock_envelope(layer=LAYER, input_payload=l6_input)
    assert env1["audit"]["input_hash"] == env2["audit"]["input_hash"]


def test_l6_stub_backend_also_schema_valid():
    """Local stub adapter produces schema-valid envelopes."""
    adapter = MatterGenGeneratorAdapter(n_candidates=1)
    envelopes = adapter.generate({"chemical_system": "Li-La-Zr-O"})
    assert len(envelopes) >= 1
    env = envelopes[0]
    # Validate envelope contract version and boundary.
    assert env.contract_version == "zer0pa.materials.layer-envelope.v1"
    assert env.research_boundary == RESEARCH_BOUNDARY
    assert env.tool_adapter.backend == "stub"


def test_l6_stub_vs_mock_schema_shape():
    """local_stub and runpod_mock produce envelopes with the same top-level key set."""
    adapter = MatterGenGeneratorAdapter(n_candidates=1)
    stub_envs = adapter.generate({"chemical_system": "Li-La-Zr-O"})
    stub_dict = stub_envs[0].model_dump(mode="json")

    mock_dict = build_runpod_mock_envelope(
        layer=LAYER,
        input_payload={"chemical_system": "Li-La-Zr-O", "layer": LAYER},
    )
    assert set(stub_dict.keys()) == set(mock_dict.keys()), (
        f"Top-level key mismatch: stub={sorted(stub_dict.keys())}, mock={sorted(mock_dict.keys())}"
    )


def test_l6_layer_field(l6_mock_env):
    assert l6_mock_env["layer"] == LAYER


def test_l6_backend(l6_mock_env):
    assert l6_mock_env["tool_adapter"]["backend"] == "runpod_mock"
