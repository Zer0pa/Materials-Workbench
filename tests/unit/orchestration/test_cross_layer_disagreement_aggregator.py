"""Test the CrossLayerDisagreementAggregator (universal disagreement primitive)."""

from __future__ import annotations

import pytest

from zer0pa_materials.orchestration.disagreement_aggregator import (
    DEFAULT_NORMALISERS,
    AggregateDisagreement,
    CrossLayerDisagreementAggregator,
    LayerDisagreementInput,
)


def _input(layer: str, raw_value: float, unit: str = "x") -> LayerDisagreementInput:
    return LayerDisagreementInput(
        layer=layer,  # type: ignore[arg-type]
        raw_value=raw_value,
        unit=unit,
        layer_audit_ref=f"audit:test:{layer}",
    )


def test_no_inputs_zero_score():
    agg = CrossLayerDisagreementAggregator()
    out = agg.aggregate([])
    assert out.aggregate_score == 0.0
    assert out.layers_contributing == []


def test_normalisation_clips_to_unit_interval():
    agg = CrossLayerDisagreementAggregator()
    # L1 saturation is 50 meV/atom; pass 100 → clip to 1.0.
    n = agg.normalise("L1", 100.0)
    assert n == 1.0


def test_aggregate_score_in_unit_interval():
    agg = CrossLayerDisagreementAggregator()
    inputs = [
        _input("L1", 25.0, "meV/atom"),
        _input("L2", 30.0, "meV/atom"),
        _input("ionic", 0.3, "log10(D)"),
    ]
    out = agg.aggregate(inputs)
    assert 0.0 <= out.aggregate_score <= 1.0


def test_5_layer_aggregate_well_defined():
    """Synthetic disagreement metrics from 5 layers; aggregate is well-defined."""
    agg = CrossLayerDisagreementAggregator()
    inputs = [
        _input("L1", 10.0, "meV/atom"),
        _input("L2", 15.0, "meV/atom"),
        _input("L1.5", 0.2, "tau"),
        _input("L3", 0.1, "Jaccard"),
        _input("ionic", 0.2, "dex"),
    ]
    out = agg.aggregate(inputs)
    assert 0.0 <= out.aggregate_score <= 1.0
    assert set(out.layers_contributing) == {"L1", "L2", "L1.5", "L3", "ionic"}


def test_per_layer_audit_refs_traceable():
    agg = CrossLayerDisagreementAggregator()
    inputs = [_input("L1", 5.0), _input("L2", 10.0)]
    out = agg.aggregate(inputs)
    assert out.per_layer_audit_refs["L1"] == "audit:test:L1"
    assert out.per_layer_audit_refs["L2"] == "audit:test:L2"


def test_higher_disagreement_yields_higher_score():
    agg = CrossLayerDisagreementAggregator()
    low = agg.aggregate([_input("L1", 5.0), _input("L2", 5.0)])
    high = agg.aggregate([_input("L1", 50.0), _input("L2", 75.0)])
    assert high.aggregate_score > low.aggregate_score


def test_default_normalisers_match_prd_thresholds():
    """The PRD-aligned thresholds are baked into the defaults."""
    assert DEFAULT_NORMALISERS["L1"] == 50.0
    assert DEFAULT_NORMALISERS["L2"] == 75.0
    assert DEFAULT_NORMALISERS["ionic"] == 0.5
    assert DEFAULT_NORMALISERS["L4"] == 0.10
    assert DEFAULT_NORMALISERS["L5"] == 0.02
