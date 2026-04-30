"""L5 continuum falsifiers (PRD §L5 Falsifiers).

All falsifiers accept an ``envelope`` dict (wire-level, as emitted by
L5 adapters) and return a ``FalsifierItem``.

PRD-mandated gates:
    Reject non-SPD stiffness or conductivity tensors
    Analytic heat slab error < 1e-6
    Elastic patch residual < 1e-8
    FEniCSx vs deal.II strain energy disagreement < 2%
    OpenFOAM Poiseuille profile error < 5%
    CFD mass balance error < 1e-4
    CFD heat balance error < 1e-4
    VTK/Exodus/FMI artifacts must include units sidecars and hashes

SPD check uses numpy.linalg.eigvalsh for numerical robustness (PRD discipline).
"""

from __future__ import annotations

from typing import Any

import numpy as np

from zer0pa_materials.envelope.falsifier import FalsifierItem, FalsifierStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_output(envelope: dict[str, Any]) -> dict[str, Any]:
    """Extract and validate the output sub-dict from an envelope."""
    out = envelope.get("output")
    if not isinstance(out, dict):
        raise ValueError(
            f"envelope.output is missing or not a dict; got {type(out)}"
        )
    return out


def _status_le(actual: float | None, threshold: float) -> FalsifierStatus:
    if actual is None:
        return "blocked"
    return "pass" if actual <= threshold else "fail"


def _status_lt(actual: float | None, threshold: float) -> FalsifierStatus:
    if actual is None:
        return "blocked"
    return "pass" if actual < threshold else "fail"


# ---------------------------------------------------------------------------
# tensor_spd_check
# ---------------------------------------------------------------------------


def tensor_spd_check(
    tensor: list[list[float]] | Any,
    name: str = "tensor",
    symmetry_tol: float = 1e-10,
) -> FalsifierItem:
    """Check that ``tensor`` is symmetric positive-definite.

    Uses ``numpy.linalg.eigvalsh`` for numerical robustness (PRD discipline).
    Symmetry is checked to within ``symmetry_tol``.

    Parameters
    ----------
    tensor:
        2D list-of-lists or numpy array (must be square, 3×3 or 6×6).
    name:
        Human-readable name for the tensor (e.g. ``"stiffness_C_3x3"``).
    symmetry_tol:
        Tolerance for symmetry check: ``max|A - A^T| <= symmetry_tol``.

    Returns
    -------
    FalsifierItem
        * ``pass``    — tensor is symmetric and all eigenvalues > 0.
        * ``fail``    — tensor is not symmetric or has a non-positive eigenvalue.
        * ``blocked`` — tensor cannot be parsed as a numeric array.
    """
    try:
        arr = np.array(tensor, dtype=float)
    except (TypeError, ValueError) as exc:
        return FalsifierItem(
            name="l5.tensor_spd",
            threshold=f"symmetric + all eigenvalues > 0 (tensor: {name!r})",
            actual=None,
            status="blocked",
            rationale=f"tensor cannot be parsed as a numeric array: {exc}",
        )

    if arr.ndim != 2 or arr.shape[0] != arr.shape[1]:
        return FalsifierItem(
            name="l5.tensor_spd",
            threshold=f"symmetric + all eigenvalues > 0 (tensor: {name!r})",
            actual={"shape": list(arr.shape)},
            status="fail",
            rationale="tensor must be a square 2D array",
        )

    sym_err = float(np.max(np.abs(arr - arr.T)))
    if sym_err > symmetry_tol:
        return FalsifierItem(
            name="l5.tensor_spd",
            threshold=f"symmetric (|A - A^T|_inf <= {symmetry_tol}) + all eigenvalues > 0 (tensor: {name!r})",
            actual={"symmetry_error": sym_err, "n": arr.shape[0]},
            status="fail",
            rationale=f"tensor is not symmetric: max|A - A^T| = {sym_err:.3e} > tol={symmetry_tol}",
        )

    eigvals = np.linalg.eigvalsh(arr)
    eigmin = float(eigvals.min())
    spd = bool(eigmin > 0.0)

    return FalsifierItem(
        name="l5.tensor_spd",
        threshold=f"symmetric + all eigenvalues > 0 (tensor: {name!r})",
        actual={"eigvals_min": eigmin, "n": arr.shape[0], "tensor_name": name},
        status="pass" if spd else "fail",
    )


# ---------------------------------------------------------------------------
# analytic_heat_slab_error
# ---------------------------------------------------------------------------


