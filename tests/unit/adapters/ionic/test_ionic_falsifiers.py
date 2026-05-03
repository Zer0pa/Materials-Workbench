"""Unit tests for the ionic falsifiers."""

from __future__ import annotations

import pytest

from zer0pa_materials_workbench.adapters.ionic.aimd import AimdDiffusionAdapter
from zer0pa_materials_workbench.adapters.ionic.arrhenius import (
    ArrheniusFitAdapter,
    ArrheniusFitParams,
)
from zer0pa_materials_workbench.adapters.ionic.base import (
    IonicJobParams,
)
from zer0pa_materials_workbench.adapters.ionic.electrochemical_window import (
    ElectrochemicalWindowAdapter,
)
from zer0pa_materials_workbench.adapters.ionic.interface_stability import (
    InterfaceStabilityAdapter,
)
from zer0pa_materials_workbench.adapters.ionic.mlip_md import MlipMdDiffusionAdapter
from zer0pa_materials_workbench.adapters.ionic.neb import NebMigrationBarrierAdapter
from zer0pa_materials_workbench.falsifiers.ionic_falsifiers import (
    REQUIRED_EVIDENCE_KEYS,
    activation_energy_target_threshold,
    arrhenius_fit_quality,
    defect_disorder_assumptions_documented,
    full_battery_evidence_chain_complete,
    li_metal_reduction_route_compatibility,
    mlip_aimd_diffusion_disagreement,
    oxidative_stability_threshold,
    requires_ionic_transport_service,
    room_temperature_conductivity_credible_interval_meets_threshold,
)


@pytest.fixture
def llzo_params() -> IonicJobParams:
    return IonicJobParams(
        structure_hash="sha256:" + "a" * 64,
        fixture_id="fixture:LLZO_cubic:d45cb2bf",
        candidate_id="candidate:LLZO/cubic",
    )


# ----------------------------------------------------------------------------
# requires_ionic_transport_service
# ----------------------------------------------------------------------------


def test_requires_service_pass_when_envelope_carries_ref(
    llzo_params: IonicJobParams,
) -> None:
    env = MlipMdDiffusionAdapter().compute(llzo_params)
    item = requires_ionic_transport_service(env)
    assert item.status == "pass"


def test_requires_service_fail_for_flat_overclaim() -> None:
    """A flat-shape candidate JSON claiming ionic_conductivity_S_per_cm
    without a service ref triggers the fail."""
    flat = {
        "research_boundary": "x",
        "ionic_conductivity_S_per_cm": 5.0e-3,
        "ionic_transport_service_ref": None,
    }
    item = requires_ionic_transport_service(flat)
    assert item.status == "fail"


def test_requires_service_fail_for_flat_overclaim_missing_ref_field() -> None:
    flat = {"ionic_conductivity_S_per_cm": 5.0e-3}
    item = requires_ionic_transport_service(flat)
    assert item.status == "fail"


def test_requires_service_pass_for_flat_with_ref() -> None:
    flat = {
        "ionic_conductivity_S_per_cm": 5.0e-3,
        "ionic_transport_service_ref": "service:ionic-transport-service:v1",
    }
    item = requires_ionic_transport_service(flat)
    assert item.status == "pass"


def test_requires_service_pass_when_no_claim() -> None:
    """Vacuous-truth: no ionic conductivity claim -> gate not triggered."""
    flat = {"some_other_field": 1.0}
    item = requires_ionic_transport_service(flat)
    assert item.status == "pass"


# ----------------------------------------------------------------------------
# room_temperature_conductivity_credible_interval_meets_threshold
# ----------------------------------------------------------------------------


def test_rt_ci_pass_for_llzo(llzo_params: IonicJobParams) -> None:
    env = MlipMdDiffusionAdapter().compute(llzo_params)
    item = room_temperature_conductivity_credible_interval_meets_threshold(env)
    assert item.status == "pass"


def test_rt_ci_blocked_when_no_sigma() -> None:
    item = room_temperature_conductivity_credible_interval_meets_threshold(
        {"output": {}}
    )
    assert item.status == "blocked"


