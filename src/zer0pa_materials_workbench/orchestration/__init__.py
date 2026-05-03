"""L7 orchestration: campaign engine, state machine, BoTorch loop, gates.

Public surface:

* :class:`Campaign` — central orchestration object with state machine.
* :class:`CandidateState` — per-candidate state machine.
* :class:`AcceptanceGate` — unified gate composition (audit-provenance,
  cross-layer disagreement, rights/reuse-scope, duplicate-rejection,
  layer-specific falsifiers).
* :class:`SelfBootstrappingReasoner` — Bayesian update over reasoner-tuple
  history.
* :class:`CrossLayerDisagreementAggregator` — universal-disagreement primitive
  that merges per-layer disagreement metrics into a single score.

The orchestration package is the **only** place that may write Decisions,
Hypothesis nodes, AcceptanceGate verdicts, and Campaign nodes to the audit
log + KG. Adapters emit envelopes; orchestration interprets and routes.
"""

from zer0pa_materials_workbench.orchestration.acceptance_gates import (
    AcceptanceGate,
    AcceptanceGateVerdict,
    GateContext,
    GateName,
    PromotionFailureReason,
)
from zer0pa_materials_workbench.orchestration.campaign import (
    Campaign,
    CampaignSpec,
    CampaignState,
    CampaignStatus,
)
from zer0pa_materials_workbench.orchestration.candidate_state import (
    CandidateRecord,
    CandidateStatus,
)
from zer0pa_materials_workbench.orchestration.disagreement_aggregator import (
    AggregateDisagreement,
    CrossLayerDisagreementAggregator,
    LayerDisagreementInput,
)
from zer0pa_materials_workbench.orchestration.self_bootstrapping import (
    BayesianActionPosterior,
    SelfBootstrappingReasoner,
)

__all__ = [
    # campaign
    "Campaign",
    "CampaignSpec",
    "CampaignState",
    "CampaignStatus",
    # candidate
    "CandidateRecord",
    "CandidateStatus",
    # gates
    "AcceptanceGate",
    "AcceptanceGateVerdict",
    "GateContext",
    "GateName",
    "PromotionFailureReason",
    # disagreement
    "CrossLayerDisagreementAggregator",
    "LayerDisagreementInput",
    "AggregateDisagreement",
    # reasoner
    "SelfBootstrappingReasoner",
    "BayesianActionPosterior",
]
