"""Tests for QuantumEspressoAiiDASolver — dry-run and parse-only."""

from __future__ import annotations

import pytest

from zer0pa_materials_workbench import read_fixture
from zer0pa_materials_workbench.adapters.l1.base import L1JobParams
from zer0pa_materials_workbench.adapters.l1.qe_aiida import (
    QE_BLOCKED_MANIFEST,
    QuantumEspressoAiiDASolver,
)
from zer0pa_materials_workbench.envelope import L1DftOutput, cif_hash_from_text

H2_CIF = read_fixture("structures", "H2", "structure.cif")
SI_CIF = read_fixture("structures", "Si", "structure.cif")


@pytest.fixture
def solver() -> QuantumEspressoAiiDASolver:
    return QuantumEspressoAiiDASolver()


@pytest.fixture
def h2_params() -> L1JobParams:
    return L1JobParams(
        structure_cif=H2_CIF,
        structure_hash=cif_hash_from_text(H2_CIF),
        campaign_id="campaign:test-qe-h2",
        candidate_id="candidate:test-qe-h2",
    )


def test_qe_adapter_backend_is_stub(solver: QuantumEspressoAiiDASolver) -> None:
    assert solver.BACKEND == "stub"


def test_qe_adapter_engine(solver: QuantumEspressoAiiDASolver) -> None:
    assert "QE" in solver.ENGINE or "pw" in solver.ENGINE.lower()


def test_submit_job_returns_envelope(solver: QuantumEspressoAiiDASolver, h2_params: L1JobParams) -> None:
    from zer0pa_materials_workbench.envelope import Envelope
    envelope = solver.submit_job(H2_CIF, h2_params)
    assert isinstance(envelope, Envelope)
    assert envelope.layer == "L1"


def test_submit_job_output_code_is_qe(solver: QuantumEspressoAiiDASolver, h2_params: L1JobParams) -> None:
    envelope = solver.submit_job(H2_CIF, h2_params)
    output = L1DftOutput.model_validate(envelope.output)
    assert output.code == "QE"


def test_submit_job_functional_is_pbe(solver: QuantumEspressoAiiDASolver, h2_params: L1JobParams) -> None:
    envelope = solver.submit_job(H2_CIF, h2_params)
    output = L1DftOutput.model_validate(envelope.output)
    assert "PBE" in output.functional


def test_dry_run_emits_qe_input(solver: QuantumEspressoAiiDASolver, h2_params: L1JobParams) -> None:
    solver._compute_output(H2_CIF, h2_params)
    assert hasattr(solver, "_last_qe_input")
    qe_input = solver._last_qe_input
    assert "&CONTROL" in qe_input
    assert "DRY-RUN" in qe_input


def test_qe_input_contains_structure_hash(solver: QuantumEspressoAiiDASolver, h2_params: L1JobParams) -> None:
    solver._compute_output(H2_CIF, h2_params)
    assert h2_params.structure_hash in solver._last_qe_input


def test_parse_output_minimal(solver: QuantumEspressoAiiDASolver) -> None:
    raw = """\
     !    total energy              =     -2.3163 Ry
     Total force =      0.0000     Total SCF correction =       0.0000
    """
    output = solver.parse_output(raw)
    assert output.code == "QE"
    assert output.total_energy_eV < 0.0
    assert output.force_rmse_eV_per_Ang == pytest.approx(0.0, abs=1e-3)


def test_parse_output_with_delta(solver: QuantumEspressoAiiDASolver) -> None:
    raw = """\
     !    total energy              =     -2.3163 Ry
     CONVERGENCE_DELTA: 8.5
    """
    output = solver.parse_output(raw)
    assert output.convergence_delta_meV_per_atom == pytest.approx(8.5)


def test_si_system_detected(solver: QuantumEspressoAiiDASolver) -> None:
    si_params = L1JobParams(
        structure_cif=SI_CIF,
        structure_hash=cif_hash_from_text(SI_CIF),
        campaign_id="campaign:test-qe-si",
        candidate_id="candidate:test-qe-si",
    )
    envelope = solver.submit_job(SI_CIF, si_params)
    output = L1DftOutput.model_validate(envelope.output)
    # Si energy should be more negative than H2
    assert output.total_energy_eV < -50.0


def test_qe_blocked_manifest_id(solver: QuantumEspressoAiiDASolver) -> None:
    assert QE_BLOCKED_MANIFEST.source_manifest_id.startswith("src:blocked:qe")


def test_qe_blocked_manifest_reason(solver: QuantumEspressoAiiDASolver) -> None:
    assert QE_BLOCKED_MANIFEST.blocker_reason == "license_unverified"
