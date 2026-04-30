"""Test the SelfBootstrappingReasoner Bayesian update."""

from __future__ import annotations

import pytest

from zer0pa_materials.orchestration.self_bootstrapping import (
    ALL_ACTIONS,
    BayesianActionPosterior,
    SelfBootstrappingReasoner,
)
from zer0pa_materials.reasoner.tuples import ReasonerTuple


def _tuple(
    action: str,
    decision: str,
    tenant: str = "test",
    scope: str = "tenant_only",
    suffix: str = "1",
) -> ReasonerTuple:
    return ReasonerTuple(
        tuple_id=f"tuple:test/{suffix}",
        campaign_id=f"campaign:{tenant}/c1",
        candidate_id=f"candidate:{tenant}/c1",
        input={"prop": 1.0},
        proposed_action=action,  # type: ignore[arg-type]
        simulation_or_experiment={"layer": "L2"},
        output={"pred": 1.0},
        falsifier={"name": "x", "status": "pass"},
        decision=decision,  # type: ignore[arg-type]
        audit_ref="sha256:" + "0" * 64,
        reuse_scope=scope,  # type: ignore[arg-type]
    )


def test_uniform_posterior_with_no_observations():
    r = SelfBootstrappingReasoner(per_tenant=False)
    p = r.posterior_for("global", "tenant_only")
    probs = p.probabilities()
    assert pytest.approx(sum(probs.values()), abs=1e-6) == 1.0
    # All entries equal under uniform prior.
    assert len(set(round(v, 6) for v in probs.values())) == 1


def test_promotion_upweights_action():
    r = SelfBootstrappingReasoner(per_tenant=False)
    # Five run_l2-then-promote tuples → run_l2 should dominate.
    for i in range(5):
        r.update(_tuple("run_l2", "promote", suffix=str(i)))
    best = r.best_action_for("global", "tenant_only")
    assert best == "run_l2"


def test_per_tenant_isolation():
    r = SelfBootstrappingReasoner(per_tenant=True)
    for i in range(5):
        r.update(_tuple("run_l2", "promote", tenant="tenantA", suffix=str(i)))
    for i in range(5):
        r.update(_tuple("run_dft", "promote", tenant="tenantB", suffix=f"b{i}"))
    assert r.best_action_for("tenantA", "tenant_only") == "run_l2"
    assert r.best_action_for("tenantB", "tenant_only") == "run_dft"


def test_reject_decision_increments_reject_bucket():
    r = SelfBootstrappingReasoner(per_tenant=False)
    for i in range(5):
        r.update(_tuple("run_l2", "reject", suffix=str(i)))
    p = r.posterior_for("global", "tenant_only")
    # The reject bucket has accumulated mass.
    assert p.counts["reject"] > 1.0


def test_n_observations_counter_increments():
    r = SelfBootstrappingReasoner(per_tenant=False)
    r.update_many([_tuple("run_l2", "promote", suffix=str(i)) for i in range(7)])
    p = r.posterior_for("global", "tenant_only")
    assert p.n_observations == 7


def test_all_keys_listed():
    r = SelfBootstrappingReasoner(per_tenant=True)
    r.update(_tuple("run_l2", "promote", tenant="tenantA"))
    r.update(_tuple("run_l2", "promote", tenant="tenantB"))
    keys = r.all_keys()
    assert ("tenantA", "tenant_only") in keys
    assert ("tenantB", "tenant_only") in keys
