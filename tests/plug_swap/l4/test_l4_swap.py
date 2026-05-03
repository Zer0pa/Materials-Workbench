"""Plug-swap tests for L4 — schema invariance across PRISMS-PF / MOOSE / neural-op.

PRD §L4 plug-swap gate: "plug-swap from stub to another L4 backend changes
backend, NOT schema."

This is the ADVERSARIAL test: we swap the primary and secondary positions in
the ensemble, swap a classical solver for the neural-operator surrogate
(advisory-only, but same schema), and use ``runpod_mock`` as a third backend
class. The test asserts the wire-level schema is invariant across all
combinations.
"""

from __future__ import annotations

import pytest

from zer0pa_materials_workbench.adapters.l4.base import L4PredictRequest
from zer0pa_materials_workbench.adapters.l4.contracts import (
    PhaseFieldDomain,
    PhaseFieldMaterial,
    PhaseFieldMesh,
    PhaseFieldRunSpec,
)
from zer0pa_materials_workbench.adapters.l4.ensemble import L4SolverEnsemble
from zer0pa_materials_workbench.adapters.l4.moose import MoosePhaseFieldAdapter
from zer0pa_materials_workbench.adapters.l4.neural_operator import NeuralOperatorPhaseFieldAdapter
from zer0pa_materials_workbench.adapters.l4.prisms_pf import PrismsPfAdapter
from zer0pa_materials_workbench.envelope.envelope import Envelope
from zer0pa_materials_workbench.envelope.layer_outputs import L4PhaseFieldOutput
from zer0pa_materials_workbench.falsifiers.l4_falsifiers import plug_swap_schema_invariance

SPEC = PhaseFieldRunSpec(
    equation="cahn_hilliard",
    domain=PhaseFieldDomain(dimension=2, extents=[10.0, 10.0], units="nm"),
    mesh=PhaseFieldMesh(nodes=[16, 16]),
    materials=[PhaseFieldMaterial(phase_name="alpha", initial_fraction=0.5)],
    time_steps=10,
    dt=0.01,
    n_dumps=6,
)


def _req(suffix: str) -> L4PredictRequest:
    return L4PredictRequest(
        run_id=f"run:swap/l4/{suffix}",
        candidate_id="candidate:swap/001",
        campaign_id="campaign:swap/001",
        rights_claim_id="rights:swap/001",
    )


# ---------------------------------------------------------------------------
# Backend wrappers
# ---------------------------------------------------------------------------


class LocalStubRunner:
    """Default L4SolverEnsemble: PRISMS-PF + MOOSE."""

    def run(self, spec: PhaseFieldRunSpec, request: L4PredictRequest) -> dict:
        return L4SolverEnsemble().run(spec, request)


class RunpodMockRunner:
    """Simulates a runpod_mock response by overriding the backend label."""

    def run(self, spec: PhaseFieldRunSpec, request: L4PredictRequest) -> dict:
        env = L4SolverEnsemble().run(spec, request)
        env["tool_adapter"]["backend"] = "runpod_mock"
        return env


class SwappedEnsembleRunner:
    """Swap primary/secondary order. Schema must NOT change."""

    def run(self, spec: PhaseFieldRunSpec, request: L4PredictRequest) -> dict:
        return L4SolverEnsemble(
            primary=MoosePhaseFieldAdapter(),
            secondary=PrismsPfAdapter(),
        ).run(spec, request)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def local_envelope():
    return LocalStubRunner().run(SPEC, _req("local"))


@pytest.fixture
def runpod_envelope():
    return RunpodMockRunner().run(SPEC, _req("runpod"))


@pytest.fixture
def swapped_envelope():
    return SwappedEnsembleRunner().run(SPEC, _req("swapped"))


@pytest.fixture
def neural_op_envelope():
    """Neural-operator emits same schema (advisory=True at default)."""
    return NeuralOperatorPhaseFieldAdapter().run(SPEC, _req("neural-op"))


# ---------------------------------------------------------------------------
# Schema parity: top-level envelope keys
# ---------------------------------------------------------------------------


