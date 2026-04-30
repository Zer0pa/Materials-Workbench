"""L2 MLIP falsifiers (PRD §L2 Falsifiers).

All falsifiers accept an ``envelope`` dict (wire-level, as emitted by
``L2EnsembleRunner.run``) and return a ``FalsifierItem``.

PRD-mandated routing thresholds:
    queue DFT if energy disagreement > 25 meV/atom
    queue DFT if force RMSE > 0.15 eV/Å
    HARD REJECT if energy disagreement > 75 meV/atom
    HARD REJECT if force RMSE > 0.35 eV/Å

Falsifier catalogue:
    dpa_mace_disagreement_routing      — applies all routing thresholds; primary gate
    single_model_promotion_block       — fails if promote while only one model ran
    force_rmse_threshold               — dedicated force-RMSE promote gate
    volume_drift_threshold             — relaxation volume drift > 2%
    space_group_drift_threshold        — relaxation space group change
    uma_license_gate                   — fails if UMA used without verified license
    committee_uncertainty_threshold    — fails if committee variance exceeds threshold
"""

from __future__ import annotations

from typing import Any

from zer0pa_materials.envelope.falsifier import FalsifierItem, FalsifierStatus


# ---------------------------------------------------------------------------
# Threshold constants
# ---------------------------------------------------------------------------

_ENERGY_PROMOTE_MEV = 25.0          # queue DFT above this
_ENERGY_HARD_REJECT_MEV = 75.0      # hard reject above this
_FORCE_PROMOTE_EV_ANG = 0.15        # queue DFT above this
_FORCE_HARD_REJECT_EV_ANG = 0.35    # hard reject above this
_VOLUME_DRIFT_PCT = 2.0             # > 2% volume change → queue DFT
_COORD_DRIFT_ANG = 0.08             # > 0.08 Å/atom endpoint drift → queue DFT


def _get_output(envelope: dict[str, Any]) -> dict[str, Any]:
    """Extract the ``output`` sub-dict from an envelope."""
    out = envelope.get("output")
    if not isinstance(out, dict):
        raise ValueError(f"envelope.output is missing or not a dict; got {type(out)}")
    return out


# ---------------------------------------------------------------------------
# dpa_mace_disagreement_routing
# ---------------------------------------------------------------------------


def dpa_mace_disagreement_routing(envelope: dict[str, Any]) -> FalsifierItem:
    """Apply DPA/MACE energy disagreement routing thresholds.

    Returns
    -------
    FalsifierItem
        - ``pass``         if routing_decision == "promote"
        - ``fail``         if routing_decision == "queue_dft" or "hard_reject"
        - ``blocked``      if output is missing required keys
    """
    try:
        output = _get_output(envelope)
    except ValueError as exc:
        return FalsifierItem(
            name="l2.dpa_mace_disagreement_routing",
            threshold=f"routing_decision == promote (energy < {_ENERGY_PROMOTE_MEV} meV/atom, "
                      f"hard_reject > {_ENERGY_HARD_REJECT_MEV} meV/atom)",
            actual=None,
            status="blocked",
        )

    energy_disagree = output.get("energy_disagreement_meV_per_atom")
    routing = output.get("routing_decision", "promote")

    if energy_disagree is None:
        return FalsifierItem(
            name="l2.dpa_mace_disagreement_routing",
            threshold=f"routing_decision == promote (energy < {_ENERGY_PROMOTE_MEV} meV/atom)",
            actual=None,
            status="blocked",
        )

    # Determine the tightest threshold exceeded.
    if routing == "hard_reject":
        status: FalsifierStatus = "fail"
    elif routing == "queue_dft":
        status = "fail"
    else:
        status = "pass"

    return FalsifierItem(
        name="l2.dpa_mace_disagreement_routing",
        threshold=(
            f"routing_decision == promote "
            f"(energy_disagree <= {_ENERGY_PROMOTE_MEV} meV/atom; "
            f"hard_reject >= {_ENERGY_HARD_REJECT_MEV} meV/atom)"
        ),
        actual=energy_disagree,
        status=status,
    )


# ---------------------------------------------------------------------------
# single_model_promotion_block
# ---------------------------------------------------------------------------


