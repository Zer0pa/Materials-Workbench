"""Ionic falsifiers — the most consequential battery-MVP gates.

PRD §Ionic Transport: "Battery MVP claims require an explicit
IonicTransportService; phonons do not substitute for Li-ion conductivity."

This module owns the gate that prevents L1.5 (phonon) outputs from
being interpreted as ionic conductivity claims and the gate that
requires every battery candidate to have all six PRD-required pieces
of evidence before promotion.

Every falsifier is a pure function of an envelope (or a list of
envelopes, for the chain falsifiers). They return
:class:`FalsifierItem` rows so the audit ledger sees a uniform shape.

Coverage map
------------

PRD §Ionic Transport gates                     -> Function
-----------------------------------------------------------
"phonons do not substitute for Li-ion          -> requires_ionic_transport_service
conductivity" — claims of ionic_conductivity
require IonicTransportService reference

room-temperature conductivity CI includes      -> room_temperature_conductivity_credible_interval_meets_threshold
or exceeds 1e-3 S/cm

activation barrier target <= 0.35 eV;          -> activation_energy_target_threshold
stretch <= 0.30 eV (separate flag)

oxidative stability >= 4.0 V vs Li/Li+         -> oxidative_stability_threshold

Li-metal reduction instability allowed only    -> li_metal_reduction_route_compatibility
if mode == coating_interlayer

Arrhenius fit quality R² >= 0.95               -> arrhenius_fit_quality

MLIP/AIMD diffusion disagreement > 0.5 dex     -> mlip_aimd_diffusion_disagreement

defect/disorder assumptions documented         -> defect_disorder_assumptions_documented

full battery evidence chain has 6 pieces       -> full_battery_evidence_chain_complete
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

from zer0pa_materials_workbench.adapters.ionic.base import IONIC_TRANSPORT_SERVICE_REF
from zer0pa_materials_workbench.envelope import Envelope, FalsifierItem
from zer0pa_materials_workbench.falsifiers.raw_evidence import (
    find_ionic_back_edge_target,
    implied_arrhenius_barrier_eV,
)

__all__ = [
    "ARRHENIUS_BARRIER_BAND_AT_1E_3_EV",
    "MAX_PLAUSIBLE_BARRIER_EV",
    "MIN_PLAUSIBLE_BARRIER_EV",
    "REQUIRED_EVIDENCE_KEYS",
    "activation_energy_target_threshold",
    "arrhenius_fit_quality",
    "defect_disorder_assumptions_documented",
    "full_battery_evidence_chain_complete",
    "li_metal_reduction_route_compatibility",
    "mlip_aimd_diffusion_disagreement",
    "neb_barrier_range_check",
    "oxidative_stability_threshold",
    "requires_ionic_transport_service",
    "room_temperature_conductivity_credible_interval_meets_threshold",
    "verify_ionic_service_back_edge",
]


# The six PRD-required pieces of evidence, keyed by the envelope output
# field that records them. Ordered so the chain falsifier can report
# missing pieces in a stable order.
REQUIRED_EVIDENCE_KEYS: tuple[str, ...] = (
    "migration_barrier_eV",
    "diffusion_coefficient_cm2_per_s",
    "arrhenius",
    "electrochemical_window_V_vs_LiLi",
    "interface_stability",
    "defect_disorder_assumptions",
)


# Wave D NEB barrier plausibility band (gate 5).
#
# Lower bound 0.05 eV: below this, the activation energy is in the
# k_B T regime at room temperature; superionic conductors with
# essentially-zero barriers are not physical at 300 K and almost always
# indicate a bug in the NEB integrator or the climbing-image setup
# (see e.g. Mo, Ong, Ceder 2012 Chem. Mater.).
#
# Upper bound 3.0 eV: above this, no candidate could plausibly conduct
# Li ions at any practical temperature. A claim of 5 eV migration
# barrier on a battery candidate is essentially garbage.
MIN_PLAUSIBLE_BARRIER_EV: float = 0.05
MAX_PLAUSIBLE_BARRIER_EV: float = 3.0


# For battery candidates with claimed sigma >= 1e-3 S/cm (the canonical
# PRD MVP threshold), the implied Arrhenius barrier at 300 K with a
# typical superionic prefactor (sigma_0 ~ 1e3 S/cm) falls in
# [0.20, 0.45] eV. A claimed migration_barrier outside this band while
# the conductivity claim is at or above 1e-3 S/cm is internally
# inconsistent.
ARRHENIUS_BARRIER_BAND_AT_1E_3_EV: tuple[float, float] = (0.20, 0.45)


# ----------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------


def _as_dict(envelope: Envelope | Mapping[str, Any]) -> dict[str, Any]:
    """Return a plain dict view of an envelope or already-dict input."""
    if isinstance(envelope, Envelope):
        return envelope.model_dump(mode="json")
    if isinstance(envelope, Mapping):
        return dict(envelope)
    raise TypeError(f"expected Envelope or Mapping, got {type(envelope).__name__}")


def _envelope_input_refs(envelope: Envelope | Mapping[str, Any]) -> list[str]:
    if isinstance(envelope, Envelope):
        return list(envelope.input_refs)
    if isinstance(envelope, Mapping):
        refs = envelope.get("input_refs", [])
        return list(refs) if isinstance(refs, (list, tuple)) else []
    return []


def _envelope_output(envelope: Envelope | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(envelope, Envelope):
        return dict(envelope.output)
    if isinstance(envelope, Mapping):
        out = envelope.get("output", {})
        return dict(out) if isinstance(out, Mapping) else {}
    return {}


# ----------------------------------------------------------------------------
# 1. requires_ionic_transport_service
#    PRD: "phonons do not substitute for Li-ion conductivity."
# ----------------------------------------------------------------------------


def requires_ionic_transport_service(
    envelope: Envelope | Mapping[str, Any],
    service_ref: str = IONIC_TRANSPORT_SERVICE_REF,
) -> FalsifierItem:
    """FAIL if the envelope claims ionic conductivity without an IonicTransportService ref.

    The claim signal is any of:

    * the canonical envelope.output["nernst_einstein_conductivity_S_per_cm"]
      being non-null
    * a top-level dict key ``ionic_conductivity_S_per_cm`` (handles the
      negative fixture's flat-shape candidate JSON)

    The service reference signal is any of:

    * ``service_ref`` appearing in ``envelope.input_refs``
    * the layer being ``ionic`` and the tool_adapter.name being a
      registered ionic adapter (i.e. the envelope WAS produced inside
      the service)
    * a top-level dict key ``ionic_transport_service_ref`` set to a
      non-null value (handles the negative fixture)

    Returns:
        FalsifierItem with name="ionic.requires_ionic_transport_service".
        ``status="pass"`` if the claim has the service reference;
        ``status="fail"`` if a claim exists without a service ref;
        ``status="pass"`` if no claim exists (vacuous truth — no
        L1.5/L2 envelope should be marked fail just because it doesn't
        carry an ionic conductivity field).
    """
    body = _as_dict(envelope)
    output = _envelope_output(envelope)
    flat_claim = body.get("ionic_conductivity_S_per_cm")

    has_claim = bool(
        (flat_claim is not None and flat_claim != 0)
        or output.get("nernst_einstein_conductivity_S_per_cm") not in (None, 0)
    )
    if not has_claim:
        return FalsifierItem(
            name="ionic.requires_ionic_transport_service",
            threshold=(
                "claim of ionic_conductivity_S_per_cm requires IonicTransportService "
                "reference (PRD §Ionic Transport: phonons do not substitute for Li-ion "
                "conductivity)"
            ),
            actual="no_ionic_conductivity_claim",
            status="pass",
            rationale="No ionic conductivity claim present; gate not triggered.",
        )

    # Look for the service reference.
    refs = _envelope_input_refs(envelope)
    flat_ref = body.get("ionic_transport_service_ref")
    has_ref = bool(
        service_ref in refs
        or (flat_ref is not None and flat_ref != "")
    )
    layer = body.get("layer")
    if has_ref or layer == "ionic":
        return FalsifierItem(
            name="ionic.requires_ionic_transport_service",
            threshold=(
                "claim of ionic_conductivity_S_per_cm requires IonicTransportService "
                "reference (PRD §Ionic Transport: phonons do not substitute for Li-ion "
                "conductivity)"
            ),
            actual={"service_ref_found": True, "input_refs": refs, "flat_ref": flat_ref},
            status="pass",
        )

    return FalsifierItem(
        name="ionic.requires_ionic_transport_service",
        threshold=(
            "claim of ionic_conductivity_S_per_cm requires IonicTransportService "
            "reference (PRD §Ionic Transport: phonons do not substitute for Li-ion "
            "conductivity)"
        ),
        actual={
            "claim_value": flat_claim
            if flat_claim is not None
            else output.get("nernst_einstein_conductivity_S_per_cm"),
            "service_ref_found": False,
            "input_refs": refs,
            "flat_ref": flat_ref,
        },
        status="fail",
        rationale=(
            "Envelope claims ionic conductivity without an IonicTransportService "
            "reference. The PRD requires battery MVP claims to come from the "
            "IonicTransportService — L1.5 phonon outputs DO NOT substitute."
        ),
    )


# ----------------------------------------------------------------------------
# 2. room_temperature_conductivity_credible_interval_meets_threshold
# ----------------------------------------------------------------------------


def room_temperature_conductivity_credible_interval_meets_threshold(
    envelope: Envelope | Mapping[str, Any],
    threshold_S_per_cm: float = 1e-3,
) -> FalsifierItem:
    """PASS if the conductivity credible interval includes or exceeds the threshold.

    The CI is read from the envelope's falsifier items
    (``ionic.rt_conductivity_credible_interval``). If absent, falls
    back to a 0-width interval at the mean.
    """
    output = _envelope_output(envelope)
    sigma = output.get("nernst_einstein_conductivity_S_per_cm")

    # Try to find the rt_conductivity_credible_interval falsifier.
    body = _as_dict(envelope)
    falsifier_items = body.get("falsifier", {}).get("items", [])
    ci_lo, ci_hi = sigma, sigma
    uncertainty_dex = 0.0
    for item in falsifier_items:
        if item.get("name") == "ionic.rt_conductivity_credible_interval":
            actual = item.get("actual", {})
            if isinstance(actual, Mapping):
                ci_lo = actual.get("lo_S_per_cm", sigma)
                ci_hi = actual.get("hi_S_per_cm", sigma)
                uncertainty_dex = actual.get("uncertainty_dex", 0.0)
            break

    if sigma is None:
        return FalsifierItem(
            name="ionic.rt_conductivity_ci_meets_threshold",
            threshold=f"CI includes or exceeds {threshold_S_per_cm:.0e} S/cm",
            actual={"mean_S_per_cm": None},
            status="blocked",
            rationale="No conductivity recorded; cannot evaluate gate.",
        )
    if ci_hi is None:
        ci_hi = sigma
    if ci_lo is None:
        ci_lo = sigma

    status = "pass" if ci_hi >= threshold_S_per_cm else "fail"
    return FalsifierItem(
        name="ionic.rt_conductivity_ci_meets_threshold",
        threshold=f"CI includes or exceeds {threshold_S_per_cm:.0e} S/cm",
        actual={
            "mean_S_per_cm": sigma,
            "lo_S_per_cm": ci_lo,
            "hi_S_per_cm": ci_hi,
            "uncertainty_dex": uncertainty_dex,
        },
        status=status,
    )


# ----------------------------------------------------------------------------
# 3. activation_energy_target_threshold
# ----------------------------------------------------------------------------


def activation_energy_target_threshold(
    envelope: Envelope | Mapping[str, Any],
    target: float = 0.35,
    stretch: float = 0.30,
) -> tuple[FalsifierItem, FalsifierItem]:
    """Return (target gate, stretch gate) FalsifierItems for activation barrier.

    The target gate is required for promotion; the stretch gate is a
    SEPARATE flag that does not block promotion but is recorded for
    the MVP packet.
    """
    output = _envelope_output(envelope)
    arrhenius = output.get("arrhenius") or {}
    E_a = (
        arrhenius.get("activation_energy_eV")
        if isinstance(arrhenius, Mapping)
        else None
    )
    if E_a is None:
        E_a = output.get("migration_barrier_eV")

    target_status = (
        "blocked" if E_a is None else ("pass" if E_a <= target else "fail")
    )
    stretch_status = (
        "blocked" if E_a is None else ("pass" if E_a <= stretch else "fail")
    )
    target_item = FalsifierItem(
        name="ionic.activation_energy_target",
        threshold=f"<= {target} eV",
        actual=E_a,
        status=target_status,
    )
    stretch_item = FalsifierItem(
        name="ionic.activation_energy_stretch",
        threshold=f"<= {stretch} eV",
        actual=E_a,
        status=stretch_status,
        rationale="Stretch flag; documents stricter target for MVP promotion.",
    )
    return target_item, stretch_item


# ----------------------------------------------------------------------------
# 4. oxidative_stability_threshold
# ----------------------------------------------------------------------------


def oxidative_stability_threshold(
    envelope: Envelope | Mapping[str, Any],
    threshold_V: float = 4.0,
) -> FalsifierItem:
    """PASS if the oxidative stability is at or above the threshold V vs Li/Li+."""
    output = _envelope_output(envelope)
    window = output.get("electrochemical_window_V_vs_LiLi")
    ox: float | None = None
    if isinstance(window, (list, tuple)) and len(window) >= 2:
        ox = window[1]
    if ox is None:
        return FalsifierItem(
            name="ionic.oxidative_stability_threshold",
            threshold=f">= {threshold_V} V vs Li/Li+",
            actual=None,
            status="blocked",
            rationale="No electrochemical window recorded.",
        )
    return FalsifierItem(
        name="ionic.oxidative_stability_threshold",
        threshold=f">= {threshold_V} V vs Li/Li+",
        actual=ox,
        status="pass" if ox >= threshold_V else "fail",
    )


# ----------------------------------------------------------------------------
# 5. li_metal_reduction_route_compatibility
# ----------------------------------------------------------------------------


def li_metal_reduction_route_compatibility(
    envelope: Envelope | Mapping[str, Any],
    interface_mode: str | None = None,
) -> FalsifierItem:
    """PASS if interface is stable OR mode is coating_interlayer.

    Reads the ``interface_stability`` field. ``interface_mode`` may be
    supplied explicitly; otherwise it is read from the envelope's
    ``output.defect_disorder_assumptions`` list (search for
    ``"interface_mode=..."``).
    """
    output = _envelope_output(envelope)
    classification = output.get("interface_stability", "unknown")
    mode = interface_mode
    if mode is None:
        # Best-effort: pull from the assumption list.
        for assumption in output.get("defect_disorder_assumptions", []) or []:
            if isinstance(assumption, str) and assumption.startswith("interface_mode="):
                mode = assumption.split("=", 1)[1].strip()
                break
    if mode is None:
        mode = "li_metal"  # default route the operator must override explicitly

    stable_classifications = {"li_metal_stable", "cathode_facing_stable"}
    is_stable = classification in stable_classifications
    needs_coating = classification == "li_metal_unstable_coating_required"
    coating_route = mode == "coating_interlayer"

    if classification == "unknown":
        return FalsifierItem(
            name="ionic.li_metal_route_compatibility",
            threshold=(
                "stable interface OR (unstable AND mode=coating_interlayer)"
            ),
            actual={"classification": classification, "mode": mode},
            status="blocked",
            rationale="Interface classification unknown; route to AIMD interface sim.",
        )
    if is_stable:
        return FalsifierItem(
            name="ionic.li_metal_route_compatibility",
            threshold=(
                "stable interface OR (unstable AND mode=coating_interlayer)"
            ),
            actual={"classification": classification, "mode": mode},
            status="pass",
        )
    if needs_coating and coating_route:
        return FalsifierItem(
            name="ionic.li_metal_route_compatibility",
            threshold=(
                "stable interface OR (unstable AND mode=coating_interlayer)"
            ),
            actual={"classification": classification, "mode": mode},
            status="pass",
            rationale="Interface unstable but explicitly routed to coating/interlayer mode.",
        )
    return FalsifierItem(
        name="ionic.li_metal_route_compatibility",
        threshold=(
            "stable interface OR (unstable AND mode=coating_interlayer)"
        ),
        actual={"classification": classification, "mode": mode},
        status="fail",
        rationale=(
            "Interface unstable and not routed to coating/interlayer mode; "
            "PRD §Ionic Transport disallows Li-metal reduction instability "
            "outside the coating route."
        ),
    )


# ----------------------------------------------------------------------------
# 6. arrhenius_fit_quality
# ----------------------------------------------------------------------------


def arrhenius_fit_quality(
    envelope: Envelope | Mapping[str, Any],
    R2_threshold: float = 0.95,
) -> FalsifierItem:
    """PASS if the Arrhenius fit R² is at or above the threshold."""
    body = _as_dict(envelope)
    output = body.get("output", {}) if isinstance(body, Mapping) else {}
    R2 = None
    # Try the assumption list (where the adapter records it).
    for assumption in output.get("defect_disorder_assumptions", []) or []:
        if isinstance(assumption, str) and assumption.startswith("arrhenius_R2="):
            try:
                R2 = float(assumption.split("=", 1)[1].strip())
            except ValueError:
                R2 = None
            break
    # Fall back to embedded falsifier item from the ArrheniusFitAdapter.
    if R2 is None:
        for item in body.get("falsifier", {}).get("items", []) or []:
            if item.get("name") == "ionic.arrhenius_fit_quality":
                actual = item.get("actual")
                if isinstance(actual, (int, float)):
                    R2 = float(actual)
                    break
    if R2 is None:
        return FalsifierItem(
            name="ionic.arrhenius_fit_quality_gate",
            threshold=f">= {R2_threshold} R²",
            actual=None,
            status="blocked",
            rationale="No Arrhenius fit R² recorded.",
        )
    return FalsifierItem(
        name="ionic.arrhenius_fit_quality_gate",
        threshold=f">= {R2_threshold} R²",
        actual=R2,
        status="pass" if R2 >= R2_threshold else "fail",
    )


# ----------------------------------------------------------------------------
# 7. mlip_aimd_diffusion_disagreement
# ----------------------------------------------------------------------------


def mlip_aimd_diffusion_disagreement(
    envelope_mlip: Envelope | Mapping[str, Any],
    envelope_aimd: Envelope | Mapping[str, Any],
    max_disagreement_dex: float = 0.5,
) -> FalsifierItem:
    """FLAG if D values from MLIP-MD and AIMD differ by more than the threshold (dex).

    Returns ``status="fail"`` if |log10(D_mlip / D_aimd)| > threshold,
    else ``"pass"``.
    """
    out_m = _envelope_output(envelope_mlip)
    out_a = _envelope_output(envelope_aimd)
    D_m = out_m.get("diffusion_coefficient_cm2_per_s")
    D_a = out_a.get("diffusion_coefficient_cm2_per_s")
    if D_m is None or D_a is None:
        return FalsifierItem(
            name="ionic.mlip_aimd_diffusion_disagreement",
            threshold=f"|log10(D_mlip / D_aimd)| <= {max_disagreement_dex} dex",
            actual={"D_mlip": D_m, "D_aimd": D_a},
            status="blocked",
            rationale="One or both diffusion coefficients missing; cannot compare.",
        )
    if D_m <= 0 or D_a <= 0:
        return FalsifierItem(
            name="ionic.mlip_aimd_diffusion_disagreement",
            threshold=f"|log10(D_mlip / D_aimd)| <= {max_disagreement_dex} dex",
            actual={"D_mlip": D_m, "D_aimd": D_a},
            status="fail",
            rationale="Non-positive diffusion coefficient; flagged.",
        )
    disagreement = abs(math.log10(D_m / D_a))
    return FalsifierItem(
        name="ionic.mlip_aimd_diffusion_disagreement",
        threshold=f"|log10(D_mlip / D_aimd)| <= {max_disagreement_dex} dex",
        actual={"D_mlip": D_m, "D_aimd": D_a, "disagreement_dex": disagreement},
        status="pass" if disagreement <= max_disagreement_dex else "fail",
    )


# ----------------------------------------------------------------------------
# 8. defect_disorder_assumptions_documented
# ----------------------------------------------------------------------------


def defect_disorder_assumptions_documented(
    envelope: Envelope | Mapping[str, Any],
) -> FalsifierItem:
    """PASS if defect/disorder assumptions are present AND confidence is non-zero."""
    output = _envelope_output(envelope)
    assumptions = output.get("defect_disorder_assumptions") or []
    confidence = output.get("confidence", 0.0)
    has_assumptions = bool(assumptions)
    has_confidence = isinstance(confidence, (int, float)) and confidence > 0.0
    status = "pass" if has_assumptions and has_confidence else "fail"
    return FalsifierItem(
        name="ionic.defect_disorder_assumptions_documented",
        threshold="non-empty defect_disorder_assumptions AND confidence > 0",
        actual={
            "n_assumptions": len(assumptions),
            "confidence": confidence,
        },
        status=status,
        rationale=(
            "Stub adapters record the assumption set explicitly; missing "
            "assumptions or zero confidence forfeit the calibrated-uncertainty gate."
        )
        if status == "fail"
        else None,
    )


# ----------------------------------------------------------------------------
# 9. full_battery_evidence_chain_complete
# ----------------------------------------------------------------------------


def full_battery_evidence_chain_complete(
    envelopes: list[Envelope | Mapping[str, Any]],
    required_keys: tuple[str, ...] = REQUIRED_EVIDENCE_KEYS,
) -> FalsifierItem:
    """PASS if every PRD-required evidence key appears in at least one envelope.

    The PRD §Ionic Transport mandates SIX pieces of evidence for a
    battery MVP claim. This falsifier checks the union of all envelope
    output dicts and reports which keys are missing (if any).
    """
    seen: dict[str, bool] = {key: False for key in required_keys}
    for env in envelopes:
        out = _envelope_output(env)
        for key in required_keys:
            val = out.get(key)
            # The check is "present and non-null"; for the assumption
            # list and Arrhenius dict, also require non-empty.
            if val is None:
                continue
            if key == "defect_disorder_assumptions" and not val:
                continue
            if key == "interface_stability" and val == "unknown":
                continue
            seen[key] = True
    missing = [k for k, v in seen.items() if not v]
    return FalsifierItem(
        name="ionic.full_battery_evidence_chain_complete",
        threshold=f"all {len(required_keys)} required evidence keys present",
        actual={"present": [k for k, v in seen.items() if v], "missing": missing},
        status="pass" if not missing else "fail",
        rationale=(
            f"Missing evidence keys: {missing}"
            if missing
            else "All six PRD-required pieces of evidence present."
        ),
    )


# ----------------------------------------------------------------------------
# verify_ionic_service_back_edge   (Wave D hardened gate 4)
# ----------------------------------------------------------------------------


def verify_ionic_service_back_edge(
    envelope: Envelope | Mapping[str, Any],
    audit_log: Any,
) -> FalsifierItem:
    """Verify that an ionic-conductivity claim has a back-edge that resolves.

    Wave D hardened version of :func:`requires_ionic_transport_service`.
    The original gate accepted any envelope with an ``IonicTransportService``
    string in ``input_refs`` or any back-edge labelled ``"ionic"``.
    A buggy adapter could fabricate a back-edge with a non-existent
    ``audit_record_id`` and still pass.

    The hardened gate:

      1. Looks for an ionic-conductivity claim in the envelope (same
         shape as the original gate: ``output.nernst_einstein_conductivity_S_per_cm``,
         flat ``ionic_conductivity_S_per_cm``).
      2. If a claim exists, walks the back-edges, finds the one with
         ``layer == "ionic"``, and uses :func:`find_ionic_back_edge_target`
         to resolve the ``audit_record_id`` in the live audit log
         (``events.jsonl`` / ``artifacts.jsonl``).
      3. If the back-edge does NOT resolve, returns ``status="fail"``
         with reason ``ionic_back_edge_does_not_resolve``.

    Pass conditions (all must hold OR no claim is present):
      * The envelope has at least one ionic back-edge.
      * The back-edge resolves to a row whose payload references an
        ionic-layer adapter (best-effort: the row's ``layer`` field is
        ``"ionic"`` OR the ``tool_adapter.name`` includes ``"ionic"`` /
        the row's ``adapter`` mentions an ionic adapter).

    The gate is a NO-OP for envelopes with no ionic-conductivity claim.
    """
    body = _as_dict(envelope)
    output = _envelope_output(envelope)
    flat_claim = body.get("ionic_conductivity_S_per_cm")
    has_claim = bool(
        (flat_claim is not None and flat_claim != 0)
        or output.get("nernst_einstein_conductivity_S_per_cm") not in (None, 0)
    )
    if not has_claim:
        return FalsifierItem(
            name="ionic.verify_back_edge_resolves",
            threshold=(
                "if envelope claims ionic_conductivity, an ionic-layer "
                "back-edge must resolve in the audit log"
            ),
            actual={"reason": "no_claim_present"},
            status="pass",
            rationale="No ionic-conductivity claim; gate not triggered.",
        )

    back_edges = body.get("back_edges") or []
    ionic_back_edges = [
        be for be in back_edges
        if isinstance(be, Mapping) and be.get("layer") == "ionic"
    ]
    if not ionic_back_edges:
        return FalsifierItem(
            name="ionic.verify_back_edge_resolves",
            threshold=(
                "if envelope claims ionic_conductivity, an ionic-layer "
                "back-edge must exist"
            ),
            actual={"back_edges": list(back_edges)},
            status="fail",
            rationale=(
                "envelope claims ionic conductivity but has no back_edge "
                "with layer='ionic'"
            ),
        )

    target_row = find_ionic_back_edge_target(body, audit_log)
    if target_row is None:
        unresolved_ids = [be.get("audit_record_id") for be in ionic_back_edges]
        return FalsifierItem(
            name="ionic.verify_back_edge_resolves",
            threshold=(
                "ionic back-edge audit_record_id MUST resolve in events.jsonl"
            ),
            actual={
                "back_edges": list(back_edges),
                "unresolved_audit_record_ids": unresolved_ids,
            },
            status="fail",
            rationale=(
                "ionic back-edge audit_record_id does not resolve in the "
                "audit log; possible fabricated back-edge"
            ),
        )

    # Best-effort: confirm the resolved row was produced by an ionic adapter.
    adapter_name = ""
    if isinstance(target_row, Mapping):
        adapter = target_row.get("tool_adapter") or {}
        if isinstance(adapter, Mapping):
            adapter_name = str(adapter.get("name") or "")
        if not adapter_name:
            adapter_name = str(target_row.get("adapter") or "")
    layer_field = target_row.get("layer", "") if isinstance(target_row, Mapping) else ""
    looks_ionic = (
        str(layer_field).lower() == "ionic"
        or "ionic" in adapter_name.lower()
        or "neb" in adapter_name.lower()
        or "arrhenius" in adapter_name.lower()
        or "kmc" in adapter_name.lower()
    )
    if not looks_ionic:
        return FalsifierItem(
            name="ionic.verify_back_edge_resolves",
            threshold=(
                "ionic back-edge MUST resolve to an ionic-layer adapter row"
            ),
            actual={
                "resolved_layer": layer_field,
                "resolved_adapter": adapter_name,
            },
            status="fail",
            rationale=(
                "back-edge resolved but the target row was not produced by "
                "an ionic adapter"
            ),
        )

    return FalsifierItem(
        name="ionic.verify_back_edge_resolves",
        threshold=(
            "ionic back-edge MUST resolve to an ionic-layer adapter row"
        ),
        actual={
            "resolved_layer": layer_field,
            "resolved_adapter": adapter_name,
            "resolved_audit_record_id": target_row.get("audit_record_id")
            if isinstance(target_row, Mapping)
            else None,
        },
        status="pass",
    )


# ----------------------------------------------------------------------------
# neb_barrier_range_check   (Wave D hardened gate 5)
# ----------------------------------------------------------------------------


def neb_barrier_range_check(
    envelope: Envelope | Mapping[str, Any],
    sigma_threshold_S_per_cm: float = 1e-3,
    barrier_band: tuple[float, float] = ARRHENIUS_BARRIER_BAND_AT_1E_3_EV,
    min_barrier_eV: float = MIN_PLAUSIBLE_BARRIER_EV,
    max_barrier_eV: float = MAX_PLAUSIBLE_BARRIER_EV,
) -> FalsifierItem:
    """Range-check ``output.migration_barrier_eV`` and Arrhenius consistency.

    Wave D adds an explicit NEB barrier sanity gate (the previous ionic
    falsifier set had no plausibility band check). Two failure modes:

    A. Out-of-band barrier: ``barrier`` outside ``[0.05, 3.0]`` eV. This
       is almost always a bug — superionic conductors at room temperature
       cannot have barriers below ``k_B T`` (≈0.025 eV), and conductors
       above 3 eV are not physical at any practical T.

    B. Arrhenius inconsistency: when the candidate is being PROMOTED
       (``ionic_conductivity_S_per_cm >= 1e-3``) but its claimed
       ``migration_barrier_eV`` lies outside ``[0.20, 0.45]`` eV. The
       implied barrier from σ via :func:`implied_arrhenius_barrier_eV`
       at 300 K with a typical sigma_0 lives in this band.

    Pass conditions:
      * ``output.migration_barrier_eV`` is None (gate not applicable), OR
      * barrier is in ``[min_barrier_eV, max_barrier_eV]`` AND
      * if claimed σ >= ``sigma_threshold``, barrier is in ``barrier_band``.

    Returns ``status="fail"`` with rationale ``barrier_outside_literature_band``
    or ``arrhenius_inconsistent`` depending on which check trips.
    """
    output = _envelope_output(envelope)
    body = _as_dict(envelope)
    barrier = output.get("migration_barrier_eV")
    if barrier is None:
        # Try Arrhenius block too.
        arrhenius = output.get("arrhenius") or {}
        if isinstance(arrhenius, Mapping):
            barrier = arrhenius.get("activation_energy_eV")

    sigma = output.get("nernst_einstein_conductivity_S_per_cm")
    if sigma is None:
        sigma = body.get("ionic_conductivity_S_per_cm")

    if barrier is None:
        return FalsifierItem(
            name="ionic.neb_barrier_range_check",
            threshold=(
                f"{min_barrier_eV} <= migration_barrier_eV <= {max_barrier_eV}; "
                f"if sigma >= {sigma_threshold_S_per_cm:.0e} also in {barrier_band}"
            ),
            actual={"barrier_eV": None},
            status="pass",
            rationale="No migration_barrier_eV recorded; gate not triggered.",
        )

    try:
        barrier_f = float(barrier)
    except (TypeError, ValueError):
        return FalsifierItem(
            name="ionic.neb_barrier_range_check",
            threshold=(
                f"{min_barrier_eV} <= migration_barrier_eV <= {max_barrier_eV}"
            ),
            actual={"barrier_eV": barrier, "reason": "non_numeric_barrier"},
            status="fail",
            rationale="migration_barrier_eV is not a number",
        )

    # Check A: literature band.
    if barrier_f < min_barrier_eV or barrier_f > max_barrier_eV:
        return FalsifierItem(
            name="ionic.neb_barrier_range_check",
            threshold=(
                f"{min_barrier_eV} <= migration_barrier_eV <= {max_barrier_eV}"
            ),
            actual={"barrier_eV": barrier_f},
            status="fail",
            rationale="barrier_outside_literature_band",
        )

    # Check B: Arrhenius consistency for promoted candidates.
    if sigma is not None:
        try:
            sigma_f = float(sigma)
        except (TypeError, ValueError):
            sigma_f = 0.0
        if sigma_f >= sigma_threshold_S_per_cm:
            lo, hi = barrier_band
            if barrier_f < lo or barrier_f > hi:
                # Compute the implied barrier from sigma for diagnostics.
                try:
                    implied = implied_arrhenius_barrier_eV(sigma_f)
                except ValueError:
                    implied = None
                return FalsifierItem(
                    name="ionic.neb_barrier_range_check",
                    threshold=(
                        f"if sigma >= {sigma_threshold_S_per_cm:.0e} S/cm at 300 K, "
                        f"barrier in {barrier_band} eV"
                    ),
                    actual={
                        "barrier_eV": barrier_f,
                        "sigma_S_per_cm": sigma_f,
                        "implied_barrier_eV_from_sigma": implied,
                        "expected_band": list(barrier_band),
                    },
                    status="fail",
                    rationale="arrhenius_inconsistent",
                )

    return FalsifierItem(
        name="ionic.neb_barrier_range_check",
        threshold=(
            f"{min_barrier_eV} <= migration_barrier_eV <= {max_barrier_eV}; "
            f"if sigma >= {sigma_threshold_S_per_cm:.0e} also in {barrier_band}"
        ),
        actual={"barrier_eV": barrier_f, "sigma_S_per_cm": sigma},
        status="pass",
    )
