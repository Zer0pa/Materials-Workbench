"""HomogenisationOperator — L4 microstructure trajectory → L5 effective properties.

Connects L4 (phase-field / kMC) to L5 (continuum FEM/CFD) in the
orchestration chain.  Volume-averages a microstructure trajectory to produce
effective mechanical and thermal properties.

PRD: effective stiffness tensor (SPD-checked), effective thermal conductivity.

Homogenisation strategy
-----------------------
For the stub, we use the Voigt (upper bound) and Reuss (lower bound) mixture
rules for a two-phase composite.  The effective property is the arithmetic mean
of the two bounds (Hill average):

    C_eff = (C_Voigt + C_Reuss) / 2

Both bounds produce SPD tensors when the constituent tensors are SPD, so the
Hill average is also SPD.

The microstructure trajectory is described by a list of
``(phase_label, volume_fraction, time_step)`` tuples.  The trajectory is
time-averaged to produce a single effective property.

Input (from L4 envelope)
------------------------
``microstructure_trajectory``: list of dicts, each with:
    ``phase``: str  — phase label (used to look up material data)
    ``volume_fraction``: float in [0, 1]
    ``time_step``: int

``material_library``: dict[str, dict]  — per-phase elastic/thermal data.

Output (to L5 envelope)
-----------------------
``effective_stiffness_3x3``   — 3×3 Hill-average SPD stiffness (GPa)
``effective_conductivity_3x3`` — 3×3 Voigt isotropic SPD conductivity (W/(m·K))
``stiffness_spd``              — bool
``conductivity_spd``           — bool
"""

from __future__ import annotations

from typing import Any

import numpy as np

# ---------------------------------------------------------------------------
# Voigt / Reuss mixture rules (3x3 isotropic diagonal approximation)
# ---------------------------------------------------------------------------

def _isotropic_3x3(E: float, nu: float) -> np.ndarray:
    """Return 3×3 isotropic stiffness matrix (top-left block of Voigt 6×6)."""
    lam = E * nu / ((1.0 + nu) * (1.0 - 2.0 * nu))
    mu = E / (2.0 * (1.0 + nu))
    C11 = lam + 2.0 * mu
    C12 = lam
    return np.array([
        [C11, C12, C12],
        [C12, C11, C12],
        [C12, C12, C11],
    ])


def _conductivity_3x3(kappa: float) -> np.ndarray:
    """Return 3×3 isotropic thermal conductivity matrix."""
    return kappa * np.eye(3)


def _voigt_average(
    tensors: list[np.ndarray],
    fractions: list[float],
) -> np.ndarray:
    """Voigt (arithmetic) average: C_Voigt = Σ f_i * C_i."""
    result = np.zeros_like(tensors[0])
    for C, f in zip(tensors, fractions):
        result += f * C
    return result


def _reuss_average(
    tensors: list[np.ndarray],
    fractions: list[float],
) -> np.ndarray:
    """Reuss (harmonic) average: S_Reuss = Σ f_i * S_i, then C = S⁻¹."""
    S_avg = np.zeros_like(tensors[0])
    for C, f in zip(tensors, fractions):
        S_i = np.linalg.inv(C)
        S_avg += f * S_i
    return np.linalg.inv(S_avg)


def _hill_average(
    tensors: list[np.ndarray],
    fractions: list[float],
) -> np.ndarray:
    """Hill average: (C_Voigt + C_Reuss) / 2."""
    C_V = _voigt_average(tensors, fractions)
    C_R = _reuss_average(tensors, fractions)
    return (C_V + C_R) / 2.0


def _is_spd(tensor: np.ndarray, tol: float = 1e-10) -> tuple[bool, float]:
    """Check whether ``tensor`` is symmetric positive-definite.

    Returns
    -------
    (is_spd, min_eigenvalue)
    """
    sym_err = float(np.max(np.abs(tensor - tensor.T)))
    if sym_err > tol:
        return False, float(np.linalg.eigvalsh(tensor).min())
    eigvals = np.linalg.eigvalsh(tensor)
    return bool(eigvals.min() > 0.0), float(eigvals.min())


# ---------------------------------------------------------------------------
# Default material library (used when caller does not supply one)
# ---------------------------------------------------------------------------

DEFAULT_MATERIAL_LIBRARY: dict[str, dict[str, float]] = {
    "matrix": {"E_GPa": 200.0, "nu": 0.30, "kappa_W_per_mK": 10.0},
    "precipitate": {"E_GPa": 350.0, "nu": 0.25, "kappa_W_per_mK": 20.0},
    "pore": {"E_GPa": 1e-6,  "nu": 0.00, "kappa_W_per_mK": 0.025},
    # Fallback for unknown phases
    "unknown": {"E_GPa": 100.0, "nu": 0.30, "kappa_W_per_mK": 5.0},
}


