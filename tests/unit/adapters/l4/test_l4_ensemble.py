"""Unit tests for L4SolverEnsemble — primary user-facing L4 adapter.

The plug-swap invariance gate is here: swap PRISMS-PF for MOOSE (or any
other L4Adapter) and the schema must NOT change.
"""

from __future__ import annotations

import pytest

from zer0pa_materials.adapters.l4.base import L4Adapter, L4PredictRequest
from zer0pa_materials.adapters.l4.contracts import (
    PhaseFieldDomain,
    PhaseFieldMaterial,
    PhaseFieldMesh,
    PhaseFieldRunSpec,
)
from zer0pa_materials.adapters.l4.ensemble import L4SolverEnsemble
from zer0pa_materials.adapters.l4.moose import MoosePhaseFieldAdapter
from zer0pa_materials.adapters.l4.prisms_pf import PrismsPfAdapter
from zer0pa_materials.boundary import RESEARCH_BOUNDARY
from zer0pa_materials.envelope.envelope import Envelope


@pytest.fixture
def request_obj():
    return L4PredictRequest(
        run_id="run:test/ensemble/001",
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


class TestEnsembleShape:
    def test_runs_both_backends(self, cahn_hilliard_spec, request_obj):
        runner = L4SolverEnsemble()
        result = runner.run(cahn_hilliard_spec, request_obj)
        assert result["layer"] == "L4"
        assert "_l4_ensemble_meta" in result

    def test_envelope_validates(self, cahn_hilliard_spec, request_obj):
        runner = L4SolverEnsemble()
        result = runner.run(cahn_hilliard_spec, request_obj)
        clean = {k: v for k, v in result.items() if not k.startswith("_")}
        env = Envelope.model_validate(clean)
        assert env.layer == "L4"

    def test_boundary_verbatim(self, cahn_hilliard_spec, request_obj):
        runner = L4SolverEnsemble()
        result = runner.run(cahn_hilliard_spec, request_obj)
        assert result["research_boundary"] == RESEARCH_BOUNDARY

    def test_engine_combined(self, cahn_hilliard_spec, request_obj):
        runner = L4SolverEnsemble()
        result = runner.run(cahn_hilliard_spec, request_obj)
        engine = result["tool_adapter"]["engine"]
        assert "+" in engine
        assert "PRISMS-PF" in engine
        assert "MOOSE" in engine

    def test_meta_has_both_backends(self, cahn_hilliard_spec, request_obj):
        runner = L4SolverEnsemble()
        result = runner.run(cahn_hilliard_spec, request_obj)
        meta = result["_l4_ensemble_meta"]
        assert meta["primary"]["adapter_name"] == "PrismsPfAdapter"
        assert meta["secondary"]["adapter_name"] == "MoosePhaseFieldAdapter"

    def test_disagreement_metrics_present(self, cahn_hilliard_spec, request_obj):
        runner = L4SolverEnsemble()
        result = runner.run(cahn_hilliard_spec, request_obj)
        assert len(result["disagreement"]["metrics"]) >= 1


class TestEnsembleDisagreementMetric:
    def test_ch_disagreement_metric_name(self, cahn_hilliard_spec, request_obj):
        runner = L4SolverEnsemble()
        result = runner.run(cahn_hilliard_spec, request_obj)
        names = {m["name"] for m in result["disagreement"]["metrics"]}
        assert "l4.cross_code_mass_drift_disagreement" in names

    def test_ac_disagreement_metric_name(self, allen_cahn_spec, request_obj):
        runner = L4SolverEnsemble()
        result = runner.run(allen_cahn_spec, request_obj)
        names = {m["name"] for m in result["disagreement"]["metrics"]}
        assert "l4.cross_code_bounds_violation_disagreement" in names

    def test_mpf_two_disagreement_metrics(self, mpf_spec, request_obj):
        runner = L4SolverEnsemble()
        result = runner.run(mpf_spec, request_obj)
        names = {m["name"] for m in result["disagreement"]["metrics"]}
        assert len(names) == 2


class TestPlugSwapEquivalence:
    """The "<1 day swap" invariant: any two L4Adapters can fill the primary
    or secondary slot and the schema must remain identical."""

    def test_swap_primary_and_secondary_yields_same_keys(
        self, cahn_hilliard_spec, request_obj
    ):
        prisms = PrismsPfAdapter()
        moose = MoosePhaseFieldAdapter()
        runner_a = L4SolverEnsemble(primary=prisms, secondary=moose)
        runner_b = L4SolverEnsemble(primary=moose, secondary=prisms)
        result_a = runner_a.run(cahn_hilliard_spec, request_obj)
        result_b = runner_b.run(cahn_hilliard_spec, request_obj)
        keys_a = {k for k in result_a if not k.startswith("_")}
        keys_b = {k for k in result_b if not k.startswith("_")}
        assert keys_a == keys_b

    def test_output_schema_identical_after_swap(self, cahn_hilliard_spec, request_obj):
        runner_a = L4SolverEnsemble()
        runner_b = L4SolverEnsemble(primary=MoosePhaseFieldAdapter(), secondary=PrismsPfAdapter())
        result_a = runner_a.run(cahn_hilliard_spec, request_obj)
        result_b = runner_b.run(cahn_hilliard_spec, request_obj)
        assert set(result_a["output"].keys()) == set(result_b["output"].keys())

    def test_layer_unchanged_after_swap(self, cahn_hilliard_spec, request_obj):
        runner_a = L4SolverEnsemble()
        runner_b = L4SolverEnsemble(primary=MoosePhaseFieldAdapter(), secondary=PrismsPfAdapter())
        result_a = runner_a.run(cahn_hilliard_spec, request_obj)
        result_b = runner_b.run(cahn_hilliard_spec, request_obj)
        assert result_a["layer"] == result_b["layer"] == "L4"


class TestBlockedManifests:
    def test_aggregates_manifests_from_both(self):
        runner = L4SolverEnsemble()
        manifests = runner.blocked_manifests()
        ids = {m["source_manifest_id"] for m in manifests}
        assert "src:prisms-pf:cxx-build" in ids
        assert "src:moose:cxx-build" in ids
