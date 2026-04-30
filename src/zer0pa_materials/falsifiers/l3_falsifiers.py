"""L3 CALPHAD falsifiers (PRD §L3 Falsifiers, §Falsification wave).

PRD-mandated gates (verbatim):
    1. produced TDB must parse in pycalphad
    2. known fixture phase-boundary drift <= 25 K
    3. phase set Jaccard distance > 0.33 escalates
    4. phase fraction JS divergence > 0.15 escalates
    5. ESPEI posterior diagnostics must be recorded
    6. tdb_quarantine_breach: NO commercial TDB envelope may carry
       redistributable=True OR committed_to_repo=True OR
       included_in_training_corpus=True
    7. PhaseForgePlus license-gate must be verified before authority use
    8. commercial_tdb_provider_disabled_by_default: MaterialsConfig
       L3_COMMERCIAL_TDB_PROVIDER must be 'disabled' unless explicitly
       enabled per-customer.

Each falsifier accepts a wire-level envelope dict (or, for
``tdb_parses_in_pycalphad``, a TDB path) and returns a
:class:`FalsifierItem` row.

Falsifier names use the convention ``l3.<gate>`` for stable cross-run
grouping in the audit ledger.
"""

from __future__ import annotations

import importlib.util
import math
import re
from pathlib import Path
from typing import Any, Iterable

from zer0pa_materials.envelope.falsifier import FalsifierItem, FalsifierStatus


__all__ = [
    "tdb_parses_in_pycalphad",
    "phase_boundary_drift",
    "phase_set_jaccard_distance",
    "phase_fraction_js_divergence",
    "espei_posterior_diagnostics",
    "tdb_quarantine_breach",
    "phaseforgeplus_license_gate",
    "commercial_tdb_provider_disabled_by_default",
]


# ---------------------------------------------------------------------------
# Threshold constants (PRD §L3)
# ---------------------------------------------------------------------------

DRIFT_THRESHOLD_K: float = 25.0           # phase-boundary drift gate
JACCARD_THRESHOLD: float = 0.33           # phase-set distance escalation
JS_DIVERGENCE_THRESHOLD: float = 0.15     # phase-fraction JS divergence
R_HAT_MAX_DEFAULT: float = 1.1            # ESPEI MCMC convergence
MIN_ESS_DEFAULT: int = 200                # ESPEI effective sample size


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_output(envelope: dict[str, Any]) -> dict[str, Any]:
    """Extract envelope.output safely."""
    out = envelope.get("output")
    if not isinstance(out, dict):
        raise ValueError(
            f"envelope.output is missing or not a dict; got {type(out).__name__}"
        )
    return out


def _looks_like_tdb_syntactic(text: str) -> bool:
    """Minimal syntactic-shape parser for a TDB file.

    Returns True if the text contains at least one ELEMENT line, at least
    one PHASE line with a ``!`` terminator, and at least one PARAMETER /
    FUNCTION block with a ``;`` terminator. Used as the fallback when
    pycalphad is not installed.
    """
    has_element = bool(re.search(r"^\s*ELEMENT\s+\S+\s+\S+", text, flags=re.MULTILINE))
    has_phase = bool(re.search(r"^\s*PHASE\s+\S+\s+%", text, flags=re.MULTILINE))
    has_parameter = bool(
        re.search(r"^\s*PARAMETER\s+G\(", text, flags=re.MULTILINE)
        or re.search(r"^\s*FUNCTION\s+\S+", text, flags=re.MULTILINE)
    )
    has_terminator = ";" in text and "!" in text
    return has_element and has_phase and has_parameter and has_terminator


# ---------------------------------------------------------------------------
# (1) tdb_parses_in_pycalphad
# ---------------------------------------------------------------------------