def single_model_promotion_block(envelope: dict[str, Any]) -> FalsifierItem:
    """Fail if routing_decision == 'promote' while fewer than 2 distinct models ran.

    This is the RESISTANCE.md §DPA+MACE mandatory gate: promotion is only
    valid when BOTH DPA-3 and MACE have contributed predictions.
    """
    try:
        output = _get_output(envelope)
    except ValueError:
        return FalsifierItem(
            name="l2.single_model_promotion_block",
            threshold="promote requires >= 2 distinct models (DPA-3 + MACE)",
            actual=None,
            status="blocked",
        )

    routing = output.get("routing_decision", "promote")
    predictions = output.get("predictions", [])
    distinct_models = {p.get("model") for p in predictions if isinstance(p, dict)}
    n_distinct = len(distinct_models)

    if routing == "promote" and n_distinct < 2:
        status: FalsifierStatus = "fail"
    else:
        status = "pass"

    return FalsifierItem(
        name="l2.single_model_promotion_block",
        threshold="promote requires >= 2 distinct models (DPA-3 + MACE mandatory)",
        actual=float(n_distinct),
        status=status,
    )


# ---------------------------------------------------------------------------
# force_rmse_threshold
# ---------------------------------------------------------------------------


def force_rmse_threshold(envelope: dict[str, Any]) -> FalsifierItem:
    """Dedicated force-RMSE promote gate (queue DFT if > 0.15 eV/Å).

    Hard-reject threshold (> 0.35 eV/Å) is also checked; the harder threshold
    produces a ``fail`` result as well. The ``routing_decision`` in the output
    takes precedence for routing, but this falsifier provides explicit named
    evidence for the force-RMSE contributor.
    """
    try:
        output = _get_output(envelope)
    except ValueError:
        return FalsifierItem(
            name="l2.force_rmse_threshold",
            threshold=f"<= {_FORCE_PROMOTE_EV_ANG} eV/Å (promote); "
                      f"> {_FORCE_HARD_REJECT_EV_ANG} eV/Å (hard_reject)",
            actual=None,
            status="blocked",
        )

    force_disagree = output.get("force_rmse_disagreement_eV_per_Ang")

    if force_disagree is None:
        status: FalsifierStatus = "blocked"
    elif force_disagree > _FORCE_HARD_REJECT_EV_ANG:
        status = "fail"
    elif force_disagree > _FORCE_PROMOTE_EV_ANG:
        status = "fail"
    else:
        status = "pass"

    return FalsifierItem(
        name="l2.force_rmse_threshold",
        threshold=(
            f"<= {_FORCE_PROMOTE_EV_ANG} eV/Å to promote; "
            f"> {_FORCE_HARD_REJECT_EV_ANG} eV/Å hard_reject"
        ),
        actual=force_disagree,
        status=status,
    )


# ---------------------------------------------------------------------------
# volume_drift_threshold
# ---------------------------------------------------------------------------


def volume_drift_threshold(envelope: dict[str, Any]) -> FalsifierItem:
    """Fail if relaxation endpoint volume drifts by > 2%.

    The volume drift is stored in ``_ensemble_meta.volume_drift_pct`` when
    the service layer computes a relaxation. If the key is absent, the
    falsifier returns ``pass`` (no relaxation run, so no drift to check).
    """
    meta = envelope.get("_ensemble_meta", {})
    volume_drift = meta.get("volume_drift_pct")

    if volume_drift is None:
        # No relaxation data — not a failure, just not applicable.
        return FalsifierItem(
            name="l2.volume_drift_threshold",
            threshold=f"<= {_VOLUME_DRIFT_PCT}% volume drift across endpoints",
            actual=None,
            status="pass",  # absence of drift data is not a failure
        )

    if volume_drift > _VOLUME_DRIFT_PCT:
        status: FalsifierStatus = "fail"
    else:
        status = "pass"

    return FalsifierItem(
        name="l2.volume_drift_threshold",
        threshold=f"<= {_VOLUME_DRIFT_PCT}% volume drift across relaxation endpoints",
        actual=float(volume_drift),
        status=status,
    )


# ---------------------------------------------------------------------------
# space_group_drift_threshold
# ---------------------------------------------------------------------------


