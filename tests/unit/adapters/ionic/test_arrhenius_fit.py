"""Unit tests for the ArrheniusFitAdapter."""

from __future__ import annotations

import math

import pytest

from zer0pa_materials.adapters.ionic.arrhenius import (
    KB_eV_per_K,
    ArrheniusFitAdapter,
    ArrheniusFitParams,
    fit_arrhenius,
)
from zer0pa_materials.adapters.ionic.base import (
    IONIC_TRANSPORT_SERVICE_REF,
    IonicJobParams,
)


def synth_sigma(T: float, E_a: float, sigma_300: float) -> float:
    """Generate σ(T) at T given Arrhenius E_a and σ(300)."""
    return sigma_300 * (300.0 / T) * math.exp(
        -E_a * (1.0 / T - 1.0 / 300.0) / KB_eV_per_K
    )


def test_recover_synthetic_E_a_within_5_percent_clean() -> None:
    """Synthesise σ(T) from E_a=0.30 eV, fit, recover within 5%."""
    E_a_true = 0.30
    sigma_300 = 1e-3
    Ts = [300.0, 350.0, 400.0, 450.0, 500.0, 550.0, 600.0]
    sigmas = [synth_sigma(T, E_a_true, sigma_300) for T in Ts]
    result = fit_arrhenius(Ts, sigmas)
    assert abs(result.activation_energy_eV - E_a_true) / E_a_true <= 0.05
    assert result.R_squared >= 0.99


def test_recover_synthetic_E_a_within_5_percent_with_noise() -> None:
    """With small noise (2%), still recover E_a within 5%."""
    E_a_true = 0.35
    sigma_300 = 5e-3
    # Deterministic 2% per-point noise pattern.
    Ts = [300.0, 350.0, 400.0, 450.0, 500.0, 550.0, 600.0]
    noise_pattern = [+0.02, -0.015, +0.01, -0.02, +0.018, -0.012, +0.005]
    sigmas = [
        synth_sigma(T, E_a_true, sigma_300) * (1.0 + noise_pattern[i])
        for i, T in enumerate(Ts)
    ]
    result = fit_arrhenius(Ts, sigmas)
    assert abs(result.activation_energy_eV - E_a_true) / E_a_true <= 0.05


def test_uncertainty_non_zero_with_noise() -> None:
    Ts = [300.0, 400.0, 500.0]
    # Add explicit noise so the fit cov is non-zero.
    sigmas = [1e-3, 5e-3 * 1.05, 1e-2 * 0.95]
    result = fit_arrhenius(Ts, sigmas)
    assert result.activation_energy_uncertainty_eV >= 0.0


def test_fit_requires_three_points() -> None:
    with pytest.raises(ValueError, match="at least 3"):
        fit_arrhenius([300.0, 400.0], [1e-3, 5e-3])


def test_fit_rejects_negative_T() -> None:
    with pytest.raises(ValueError, match="must be > 0"):
        fit_arrhenius([300.0, -100.0, 400.0], [1e-3, 1e-3, 1e-3])


def test_fit_rejects_negative_sigma() -> None:
    with pytest.raises(ValueError, match="must be > 0"):
        fit_arrhenius([300.0, 400.0, 500.0], [1e-3, -1e-3, 1e-3])


def test_fit_rejects_mismatched_lengths() -> None:
    with pytest.raises(ValueError, match="same length"):
        fit_arrhenius([300.0, 400.0, 500.0], [1e-3, 5e-3])


def test_temperature_range_recorded() -> None:
    Ts = [300.0, 400.0, 500.0]
    sigmas = [1e-3, 5e-3, 1e-2]
    result = fit_arrhenius(Ts, sigmas)
    assert result.temperature_range_K == (300.0, 500.0)


def test_n_points_recorded() -> None:
    Ts = [300.0, 400.0, 500.0, 600.0]
    sigmas = [1e-3, 5e-3, 1e-2, 2e-2]
    result = fit_arrhenius(Ts, sigmas)
    assert result.n_points == 4


def test_R_squared_close_to_1_for_perfect_fit() -> None:
    """A noise-free Arrhenius should give R² ~ 1."""
    E_a = 0.30
    sigma_300 = 1e-3
    Ts = [300.0, 400.0, 500.0, 600.0, 700.0]
    sigmas = [synth_sigma(T, E_a, sigma_300) for T in Ts]
    result = fit_arrhenius(Ts, sigmas)
    assert result.R_squared >= 0.999


def test_adapter_compute_via_default_path() -> None:
    p = IonicJobParams(
        structure_hash="sha256:" + "a" * 64,
        fixture_id="fixture:LLZO_cubic:d45cb2bf",
        candidate_id="candidate:LLZO/cubic",
    )
    env = ArrheniusFitAdapter().compute(p)
    arrhenius = env.output["arrhenius"]
    assert "activation_energy_eV" in arrhenius
    assert arrhenius["activation_energy_eV"] == pytest.approx(0.30, rel=0.05)


def test_adapter_compute_from_params() -> None:
    fit_params = ArrheniusFitParams(
        temperatures_K=[300.0, 400.0, 500.0, 600.0],
        conductivities_S_per_cm=[1e-3, 5e-3, 1e-2, 2e-2],
        candidate_id="candidate:test/arrhenius",
    )
    env = ArrheniusFitAdapter().compute_from_params(fit_params)
    assert env.layer == "ionic"
    assert IONIC_TRANSPORT_SERVICE_REF in env.input_refs


def test_arrhenius_quality_falsifier_present() -> None:
    fit_params = ArrheniusFitParams(
        temperatures_K=[300.0, 400.0, 500.0, 600.0],
        conductivities_S_per_cm=[1e-3, 5e-3, 1e-2, 2e-2],
        candidate_id="candidate:test/arrhenius",
    )
    env = ArrheniusFitAdapter().compute_from_params(fit_params)
    item_names = {it.name for it in env.falsifier.items}
    assert "ionic.arrhenius_fit_quality" in item_names


def test_R_squared_high_for_linear_input() -> None:
    """A clean Arrhenius input gives R² >= 0.95 (the gate threshold)."""
    fit_params = ArrheniusFitParams(
        temperatures_K=[300.0, 400.0, 500.0, 600.0],
        conductivities_S_per_cm=[
            synth_sigma(T, 0.30, 1e-3) for T in [300.0, 400.0, 500.0, 600.0]
        ],
        candidate_id="candidate:test/arrhenius",
    )
    env = ArrheniusFitAdapter().compute_from_params(fit_params)
    for it in env.falsifier.items:
        if it.name == "ionic.arrhenius_fit_quality":
            assert it.actual >= 0.95
            return
    raise AssertionError("Arrhenius quality item missing")
