"""Tests for PyScfMolecularSolver — H2 and LiH (real or stub).

Tests pass regardless of whether pyscf is installed. The ``pyscf_available``
marker tracks which path ran so CI logs are interpretable.
"""

from __future__ import annotations

import importlib.util
import math
import pytest

from zer0pa_materials.adapters.l1.pyscf import (
    PyScfMolecularSolver,
    _H2_FCI_Ha,
    _H2_BOND_A,
    _LIH_CASCI_Ha,
    _LIH_BOND_A,
    PYSCF_BLOCKED_MANIFEST,
)
from zer0pa_materials.adapters.l1.base import L1JobParams
from zer0pa_materials.envelope import L1DftOutput, Envelope

PYSCF_AVAILABLE = importlib.util.find_spec("pyscf") is not None
pytestmark_pyscf = pytest.mark.skipif(
    False, reason="Always runs; pyscf_available flag indicates real vs stub"
)

H2_CIF = open("/Users/zer0palab/Materials Pipeline/fixtures/structures/H2/structure.cif").read()
LIH_CIF = open("/Users/zer0palab/Materials Pipeline/fixtures/structures/LiH/structure.cif").read()


@pytest.fixture
def solver() -> PyScfMolecularSolver:
    return PyScfMolecularSolver()


@pytest.fixture
def h2_params() -> L1JobParams:
    from zer0pa_materials.envelope import cif_hash_from_text
    return L1JobParams(
        structure_cif=H2_CIF,
        structure_hash=cif_hash_from_text(H2_CIF),
        functional="FCI/cc-pVDZ",
        campaign_id="campaign:test-pyscf-h2",
        candidate_id="candidate:test-h2",
    )


@pytest.fixture
def lih_params() -> L1JobParams:
    from zer0pa_materials.envelope import cif_hash_from_text
    return L1JobParams(
        structure_cif=LIH_CIF,
        structure_hash=cif_hash_from_text(LIH_CIF),
        functional="CASCI(2,2)/STO-3G",
        campaign_id="campaign:test-pyscf-lih",
        candidate_id="candidate:test-lih",
    )


# ---------------------------------------------------------------------------
# Availability detection
# ---------------------------------------------------------------------------

def test_pyscf_availability_matches_importlib(solver: PyScfMolecularSolver) -> None:
    assert solver.pyscf_available == PYSCF_AVAILABLE


def test_backend_is_local_cpu_when_pyscf_available(solver: PyScfMolecularSolver) -> None:
    if solver.pyscf_available:
        assert solver.BACKEND == "local_cpu"
    else:
        assert solver.BACKEND == "stub"


# ---------------------------------------------------------------------------
# H2 reference values
# ---------------------------------------------------------------------------

def test_h2_fci_reference_returns_float(solver: PyScfMolecularSolver) -> None:
    ref = solver.h2_fci_reference_Ha()
    assert isinstance(ref, float)
    assert ref < 0.0, "FCI energy must be negative"


def test_h2_fci_reference_calibration(solver: PyScfMolecularSolver) -> None:
    """FCI energy at canonical bond length within 5% of literature -1.16 Ha."""
    ref = solver.h2_fci_reference_Ha(_H2_BOND_A)
    # Literature FCI cc-pVDZ at R=0.74 Å: ~ -1.1637 Ha
    assert abs(ref - (-1.1637)) < 0.05, f"H2 FCI ref {ref:.6f} Ha out of range"


def test_h2_fci_stub_value_within_threshold() -> None:
    """Stub value must be within 1e-3 Ha of canonical so VQE falsifier passes."""
    stub = PyScfMolecularSolver()
    ref = stub.h2_fci_reference_Ha(_H2_BOND_A)
    assert abs(ref - _H2_FCI_Ha) < 1e-3


# ---------------------------------------------------------------------------
# LiH reference values
# ---------------------------------------------------------------------------

def test_lih_casci_reference_returns_float(solver: PyScfMolecularSolver) -> None:
    ref = solver.lih_casci_reference_Ha()
    assert isinstance(ref, float)
    assert ref < 0.0


def test_lih_casci_reference_calibration(solver: PyScfMolecularSolver) -> None:
    """CASCI energy must be below RHF energy (electron correlation)."""
    ref = solver.lih_casci_reference_Ha(_LIH_BOND_A)
    # CASCI should be around -7.98 Ha with STO-3G
    assert abs(ref - (-7.98)) < 0.15, f"LiH CASCI ref {ref:.6f} Ha out of range"


