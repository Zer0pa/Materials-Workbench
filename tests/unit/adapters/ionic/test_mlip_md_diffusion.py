"""Unit tests for the MlipMdDiffusionAdapter."""

from __future__ import annotations

import pytest

from zer0pa_materials_workbench.adapters.ionic.base import (
    IONIC_TRANSPORT_SERVICE_REF,
    IonicJobParams,
)
from zer0pa_materials_workbench.adapters.ionic.mlip_md import (
    MLIP_MD_BLOCKED_MANIFEST,
    MlipMdDiffusionAdapter,
    fit_diffusion_blocks,
    synthetic_msd_trace,
)


@pytest.fixture
def llzo_params() -> IonicJobParams:
    return IonicJobParams(
        structure_hash="sha256:d45cb2bfe5e76b86b365e1402e118ed32280049a62345c903558c6cfac04ef19",
        fixture_id="fixture:LLZO_cubic:d45cb2bf",
        candidate_id="candidate:LLZO/cubic",
    )


def test_synthetic_msd_trace_increasing(llzo_params: IonicJobParams) -> None:
    times, msd = synthetic_msd_trace(
        llzo_params.structure_hash,
        llzo_params.fixture_id,
        n_steps=200,
        dt_ps=0.01,
    )
    assert len(times) == len(msd) == 200
    # Trend is increasing on average; allow per-step jitter.
    assert msd[-1] > msd[0]
    # Times are monotonically increasing.
    for i in range(1, len(times)):
        assert times[i] > times[i - 1]


def test_fit_diffusion_blocks_recovers_D_close_to_anchor(
    llzo_params: IonicJobParams,
) -> None:
    times, msd = synthetic_msd_trace(
        llzo_params.structure_hash,
        llzo_params.fixture_id,
        n_steps=500,
        dt_ps=0.02,
    )
    block = fit_diffusion_blocks(times, msd, n_blocks=4)
    # LLZO anchor: 1e-7 cm²/s; allow 30% tolerance (block jitter).
    assert 0.7e-7 <= block.D_mean_cm2_per_s <= 1.5e-7
    # Uncertainty should be small but non-zero (blocks vary).
    assert block.D_uncertainty_dex >= 0.0


def test_fit_diffusion_blocks_uncertainty_dex_returns_real_value() -> None:
    """Block-stdev uncertainty must be a positive finite number."""
    times, msd = synthetic_msd_trace(
        "sha256:" + "a" * 64,
        "fixture:LLZO_cubic:d45cb2bf",
        n_steps=400,
        dt_ps=0.02,
    )
    block = fit_diffusion_blocks(times, msd, n_blocks=4)
    assert 0.0 <= block.D_uncertainty_dex < 2.0


def test_llzo_diffusion_clears_threshold(llzo_params: IonicJobParams) -> None:
    """LLZO MLIP-MD stub: D ~ 1e-7 -> sigma_NE ~ 1.24e-2 S/cm at 300 K -> clears 1e-3."""
    env = MlipMdDiffusionAdapter().compute(llzo_params)
    sigma = env.output["nernst_einstein_conductivity_S_per_cm"]
    assert sigma >= 1e-3


def test_envelope_layer_is_ionic(llzo_params: IonicJobParams) -> None:
    env = MlipMdDiffusionAdapter().compute(llzo_params)
    assert env.layer == "ionic"


def test_envelope_carries_service_ref(llzo_params: IonicJobParams) -> None:
    env = MlipMdDiffusionAdapter().compute(llzo_params)
    assert IONIC_TRANSPORT_SERVICE_REF in env.input_refs


def test_msd_returned_in_output(llzo_params: IonicJobParams) -> None:
    env = MlipMdDiffusionAdapter().compute(llzo_params)
    assert env.output["msd_A2"] > 0


def test_diffusion_returned_in_output(llzo_params: IonicJobParams) -> None:
    env = MlipMdDiffusionAdapter().compute(llzo_params)
    assert env.output["diffusion_coefficient_cm2_per_s"] > 0


def test_credible_interval_falsifier_present(llzo_params: IonicJobParams) -> None:
    env = MlipMdDiffusionAdapter().compute(llzo_params)
    item_names = [it.name for it in env.falsifier.items]
    assert "ionic.rt_conductivity_credible_interval" in item_names


def test_credible_interval_has_lo_hi_dex(llzo_params: IonicJobParams) -> None:
    env = MlipMdDiffusionAdapter().compute(llzo_params)
    for it in env.falsifier.items:
        if it.name == "ionic.rt_conductivity_credible_interval":
            assert "lo_S_per_cm" in it.actual
            assert "hi_S_per_cm" in it.actual
            assert "uncertainty_dex" in it.actual
            return
    raise AssertionError("CI falsifier item missing")


def test_unknown_fixture_below_threshold() -> None:
    """Novel structures default to low D so sigma_NE is below the 1e-3 gate."""
    p = IonicJobParams(
        structure_hash="sha256:" + "0" * 64,
        fixture_id=None,
        candidate_id="candidate:novel",
    )
    env = MlipMdDiffusionAdapter().compute(p)
    sigma = env.output["nernst_einstein_conductivity_S_per_cm"]
    # Default fallback D = 1e-9 cm²/s -> sigma ~ 1.24e-4 S/cm < 1e-3
    assert sigma < 1e-3


def test_blocked_source_manifest_exists() -> None:
    assert MLIP_MD_BLOCKED_MANIFEST.source_manifest_id == "src:blocked:mlip-md-real-backend"
    assert MLIP_MD_BLOCKED_MANIFEST.blocker_reason == "unavailable_credentials"


def test_haven_ratio_modifies_sigma(llzo_params: IonicJobParams) -> None:
    """Haven ratio > 1.0 lowers reported sigma."""
    p1 = llzo_params
    p2 = IonicJobParams(**{**p1.model_dump(), "haven_ratio": 2.0})
    env1 = MlipMdDiffusionAdapter().compute(p1)
    env2 = MlipMdDiffusionAdapter().compute(p2)
    assert env2.output["nernst_einstein_conductivity_S_per_cm"] == pytest.approx(
        env1.output["nernst_einstein_conductivity_S_per_cm"] / 2.0, rel=1e-9
    )


def test_method_seed_is_mlip(llzo_params: IonicJobParams) -> None:
    """The MLIP-MD adapter uses method_seed='mlip'."""
    assert MlipMdDiffusionAdapter.METHOD_SEED == "mlip"


def test_fit_blocks_rejects_short_traces() -> None:
    with pytest.raises(ValueError, match="at least"):
        fit_diffusion_blocks([0.0, 1.0], [0.0, 1.0], n_blocks=4)


def test_fit_blocks_rejects_mismatched_lengths() -> None:
    with pytest.raises(ValueError, match="same length"):
        fit_diffusion_blocks([0.0, 1.0, 2.0, 3.0], [0.0], n_blocks=2)