# ---------------------------------------------------------------------------
# HomogenisationOperator
# ---------------------------------------------------------------------------

class HomogenisationOperator:
    """Volume-average a microstructure trajectory to produce effective properties.

    Parameters
    ----------
    material_library:
        Dict mapping phase label → ``{E_GPa, nu, kappa_W_per_mK}``.
        Defaults to :data:`DEFAULT_MATERIAL_LIBRARY`.

    Usage::

        operator = HomogenisationOperator()
        result = operator.homogenise(trajectory=[
            {"phase": "matrix",      "volume_fraction": 0.8, "time_step": 0},
            {"phase": "precipitate", "volume_fraction": 0.2, "time_step": 0},
        ])
        # result["effective_stiffness_3x3"]      — 3x3 list[list[float]]
        # result["effective_conductivity_3x3"]   — 3x3 list[list[float]]
        # result["stiffness_spd"]                — bool
        # result["conductivity_spd"]             — bool
    """

    def __init__(
        self,
        material_library: dict[str, dict[str, float]] | None = None,
    ) -> None:
        self.material_library = material_library or DEFAULT_MATERIAL_LIBRARY

    def _resolve_phase_data(self, phase: str) -> dict[str, float]:
        if phase in self.material_library:
            return self.material_library[phase]
        return self.material_library.get("unknown", {"E_GPa": 100.0, "nu": 0.30, "kappa_W_per_mK": 5.0})

    def homogenise(
        self,
        trajectory: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Compute effective properties from a microstructure trajectory.

        Parameters
        ----------
        trajectory:
            List of dicts with keys ``phase``, ``volume_fraction``, and
            optionally ``time_step``.  All entries at each time step must
            have ``volume_fraction`` summing to 1.0 ± 1e-6.

        Returns
        -------
        dict with keys:
            ``effective_stiffness_3x3``    — 3x3 Hill-average stiffness (GPa)
            ``effective_conductivity_3x3`` — 3x3 Voigt-average conductivity (W/(m·K))
            ``stiffness_spd``              — bool
            ``conductivity_spd``           — bool
            ``stiffness_eigmin``           — float (min eigenvalue, GPa)
            ``conductivity_eigmin``        — float (min eigenvalue, W/(m·K))
            ``n_phases``                   — int
            ``n_time_steps``               — int
        """
        if not trajectory:
            raise ValueError("trajectory must be non-empty")

        # Group by time step (or treat all as a single snapshot if no time_step).
        snapshots: dict[int, list[dict[str, Any]]] = {}
        for entry in trajectory:
            ts = entry.get("time_step", 0)
            snapshots.setdefault(ts, []).append(entry)

        C_eff_accum = np.zeros((3, 3))
        K_eff_accum = np.zeros((3, 3))
        n_steps = len(snapshots)

        for ts, entries in snapshots.items():
            fracs = [e["volume_fraction"] for e in entries]
            frac_sum = sum(fracs)
            if abs(frac_sum - 1.0) > 1e-6:
                # Normalise if slightly off.
                fracs = [f / frac_sum for f in fracs]

            phases = [e["phase"] for e in entries]
            C_list = []
            K_list = []
            for phase in phases:
                pdata = self._resolve_phase_data(phase)
                C_list.append(_isotropic_3x3(pdata["E_GPa"], pdata["nu"]))
                K_list.append(_conductivity_3x3(pdata["kappa_W_per_mK"]))

            C_step = _hill_average(C_list, fracs)
            K_step = _voigt_average(K_list, fracs)  # conductivity: Voigt is sufficient

            C_eff_accum += C_step
            K_eff_accum += K_step

        C_eff = C_eff_accum / n_steps
        K_eff = K_eff_accum / n_steps

        C_spd, C_eigmin = _is_spd(C_eff)
        K_spd, K_eigmin = _is_spd(K_eff)

        unique_phases = {e["phase"] for e in trajectory}

        return {
            "effective_stiffness_3x3": C_eff.tolist(),
            "effective_conductivity_3x3": K_eff.tolist(),
            "stiffness_spd": C_spd,
            "conductivity_spd": K_spd,
            "stiffness_eigmin": C_eigmin,
            "conductivity_eigmin": K_eigmin,
            "n_phases": len(unique_phases),
            "n_time_steps": n_steps,
        }
