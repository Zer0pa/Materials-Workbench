"""Cross-layer disagreement aggregation (PRD §Disagreement gates / synthesis).

Per ``synthesis/01-fresh-eyes-on-materials-briefs.md`` §"BoTorch ↔ active
inference equivalence is exact, not analogical": disagreement across
layers is the universal-uncertainty primitive. Every layer that runs at
least two methods produces a per-layer disagreement metric:

    L1 (cross-code DFT)            functional/code disagreement (meV/atom)
    L2 (DPA vs MACE ensemble)      energy/force disagreement (meV/atom, eV/Å)
    L1.5 (BoltzTraP2 vs AMSET)     ZT rank-stability tau-Kendall on top-N
    L3 (ESPEI vs Thermo-Calc)      phase-set Jaccard, fraction JS divergence
    L4 (PRISMS-PF vs MOOSE)        QoI mismatch percentile
    ionic (MLIP-MD vs AIMD)        diffusion log-dex disagreement
    L5 (FEniCSx vs deal.II)        strain-energy %

This module normalises each metric into [0, 1] (1 = maximum disagreement)
and aggregates with a weighted L2-norm to produce
:class:`AggregateDisagreement`. The L2 norm is chosen because it gives a
natural "credible interval radius" interpretation: the joint disagreement
is the Euclidean distance from "all methods perfectly agree" in the
normalised metric space.

The aggregator's output feeds:
  * BoTorch acquisition as a UQ signal (high disagreement → request
    higher-fidelity sample / posterior-variance preferred candidate)
  * AcceptanceGate's disagreement gate (rejects promotion if aggregate
    score > threshold)
  * KG ``DisagreementMetric`` nodes (one per layer, plus an aggregate node)
"""

from __future__ import annotations

import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "DEFAULT_LAYER_WEIGHTS",
    "DEFAULT_NORMALISERS",
    "AggregateDisagreement",
    "CrossLayerDisagreementAggregator",
    "LayerDisagreementInput",
]


LayerName = Literal["L1", "L2", "L1.5", "L3", "L4", "L5", "ionic"]


class LayerDisagreementInput(BaseModel):
    """One layer's disagreement contribution.

    The ``raw_value`` is in the layer's natural unit. The aggregator
    normalises it via the layer's normaliser. The ``layer_audit_ref`` is the
    audit_record_id of the envelope that produced the disagreement metric;
    this is what the falsifier ``cross_layer_disagreement_attribution``
    consumes to verify back-traceability.
    """

    model_config = ConfigDict(extra="forbid")

    layer: LayerName
    raw_value: float = Field(..., ge=0.0, description="Native-unit disagreement value (>= 0).")
    unit: str = Field(..., min_length=1, description="Native unit, e.g. 'meV/atom', 'log10(D)', 'fraction'.")
    layer_audit_ref: str = Field(
        ...,
        description="audit_record_id of the envelope that computed this disagreement.",
    )


# Default normaliser table.
# Each entry maps a layer to (saturation_value_in_native_units): values
# >= saturation map to 1.0; smaller values scale linearly to [0, 1).
# Saturation values are PRD-aligned thresholds.
DEFAULT_NORMALISERS: dict[LayerName, float] = {
    "L1": 50.0,        # 50 meV/atom — PRD §L1 screening threshold
    "L2": 75.0,        # 75 meV/atom — PRD §L2 hard-reject threshold
    "L1.5": 1.0,       # 1.0 = full rank inversion (tau-Kendall = -1 → distance 1)
    "L3": 1.0,         # Jaccard already in [0, 1]
    "L4": 0.10,        # PRD §L4: 10% relative QoI error threshold
    "L5": 0.02,        # PRD §L5: 2% strain-energy disagreement threshold
    "ionic": 0.5,      # 0.5 dex (factor of ~3) — PRD §Ionic Transport
}


# Default layer weights for the L2 norm. Sum is not required to be 1; the
# aggregator divides by sum-of-weights so the result is in [0, 1].
DEFAULT_LAYER_WEIGHTS: dict[LayerName, float] = {
    "L1": 1.0,
    "L2": 1.0,
    "L1.5": 1.0,
    "L3": 1.0,
    "L4": 1.0,
    "L5": 1.0,
    "ionic": 1.0,
}


class AggregateDisagreement(BaseModel):
    """The aggregator's output.

    ``aggregate_score`` is the weighted L2 norm of normalised per-layer
    disagreements, divided by sum of weights. Always in [0, 1].
    """

    model_config = ConfigDict(extra="forbid")

    aggregate_score: float = Field(..., ge=0.0, le=1.0)
    per_layer_normalised: dict[str, float] = Field(default_factory=dict)
    per_layer_audit_refs: dict[str, str] = Field(default_factory=dict)
    layers_contributing: list[str] = Field(default_factory=list)


class CrossLayerDisagreementAggregator:
    """Aggregate per-layer disagreement metrics into a single score.

    The aggregator is stateless; you pass it a list of
    :class:`LayerDisagreementInput` and it returns the aggregate.

    Example::

        agg = CrossLayerDisagreementAggregator()
        result = agg.aggregate([
            LayerDisagreementInput(layer="L1", raw_value=12.0, unit="meV/atom",
                                   layer_audit_ref="audit:x"),
            LayerDisagreementInput(layer="L2", raw_value=18.0, unit="meV/atom",
                                   layer_audit_ref="audit:y"),
        ])
        assert 0.0 <= result.aggregate_score <= 1.0
    """

    def __init__(
        self,
        normalisers: dict[LayerName, float] | None = None,
        weights: dict[LayerName, float] | None = None,
    ) -> None:
        self.normalisers: dict[LayerName, float] = dict(normalisers or DEFAULT_NORMALISERS)
        self.weights: dict[LayerName, float] = dict(weights or DEFAULT_LAYER_WEIGHTS)

    def normalise(self, layer: LayerName, raw_value: float) -> float:
        """Map a layer's native disagreement value to [0, 1]."""
        sat = self.normalisers.get(layer, 1.0)
        if sat <= 0.0:
            return 1.0 if raw_value > 0.0 else 0.0
        return max(0.0, min(1.0, raw_value / sat))

    def aggregate(self, inputs: list[LayerDisagreementInput]) -> AggregateDisagreement:
        if not inputs:
            return AggregateDisagreement(
                aggregate_score=0.0,
                per_layer_normalised={},
                per_layer_audit_refs={},
                layers_contributing=[],
            )
        per_layer_norm: dict[str, float] = {}
        per_layer_refs: dict[str, str] = {}
        weighted_sq_sum = 0.0
        weight_sq_sum = 0.0
        for inp in inputs:
            n = self.normalise(inp.layer, inp.raw_value)
            w = self.weights.get(inp.layer, 1.0)
            per_layer_norm[inp.layer] = n
            per_layer_refs[inp.layer] = inp.layer_audit_ref
            weighted_sq_sum += (w * n) ** 2
            weight_sq_sum += w * w
        if weight_sq_sum == 0.0:
            score = 0.0
        else:
            score = math.sqrt(weighted_sq_sum / weight_sq_sum)
        # Clamp for floating-point safety.
        score = max(0.0, min(1.0, score))
        return AggregateDisagreement(
            aggregate_score=score,
            per_layer_normalised=per_layer_norm,
            per_layer_audit_refs=per_layer_refs,
            layers_contributing=sorted(per_layer_norm.keys()),
        )
