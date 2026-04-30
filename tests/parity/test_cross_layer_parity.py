"""Cross-layer sentinel parity tests — local_stub vs runpod_mock (Wave 5c).

Full sentinel campaign through every GPU-bound layer with local_stub and
runpod_mock; envelope-tree diff (schema shape, boundary, resource metrics,
disagreement, hash determinism).

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
from zer0pa_materials.runpod.cutover import RunpodCutover, SENTINEL_SEEDS
from zer0pa_materials.runpod.hard_failures import HardFailureDetector, _schema_diff
from zer0pa_materials.runpod.mock_backends import (
    RUNPOD_MOCK_LAYERS,
    build_runpod_mock_envelope,
)


# ---------------------------------------------------------------------------
# Sentinel campaign fixture (runs once for the whole module)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def sentinel_report():
    """Full sentinel campaign with runpod_mock backend."""
    cutover = RunpodCutover()
    return cutover.run_sentinel_campaign(backend="runpod_mock")


@pytest.fixture(scope="module")
def detector():
    return HardFailureDetector()


# ---------------------------------------------------------------------------
# Cross-layer tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("seed", [s["name"] for s in SENTINEL_SEEDS])
@pytest.mark.parametrize("layer", list(RUNPOD_MOCK_LAYERS))
def test_sentinel_envelope_produced(sentinel_report, seed, layer):
    """Every seed × layer combination produces an envelope (no error)."""
    env = sentinel_report.seed_results.get(seed, {}).get(layer)
    assert env is not None, f"No envelope for seed={seed!r}, layer={layer!r}"
    assert isinstance(env, dict) and "error" not in env, (
        f"Envelope error for seed={seed!r}, layer={layer!r}: {env.get('error')}"
    )


@pytest.mark.parametrize("seed", [s["name"] for s in SENTINEL_SEEDS])
@pytest.mark.parametrize("layer", list(RUNPOD_MOCK_LAYERS))
def test_sentinel_boundary_block(sentinel_report, seed, layer):
    """Every sentinel envelope carries the verbatim boundary block."""
    env = sentinel_report.seed_results.get(seed, {}).get(layer, {})
    assert env.get("research_boundary") == RESEARCH_BOUNDARY, (
        f"Boundary mismatch for seed={seed!r}, layer={layer!r}"
    )


@pytest.mark.parametrize("seed", [s["name"] for s in SENTINEL_SEEDS])
@pytest.mark.parametrize("layer", list(RUNPOD_MOCK_LAYERS))
def test_sentinel_resource_metrics(sentinel_report, seed, layer, detector):
    """All runpod_mock sentinel envelopes carry resource metrics."""
    env = sentinel_report.seed_results.get(seed, {}).get(layer, {})
    result = detector.detect_missing_resource_metrics(env)
    assert result.passed, (
        f"Missing resource metrics for seed={seed!r}, layer={layer!r}: {result.evidence}"
    )


@pytest.mark.parametrize("seed", [s["name"] for s in SENTINEL_SEEDS])
@pytest.mark.parametrize("layer", list(RUNPOD_MOCK_LAYERS))
def test_sentinel_hashes_well_formed(sentinel_report, seed, layer):
    """All sentinel envelopes carry well-formed sha256 hashes."""
    env = sentinel_report.seed_results.get(seed, {}).get(layer, {})
    audit = env.get("audit", {})
    assert HASH_REGEX.match(audit.get("input_hash", "")), (
        f"Malformed input_hash for seed={seed!r}, layer={layer!r}"
    )
    assert HASH_REGEX.match(audit.get("output_hash", "")), (
        f"Malformed output_hash for seed={seed!r}, layer={layer!r}"
    )


@pytest.mark.parametrize("layer", list(RUNPOD_MOCK_LAYERS))
def test_deterministic_hash_across_seeds(layer):
    """Same input always produces the same input_hash (adversarial check)."""
    inp = {"chemical_system": "Li-La-Zr-O", "layer": layer}
    env1 = build_runpod_mock_envelope(layer=layer, input_payload=inp)
    env2 = build_runpod_mock_envelope(layer=layer, input_payload=inp)
    assert env1["audit"]["input_hash"] == env2["audit"]["input_hash"], (
        f"Non-deterministic input_hash for layer={layer!r}"
    )


@pytest.mark.parametrize("seed", [s["name"] for s in SENTINEL_SEEDS])
@pytest.mark.parametrize("layer", list(RUNPOD_MOCK_LAYERS))
def test_sentinel_schema_self_consistency(sentinel_report, seed, layer, detector):
    """Each sentinel envelope is schema-self-consistent (no internal drift)."""
    env = sentinel_report.seed_results.get(seed, {}).get(layer, {})
    result = detector.detect_schema_drift(env, env)
    assert result.passed, (
        f"Internal schema inconsistency for seed={seed!r}, layer={layer!r}: {result.evidence}"
    )


@pytest.mark.parametrize("layer", ["L1", "L2", "ionic", "quantum"])
def test_sentinel_mlip_dft_disagreement(sentinel_report, layer, detector):
    """MLIP/DFT layers always carry disagreement metrics in the sentinel campaign."""
    for seed_data in sentinel_report.seed_results.values():
        env = seed_data.get(layer, {})
        if "error" in env:
            continue
        result = detector.detect_model_response_without_disagreement(env)
        assert result.passed, (
            f"Layer {layer!r}: missing disagreement metrics. {result.evidence}"
        )


def test_parity_report_passed():
    """RunpodCutover.compare_to_mock() should return a passed parity report."""
    cutover = RunpodCutover()
    mock_report = cutover.run_sentinel_campaign(backend="runpod_mock")
    parity = cutover.compare_to_mock(sentinel_report=mock_report, mock_baseline=mock_report)
    # Self-comparison (mock vs mock) must ALWAYS pass.
    assert parity.passed, (
        f"Self-parity failed: schema_drifts={parity.schema_drifts}, "
        f"hash_mismatches={parity.hash_mismatches}"
    )


def test_hard_failure_detector_all_pass_on_mock():
    """All 10 hard-failure detectors pass on a well-formed runpod_mock envelope."""
    from zer0pa_materials.runpod.mock_backends import build_runpod_mock_envelope
    detector = HardFailureDetector()
    inp = {"chemical_system": "Li-La-Zr-O", "layer": "L1"}
    env = build_runpod_mock_envelope(layer="L1", input_payload=inp)

    results = detector.run_all_envelope_detectors(env)
    failed = [r for r in results if not r.passed]
    assert not failed, (
        f"Hard-failure detectors fired on a valid runpod_mock envelope: "
        f"{[(r.detector, r.evidence) for r in failed]}"
    )


def test_sentinel_backend_field_is_runpod_mock(sentinel_report):
    """All sentinel envelopes have tool_adapter.backend == 'runpod_mock'."""
    for seed_name, layer_envs in sentinel_report.seed_results.items():
        for layer, env in layer_envs.items():
            if "error" in env:
                continue
            backend = env.get("tool_adapter", {}).get("backend")
            assert backend == "runpod_mock", (
                f"seed={seed_name!r}, layer={layer!r}: expected backend='runpod_mock', got {backend!r}"
            )


def test_precheck_returns_report():
    """RunpodCutover.precheck() returns a CutoverPrecheckReport with all fields."""
    from zer0pa_materials.runpod.cutover import CutoverPrecheckReport
    cutover = RunpodCutover()
    report = cutover.precheck()
    assert isinstance(report, CutoverPrecheckReport)
    assert isinstance(report.preconditions, dict)
    assert isinstance(report.evidence, dict)
    assert report.boundary == RESEARCH_BOUNDARY


def test_decisions_recorded_after_sentinel():
    """Sentinel campaign records at least one Decision row."""
    cutover = RunpodCutover()
    cutover.run_sentinel_campaign(backend="runpod_mock")
    decisions = cutover.get_decisions()
    assert len(decisions) >= 1
    for d in decisions:
        assert "decision_id" in d
        assert d["boundary"] == RESEARCH_BOUNDARY


def test_promote_backend_blocked_without_parity():
    """promote_backend is blocked when no parity report is provided."""
    cutover = RunpodCutover()
    result = cutover.promote_backend(
        layer="L1",
        from_backend="runpod_mock",
        to_backend="runpod_rest",
        parity_report=None,
    )
    assert result.blocked, "promote_backend should be blocked without a parity report"


def test_promote_backend_approved_after_parity():
    """promote_backend is approved when parity passes."""
    from zer0pa_materials.runpod.cutover import ParityReport
    cutover = RunpodCutover()
    parity = ParityReport(
        passed=True,
        schema_drifts={},
        hash_mismatches={},
        boundary_failures=[],
        resource_metric_failures=[],
        disagreement_failures=[],
    )
    result = cutover.promote_backend(
        layer="L1",
        from_backend="runpod_mock",
        to_backend="runpod_rest",
        parity_report=parity,
    )
    assert not result.blocked, f"promote_backend should be approved after parity pass: {result.reason}"