def analytic_heat_slab_error(
    envelope: dict[str, Any],
    threshold: float = 1e-6,
) -> FalsifierItem:
    """Check that the 1D heat slab analytic error is < threshold.

    Reads ``output.analytic_heat_slab_error`` from the envelope.

    Parameters
    ----------
    envelope:
        L5 Envelope dict.
    threshold:
        Maximum allowed relative L2 error (default 1e-6 per PRD).
    """
    try:
        output = _get_output(envelope)
    except ValueError:
        return FalsifierItem(
            name="l5.analytic_heat_slab_error",
            threshold=f"< {threshold:.0e}",
            actual=None,
            status="blocked",
        )

    actual = output.get("analytic_heat_slab_error")

    return FalsifierItem(
        name="l5.analytic_heat_slab_error",
        threshold=f"< {threshold:.0e} (relative L2 error vs analytic T(x))",
        actual=actual,
        status=_status_lt(actual, threshold),
    )


# ---------------------------------------------------------------------------
# elastic_patch_residual
# ---------------------------------------------------------------------------


def elastic_patch_residual(
    envelope: dict[str, Any],
    threshold: float = 1e-8,
) -> FalsifierItem:
    """Check that the 2D elasticity patch test residual is < threshold.

    Reads ``output.elastic_patch_residual`` from the envelope.

    Parameters
    ----------
    envelope:
        L5 Envelope dict.
    threshold:
        Maximum allowed residual (default 1e-8 per PRD).
    """
    try:
        output = _get_output(envelope)
    except ValueError:
        return FalsifierItem(
            name="l5.elastic_patch_residual",
            threshold=f"< {threshold:.0e}",
            actual=None,
            status="blocked",
        )

    actual = output.get("elastic_patch_residual")

    return FalsifierItem(
        name="l5.elastic_patch_residual",
        threshold=f"< {threshold:.0e} (max nodal residual / prescribed strain)",
        actual=actual,
        status=_status_lt(actual, threshold),
    )


# ---------------------------------------------------------------------------
# fenicsx_dealii_strain_energy_disagreement
# ---------------------------------------------------------------------------


def fenicsx_dealii_strain_energy_disagreement(
    env_a: dict[str, Any],
    env_b: dict[str, Any],
    threshold: float = 0.02,
) -> FalsifierItem:
    """Check FEniCSx vs deal.II strain energy disagreement < threshold.

    Reads ``output.fenicsx_vs_dealii_strain_energy_disagreement_pct`` from
    whichever envelope carries a non-None value for that field.  If both
    carry it, the average is used.

    Parameters
    ----------
    env_a, env_b:
        L5 Envelope dicts from FEniCSx and deal.II respectively.
    threshold:
        Maximum allowed fractional disagreement (default 0.02 = 2% per PRD).
    """
    try:
        out_a = _get_output(env_a)
        out_b = _get_output(env_b)
    except ValueError:
        return FalsifierItem(
            name="l5.fenicsx_dealii_strain_energy_disagreement",
            threshold=f"< {threshold * 100:.0f}%",
            actual=None,
            status="blocked",
        )

    # Prefer the deal.II envelope's disagreement field (it was computed with
    # respect to the analytic value), but fall back to FEniCSx if present.
    disagree_b = out_b.get("fenicsx_vs_dealii_strain_energy_disagreement_pct")
    disagree_a = out_a.get("fenicsx_vs_dealii_strain_energy_disagreement_pct")

    actual_pct: float | None = None
    if disagree_b is not None:
        actual_pct = disagree_b
    elif disagree_a is not None:
        actual_pct = disagree_a

    threshold_pct = threshold * 100.0

    status: FalsifierStatus
    if actual_pct is None:
        status = "blocked"
    elif actual_pct < threshold_pct:
        status = "pass"
    else:
        status = "fail"

    return FalsifierItem(
        name="l5.fenicsx_dealii_strain_energy_disagreement",
        threshold=f"< {threshold_pct:.0f}% FEniCSx vs deal.II strain energy",
        actual=actual_pct,
        status=status,
    )


# ---------------------------------------------------------------------------
# openfoam_poiseuille_profile_error
# ---------------------------------------------------------------------------


