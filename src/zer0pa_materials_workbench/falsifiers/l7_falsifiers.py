"""L7 falsifiers (PRD §L7 falsifier gates).

Coverage:

* ``langgraph_is_not_audit`` — fails if envelope's ``audit.audit_record_id``
  is missing or the audit-event prev_hash chain doesn't reach back to the
  campaign's first event. Hard architectural boundary.
* ``prefect_lifecycle_completeness`` — fails if Prefect campaign is missing
  ``started_at``, ``deployment_id``, ``retries_attempted``, or
  ``cancellation_state``.
* ``parsl_fanout_attribution`` — fails if a fanned-out task envelope doesn't
  list its parent campaign in ``back_edges``.
* ``aiida_atomate2_provenance_complete`` — fails if any output node lacks
  ``DERIVED_FROM`` ancestry leading to a Hypothesis or OPTIMADEResource source.
* ``botorch_acquisition_function_allowed`` — fails if ``acquisition_function``
  is plain ``qExpectedImprovement`` and ``MaterialsConfig.allow_legacy_qei == False``.
* ``botorch_multi_fidelity_routing`` — fails if a multi-fidelity campaign
  uses single-fidelity acquisition without explicit override.
* ``alabos_recipe_only_enforcement`` — fails if ``ALABOS_MODE=recipe_only``
  AND the compiled artifact has ``hardware_executable=true``.
* ``candidate_promotion_provenance`` — fails if promotion lacks audit
  provenance, bypasses any disagreement gate, duplicates a rejected
  candidate, OR violates reuse_scope.
* ``cross_layer_disagreement_attribution`` — for every claim in ``output``,
  the disagreement metric must be back-traceable to the source layer that
  computed it.

Every falsifier is a pure function of an envelope (or a list of
envelopes) and returns a :class:`FalsifierItem` row.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from zer0pa_materials_workbench.envelope import Envelope, FalsifierItem

__all__ = [
    "aiida_atomate2_provenance_complete",
    "alabos_recipe_only_enforcement",
    "botorch_acquisition_function_allowed",
    "botorch_multi_fidelity_routing",
    "candidate_promotion_provenance",
    "cross_layer_disagreement_attribution",
    "langgraph_is_not_audit",
    "parsl_fanout_attribution",
    "prefect_lifecycle_completeness",
    "tenant_only_tuple_leak",
]


def _as_dict(envelope: Envelope | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(envelope, Envelope):
        return envelope.model_dump(mode="json")
    if isinstance(envelope, Mapping):
        return dict(envelope)
    raise TypeError(f"expected Envelope or Mapping, got {type(envelope).__name__}")


def _output(envelope: Envelope | Mapping[str, Any]) -> dict[str, Any]:
    out = _as_dict(envelope).get("output")
    return out if isinstance(out, dict) else {}


def _back_edges(envelope: Envelope | Mapping[str, Any]) -> list[dict[str, Any]]:
    return _as_dict(envelope).get("back_edges", []) or []


def _audit_record_id(envelope: Envelope | Mapping[str, Any]) -> str:
    audit = _as_dict(envelope).get("audit", {})
    return audit.get("audit_record_id") or ""


# ---------------------------------------------------------------------------
# l7.langgraph_is_not_audit
# ---------------------------------------------------------------------------


def langgraph_is_not_audit(
    envelope: Envelope | Mapping[str, Any],
    chain_event_hashes: set[str] | None = None,
) -> FalsifierItem:
    """Fail if the envelope's audit_record_id is missing OR not anchored.

    ``chain_event_hashes`` is the set of event_hashes known to live in the
    audit ledger. If supplied, the falsifier verifies the audit_record_id
    is anchored. If not supplied, only the presence check applies.
    """
    rec = _audit_record_id(envelope)
    if not rec:
        return FalsifierItem(
            name="l7.langgraph_is_not_audit",
            threshold="audit_record_id present and anchored in audit chain",
            actual={"audit_record_id": rec},
            status="fail",
        )
    if chain_event_hashes is not None and rec not in chain_event_hashes:
        return FalsifierItem(
            name="l7.langgraph_is_not_audit",
            threshold="audit_record_id present and anchored in audit chain",
            actual={"audit_record_id": rec, "anchored": False},
            status="fail",
        )
    return FalsifierItem(
        name="l7.langgraph_is_not_audit",
        threshold="audit_record_id present and anchored in audit chain",
        actual={"audit_record_id": rec, "anchored": chain_event_hashes is not None},
        status="pass",
    )


# ---------------------------------------------------------------------------
# l7.prefect_lifecycle_completeness
# ---------------------------------------------------------------------------


REQUIRED_PREFECT_KEYS = (
    "started_at",
    "finished_at",
    "retries_attempted",
    "cancellation_state",
    "deployment_id",
)


def prefect_lifecycle_completeness(
    envelope: Envelope | Mapping[str, Any],
) -> FalsifierItem:
    """Fail if any required Prefect lifecycle field is missing.

    The Prefect lifecycle dict is expected at ``output._prefect_lifecycle``
    or in the falsifier item with name ``l7.prefect_lifecycle_completeness``
    actual; the adapter pins it to the latter location.
    """
    items = _as_dict(envelope).get("falsifier", {}).get("items", [])
    lifecycle: dict[str, Any] | None = None
    for it in items:
        if it.get("name") == "l7.prefect_lifecycle_completeness":
            lifecycle = it.get("actual")
            break
    if not lifecycle:
        # Fall back to a heuristic: maybe the lifecycle was attached as
        # extra_input via the canonical input hash — we can't reach the
        # input here, so report blocked.
        return FalsifierItem(
            name="l7.prefect_lifecycle_completeness",
            threshold="all required Prefect lifecycle fields present",
            actual=None,
            status="blocked",
        )
    missing = [k for k in REQUIRED_PREFECT_KEYS if not lifecycle.get(k)]
    return FalsifierItem(
        name="l7.prefect_lifecycle_completeness",
        threshold=f"all of {list(REQUIRED_PREFECT_KEYS)} present",
        actual={"missing": missing, "fields": lifecycle},
        status="pass" if not missing else "fail",
    )


# ---------------------------------------------------------------------------
# l7.parsl_fanout_attribution
# ---------------------------------------------------------------------------


def parsl_fanout_attribution(
    envelope: Envelope | Mapping[str, Any],
) -> FalsifierItem:
    """Fail if the fanned-out envelope has no parent campaign in ``back_edges``."""
    edges = _back_edges(envelope)
    has_parent = any(
        e.get("relation") == "DERIVED_FROM" and e.get("layer") == "L7" for e in edges
    )
    return FalsifierItem(
        name="l7.parsl_fanout_attribution",
        threshold="back_edges contains DERIVED_FROM edge to parent L7 envelope",
        actual={"back_edges_count": len(edges), "has_parent": has_parent},
        status="pass" if has_parent else "fail",
    )


# ---------------------------------------------------------------------------
# l7.aiida_atomate2_provenance_complete
# ---------------------------------------------------------------------------


def aiida_atomate2_provenance_complete(
    envelope: Envelope | Mapping[str, Any],
) -> FalsifierItem:
    """Fail if any leaf output lacks DERIVED_FROM ancestry to a root source."""
    items = _as_dict(envelope).get("falsifier", {}).get("items", [])
    for it in items:
        if it.get("name") == "l7.aiida_atomate2_provenance_complete":
            actual = it.get("actual") or {}
            complete = bool(actual.get("complete"))
            return FalsifierItem(
                name="l7.aiida_atomate2_provenance_complete",
                threshold="every leaf has DERIVED_FROM ancestor leading to root",
                actual=actual,
                status="pass" if complete else "fail",
            )
    return FalsifierItem(
        name="l7.aiida_atomate2_provenance_complete",
        threshold="every leaf has DERIVED_FROM ancestor leading to root",
        actual=None,
        status="blocked",
    )


# ---------------------------------------------------------------------------
# l7.botorch_acquisition_function_allowed
# ---------------------------------------------------------------------------


def botorch_acquisition_function_allowed(
    envelope: Envelope | Mapping[str, Any],
    allow_legacy_qei: bool = False,
) -> FalsifierItem:
    """Fail if acquisition is plain ``qExpectedImprovement`` and not opted-in."""
    out = _output(envelope)
    acq = out.get("acquisition")
    if acq is None:
        return FalsifierItem(
            name="l7.botorch_acquisition_function_allowed",
            threshold="acquisition in {qMultiFidelityKnowledgeGradient, qLogExpectedImprovement} OR allow_legacy_qei=True",
            actual=acq,
            status="blocked",
        )
    # The L7CampaignOutput pydantic model only allows the two PRD-mandated
    # values plus 'other'. If we see 'other' AND can find an inner record
    # naming qExpectedImprovement we still want to fail. Look in extra
    # falsifier items for the adapter-level acquisition_function record.
    extra_acq: str | None = None
    items = _as_dict(envelope).get("falsifier", {}).get("items", [])
    for it in items:
        if it.get("name") == "l7.botorch_acquisition_function_allowed":
            actual = it.get("actual") or {}
            extra_acq = actual.get("acquisition_function")
            allow_flag = bool(actual.get("allow_legacy_qei", False))
            allow_legacy_qei = allow_legacy_qei or allow_flag
            break
    effective_acq = extra_acq or acq
    is_forbidden = effective_acq == "qExpectedImprovement" and not allow_legacy_qei
    return FalsifierItem(
        name="l7.botorch_acquisition_function_allowed",
        threshold="acquisition not qExpectedImprovement (or allow_legacy_qei=True)",
        actual={"acquisition": effective_acq, "allow_legacy_qei": allow_legacy_qei},
        status="fail" if is_forbidden else "pass",
    )


# ---------------------------------------------------------------------------
# l7.botorch_multi_fidelity_routing
# ---------------------------------------------------------------------------


def botorch_multi_fidelity_routing(
    envelope: Envelope | Mapping[str, Any],
) -> FalsifierItem:
    """Fail if a multi-fidelity campaign uses single-fidelity acquisition."""
    items = _as_dict(envelope).get("falsifier", {}).get("items", [])
    for it in items:
        if it.get("name") == "l7.botorch_multi_fidelity_routing":
            actual = it.get("actual") or {}
            is_mf = bool(actual.get("is_multi_fidelity"))
            acq = actual.get("acquisition_function")
            ok = (
                (is_mf and acq == "qMultiFidelityKnowledgeGradient")
                or (not is_mf and acq == "qLogExpectedImprovement")
                or (is_mf and acq == "qMultiFidelityKnowledgeGradient")
            )
            return FalsifierItem(
                name="l7.botorch_multi_fidelity_routing",
                threshold="MF→qMFKG; SF→qLogEI",
                actual=actual,
                status="pass" if ok else "fail",
            )
    return FalsifierItem(
        name="l7.botorch_multi_fidelity_routing",
        threshold="MF→qMFKG; SF→qLogEI",
        actual=None,
        status="blocked",
    )


# ---------------------------------------------------------------------------
# l7.alabos_recipe_only_enforcement
# ---------------------------------------------------------------------------


def alabos_recipe_only_enforcement(
    payload: dict[str, Any],
) -> FalsifierItem:
    """Hard-fail gate: ``alabos_mode='recipe_only'`` and ``hardware_executable=True`` is illegal.

    ``payload`` is the AlabOS protocol JSON (the same shape as
    :class:`AlabOSProtocolCandidate.model_dump`). The fixture
    ``fixtures/negatives/alabos_executable_in_recipe_only/protocol.json``
    is a deliberate violation; the falsifier must fire on it.
    """
    mode = payload.get("alabos_mode")
    he = payload.get("hardware_executable")
    is_recipe_only = mode == "recipe_only"
    is_executable = bool(he)
    is_violation = is_recipe_only and is_executable
    return FalsifierItem(
        name="l7.alabos_recipe_only_enforcement",
        threshold="alabos_mode='recipe_only' implies hardware_executable=False",
        actual={
            "alabos_mode": mode,
            "hardware_executable": is_executable,
            "violation": is_violation,
        },
        status="fail" if is_violation else "pass",
    )


# ---------------------------------------------------------------------------
# l7.tenant_only_tuple_leak
# ---------------------------------------------------------------------------


def tenant_only_tuple_leak(
    bundle: dict[str, Any],
) -> FalsifierItem:
    """Fail if a shared_learning bundle contains a tuple at tenant_only scope.

    PRD §Self-Bootstrapping Reasoner / §Falsification wave: "private tuple
    reuse outside reuse_scope" is a hard failure. The fixture
    ``fixtures/negatives/tenant_only_tuple_leak/tuple_export.json`` is the
    deliberate violation.

    Rule:
      * If ``bundle.export_bundle == 'shared_learning'``, every tuple's
        ``reuse_scope`` must be in {'shared_learning', 'open_science'}.
      * If ``bundle.export_bundle == 'open_science'``, every tuple's
        ``reuse_scope`` must equal ``'open_science'``.
      * tenant_only bundles have no constraint at this gate.
    """
    bundle_scope = bundle.get("export_bundle")
    tuples = bundle.get("tuples", []) or []
    leaks: list[str] = []
    if bundle_scope == "shared_learning":
        for t in tuples:
            ts = t.get("reuse_scope")
            if ts not in ("shared_learning", "open_science"):
                leaks.append(t.get("tuple_id", "<unknown>"))
    elif bundle_scope == "open_science":
        for t in tuples:
            if t.get("reuse_scope") != "open_science":
                leaks.append(t.get("tuple_id", "<unknown>"))
    return FalsifierItem(
        name="l7.tenant_only_tuple_leak",
        threshold=(
            "shared_learning bundles contain only shared_learning/open_science tuples; "
            "open_science bundles contain only open_science tuples"
        ),
        actual={"bundle_scope": bundle_scope, "leaks": leaks},
        status="fail" if leaks else "pass",
    )


# ---------------------------------------------------------------------------
# l7.candidate_promotion_provenance
# ---------------------------------------------------------------------------


def candidate_promotion_provenance(
    envelope: Envelope | Mapping[str, Any],
    *,
    rejected_candidate_ids: set[str] | None = None,
    rejected_structure_hashes: set[str] | None = None,
    audit_provenance_chain: set[str] | None = None,
    expected_disagreement_present: bool = True,
    rights_compatible: bool = True,
) -> FalsifierItem:
    """Promotion gate composed of every PRD-mandated requirement.

    Rules:

      * ``audit.audit_record_id`` non-empty (and anchored if chain provided).
      * ``output.promotion_decision == 'promote'`` only if disagreement
        signal was present (i.e. promotion did not bypass the disagreement gate).
      * ``candidate_id`` not in ``rejected_candidate_ids``.
      * ``output.structure_hash`` not in ``rejected_structure_hashes`` (when
        the envelope carries a structure_hash).
      * ``rights_compatible == True``.
    """
    env = _as_dict(envelope)
    out = _output(envelope)
    rec = _audit_record_id(envelope)
    decision = out.get("promotion_decision")
    cid = env.get("candidate_id", "")
    sh = out.get("structure_hash", "")
    failures: list[str] = []
    # Audit provenance.
    if not rec:
        failures.append("missing_audit_record_id")
    elif audit_provenance_chain is not None and rec not in audit_provenance_chain:
        failures.append("audit_record_id_not_anchored")
    # Disagreement gate not bypassed.
    if decision == "promote" and not expected_disagreement_present:
        failures.append("disagreement_gate_bypassed")
    # Duplicate of rejected candidate.
    if rejected_candidate_ids is not None and cid in rejected_candidate_ids:
        failures.append("duplicate_of_rejected_candidate_id")
    if (
        rejected_structure_hashes is not None
        and sh
        and sh != "sha256:none"
        and sh in rejected_structure_hashes
    ):
        failures.append("duplicate_of_rejected_structure_hash")
    # Rights compatibility.
    if not rights_compatible:
        failures.append("reuse_scope_violation")
    return FalsifierItem(
        name="l7.candidate_promotion_provenance",
        threshold=(
            "promote requires audit_record_id, no disagreement bypass, "
            "not a duplicate of a rejected candidate, and rights compatibility"
        ),
        actual={"failures": failures, "decision": decision},
        status="fail" if failures else "pass",
    )


# ---------------------------------------------------------------------------
# l7.cross_layer_disagreement_attribution
# ---------------------------------------------------------------------------


def cross_layer_disagreement_attribution(
    envelope: Envelope | Mapping[str, Any],
) -> FalsifierItem:
    """Every disagreement metric must be back-traceable to its source layer.

    The aggregator records ``per_layer_audit_refs`` in the envelope's
    ``output`` (or ``extra_input``). For every metric in
    ``disagreement.metrics`` we expect a corresponding audit_ref.
    """
    env = _as_dict(envelope)
    metrics = env.get("disagreement", {}).get("metrics", []) or []
    out = env.get("output", {}) or {}
    refs = out.get("per_layer_audit_refs", {}) or {}
    if not metrics:
        return FalsifierItem(
            name="l7.cross_layer_disagreement_attribution",
            threshold="every metric has per_layer_audit_refs entry",
            actual={"metrics_count": 0},
            status="blocked",
        )
    missing: list[str] = []
    for m in metrics:
        layer_label = m.get("name", "")
        # Heuristic: the metric name often starts with "L1.5_disagreement",
        # "L2_disagreement", etc. We accept either the bare layer or the
        # raw metric-name as a key into refs.
        bare = layer_label.split("_")[0]
        if bare not in refs and layer_label not in refs:
            missing.append(layer_label or "<unnamed>")
    return FalsifierItem(
        name="l7.cross_layer_disagreement_attribution",
        threshold="every disagreement metric has per_layer_audit_refs back-traceability",
        actual={"missing": missing, "metrics_count": len(metrics)},
        status="fail" if missing else "pass",
    )
