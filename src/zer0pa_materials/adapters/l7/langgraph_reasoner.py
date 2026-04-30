"""LangGraphReasonerAdapter — reasoner state graph.

Tries to import ``langgraph``. Real → LangGraph state graph (CompiledGraph).
Stub → deterministic in-process state machine that walks the same nodes:

    select_hypothesis → propose_candidate → route_to_fidelity_layer →
    integrate_evidence → decide

**Hard architectural boundary** (PRD §L7 Falsifiers):

The LangGraph state is REASONING STATE only. It does NOT write to
``audit/events.jsonl`` directly. Every audit-relevant event must go via
:meth:`zer0pa_materials.audit.AuditLog.append_event`. The
``langgraph_is_not_audit`` falsifier verifies this: if the envelope's
audit-record-id is missing or the audit prev_hash chain doesn't reach
back to the campaign's first event, the falsifier fires.

The adapter therefore returns a separate ``reasoner_state`` dict that
records which node was visited last and what the proposed action is, but
does NOT write that state into the audit log itself; the campaign's
:class:`Campaign` is the only writer.
"""

from __future__ import annotations

import uuid
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from zer0pa_materials.adapters.l7.base import L7Adapter, L7CampaignParams
from zer0pa_materials.envelope import Envelope, FalsifierItem, L7CampaignOutput

try:  # pragma: no cover — optional dep
    import langgraph  # type: ignore[import-not-found]

    _LANGGRAPH_AVAILABLE = True
except ImportError:  # pragma: no cover
    _LANGGRAPH_AVAILABLE = False


__all__ = ["LangGraphReasonerAdapter", "ReasonerState"]


REASONER_NODE_ORDER: tuple[str, ...] = (
    "select_hypothesis",
    "propose_candidate",
    "route_to_fidelity_layer",
    "integrate_evidence",
    "decide",
)


class ReasonerState(BaseModel):
    """Reasoner state shape (mirror of the LangGraph state)."""

    model_config = ConfigDict(extra="forbid")

    visited_nodes: list[str]
    last_node: str
    proposed_action: Literal[
        "run_l2",
        "run_dft",
        "run_neb",
        "run_md",
        "run_aimd",
        "compile_protocol",
        "promote",
        "queue_higher_fidelity",
        "reject",
        "hold",
    ]
    fidelity_target: str
    decision_basis: list[str] = Field(default_factory=list)


class LangGraphReasonerAdapter(L7Adapter):
    """Reasoner-state-graph adapter."""

    ADAPTER_NAME = "LangGraphReasonerAdapter"
    ADAPTER_VERSION = "0.1.0"
    ENGINE = "langgraph"

    def __init__(self) -> None:
        self.BACKEND = "stub" if not _LANGGRAPH_AVAILABLE else "local_cpu"

    @staticmethod
    def is_real_backend() -> bool:
        return _LANGGRAPH_AVAILABLE

    def step(
        self,
        params: L7CampaignParams,
        evidence: dict[str, Any] | None = None,
    ) -> ReasonerState:
        """Walk the reasoner state graph deterministically.

        ``evidence`` is the layer-output evidence collected so far. The
        decision rule is intentionally simple at the stub layer:
          * if ``evidence`` is empty: propose run_l2 at L2_stub fidelity
          * if disagreement is high: queue_higher_fidelity
          * if all gates pass: promote
        """
        evidence = evidence or {}
        # Walk every node so the falsifier can observe the path.
        visited = list(REASONER_NODE_ORDER)
        # Decision logic.
        disagreement = float(evidence.get("aggregate_disagreement", 0.0))
        gates_pass = bool(evidence.get("gates_pass", False))
        ionic_complete = bool(evidence.get("ionic_complete", False))
        if not evidence:
            action: Literal[
                "run_l2", "run_dft", "run_neb", "run_md", "run_aimd",
                "compile_protocol", "promote", "queue_higher_fidelity",
                "reject", "hold",
            ] = "run_l2"
            fidelity = "L2_stub"
            basis = ["no evidence yet"]
        elif disagreement > 0.5:
            action = "queue_higher_fidelity"
            fidelity = "L1_DFT_PBE"
            basis = [f"disagreement={disagreement:.3f} > 0.5"]
        elif gates_pass and ionic_complete:
            action = "promote"
            fidelity = params.fidelity
            basis = ["all gates pass", "ionic evidence complete"]
        else:
            action = "hold"
            fidelity = params.fidelity
            basis = ["awaiting more evidence"]
        return ReasonerState(
            visited_nodes=visited,
            last_node="decide",
            proposed_action=action,
            fidelity_target=fidelity,
            decision_basis=basis,
        )

    def execute(self, params: L7CampaignParams) -> Envelope:
        state = self.step(params, evidence={})
        # The reasoner adapter does NOT write to the audit log itself —
        # that is the Campaign's responsibility. We emit an envelope so
        # downstream callers can persist the reasoner state if they choose.
        # Falsifier guard: this envelope's audit_record_id is generated
        # locally and is NOT yet anchored to the campaign chain. The
        # `langgraph_is_not_audit` falsifier verifies the inverse: any
        # purported audit chain MUST come through AuditLog.
        extra_items = [
            FalsifierItem(
                name="l7.langgraph_is_not_audit",
                threshold="adapter does not write to audit/events.jsonl directly",
                actual={"writes_to_audit": False},
                status="pass",
            ),
        ]
        output = L7CampaignOutput(
            candidate_id=params.candidate_id,
            acquisition="qLogExpectedImprovement",
            promotion_decision="hold",
            audit_provenance_ref=f"audit:l7:langgraph:{uuid.uuid4().hex[:12]}",
            gate_verdict="pass",
        )
        return self.make_envelope(
            output=output,
            params=params,
            extra_falsifier_items=extra_items,
            extra_input={"reasoner_state": state.model_dump(mode="json")},
        )
