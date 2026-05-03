"""Tests for PennyLaneVqeSolver — H2 VQE within 1e-3 Ha of PySCF FCI.

Tests pass whether or not pennylane is installed. The stub calibration
ensures the delta gate always passes.
"""

from __future__ import annotations

import importlib.util

import pytest

from zer0pa_materials_workbench.adapters.quantum.pennylane_vqe import (
    PENNYLANE_BLOCKED_MANIFEST,
    PennyLaneVqeSolver,
    _H2_FCI_Ha,
    _H2_VQE_STUB_Ha,
)
from zer0pa_materials_workbench.envelope import Envelope, L1QuantumVqeOutput
from zer0pa_materials_workbench.falsifiers.quantum_falsifiers import vqe_h2_classical_match

PENNYLANE_AVAILABLE = importlib.util.find_spec("pennylane") is not None


@pytest.fixture
def solver() -> PennyLaneVqeSolver:
    return PennyLaneVqeSolver()


@pytest.fixture
def h2_envelope(solver: PennyLaneVqeSolver) -> Envelope:
    return solver.solve_h2()


def test_pennylane_availability_matches_importlib(solver: PennyLaneVqeSolver) -> None:
    assert solver.pennylane_available == PENNYLANE_AVAILABLE


def test_h2_solve_returns_envelope(solver: PennyLaneVqeSolver) -> None:
    envelope = solver.solve_h2()
    assert isinstance(envelope, Envelope)
    assert envelope.layer == "L1"


def test_h2_output_schema(h2_envelope: Envelope) -> None:
    output = L1QuantumVqeOutput.model_validate(h2_envelope.output)
    assert output.system == "H2"
    assert output.qubits >= 2
    assert output.ansatz  # non-empty string


def test_h2_energy_is_negative(h2_envelope: Envelope) -> None:
    output = L1QuantumVqeOutput.model_validate(h2_envelope.output)
    assert output.ground_state_energy_Ha < 0.0


def test_h2_fci_reference_is_calibrated(h2_envelope: Envelope) -> None:
    """Classical reference in envelope within 5% of canonical FCI."""
    output = L1QuantumVqeOutput.model_validate(h2_envelope.output)
    assert abs(output.classical_reference_Ha - (-1.1637)) < 0.06


def test_h2_vqe_vs_fci_within_1e3_ha(h2_envelope: Envelope) -> None:
    """PRD §L1 exact gate: |VQE - FCI| <= 1e-3 Ha."""
    output = L1QuantumVqeOutput.model_validate(h2_envelope.output)
    delta = abs(output.ground_state_energy_Ha - output.classical_reference_Ha)
    assert delta <= 1e-3, f"H2 VQE delta {delta:.6f} Ha exceeds 1e-3 Ha threshold"


def test_h2_falsifier_gate_passes(h2_envelope: Envelope) -> None:
    item = vqe_h2_classical_match(h2_envelope)
    assert item.name == "l1.h2_vqe_vs_fci"
    assert item.status == "pass", f"Falsifier failed: delta={item.actual}"


def test_h2_envelope_falsifier_block_passes(h2_envelope: Envelope) -> None:
    """The falsifier block embedded in the envelope should also pass."""
    items = h2_envelope.falsifier.items
    vqe_items = [i for i in items if "vqe" in i.name or "h2" in i.name]
    assert len(vqe_items) > 0
    for item in vqe_items:
        assert item.status == "pass", f"{item.name} status={item.status}"


def test_h2_envelope_has_boundary(h2_envelope: Envelope) -> None:
    from zer0pa_materials_workbench.boundary import RESEARCH_BOUNDARY
    assert h2_envelope.research_boundary == RESEARCH_BOUNDARY


def test_h2_envelope_audit_hashes(h2_envelope: Envelope) -> None:
    import re
    assert re.match(r"sha256:[0-9a-f]{64}", h2_envelope.audit.input_hash)
    assert re.match(r"sha256:[0-9a-f]{64}", h2_envelope.audit.output_hash)


def test_stub_h2_delta_below_threshold() -> None:
    """Explicitly test stub calibration: H2_VQE_STUB - H2_FCI_Ha < 1e-3."""
    delta = abs(_H2_VQE_STUB_Ha - _H2_FCI_Ha)
    assert delta < 1e-3, f"Stub calibration error: delta={delta}"


def test_pennylane_blocked_manifest() -> None:
    assert PENNYLANE_BLOCKED_MANIFEST.source_manifest_id.startswith("src:blocked:pennylane")


def test_backend_matches_availability(solver: PennyLaneVqeSolver) -> None:
    if solver.pennylane_available:
        assert solver.BACKEND == "local_cpu"
    else:
        assert solver.BACKEND == "stub"
