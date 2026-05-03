"""Unit tests for the AimdDiffusionAdapter."""

from __future__ import annotations

import math

import pytest

from zer0pa_materials_workbench.adapters.ionic.aimd import (
    AIMD_BLOCKED_MANIFEST,
    AimdDiffusionAdapter,
)
from zer0pa_materials_workbench.adapters.ionic.base import (
    IONIC_TRANSPORT_SERVICE_REF,
    IonicJobParams,
)
from zer0pa_materials_workbench.adapters.ionic.mlip_md import MlipMdDiffusionAdapter


@pytest.fixture
def llzo_params() -> IonicJobParams:
    return IonicJobParams(
        structure_hash="sha256:d45cb2bfe5e76b86b365e1402e118ed32280049a62345c903558c6cfac04ef19",
        fixture_id="fixture:LLZO_cubic:d45cb2bf",
        candidate_id="candidate:LLZO/cubic",
    )


def test_aimd_runs(llzo_params: IonicJobParams) -> None:
    env = AimdDiffusionAdapter().compute(llzo_params)
    assert env.output["diffusion_coefficient_cm2_per_s"] > 0


def test_aimd_method_seed_differs_from_mlip() -> None:
    assert AimdDiffusionAdapter.METHOD_SEED == "aimd"
    assert AimdDiffusionAdapter.METHOD_SEED != MlipMdDiffusionAdapter.METHOD_SEED


def test_aimd_lower_than_mlip_by_about_8pct(llzo_params: IonicJobParams) -> None:
    """AIMD stub is ~8% lower than MLIP-MD on the same fixture."""
    env_m = MlipMdDiffusionAdapter().compute(llzo_params)
    env_a = AimdDiffusionAdapter().compute(llzo_params)
    Dm = env_m.output["diffusion_coefficient_cm2_per_s"]
    Da = env_a.output["diffusion_coefficient_cm2_per_s"]
    # AIMD is biased ~8% lower; the deviation may be larger due to
    # block jitter but should not exceed a factor of 2.
    ratio = Da / Dm
    assert 0.5 < ratio < 1.0


def test_aimd_disagreement_within_threshold(llzo_params: IonicJobParams) -> None:
    """LLZO MLIP-vs-AIMD disagreement should be well under 0.5 dex."""
    env_m = MlipMdDiffusionAdapter().compute(llzo_params)
    env_a = AimdDiffusionAdapter().compute(llzo_params)
    Dm = env_m.output["diffusion_coefficient_cm2_per_s"]
    Da = env_a.output["diffusion_coefficient_cm2_per_s"]
    disagreement = abs(math.log10(Dm / Da))
    assert disagreement <= 0.5


def test_aimd_envelope_layer_is_ionic(llzo_params: IonicJobParams) -> None:
    env = AimdDiffusionAdapter().compute(llzo_params)
    assert env.layer == "ionic"


def test_aimd_envelope_carries_service_ref(llzo_params: IonicJobParams) -> None:
    env = AimdDiffusionAdapter().compute(llzo_params)
    assert IONIC_TRANSPORT_SERVICE_REF in env.input_refs


def test_blocked_source_manifest_exists() -> None:
    assert AIMD_BLOCKED_MANIFEST.source_manifest_id == "src:blocked:aimd-real-backend"
    assert AIMD_BLOCKED_MANIFEST.blocker_reason == "unavailable_credentials"


def test_aimd_known_fixture_high_confidence(llzo_params: IonicJobParams) -> None:
    env = AimdDiffusionAdapter().compute(llzo_params)
    assert env.output["confidence"] >= 0.5


def test_aimd_unknown_fixture_low_confidence() -> None:
    p = IonicJobParams(structure_hash="sha256:" + "0" * 64, fixture_id=None)
    env = AimdDiffusionAdapter().compute(p)
    # Unknown fixture -> confidence is moderated (0.50).
    assert env.output["confidence"] == 0.50


def test_aimd_credible_interval_present(llzo_params: IonicJobParams) -> None:
    env = AimdDiffusionAdapter().compute(llzo_params)
    item_names = [it.name for it in env.falsifier.items]
    assert "ionic.rt_conductivity_credible_interval" in item_names
