"""Unit tests for PrismsPfAdapter (Allen-Cahn / Cahn-Hilliard / MPF stub)."""

from __future__ import annotations

import pytest

from zer0pa_materials.adapters.l4.base import L4PredictRequest
from zer0pa_materials.adapters.l4.contracts import (
    KmcRunSpec,
    PhaseFieldDomain,
    PhaseFieldMaterial,
    PhaseFieldMesh,
    PhaseFieldRunSpec,
)
from zer0pa_materials.adapters.l4.prisms_pf import PrismsPfAdapter
from zer0pa_materials.boundary import RESEARCH_BOUNDARY
from zer0pa_materials.envelope.envelope import Envelope


@pytest.fixture
def adapter():
    return PrismsPfAdapter()


@pytest.fixture
def request_obj():
    return L4PredictRequest(
        run_id="run:test/prisms-pf/001",
        candidate_id="candidate:test/001",
        campaign_id="campaign:test/001",
        rights_claim_id="rights:test/001",
    )


@pytest.fixture
def cahn_hilliard_spec():
    return PhaseFieldRunSpec(
        equation="cahn_hilliard",
        domain=PhaseFieldDomain(dimension=2, extents=[10.0, 10.0], units="nm"),
        mesh=PhaseFieldMesh(nodes=[16, 16]),
        materials=[PhaseFieldMaterial(phase_name="alpha", initial_fraction=0.5)],
        time_steps=10,
        dt=0.01,
        n_dumps=6,
    )


@pytest.fixture
def allen_cahn_spec():
    return PhaseFieldRunSpec(
        equation="allen_cahn",
        domain=PhaseFieldDomain(dimension=2, extents=[10.0, 10.0], units="nm"),
        mesh=PhaseFieldMesh(nodes=[16, 16]),
        materials=[PhaseFieldMaterial(phase_name="alpha", initial_fraction=0.5)],
        time_steps=10,
        dt=0.01,
        n_dumps=6,
    )


@pytest.fixture
def mpf_spec():
    return PhaseFieldRunSpec(
        equation="mpf",
        domain=PhaseFieldDomain(dimension=2, extents=[10.0, 10.0], units="nm"),
        mesh=PhaseFieldMesh(nodes=[16, 16]),
        materials=[
            PhaseFieldMaterial(phase_name="alpha", initial_fraction=0.4),
            PhaseFieldMaterial(phase_name="beta", initial_fraction=0.6),
        ],
        time_steps=10,
        dt=0.01,
        n_dumps=6,
    )


class TestPrismsPfShape:
    def test_run_returns_dict(self, adapter, cahn_hilliard_spec, request_obj):
        result = adapter.run(cahn_hilliard_spec, request_obj)
        assert isinstance(result, dict)

    def test_layer_is_L4(self, adapter, cahn_hilliard_spec, request_obj):
        result = adapter.run(cahn_hilliard_spec, request_obj)
        assert result["layer"] == "L4"

    def test_boundary_verbatim(self, adapter, cahn_hilliard_spec, request_obj):
        result = adapter.run(cahn_hilliard_spec, request_obj)
        assert result["research_boundary"] == RESEARCH_BOUNDARY

    def test_envelope_validates(self, adapter, cahn_hilliard_spec, request_obj):
        result = adapter.run(cahn_hilliard_spec, request_obj)
        clean = {k: v for k, v in result.items() if not k.startswith("_")}
        env = Envelope.model_validate(clean)
        assert env.layer == "L4"

    def test_tool_adapter_name(self, adapter, cahn_hilliard_spec, request_obj):
        result = adapter.run(cahn_hilliard_spec, request_obj)
        assert result["tool_adapter"]["name"] == "PrismsPfAdapter"

    def test_engine_label(self, adapter, cahn_hilliard_spec, request_obj):
        result = adapter.run(cahn_hilliard_spec, request_obj)
        assert "PRISMS-PF" in result["tool_adapter"]["engine"]

    def test_backend_is_stub(self, adapter, cahn_hilliard_spec, request_obj):
        result = adapter.run(cahn_hilliard_spec, request_obj)
        assert result["tool_adapter"]["backend"] == "stub"

    def test_meta_block_present(self, adapter, cahn_hilliard_spec, request_obj):
        result = adapter.run(cahn_hilliard_spec, request_obj)
        assert "_l4_meta" in result

    def test_advisory_default_false(self, adapter, cahn_hilliard_spec, request_obj):
        result = adapter.run(cahn_hilliard_spec, request_obj)
        assert result["_l4_meta"]["advisory"] is False


