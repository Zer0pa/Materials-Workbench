"""Test every L7 falsifier."""

from __future__ import annotations

from zer0pa_materials_workbench.adapters.l7 import (
    BoTorchAcquisitionAdapter,
    LangGraphReasonerAdapter,
    ParslFanoutAdapter,
    PrefectCampaignAdapter,
)
from zer0pa_materials_workbench.adapters.l7.base import L7CampaignParams
from zer0pa_materials_workbench.falsifiers.l7_falsifiers import (
    aiida_atomate2_provenance_complete,
    alabos_recipe_only_enforcement,
    botorch_acquisition_function_allowed,
    botorch_multi_fidelity_routing,
    candidate_promotion_provenance,
    cross_layer_disagreement_attribution,
    langgraph_is_not_audit,
    parsl_fanout_attribution,
    prefect_lifecycle_completeness,
    tenant_only_tuple_leak,
)


def _params() -> L7CampaignParams:
    return L7CampaignParams(campaign_id="campaign:test/c1", candidate_id="candidate:test/c1")


def test_langgraph_is_not_audit_pass():
    env = LangGraphReasonerAdapter().execute(_params())
    item = langgraph_is_not_audit(env, chain_event_hashes=None)
    assert item.status == "pass"


def test_langgraph_is_not_audit_fail_when_not_anchored():
    env = LangGraphReasonerAdapter().execute(_params())
    # Provide a non-empty chain that does not include the envelope's audit_record_id.
    item = langgraph_is_not_audit(env, chain_event_hashes={"audit:wrong"})
    assert item.status == "fail"


def test_prefect_lifecycle_completeness_pass():
    env = PrefectCampaignAdapter().execute(_params())
    item = prefect_lifecycle_completeness(env)
    assert item.status == "pass"


def test_parsl_fanout_attribution_pass():
    envs = ParslFanoutAdapter().fan_out(_params(), ["candidate:test/c1"], parent_audit_ref="audit:l7:parent")
    item = parsl_fanout_attribution(envs[0])
    assert item.status == "pass"


def test_parsl_fanout_attribution_fail_when_no_parent():
    envs = ParslFanoutAdapter().fan_out(_params(), ["candidate:test/c1"], parent_audit_ref=None)
    item = parsl_fanout_attribution(envs[0])
    assert item.status == "fail"


def test_aiida_atomate2_provenance_complete_pass():
    from zer0pa_materials_workbench.adapters.l7 import AiiDAProvenanceAdapter

    env = AiiDAProvenanceAdapter().execute(_params())
    item = aiida_atomate2_provenance_complete(env)
    assert item.status == "pass"


def test_botorch_acquisition_function_allowed_pass():
    env = BoTorchAcquisitionAdapter().execute(_params())
    item = botorch_acquisition_function_allowed(env, allow_legacy_qei=False)
    assert item.status == "pass"


def test_botorch_acquisition_function_allowed_fail_for_qei():
    """An envelope reporting acquisition='qExpectedImprovement' under no opt-in fails."""
    env_dict = {
        "research_boundary": "_irrelevant_",
        "audit": {"audit_record_id": "audit:test:x"},
        "output": {"acquisition": "qExpectedImprovement"},
        "falsifier": {"items": [{
            "name": "l7.botorch_acquisition_function_allowed",
            "actual": {"acquisition_function": "qExpectedImprovement", "allow_legacy_qei": False},
            "status": "fail",
            "threshold": "x",
        }]},
        "disagreement": {"metrics": []},
    }
    item = botorch_acquisition_function_allowed(env_dict, allow_legacy_qei=False)
    assert item.status == "fail"


def test_botorch_multi_fidelity_routing_pass():
    env = BoTorchAcquisitionAdapter().execute(_params())
    item = botorch_multi_fidelity_routing(env)
    # Single-fidelity unit envelope routes to qLogExpectedImprovement.
    assert item.status == "pass"


