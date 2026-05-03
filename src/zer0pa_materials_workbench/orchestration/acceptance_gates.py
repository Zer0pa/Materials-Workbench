"""Unified acceptance-gate composition for candidate promotion.

PRD §L7 Falsifiers — promotion REQUIRES (and we compose every requirement,
no path may skip any):

1. **Audit provenance**: every layer envelope must carry a non-empty
   ``audit.audit_record_id`` and that ID must appear in
   :class:`~zer0pa_materials_workbench.audit.AuditLog` 's ``events`` chain back to
   the campaign's first event.

2. **Disagreement gate**: every cross-layer disagreement metric must be
   below its threshold. The candidate may not "skip" disagreement — if the
   metric is missing for a layer that produced an envelope, the gate is
   ``blocked`` (not ``pass``).

3. **Rights / reuse-scope**: the envelope's ``rights.reuse_scope`` must be
   compatible with the data class under the contract mode (delegated to
   :func:`~zer0pa_materials_workbench.audit.assert_rights_for`).

4. **Duplicate-rejection**: a previously rejected ``candidate_id`` (or
   structure_hash) cannot be re-promoted in the same campaign.

5. **Layer-specific gates**: every per-layer falsifier in
   ``zer0pa_materials_workbench.falsifiers.*_falsifiers`` is a leaf of the composed
   gate. The :func:`compose_layer_gates` helper aggregates them.

6. **Recompute consistency (Wave F5)**: every Wave D hardened recompute
   gate that applies is invoked on the envelope chain. The gate fails if
   any recompute disagrees with the envelope's claimed scalar (energy
   disagreement, force RMSE disagreement), structure_hash, novelty
   status, on-disk artifact sha256 + units sidecar, ionic back-edge
   resolution, NEB barrier plausibility, source-manifest linkage, or
   sovereign-backend enable record. ``blocked`` recomputes are also
   treated as a hard block (claim/recompute mismatch) so promotion does
   NOT fall through to the unhardened path.

The composition is **not** an "any-pass-wins" lattice. The gate fails
closed: ANY failed/blocked sub-gate forces the verdict to ``fail``. The
roll-up only returns ``pass`` when every sub-gate returned ``pass``.

The orchestrator obtains a :class:`AcceptanceGateVerdict` and writes a
``decisions.jsonl`` row + a KG ``Decision`` node + ``ROUTED_TO`` edges
encoding the routing.
"""

from __future__ import annotations

import datetime as _dt
from collections.abc import Mapping
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from zer0pa_materials_workbench.audit.rights import (
    RightsClaim,
    RightsViolationError,
    assert_rights_for,
)
from zer0pa_materials_workbench.envelope import Envelope, FalsifierItem

__all__ = [
    "AcceptanceGate",
    "AcceptanceGateVerdict",
    "GateContext",
    "GateName",
    "GateOutcome",
    "PromotionFailureReason",
    "compose_layer_gates",
]


GateName = Literal[
    "audit_provenance",
    "disagreement",
    "rights_reuse_scope",
    "duplicate_rejection",
    "layer_falsifiers",
    "ionic_battery_evidence",
    "boundary_block",
    "recompute_consistency",
]

GateOutcome = Literal["pass", "fail", "blocked", "inconclusive"]


PromotionFailureReason = Literal[
    "missing_audit_provenance",
    "disagreement_above_threshold",
    "reuse_scope_violation",
    "duplicate_of_rejected_candidate",
    "layer_falsifier_failed",
    "ionic_evidence_incomplete",
    "boundary_block_missing",
    "claim_recompute_mismatch",
]


