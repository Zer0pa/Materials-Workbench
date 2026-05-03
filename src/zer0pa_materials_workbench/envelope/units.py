"""Canonical unit registry for the materials pipeline.

Every layer schema declares physical quantities with explicit units. The
PRD requires unit-normalised values across boundaries (Phase 0 §"Normalize
units before promotion"; L1.5 imaginary mode magnitudes in THz; ionic
transport in S/cm and cm²/s; phonon force RMSE in eV/Å; etc).

This module is the single source of truth. Adapters convert their tool's
native units into canonical units before emitting an envelope, and
downstream layers consume canonical units exclusively. We use ``pint``
because:

1. It already understands eV, Hartree, kJ/mol, GPa, K, cm⁻¹, etc.
2. It supports user-defined units and aliases.
3. Round-trip conversions between SI and chemistry units are well-tested.

We extend pint with:

* ``meV/atom`` (per-atom energy density) — pint by default treats "atom"
  as an undefined dimension; we register it as a counting unit.
* ``Å/ps`` and ``cm**2/s`` — already understood, but we test the round trip
  explicitly because diffusion units flip easily.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

import pint

__all__ = [
    "CANONICAL_UNITS",
    "UREG",
    "DimensionalityError",
    "Quantity",
    "format_canonical",
    "parse_quantity",
    "to_canonical",
]


# ----------------------------------------------------------------------------
# Registry construction
# ----------------------------------------------------------------------------

UREG: Final[pint.UnitRegistry] = pint.UnitRegistry()
# pint 0.23+ already provides 'eV', 'hartree' (with no built-in 'Ha' alias),
# 'bohr', 'angstrom' (and 'Å'), 'picosecond' (with 'ps'), 'terahertz' (with
# 'THz'), 'siemens', 'cm**-1', 'GPa', etc.
#
# We need two registry-level extensions:
#   1. 'atom' as a counting unit so 'meV/atom' has a clean dimension and
#      conversions to canonical 'meV/atom' don't trip pint's dimensionality
#      check.
#   2. 'Ha' as an alias for 'hartree' — adapter authors write 'Ha' more
#      often than 'hartree' (PySCF / PennyLane convention).
UREG.define("atom = [_atom_count] = atoms")
UREG.define("@alias hartree = Ha = ha")

Quantity = UREG.Quantity
DimensionalityError = pint.DimensionalityError


# ----------------------------------------------------------------------------
# Canonical units per quantity
# ----------------------------------------------------------------------------


@dataclass(frozen=True)
class CanonicalUnit:
    """Canonical unit for a named physical quantity."""

    name: str
    unit: str
    description: str


# Map of quantity name -> canonical unit string. Layer schemas reference these
# by name when documenting fields; adapters call ``to_canonical`` with the
# unit string directly.
CANONICAL_UNITS: Final[dict[str, CanonicalUnit]] = {
    "energy": CanonicalUnit("energy", "eV", "Total or reference energies"),
    "energy_per_atom": CanonicalUnit(
        "energy_per_atom", "meV/atom", "MLIP / DFT cohesive energy density"
    ),
    "energy_hartree": CanonicalUnit(
        "energy_hartree", "Ha", "VQE/PySCF native energy"
    ),
    "energy_kjmol": CanonicalUnit(
        "energy_kjmol", "kJ/mol", "Reaction energetics"
    ),
    "length": CanonicalUnit("length", "Å", "Lattice and bond lengths"),
    "length_nm": CanonicalUnit("length_nm", "nm", "Mesoscale length"),
    "length_pm": CanonicalUnit("length_pm", "pm", "Sub-Å length"),
    "length_bohr": CanonicalUnit("length_bohr", "bohr", "Bohr radius"),
    "temperature": CanonicalUnit("temperature", "K", "Absolute temperature"),
    "temperature_celsius": CanonicalUnit(
        "temperature_celsius",
        "degC",
        "Process temperature (offset unit; convert with UREG.Quantity not bare arithmetic).",
    ),
    "pressure": CanonicalUnit("pressure", "GPa", "Mechanical / DFT pressure"),
    "pressure_bar": CanonicalUnit("pressure_bar", "bar", "Process pressure"),
    "ionic_conductivity": CanonicalUnit(
        "ionic_conductivity", "S/cm", "Battery ionic conductivity"
    ),
    "ionic_conductivity_low": CanonicalUnit(
        "ionic_conductivity_low", "mS/cm", "Lower-conductivity convention"
    ),
    "diffusion": CanonicalUnit(
        "diffusion", "cm**2/s", "MD/AIMD/MLIP-MD diffusion coefficient"
    ),
    "diffusion_alt": CanonicalUnit(
        "diffusion_alt", "Å**2/ps", "Native MD output unit"
    ),
    "thermal_conductivity": CanonicalUnit(
        "thermal_conductivity", "W/(m*K)", "Phonon BTE / L1.5 transport"
    ),
    "voltage": CanonicalUnit("voltage", "V", "Electrochemical window vs Li/Li+"),
    "frequency_thz": CanonicalUnit(
        "frequency_thz", "THz", "Phonon mode magnitude"
    ),
    "frequency_wavenumber": CanonicalUnit(
        "frequency_wavenumber", "1/cm", "Spectroscopic phonon frequency"
    ),
    "force_density": CanonicalUnit(
        "force_density", "eV/Å", "MLIP / DFT force RMSE"
    ),
    "zt": CanonicalUnit("zt", "dimensionless", "Thermoelectric figure of merit"),
}


# ----------------------------------------------------------------------------
# Public helpers
# ----------------------------------------------------------------------------


def parse_quantity(text: str) -> pint.Quantity:
    """Parse a string like ``"0.35 eV"`` or ``"1.0e-3 S/cm"`` into a Quantity.

    Accepts pint-native syntax. Raises ``pint.UndefinedUnitError`` for
    unknown units (caller treats this as a falsifier-grade failure: an
    adapter emitted a unit the registry does not know).
    """
    return UREG.parse_expression(text)


def to_canonical(value: float | int | pint.Quantity, target_unit: str) -> float:
    """Convert ``value`` to ``target_unit`` and return the magnitude.

    * If ``value`` is a bare number, it is assumed to already be in
      ``target_unit``.
    * If ``value`` is a Quantity, it is converted via pint and the
      dimensional-mismatch raises ``DimensionalityError``.
    * The return type is always a Python ``float`` so envelopes serialise
      stably (pint's ``magnitude`` is sometimes a numpy scalar, which
      orjson handles but we coerce explicitly for hash determinism).

    The materials convention is to always store canonical magnitudes as
    floats and to attach the unit at the schema level — never pickle a
    pint Quantity into the envelope. That keeps the JSON Schema simple
    and the audit hash chain language-agnostic.
    """
    if isinstance(value, pint.Quantity):
        return float(value.to(target_unit).magnitude)
    return float(value)


def format_canonical(value: float, unit_name: str) -> str:
    """Format a canonical magnitude as ``"<value> <unit>"`` for display.

    Used by the CLI ``envelope-schema`` command and by audit log formatters.
    The unit string comes from :data:`CANONICAL_UNITS`.
    """
    if unit_name not in CANONICAL_UNITS:
        raise KeyError(f"unknown canonical-unit name: {unit_name}")
    return f"{value} {CANONICAL_UNITS[unit_name].unit}"
