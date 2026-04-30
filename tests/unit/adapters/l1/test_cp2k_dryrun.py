"""Tests for Cp2kAiiDASolver — dry-run and parse-only."""

from __future__ import annotations

import pytest

from zer0pa_materials.adapters.l1.cp2k_aiida import Cp2kAiiDASolver, CP2K_BLOCKED_MANIFEST
from zer0pa_materials.adapters.l1.base import L1JobParams
from zer0pa_materials.envelope import L1DftOutput, cif_hash_from_text

from zer0pa_materials import read_fixture

H2_CIF = read_fixture("structures", "H2", "structure.cif")


@pytest.fixture
def solver() -> Cp2kAiiDASolver:
    return Cp2kAiiDASolver()


@pytest.fixture
def h2_params() -> L1JobParams:
    return L1JobParams(
        structure_cif=H2_CIF,
        structure_hash=cif_hash_from_text(H2_CIF),
        campaign_id="campaign:test-cp2k-h2",
        candidate_id="candidate:test-cp2k-h2",
    )


def test_backend_is_stub(solver: Cp2kAiiDASolver) -> None:
    assert solver.BACKEND == "stub"


def test_engine_is_cp2k(solver: Cp2kAiiDASolver) -> None:
    assert "CP2K" in solver.ENGINE


def test_submit_job_returns_envelope(solver: Cp2kAiiDASolver, h2_params: L1JobParams) -> None:
    from zer0pa_materials.envelope import Envelope
    envelope = solver.submit_job(H2_CIF, h2_params)
    assert isinstance(envelope, Envelope)


def test_output_code_is_cp2k(solver: Cp2kAiiDASolver, h2_params: L1JobParams) -> None:
    envelope = solver.submit_job(H2_CIF, h2_params)
    output = L1DftOutput.model_validate(envelope.output)
    assert output.code == "CP2K"


def test_dry_run_emits_cp2k_input(solver: Cp2kAiiDASolver, h2_params: L1JobParams) -> None:
    solver._compute_output(H2_CIF, h2_params)
    assert hasattr(solver, "_last_cp2k_input")
    inp = solver._last_cp2k_input
    assert "&GLOBAL" in inp
    assert "DRY-RUN" in inp


def test_parse_output_cp2k(solver: Cp2kAiiDASolver) -> None:
    raw = " ENERGY| Total FORCE_EVAL ( QS ) energy [a.u.]:   -1.1637291\n"
    output = solver.parse_output(raw)
    assert output.code == "CP2K"
    # -1.1637 Ha * 27.211 eV/Ha ≈ -31.66 eV
    assert abs(output.total_energy_eV - (-1.1637 * 27.211386)) < 1.0


def test_cp2k_blocked_manifest(solver: Cp2kAiiDASolver) -> None:
    assert CP2K_BLOCKED_MANIFEST.blocker_reason == "license_unverified"
    assert CP2K_BLOCKED_MANIFEST.source_manifest_id.startswith("src:blocked:cp2k")
