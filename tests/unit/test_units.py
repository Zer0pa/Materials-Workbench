"""Unit tests for the canonical unit registry."""

from __future__ import annotations

import math

import pytest

from zer0pa_materials.envelope import (
    CANONICAL_UNITS,
    DimensionalityError,
    UREG,
    parse_quantity,
    to_canonical,
    format_canonical,
)


# ----------------------------------------------------------------------------
# parse_quantity coverage
# ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "0.35 eV",
        "1.0e-3 S/cm",
        "5 meV/atom",
        "1 Ha",
        "1 hartree",
        "1 angstrom",
        "1 Å",
        "1 nm",
        "1 pm",
        "1 bohr",
        "300 K",
        "1 GPa",
        "1 bar",
        "1 mS/cm",
        "1e-6 cm**2/s",
        "1 angstrom**2/ps",
        "5 W/(m*K)",
        "3 V",
        "0.5 THz",
        "100 cm**-1",
    ],
)
def test_parse_quantity_accepts_canonical_strings(text: str):
    q = parse_quantity(text)
    assert q.magnitude is not None
    assert str(q.units) is not None


def test_parse_quantity_unknown_unit_raises():
    import pint
    with pytest.raises(pint.errors.UndefinedUnitError):
        parse_quantity("1 frobnitz")


# ----------------------------------------------------------------------------
# to_canonical conversions
# ----------------------------------------------------------------------------


def test_to_canonical_bare_number_passes_through():
    assert to_canonical(0.35, "eV") == 0.35


def test_to_canonical_quantity_converts():
    q = parse_quantity("1 Ha")
    eV = to_canonical(q, "eV")
    # 1 Ha = 27.2113... eV. Use a wider tolerance to absorb pint version drift.
    assert math.isclose(eV, 27.2114, rel_tol=1e-3)


def test_to_canonical_dimensional_mismatch_raises():
    q = parse_quantity("1 K")
    with pytest.raises(DimensionalityError):
        to_canonical(q, "eV")


def test_to_canonical_returns_python_float():
    q = parse_quantity("1.0 eV")
    out = to_canonical(q, "meV")
    assert isinstance(out, float)


# ----------------------------------------------------------------------------
# Round trips
# ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value,from_unit,to_unit,expected",
    [
        # eV <-> Ha
        (1.0, "Ha", "eV", 27.2114),
        # meV/atom <-> eV/atom
        (1000.0, "meV/atom", "eV/atom", 1.0),
        # S/cm <-> mS/cm
        (1.0, "S/cm", "mS/cm", 1000.0),
        # Å <-> nm
        (10.0, "Å", "nm", 1.0),
        # cm**2/s <-> Å**2/ps (cross-check the diffusion conversion)
        (1.0, "Å**2/ps", "cm**2/s", 1.0e-4),
        # GPa <-> bar
        (1.0, "GPa", "bar", 10000.0),
        # K identity
        (300.0, "K", "K", 300.0),
        # length: bohr <-> angstrom
        (1.0, "bohr", "angstrom", 0.529177),
    ],
)
def test_unit_round_trip(value, from_unit, to_unit, expected):
    q = UREG.Quantity(value, from_unit)
    converted = to_canonical(q, to_unit)
    assert math.isclose(converted, expected, rel_tol=1e-3)


def test_spectroscopy_wavenumber_to_frequency_via_context():
    """1 cm⁻¹ ≈ 0.0299792 THz using pint's ``spectroscopy`` context.

    Wavenumber (1/length) and frequency (1/time) are different dimensions.
    pint exposes the spectroscopy context that bridges them via c. The
    materials pipeline performs this conversion inside the L1.5 phonon
    adapter; this test pins down the contract for that adapter.
    """
    q = UREG.Quantity(33.356, "cm**-1")
    with UREG.context("spectroscopy"):
        thz = q.to("THz").magnitude
    assert math.isclose(thz, 1.0, rel_tol=1e-2)


def test_round_trip_through_canonical_and_back():
    """0.35 eV -> Ha -> back to eV should round-trip within float precision."""
    q = parse_quantity("0.35 eV")
    in_Ha = to_canonical(q, "Ha")
    back = to_canonical(UREG.Quantity(in_Ha, "Ha"), "eV")
    assert math.isclose(back, 0.35, rel_tol=1e-9, abs_tol=1e-12)


# ----------------------------------------------------------------------------
# CANONICAL_UNITS coverage
# ----------------------------------------------------------------------------


def test_canonical_units_keys_present():
    """The canonical-units registry must cover every quantity layer schemas use."""
    required_keys = {
        "energy", "energy_per_atom", "energy_hartree", "energy_kjmol",
        "length", "length_nm", "length_pm", "length_bohr",
        "temperature", "pressure", "pressure_bar",
        "ionic_conductivity", "ionic_conductivity_low",
        "diffusion", "diffusion_alt",
        "thermal_conductivity", "voltage",
        "frequency_thz", "frequency_wavenumber",
        "force_density", "zt",
    }
    assert required_keys.issubset(set(CANONICAL_UNITS.keys()))


def test_canonical_units_unit_strings_parseable_except_offset():
    """Every CANONICAL_UNITS unit string must be parseable by pint, except the
    offset unit (degC) which is non-multiplicative and tested separately."""
    for name, cu in CANONICAL_UNITS.items():
        if cu.unit == "degC":
            # Offset unit; pint requires Quantity, not parse_expression with arithmetic.
            UREG.Quantity(0.0, "degC")
            continue
        if cu.unit == "dimensionless":
            UREG.Quantity(1.0, "dimensionless")
            continue
        q = parse_quantity(f"1 {cu.unit}")
        assert q.magnitude == 1.0


def test_format_canonical_known_unit():
    s = format_canonical(0.35, "energy")
    assert s == "0.35 eV"


def test_format_canonical_unknown_unit_raises():
    with pytest.raises(KeyError):
        format_canonical(1.0, "totally_made_up")
