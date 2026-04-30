"""Tests for AbinitAiiDASolver — dry-run and parse-only."""

from __future__ import annotations

import pytest

from zer0pa_materials.adapters.l1.abinit_aiida import AbinitAiiDASolver, ABINIT_BLOCKED_MANIFEST
from zer0pa_materials.adapters.l1.base import L1JobParams
from zer0pa_materials.envelope import L1DftOutput, cif_hash_from_text

from zer0pa_materials import read_fixture

H2_CIF = read_fixture("structures", "H2", "structure.cif")


@pytest.fixture
def solver() -> AbinitAiiDASolver:
    return AbinitAiiDASolver()


@pytest.fixture
def h2_params() -> L1JobParams:
    return L1JobParams(
        structure_cif=H2_CIF,
        structure_hash=cif_hash_from_text(H2_CIF),
        campaign_id="campaign:test-abinit-h2",
        candidate_id="candidate:test-abinit-h2",
    )


def test_backend_is_stub(solver: AbinitAiiDASolver) -> None:
    assert solver.BACKEND == "stub"


def test_engine_is_abinit(solver: AbinitAiiDASolver) -> None:
    assert "ABINIT" in solver.ENGINE


def test_submit_job_returns_envelope(solver: AbinitAiiDASolver, h2_params: L1JobParams) -> None:
    from zer0pa_materials.envelope import Envelope
    envelope = solver.submit_job(H2_CIF, h2_params)
    assert isinstance(envelope, Envelope)


def test_output_code_is_abinit(solver: AbinitAiiDASolver, h2_params: L1JobParams) -> None:
    envelope = solver.submit_job(H2_CIF, h2_params)
    output = L1DftOutput.model_validate(envelope.output)
    assert output.code == "ABINIT"


def test_dry_run_emits_abinit_input(solver: AbinitAiiDASolver, h2_params: L1JobParams) -> None:
    solver._compute_output(H2_CIF, h2_params)
    assert hasattr(solver, "_last_abinit_input")
    inp = solver._last_abinit_input
    assert "ndtset" in inp or "ABINIT" in inp
    assert "DRY-RUN" in inp


def test_parse_output_abinit(solver: AbinitAiiDASolver) -> None:
    raw = "  etotal   -1.1637291  Ha\n"
    output = solver.parse_output(raw)
    assert output.code == "ABINIT"
    assert abs(output.total_energy_eV - (-1.1637291 * 27.211386)) < 0.5


def test_abinit_blocked_manifest(solver: AbinitAiiDASolver) -> None:
    assert ABINIT_BLOCKED_MANIFEST.blocker_reason == "license_unverified"
    assert ABINIT_BLOCKED_MANIFEST.source_manifest_id.startswith("src:blocked:abinit")
