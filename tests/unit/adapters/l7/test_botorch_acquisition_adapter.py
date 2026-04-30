"""Test the BoTorchAcquisitionAdapter — multi-fidelity routing + qEI guardrails."""

from __future__ import annotations

import pytest

from zer0pa_materials.adapters.l7 import BoTorchAcquisitionAdapter, ForbiddenAcquisitionError
from zer0pa_materials.adapters.l7.base import L7CampaignParams
from zer0pa_materials.adapters.l7.botorch_acquisition import AcquisitionInput


def _ai(cid: str, var: float = 0.05, fidelities: dict[str, float] | None = None) -> AcquisitionInput:
    return AcquisitionInput(
        candidate_id=cid,
        predicted_value=0.0,
        posterior_variance=var,
        fidelity_options=fidelities or {"L2_stub": 1.0},
    )


def test_qei_default_forbidden():
    adapter = BoTorchAcquisitionAdapter(allow_legacy_qei=False)
    with pytest.raises(ForbiddenAcquisitionError):
        adapter.select_acquisition(False, requested="qExpectedImprovement")


def test_qei_allowed_when_opt_in():
    adapter = BoTorchAcquisitionAdapter(allow_legacy_qei=True)
    acq = adapter.select_acquisition(False, requested="qExpectedImprovement")
    assert acq == "qExpectedImprovement"


def test_default_single_fidelity_is_qLogEI():
    adapter = BoTorchAcquisitionAdapter()
    acq = adapter.select_acquisition(is_multi_fidelity=False, requested=None)
    assert acq == "qLogExpectedImprovement"


def test_default_multi_fidelity_is_qMFKG():
    adapter = BoTorchAcquisitionAdapter()
    acq = adapter.select_acquisition(is_multi_fidelity=True, requested=None)
    assert acq == "qMultiFidelityKnowledgeGradient"


def test_acquire_routes_to_mf_when_two_fidelities():
    adapter = BoTorchAcquisitionAdapter()
    inputs = [
        _ai("candidate:test/c1", fidelities={"L2_stub": 1.0, "L1_DFT_PBE": 10.0}),
        _ai("candidate:test/c2", fidelities={"L2_stub": 1.0, "L1_DFT_PBE": 10.0}),
    ]
    result = adapter.acquire(inputs)
    assert result.is_multi_fidelity
    assert result.acquisition_function == "qMultiFidelityKnowledgeGradient"


def test_acquire_returns_ranked_candidates():
    adapter = BoTorchAcquisitionAdapter()
    inputs = [
        _ai("candidate:test/c1", var=0.1),
        _ai("candidate:test/c2", var=0.05),
        _ai("candidate:test/c3", var=0.01),
    ]
    result = adapter.acquire(inputs)
    assert len(result.ranked_candidates) == 3
    ranks = [r.rank for r in result.ranked_candidates]
    assert ranks == [0, 1, 2]


def test_higher_variance_prefers_cheaper_fidelity_under_kg():
    adapter = BoTorchAcquisitionAdapter()
    inputs = [_ai("candidate:test/c1", var=0.5, fidelities={"cheap": 1.0, "expensive": 10.0})]
    result = adapter.acquire(inputs)
    # When variance is high (>0.01), recommend cheap fidelity.
    if result.acquisition_function == "qMultiFidelityKnowledgeGradient":
        assert result.ranked_candidates[0].recommended_fidelity == "cheap"


def test_lower_variance_prefers_expensive_under_kg():
    adapter = BoTorchAcquisitionAdapter()
    inputs = [_ai("candidate:test/c1", var=0.001, fidelities={"cheap": 1.0, "expensive": 10.0})]
    result = adapter.acquire(inputs)
    if result.acquisition_function == "qMultiFidelityKnowledgeGradient":
        assert result.ranked_candidates[0].recommended_fidelity == "expensive"


def test_unit_envelope_emits_routing_falsifier():
    adapter = BoTorchAcquisitionAdapter()
    env = adapter.execute(L7CampaignParams(
        campaign_id="campaign:test/c1",
        candidate_id="candidate:test/c1",
        fidelity="L2_stub",
    ))
    items = {fi.name: fi for fi in env.falsifier.items}
    assert "l7.botorch_acquisition_function_allowed" in items
    assert "l7.botorch_multi_fidelity_routing" in items


def test_acquire_empty_list_raises():
    with pytest.raises(ValueError, match="non-empty"):
        BoTorchAcquisitionAdapter().acquire([])