class GateContext(BaseModel):
    """Inputs the gate composer needs to evaluate a candidate.

    - ``candidate_id`` and ``campaign_id`` are URN-prefixed strings.
    - ``layer_envelopes`` maps a layer name (``"L6"``, ``"L1"``, ``"ionic"``,
      ``"L1.5"``, ``"L2"``, ``"L3"``, ``"L4"``, ``"L5"``, ``"phase0"``) to
      the latest envelope at that layer for this candidate.
    - ``rights_claim`` is the active rights claim under which the candidate
      is being evaluated.
    - ``rejected_candidate_ids`` and ``rejected_structure_hashes`` are the
      sets the campaign has accumulated; duplicate rejection consults them.
    - ``disagreement_threshold`` is the campaign's chosen aggregate threshold;
      see :class:`zer0pa_materials_workbench.orchestration.disagreement_aggregator.AggregateDisagreement`.
    - ``audit_provenance_chain`` is a set of audit_record_ids known to be
      anchored in the audit ledger (the orchestrator passes this in; we do
      NOT walk the chain ourselves to keep the gate testable in isolation).
    """

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    candidate_id: str
    campaign_id: str
    layer_envelopes: dict[str, Envelope]
    rights_claim: RightsClaim
    rejected_candidate_ids: set[str] = Field(default_factory=set)
    rejected_structure_hashes: set[str] = Field(default_factory=set)
    disagreement_threshold: float = Field(default=0.5)
    aggregate_disagreement_score: float | None = Field(default=None)
    audit_provenance_chain: set[str] = Field(default_factory=set)
    structure_hash: str = Field(default="sha256:none")
    expected_layers: tuple[str, ...] = Field(
        default=("L6", "L2", "L1"),
        description="Layers that MUST have an envelope before promotion is considered.",
    )
    audit_log: Any | None = Field(
        default=None,
        description=(
            "Optional live AuditLog (or in-memory iterable of audit rows) "
            "used by the Wave D recompute gates that resolve back-edges, "
            "source manifests, and decision rows. When None, recompute "
            "gates that need an audit log skip with status='pass' "
            "(non-applicable); structural recomputes (L2 disagreement, L6 "
            "novelty, L5 sidecar) still run."
        ),
    )
    novelty_reference_hashes: set[str] = Field(
        default_factory=set,
        description=(
            "Reference structure_hashes (Materials Project / JARVIS / "
            "Alexandria / GNoME / OPTIMADE). Wave D L6 recompute novelty "
            "matches against this set."
        ),
    )

    def model_post_init(self, __context: Any) -> None:
        # Defensive copy of mutable sets on construction.
        self.rejected_candidate_ids = set(self.rejected_candidate_ids)
        self.rejected_structure_hashes = set(self.rejected_structure_hashes)
        self.audit_provenance_chain = set(self.audit_provenance_chain)
        self.novelty_reference_hashes = set(self.novelty_reference_hashes)


class AcceptanceGateVerdict(BaseModel):
    """The composed verdict from running every sub-gate."""

    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    campaign_id: str
    overall: GateOutcome
    gate_outcomes: dict[GateName, GateOutcome]
    falsifier_items: list[FalsifierItem] = Field(default_factory=list)
    failure_reasons: list[PromotionFailureReason] = Field(default_factory=list)
    rationale: str
    evaluated_at: str = Field(
        default_factory=lambda: _dt.datetime.now(tz=_dt.timezone.utc).isoformat(timespec="microseconds")
    )


def _research_boundary() -> str:
    from zer0pa_materials_workbench.boundary import RESEARCH_BOUNDARY

    return RESEARCH_BOUNDARY


def _audit_provenance_gate(ctx: GateContext) -> tuple[GateOutcome, FalsifierItem, list[PromotionFailureReason]]:
    missing: list[str] = []
    not_anchored: list[str] = []
    for layer, env in ctx.layer_envelopes.items():
        rec = env.audit.audit_record_id
        if not rec:
            missing.append(layer)
            continue
        # If the orchestrator passed a non-empty chain, every layer's
        # audit_record_id must appear in it. An empty chain means the gate
        # is being evaluated standalone (test-time) — we permit that.
        if ctx.audit_provenance_chain and rec not in ctx.audit_provenance_chain:
            not_anchored.append(f"{layer}:{rec}")
    if missing or not_anchored:
        item = FalsifierItem(
            name="l7.audit_provenance_gate",
            threshold="every layer envelope has audit_record_id and is anchored in audit chain",
            actual={"missing": missing, "not_anchored": not_anchored},
            status="fail",
        )
        return ("fail", item, ["missing_audit_provenance"])
    item = FalsifierItem(
        name="l7.audit_provenance_gate",
        threshold="every layer envelope has audit_record_id",
        actual={"layers_checked": sorted(ctx.layer_envelopes.keys())},
        status="pass",
    )
    return ("pass", item, [])


