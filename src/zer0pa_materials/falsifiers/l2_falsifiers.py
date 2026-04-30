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
    dpa_mace_disagreement_routing_recomputed
                                       — Wave D hardened: recomputes
                                         disagreement from per-model
                                         predictions before routing
    single_model_promotion_block       — fails if promote while only one model ran
    force_rmse_threshold               — dedicated force-RMSE promote gate
    volume_drift_threshold             — relaxation volume drift > 2%
    space_group_drift_threshold        — relaxation space group change
    uma_license_gate                   — fails if UMA used without verified license
    committee_uncertainty_threshold    — fails if committee variance exceeds threshold

Wave D discipline (RESISTANCE.md ``fp-shapematch``):
    ``dpa_mace_disagreement_routing`` (the original) trusts
    ``output.energy_disagreement_meV_per_atom`` and
    ``output.routing_decision``. A buggy or malicious adapter can write
    a small disagreement value with a "promote" label while the actual
    DPA / MACE energies in ``output.predictions`` would route to
    ``hard_reject``. The recomputed variant catches that.
"""

from __future__ import annotations

from typing import Any

from zer0pa_materials.envelope.falsifier import FalsifierItem, FalsifierStatus
from zer0pa_materials.falsifiers.raw_evidence import (
    DEFAULT_DISAGREEMENT_TOLERANCE_MEV,
    DEFAULT_FORCE_TOLERANCE_EV_PER_A,
    recompute_l2_disagreement,
)


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
# dpa_mace_disagreement_routing_recomputed   (Wave D hardened gate 1)
# ---------------------------------------------------------------------------


def dpa_mace_disagreement_routing_recomputed(
    envelope: dict[str, Any],
    energy_tolerance_meV: float = DEFAULT_DISAGREEMENT_TOLERANCE_MEV,
    force_tolerance_eV_per_A: float = DEFAULT_FORCE_TOLERANCE_EV_PER_A,
) -> FalsifierItem:
    """Recompute DPA/MACE disagreement from raw predictions then apply thresholds.

    Wave D hardened version of ``dpa_mace_disagreement_routing``. The
    original gate read ``output.energy_disagreement_meV_per_atom`` and
    ``output.routing_decision`` directly; this gate IGNORES those claim
    fields when adjudicating and instead:

      1. Pulls the per-model predictions from ``output.predictions``
         (also accepting ``output.per_model_predictions`` as alias).
      2. Recomputes ``energy_meV = abs(E_DPA - E_MACE) * 1000`` and
         ``force = abs(F_DPA - F_MACE)``. This uses the same formula as
         :class:`L2EnsembleRunner.run` so a clean adapter is never
         flagged.
      3. Applies the PRD routing thresholds against the RECOMPUTED
         scalar (queue at 25, hard-reject at 75 for energy; queue at
         0.15, hard-reject at 0.35 for force).
      4. Compares the recomputed scalar against the envelope's claimed
         scalar; if they differ by more than the tolerance, returns
         ``status="fail"`` with reason
         ``claimed_disagreement_inconsistent_with_per_model_predictions``.

    Status semantics:

    * ``pass`` — recomputed values < the queue thresholds AND match the
      envelope's claim within tolerance.
    * ``fail`` — either the recomputed value exceeds a threshold, OR
      the claim does not match the recompute within tolerance.
    * ``blocked`` — the per-model predictions are missing or do not
      include both DPA and MACE; cannot recompute.
    """
    energy_recomputed, force_recomputed = recompute_l2_disagreement(envelope)
    if energy_recomputed is None and force_recomputed is None:
        return FalsifierItem(
            name="l2.dpa_mace_disagreement_routing_recomputed",
            threshold=(
                f"recomputed energy <= {_ENERGY_PROMOTE_MEV} meV/atom AND "
                f"recomputed force <= {_FORCE_PROMOTE_EV_ANG} eV/Å AND "
                "claim within tolerance"
            ),
            actual={
                "reason": "missing_per_model_predictions",
                "energy_recomputed_meV": None,
                "force_recomputed_eV_per_A": None,
            },
            status="blocked",
            rationale=(
                "envelope does not include both DPA and MACE per-model "
                "predictions; cannot recompute disagreement from raw evidence"
            ),
        )

    output = envelope.get("output") or {}
    if not isinstance(output, dict):
        output = {}
    energy_claim = output.get("energy_disagreement_meV_per_atom")
    force_claim = output.get("force_rmse_disagreement_eV_per_Ang")
    routing_claim = output.get("routing_decision")

    # Compare claim to recompute.
    energy_mismatch = (
        energy_recomputed is not None
        and energy_claim is not None
        and abs(float(energy_claim) - float(energy_recomputed)) > energy_tolerance_meV
    )
    force_mismatch = (
        force_recomputed is not None
        and force_claim is not None
        and abs(float(force_claim) - float(force_recomputed)) > force_tolerance_eV_per_A
    )
    claim_mismatch = energy_mismatch or force_mismatch

    # What the routing decision SHOULD be from the recomputed scalar.
    routing_recomputed: str
    if (
        energy_recomputed is not None
        and energy_recomputed > _ENERGY_HARD_REJECT_MEV
    ) or (
        force_recomputed is not None
        and force_recomputed > _FORCE_HARD_REJECT_EV_ANG
    ):
        routing_recomputed = "hard_reject"
    elif (
        energy_recomputed is not None
        and energy_recomputed > _ENERGY_PROMOTE_MEV
    ) or (
        force_recomputed is not None
        and force_recomputed > _FORCE_PROMOTE_EV_ANG
    ):
        routing_recomputed = "queue_dft"
    else:
        routing_recomputed = "promote"

    if routing_recomputed != "promote" or claim_mismatch:
        rationale_parts: list[str] = []
        if claim_mismatch:
            rationale_parts.append(
                "claimed_disagreement_inconsistent_with_per_model_predictions"
            )
        if routing_recomputed != "promote":
            rationale_parts.append(
                f"recomputed routing={routing_recomputed!r} (claim was {routing_claim!r})"
            )
        return FalsifierItem(
            name="l2.dpa_mace_disagreement_routing_recomputed",
            threshold=(
                f"recomputed energy <= {_ENERGY_PROMOTE_MEV} meV/atom AND "
                f"recomputed force <= {_FORCE_PROMOTE_EV_ANG} eV/Å AND "
                f"|claim - recompute| <= ({energy_tolerance_meV} meV, "
                f"{force_tolerance_eV_per_A} eV/Å)"
            ),
            actual={
                "energy_recomputed_meV": energy_recomputed,
                "energy_claimed_meV": energy_claim,
                "force_recomputed_eV_per_A": force_recomputed,
                "force_claimed_eV_per_A": force_claim,
                "routing_claim": routing_claim,
                "routing_recomputed": routing_recomputed,
                "claim_recompute_mismatch": claim_mismatch,
            },
            status="fail",
            rationale="; ".join(rationale_parts) or "recomputed_routing_not_promote",
        )

    return FalsifierItem(
        name="l2.dpa_mace_disagreement_routing_recomputed",
        threshold=(
            f"recomputed energy <= {_ENERGY_PROMOTE_MEV} meV/atom AND "
            f"recomputed force <= {_FORCE_PROMOTE_EV_ANG} eV/Å AND "
            f"|claim - recompute| <= ({energy_tolerance_meV} meV, "
            f"{force_tolerance_eV_per_A} eV/Å)"
        ),
        actual={
            "energy_recomputed_meV": energy_recomputed,
            "energy_claimed_meV": energy_claim,
            "force_recomputed_eV_per_A": force_recomputed,
            "force_claimed_eV_per_A": force_claim,
            "routing_recomputed": routing_recomputed,
        },
        status="pass",
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
