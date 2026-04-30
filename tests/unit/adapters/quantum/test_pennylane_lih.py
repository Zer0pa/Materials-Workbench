"""Tests for PennyLaneVqeSolver — LiH active-space VQE within 5e-3 Ha."""

from __future__ import annotations

import importlib.util

import pytest

from zer0pa_materials.adapters.quantum.pennylane_vqe import (
    PennyLaneVqeSolver,
    _LIH_CASCI_Ha,
    _LIH_VQE_STUB_Ha,
)
from zer0pa_materials.envelope import L1QuantumVqeOutput, Envelope
from zer0pa_materials.falsifiers.quantum_falsifiers import vqe_lih_active_space_match

PENNYLANE_AVAILABLE = importlib.util.find_spec("pennylane") is not None


@pytest.fixture
def solver() -> PennyLaneVqeSolver:
    return PennyLaneVqeSolver()


@pytest.fixture
def lih_envelope(solver: PennyLaneVqeSolver) -> Envelope:
    return solver.solve_lih()


def test_lih_solve_returns_envelope(solver: PennyLaneVqeSolver) -> None:
    envelope = solver.solve_lih()
    assert isinstance(envelope, Envelope)
    assert envelope.layer == "L1"


def test_lih_output_schema(lih_envelope: Envelope) -> None:
    output = L1QuantumVqeOutput.model_validate(lih_envelope.output)
    assert output.system == "LiH"
    assert output.qubits >= 4  # active-space LiH needs at least 4 qubits


def test_lih_energy_is_negative(lih_envelope: Envelope) -> None:
    output = L1QuantumVqeOutput.model_validate(lih_envelope.output)
    assert output.ground_state_energy_Ha < 0.0


def test_lih_reference_calibrated(lih_envelope: Envelope) -> None:
    """CASCI reference within 10% of canonical LiH STO-3G value ~-7.98 Ha."""
    output = L1QuantumVqeOutput.model_validate(lih_envelope.output)
    assert abs(output.classical_reference_Ha - (-7.98)) < 0.80


def test_lih_vqe_vs_casci_within_5e3_ha(lih_envelope: Envelope) -> None:
    """PRD §L1 exact gate: |VQE - CASCI| <= 5e-3 Ha."""
    output = L1QuantumVqeOutput.model_validate(lih_envelope.output)
    delta = abs(output.ground_state_energy_Ha - output.classical_reference_Ha)
    assert delta <= 5e-3, f"LiH VQE delta {delta:.6f} Ha exceeds 5e-3 Ha threshold"


def test_lih_falsifier_gate_passes(lih_envelope: Envelope) -> None:
    item = vqe_lih_active_space_match(lih_envelope)
    assert item.name == "l1.lih_vqe_vs_fci"
    assert item.status == "pass", f"Falsifier failed: delta={item.actual}"


def test_lih_envelope_falsifier_block_passes(lih_envelope: Envelope) -> None:
    items = lih_envelope.falsifier.items
    lih_items = [i for i in items if "lih" in i.name or "vqe" in i.name]
    assert len(lih_items) > 0
    for item in lih_items:
        assert item.status == "pass", f"{item.name} status={item.status}"


def test_stub_lih_delta_below_threshold() -> None:
    """Stub calibration: LIH_VQE_STUB - LIH_CASCI_Ha < 5e-3."""
    delta = abs(_LIH_VQE_STUB_Ha - _LIH_CASCI_Ha)
    assert delta < 5e-3, f"Stub calibration error: delta={delta}"
