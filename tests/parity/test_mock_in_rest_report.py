"""Wave F.4 — adversarial test: parity rejects runpod_rest reports
containing runpod_mock envelopes.

The user audit caught the deception: a sentinel report could claim
``backend="runpod_rest"`` while every internal cell carried a
``runpod_mock`` envelope.  This test pins the hard-reject behaviour added
in Wave F.4: ``ParityReport.mock_envelope_in_rest_report`` is non-empty
on detection, and ``ParityReport.passed`` is ``False``.

Boundary
--------
Research infrastructure for in silico materials science discovery.
No regulatory certification claims. No clinical or human-subject use.
ITAR/weapons out of scope.
"""

from __future__ import annotations

import os
from contextlib import contextmanager

from zer0pa_materials_workbench.envelope.config import MaterialsConfig
from zer0pa_materials_workbench.runpod.cutover import (
    ParityReport,
    RunpodCutover,
    SentinelCampaignReport,
)


@contextmanager
def _no_runpod_credentials():
    """Temporarily clear Runpod credentials so honest-block fires."""
    saved = {
        "RUNPOD_BASE_URL": os.environ.pop("RUNPOD_BASE_URL", None),
        "RUNPOD_API_TOKEN": os.environ.pop("RUNPOD_API_TOKEN", None),
        "MATERIALS_MODE": os.environ.get("MATERIALS_MODE"),
    }
    os.environ["MATERIALS_MODE"] = "runpod_rest"
    try:
        yield
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _build_forged_rest_report(
    mock_baseline: SentinelCampaignReport,
) -> SentinelCampaignReport:
    """Construct the deception: a sentinel_report whose top-level backend
    claims runpod_rest but whose cells carry runpod_mock-labelled envelopes.

    This is exactly the failure mode the user audit demanded we catch.
    """
    forged = SentinelCampaignReport(
        seed_results=mock_baseline.seed_results,  # mock-labelled cells
        layers_run=mock_baseline.layers_run,
        seeds_run=mock_baseline.seeds_run,
        backend="runpod_rest",  # the lie
        started_at=mock_baseline.started_at,
        completed_at=mock_baseline.completed_at,
    )
    return forged


def test_parity_hard_rejects_mock_envelopes_in_rest_report():
    """A relabelled mock report (backend=runpod_rest with mock cells)
    fails parity with a non-empty mock_envelope_in_rest_report list."""
    cfg = MaterialsConfig.from_env()
    cutover = RunpodCutover(config=cfg)

    # Step 1: generate a clean mock baseline.
    mock_baseline = cutover.run_sentinel_campaign(backend="runpod_mock")
    # Sanity: every cell in the mock baseline carries the mock label.
    for layer_envs in mock_baseline.seed_results.values():
        for env in layer_envs.values():
            if isinstance(env, dict) and "tool_adapter" in env:
                assert env["tool_adapter"]["backend"] == "runpod_mock"

    # Step 2: build the forged "rest" report (relabelled mock).
    forged = _build_forged_rest_report(mock_baseline)
    assert forged.backend == "runpod_rest"

    # Step 3: parity check.
    parity = cutover.compare_to_mock(
        sentinel_report=forged,
        mock_baseline=mock_baseline,
    )

    # Hard-fail expectation:
    assert isinstance(parity, ParityReport)
    assert parity.passed is False, (
        "Parity must HARD-FAIL when a runpod_rest report contains runpod_mock "
        "envelopes (Wave F.4 deception case)."
    )
    assert len(parity.mock_envelope_in_rest_report) > 0, (
        "mock_envelope_in_rest_report must surface every offending cell."
    )
    # Each entry should mention the offending cell's backend label so the
    # operator can audit the leak by seed/layer.
    for entry in parity.mock_envelope_in_rest_report:
        assert "runpod_mock" in entry
        assert "runpod_rest sentinel report" in entry


def test_parity_accepts_clean_mock_to_mock_baseline():
    """A genuine mock baseline parity-checked against itself passes."""
    cfg = MaterialsConfig.from_env()
    cutover = RunpodCutover(config=cfg)
    mock_baseline = cutover.run_sentinel_campaign(backend="runpod_mock")
    parity = cutover.compare_to_mock(
        sentinel_report=mock_baseline,
        mock_baseline=mock_baseline,
    )
    # Mock-vs-mock: the mock_envelope_in_rest_report check does NOT fire
    # because the report's backend is runpod_mock (not runpod_rest).
    assert parity.mock_envelope_in_rest_report == []


def test_parity_accepts_honest_block_rest_report():
    """A runpod_rest sentinel report with no credentials produces only
    blocked cells; the mock-in-rest check does NOT fire because
    ``blocked=true`` cells carry no ``tool_adapter`` field."""
    cfg = MaterialsConfig.from_env()
    cutover = RunpodCutover(config=cfg)
    with _no_runpod_credentials():
        rest_report = cutover.run_sentinel_campaign(backend="runpod_rest")
    # Every cell is blocked.
    blocked_cells = sum(
        1
        for layer_envs in rest_report.seed_results.values()
        for env in layer_envs.values()
        if isinstance(env, dict) and env.get("blocked") is True
    )
    assert blocked_cells == len(rest_report.seeds_run) * len(rest_report.layers_run)

    # Compare against a mock baseline.  The honest-block cells are not
    # mock-relabel deceptions; they carry no tool_adapter at all.
    mock_baseline = cutover.run_sentinel_campaign(backend="runpod_mock")
    parity = cutover.compare_to_mock(
        sentinel_report=rest_report,
        mock_baseline=mock_baseline,
    )
    # The check correctly does NOT flag honest-block cells.
    assert parity.mock_envelope_in_rest_report == []


def test_parity_to_dict_serialises_mock_in_rest_report_field():
    """The to_dict surface includes the new field for downstream JSON."""
    report = ParityReport(
        passed=False,
        schema_drifts={},
        hash_mismatches={},
        boundary_failures=[],
        resource_metric_failures=[],
        disagreement_failures=[],
        mock_envelope_in_rest_report=["LLZO_cubic/L1: tool_adapter.backend='runpod_mock'"],
    )
    payload = report.to_dict()
    assert "mock_envelope_in_rest_report" in payload
    assert len(payload["mock_envelope_in_rest_report"]) == 1