def openfoam_poiseuille_profile_error(
    envelope: dict[str, Any],
    threshold: float = 0.05,
) -> FalsifierItem:
    """Check that the Poiseuille flow profile error is < threshold.

    Reads ``output.openfoam_poiseuille_error_pct`` from the envelope.

    Parameters
    ----------
    envelope:
        L5 Envelope dict.
    threshold:
        Maximum allowed relative L2 error in percent (default 5% per PRD;
        i.e., the stored value must be < 5.0).
    """
    try:
        output = _get_output(envelope)
    except ValueError:
        return FalsifierItem(
            name="l5.openfoam_poiseuille_error",
            threshold=f"< {threshold * 100:.0f}%",
            actual=None,
            status="blocked",
        )

    actual_pct = output.get("openfoam_poiseuille_error_pct")
    threshold_pct = threshold * 100.0

    return FalsifierItem(
        name="l5.openfoam_poiseuille_error",
        threshold=f"< {threshold_pct:.0f}% relative L2 error vs analytic Poiseuille",
        actual=actual_pct,
        status=_status_lt(actual_pct, threshold_pct),
    )


# ---------------------------------------------------------------------------
# cfd_mass_balance_error
# ---------------------------------------------------------------------------


def cfd_mass_balance_error(
    envelope: dict[str, Any],
    threshold: float = 1e-4,
) -> FalsifierItem:
    """Check that the CFD mass balance error is < threshold.

    Reads ``output.cfd_mass_balance_error`` from the envelope.
    """
    try:
        output = _get_output(envelope)
    except ValueError:
        return FalsifierItem(
            name="l5.cfd_mass_balance_error",
            threshold=f"< {threshold:.0e}",
            actual=None,
            status="blocked",
        )

    actual = output.get("cfd_mass_balance_error")

    return FalsifierItem(
        name="l5.cfd_mass_balance_error",
        threshold=f"< {threshold:.0e} (|mass_in - mass_out| / mass_in)",
        actual=actual,
        status=_status_lt(actual, threshold),
    )


# ---------------------------------------------------------------------------
# cfd_heat_balance_error
# ---------------------------------------------------------------------------


def cfd_heat_balance_error(
    envelope: dict[str, Any],
    threshold: float = 1e-4,
) -> FalsifierItem:
    """Check that the CFD heat balance error is < threshold.

    Reads ``output.cfd_heat_balance_error`` from the envelope.
    """
    try:
        output = _get_output(envelope)
    except ValueError:
        return FalsifierItem(
            name="l5.cfd_heat_balance_error",
            threshold=f"< {threshold:.0e}",
            actual=None,
            status="blocked",
        )

    actual = output.get("cfd_heat_balance_error")

    return FalsifierItem(
        name="l5.cfd_heat_balance_error",
        threshold=f"< {threshold:.0e} (|heat_in - heat_out| / heat_in)",
        actual=actual,
        status=_status_lt(actual, threshold),
    )


# ---------------------------------------------------------------------------
# artifact_units_sidecar_present
# ---------------------------------------------------------------------------


def artifact_units_sidecar_present(
    envelope: dict[str, Any],
) -> FalsifierItem:
    """Check that VTK/Exodus/FMI artifacts carry units sidecars and hashes.

    Reads ``_artifact_sidecars`` from the envelope (a list of artifact dicts
    emitted by ``ContinuumHandoffCodec``).  Each artifact dict must have:
    * ``units`` — non-empty dict
    * ``sha256`` — non-empty string

    If ``_artifact_sidecars`` is absent or empty, returns ``pass``
    (no artifacts emitted — gate not applicable).

    If any artifact is missing ``units`` or ``sha256``, returns ``fail``.

    Returns
    -------
    FalsifierItem
        * ``pass``    — all artifacts have units + hash, or no artifacts.
        * ``fail``    — at least one artifact is missing units or hash.
        * ``blocked`` — envelope output is malformed.
    """
    try:
        _get_output(envelope)
    except ValueError:
        return FalsifierItem(
            name="l5.artifact_units_sidecar",
            threshold="all VTK/Exodus/FMI artifacts carry units sidecar + sha256",
            actual=None,
            status="blocked",
        )

    artifacts = envelope.get("_artifact_sidecars", [])
    if not artifacts:
        return FalsifierItem(
            name="l5.artifact_units_sidecar",
            threshold="all VTK/Exodus/FMI artifacts carry units sidecar + sha256",
            actual={"n_artifacts": 0},
            status="pass",
        )

    failing: list[str] = []
    for art in artifacts:
        if not isinstance(art, dict):
            failing.append("<non-dict-artifact>")
            continue
        fmt = art.get("format", "unknown")
        if not art.get("units"):
            failing.append(f"{fmt}:missing_units")
        if not art.get("sha256"):
            failing.append(f"{fmt}:missing_sha256")

    status: FalsifierStatus = "fail" if failing else "pass"
    return FalsifierItem(
        name="l5.artifact_units_sidecar",
        threshold="all VTK/Exodus/FMI artifacts carry units sidecar + sha256",
        actual={"n_artifacts": len(artifacts), "failures": failing},
        status=status,
    )
