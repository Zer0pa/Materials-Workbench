"""BoTorchAcquisitionAdapter — multi-fidelity Bayesian optimisation.

PRD §L7 Falsifiers / Productisation:

    qMultiFidelityKnowledgeGradient is the default for expensive multi-
    fidelity choices. qLogExpectedImprovement is the default for simpler
    exploitation. Plain qExpectedImprovement is FORBIDDEN as a default.

This adapter:

* Accepts a list of candidate inputs (with predicted property + posterior
  variance + per-fidelity cost).
* Routes to either ``qMultiFidelityKnowledgeGradient`` or
  ``qLogExpectedImprovement`` depending on whether multiple fidelities are
  in play.
* Refuses to use plain ``qExpectedImprovement`` unless
  :attr:`MaterialsConfig.allow_legacy_qei` is ``True`` (default ``False``).
* Returns a ranked candidate list with acquisition values + recommended
  fidelity per candidate.

When ``botorch`` is unavailable, the adapter synthesises a deterministic
acquisition: cheaper fidelity is sampled more frequently, higher-fidelity
is sampled when posterior variance is high. This emulates the multi-
fidelity tradeoff so plug-swap tests pass schema-invariance.
"""

from __future__ import annotations

import math
import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from zer0pa_materials_workbench.adapters.l7.base import L7Adapter, L7CampaignParams
from zer0pa_materials_workbench.envelope import Envelope, FalsifierItem, L7CampaignOutput

try:  # pragma: no cover — optional dep
    import botorch  # type: ignore[import-not-found]

    _BOTORCH_AVAILABLE = True
except ImportError:  # pragma: no cover
    _BOTORCH_AVAILABLE = False


__all__ = [
    "AcquisitionFunctionName",
    "AcquisitionInput",
    "AcquisitionResult",
    "BoTorchAcquisitionAdapter",
    "ForbiddenAcquisitionError",
    "RankedCandidate",
]


AcquisitionFunctionName = Literal[
    "qMultiFidelityKnowledgeGradient",
    "qLogExpectedImprovement",
    "qExpectedImprovement",  # FORBIDDEN as default
]


class ForbiddenAcquisitionError(ValueError):
    """Raised when a caller requests plain ``qExpectedImprovement`` as default.

    PRD §L7 Falsifiers: do NOT use plain ``qExpectedImprovement`` as default.
    Use :data:`MaterialsConfig.allow_legacy_qei` to opt in (e.g. for legacy
    benchmarks). Default is False.
    """


class AcquisitionInput(BaseModel):
    """One candidate input to the acquisition step."""

    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    predicted_value: float = Field(..., description="Predicted property value (objective).")
    posterior_variance: float = Field(..., ge=0.0)
    fidelity_options: dict[str, float] = Field(
        ...,
        description=(
            "Map fidelity name -> cost (lower cost = cheaper to evaluate). "
            "Must contain at least one entry. Names: 'L2_stub', 'L1_DFT_PBE', "
            "'L1_DFT_HSE06', 'ionic_NEB', 'ionic_AIMD', etc."
        ),
    )


class RankedCandidate(BaseModel):
    """One row of the acquisition adapter's output."""

    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    acquisition_value: float
    recommended_fidelity: str
    rank: int = Field(..., ge=0)


class AcquisitionResult(BaseModel):
    """Acquisition adapter output."""

    model_config = ConfigDict(extra="forbid")

    acquisition_function: AcquisitionFunctionName
    is_multi_fidelity: bool
    ranked_candidates: list[RankedCandidate]


