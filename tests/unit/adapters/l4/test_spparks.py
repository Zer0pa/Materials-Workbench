"""Unit tests for SpparksKmcAdapter (T=0 Potts energy-monotonic gate)."""

from __future__ import annotations

import pytest

from zer0pa_materials.adapters.l4.base import L4PredictRequest
from zer0pa_materials.adapters.l4.contracts import KmcRunSpec, PhaseFieldRunSpec
from zer0pa_materials.adapters.l4.spparks import SpparksKmcAdapter
from zer0pa_materials.boundary import RESEARCH_BOUNDARY
from zer0pa_materials.envelope.envelope import Envelope


@pytest.fixture
def adapter():
    return SpparksKmcAdapter()


@pytest.fixture
def request_obj():
    return L4PredictRequest(
        run_id="run:test/spparks/001",
        candidate_id="candidate:test/001",
        campaign_id="campaign:test/001",
        rights_claim_id="rights:test/001",
    )


@pytest.fixture
def t0_spec():
    return KmcRunSpec(
        grid_size=[12, 12],
        n_states=4,
        n_steps=20,
        n_dumps=5,
        temperature_K=0.0,
    )


@pytest.fixture
def thermal_spec():
    return KmcRunSpec(
        grid_size=[12, 12],
        n_states=4,
        n_steps=20,
        n_dumps=5,
        temperature_K=500.0,
    )


class TestSpparksShape:
    def test_layer_is_L4(self, adapter, t0_spec, request_obj):
        result = adapter.run(t0_spec, request_obj)
        assert result["layer"] == "L4"

    def test_boundary_verbatim(self, adapter, t0_spec, request_obj):
        result = adapter.run(t0_spec, request_obj)
        assert result["research_boundary"] == RESEARCH_BOUNDARY

    def test_envelope_validates(self, adapter, t0_spec, request_obj):
        result = adapter.run(t0_spec, request_obj)
        clean = {k: v for k, v in result.items() if not k.startswith("_")}
        env = Envelope.model_validate(clean)
        assert env.layer == "L4"

    def test_engine_label_potts(self, adapter, t0_spec, request_obj):
        result = adapter.run(t0_spec, request_obj)
        assert "Potts" in result["tool_adapter"]["engine"]

    def test_meta_block_records_grid_size(self, adapter, t0_spec, request_obj):
        result = adapter.run(t0_spec, request_obj)
        assert result["_l4_meta"]["grid_size"] == [12, 12]


class TestEnergyMonotonicAtT0:
    """PRD §L4: T=0 SPPARKS Potts energy does NOT increase across dumps."""

    def test_energies_are_monotonic_non_increasing(self, adapter, t0_spec, request_obj):
        result = adapter.run(t0_spec, request_obj)
        energies = result["_l4_meta"]["energies"]
        for k in range(1, len(energies)):
            assert energies[k] <= energies[k - 1], (
                f"Energy increased at dump {k}: {energies[k - 1]} -> {energies[k]}"
            )

    def test_monotonic_flag_true_at_t0(self, adapter, t0_spec, request_obj):
        result = adapter.run(t0_spec, request_obj)
        assert result["output"]["spparks_potts_energy_monotonic"] is True

    def test_falsifier_passes(self, adapter, t0_spec, request_obj):
        result = adapter.run(t0_spec, request_obj)
        assert result["falsifier"]["status"] == "pass"


class TestThermalKickIntroducesNonMonotonicity:
    """T>0 evolutions must NOT pass the monotonic gate (a positive control
    for the falsifier)."""

    def test_thermal_evolution_non_monotonic(self, adapter, thermal_spec, request_obj):
        result = adapter.run(thermal_spec, request_obj)
        energies = result["_l4_meta"]["energies"]
        # At least one step where energy went UP relative to previous
        increased_at_some_step = any(
            energies[k] > energies[k - 1] for k in range(1, len(energies))
        )
        assert increased_at_some_step, f"Thermal kick should produce non-monotonic energies; got {energies}"

    def test_thermal_monotonic_flag_false(self, adapter, thermal_spec, request_obj):
        result = adapter.run(thermal_spec, request_obj)
        assert result["output"]["spparks_potts_energy_monotonic"] is False


class TestRefusesPhaseFieldSpec:
    def test_phase_field_spec_raises(self, adapter, request_obj):
        from zer0pa_materials.adapters.l4.contracts import (
            PhaseFieldDomain,
            PhaseFieldMaterial,
            PhaseFieldMesh,
        )
        spec = PhaseFieldRunSpec(
            equation="cahn_hilliard",
            domain=PhaseFieldDomain(dimension=2, extents=[10.0, 10.0], units="nm"),
            mesh=PhaseFieldMesh(nodes=[16, 16]),
            materials=[PhaseFieldMaterial(phase_name="alpha", initial_fraction=0.5)],
            time_steps=10,
            dt=0.01,
            n_dumps=6,
        )
        with pytest.raises(TypeError):
            adapter.run(spec, request_obj)


class TestDeterminism:
    def test_two_calls_same_energies(self, adapter, t0_spec, request_obj):
        r1 = adapter.run(t0_spec, request_obj)
        r2 = adapter.run(t0_spec, request_obj)
        assert r1["_l4_meta"]["energies"] == r2["_l4_meta"]["energies"]


class TestBlockedManifest:
    def test_spparks_blocked_manifest(self, adapter):
        manifests = adapter.blocked_manifests()
        ids = [m["source_manifest_id"] for m in manifests]
        assert "src:spparks:cxx-build" in ids
