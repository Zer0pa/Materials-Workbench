"""Campaign object — the central L7 orchestration state.

State machine:

    created → hypothesising → generating → screening_l2 → validating_l1 →
    ionic_evidence → packet_assembly → {promoted | rejected | parked}

Every transition writes a :class:`zer0pa_materials_workbench.audit.Decision` row to
``decisions.jsonl`` and a KG ``Decision`` node + ``ROUTED_TO`` edge into
the active :class:`zer0pa_materials_workbench.audit.MaterialsKG`. The campaign
``runs.jsonl`` row is written once at creation; resume uses
``runs.jsonl`` + ``events.jsonl`` + ``decisions.jsonl`` to reconstruct
state.

Resume protocol (PRD §Brain-functionality):

    A fresh agent reading only audit JSONL files can reconstruct campaign
    state without chat history.

The :meth:`Campaign.resume_from_audit` classmethod implements this. It
reads:

    1. ``runs.jsonl`` for the campaign's ``CampaignSpec``
    2. ``decisions.jsonl`` for the transition history
    3. ``events.jsonl`` for per-candidate envelope refs

and returns a fully-populated :class:`Campaign` whose state matches the
last persisted moment.
"""

from __future__ import annotations

import datetime as _dt
import re
import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from zer0pa_materials_workbench.audit.decisions import Decision, DecisionMaker
from zer0pa_materials_workbench.audit.kg import KGEdgeType, KGNodeType, MaterialsKG
from zer0pa_materials_workbench.audit.log import AuditLog
from zer0pa_materials_workbench.envelope import Envelope
from zer0pa_materials_workbench.orchestration.candidate_state import (
    CandidateRecord,
    CandidateStatus,
)

__all__ = [
    "Campaign",
    "CampaignSpec",
    "CampaignState",
    "CampaignStatus",
]


CampaignStatus = Literal[
    "created",
    "hypothesising",
    "generating",
    "screening_l2",
    "validating_l1",
    "ionic_evidence",
    "packet_assembly",
    "promoted",
    "rejected",
    "parked",
]


_CAMPAIGN_TRANSITIONS: frozenset[tuple[CampaignStatus, CampaignStatus]] = frozenset(
    {
        ("created", "hypothesising"),
        ("hypothesising", "generating"),
        ("hypothesising", "parked"),
        ("generating", "screening_l2"),
        ("generating", "parked"),
        ("screening_l2", "validating_l1"),
        ("screening_l2", "parked"),
        ("validating_l1", "ionic_evidence"),
        ("validating_l1", "parked"),
        ("ionic_evidence", "packet_assembly"),
        ("ionic_evidence", "parked"),
        ("packet_assembly", "promoted"),
        ("packet_assembly", "rejected"),
        ("packet_assembly", "parked"),
        # Resume from a parked state can re-enter any earlier state.
        ("parked", "hypothesising"),
        ("parked", "generating"),
        ("parked", "screening_l2"),
        ("parked", "validating_l1"),
        ("parked", "ionic_evidence"),
        ("parked", "packet_assembly"),
    }
)


_CAMPAIGN_ID_RE = re.compile(r"^campaign:[A-Za-z0-9._\-:/]+$")


def _utc_now() -> str:
    return _dt.datetime.now(tz=_dt.timezone.utc).isoformat(timespec="microseconds")


class CampaignSpec(BaseModel):
    """Immutable spec for a campaign.

    Recorded once at creation in ``runs.jsonl``; used by :meth:`Campaign.resume_from_audit`
    to reconstruct the campaign object.
    """

    model_config = ConfigDict(extra="forbid")

    campaign_id: str = Field(..., description="URN starting with 'campaign:'.")
    tenant: str = Field(..., min_length=1, description="Tenant URN-fragment, e.g. 'demo'.")
    objective: str = Field(
        ...,
        min_length=1,
        description="Property target (e.g. 'Li-ion conductivity > 1e-3 S/cm').",
    )
    chemical_system: str = Field(
        default="",
        description="Chemical system constraint, e.g. 'Li-La-Zr-O'.",
    )
    rights_claim_id: str = Field(default="rights:default")
    reuse_scope: str = Field(default="tenant_only")
    created_at: str = Field(default_factory=_utc_now)
    boundary_block: str = Field(
        default="",
        description="RESEARCH_BOUNDARY value baked in at construction.",
    )

    @field_validator("campaign_id")
    @classmethod
    def _v(cls, v: str) -> str:
        if not _CAMPAIGN_ID_RE.match(v):
            raise ValueError(f"campaign_id must match {_CAMPAIGN_ID_RE.pattern!r}; got {v!r}")
        return v