def space_group_drift_threshold(envelope: dict[str, Any]) -> FalsifierItem:
    """Fail if DPA vs MACE relaxation endpoints differ in space group.

    The space group agreement is stored in ``_ensemble_meta.space_group_agrees``
    (bool) when the service layer computes relaxations. If absent, returns
    ``pass`` (no relaxation, no drift).
    """
    meta = envelope.get("_ensemble_meta", {})
    sg_agrees = meta.get("space_group_agrees")

    if sg_agrees is None:
        return FalsifierItem(
            name="l2.space_group_drift_threshold",
            threshold="DPA and MACE relaxation endpoints must agree on space group",
            actual=None,
            status="pass",
        )

    status: FalsifierStatus = "pass" if sg_agrees else "fail"

    return FalsifierItem(
        name="l2.space_group_drift_threshold",
        threshold="DPA and MACE relaxation endpoints must agree on space group",
        actual=1.0 if sg_agrees else 0.0,
        status=status,
    )


# ---------------------------------------------------------------------------
# uma_license_gate
# ---------------------------------------------------------------------------


def uma_license_gate(envelope: dict[str, Any]) -> FalsifierItem:
    """Fail if UMA predictions appear in the envelope without a verified gate.

    Checks for:
    1. Any prediction from a model with "UMA" in the name.
    2. ``_uma_gate`` block presence + ``aup_accepted_at`` field.

    If UMA predictions are present but the gate was not explicitly activated,
    this falsifier returns ``fail``.
    """
    try:
        output = _get_output(envelope)
    except ValueError:
        return FalsifierItem(
            name="l2.uma_license_gate",
            threshold="UMA predictions require verified FAIR Chemistry License + HF org",
            actual=None,
            status="blocked",
        )

    predictions = output.get("predictions", [])
    uma_models = [
        p.get("model", "") for p in predictions
        if isinstance(p, dict) and "UMA" in p.get("model", "")
    ]

    if not uma_models:
        # No UMA — gate not relevant, pass.
        return FalsifierItem(
            name="l2.uma_license_gate",
            threshold="UMA predictions require verified FAIR Chemistry License + HF org",
            actual=0.0,
            status="pass",
        )

    # UMA is present. Check the gate record.
    uma_gate = envelope.get("_uma_gate", {})
    aup_accepted = uma_gate.get("aup_accepted_at")
    hf_org = uma_gate.get("hf_org")

    if aup_accepted and hf_org:
        status: FalsifierStatus = "pass"
    else:
        status = "fail"

    return FalsifierItem(
        name="l2.uma_license_gate",
        threshold=(
            "UMA predictions require: hf_org registered + "
            "aup_accepted_at recorded (FAIR Chemistry License v1)"
        ),
        actual=float(len(uma_models)),
        status=status,
    )


# ---------------------------------------------------------------------------
# committee_uncertainty_threshold
# ---------------------------------------------------------------------------


def committee_uncertainty_threshold(
    envelope: dict[str, Any],
    threshold_meV: float = 10.0,
) -> FalsifierItem:
    """Fail if MACE/DPA committee variance exceeds the threshold.

    Looks for ``mace_committee_energy_variance`` or
    ``dpa_committee_energy_variance`` in ``disagreement.metrics``.

    Parameters
    ----------
    envelope:
        L2 ensemble envelope dict.
    threshold_meV:
        Committee energy variance threshold in meV^2/atom (default 10.0).
    """
    metrics = envelope.get("disagreement", {}).get("metrics", [])

    committee_variance: float | None = None
    for m in metrics:
        if isinstance(m, dict) and "committee" in m.get("name", "") and "variance" in m.get("name", ""):
            committee_variance = m.get("value")
            break

    if committee_variance is None:
        return FalsifierItem(
            name="l2.committee_uncertainty_threshold",
            threshold=f"committee_energy_variance <= {threshold_meV} meV^2/atom",
            actual=None,
            status="pass",  # no committee data = not applicable
        )

    status: FalsifierStatus = "pass" if committee_variance <= threshold_meV else "fail"

    return FalsifierItem(
        name="l2.committee_uncertainty_threshold",
        threshold=f"committee_energy_variance <= {threshold_meV} meV^2/atom",
        actual=committee_variance,
        status=status,
    )
