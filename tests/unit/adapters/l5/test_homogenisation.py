"""Unit tests for HomogenisationOperator (L4 microstructure → L5 effective properties)."""

from __future__ import annotations

import numpy as np
import pytest

from zer0pa_materials_workbench.adapters.l5.homogenisation import (
    DEFAULT_MATERIAL_LIBRARY,
    HomogenisationOperator,
    _hill_average,
    _is_spd,
    _isotropic_3x3,
    _reuss_average,
    _voigt_average,
)

# ---------------------------------------------------------------------------
# SPD helper tests
# ---------------------------------------------------------------------------

class TestSpdHelper:
    def test_identity_is_spd(self):
        spd, eigmin = _is_spd(np.eye(3))
        assert spd is True
        assert eigmin == pytest.approx(1.0, rel=1e-6)

    def test_negative_definite_is_not_spd(self):
        spd, eigmin = _is_spd(-np.eye(3))
        assert spd is False
        assert eigmin < 0.0

    def test_asymmetric_not_spd(self):
        A = np.array([[1.0, 2.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]])
        spd, _ = _is_spd(A, tol=1e-10)
        assert spd is False

    def test_isotropic_stiffness_spd(self):
        C = _isotropic_3x3(200.0, 0.3)
        spd, eigmin = _is_spd(C)
        assert spd is True
        assert eigmin > 0.0


# ---------------------------------------------------------------------------
# Voigt / Reuss / Hill averages
# ---------------------------------------------------------------------------

class TestMixtureRules:
    def test_voigt_single_phase_identity(self):
        C = _isotropic_3x3(200.0, 0.3)
        C_v = _voigt_average([C], [1.0])
        assert np.allclose(C_v, C, atol=1e-10)

    def test_reuss_single_phase_identity(self):
        C = _isotropic_3x3(200.0, 0.3)
        C_r = _reuss_average([C], [1.0])
        assert np.allclose(C_r, C, atol=1e-8)

    def test_hill_single_phase_identity(self):
        C = _isotropic_3x3(200.0, 0.3)
        C_h = _hill_average([C], [1.0])
        assert np.allclose(C_h, C, atol=1e-8)

    def test_voigt_ub_geq_reuss_lb(self):
        """Voigt upper bound >= Reuss lower bound (Hashin-Shtrikman)."""
        C1 = _isotropic_3x3(100.0, 0.25)
        C2 = _isotropic_3x3(300.0, 0.35)
        fracs = [0.6, 0.4]
        C_v = _voigt_average([C1, C2], fracs)
        C_r = _reuss_average([C1, C2], fracs)
        # Voigt (0,0) >= Reuss (0,0): arithmetic >= harmonic.
        assert C_v[0, 0] >= C_r[0, 0] - 1e-10

    def test_hill_between_voigt_reuss(self):
        C1 = _isotropic_3x3(100.0, 0.25)
        C2 = _isotropic_3x3(300.0, 0.35)
        fracs = [0.5, 0.5]
        C_v = _voigt_average([C1, C2], fracs)
        C_r = _reuss_average([C1, C2], fracs)
        C_h = _hill_average([C1, C2], fracs)
        assert C_h[0, 0] <= C_v[0, 0] + 1e-10
        assert C_h[0, 0] >= C_r[0, 0] - 1e-10


# ---------------------------------------------------------------------------
# HomogenisationOperator
# ---------------------------------------------------------------------------

@pytest.fixture
def operator() -> HomogenisationOperator:
    return HomogenisationOperator()


SIMPLE_TRAJECTORY = [
    {"phase": "matrix", "volume_fraction": 0.8, "time_step": 0},
    {"phase": "precipitate", "volume_fraction": 0.2, "time_step": 0},
]