class CampaignState(BaseModel):
    """Mutable in-memory state of a campaign."""

    model_config = ConfigDict(extra="forbid")

    spec: CampaignSpec
    status: CampaignStatus = Field(default="created")
    candidates: dict[str, CandidateRecord] = Field(default_factory=dict)
    rejected_candidate_ids: list[str] = Field(default_factory=list)
    rejected_structure_hashes: list[str] = Field(default_factory=list)
    promoted_candidate_ids: list[str] = Field(default_factory=list)
    last_decision_id: str | None = Field(default=None)
    last_event_hash: str | None = Field(default=None)
    updated_at: str = Field(default_factory=_utc_now)

    def can_transition_to(self, next_status: CampaignStatus) -> bool:
        return (self.status, next_status) in _CAMPAIGN_TRANSITIONS

    @property
    def is_terminal(self) -> bool:
        return self.status in ("promoted", "rejected")


class Campaign:
    """Central orchestration object.

    Construction (new):

        camp = Campaign.create(
            spec=spec,
            audit_log=AuditLog(...),
            kg=MaterialsKG(...),
        )

    Construction (resume):

        camp = Campaign.resume_from_audit(
            campaign_id="campaign:foo",
            audit_log=AuditLog(...),
            kg=MaterialsKG(...),
        )

    Each :meth:`transition_to` call:

      * checks the candidate transition against :data:`_CAMPAIGN_TRANSITIONS`
      * appends a :class:`Decision` row to ``decisions.jsonl``
      * writes a KG ``Decision`` node and a ``ROUTED_TO`` edge from the
        previous decision (if any) to the new one
      * updates ``CampaignState.status`` and ``last_decision_id``

    Concurrency: ``transition_to`` is not thread-safe; the orchestrator
    is expected to run on a single thread per campaign. The ``AuditLog``
    family-level locking serialises across processes if the campaign is
    accessed from multiple processes.
    """

    def __init__(
        self,
        state: CampaignState,
        audit_log: AuditLog,
        kg: MaterialsKG,
    ) -> None:
        self.state = state
        self.audit_log = audit_log
        self.kg = kg

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    @classmethod
    def create(
        cls,
        spec: CampaignSpec,
        audit_log: AuditLog,
        kg: MaterialsKG,
        decision_maker: DecisionMaker = "policy",
    ) -> Campaign:
        """Persist a new campaign to the audit log and KG, then return the object."""
        # 1. Write run row.
        from zer0pa_materials_workbench.boundary import RESEARCH_BOUNDARY

        spec_with_boundary = spec.model_copy(
            update={
                "boundary_block": spec.boundary_block or RESEARCH_BOUNDARY,
            }
        )
        run_payload = {
            "campaign_id": spec_with_boundary.campaign_id,
            "tenant": spec_with_boundary.tenant,
            "objective": spec_with_boundary.objective,
            "chemical_system": spec_with_boundary.chemical_system,
            "rights_claim_id": spec_with_boundary.rights_claim_id,
            "reuse_scope": spec_with_boundary.reuse_scope,
            "research_boundary": spec_with_boundary.boundary_block,
            "spec_kind": "campaign",
        }
        run_row = audit_log.append_event("runs", run_payload)

        # 2. KG: Campaign + Objective + AcceptanceGate placeholder + CustomerTenant.
        tenant_node_id = f"tenant:{spec_with_boundary.tenant}"
        # Idempotent: only create if missing.
        if kg.get_node(tenant_node_id) is None:
            kg.add_node(
                node_id=tenant_node_id,
                node_type=KGNodeType.CustomerTenant,
                properties={"name": spec_with_boundary.tenant},
                run_id=spec_with_boundary.campaign_id,
            )
        kg.add_node(
            node_id=spec_with_boundary.campaign_id,
            node_type=KGNodeType.Campaign,
            properties={
                "objective": spec_with_boundary.objective,
                "chemical_system": spec_with_boundary.chemical_system,
            },
            run_id=spec_with_boundary.campaign_id,
        )
        kg.add_edge(
            edge_id=f"edge:{spec_with_boundary.campaign_id}->{tenant_node_id}",
            src_id=spec_with_boundary.campaign_id,
            dst_id=tenant_node_id,
            edge_type=KGEdgeType.ATTRIBUTED_TO,
            run_id=spec_with_boundary.campaign_id,
        )
        # AcceptanceGate placeholder node.
        gate_node_id = f"gate:{spec_with_boundary.campaign_id}:promotion"
        kg.add_node(
            node_id=gate_node_id,
            node_type=KGNodeType.AcceptanceGate,
            properties={"name": "promotion_gate", "objective": spec_with_boundary.objective},
            run_id=spec_with_boundary.campaign_id,
        )

        # 3. Initial state and "creation" decision.
        state = CampaignState(
            spec=spec_with_boundary,
            status="created",
            last_event_hash=run_row.event_hash,
        )
        camp = cls(state=state, audit_log=audit_log, kg=kg)
        camp._record_decision(
            from_status="created",
            to_status="created",
            context="campaign created",
            options=["create", "abort"],
            chosen="create",
            rationale=f"campaign {spec_with_boundary.campaign_id} created for tenant {spec_with_boundary.tenant}",
            decision_maker=decision_maker,
            initial=True,
        )
        return camp

    @classmethod
    def resume_from_audit(
        cls,
        campaign_id: str,
        audit_log: AuditLog,
        kg: MaterialsKG,
    ) -> Campaign:
        """Reconstruct a Campaign from the audit log alone.

        Reads ``runs.jsonl`` for the matching campaign spec, then walks
        ``decisions.jsonl`` to replay every transition. Per-candidate state
        is reconstructed from ``events.jsonl`` rows with ``payload.kind ==
        "candidate_transition"``.
        """
        # 1. Find the spec.
        spec: CampaignSpec | None = None
        for row in audit_log.iter_rows("runs"):
            payload = row.payload
            if payload.get("campaign_id") == campaign_id and payload.get("spec_kind") == "campaign":
                spec = CampaignSpec(
                    campaign_id=payload["campaign_id"],
                    tenant=payload["tenant"],
                    objective=payload["objective"],
                    chemical_system=payload.get("chemical_system", ""),
                    rights_claim_id=payload.get("rights_claim_id", "rights:default"),
                    reuse_scope=payload.get("reuse_scope", "tenant_only"),
                    boundary_block=payload.get("research_boundary", ""),
                )
                break
        if spec is None:
            raise KeyError(f"no campaign spec found for {campaign_id!r} in runs.jsonl")

        # 2. Replay transitions.
        state = CampaignState(spec=spec, status="created")
        for row in audit_log.iter_rows("decisions"):
            payload = row.payload
            if payload.get("scope_campaign_id") != campaign_id:
                continue
            kind = payload.get("kind")
            if kind == "campaign_transition":
                next_status: CampaignStatus = payload["to_status"]
                # Skip the bootstrap "created→created" record.
                if payload.get("from_status") == next_status:
                    state.last_decision_id = payload.get("decision_id")
                    state.last_event_hash = row.event_hash
                    continue
                if state.can_transition_to(next_status):
                    state.status = next_status
                state.last_decision_id = payload.get("decision_id")
                state.last_event_hash = row.event_hash
            elif kind == "candidate_transition":
                cid = payload["candidate_id"]
                cur = state.candidates.get(
                    cid,
                    CandidateRecord(candidate_id=cid),
                )
                next_cs: CandidateStatus = payload["to_status"]
                try:
                    new = cur.transition_to(
                        next_cs,
                        decision_id=payload.get("decision_id"),
                        rejection_reason=payload.get("rejection_reason"),
                        higher_fidelity_request=payload.get("higher_fidelity_request"),
                    )
                except ValueError:
                    # Tolerate replay of an illegal transition by keeping the
                    # current record; this can happen if a category file was
                    # restored out-of-order.
                    new = cur
                state.candidates[cid] = new
                if new.status == "rejected":
                    if cid not in state.rejected_candidate_ids:
                        state.rejected_candidate_ids.append(cid)
                elif new.status == "promoted":
                    if cid not in state.promoted_candidate_ids:
                        state.promoted_candidate_ids.append(cid)

        # 3. Replay attached envelopes via events.jsonl.
        for row in audit_log.iter_rows("events"):
            payload = row.payload
            if payload.get("campaign_id") != campaign_id:
                continue
            if payload.get("kind") != "envelope_attached":
                continue
            cid = payload.get("candidate_id")
            layer = payload.get("layer")
            audit_record_id = payload.get("audit_record_id")
            if cid and layer and audit_record_id:
                cur = state.candidates.get(cid, CandidateRecord(candidate_id=cid))
                state.candidates[cid] = cur.attach_layer_envelope(layer, audit_record_id)
                # Track the structure_hash for duplicate detection.
                sh = payload.get("structure_hash")
                if sh and sh != "sha256:none":
                    state.candidates[cid] = state.candidates[cid].model_copy(
                        update={"structure_hash": sh}
                    )
        return cls(state=state, audit_log=audit_log, kg=kg)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def transition_to(
        self,
        next_status: CampaignStatus,
        *,
        rationale: str = "",
        options_considered: list[str] | None = None,
        decision_maker: DecisionMaker = "policy",
    ) -> Decision:
        """Advance the campaign to ``next_status``."""
        if not self.state.can_transition_to(next_status):
            raise ValueError(
                f"illegal campaign transition {self.state.status!r} -> {next_status!r}"
            )
        from_status = self.state.status
        decision = self._record_decision(
            from_status=from_status,
            to_status=next_status,
            context=f"campaign moves from {from_status} to {next_status}",
            options=options_considered or [from_status, next_status],
            chosen=next_status,
            rationale=rationale or f"transition {from_status} -> {next_status}",
            decision_maker=decision_maker,
        )
        self.state.status = next_status
        self.state.updated_at = _utc_now()
        return decision

    def register_candidate(
        self,
        candidate_id: str,
        structure_hash: str = "sha256:none",
        proposed_action: str = "propose_candidate",
    ) -> CandidateRecord:
        """Register a fresh candidate with status='proposed'."""
        if candidate_id in self.state.candidates:
            return self.state.candidates[candidate_id]
        rec = CandidateRecord(
            candidate_id=candidate_id,
            structure_hash=structure_hash,
            proposed_action=proposed_action,
        )
        self.state.candidates[candidate_id] = rec
        # KG: CandidateMaterial node.
        if self.kg.get_node(candidate_id) is None:
            self.kg.add_node(
                node_id=candidate_id,
                node_type=KGNodeType.CandidateMaterial,
                properties={
                    "structure_hash": structure_hash,
                    "proposed_action": proposed_action,
                },
                run_id=self.state.spec.campaign_id,
            )
            self.kg.add_edge(
                edge_id=f"edge:{self.state.spec.campaign_id}->{candidate_id}",
                src_id=self.state.spec.campaign_id,
                dst_id=candidate_id,
                edge_type=KGEdgeType.GENERATED,
                run_id=self.state.spec.campaign_id,
            )
        # Hypothesis node — one per candidate; signal that the campaign has
        # a hypothesis under test for this candidate.
        hyp_node = f"hypothesis:{candidate_id}"
        if self.kg.get_node(hyp_node) is None:
            self.kg.add_node(
                node_id=hyp_node,
                node_type=KGNodeType.Hypothesis,
                properties={
                    "candidate_id": candidate_id,
                    "objective": self.state.spec.objective,
                },
                run_id=self.state.spec.campaign_id,
            )
            self.kg.add_edge(
                edge_id=f"edge:{candidate_id}->{hyp_node}",
                src_id=candidate_id,
                dst_id=hyp_node,
                edge_type=KGEdgeType.HAS_PROPERTY,
                run_id=self.state.spec.campaign_id,
            )
        return rec

    def transition_candidate(
        self,
        candidate_id: str,
        next_status: CandidateStatus,
        *,
        rationale: str = "",
        rejection_reason: str | None = None,
        higher_fidelity_request: str | None = None,
        decision_maker: DecisionMaker = "policy",
    ) -> Decision:
        """Advance a candidate's state machine."""
        rec = self.state.candidates.get(candidate_id)
        if rec is None:
            raise KeyError(f"unknown candidate {candidate_id!r}")
        new_rec = rec.transition_to(
            next_status,
            rejection_reason=rejection_reason,
            higher_fidelity_request=higher_fidelity_request,
        )
        # Decision row.
        decision = self._record_candidate_decision(
            candidate_id=candidate_id,
            from_status=rec.status,
            to_status=next_status,
            rationale=rationale or f"candidate {rec.status} -> {next_status}",
            rejection_reason=rejection_reason,
            higher_fidelity_request=higher_fidelity_request,
            decision_maker=decision_maker,
        )
        new_rec = new_rec.model_copy(update={"last_decision_id": decision.decision_id})
        self.state.candidates[candidate_id] = new_rec
        if next_status == "rejected" and candidate_id not in self.state.rejected_candidate_ids:
            self.state.rejected_candidate_ids.append(candidate_id)
            if rec.structure_hash != "sha256:none":
                self.state.rejected_structure_hashes.append(rec.structure_hash)
        if next_status == "promoted" and candidate_id not in self.state.promoted_candidate_ids:
            self.state.promoted_candidate_ids.append(candidate_id)
        return decision

    def attach_envelope(self, env: Envelope) -> None:
        """Pin a layer envelope to the candidate referenced in it.

        Writes an ``events.jsonl`` row of kind ``envelope_attached`` so
        :meth:`resume_from_audit` can reconstruct the link.
        """
        cid = env.candidate_id
        if cid not in self.state.candidates:
            self.register_candidate(cid)
        new_rec = self.state.candidates[cid].attach_layer_envelope(
            env.layer, env.audit.audit_record_id
        )
        # Pull structure_hash from the envelope's output if available
        # (L6, L1, ionic, L2, L1.5 all carry one when relevant).
        out = env.output or {}
        if "structure_hash" in out and isinstance(out["structure_hash"], str):
            new_rec = new_rec.model_copy(update={"structure_hash": out["structure_hash"]})
        self.state.candidates[cid] = new_rec
        payload = {
            "campaign_id": self.state.spec.campaign_id,
            "candidate_id": cid,
            "layer": env.layer,
            "audit_record_id": env.audit.audit_record_id,
            "structure_hash": new_rec.structure_hash,
            "kind": "envelope_attached",
            "tool_adapter": env.tool_adapter.model_dump(mode="json"),
        }
        row = self.audit_log.append_event("events", payload)
        self.state.last_event_hash = row.event_hash

    # ------------------------------------------------------------------
    # Decision recording (private)
    # ------------------------------------------------------------------

    def _record_decision(
        self,
        from_status: CampaignStatus,
        to_status: CampaignStatus,
        context: str,
        options: list[str],
        chosen: str,
        rationale: str,
        decision_maker: DecisionMaker = "policy",
        initial: bool = False,
    ) -> Decision:
        decision_id = f"decision:{self.state.spec.campaign_id}:{uuid.uuid4().hex[:8]}"
        # Always supply at least the from/to as options to satisfy min_length=1.
        opts: list[str] = list(options) if options else [chosen]
        if chosen not in opts:
            opts.append(chosen)
        decision = Decision(
            decision_id=decision_id,
            made_by=decision_maker,
            context=context,
            options_considered=opts,
            chosen=chosen,
            rationale=rationale,
            supersedes=[self.state.last_decision_id] if self.state.last_decision_id else [],
        )
        payload = decision.model_dump(mode="json")
        payload["scope_campaign_id"] = self.state.spec.campaign_id
        payload["from_status"] = from_status
        payload["to_status"] = to_status
        payload["kind"] = "campaign_transition"
        if initial:
            payload["initial"] = True
        row = self.audit_log.append_event("decisions", payload)
        self.state.last_decision_id = decision_id
        self.state.last_event_hash = row.event_hash

        # KG: Decision node + ROUTED_TO edge from prior decision (if any).
        self.kg.add_node(
            node_id=decision_id,
            node_type=KGNodeType.Decision,
            properties={
                "from_status": from_status,
                "to_status": to_status,
                "context": context,
                "kind": "campaign_transition",
            },
            run_id=self.state.spec.campaign_id,
        )
        self.kg.add_edge(
            edge_id=f"edge:{self.state.spec.campaign_id}->{decision_id}",
            src_id=self.state.spec.campaign_id,
            dst_id=decision_id,
            edge_type=KGEdgeType.ROUTED_TO,
            run_id=self.state.spec.campaign_id,
        )
        return decision

    def _record_candidate_decision(
        self,
        candidate_id: str,
        from_status: CandidateStatus,
        to_status: CandidateStatus,
        rationale: str,
        rejection_reason: str | None,
        higher_fidelity_request: str | None,
        decision_maker: DecisionMaker = "policy",
    ) -> Decision:
        decision_id = f"decision:{self.state.spec.campaign_id}:cand:{uuid.uuid4().hex[:8]}"
        decision = Decision(
            decision_id=decision_id,
            made_by=decision_maker,
            context=f"candidate {candidate_id} {from_status} -> {to_status}",
            options_considered=[from_status, to_status],
            chosen=to_status,
            rationale=rationale,
            supersedes=[self.state.last_decision_id] if self.state.last_decision_id else [],
        )
        payload = decision.model_dump(mode="json")
        payload["scope_campaign_id"] = self.state.spec.campaign_id
        payload["candidate_id"] = candidate_id
        payload["from_status"] = from_status
        payload["to_status"] = to_status
        payload["rejection_reason"] = rejection_reason
        payload["higher_fidelity_request"] = higher_fidelity_request
        payload["kind"] = "candidate_transition"
        row = self.audit_log.append_event("decisions", payload)
        self.state.last_decision_id = decision_id
        self.state.last_event_hash = row.event_hash
        # KG: Decision node + ROUTED_TO edge from candidate.
        self.kg.add_node(
            node_id=decision_id,
            node_type=KGNodeType.Decision,
            properties={
                "from_status": from_status,
                "to_status": to_status,
                "candidate_id": candidate_id,
                "kind": "candidate_transition",
            },
            run_id=self.state.spec.campaign_id,
        )
        self.kg.add_edge(
            edge_id=f"edge:{candidate_id}->{decision_id}",
            src_id=candidate_id,
            dst_id=decision_id,
            edge_type=KGEdgeType.ROUTED_TO,
            run_id=self.state.spec.campaign_id,
        )
        return decision

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    @property
    def campaign_id(self) -> str:
        return self.state.spec.campaign_id

    @property
    def status(self) -> CampaignStatus:
        return self.state.status

    def candidate(self, candidate_id: str) -> CandidateRecord:
        if candidate_id not in self.state.candidates:
            raise KeyError(f"unknown candidate {candidate_id!r}")
        return self.state.candidates[candidate_id]

    def candidates(self) -> list[CandidateRecord]:
        return list(self.state.candidates.values())

    def rejected_set(self) -> set[str]:
        return set(self.state.rejected_candidate_ids)

    def rejected_hash_set(self) -> set[str]:
        return set(self.state.rejected_structure_hashes)