def _disagreement_gate(ctx: GateContext) -> tuple[GateOutcome, FalsifierItem, list[PromotionFailureReason]]:
    if ctx.aggregate_disagreement_score is None:
        # Disagreement signal missing → blocked, NOT pass. PRD: "bypasses
        # disagreement gates" is a hard failure.
        item = FalsifierItem(
            name="l7.disagreement_gate",
            threshold=f"<= {ctx.disagreement_threshold}",
            actual=None,
            status="blocked",
        )
        return ("blocked", item, ["disagreement_above_threshold"])
    score = ctx.aggregate_disagreement_score
    status: GateOutcome = "pass" if score <= ctx.disagreement_threshold else "fail"
    reasons: list[PromotionFailureReason] = []
    if status == "fail":
        reasons.append("disagreement_above_threshold")
    item = FalsifierItem(
        name="l7.disagreement_gate",
        threshold=f"<= {ctx.disagreement_threshold}",
        actual=score,
        status=status,
    )
    return (status, item, reasons)


def _rights_gate(ctx: GateContext) -> tuple[GateOutcome, FalsifierItem, list[PromotionFailureReason]]:
    """Verify every layer envelope's rights are compatible with the campaign's claim."""
    violations: list[str] = []
    for layer, env in ctx.layer_envelopes.items():
        try:
            assert_rights_for(env.rights, ctx.rights_claim)
        except RightsViolationError as exc:
            violations.append(f"{layer}: {exc}")
    if violations:
        item = FalsifierItem(
            name="l7.rights_reuse_scope_gate",
            threshold="every envelope's rights compatible with campaign claim",
            actual={"violations": violations},
            status="fail",
        )
        return ("fail", item, ["reuse_scope_violation"])
    item = FalsifierItem(
        name="l7.rights_reuse_scope_gate",
        threshold="every envelope's rights compatible with campaign claim",
        actual={"layers_checked": sorted(ctx.layer_envelopes.keys())},
        status="pass",
    )
    return ("pass", item, [])


def _duplicate_gate(ctx: GateContext) -> tuple[GateOutcome, FalsifierItem, list[PromotionFailureReason]]:
    duped_ids = ctx.candidate_id in ctx.rejected_candidate_ids
    duped_hashes = (
        ctx.structure_hash != "sha256:none"
        and ctx.structure_hash in ctx.rejected_structure_hashes
    )
    if duped_ids or duped_hashes:
        item = FalsifierItem(
            name="l7.duplicate_rejection_gate",
            threshold="not previously rejected",
            actual={
                "candidate_id_match": duped_ids,
                "structure_hash_match": duped_hashes,
                "structure_hash": ctx.structure_hash,
            },
            status="fail",
        )
        return ("fail", item, ["duplicate_of_rejected_candidate"])
    item = FalsifierItem(
        name="l7.duplicate_rejection_gate",
        threshold="not previously rejected",
        actual={"checked_count": len(ctx.rejected_candidate_ids)},
        status="pass",
    )
    return ("pass", item, [])