class TestHomogenisationOperator:
    def test_single_snapshot_returns_dict(self, operator):
        result = operator.homogenise(SIMPLE_TRAJECTORY)
        assert isinstance(result, dict)

    def test_effective_stiffness_3x3_shape(self, operator):
        result = operator.homogenise(SIMPLE_TRAJECTORY)
        C = np.array(result["effective_stiffness_3x3"])
        assert C.shape == (3, 3)

    def test_effective_conductivity_3x3_shape(self, operator):
        result = operator.homogenise(SIMPLE_TRAJECTORY)
        K = np.array(result["effective_conductivity_3x3"])
        assert K.shape == (3, 3)

    def test_effective_stiffness_spd(self, operator):
        result = operator.homogenise(SIMPLE_TRAJECTORY)
        assert result["stiffness_spd"] is True

    def test_effective_conductivity_spd(self, operator):
        result = operator.homogenise(SIMPLE_TRAJECTORY)
        assert result["conductivity_spd"] is True

    def test_stiffness_eigmin_positive(self, operator):
        result = operator.homogenise(SIMPLE_TRAJECTORY)
        assert result["stiffness_eigmin"] > 0.0

    def test_conductivity_eigmin_positive(self, operator):
        result = operator.homogenise(SIMPLE_TRAJECTORY)
        assert result["conductivity_eigmin"] > 0.0

    def test_n_phases(self, operator):
        result = operator.homogenise(SIMPLE_TRAJECTORY)
        assert result["n_phases"] == 2

    def test_n_time_steps(self, operator):
        result = operator.homogenise(SIMPLE_TRAJECTORY)
        assert result["n_time_steps"] == 1

    def test_multiple_time_steps(self, operator):
        trajectory = [
            {"phase": "matrix", "volume_fraction": 0.8, "time_step": 0},
            {"phase": "precipitate", "volume_fraction": 0.2, "time_step": 0},
            {"phase": "matrix", "volume_fraction": 0.7, "time_step": 1},
            {"phase": "precipitate", "volume_fraction": 0.3, "time_step": 1},
        ]
        result = operator.homogenise(trajectory)
        assert result["n_time_steps"] == 2
        assert result["stiffness_spd"] is True

    def test_empty_trajectory_raises(self, operator):
        with pytest.raises(ValueError, match="non-empty"):
            operator.homogenise([])

    def test_normalised_fractions(self, operator):
        # Fractions don't sum to 1.0 — should auto-normalise without raising.
        trajectory = [
            {"phase": "matrix", "volume_fraction": 0.8, "time_step": 0},
            {"phase": "precipitate", "volume_fraction": 0.19, "time_step": 0},
        ]
        result = operator.homogenise(trajectory)
        assert result["stiffness_spd"] is True

    def test_unknown_phase_uses_fallback(self, operator):
        trajectory = [
            {"phase": "unknown_exotic_phase", "volume_fraction": 1.0, "time_step": 0},
        ]
        result = operator.homogenise(trajectory)
        assert result["stiffness_spd"] is True

    def test_single_phase_result_equals_pure_material(self, operator):
        """Single-phase → effective = constituent (Voigt = Reuss = Hill)."""
        trajectory = [
            {"phase": "matrix", "volume_fraction": 1.0, "time_step": 0},
        ]
        result = operator.homogenise(trajectory)
        lib_data = DEFAULT_MATERIAL_LIBRARY["matrix"]
        C_expected = _isotropic_3x3(lib_data["E_GPa"], lib_data["nu"])
        C_actual = np.array(result["effective_stiffness_3x3"])
        assert np.allclose(C_actual, C_expected, atol=1e-8)

    def test_custom_material_library(self):
        lib = {
            "steel": {"E_GPa": 210.0, "nu": 0.29, "kappa_W_per_mK": 50.0},
            "void":  {"E_GPa": 1e-6,  "nu": 0.0,  "kappa_W_per_mK": 0.0},
        }
        operator = HomogenisationOperator(material_library=lib)
        trajectory = [
            {"phase": "steel", "volume_fraction": 0.9, "time_step": 0},
            {"phase": "void", "volume_fraction": 0.1, "time_step": 0},
        ]
        result = operator.homogenise(trajectory)
        assert result["stiffness_spd"] is True
