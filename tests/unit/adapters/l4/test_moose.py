"""Unit tests for MoosePhaseFieldAdapter (cross-code disagreement primitive)."""

from __future__ import annotations

import pytest

from zer0pa_materials.adapters.l4.base import L4PredictRequest
from zer0pa_materials.adapters.l4.contracts import (
    PhaseFieldDomain,
    PhaseFieldMaterial,
    PhaseFieldMesh,
    PhaseFieldRunSpec,
)
from zer0pa_materials.adapters.l4.moose import MoosePhaseFieldAdapter
from zer0pa_materials.adapters.l4.prisms_pf import PrismsPfAdapter
from zer0pa_materials.boundary import RESEARCH_BOUNDARY
from zer0pa_materials.envelope.envelope import Envelope


@pytest.fixture
def adapter():
    return MoosePhaseFieldAdapter()


@pytest.fixture
def request_obj():
    return L4PredictRequest(
        run_id="run:test/moose/001",
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


class TestMooseShape:
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

    def test_engine_label_marmot(self, adapter, cahn_hilliard_spec, request_obj):
        result = adapter.run(cahn_hilliard_spec, request_obj)
        assert "MOOSE" in result["tool_adapter"]["engine"]


class TestMooseConservation:
    def test_mass_drift_below_threshold(self, adapter, cahn_hilliard_spec, request_obj):
        result = adapter.run(cahn_hilliard_spec, request_obj)
        drift = result["output"]["cahn_hilliard_mass_drift"]
        assert drift is not None
        assert drift < 1e-3

    def test_bounds_violation_below_threshold(self, adapter, allen_cahn_spec, request_obj):
        result = adapter.run(allen_cahn_spec, request_obj)
        bv = result["output"]["allen_cahn_bounds_violation"]
        assert bv is not None
        assert bv < 1e-4


class TestCrossCodeDisagreement:
    """MOOSE and PRISMS-PF must produce schema-identical but numerically
    different output on the same input (the disagreement primitive)."""

    def test_same_top_level_keys(self, adapter, cahn_hilliard_spec, request_obj):
        prisms = PrismsPfAdapter().run(cahn_hilliard_spec, request_obj)
        moose = adapter.run(cahn_hilliard_spec, request_obj)
        prisms_keys = {k for k in prisms if not k.startswith("_")}
        moose_keys = {k for k in moose if not k.startswith("_")}
        assert prisms_keys == moose_keys

    def test_same_output_keys(self, adapter, cahn_hilliard_spec, request_obj):
        prisms = PrismsPfAdapter().run(cahn_hilliard_spec, request_obj)
        moose = adapter.run(cahn_hilliard_spec, request_obj)
        assert set(prisms["output"].keys()) == set(moose["output"].keys())

    def test_different_engine_labels(self, adapter, cahn_hilliard_spec, request_obj):
        prisms = PrismsPfAdapter().run(cahn_hilliard_spec, request_obj)
        moose = adapter.run(cahn_hilliard_spec, request_obj)
        assert prisms["tool_adapter"]["engine"] != moose["tool_adapter"]["engine"]

    def test_different_adapter_names(self, adapter, cahn_hilliard_spec, request_obj):
        prisms = PrismsPfAdapter().run(cahn_hilliard_spec, request_obj)
        moose = adapter.run(cahn_hilliard_spec, request_obj)
        assert prisms["tool_adapter"]["name"] != moose["tool_adapter"]["name"]

    def test_ac_bounds_can_differ(self, adapter, allen_cahn_spec, request_obj):
        # MOOSE uses a different decay rate, so for AC the bounds-violation
        # values can differ between the two backends. At minimum the output
        # type is the same float.
        prisms = PrismsPfAdapter().run(allen_cahn_spec, request_obj)
        moose = adapter.run(allen_cahn_spec, request_obj)
        assert isinstance(prisms["output"]["allen_cahn_bounds_violation"], float)
        assert isinstance(moose["output"]["allen_cahn_bounds_violation"], float)


class TestBlockedManifest:
    def test_moose_blocked_manifest(self, adapter):
        manifests = adapter.blocked_manifests()
        ids = [m["source_manifest_id"] for m in manifests]
        assert "src:moose:cxx-build" in ids