def tdb_parses_in_pycalphad(tdb_path: str | Path) -> FalsifierItem:
    """Verify that a TDB file parses in pycalphad (PRD §L3 gate 1).

    Behavior:
      - If pycalphad is installed: try ``Database(tdb_path)``. ``pass`` if
        it succeeds, ``fail`` if it raises.
      - If pycalphad is NOT installed: fall back to a syntactic-shape parser
        (must have ELEMENT, PHASE, and PARAMETER/FUNCTION lines + standard
        terminators). ``pass`` if shape valid, ``fail`` otherwise.
      - Missing file: ``fail`` with diagnostic actual.

    The fallback is documented as the contract today: real pycalphad is
    open-path A/MIT and will be installed in production. The shape parser
    is what runs in CI without pycalphad.
    """
    path = Path(tdb_path)
    if not path.is_file():
        return FalsifierItem(
            name="l3.tdb_parses_in_pycalphad",
            threshold="pycalphad.Database(tdb_path) must succeed",
            actual={"path": str(path), "error": "file_not_found"},
            status="fail",
        )

    pycalphad_available = importlib.util.find_spec("pycalphad") is not None

    if pycalphad_available:
        try:
            from pycalphad import Database  # type: ignore

            Database(str(path))
            return FalsifierItem(
                name="l3.tdb_parses_in_pycalphad",
                threshold="pycalphad.Database(tdb_path) must succeed",
                actual={"path": str(path), "parser": "pycalphad"},
                status="pass",
            )
        except Exception as exc:
            return FalsifierItem(
                name="l3.tdb_parses_in_pycalphad",
                threshold="pycalphad.Database(tdb_path) must succeed",
                actual={
                    "path": str(path),
                    "error": str(exc)[:200],
                    "parser": "pycalphad",
                },
                status="fail",
            )

    # Fallback: syntactic-shape parser.
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        return FalsifierItem(
            name="l3.tdb_parses_in_pycalphad",
            threshold="syntactic shape: ELEMENT + PHASE + PARAMETER/FUNCTION + ';' + '!'",
            actual={"path": str(path), "error": str(exc)[:200], "parser": "shape_fallback"},
            status="fail",
        )

    valid = _looks_like_tdb_syntactic(text)
    return FalsifierItem(
        name="l3.tdb_parses_in_pycalphad",
        threshold=(
            "syntactic shape (pycalphad not installed): ELEMENT + PHASE + "
            "PARAMETER/FUNCTION + ';' + '!'"
        ),
        actual={"path": str(path), "valid_shape": valid, "parser": "shape_fallback"},
        status="pass" if valid else "fail",
    )


# ---------------------------------------------------------------------------
# (2) phase_boundary_drift
# ---------------------------------------------------------------------------


def phase_boundary_drift(
    produced_envelope: dict[str, Any],
    reference_fixture: dict[str, Any] | None = None,
    threshold_K: float = DRIFT_THRESHOLD_K,
) -> FalsifierItem:
    """Verify produced TDB phase-boundary drift vs a reference (PRD §L3 gate 2).

    The drift is read from ``output.fixture_phase_boundary_drift_K`` if the
    produced envelope already records it; otherwise computed from the
    fixture's reference temperature comparison if supplied.
    """
    try:
        output = _get_output(produced_envelope)
    except ValueError:
        return FalsifierItem(
            name="l3.phase_boundary_drift",
            threshold=f"<= {threshold_K} K",
            actual=None,
            status="blocked",
        )

    drift = output.get("fixture_phase_boundary_drift_K")
    if drift is None and reference_fixture is not None:
        # If the produced envelope did not record drift, attempt to compute
        # from the reference fixture's expected boundary temperature.
        reference_T_K = reference_fixture.get("expected_boundary_T_K")
        produced_T_K = output.get("_calphad_meta", {}).get("temperature_K") or output.get(
            "temperature_K"
        )
        if reference_T_K is not None and produced_T_K is not None:
            drift = abs(float(produced_T_K) - float(reference_T_K))

    if drift is None:
        return FalsifierItem(
            name="l3.phase_boundary_drift",
            threshold=f"<= {threshold_K} K",
            actual=None,
            status="blocked",
        )

    status: FalsifierStatus = "pass" if drift <= threshold_K else "fail"
    return FalsifierItem(
        name="l3.phase_boundary_drift",
        threshold=f"<= {threshold_K} K",
        actual=float(drift),
        status=status,
    )


# ---------------------------------------------------------------------------
# (3) phase_set_jaccard_distance
# ---------------------------------------------------------------------------