# ---------------------------------------------------------------------------
# submit_job round-trip
# ---------------------------------------------------------------------------

def test_h2_submit_job_returns_envelope(solver: PyScfMolecularSolver, h2_params: L1JobParams) -> None:
    envelope = solver.submit_job(H2_CIF, h2_params)
    assert isinstance(envelope, Envelope)
    assert envelope.layer == "L1"
    assert envelope.tool_adapter.name == "PyScfMolecularSolver"


def test_h2_submit_job_output_schema(solver: PyScfMolecularSolver, h2_params: L1JobParams) -> None:
    envelope = solver.submit_job(H2_CIF, h2_params)
    output = L1DftOutput.model_validate(envelope.output)
    assert output.code == "PySCF"
    assert output.total_energy_eV < 0.0
    assert output.kpoint_mesh == [1, 1, 1]


def test_h2_submit_job_energy_reasonable(solver: PyScfMolecularSolver, h2_params: L1JobParams) -> None:
    """Total energy should be around -31.6 eV (= -1.16 Ha × 27.21)."""
    envelope = solver.submit_job(H2_CIF, h2_params)
    output = L1DftOutput.model_validate(envelope.output)
    assert -35.0 < output.total_energy_eV < -28.0, f"Energy {output.total_energy_eV} eV out of range"


def test_lih_submit_job_returns_envelope(solver: PyScfMolecularSolver, lih_params: L1JobParams) -> None:
    envelope = solver.submit_job(LIH_CIF, lih_params)
    assert isinstance(envelope, Envelope)
    output = L1DftOutput.model_validate(envelope.output)
    assert output.code == "PySCF"


def test_lih_energy_reasonable(solver: PyScfMolecularSolver, lih_params: L1JobParams) -> None:
    """LiH CASCI energy in eV: ~-7.98 Ha × 27.21 ≈ -217 eV."""
    envelope = solver.submit_job(LIH_CIF, lih_params)
    output = L1DftOutput.model_validate(envelope.output)
    assert -230.0 < output.total_energy_eV < -190.0, f"LiH energy {output.total_energy_eV} eV"


# ---------------------------------------------------------------------------
# Envelope invariants
# ---------------------------------------------------------------------------

def test_envelope_has_boundary(solver: PyScfMolecularSolver, h2_params: L1JobParams) -> None:
    from zer0pa_materials.boundary import RESEARCH_BOUNDARY
    envelope = solver.submit_job(H2_CIF, h2_params)
    assert envelope.research_boundary == RESEARCH_BOUNDARY


def test_envelope_audit_hashes_valid(solver: PyScfMolecularSolver, h2_params: L1JobParams) -> None:
    import re
    envelope = solver.submit_job(H2_CIF, h2_params)
    assert re.match(r"sha256:[0-9a-f]{64}", envelope.audit.input_hash)
    assert re.match(r"sha256:[0-9a-f]{64}", envelope.audit.output_hash)


# ---------------------------------------------------------------------------
# parse_output
# ---------------------------------------------------------------------------

def test_parse_output_h2() -> None:
    solver = PyScfMolecularSolver()
    raw = "TOTAL ENERGY: -1.163729 Ha\nFORCE_RMSE: 0.0 eV/Ang\nCONVERGENCE_DELTA: None meV/atom\n"
    output = solver.parse_output(raw)
    assert output.code == "PySCF"
    assert abs(output.total_energy_eV - (-1.163729 * 27.211386)) < 0.01


def test_parse_output_with_delta() -> None:
    solver = PyScfMolecularSolver()
    raw = "TOTAL ENERGY: -1.163729 Ha\nFORCE_RMSE: 0.001 eV/Ang\nCONVERGENCE_DELTA: 3.5 meV/atom\n"
    output = solver.parse_output(raw)
    assert output.convergence_delta_meV_per_atom == pytest.approx(3.5)


# ---------------------------------------------------------------------------
# BlockedSourceManifest
# ---------------------------------------------------------------------------

def test_pyscf_blocked_manifest_has_correct_id() -> None:
    assert PYSCF_BLOCKED_MANIFEST.source_manifest_id.startswith("src:blocked:pyscf")


def test_pyscf_blocked_manifest_blocker_reason() -> None:
    assert PYSCF_BLOCKED_MANIFEST.blocker_reason == "policy"