class TestCahnHilliardConservation:
    """Cahn-Hilliard mass-drift gate (PRD §L4: < 1e-3 on tiny fixture)."""

    def test_mass_drift_below_threshold(self, adapter, cahn_hilliard_spec, request_obj):
        result = adapter.run(cahn_hilliard_spec, request_obj)
        drift = result["output"]["cahn_hilliard_mass_drift"]
        assert drift is not None
        assert drift < 1e-3

    def test_mass_drift_is_zero_or_machine_epsilon(self, adapter, cahn_hilliard_spec, request_obj):
        # Synthetic CH evolution conserves mass exactly
        result = adapter.run(cahn_hilliard_spec, request_obj)
        drift = result["output"]["cahn_hilliard_mass_drift"]
        assert drift < 1e-10

    def test_falsifier_status_pass(self, adapter, cahn_hilliard_spec, request_obj):
        result = adapter.run(cahn_hilliard_spec, request_obj)
        assert result["falsifier"]["status"] == "pass"


class TestAllenCahnBounds:
    """Allen-Cahn bounds gate (PRD §L4: < 1e-4)."""

    def test_bounds_violation_below_threshold(self, adapter, allen_cahn_spec, request_obj):
        result = adapter.run(allen_cahn_spec, request_obj)
        bv = result["output"]["allen_cahn_bounds_violation"]
        assert bv is not None
        assert bv < 1e-4

    def test_bounds_violation_zero_at_clamp(self, adapter, allen_cahn_spec, request_obj):
        # The synthetic AC evolution clamps to ±(1 - 1e-12), so bounds
        # violation should be 0 exactly.
        result = adapter.run(allen_cahn_spec, request_obj)
        bv = result["output"]["allen_cahn_bounds_violation"]
        assert bv == 0.0

    def test_falsifier_status_pass(self, adapter, allen_cahn_spec, request_obj):
        result = adapter.run(allen_cahn_spec, request_obj)
        assert result["falsifier"]["status"] == "pass"


class TestMpfBoth:
    """MPF should produce both mass-drift and bounds-violation values."""

    def test_mass_drift_present(self, adapter, mpf_spec, request_obj):
        result = adapter.run(mpf_spec, request_obj)
        assert result["output"]["cahn_hilliard_mass_drift"] is not None

    def test_bounds_violation_present(self, adapter, mpf_spec, request_obj):
        result = adapter.run(mpf_spec, request_obj)
        assert result["output"]["allen_cahn_bounds_violation"] is not None


class TestRefusesKmcSpec:
    def test_kmc_spec_raises(self, adapter, request_obj):
        kmc = KmcRunSpec(grid_size=[8, 8], n_states=4, n_steps=10, n_dumps=4, temperature_K=0.0)
        with pytest.raises(TypeError):
            adapter.run(kmc, request_obj)


class TestRefusesGrandPotential:
    def test_grand_potential_raises(self, adapter, request_obj):
        spec = PhaseFieldRunSpec(
            equation="grand_potential",
            domain=PhaseFieldDomain(dimension=2, extents=[10.0, 10.0], units="nm"),
            mesh=PhaseFieldMesh(nodes=[16, 16]),
            materials=[PhaseFieldMaterial(phase_name="alpha", initial_fraction=0.5)],
            time_steps=10,
            dt=0.01,
            n_dumps=6,
        )
        with pytest.raises(ValueError, match="grand_potential"):
            adapter.run(spec, request_obj)


class TestDeterminism:
    """Identical inputs must produce identical outputs."""

    def test_two_calls_same_output(self, adapter, cahn_hilliard_spec, request_obj):
        r1 = adapter.run(cahn_hilliard_spec, request_obj)
        r2 = adapter.run(cahn_hilliard_spec, request_obj)
        assert r1["output"] == r2["output"]
        assert r1["audit"]["input_hash"] == r2["audit"]["input_hash"]
        assert r1["audit"]["output_hash"] == r2["audit"]["output_hash"]


class TestBlockedManifest:
    def test_blocked_manifest_returned(self, adapter):
        manifests = adapter.blocked_manifests()
        assert len(manifests) >= 1

    def test_blocked_manifest_has_prisms_pf_id(self, adapter):
        manifests = adapter.blocked_manifests()
        ids = [m["source_manifest_id"] for m in manifests]
        assert "src:prisms-pf:cxx-build" in ids