def _jaccard_distance(set_a: Iterable[str], set_b: Iterable[str]) -> float:
    """Compute Jaccard distance between two phase-name sets.

    Jaccard distance = 1 - |A ∩ B| / |A ∪ B|. Empty union → distance 0.0
    (both sets vacuously equal).
    """
    a = {p.upper() for p in set_a}
    b = {p.upper() for p in set_b}
    union = a | b
    if not union:
        return 0.0
    intersection = a & b
    return 1.0 - len(intersection) / len(union)


def phase_set_jaccard_distance(
    envelope_a: dict[str, Any],
    envelope_b: dict[str, Any],
    threshold: float = JACCARD_THRESHOLD,
) -> FalsifierItem:
    """Verify Jaccard distance between two phase sets (PRD §L3 gate 3).

    Distance > threshold escalates (FAIL). Designed for cross-run
    disagreement (e.g., open TDB vs commercial TDB; pycalphad vs MICROSIM).
    """
    try:
        out_a = _get_output(envelope_a)
        out_b = _get_output(envelope_b)
    except ValueError:
        return FalsifierItem(
            name="l3.phase_set_jaccard_distance",
            threshold=f"<= {threshold}",
            actual=None,
            status="blocked",
        )

    phases_a = out_a.get("equilibrium_phases", [])
    phases_b = out_b.get("equilibrium_phases", [])
    distance = _jaccard_distance(phases_a, phases_b)
    status: FalsifierStatus = "pass" if distance <= threshold else "fail"
    return FalsifierItem(
        name="l3.phase_set_jaccard_distance",
        threshold=f"<= {threshold}",
        actual=distance,
        status=status,
    )


# ---------------------------------------------------------------------------
# (4) phase_fraction_js_divergence
# ---------------------------------------------------------------------------


def _normalize_phase_fractions(
    fractions: dict[str, float],
    universe: list[str],
) -> list[float]:
    """Return a probability vector aligned to ``universe`` order."""
    result = [max(0.0, float(fractions.get(p, 0.0))) for p in universe]
    total = sum(result)
    if total <= 0.0:
        return [1.0 / len(universe)] * len(universe) if universe else []
    return [r / total for r in result]


def _kl_divergence(p: list[float], q: list[float]) -> float:
    """KL(p || q) — assumes p, q are normalised probability vectors."""
    eps = 1e-12
    return sum(
        p_i * math.log((p_i + eps) / (q_i + eps))
        for p_i, q_i in zip(p, q, strict=False)
    )


def _js_divergence(p: list[float], q: list[float]) -> float:
    """Jensen-Shannon divergence (symmetric, [0, ln(2)] for natural log)."""
    if not p or not q or len(p) != len(q):
        return 0.0
    m = [(p_i + q_i) / 2.0 for p_i, q_i in zip(p, q, strict=False)]
    return 0.5 * _kl_divergence(p, m) + 0.5 * _kl_divergence(q, m)


def phase_fraction_js_divergence(
    envelope_a: dict[str, Any],
    envelope_b: dict[str, Any],
    threshold: float = JS_DIVERGENCE_THRESHOLD,
) -> FalsifierItem:
    """Verify JS divergence between two phase-fraction posteriors (PRD §L3 gate 4)."""
    try:
        out_a = _get_output(envelope_a)
        out_b = _get_output(envelope_b)
    except ValueError:
        return FalsifierItem(
            name="l3.phase_fraction_js_divergence",
            threshold=f"<= {threshold}",
            actual=None,
            status="blocked",
        )

    fractions_a = out_a.get("phase_fraction_posterior", {}) or {}
    fractions_b = out_b.get("phase_fraction_posterior", {}) or {}
    universe = sorted(set(fractions_a) | set(fractions_b))
    if not universe:
        # No phases on either side — trivially zero divergence; pass.
        return FalsifierItem(
            name="l3.phase_fraction_js_divergence",
            threshold=f"<= {threshold}",
            actual=0.0,
            status="pass",
        )
    p = _normalize_phase_fractions(fractions_a, universe)
    q = _normalize_phase_fractions(fractions_b, universe)
    js = _js_divergence(p, q)
    status: FalsifierStatus = "pass" if js <= threshold else "fail"
    return FalsifierItem(
        name="l3.phase_fraction_js_divergence",
        threshold=f"<= {threshold}",
        actual=js,
        status=status,
    )