def test_rt_ci_fail_when_sigma_below_threshold() -> None:
    body = {
        "output": {"nernst_einstein_conductivity_S_per_cm": 1e-5},
        "falsifier": {
            "items": [
                {
                    "name": "ionic.rt_conductivity_credible_interval",
                    "actual": {
                        "lo_S_per_cm": 1e-6,
                        "hi_S_per_cm": 5e-5,
                        "uncertainty_dex": 0.05,
                    },
                }
            ]
        },
    }
    item = room_temperature_conductivity_credible_interval_meets_threshold(body)
    assert item.status == "fail"


# ----------------------------------------------------------------------------
# activation_energy_target_threshold
# ----------------------------------------------------------------------------


def test_activation_target_pass_for_llzo(llzo_params: IonicJobParams) -> None:
    env = NebMigrationBarrierAdapter().compute(llzo_params)
    target, stretch = activation_energy_target_threshold(env)
    assert target.status == "pass"


def test_activation_target_blocked_when_missing() -> None:
    body = {"output": {}}
    target, stretch = activation_energy_target_threshold(body)
    assert target.status == "blocked"


def test_stretch_separate_from_target(llzo_params: IonicJobParams) -> None:
    env = NebMigrationBarrierAdapter().compute(llzo_params)
    target, stretch = activation_energy_target_threshold(env)
    # Both items are returned and named distinctly.
    assert target.name == "ionic.activation_energy_target"
    assert stretch.name == "ionic.activation_energy_stretch"


# ----------------------------------------------------------------------------
# oxidative_stability_threshold
# ----------------------------------------------------------------------------


def test_oxidative_pass_for_llzo() -> None:
    p = IonicJobParams(
        structure_hash="sha256:" + "a" * 64,
        fixture_id="fixture:LLZO_cubic:d45cb2bf",
    )
    env = ElectrochemicalWindowAdapter().compute(p)
    item = oxidative_stability_threshold(env)
    assert item.status == "pass"


def test_oxidative_fail_for_li6ps5cl() -> None:
    p = IonicJobParams(
        structure_hash="sha256:" + "b" * 64,
        fixture_id="fixture:Li6PS5Cl:8d7b2175",
    )
    env = ElectrochemicalWindowAdapter().compute(p)
    item = oxidative_stability_threshold(env)
    assert item.status == "fail"


def test_oxidative_blocked_when_missing() -> None:
    body = {"output": {}}
    item = oxidative_stability_threshold(body)
    assert item.status == "blocked"


# ----------------------------------------------------------------------------
# li_metal_reduction_route_compatibility
# ----------------------------------------------------------------------------


def test_li_metal_route_pass_for_stable_interface() -> None:
    p = IonicJobParams(
        structure_hash="sha256:" + "a" * 64,
        fixture_id="fixture:LLZO_cubic:d45cb2bf",
        interface_mode="li_metal",
    )
    env = InterfaceStabilityAdapter().compute(p)
    item = li_metal_reduction_route_compatibility(env)
    assert item.status == "pass"


def test_li_metal_route_fail_for_unstable_default_mode() -> None:
    p = IonicJobParams(
        structure_hash="sha256:" + "b" * 64,
        fixture_id="fixture:Li6PS5Cl:8d7b2175",
        interface_mode="li_metal",
    )
    env = InterfaceStabilityAdapter().compute(p)
    item = li_metal_reduction_route_compatibility(env)
    assert item.status == "fail"


def test_li_metal_route_pass_for_unstable_with_coating() -> None:
    p = IonicJobParams(
        structure_hash="sha256:" + "b" * 64,
        fixture_id="fixture:Li6PS5Cl:8d7b2175",
        interface_mode="coating_interlayer",
    )
    env = InterfaceStabilityAdapter().compute(p)
    item = li_metal_reduction_route_compatibility(env)
    assert item.status == "pass"


def test_li_metal_route_blocked_for_unknown_classification() -> None:
    p = IonicJobParams(structure_hash="sha256:" + "0" * 64, fixture_id=None)
    env = InterfaceStabilityAdapter().compute(p)
    item = li_metal_reduction_route_compatibility(env)
    assert item.status == "blocked"


# ----------------------------------------------------------------------------
# arrhenius_fit_quality
# ----------------------------------------------------------------------------


def test_arrhenius_quality_pass_for_clean_fit() -> None:
    fit_params = ArrheniusFitParams(
        temperatures_K=[300.0, 400.0, 500.0, 600.0],
        conductivities_S_per_cm=[1e-3, 5e-3, 1e-2, 2e-2],
        candidate_id="candidate:test/arrhenius",
    )
    env = ArrheniusFitAdapter().compute_from_params(fit_params)
    item = arrhenius_fit_quality(env)
    assert item.status == "pass"