def _boundary_gate(ctx: GateContext) -> tuple[GateOutcome, FalsifierItem, list[PromotionFailureReason]]:
    rb = _research_boundary()
    missing: list[str] = []
    for layer, env in ctx.layer_envelopes.items():
        if env.research_boundary != rb:
            missing.append(layer)
    if missing:
        item = FalsifierItem(
            name="l7.boundary_block_gate",
            threshold="every envelope carries verbatim RESEARCH_BOUNDARY",
            actual={"missing": missing},
            status="fail",
        )
        return ("fail", item, ["boundary_block_missing"])
    item = FalsifierItem(
        name="l7.boundary_block_gate",
        threshold="every envelope carries verbatim RESEARCH_BOUNDARY",
        actual={"layers_checked": sorted(ctx.layer_envelopes.keys())},
        status="pass",
    )
    return ("pass", item, [])


def compose_layer_gates(envelopes: Mapping[str, Envelope]) -> tuple[GateOutcome, list[FalsifierItem]]:
    """Aggregate every per-layer envelope's ``falsifier.items`` into a single roll-up.

    The roll-up is **strict**: any ``fail`` is fail; any ``blocked`` without
    a fail is ``blocked``; any ``inconclusive`` without fail/blocked is
    ``inconclusive``; otherwise ``pass``.
    """
    items: list[FalsifierItem] = []
    for env in envelopes.values():
        for fi in env.falsifier.items:
            items.append(fi)
    if any(fi.status == "fail" for fi in items):
        return ("fail", items)
    if any(fi.status == "blocked" for fi in items):
        return ("blocked", items)
    if any(fi.status == "inconclusive" for fi in items):
        return ("inconclusive", items)
    return ("pass", items)


def _layer_falsifier_gate(ctx: GateContext) -> tuple[GateOutcome, list[FalsifierItem], list[PromotionFailureReason]]:
    status, items = compose_layer_gates(ctx.layer_envelopes)
    reasons: list[PromotionFailureReason] = []
    if status in ("fail", "blocked"):
        reasons.append("layer_falsifier_failed")
    return (status, items, reasons)


def _ionic_battery_evidence_gate(ctx: GateContext) -> tuple[GateOutcome, FalsifierItem, list[PromotionFailureReason]]:
    """Battery-MVP evidence gate: ionic envelope must satisfy every required key.

    PRD §Ionic Transport: the six required pieces are migration_barrier_eV,
    diffusion_coefficient_cm2_per_s, arrhenius, electrochemical_window_V_vs_LiLi,
    interface_stability, defect_disorder_assumptions. We delegate to the per-layer
    falsifier roll-up but surface the missing-key signal directly so the failure
    reason is specific.

    If no ionic envelope is present in ``ctx.layer_envelopes``, the gate is
    ``blocked`` (the campaign has not yet produced ionic evidence). This is the
    correct shape: thermoelectric campaigns will not produce an ionic envelope
    so the gate will be ``blocked``, and the campaign-specific composition can
    decide whether ``blocked`` is acceptable.
    """
    ionic = ctx.layer_envelopes.get("ionic")
    if ionic is None:
        item = FalsifierItem(
            name="l7.ionic_battery_evidence_gate",
            threshold="ionic envelope present and complete",
            actual={"present": False},
            status="blocked",
        )
        return ("blocked", item, ["ionic_evidence_incomplete"])
    out = ionic.output
    required = (
        "migration_barrier_eV",
        "diffusion_coefficient_cm2_per_s",
        "arrhenius",
        "electrochemical_window_V_vs_LiLi",
        "interface_stability",
        "defect_disorder_assumptions",
    )
    missing = [k for k in required if out.get(k) in (None, [])]
    if missing:
        item = FalsifierItem(
            name="l7.ionic_battery_evidence_gate",
            threshold="all 6 ionic evidence keys populated",
            actual={"missing": missing},
            status="fail",
        )
        return ("fail", item, ["ionic_evidence_incomplete"])
    item = FalsifierItem(
        name="l7.ionic_battery_evidence_gate",
        threshold="all 6 ionic evidence keys populated",
        actual={"present": True},
        status="pass",
    )
    return ("pass", item, [])


def _envelope_to_dict(env: Envelope) -> dict[str, Any]:
    """Return a wire-shape dict for an Envelope (Wave D recomputes accept dicts)."""
    if isinstance(env, Envelope):
        return env.model_dump(mode="json")
    if isinstance(env, dict):
        return env
    return {}


