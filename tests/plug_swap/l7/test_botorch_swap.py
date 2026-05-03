"""Plug-swap test: BoTorch acquisition shapes invariant under qMFKG ↔ qLogEI."""

from __future__ import annotations

from zer0pa_materials_workbench.adapters.l7 import BoTorchAcquisitionAdapter
from zer0pa_materials_workbench.adapters.l7.botorch_acquisition import AcquisitionInput


def _ai(cid: str, fidelities: dict[str, float]) -> AcquisitionInput:
    return AcquisitionInput(
        candidate_id=cid,
        predicted_value=0.5,
        posterior_variance=0.05,
        fidelity_options=fidelities,
    )


def test_qmfkg_and_qlogei_emit_same_envelope_shape():
    adapter = BoTorchAcquisitionAdapter()
    # Multi-fidelity input → qMFKG.
    mf_inputs = [
        _ai("candidate:test/c1", {"L2_stub": 1.0, "L1_DFT_PBE": 10.0}),
        _ai("candidate:test/c2", {"L2_stub": 1.0, "L1_DFT_PBE": 10.0}),
    ]
    sf_inputs = [
        _ai("candidate:test/c1", {"L2_stub": 1.0}),
        _ai("candidate:test/c2", {"L2_stub": 1.0}),
    ]
    mf_result = adapter.acquire(mf_inputs)
    sf_result = adapter.acquire(sf_inputs)
    # Same envelope shape (same key set).
    assert set(mf_result.model_dump(mode="json").keys()) == set(sf_result.model_dump(mode="json").keys())
    # Same per-row shape.
    assert set(mf_result.ranked_candidates[0].model_dump(mode="json").keys()) == set(
        sf_result.ranked_candidates[0].model_dump(mode="json").keys()
    )


def test_acquisition_function_is_one_of_allowed_set():
    adapter = BoTorchAcquisitionAdapter()
    inputs = [_ai("candidate:test/c1", {"L2_stub": 1.0})]
    result = adapter.acquire(inputs)
    assert result.acquisition_function in (
        "qMultiFidelityKnowledgeGradient",
        "qLogExpectedImprovement",
    )