def test_arrhenius_quality_blocked_when_no_fit() -> None:
    body = {"output": {}, "falsifier": {"items": []}}
    item = arrhenius_fit_quality(body)
    assert item.status == "blocked"


# ----------------------------------------------------------------------------
# mlip_aimd_diffusion_disagreement
# ----------------------------------------------------------------------------


def test_disagreement_pass_for_close_values(llzo_params: IonicJobParams) -> None:
    env_m = MlipMdDiffusionAdapter().compute(llzo_params)
    env_a = AimdDiffusionAdapter().compute(llzo_params)
    item = mlip_aimd_diffusion_disagreement(env_m, env_a)
    assert item.status == "pass"


def test_disagreement_fail_for_far_values() -> None:
    """Manually craft envelopes with D values 1 dex apart."""
    env_m = {"output": {"diffusion_coefficient_cm2_per_s": 1e-7}}
    env_a = {"output": {"diffusion_coefficient_cm2_per_s": 1e-9}}
    item = mlip_aimd_diffusion_disagreement(env_m, env_a)
    assert item.status == "fail"


def test_disagreement_blocked_when_missing() -> None:
    item = mlip_aimd_diffusion_disagreement({"output": {}}, {"output": {}})
    assert item.status == "blocked"


# ----------------------------------------------------------------------------
# defect_disorder_assumptions_documented
# ----------------------------------------------------------------------------


def test_assumptions_pass_for_real_envelope(llzo_params: IonicJobParams) -> None:
    env = MlipMdDiffusionAdapter().compute(llzo_params)
    item = defect_disorder_assumptions_documented(env)
    assert item.status == "pass"


def test_assumptions_fail_when_empty() -> None:
    body = {"output": {"defect_disorder_assumptions": [], "confidence": 0.0}}
    item = defect_disorder_assumptions_documented(body)
    assert item.status == "fail"


def test_assumptions_fail_when_zero_confidence() -> None:
    body = {
        "output": {"defect_disorder_assumptions": ["x"], "confidence": 0.0}
    }
    item = defect_disorder_assumptions_documented(body)
    assert item.status == "fail"


# ----------------------------------------------------------------------------
# full_battery_evidence_chain_complete
# ----------------------------------------------------------------------------


def test_chain_complete_pass_for_full_bundle(llzo_params: IonicJobParams) -> None:
    envs = [
        NebMigrationBarrierAdapter().compute(llzo_params),
        MlipMdDiffusionAdapter().compute(llzo_params),
        AimdDiffusionAdapter().compute(llzo_params),
        ArrheniusFitAdapter().compute(llzo_params),
        ElectrochemicalWindowAdapter().compute(llzo_params),
        InterfaceStabilityAdapter().compute(llzo_params),
    ]
    item = full_battery_evidence_chain_complete(envs)
    assert item.status == "pass"


def test_chain_complete_fail_when_one_evidence_missing(llzo_params: IonicJobParams) -> None:
    """Drop the NEB envelope and verify the migration_barrier_eV key is missing."""
    envs = [
        # NebMigrationBarrierAdapter().compute(llzo_params),  # MISSING
        MlipMdDiffusionAdapter().compute(llzo_params),
        AimdDiffusionAdapter().compute(llzo_params),
        ArrheniusFitAdapter().compute(llzo_params),
        ElectrochemicalWindowAdapter().compute(llzo_params),
        InterfaceStabilityAdapter().compute(llzo_params),
    ]
    item = full_battery_evidence_chain_complete(envs)
    assert item.status == "fail"
    assert "migration_barrier_eV" in item.actual["missing"]


def test_required_evidence_keys_constant() -> None:
    """The constant must contain six entries (PRD §Ionic Transport)."""
    assert len(REQUIRED_EVIDENCE_KEYS) == 6
    for key in (
        "migration_barrier_eV",
        "diffusion_coefficient_cm2_per_s",
        "arrhenius",
        "electrochemical_window_V_vs_LiLi",
        "interface_stability",
        "defect_disorder_assumptions",
    ):
        assert key in REQUIRED_EVIDENCE_KEYS
