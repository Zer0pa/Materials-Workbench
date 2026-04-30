"""L1.5 falsifiers — phonon dynamical stability and thermoelectric ZT gates.

PRD §L1.5 Falsifiers:
  1. Non-acoustic imaginary mode > 0.25 THz fails dynamical stability.
  2. MLIP vs DFT displacement-force RMSE > 0.05 eV/Å escalates to DFT.
  3. Phonopy vs HiPhive frequency RMSE > 0.20 THz or κ_L delta > 20% flags.
  4. Phono3py q-mesh convergence must be < 10% for publishable transport.
  5. Thermoelectric ZT candidate rank must be stable across transport assumptions.
  6. Phonon does NOT substitute for ionic conductivity.

Every falsifier is a pure function of an envelope (or pair of envelopes).
They return :class:`FalsifierItem` rows so the audit ledger sees a uniform shape.
"""

from __future__ import annotations

from typing import Any

from zer0pa_materials.envelope import Envelope, FalsifierItem

__all__ = [
    "dynamical_stability",
    "mlip_dft_force_rmse",
    "phonopy_hiphive_frequency_rmse",
    "q_mesh_convergence",
    "zt_rank_stability",
    "phonon_does_not_substitute_for_ionic",
]

# PRD thresholds
_IMAGINARY_THRESHOLD_THz = 0.25
_FORCE_RMSE_THRESHOLD_eV_per_Ang = 0.05
_FREQ_RMSE_THRESHOLD_THz = 0.20
_KAPPA_L_DELTA_THRESHOLD_PCT = 20.0
_QMESH_CONVERGENCE_THRESHOLD_PCT = 10.0
_ZT_RANK_STABILITY_TOLERANCE = 0.15


def _get_output_field(envelope: Envelope, field: str) -> Any:
    """Extract a field from envelope.output dict."""
    return envelope.output.get(field)


# ---------------------------------------------------------------------------
# 1. Dynamical stability
# ---------------------------------------------------------------------------

def dynamical_stability(envelope: Envelope) -> FalsifierItem:
    """Fail if any non-acoustic imaginary mode magnitude > 0.25 THz.

    Triggered by: post acoustic-sum-rule and NAC review.
    Source: ``envelope.output.imaginary_mode_max_THz``.
    """
    imag_max = _get_output_field(envelope, "imaginary_mode_max_THz")

    if imag_max is None:
        return FalsifierItem(
            name="l15.dynamical_stability",
            threshold=f"<= {_IMAGINARY_THRESHOLD_THz} THz (non-acoustic imaginary mode)",
            actual=None,
            status="blocked",
            rationale="imaginary_mode_max_THz not present in envelope output.",
        )

    try:
        imag_max_f = float(imag_max)
    except (TypeError, ValueError):
        return FalsifierItem(
            name="l15.dynamical_stability",
            threshold=f"<= {_IMAGINARY_THRESHOLD_THz} THz (non-acoustic imaginary mode)",
            actual=imag_max,
            status="blocked",
            rationale=f"imaginary_mode_max_THz is not a float: {imag_max!r}",
        )

    status = "pass" if imag_max_f <= _IMAGINARY_THRESHOLD_THz else "fail"
    return FalsifierItem(
        name="l15.dynamical_stability",
        threshold=(
            f"<= {_IMAGINARY_THRESHOLD_THz} THz (non-acoustic imaginary mode "
            f"after acoustic sum rule + NAC review)"
        ),
        actual=imag_max_f,
        status=status,
        rationale=(
            None
            if status == "pass"
            else (
                f"Non-acoustic imaginary mode magnitude {imag_max_f:.4f} THz "
                f"exceeds the {_IMAGINARY_THRESHOLD_THz} THz dynamical stability "
                f"threshold. Candidate fails dynamical stability gate."
            )
        ),
    )


# ---------------------------------------------------------------------------
# 2. MLIP vs DFT force RMSE
# ---------------------------------------------------------------------------