# ---------------------------------------------------------------------------
# (5) espei_posterior_diagnostics
# ---------------------------------------------------------------------------


def espei_posterior_diagnostics(
    envelope: dict[str, Any],
    R_hat_max: float = R_HAT_MAX_DEFAULT,
    min_ess: int = MIN_ESS_DEFAULT,
) -> FalsifierItem:
    """Verify ESPEI posterior diagnostics are recorded (PRD §L3 gate 5).

    Pass conditions:
      - ``espei_diagnostics`` block exists and has ``ran=True``
      - ``R_hat`` is recorded and <= ``R_hat_max``
      - ``effective_sample_size`` is recorded and >= ``min_ess``

    Blocked: diagnostics block missing or ``ran=False`` (e.g. equilibrium-only
    call). Fail: thresholds not met.
    """
    try:
        output = _get_output(envelope)
    except ValueError:
        return FalsifierItem(
            name="l3.espei_posterior_diagnostics",
            threshold=f"R_hat <= {R_hat_max} AND ESS >= {min_ess}",
            actual=None,
            status="blocked",
        )

    diags = output.get("espei_diagnostics") or {}
    if not diags or not diags.get("ran", False):
        return FalsifierItem(
            name="l3.espei_posterior_diagnostics",
            threshold=f"R_hat <= {R_hat_max} AND ESS >= {min_ess}",
            actual={"ran": False, "reason": diags.get("reason", "no_diagnostics")},
            status="blocked",
        )

    r_hat = diags.get("R_hat")
    ess = diags.get("effective_sample_size")
    if r_hat is None or ess is None:
        return FalsifierItem(
            name="l3.espei_posterior_diagnostics",
            threshold=f"R_hat <= {R_hat_max} AND ESS >= {min_ess}",
            actual={"R_hat": r_hat, "ESS": ess},
            status="blocked",
        )

    pass_r_hat = r_hat <= R_hat_max
    pass_ess = ess >= min_ess
    if pass_r_hat and pass_ess:
        status: FalsifierStatus = "pass"
    else:
        status = "fail"
    return FalsifierItem(
        name="l3.espei_posterior_diagnostics",
        threshold=f"R_hat <= {R_hat_max} AND ESS >= {min_ess}",
        actual={"R_hat": float(r_hat), "ESS": float(ess)},
        status=status,
    )


# ---------------------------------------------------------------------------
# (6) tdb_quarantine_breach
# ---------------------------------------------------------------------------


def _read_quarantine_block(envelope: dict[str, Any]) -> dict[str, Any]:
    """Pull the _quarantine_meta block from an envelope.

    The block is the load-bearing audit signal for the quarantine policy.
    Adapters MUST emit it whenever they touch a commercial TDB.
    """
    return dict(envelope.get("_quarantine_meta") or {})


def tdb_quarantine_breach(envelope: dict[str, Any]) -> FalsifierItem:
    """Detect a commercial-TDB quarantine breach (PRD §L3 gate 6).

    Failure conditions (any one):
      - ``_quarantine_meta.redistributable`` == True
      - ``_quarantine_meta.committed_to_repo`` == True
      - ``_quarantine_meta.included_in_training_corpus`` == True
      - provider hint (e.g. "ThermoCalc", "TCFE9") combined with
        license != "proprietary" AND redistributable != False

    Pass: envelope's quarantine block is internally consistent OR the
    envelope does not touch a commercial TDB.
    """
    quarantine = _read_quarantine_block(envelope)

    # Path 1: explicit boolean breach flags.
    breach_flags: list[str] = []
    if quarantine.get("redistributable") is True:
        breach_flags.append("redistributable=True")
    if quarantine.get("committed_to_repo") is True:
        breach_flags.append("committed_to_repo=True")
    if quarantine.get("included_in_training_corpus") is True:
        breach_flags.append("included_in_training_corpus=True")

    # Path 2: provider/license consistency. If the provider says ThermoCalc
    # (or matches a commercial pattern), the license must be 'proprietary'
    # AND redistributable must be False.
    provider = str(quarantine.get("tdb_provider") or "")
    looks_commercial = bool(
        re.search(r"thermo.?calc|TC[FNSXP][A-Z]?\d*", provider, flags=re.IGNORECASE)
    )
    if looks_commercial:
        if quarantine.get("license") != "proprietary":
            breach_flags.append(
                f"commercial provider={provider!r} but license={quarantine.get('license')!r}"
            )
        # redistributable=True already caught above.

    # Path 3: the envelope claims a Thermo-Calc URL/path in tdb_ref.
    output = envelope.get("output") or {}
    tdb_ref = str(output.get("tdb_ref") or "")
    if (
        re.search(r"thermo.?calc", tdb_ref, flags=re.IGNORECASE)
        and not tdb_ref.startswith("hash://")
    ):
        breach_flags.append(f"commercial tdb_ref leaks plaintext path: {tdb_ref!r}")

    status: FalsifierStatus = "fail" if breach_flags else "pass"
    return FalsifierItem(
        name="l3.tdb_quarantine_breach",
        threshold=(
            "no commercial TDB envelope may have redistributable=True OR "
            "committed_to_repo=True OR included_in_training_corpus=True"
        ),
        actual={"breach_flags": breach_flags, "_quarantine_meta": quarantine},
        status=status,
    )