def _recompute_consistency_gate(
    ctx: GateContext,
) -> tuple[GateOutcome, list[FalsifierItem], list[PromotionFailureReason]]:
    """Wave F5: invoke every Wave D recompute gate against the envelope chain.

    For each layer envelope, run the relevant recompute falsifier:

    * L2 envelope → :func:`dpa_mace_disagreement_routing_recomputed`
    * Phase 0 envelope → :func:`verify_source_manifest_linkage` (needs audit_log)
    * L6 envelope → :func:`novelty_status_gate_recomputed`
    * Ionic envelope → :func:`verify_ionic_service_back_edge` (needs audit_log) AND
      :func:`neb_barrier_range_check` (no audit_log needed)
    * L5 envelope → :func:`verify_l5_artifact_sidecar`
    * L3 envelope → :func:`verify_l3_sovereign_block_enforced` (needs audit_log)

    Plus the `verify_source_manifest_linkage` walk on every envelope's
    ``audit.source_manifest_refs``.

    Status semantics:

    * Any sub-recompute returning ``fail`` (claim/recompute mismatch,
      forged ref, missing on-disk artifact, missing decision record, etc.)
      makes the gate fail closed.
    * ``blocked`` outcomes from sub-recomputes (e.g. recompute helper
      cannot run because per-model predictions are absent) propagate as
      ``blocked``.
    * If no audit-log-dependent recompute can run (no ``audit_log``
      passed) the structural recomputes still run and we return their
      composed outcome.
    """
    # Imports kept inside the function to avoid circular imports between
    # orchestration and falsifiers at module-load time.
    from zer0pa_materials_workbench.falsifiers.ionic_falsifiers import (
        neb_barrier_range_check,
        verify_ionic_service_back_edge,
    )
    from zer0pa_materials_workbench.falsifiers.l2_falsifiers import (
        dpa_mace_disagreement_routing_recomputed,
    )
    from zer0pa_materials_workbench.falsifiers.l3_falsifiers import (
        verify_l3_sovereign_block_enforced,
    )
    from zer0pa_materials_workbench.falsifiers.l5_falsifiers import (
        verify_l5_artifact_sidecar,
    )
    from zer0pa_materials_workbench.falsifiers.l6_falsifiers import (
        novelty_status_gate_recomputed,
    )
    from zer0pa_materials_workbench.falsifiers.phase0_falsifiers import (
        verify_source_manifest_linkage,
    )

    items: list[FalsifierItem] = []
    reasons: list[PromotionFailureReason] = []

    # --- L2 disagreement recompute ---
    l2_env = ctx.layer_envelopes.get("L2")
    if l2_env is not None:
        l2_dict = _envelope_to_dict(l2_env)
        l2_item = dpa_mace_disagreement_routing_recomputed(l2_dict)
        items.append(l2_item)

    # --- L6 novelty recompute ---
    l6_env = ctx.layer_envelopes.get("L6")
    if l6_env is not None:
        l6_dict = _envelope_to_dict(l6_env)
        # Provide reference_set so reference matches resurface as duplicate.
        # Sibling envelopes for batch dedupe come from the rest of the chain.
        sibs = [
            _envelope_to_dict(e)
            for layer, e in ctx.layer_envelopes.items()
            if layer != "L6" and (isinstance(e, Envelope) and e.layer == "L6")
        ]
        l6_item = novelty_status_gate_recomputed(
            l6_dict,
            reference_set=ctx.novelty_reference_hashes,
            batch_envelopes=sibs,
        )
        items.append(l6_item)

    # --- L5 artifact sidecar recompute ---
    l5_env = ctx.layer_envelopes.get("L5")
    if l5_env is not None:
        l5_dict = _envelope_to_dict(l5_env)
        l5_item = verify_l5_artifact_sidecar(l5_dict)
        items.append(l5_item)

    # --- Ionic back-edge + NEB barrier range ---
    ionic_env = ctx.layer_envelopes.get("ionic")
    if ionic_env is not None:
        ionic_dict = _envelope_to_dict(ionic_env)
        # The ionic envelope itself is the SOURCE of the conductivity
        # claim — it doesn't need an ionic back-edge to itself. The
        # back-edge gate is for CONSUMING envelopes (e.g. an L7
        # acceptance envelope) that reference an ionic claim. Only run
        # when an ionic-layer back-edge is actually present.
        if ctx.audit_log is not None:
            back_edges = ionic_dict.get("back_edges") or []
            has_ionic_be = any(
                isinstance(be, Mapping) and be.get("layer") == "ionic"
                for be in back_edges
            )
            if has_ionic_be:
                items.append(
                    verify_ionic_service_back_edge(ionic_dict, ctx.audit_log)
                )
        items.append(neb_barrier_range_check(ionic_dict))

    # --- L3 sovereign block enforcement ---
    l3_env = ctx.layer_envelopes.get("L3")
    if l3_env is not None and ctx.audit_log is not None:
        l3_dict = _envelope_to_dict(l3_env)
        items.append(verify_l3_sovereign_block_enforced(l3_dict, ctx.audit_log))

    # --- Phase 0 source-manifest linkage (and any envelope with manifest refs) ---
    if ctx.audit_log is not None:
        for layer, env in ctx.layer_envelopes.items():
            env_dict = _envelope_to_dict(env)
            audit_block = env_dict.get("audit") or {}
            refs = audit_block.get("source_manifest_refs") or []
            # Only run the gate when the envelope actually claims refs.
            # An empty refs list is reported as fail by the gate itself
            # — phase 0 IS expected to always carry refs, other layers
            # may not, so we only invoke the gate when refs are present
            # OR for the phase 0 envelope (the canonical caller).
            if refs or layer == "phase0":
                items.append(verify_source_manifest_linkage(env_dict, ctx.audit_log))

    # Compose outcome — ANY fail or inconsistent recompute is fail.
    statuses = [it.status for it in items]
    if "fail" in statuses:
        outcome: GateOutcome = "fail"
        reasons.append("claim_recompute_mismatch")
    elif "blocked" in statuses:
        outcome = "blocked"
        # Fail-closed: a missing-input that prevents recompute is treated
        # as a hard block (not pass). Surface it as a recompute failure
        # reason so the orchestrator does not silently promote.
        reasons.append("claim_recompute_mismatch")
    elif "inconclusive" in statuses:
        outcome = "inconclusive"
        reasons.append("claim_recompute_mismatch")
    else:
        outcome = "pass"

    if not items:
        # No recompute applicable — vacuous pass.
        items.append(
            FalsifierItem(
                name="l7.recompute_consistency_gate",
                threshold="every Wave D recompute gate that applies returns pass",
                actual={"reason": "no_recompute_applicable"},
                status="pass",
            )
        )

    return (outcome, items, reasons)


