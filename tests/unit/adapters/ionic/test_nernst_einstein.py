"""Unit tests for the Nernst-Einstein conductivity formula."""

from __future__ import annotations

import math

import pytest

from zer0pa_materials.adapters.ionic.nernst_einstein import (
    BOLTZMANN_J_PER_K,
    ELEMENTARY_CHARGE_C,
    HavenRatio,
    nernst_einstein_conductivity,
)


def test_constants_match_codata_2018() -> None:
    """Constants are pinned to SI 2019 exact values."""
    assert ELEMENTARY_CHARGE_C == 1.602176634e-19
    assert BOLTZMANN_J_PER_K == 1.380649e-23


def test_calibration_anchor_D_1e7_n_2e22_T_300() -> None:
    """At T=300 K, D=1e-7 cm²/s, n=2e22 /cm³ -> sigma ~ 1.24e-2 S/cm."""
    sigma = nernst_einstein_conductivity(1e-7, 2e22, 300.0)
    assert sigma == pytest.approx(1.2395e-2, rel=1e-3)


def test_calibration_anchor_D_1e8_n_2e22_T_300_clears_threshold() -> None:
    """At D=1e-8 cm²/s, sigma should clear the 1e-3 S/cm gate."""
    sigma = nernst_einstein_conductivity(1e-8, 2e22, 300.0)
    assert sigma == pytest.approx(1.2395e-3, rel=1e-3)
    assert sigma >= 1e-3


def test_linear_in_diffusion_coefficient() -> None:
    """sigma is linear in D at fixed n, T."""
    s1 = nernst_einstein_conductivity(1e-7, 2e22, 300.0)
    s2 = nernst_einstein_conductivity(2e-7, 2e22, 300.0)
    assert s2 == pytest.approx(2.0 * s1, rel=1e-12)


def test_linear_in_carrier_concentration() -> None:
    """sigma is linear in n at fixed D, T."""
    s1 = nernst_einstein_conductivity(1e-7, 2e22, 300.0)
    s2 = nernst_einstein_conductivity(1e-7, 4e22, 300.0)
    assert s2 == pytest.approx(2.0 * s1, rel=1e-12)


def test_inverse_temperature_scaling() -> None:
    """sigma scales as 1/T at fixed D and n."""
    s_300 = nernst_einstein_conductivity(1e-7, 2e22, 300.0)
    s_600 = nernst_einstein_conductivity(1e-7, 2e22, 600.0)
    assert s_600 == pytest.approx(s_300 / 2.0, rel=1e-12)


def test_charge_number_squared() -> None:
    """sigma scales as z² (Nernst-Einstein)."""
    s1 = nernst_einstein_conductivity(1e-7, 2e22, 300.0, charge_number=1)
    s2 = nernst_einstein_conductivity(1e-7, 2e22, 300.0, charge_number=2)
    assert s2 == pytest.approx(4.0 * s1, rel=1e-12)


def test_haven_ratio_divides_into_sigma() -> None:
    """sigma_measured = sigma_NE / H_R."""
    s_pure = nernst_einstein_conductivity(1e-7, 2e22, 300.0)
    s_haven = nernst_einstein_conductivity(1e-7, 2e22, 300.0, haven_ratio=2.0)
    assert s_haven == pytest.approx(s_pure / 2.0, rel=1e-12)


def test_negative_diffusion_rejected() -> None:
    with pytest.raises(ValueError, match="diffusion"):
        nernst_einstein_conductivity(-1e-7, 2e22, 300.0)


def test_zero_concentration_rejected() -> None:
    with pytest.raises(ValueError, match="concentration"):
        nernst_einstein_conductivity(1e-7, 0.0, 300.0)


def test_zero_temperature_rejected() -> None:
    with pytest.raises(ValueError, match="temperature"):
        nernst_einstein_conductivity(1e-7, 2e22, 0.0)


def test_zero_charge_rejected() -> None:
    with pytest.raises(ValueError, match="charge"):
        nernst_einstein_conductivity(1e-7, 2e22, 300.0, charge_number=0)


def test_negative_haven_ratio_rejected() -> None:
    with pytest.raises(ValueError, match="haven"):
        nernst_einstein_conductivity(1e-7, 2e22, 300.0, haven_ratio=-1.0)


def test_haven_ratio_dataclass_default() -> None:
    h = HavenRatio()
    assert h.value == 1.0
    assert "Haven" in h.rationale


def test_haven_ratio_adjust() -> None:
    h = HavenRatio(value=0.5)
    sigma_ne = 1e-3
    measured = h.adjust(sigma_ne)
    assert measured == pytest.approx(2e-3, rel=1e-12)


def test_haven_ratio_adjust_invalid() -> None:
    h = HavenRatio(value=-1.0)
    with pytest.raises(ValueError):
        h.adjust(1e-3)


def test_zero_diffusion_returns_zero() -> None:
    """sigma_NE = 0 when D = 0 (no transport)."""
    sigma = nernst_einstein_conductivity(0.0, 2e22, 300.0)
    assert sigma == 0.0


def test_round_trip_dimensionality() -> None:
    """Hand-checked: sigma in S/m via SI, then /100 to get S/cm."""
    n_cm3 = 2e22
    D_cm2 = 1e-7
    T = 300.0
    n_si = n_cm3 * 1e6
    D_si = D_cm2 * 1e-4
    sigma_si = (n_si * ELEMENTARY_CHARGE_C ** 2 * D_si) / (BOLTZMANN_J_PER_K * T)
    expected = sigma_si / 100.0
    actual = nernst_einstein_conductivity(D_cm2, n_cm3, T)
    assert actual == pytest.approx(expected, rel=1e-12)
