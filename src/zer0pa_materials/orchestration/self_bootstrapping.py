"""Self-bootstrapping reasoner: Bayesian update over reasoner-tuple history.

Per PRD §Self-Bootstrapping Reasoner:

    Every campaign emits tuples (input, action, output, falsifier,
    ground_truth, decision); the reasoner consumes them to update its
    prior over proposed_action selection.

This implementation is intentionally lightweight: a Dirichlet-Categorical
conjugate update on the discrete action space. No PyTorch dependency.
The data model:

    p(action | context) ~ Categorical(theta)
    theta ~ Dirichlet(alpha)

where ``alpha`` is the count vector. Each observed tuple with decision in
{promote, queue_higher_fidelity} contributes a "good" count to the
proposed_action; ``reject`` and ``hold`` contribute to a "bad" mass that
implicitly down-weights the action via additive smoothing.

Reuse-scope discipline: the learner respects ``tup.reuse_scope``. Tuples
at ``tenant_only`` are tenant-isolated; the learner exposes a per-tenant
posterior so you cannot leak a tenant's signal into another tenant's prior.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Iterable, Mapping

from pydantic import BaseModel, ConfigDict, Field

from zer0pa_materials.audit.rights import ReuseScope
from zer0pa_materials.reasoner.tuples import ProposedAction, ReasonerTuple

__all__ = [
    "BayesianActionPosterior",
    "SelfBootstrappingReasoner",
    "ALL_ACTIONS",
]


# All possible proposed actions (matches the Literal in reasoner.tuples).
ALL_ACTIONS: tuple[ProposedAction, ...] = (
    "run_l2",
    "run_dft",
    "run_neb",
    "run_md",
    "run_aimd",
    "fit_calphad",
    "compile_protocol",
    "reject",
    "queue_higher_fidelity",
    "promote",
    "hold",
)


# Decisions that count as "successful" for the purpose of upweighting an action.
_GOOD_DECISIONS = {"promote", "queue_higher_fidelity"}
# Decisions that count as failures.
_BAD_DECISIONS = {"reject"}
# 'hold' contributes to neither side.


class BayesianActionPosterior(BaseModel):
    """Posterior over proposed_action under a (tenant, scope) key."""

    model_config = ConfigDict(extra="forbid")

    counts: dict[str, float] = Field(
        default_factory=lambda: {a: 1.0 for a in ALL_ACTIONS},
        description="Dirichlet-Categorical alpha counts (additive smoothing prior = 1.0).",
    )
    n_observations: int = Field(default=0, ge=0)

    def probabilities(self) -> dict[str, float]:
        """Return the posterior mean (normalised counts)."""
        total = sum(self.counts.values())
        if total <= 0.0:
            n = len(self.counts)
            return {a: 1.0 / n for a in self.counts}
        return {a: c / total for a, c in self.counts.items()}

    def best_action(self) -> str:
        """Return the action with maximum posterior mass."""
        probs = self.probabilities()
        return max(probs, key=lambda a: probs[a])


class SelfBootstrappingReasoner:
    """Update a per-tenant posterior over proposed_action from reasoner-tuple history.

    Construction defaults to a single global posterior. Pass
    ``per_tenant=True`` to track a posterior keyed by ``(tenant, reuse_scope)``
    pairs. Tenant inference: we read the tenant from the candidate URN
    when the tuple's ``input`` contains ``candidate_id`` of the form
    ``candidate:<tenant>/<rest>``; if the URN is not parseable, the tenant
    is ``"unknown"``.
    """

    def __init__(self, per_tenant: bool = True) -> None:
        self.per_tenant = per_tenant
        self._posteriors: dict[tuple[str, str], BayesianActionPosterior] = defaultdict(
            BayesianActionPosterior
        )

    @staticmethod
    def _tenant_for(tup: ReasonerTuple) -> str:
        cid = tup.candidate_id
        # candidate:<tenant>/<rest>
        if cid.startswith("candidate:") and "/" in cid:
            return cid[len("candidate:") :].split("/", 1)[0]
        return "unknown"

    def _key(self, tup: ReasonerTuple) -> tuple[str, str]:
        if not self.per_tenant:
            return ("global", "all")
        return (self._tenant_for(tup), tup.reuse_scope)

    def update(self, tup: ReasonerTuple) -> None:
        """Apply one observation to the appropriate posterior."""
        key = self._key(tup)
        post = self._posteriors[key]
        if tup.decision in _GOOD_DECISIONS:
            post.counts[tup.proposed_action] = post.counts.get(tup.proposed_action, 1.0) + 1.0
        elif tup.decision in _BAD_DECISIONS:
            # Down-weight by upweighting the "reject" bucket; this preserves
            # probability mass conservation under the Dirichlet posterior.
            post.counts["reject"] = post.counts.get("reject", 1.0) + 1.0
        post.n_observations += 1

    def update_many(self, tuples: Iterable[ReasonerTuple]) -> None:
        for t in tuples:
            self.update(t)

    def posterior_for(
        self,
        tenant: str = "global",
        scope: ReuseScope = "tenant_only",
    ) -> BayesianActionPosterior:
        """Return a copy of the posterior for ``(tenant, scope)``.

        Tenants without observations get the prior (uniform over actions).
        """
        if not self.per_tenant:
            key = ("global", "all")
        else:
            key = (tenant, scope)
        post = self._posteriors.get(key)
        if post is None:
            return BayesianActionPosterior()
        return BayesianActionPosterior(
            counts=dict(post.counts),
            n_observations=post.n_observations,
        )

    def best_action_for(
        self,
        tenant: str = "global",
        scope: ReuseScope = "tenant_only",
    ) -> str:
        return self.posterior_for(tenant, scope).best_action()

    def all_keys(self) -> list[tuple[str, str]]:
        return sorted(self._posteriors.keys())