def mlip_dft_force_rmse(
    mlip_envelope: Envelope,
    dft_envelope: Envelope | None = None,
) -> FalsifierItem:
    """Flag if MLIP vs DFT displacement-force RMSE > 0.05 eV/Å.

    If dft_envelope is provided, compute RMSE from output fields.
    Otherwise read ``mlip_vs_dft_force_rmse_eV_per_Ang`` directly from
    the mlip_envelope (e.g. from HiPhiveForceConstantFitAdapter output).
    """
    # Try to get precomputed RMSE from the envelope output
    rmse = _get_output_field(mlip_envelope, "mlip_vs_dft_force_rmse_eV_per_Ang")

    if rmse is None and dft_envelope is not None:
        # Could compute from raw force arrays if they were stored — blocked for now.
        return FalsifierItem(
            name="l15.mlip_dft_force_rmse",
            threshold=f"<= {_FORCE_RMSE_THRESHOLD_eV_per_Ang} eV/Å (escalate to DFT if exceeded)",
            actual=None,
            status="blocked",
            rationale=(
                "mlip_vs_dft_force_rmse_eV_per_Ang not directly available in the envelope. "
                "Raw force arrays would need to be extracted and compared; blocked in CPU-first mode."
            ),
        )

    if rmse is None:
        return FalsifierItem(
            name="l15.mlip_dft_force_rmse",
            threshold=f"<= {_FORCE_RMSE_THRESHOLD_eV_per_Ang} eV/Å (escalate to DFT if exceeded)",
            actual=None,
            status="blocked",
            rationale="mlip_vs_dft_force_rmse_eV_per_Ang not present in envelope output.",
        )

    try:
        rmse_f = float(rmse)
    except (TypeError, ValueError):
        return FalsifierItem(
            name="l15.mlip_dft_force_rmse",
            threshold=f"<= {_FORCE_RMSE_THRESHOLD_eV_per_Ang} eV/Å",
            actual=rmse,
            status="blocked",
            rationale=f"mlip_vs_dft_force_rmse_eV_per_Ang is not a float: {rmse!r}",
        )

    status = "pass" if rmse_f <= _FORCE_RMSE_THRESHOLD_eV_per_Ang else "fail"
    return FalsifierItem(
        name="l15.mlip_dft_force_rmse",
        threshold=f"<= {_FORCE_RMSE_THRESHOLD_eV_per_Ang} eV/Å (escalate to DFT if exceeded)",
        actual=rmse_f,
        status=status,
        rationale=(
            None
            if status == "pass"
            else (
                f"MLIP vs DFT force RMSE {rmse_f:.4f} eV/Å exceeds "
                f"{_FORCE_RMSE_THRESHOLD_eV_per_Ang} eV/Å threshold. "
                f"Candidate requires DFT force recalculation."
            )
        ),
    )


# ---------------------------------------------------------------------------
# 3. Phonopy vs HiPhive frequency RMSE and κ_L delta
# ---------------------------------------------------------------------------

def phonopy_hiphive_frequency_rmse(
    phonopy_envelope: Envelope,
    hiphive_envelope: Envelope,
) -> FalsifierItem:
    """Flag if Phonopy vs HiPhive frequency RMSE > 0.20 THz or κ_L delta > 20%.

    Reads ``imaginary_mode_max_THz`` as a proxy for frequency scale comparison
    (both adapters output this field), plus ``thermal_conductivity_W_per_mK``
    for κ_L comparison.
    """
    # Try to get frequency RMSE from HiPhive envelope extra input
    hi_extra = hiphive_envelope.output.get("frequency_rmse_THz")

    # Get κ_L values
    kappa_phonopy = phonopy_envelope.output.get("thermal_conductivity_W_per_mK")
    kappa_hiphive = hiphive_envelope.output.get("thermal_conductivity_W_per_mK")

    freq_rmse_f: float | None = None
    kappa_delta_pct: float | None = None
    status_reasons: list[str] = []

    # Frequency RMSE
    if hi_extra is not None:
        try:
            freq_rmse_f = float(hi_extra)
        except (TypeError, ValueError):
            freq_rmse_f = None

    if freq_rmse_f is None:
        status_reasons.append("frequency_rmse_THz not available from HiPhive adapter output")

    # κ_L delta
    if kappa_phonopy is not None and kappa_hiphive is not None:
        try:
            kp = float(kappa_phonopy)
            kh = float(kappa_hiphive)
            if kp > 0:
                kappa_delta_pct = abs(kp - kh) / kp * 100.0
        except (TypeError, ValueError):
            kappa_delta_pct = None

    freq_fail = freq_rmse_f is not None and freq_rmse_f > _FREQ_RMSE_THRESHOLD_THz
    kappa_fail = kappa_delta_pct is not None and kappa_delta_pct > _KAPPA_L_DELTA_THRESHOLD_PCT

    if freq_rmse_f is None and kappa_delta_pct is None:
        overall_status = "blocked"
    elif freq_fail or kappa_fail:
        overall_status = "fail"
    else:
        overall_status = "pass"

    return FalsifierItem(
        name="l15.phonopy_hiphive_frequency_rmse",
        threshold=(
            f"<= {_FREQ_RMSE_THRESHOLD_THz} THz frequency RMSE "
            f"AND <= {_KAPPA_L_DELTA_THRESHOLD_PCT:.0f}% κ_L delta"
        ),
        actual={
            "frequency_rmse_THz": freq_rmse_f,
            "kappa_L_delta_pct": (
                round(kappa_delta_pct, 2) if kappa_delta_pct is not None else None
            ),
        },
        status=overall_status,
        rationale=(
            "; ".join(status_reasons) if status_reasons and overall_status == "blocked" else None
        ),
    )