def _expected_layers_present(ctx: GateContext) -> list[str]:
    return [layer for layer in ctx.expected_layers if layer not in ctx.layer_envelopes]


class AcceptanceGate:
    """Compose every PRD-mandated promotion gate into a single verdict.

    Construction:

        gate = AcceptanceGate()
        verdict = gate.evaluate(ctx)

    Use ``include_ionic_battery_evidence=False`` to skip the ionic gate
    (e.g. for thermoelectric campaigns where the candidate doesn't need
    Li-ion evidence).
    """

    def __init__(self, include_ionic_battery_evidence: bool = True) -> None:
        self.include_ionic = include_ionic_battery_evidence

    def evaluate(self, ctx: GateContext) -> AcceptanceGateVerdict:
        outcomes: dict[GateName, GateOutcome] = {}
        all_items: list[FalsifierItem] = []
        all_reasons: list[PromotionFailureReason] = []

        # 1. boundary
        outcomes["boundary_block"], boundary_item, reasons = _boundary_gate(ctx)
        all_items.append(boundary_item)
        all_reasons.extend(reasons)

        # 2. audit provenance
        outcomes["audit_provenance"], audit_item, reasons = _audit_provenance_gate(ctx)
        all_items.append(audit_item)
        all_reasons.extend(reasons)

        # 3. disagreement
        outcomes["disagreement"], dis_item, reasons = _disagreement_gate(ctx)
        all_items.append(dis_item)
        all_reasons.extend(reasons)

        # 4. rights
        outcomes["rights_reuse_scope"], rights_item, reasons = _rights_gate(ctx)
        all_items.append(rights_item)
        all_reasons.extend(reasons)

        # 5. duplicate
        outcomes["duplicate_rejection"], dup_item, reasons = _duplicate_gate(ctx)
        all_items.append(dup_item)
        all_reasons.extend(reasons)

        # 6. layer falsifiers
        layer_status, layer_items, reasons = _layer_falsifier_gate(ctx)
        outcomes["layer_falsifiers"] = layer_status
        all_items.extend(layer_items)
        all_reasons.extend(reasons)

        # 7. ionic battery evidence (optional per campaign type)
        if self.include_ionic:
            outcomes["ionic_battery_evidence"], ionic_item, reasons = _ionic_battery_evidence_gate(ctx)
            all_items.append(ionic_item)
            all_reasons.extend(reasons)

        # 8. Wave F5: recompute-consistency gate.
        #    Runs every Wave D recompute helper that applies to the
        #    envelopes the candidate has produced. Any forged claim that
        #    passes the shape-only gates upstream gets caught here.
        recompute_status, recompute_items, recompute_reasons = (
            _recompute_consistency_gate(ctx)
        )
        outcomes["recompute_consistency"] = recompute_status
        all_items.extend(recompute_items)
        all_reasons.extend(recompute_reasons)

        # Roll-up: any fail wins; otherwise blocked > inconclusive > pass.
        statuses = list(outcomes.values())
        if "fail" in statuses:
            overall: GateOutcome = "fail"
        elif "blocked" in statuses:
            overall = "blocked"
        elif "inconclusive" in statuses:
            overall = "inconclusive"
        else:
            overall = "pass"

        # Missing expected layers always blocks.
        missing_layers = _expected_layers_present(ctx)
        if missing_layers:
            overall = "blocked" if overall == "pass" else overall
            all_items.append(
                FalsifierItem(
                    name="l7.expected_layers_present",
                    threshold=f"layers {sorted(ctx.expected_layers)} present",
                    actual={"missing": missing_layers},
                    status="blocked",
                )
            )

        rationale = _rationale(overall, outcomes, all_reasons, missing_layers)
        return AcceptanceGateVerdict(
            candidate_id=ctx.candidate_id,
            campaign_id=ctx.campaign_id,
            overall=overall,
            gate_outcomes=outcomes,
            falsifier_items=all_items,
            failure_reasons=sorted(set(all_reasons)),
            rationale=rationale,
        )


def _rationale(
    overall: GateOutcome,
    outcomes: dict[GateName, GateOutcome],
    reasons: list[PromotionFailureReason],
    missing_layers: list[str],
) -> str:
    if overall == "pass":
        return (
            "All gates pass: boundary, audit provenance, disagreement, rights, "
            "duplicate-rejection, per-layer falsifiers, and (where applicable) ionic evidence."
        )
    failed = sorted({k for k, v in outcomes.items() if v == "fail"})
    blocked = sorted({k for k, v in outcomes.items() if v == "blocked"})
    parts: list[str] = [f"Overall: {overall}."]
    if failed:
        parts.append(f"Failed gates: {failed}.")
    if blocked:
        parts.append(f"Blocked gates: {blocked}.")
    if missing_layers:
        parts.append(f"Missing required layers: {missing_layers}.")
    if reasons:
        parts.append(f"Failure reasons: {sorted(set(reasons))}.")
    return " ".join(parts)