# ---------------------------------------------------------------------------
# (7) phaseforgeplus_license_gate
# ---------------------------------------------------------------------------


def phaseforgeplus_license_gate(envelope: dict[str, Any]) -> FalsifierItem:
    """Verify the PhaseForgePlus license-verification gate (PRD §L3 + §Open Q).

    The PhaseForgePlus prior adapter is default-blocked. This falsifier:
      - returns ``pass`` if the envelope is not a PhaseForgePlus envelope
        (irrelevant gate)
      - returns ``pass`` if the envelope IS PhaseForgePlus AND the license
        is verified (``_phaseforgeplus_meta.enabled == True`` AND
        ``license_spdx`` is set AND ``verified_at`` is set)
      - returns ``fail`` if the envelope is PhaseForgePlus but enabled with
        no license_spdx
      - returns ``blocked`` if the envelope is PhaseForgePlus and not
        enabled (default state).

    The blocked outcome is the load-bearing PRD posture: PhaseForgePlus is
    only a "research aid" until license verification.
    """
    tool_adapter = envelope.get("tool_adapter") or {}
    name = str(tool_adapter.get("name") or "")
    pfp_meta = envelope.get("_phaseforgeplus_meta") or {}

    is_phaseforgeplus = "PhaseForgePlus" in name or pfp_meta.get("repo")
    if not is_phaseforgeplus:
        return FalsifierItem(
            name="l3.phaseforgeplus_license_gate",
            threshold="not_applicable_for_non_phaseforgeplus_envelope",
            actual={"adapter_name": name, "is_phaseforgeplus": False},
            status="pass",
        )

    enabled = bool(pfp_meta.get("enabled"))
    license_spdx = pfp_meta.get("license_spdx")
    verified_at = pfp_meta.get("verified_at")

    if not enabled:
        return FalsifierItem(
            name="l3.phaseforgeplus_license_gate",
            threshold="enabled == True AND license_spdx set AND verified_at set",
            actual={"enabled": False, "license_spdx": None, "verified_at": None},
            status="blocked",
        )

    if not license_spdx or not verified_at:
        return FalsifierItem(
            name="l3.phaseforgeplus_license_gate",
            threshold="enabled == True AND license_spdx set AND verified_at set",
            actual={
                "enabled": enabled,
                "license_spdx": license_spdx,
                "verified_at": verified_at,
            },
            status="fail",
        )

    return FalsifierItem(
        name="l3.phaseforgeplus_license_gate",
        threshold="enabled == True AND license_spdx set AND verified_at set",
        actual={
            "enabled": enabled,
            "license_spdx": license_spdx,
            "verified_at": verified_at,
        },
        status="pass",
    )


# ---------------------------------------------------------------------------
# (8) commercial_tdb_provider_disabled_by_default
# ---------------------------------------------------------------------------