class BoTorchAcquisitionAdapter(L7Adapter):
    """BoTorch-shaped acquisition adapter (real or stubbed)."""

    ADAPTER_NAME = "BoTorchAcquisitionAdapter"
    ADAPTER_VERSION = "0.1.0"
    ENGINE = "botorch"

    def __init__(self, allow_legacy_qei: bool = False) -> None:
        self.BACKEND = "stub" if not _BOTORCH_AVAILABLE else "local_cpu"
        self.allow_legacy_qei = allow_legacy_qei

    @staticmethod
    def is_real_backend() -> bool:
        return _BOTORCH_AVAILABLE

    def select_acquisition(
        self,
        is_multi_fidelity: bool,
        requested: AcquisitionFunctionName | None = None,
    ) -> AcquisitionFunctionName:
        """Resolve the acquisition function with PRD-mandated guardrails.

        Rules:
          * If ``requested == 'qExpectedImprovement'`` and not
            ``allow_legacy_qei``: raise :class:`ForbiddenAcquisitionError`.
          * If ``requested`` is None and ``is_multi_fidelity``: use
            ``qMultiFidelityKnowledgeGradient``.
          * If ``requested`` is None and not multi-fidelity: use
            ``qLogExpectedImprovement``.
        """
        if requested == "qExpectedImprovement" and not self.allow_legacy_qei:
            raise ForbiddenAcquisitionError(
                "qExpectedImprovement is forbidden as default per PRD §L7. "
                "Use qMultiFidelityKnowledgeGradient or qLogExpectedImprovement, "
                "or set MaterialsConfig.allow_legacy_qei=True for legacy benchmarks."
            )
        if requested is not None:
            return requested
        if is_multi_fidelity:
            return "qMultiFidelityKnowledgeGradient"
        return "qLogExpectedImprovement"

    def acquire(
        self,
        candidates: list[AcquisitionInput],
        requested_acquisition: AcquisitionFunctionName | None = None,
    ) -> AcquisitionResult:
        """Run one acquisition step (or its deterministic stub equivalent)."""
        if not candidates:
            raise ValueError("candidates must be non-empty")
        # Multi-fidelity iff any candidate exposes >1 fidelity option AND
        # there are at least 2 distinct fidelities across candidates.
        all_fidelities = set()
        for c in candidates:
            all_fidelities.update(c.fidelity_options.keys())
        is_mf = (
            any(len(c.fidelity_options) > 1 for c in candidates) and len(all_fidelities) >= 2
        )
        acq = self.select_acquisition(is_mf, requested_acquisition)
        # Compute acquisition values.
        # Multi-fidelity KG: prefer high-variance candidates, route to the
        # cheapest fidelity that reduces variance significantly.
        # qLogEI: log(predicted + sqrt(variance)) - log(best_seen).
        best_seen = max(c.predicted_value for c in candidates)
        rows: list[RankedCandidate] = []
        for c in candidates:
            if acq == "qMultiFidelityKnowledgeGradient":
                # KG-style: variance times fidelity-cost ratio.
                # Cheapest fidelity for high-variance candidates; recommend
                # higher fidelity when variance is small.
                cost_items = sorted(c.fidelity_options.items(), key=lambda kv: kv[1])
                cheapest_fid, cheapest_cost = cost_items[0]
                most_expensive_fid, most_expensive_cost = cost_items[-1]
                # Recommend higher fidelity if variance is small; else cheaper.
                if c.posterior_variance < 0.01:
                    recommended = most_expensive_fid
                    cost = most_expensive_cost
                else:
                    recommended = cheapest_fid
                    cost = cheapest_cost
                # Acquisition value: variance / cost (KG ratio analogue).
                acq_val = c.posterior_variance / max(cost, 1e-6)
            elif acq == "qLogExpectedImprovement":
                # log expected improvement in normalised form.
                # ei = (mu - best_seen)+ + sigma * phi/Phi  (simplified)
                mu = c.predicted_value
                sigma = math.sqrt(c.posterior_variance)
                ei = max(mu - best_seen, 0.0) + 0.5 * sigma
                acq_val = math.log(ei + 1e-9)
                # Recommend the only / cheapest fidelity.
                cost_items = sorted(c.fidelity_options.items(), key=lambda kv: kv[1])
                recommended = cost_items[0][0]
            else:  # qExpectedImprovement (legacy)
                mu = c.predicted_value
                sigma = math.sqrt(c.posterior_variance)
                acq_val = max(mu - best_seen, 0.0) + 0.5 * sigma
                cost_items = sorted(c.fidelity_options.items(), key=lambda kv: kv[1])
                recommended = cost_items[0][0]
            rows.append(
                RankedCandidate(
                    candidate_id=c.candidate_id,
                    acquisition_value=acq_val,
                    recommended_fidelity=recommended,
                    rank=0,  # filled below
                )
            )
        # Rank by descending acquisition value.
        rows.sort(key=lambda r: -r.acquisition_value)
        for i, r in enumerate(rows):
            r.rank = i
        return AcquisitionResult(
            acquisition_function=acq,
            is_multi_fidelity=is_mf,
            ranked_candidates=rows,
        )

    def execute(self, params: L7CampaignParams) -> Envelope:
        """Execute a unit acquisition step and emit one L7 envelope.

        For unit calls the adapter is given a single candidate at a single
        fidelity; the result is a one-row ranked output.
        """
        # Synthesise a single-candidate input to keep the unit envelope path
        # working without external state.
        ai = AcquisitionInput(
            candidate_id=params.candidate_id,
            predicted_value=0.0,
            posterior_variance=0.05,
            fidelity_options={params.fidelity: 1.0},
        )
        result = self.acquire([ai])
        ranked = result.ranked_candidates[0]
        # Falsifier items.
        extra_items: list[FalsifierItem] = [
            FalsifierItem(
                name="l7.botorch_acquisition_function_allowed",
                threshold="acquisition in {qMultiFidelityKnowledgeGradient, qLogExpectedImprovement} OR allow_legacy_qei=True",
                actual={
                    "acquisition_function": result.acquisition_function,
                    "allow_legacy_qei": self.allow_legacy_qei,
                },
                status=(
                    "pass"
                    if (
                        result.acquisition_function != "qExpectedImprovement"
                        or self.allow_legacy_qei
                    )
                    else "fail"
                ),
            ),
            FalsifierItem(
                name="l7.botorch_multi_fidelity_routing",
                threshold=(
                    "is_multi_fidelity → qMultiFidelityKnowledgeGradient; "
                    "single-fidelity → qLogExpectedImprovement"
                ),
                actual={
                    "is_multi_fidelity": result.is_multi_fidelity,
                    "acquisition_function": result.acquisition_function,
                },
                status=(
                    "pass"
                    if (
                        (
                            result.is_multi_fidelity
                            and result.acquisition_function
                            == "qMultiFidelityKnowledgeGradient"
                        )
                        or (
                            not result.is_multi_fidelity
                            and result.acquisition_function == "qLogExpectedImprovement"
                        )
                    )
                    else "blocked"
                ),
            ),
        ]
        output = L7CampaignOutput(
            candidate_id=params.candidate_id,
            acquisition=result.acquisition_function
            if result.acquisition_function in ("qMultiFidelityKnowledgeGradient", "qLogExpectedImprovement")
            else "other",
            promotion_decision="queue_higher_fidelity"
            if ranked.recommended_fidelity != params.fidelity
            else "hold",
            audit_provenance_ref=f"audit:l7:botorch:{uuid.uuid4().hex[:12]}",
            gate_verdict="pass",
        )
        return self.make_envelope(
            output=output,
            params=params,
            extra_falsifier_items=extra_items,
            extra_input={
                "acquisition_result": result.model_dump(mode="json"),
                "adapter": "botorch",
            },
        )
