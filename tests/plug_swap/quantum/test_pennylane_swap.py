"""Plug-swap test: PennyLane and Qiskit VQE produce matching schemas."""

from __future__ import annotations

import pytest

from zer0pa_materials_workbench.adapters.quantum.pennylane_vqe import PennyLaneVqeSolver
from zer0pa_materials_workbench.adapters.quantum.qiskit_nature_vqe import QiskitNatureVqeSolver
from zer0pa_materials_workbench.envelope import Envelope, L1QuantumVqeOutput

SOLVERS = [PennyLaneVqeSolver, QiskitNatureVqeSolver]


@pytest.fixture(params=SOLVERS, ids=[s.__name__ for s in SOLVERS])
def solver(request):
    return request.param()


def test_h2_solver_returns_envelope(solver) -> None:
    envelope = solver.solve_h2()
    assert isinstance(envelope, Envelope)


def test_h2_solver_layer_is_l1(solver) -> None:
    envelope = solver.solve_h2()
    assert envelope.layer == "L1"


def test_h2_solver_output_validates_schema(solver) -> None:
    envelope = solver.solve_h2()
    output = L1QuantumVqeOutput.model_validate(envelope.output)
    assert output.system == "H2"


def test_h2_solver_energy_negative(solver) -> None:
    envelope = solver.solve_h2()
    output = L1QuantumVqeOutput.model_validate(envelope.output)
    assert output.ground_state_energy_Ha < 0.0


def test_h2_solver_delta_within_1e3(solver) -> None:
    """PRD §L1 threshold must pass for all solvers in the swap set."""
    envelope = solver.solve_h2()
    output = L1QuantumVqeOutput.model_validate(envelope.output)
    delta = abs(output.ground_state_energy_Ha - output.classical_reference_Ha)
    assert delta <= 1e-3, f"{type(solver).__name__} H2 delta {delta:.6f} Ha"


def test_lih_solver_returns_envelope(solver) -> None:
    envelope = solver.solve_lih()
    assert isinstance(envelope, Envelope)
    output = L1QuantumVqeOutput.model_validate(envelope.output)
    assert output.system == "LiH"


def test_lih_solver_delta_within_5e3(solver) -> None:
    envelope = solver.solve_lih()
    output = L1QuantumVqeOutput.model_validate(envelope.output)
    delta = abs(output.ground_state_energy_Ha - output.classical_reference_Ha)
    assert delta <= 5e-3, f"{type(solver).__name__} LiH delta {delta:.6f} Ha"


def test_all_solvers_have_boundary(solver) -> None:
    from zer0pa_materials_workbench.boundary import RESEARCH_BOUNDARY
    envelope = solver.solve_h2()
    assert envelope.research_boundary == RESEARCH_BOUNDARY


def test_all_solvers_have_valid_audit_hashes(solver) -> None:
    import re
    envelope = solver.solve_h2()
    assert re.match(r"sha256:[0-9a-f]{64}", envelope.audit.input_hash)
    assert re.match(r"sha256:[0-9a-f]{64}", envelope.audit.output_hash)