def test_alabos_recipe_only_enforcement_violation():
    payload = {
        "alabos_mode": "recipe_only",
        "hardware_executable": True,
        "synthesis_steps": [],
    }
    item = alabos_recipe_only_enforcement(payload)
    assert item.status == "fail"


def test_alabos_recipe_only_enforcement_pass_for_phase2():
    payload = {
        "alabos_mode": "phase2_hardware",
        "hardware_executable": True,
        "synthesis_steps": [],
    }
    item = alabos_recipe_only_enforcement(payload)
    assert item.status == "pass"


def test_alabos_recipe_only_enforcement_pass_for_recipe_no_hw():
    payload = {
        "alabos_mode": "recipe_only",
        "hardware_executable": False,
        "synthesis_steps": [],
    }
    item = alabos_recipe_only_enforcement(payload)
    assert item.status == "pass"


def test_candidate_promotion_provenance_pass():
    env = PrefectCampaignAdapter().execute(_params())
    # Wrap to override decision='promote'.
    env_dict = env.model_dump(mode="json")
    env_dict["output"]["promotion_decision"] = "promote"
    item = candidate_promotion_provenance(
        env_dict,
        rejected_candidate_ids=set(),
        rejected_structure_hashes=set(),
        expected_disagreement_present=True,
        rights_compatible=True,
    )
    assert item.status == "pass"


def test_candidate_promotion_provenance_fails_on_duplicate():
    env = PrefectCampaignAdapter().execute(_params())
    env_dict = env.model_dump(mode="json")
    env_dict["output"]["promotion_decision"] = "promote"
    item = candidate_promotion_provenance(
        env_dict,
        rejected_candidate_ids={env.candidate_id},
        expected_disagreement_present=True,
        rights_compatible=True,
    )
    assert item.status == "fail"
    assert "duplicate_of_rejected_candidate_id" in item.actual["failures"]


def test_candidate_promotion_provenance_fails_on_disagreement_bypass():
    env = PrefectCampaignAdapter().execute(_params())
    env_dict = env.model_dump(mode="json")
    env_dict["output"]["promotion_decision"] = "promote"
    item = candidate_promotion_provenance(
        env_dict,
        rejected_candidate_ids=set(),
        expected_disagreement_present=False,
        rights_compatible=True,
    )
    assert item.status == "fail"
    assert "disagreement_gate_bypassed" in item.actual["failures"]


def test_candidate_promotion_provenance_fails_on_rights_violation():
    env = PrefectCampaignAdapter().execute(_params())
    env_dict = env.model_dump(mode="json")
    env_dict["output"]["promotion_decision"] = "promote"
    item = candidate_promotion_provenance(
        env_dict,
        rejected_candidate_ids=set(),
        expected_disagreement_present=True,
        rights_compatible=False,
    )
    assert item.status == "fail"
    assert "reuse_scope_violation" in item.actual["failures"]


def test_tenant_only_tuple_leak_fires_on_shared_learning_bundle():
    bundle = {
        "export_bundle": "shared_learning",
        "tuples": [
            {"tuple_id": "tuple:t1", "reuse_scope": "tenant_only"},
        ],
    }
    item = tenant_only_tuple_leak(bundle)
    assert item.status == "fail"
    assert "tuple:t1" in item.actual["leaks"]


def test_tenant_only_tuple_leak_passes_when_compatible():
    bundle = {
        "export_bundle": "shared_learning",
        "tuples": [
            {"tuple_id": "tuple:t1", "reuse_scope": "shared_learning"},
            {"tuple_id": "tuple:t2", "reuse_scope": "open_science"},
        ],
    }
    item = tenant_only_tuple_leak(bundle)
    assert item.status == "pass"


def test_cross_layer_disagreement_attribution_blocked_with_no_metrics():
    env = PrefectCampaignAdapter().execute(_params())
    item = cross_layer_disagreement_attribution(env)
    assert item.status == "blocked"
