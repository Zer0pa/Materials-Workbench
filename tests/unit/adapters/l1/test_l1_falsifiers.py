"""Tests for L1 DFT falsifiers — convergence-delta thresholds (5 / 50 meV/atom)."""

from __future__ import annotations

import pytest

from zer0pa_materials_workbench import read_fixture
from zer0pa_materials_workbench.adapters.l1.pyscf import PyScfMolecularSolver
from zer0pa_materials_workbench.envelope import L1DftOutput
from zer0pa_materials_workbench.falsifiers.l1_falsifiers import (
    convergence_delta_publication_threshold,
    convergence_delta_screening_threshold,
    force_threshold_check,
)

H2_CIF = read_fixture("structures", "H2", "structure.cif")


def _make_output(delta: float | None = None, force_rmse: float = 0.001) -> L1DftOutput:
    return L1DftOutput(
        code="PySCF",
        functional="PBE",
        total_energy_eV=-31.6,
        force_rmse_eV_per_Ang=force_rmse,
        kpoint_mesh=[1, 1, 1],
        convergence_delta_meV_per_atom=delta,
        publication_grade=False,
    )


# ---------------------------------------------------------------------------
# Screening threshold (50 meV/atom)
# ---------------------------------------------------------------------------

def test_screening_passes_below_50() -> None:
    output = _make_output(delta=30.0)
    item = convergence_delta_screening_threshold(output)
    assert item.name == "l1.screening_convergence_delta"
    assert item.status == "pass"
    assert item.actual == 30.0


def test_screening_fails_above_50() -> None:
    output = _make_output(delta=75.0)
    item = convergence_delta_screening_threshold(output)
    assert item.status == "fail"


def test_screening_fails_at_exactly_50() -> None:
    output = _make_output(delta=50.0)
    item = convergence_delta_screening_threshold(output)
    # threshold is < 50, so exactly 50 is a fail
    assert item.status == "fail"


def test_screening_blocked_when_no_delta() -> None:
    output = _make_output(delta=None)
    item = convergence_delta_screening_threshold(output)
    assert item.status == "blocked"
    assert item.actual is None


# ---------------------------------------------------------------------------
# Publication threshold (5 meV/atom)
# ---------------------------------------------------------------------------

def test_publication_passes_below_5() -> None:
    output = _make_output(delta=3.0)
    item = convergence_delta_publication_threshold(output)
    assert item.status == "pass"


def test_publication_fails_at_6() -> None:
    output = _make_output(delta=6.0)
    item = convergence_delta_publication_threshold(output)
    assert item.status == "fail"


def test_publication_passes_at_exactly_5() -> None:
    output = _make_output(delta=5.0)
    item = convergence_delta_publication_threshold(output)
    # threshold is <= 5, so 5.0 passes
    assert item.status == "pass"


def test_publication_blocked_when_no_delta() -> None:
    output = _make_output(delta=None)
    item = convergence_delta_publication_threshold(output)
    assert item.status == "blocked"


# ---------------------------------------------------------------------------
# Force threshold
# ---------------------------------------------------------------------------

def test_force_passes_below_default() -> None:
    output = _make_output(force_rmse=0.01)
    item = force_threshold_check(output)
    assert item.status == "pass"
    assert item.actual == pytest.approx(0.01)


def test_force_fails_above_default() -> None:
    output = _make_output(force_rmse=0.1)
    item = force_threshold_check(output)
    assert item.status == "fail"


def test_force_custom_threshold() -> None:
    output = _make_output(force_rmse=0.03)
    item = force_threshold_check(output, threshold_eV_per_Ang=0.02)
    assert item.status == "fail"


def test_force_zero_always_passes() -> None:
    output = _make_output(force_rmse=0.0)
    item = force_threshold_check(output)
    assert item.status == "pass"


# ---------------------------------------------------------------------------
# Base adapter validate_convergence
# ---------------------------------------------------------------------------

def test_adapter_validate_convergence_pass() -> None:
    solver = PyScfMolecularSolver()
    output = _make_output(delta=20.0)
    item = solver.validate_convergence(output, threshold_meV_per_atom=50.0)
    assert item.status == "pass"
    assert item.name == "l1.convergence_delta"


def test_adapter_validate_convergence_fail() -> None:
    solver = PyScfMolecularSolver()
    output = _make_output(delta=60.0)
    item = solver.validate_convergence(output, threshold_meV_per_atom=50.0)
    assert item.status == "fail"


def test_adapter_validate_convergence_blocked() -> None:
    solver = PyScfMolecularSolver()
    output = _make_output(delta=None)
    item = solver.validate_convergence(output)
    assert item.status == "blocked"