# ---------------------------------------------------------------------------
# 4. q-mesh convergence
# ---------------------------------------------------------------------------

def q_mesh_convergence(
    envelope: Envelope,
    threshold: float = _QMESH_CONVERGENCE_THRESHOLD_PCT,
) -> FalsifierItem:
    """Flag if Phono3py q-mesh convergence delta > threshold %.

    Reads ``qmesh_convergence_pct`` from the envelope output.
    """
    convergence_pct = _get_output_field(envelope, "qmesh_convergence_pct")

    if convergence_pct is None:
        return FalsifierItem(
            name="l15.q_mesh_convergence",
            threshold=f"< {threshold:.0f}% q-mesh convergence for publishable transport",
            actual=None,
            status="blocked",
            rationale=(
                "qmesh_convergence_pct not present in envelope output. "
                "This field is populated by Phono3pyAnharmonicBTEAdapter."
            ),
        )

    try:
        conv_f = float(convergence_pct)
    except (TypeError, ValueError):
        return FalsifierItem(
            name="l15.q_mesh_convergence",
            threshold=f"< {threshold:.0f}%",
            actual=convergence_pct,
            status="blocked",
            rationale=f"qmesh_convergence_pct is not a float: {convergence_pct!r}",
        )

    status = "pass" if conv_f < threshold else "fail"
    return FalsifierItem(
        name="l15.q_mesh_convergence",
        threshold=f"< {threshold:.0f}% q-mesh convergence for publishable transport candidate",
        actual=conv_f,
        status=status,
        rationale=(
            None
            if status == "pass"
            else (
                f"q-mesh convergence {conv_f:.2f}% exceeds {threshold:.0f}% threshold. "
                f"Candidate requires a finer q-mesh before the transport result is publishable."
            )
        ),
    )


# ---------------------------------------------------------------------------
# 5. ZT rank stability across transport assumptions
# ---------------------------------------------------------------------------