class TestEnvelopeSchemaParity:
    def test_local_envelope_validates(self, local_envelope):
        clean = {k: v for k, v in local_envelope.items() if not k.startswith("_")}
        env = Envelope.model_validate(clean)
        assert env.layer == "L4"

    def test_runpod_envelope_validates(self, runpod_envelope):
        clean = {k: v for k, v in runpod_envelope.items() if not k.startswith("_")}
        env = Envelope.model_validate(clean)
        assert env.layer == "L4"

    def test_swapped_envelope_validates(self, swapped_envelope):
        clean = {k: v for k, v in swapped_envelope.items() if not k.startswith("_")}
        env = Envelope.model_validate(clean)
        assert env.layer == "L4"

    def test_neural_op_envelope_validates(self, neural_op_envelope):
        clean = {k: v for k, v in neural_op_envelope.items() if not k.startswith("_")}
        env = Envelope.model_validate(clean)
        assert env.layer == "L4"

    def test_local_vs_runpod_top_level_keys(self, local_envelope, runpod_envelope):
        a = {k for k in local_envelope if not k.startswith("_")}
        b = {k for k in runpod_envelope if not k.startswith("_")}
        assert a == b

    def test_local_vs_swapped_top_level_keys(self, local_envelope, swapped_envelope):
        a = {k for k in local_envelope if not k.startswith("_")}
        b = {k for k in swapped_envelope if not k.startswith("_")}
        assert a == b

    def test_local_vs_neural_op_top_level_keys(self, local_envelope, neural_op_envelope):
        a = {k for k in local_envelope if not k.startswith("_")}
        b = {k for k in neural_op_envelope if not k.startswith("_")}
        assert a == b


# ---------------------------------------------------------------------------
# Schema parity: output keys
# ---------------------------------------------------------------------------


class TestOutputSchemaParity:
    def test_local_vs_runpod_output_keys(self, local_envelope, runpod_envelope):
        assert set(local_envelope["output"].keys()) == set(runpod_envelope["output"].keys())

    def test_local_vs_swapped_output_keys(self, local_envelope, swapped_envelope):
        assert set(local_envelope["output"].keys()) == set(swapped_envelope["output"].keys())

    def test_local_vs_neural_op_output_keys(self, local_envelope, neural_op_envelope):
        assert set(local_envelope["output"].keys()) == set(neural_op_envelope["output"].keys())

    def test_all_validate_as_l4_output(
        self, local_envelope, runpod_envelope, swapped_envelope, neural_op_envelope
    ):
        for env in (local_envelope, runpod_envelope, swapped_envelope, neural_op_envelope):
            L4PhaseFieldOutput.model_validate(env["output"])


# ---------------------------------------------------------------------------
# Backend labels DIFFER (positive control on the swap)
# ---------------------------------------------------------------------------


class TestBackendLabelsDiffer:
    def test_local_backend_is_stub(self, local_envelope):
        assert local_envelope["tool_adapter"]["backend"] == "stub"

    def test_runpod_backend_is_runpod_mock(self, runpod_envelope):
        assert runpod_envelope["tool_adapter"]["backend"] == "runpod_mock"

    def test_swapped_engine_order_differs(self, local_envelope, swapped_envelope):
        # Engine string is "<primary>+<secondary>"; swapping primary and
        # secondary inverts the order -> different engine string.
        assert local_envelope["tool_adapter"]["engine"] != swapped_envelope["tool_adapter"]["engine"]


# ---------------------------------------------------------------------------
# Falsifier-driven schema-invariance assertion
# ---------------------------------------------------------------------------


class TestFalsifierAssertsSchemaInvariance:
    def test_falsifier_passes_on_local_vs_runpod(self, local_envelope, runpod_envelope):
        result = plug_swap_schema_invariance(local_envelope, runpod_envelope)
        assert result.status == "pass"

    def test_falsifier_passes_on_local_vs_swapped(self, local_envelope, swapped_envelope):
        result = plug_swap_schema_invariance(local_envelope, swapped_envelope)
        assert result.status == "pass"

    def test_falsifier_passes_on_classical_vs_neural_op(
        self, local_envelope, neural_op_envelope
    ):
        result = plug_swap_schema_invariance(local_envelope, neural_op_envelope)
        assert result.status == "pass"


# ---------------------------------------------------------------------------
# Single-adapter schema stability across calls
# ---------------------------------------------------------------------------


class TestPrismsPfStability:
    def test_two_calls_same_schema(self):
        adapter = PrismsPfAdapter()
        r1 = adapter.run(SPEC, _req("prisms-1"))
        r2 = adapter.run(SPEC, _req("prisms-2"))
        assert set(r1.keys()) == set(r2.keys())
        assert set(r1["output"].keys()) == set(r2["output"].keys())


class TestMooseStability:
    def test_two_calls_same_schema(self):
        adapter = MoosePhaseFieldAdapter()
        r1 = adapter.run(SPEC, _req("moose-1"))
        r2 = adapter.run(SPEC, _req("moose-2"))
        assert set(r1.keys()) == set(r2.keys())
        assert set(r1["output"].keys()) == set(r2["output"].keys())


class TestNeuralOpStability:
    def test_u_afno_vs_deeponet_same_schema(self):
        u_afno = NeuralOperatorPhaseFieldAdapter(architecture="u_afno").run(SPEC, _req("uafno"))
        deeponet = NeuralOperatorPhaseFieldAdapter(architecture="deeponet").run(
            SPEC, _req("deeponet")
        )
        assert set(u_afno.keys()) == set(deeponet.keys())
        assert set(u_afno["output"].keys()) == set(deeponet["output"].keys())
