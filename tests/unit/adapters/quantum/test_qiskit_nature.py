"""Tests for QiskitNatureVqeSolver — analogous to pennylane tests."""

from __future__ import annotations

import importlib.util

import pytest

from zer0pa_materials.adapters.quantum.qiskit_nature_vqe import (
    QiskitNatureVqeSolver,
    QISKIT_NATURE_BLOCKED_MANIFEST,
    _H2_QISKIT_STUB_Ha,
    _LIH_QISKIT_STUB_Ha,
)
from zer0pa_materials.adapters.l1.pyscf import _H2_FCI_Ha, _LIH_CASCI_Ha
from zer0pa_materials.envelope import L1QuantumVqeOutput, Envelope
from zer0pa_materials.falsifiers.quantum_falsifiers import (
    vqe_h2_classical_match,
    vqe_lih_active_space_match,
)

QISKIT_AVAILABLE = importlib.util.find_spec("qiskit_nature") is not None


@pytest.fixture
def solver() -> QiskitNatureVqeSolver:
    return QiskitNatureVqeSolver()


def test_h2_returns_envelope(solver: QiskitNatureVqeSolver) -> None:
    envelope = solver.solve_h2()
    assert isinstance(envelope, Envelope)
    assert envelope.layer == "L1"


def test_h2_output_schema(solver: QiskitNatureVqeSolver) -> None:
    envelope = solver.solve_h2()
    output = L1QuantumVqeOutput.model_validate(envelope.output)
    assert output.system == "H2"


def test_h2_vqe_within_1e3_ha(solver: QiskitNatureVqeSolver) -> None:
    envelope = solver.solve_h2()
    output = L1QuantumVqeOutput.model_validate(envelope.output)
    delta = abs(output.ground_state_energy_Ha - output.classical_reference_Ha)
    assert delta <= 1e-3, f"Qiskit H2 delta {delta:.6f} Ha exceeds threshold"


def test_h2_falsifier_passes(solver: QiskitNatureVqeSolver) -> None:
    envelope = solver.solve_h2()
    item = vqe_h2_classical_match(envelope)
    assert item.status == "pass"


def test_lih_returns_envelope(solver: QiskitNatureVqeSolver) -> None:
    envelope = solver.solve_lih()
    assert isinstance(envelope, Envelope)


def test_lih_vqe_within_5e3_ha(solver: QiskitNatureVqeSolver) -> None:
    envelope = solver.solve_lih()
    output = L1QuantumVqeOutput.model_validate(envelope.output)
    delta = abs(output.ground_state_energy_Ha - output.classical_reference_Ha)
    assert delta <= 5e-3, f"Qiskit LiH delta {delta:.6f} Ha exceeds threshold"


def test_lih_falsifier_passes(solver: QiskitNatureVqeSolver) -> None:
    envelope = solver.solve_lih()
    item = vqe_lih_active_space_match(envelope)
    assert item.status == "pass"


def test_stub_h2_calibration() -> None:
    delta = abs(_H2_QISKIT_STUB_Ha - _H2_FCI_Ha)
    assert delta < 1e-3


def test_stub_lih_calibration() -> None:
    delta = abs(_LIH_QISKIT_STUB_Ha - _LIH_CASCI_Ha)
    assert delta < 5e-3


def test_qiskit_blocked_manifest() -> None:
    assert QISKIT_NATURE_BLOCKED_MANIFEST.source_manifest_id.startswith("src:blocked:qiskit")


def test_backend_matches_availability(solver: QiskitNatureVqeSolver) -> None:
    if solver.qiskit_available:
        assert solver.BACKEND == "local_cpu"
    else:
        assert solver.BACKEND == "stub"