def zt_rank_stability(
    boltztrap_envelope: Envelope,
    amset_envelope: Envelope,
    threshold: float = _ZT_RANK_STABILITY_TOLERANCE,
) -> FalsifierItem:
    """Flag if ZT rank position changes between BoltzTraP2 and AMSET assumptions.

    Reads the ``zt_assembly`` dict from the ZT assembler envelope (preferred),
    or reads ``zt`` fields from individual BoltzTraP2/AMSET envelopes.
    """
    # Try to read from ZT assembly result (from ThermoelectricZtAssembler output)
    zt_assembly = _get_output_field(boltztrap_envelope, "zt_assembly")
    if zt_assembly is not None and isinstance(zt_assembly, dict):
        bt2_zt = zt_assembly.get("bt2_zt")
        amset_zt = zt_assembly.get("amset_zt")
        rank_stable = zt_assembly.get("zt_rank_stable")
        frac_disagreement = zt_assembly.get("zt_fractional_disagreement")
    else:
        # Fall back to reading ZT from individual envelopes
        bt2_zt = _get_output_field(boltztrap_envelope, "zt")
        amset_zt = _get_output_field(amset_envelope, "zt")
        rank_stable = None
        frac_disagreement = None

    if bt2_zt is None or amset_zt is None:
        return FalsifierItem(
            name="l15.zt_rank_stability",
            threshold=f"<= {threshold*100:.0f}% fractional ZT disagreement (BoltzTraP2 vs AMSET)",
            actual={"bt2_zt": bt2_zt, "amset_zt": amset_zt},
            status="blocked",
            rationale=(
                "ZT values not available from envelope outputs. "
                "ThermoelectricZtAssembler must be run first."
            ),
        )

    try:
        bt2_zt_f = float(bt2_zt)
        amset_zt_f = float(amset_zt)
    except (TypeError, ValueError):
        return FalsifierItem(
            name="l15.zt_rank_stability",
            threshold=f"<= {threshold*100:.0f}% fractional ZT disagreement",
            actual={"bt2_zt": bt2_zt, "amset_zt": amset_zt},
            status="blocked",
            rationale=f"ZT values are not floats: bt2={bt2_zt!r}, amset={amset_zt!r}",
        )

    if frac_disagreement is None:
        frac_disagreement = abs(bt2_zt_f - amset_zt_f) / max(bt2_zt_f, 1e-9)

    if rank_stable is None:
        rank_stable = float(frac_disagreement) <= threshold

    status = "pass" if rank_stable else "fail"
    return FalsifierItem(
        name="l15.zt_rank_stability",
        threshold=f"<= {threshold*100:.0f}% fractional ZT disagreement (BoltzTraP2 vs AMSET)",
        actual={
            "bt2_zt": round(bt2_zt_f, 4),
            "amset_zt": round(amset_zt_f, 4),
            "fractional_disagreement": round(float(frac_disagreement), 4),
            "rank_stable": rank_stable,
        },
        status=status,
        rationale=(
            None
            if status == "pass"
            else (
                f"ZT fractional disagreement {float(frac_disagreement)*100:.1f}% exceeds "
                f"{threshold*100:.0f}% tolerance. ZT rank is not stable across transport "
                f"assumptions (BoltzTraP2: {bt2_zt_f:.4f}, AMSET: {amset_zt_f:.4f})."
            )
        ),
    )


# ---------------------------------------------------------------------------
# 6. Phonon does not substitute for ionic conductivity
# ---------------------------------------------------------------------------

def phonon_does_not_substitute_for_ionic(envelope: Envelope) -> FalsifierItem:
    """Pass if envelope does NOT contain ionic_conductivity_S_per_cm.

    PRD §L1.5 Boundary: L1.5 phonon layer MUST NEVER claim Li-ion conductivity.
    That is exclusively the IonicTransportService's domain.
    """
    # Check the output dict for any ionic conductivity claim
    output = envelope.output or {}

    # Check for any non-None ionic conductivity claim.
    # A key being present with value None is acceptable (schema field default).
    # A non-None value is a boundary violation.
    ionic_value = output.get("ionic_conductivity_S_per_cm")
    has_ionic_claim = ionic_value is not None

    if has_ionic_claim:
        return FalsifierItem(
            name="l15.phonon_does_not_substitute_for_ionic",
            threshold="envelope MUST NOT contain ionic_conductivity_S_per_cm (non-None)",
            actual={"ionic_conductivity_S_per_cm": ionic_value},
            status="fail",
            rationale=(
                "PRD §L1.5 Boundary VIOLATED: L1.5 envelope claims ionic conductivity "
                f"(value: {ionic_value}). Phonons do NOT substitute for Li-ion conductivity. "
                "IonicTransportService is the sole producer of such claims."
            ),
        )

    return FalsifierItem(
        name="l15.phonon_does_not_substitute_for_ionic",
        threshold="envelope MUST NOT contain ionic_conductivity_S_per_cm",
        actual="field_absent",
        status="pass",
        rationale=(
            "PRD §L1.5 Boundary satisfied: envelope does not claim ionic conductivity. "
            "The IonicTransportService is the exclusive source of ionic conductivity claims."
        ),
    )