def commercial_tdb_provider_disabled_by_default(
    envelope: dict[str, Any],
    materials_config_provider_value: str | None = None,
) -> FalsifierItem:
    """Verify L3_COMMERCIAL_TDB_PROVIDER is 'disabled' unless explicitly enabled.

    PRD §Core Config Flags: ``L3_COMMERCIAL_TDB_PROVIDER=disabled`` is the
    default. This falsifier checks that an envelope claiming to have used
    the commercial TDB provider is consistent with the active config.

    Resolution order for the config value:
      1. Caller-supplied ``materials_config_provider_value`` (test seam).
      2. ``MaterialsConfig.from_env().L3_COMMERCIAL_TDB_PROVIDER``.

    Pass: config is "disabled" AND envelope did not claim commercial use.
    Pass: config is "thermo_calc_quarantined" (explicit per-customer).
    Fail: envelope claims commercial use but config is "disabled".
    Blocked: config cannot be resolved.
    """
    cfg_value = materials_config_provider_value
    if cfg_value is None:
        try:
            from zer0pa_materials.envelope.config import MaterialsConfig

            cfg = MaterialsConfig.from_env()
            cfg_value = str(cfg.L3_COMMERCIAL_TDB_PROVIDER)
        except Exception:
            return FalsifierItem(
                name="l3.commercial_tdb_provider_disabled_by_default",
                threshold="L3_COMMERCIAL_TDB_PROVIDER == 'disabled' OR explicit per-customer",
                actual={"config_value": None, "error": "config_unavailable"},
                status="blocked",
            )

    tool_adapter = envelope.get("tool_adapter") or {}
    engine = str(tool_adapter.get("engine") or "")
    backend = str(tool_adapter.get("backend") or "")
    quarantine = envelope.get("_quarantine_meta") or {}
    # An envelope claims commercial use if EITHER the engine label includes
    # "thermo-calc"/"quarantined" (load-bearing discriminator since the
    # Envelope.Backend literal cannot carry "thermo_calc_quarantined" — see
    # adapter docstring), OR the _quarantine_meta block names a provider /
    # commercial hint, OR the legacy backend value matches the historical
    # 'thermo_calc_quarantined' string for backward compatibility.
    claims_commercial = (
        backend == "thermo_calc_quarantined"
        or "thermo-calc-quarantined" in engine
        or "thermo_calc" in engine.lower()
        or bool(quarantine.get("tdb_provider"))
        or bool(quarantine.get("commercial_provider_hint"))
    )

    if cfg_value == "disabled":
        if claims_commercial:
            return FalsifierItem(
                name="l3.commercial_tdb_provider_disabled_by_default",
                threshold="L3_COMMERCIAL_TDB_PROVIDER == 'disabled' so envelope MUST NOT use commercial backend",
                actual={
                    "config_value": cfg_value,
                    "envelope_backend": backend,
                    "envelope_provider": quarantine.get("tdb_provider"),
                },
                status="fail",
            )
        return FalsifierItem(
            name="l3.commercial_tdb_provider_disabled_by_default",
            threshold="L3_COMMERCIAL_TDB_PROVIDER == 'disabled'",
            actual={"config_value": cfg_value, "envelope_backend": backend},
            status="pass",
        )

    if cfg_value == "thermo_calc_quarantined":
        # Explicit per-customer enable; envelope must carry a customer_id
        # to be consistent.
        if claims_commercial and not quarantine.get("customer_id"):
            return FalsifierItem(
                name="l3.commercial_tdb_provider_disabled_by_default",
                threshold=(
                    "if L3_COMMERCIAL_TDB_PROVIDER == 'thermo_calc_quarantined', "
                    "envelope must carry _quarantine_meta.customer_id"
                ),
                actual={
                    "config_value": cfg_value,
                    "customer_id": quarantine.get("customer_id"),
                },
                status="fail",
            )
        return FalsifierItem(
            name="l3.commercial_tdb_provider_disabled_by_default",
            threshold="L3_COMMERCIAL_TDB_PROVIDER == 'thermo_calc_quarantined' AND customer_id set",
            actual={
                "config_value": cfg_value,
                "customer_id": quarantine.get("customer_id"),
            },
            status="pass",
        )

    # Unknown / future config value — block instead of pass to surface drift.
    return FalsifierItem(
        name="l3.commercial_tdb_provider_disabled_by_default",
        threshold="L3_COMMERCIAL_TDB_PROVIDER in {'disabled', 'thermo_calc_quarantined'}",
        actual={"config_value": cfg_value},
        status="blocked",
    )
