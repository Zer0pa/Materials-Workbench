"""Nernst-Einstein conductivity formula — testable, unit-checked.

PRD §Ionic Transport requires Nernst-Einstein conductivity (S/cm) computed
from the MD/AIMD/MLIP-MD diffusion coefficient (cm²/s) and the carrier
density (per cm³). The formula:

    sigma_NE [S/cm] = (n_Li [/cm³] * (z * e [C])² * D [cm²/s]) /
                      (k_B [J/K] * T [K]) / 100

Derivation
----------

The SI Nernst-Einstein equation reads::

    sigma [S/m] = n [/m³] * (z * e [C])² * D [m²/s] / (k_B [J/K] * T [K])

Convert to S/cm by dividing by 100 (since 1 S/m = 0.01 S/cm). Convert
n from /cm³ to /m³ by multiplying by 1e6, and D from cm²/s to m²/s by
multiplying by 1e-4. The combined factor is 1e6 * 1e-4 = 1e2, so the
final factor reduces to::

    sigma_NE [S/cm] = (n [/cm³] * (z*e)² * D [cm²/s]) / (k_B * T) / 100

Calibration anchor
------------------

We compute strictly in SI internally and convert at the boundary. The
canonical calibration anchor is:

    T = 300 K, n = 2e22 /cm³, D = 1e-7 cm²/s, z = 1
        -> sigma_NE ≈ 1.2395e-2 S/cm

    T = 300 K, n = 2e22 /cm³, D = 1e-8 cm²/s, z = 1
        -> sigma_NE ≈ 1.2395e-3 S/cm

Note: the wave brief stated the first case yields ~1.24e-3 S/cm, but
that target requires D = 1e-8 cm²/s (not 1e-7). We follow the
**physically correct** formula and assert against the value the formula
actually produces (1.24e-2 at D=1e-7). Both anchors are pinned in the
unit tests.

Why the discrepancy matters
---------------------------

A factor of ten in conductivity is exactly the magnitude that controls
whether a battery candidate clears the 1e-3 S/cm threshold. Documenting
the discrepancy is required by the "calibrated uncertainty" discipline.
The IonicTransportService stub data is calibrated to D ≈ 1e-7 cm²/s for
fast solid electrolytes (LLZO, Li6PS5Cl), giving room-temperature
sigma_NE in the 1e-2 to 1e-3 S/cm range and clearing the 1e-3 gate.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = [
    "BOLTZMANN_J_PER_K",
    "ELEMENTARY_CHARGE_C",
    "HavenRatio",
    "nernst_einstein_conductivity",
]


# Physical constants (CODATA 2018).
ELEMENTARY_CHARGE_C: float = 1.602176634e-19  # exact by definition (SI 2019)
BOLTZMANN_J_PER_K: float = 1.380649e-23  # exact by definition (SI 2019)


@dataclass(frozen=True)
class HavenRatio:
    """Haven ratio H_R = sigma_NE / sigma_measured (dimensionless).

    Default 1.0 means we assume the Nernst-Einstein conductivity equals
    the tracer-derived measured conductivity. Real systems show
    H_R < 1 (correlated motion lowers measured conductivity below the
    diffusion-derived prediction). Document the assumption in
    ``rationale``.
    """

    value: float = 1.0
    rationale: str = "Haven ratio default 1.0; correlated motion not yet modelled."

    def adjust(self, sigma_ne: float) -> float:
        """Apply the Haven ratio: sigma_measured = sigma_NE / H_R."""
        if self.value <= 0:
            raise ValueError("Haven ratio must be > 0.")
        return sigma_ne / self.value


def nernst_einstein_conductivity(
    diffusion_cm2_per_s: float,
    carrier_concentration_per_cm3: float,
    temperature_K: float,
    charge_number: int = 1,
    haven_ratio: float = 1.0,
) -> float:
    """Compute Nernst-Einstein ionic conductivity in S/cm.

    Parameters
    ----------
    diffusion_cm2_per_s
        Tracer / self-diffusion coefficient D, in cm²/s.
    carrier_concentration_per_cm3
        Mobile-ion carrier density n, in /cm³.
    temperature_K
        Absolute temperature T, in K.
    charge_number
        Mobile-ion charge state z (default 1 for Li+).
    haven_ratio
        Haven ratio H_R = sigma_NE / sigma_measured. Default 1.0.

    Returns
    -------
    sigma_NE_S_per_cm
        Nernst-Einstein conductivity in S/cm. The Haven ratio is applied
        AFTER the bare formula to keep the two factors testable
        independently.

    Implementation
    --------------

    We compute in SI internally:

    * n_SI [1/m³] = n_cm3 * 1e6
    * D_SI [m²/s] = D_cm2 * 1e-4
    * sigma_SI [S/m] = n_SI * (z*e)² * D_SI / (k_B * T)
    * sigma_S_per_cm = sigma_SI / 100

    Then divide by ``haven_ratio`` so the caller can request a
    measurement-corrected estimate.
    """
    if diffusion_cm2_per_s < 0:
        raise ValueError("diffusion coefficient must be non-negative.")
    if carrier_concentration_per_cm3 <= 0:
        raise ValueError("carrier concentration must be > 0.")
    if temperature_K <= 0:
        raise ValueError("temperature must be > 0.")
    if haven_ratio <= 0:
        raise ValueError("haven ratio must be > 0.")
    if charge_number == 0:
        raise ValueError("charge number must be non-zero.")

    n_si = carrier_concentration_per_cm3 * 1e6  # /m³
    d_si = diffusion_cm2_per_s * 1e-4  # m²/s
    z2e2 = (charge_number * ELEMENTARY_CHARGE_C) ** 2  # C²
    sigma_si = (n_si * z2e2 * d_si) / (BOLTZMANN_J_PER_K * temperature_K)  # S/m
    sigma_S_per_cm = sigma_si / 100.0
    return sigma_S_per_cm / haven_ratio
