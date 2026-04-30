"""Shared fixtures for parity tests (Wave 5c).

Parity tests assert:
    1. Same input → same envelope schema for local_stub and runpod_mock.
    2. Hash chain identical for deterministic stub seeding.
    3. tool_adapter.backend differs but is one of the allowed literals.
    4. Resource metrics present in runpod_mock; absent/zero in local_stub.
    5. Boundary block carried verbatim across all backends.

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
from zer0pa_materials.runpod.mock_backends import (
    build_runpod_mock_envelope,
    MOCK_RESOURCE_METRICS,
    RUNPOD_MOCK_LAYERS,
)


# ---------------------------------------------------------------------------
# Shared seed inputs (same inputs used for local_stub stubs AND runpod_mock)
# ---------------------------------------------------------------------------

SEED_INPUTS: dict[str, dict] = {
    "LLZO": {"chemical_system": "Li-La-Zr-O", "target_conductivity_S_per_cm": 1e-3},
    "Li6PS5Cl": {"chemical_system": "Li-P-S-Cl", "target_conductivity_S_per_cm": 5e-4},
    "Li_Mg_Zr_Cl": {"chemical_system": "Li-Mg-Zr-Cl", "target_conductivity_S_per_cm": 2e-3},
    "Bi2Te3": {"chemical_system": "Bi-Te", "target_ZT": 1.0},
}

ALLOWED_BACKENDS = frozenset({"stub", "local_cpu", "runpod_mock", "runpod_rest"})


@pytest.fixture(params=list(RUNPOD_MOCK_LAYERS))
def layer(request) -> str:
    return request.param


@pytest.fixture(params=list(SEED_INPUTS.keys()))
def seed_name(request) -> str:
    return request.param


@pytest.fixture
def seed_input(seed_name) -> dict:
    return SEED_INPUTS[seed_name]


@pytest.fixture
def runpod_mock_envelope(layer, seed_name) -> dict:
    """Build a runpod_mock envelope for the given layer and seed."""
    inp = {**SEED_INPUTS[seed_name], "layer": layer}
    return build_runpod_mock_envelope(layer=layer, input_payload=inp)


def assert_envelope_schema_invariants(env: dict, backend: str) -> None:
    """Assert that an envelope satisfies the universal schema invariants."""
    # Top-level keys.
    required_top = {
        "contract_version", "research_boundary", "run_id", "campaign_id",
        "candidate_id", "layer", "tool_adapter", "input_refs", "output",
        "confidence", "disagreement", "falsifier", "audit", "rights", "back_edges",
    }
    missing = required_top - set(env.keys())
    assert not missing, f"Missing top-level keys: {missing}"

    # Boundary.
    assert env["research_boundary"] == RESEARCH_BOUNDARY, "research_boundary mismatch"

    # tool_adapter.
    ta = env["tool_adapter"]
    assert ta["backend"] in ALLOWED_BACKENDS, f"backend {ta['backend']!r} not in allowed set"
    assert ta["backend"] == backend, f"backend {ta['backend']!r} != expected {backend!r}"

    # Hash fields.
    audit = env["audit"]
    assert HASH_REGEX.match(audit["input_hash"]), "input_hash malformed"
    assert HASH_REGEX.match(audit["output_hash"]), "output_hash malformed"

    # Resource metrics: present for runpod_* and absent/zero for local_stub.
    output = env.get("output", {})
    rm = output.get("resource_metrics", {})
    if backend.startswith("runpod_"):
        required_metrics = {"gpu_seconds", "vram_mb", "wallclock_seconds"}
        assert required_metrics.issubset(set(rm.keys())), (
            f"runpod backend missing resource_metrics keys: "
            f"{required_metrics - set(rm.keys())}"
        )
        for k in required_metrics:
            assert isinstance(rm[k], (int, float)) and rm[k] > 0, (
                f"resource_metrics[{k!r}] must be positive numeric"
            )
    else:
        # local_stub / local_cpu: resource_metrics absent or zero is fine.
        pass

    # Disagreement: MLIP/DFT layers must carry metrics.
    if env.get("layer") in ("L1", "L2", "ionic", "quantum"):
        metrics = env.get("disagreement", {}).get("metrics", [])
        assert metrics, f"Layer {env['layer']!r} must carry disagreement.metrics"
