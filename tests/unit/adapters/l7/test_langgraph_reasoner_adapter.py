"""Test the LangGraphReasonerAdapter — the hard architectural boundary lives here."""

from __future__ import annotations

from zer0pa_materials_workbench.adapters.l7 import LangGraphReasonerAdapter
from zer0pa_materials_workbench.adapters.l7.base import L7CampaignParams


def _params() -> L7CampaignParams:
    return L7CampaignParams(
        campaign_id="campaign:test/c1", candidate_id="candidate:test/c1"
    )


def test_reasoner_visits_every_node():
    state = LangGraphReasonerAdapter().step(_params())
    assert state.last_node == "decide"
    assert "select_hypothesis" in state.visited_nodes


def test_reasoner_proposes_run_l2_with_no_evidence():
    state = LangGraphReasonerAdapter().step(_params(), evidence={})
    assert state.proposed_action == "run_l2"
    assert state.fidelity_target == "L2_stub"


def test_reasoner_queues_higher_fidelity_on_high_disagreement():
    state = LangGraphReasonerAdapter().step(
        _params(), evidence={"aggregate_disagreement": 0.9}
    )
    assert state.proposed_action == "queue_higher_fidelity"


def test_reasoner_promotes_when_gates_pass_and_ionic_complete():
    state = LangGraphReasonerAdapter().step(
        _params(),
        evidence={"aggregate_disagreement": 0.1, "gates_pass": True, "ionic_complete": True},
    )
    assert state.proposed_action == "promote"


def test_envelope_carries_langgraph_is_not_audit_falsifier():
    env = LangGraphReasonerAdapter().execute(_params())
    items = {fi.name: fi for fi in env.falsifier.items}
    assert "l7.langgraph_is_not_audit" in items
    # Adapter does NOT write to audit; sentinel is False.
    assert items["l7.langgraph_is_not_audit"].actual["writes_to_audit"] is False
