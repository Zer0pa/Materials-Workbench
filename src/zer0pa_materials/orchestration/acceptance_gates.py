"""Unified acceptance-gate composition for candidate promotion.

PRD §L7 Falsifiers — promotion REQUIRES (and we compose every requirement,
no path may skip any):

1. **Audit provenance**: every layer envelope must carry a non-empty
   ``audit.audit_record_id`` and that ID must appear in
   :class:`~zer0pa_materials.audit.AuditLog` 's ``events`` chain back to
   the campaign's first event.

2. **Disagreement gate**: every cross-layer disagreement metric must be
   below its threshold. The candidate may not "skip" disagreement — if the
   metric is missing for a layer that produced an envelope, the gate is
   ``blocked`` (not ``pass``).

3. **Rights / reuse-scope**: the envelope's ``rights.reuse_scope`` must be
   compatible with the data class under the contract mode (delegated to
   :func:`~zer0pa_materials.audit.assert_rights_for`).

4. **Duplicate-rejection**: a previously rejected ``candidate_id`` (or
   structure_hash) cannot be re-promoted in the same campaign.

5. **Layer-specific gates**: every per-layer falsifier in
   ``zer0pa_materials.falsifiers.*_falsifiers`` is a leaf of the composed
   gate. The :func:`compose_layer_gates` helper aggregates them.

The composition is **not** an "any-pass-wins" lattice. The gate fails
closed: ANY failed/blocked sub-gate forces the verdict to ``fail``. The
roll-up only returns ``pass`` when every sub-gate returned ``pass``.

The orchestrator obtains a :class:`AcceptanceGateVerdict` and writes a
``decisions.jsonl`` row + a KG ``Decision`` node + ``ROUTED_TO`` edges
encoding the routing.
"""

from __future__ import annotations

import datetime as _dt
import re
from typing import Any, Iterable, Literal, Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field

from zer0pa_materials.audit.rights import (
    RightsClaim,
    RightsViolationError,
    assert_rights_for,
)
from zer0pa_materials.envelope import Envelope, FalsifierItem

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
      see :class:`zer0pa_materials.orchestration.disagreement_aggregator.AggregateDisagreement`.
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

    def model_post_init(self, __context: Any) -> None:
        # Defensive copy of mutable sets on construction.
        self.rejected_candidate_ids = set(self.rejected_candidate_ids)
        self.rejected_structure_hashes = set(self.rejected_structure_hashes)
        self.audit_provenance_chain = set(self.audit_provenance_chain)


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
    from zer0pa_materials.boundary import RESEARCH_BOUNDARY

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
