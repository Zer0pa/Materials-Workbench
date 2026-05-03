"""Plug-swap tests for L3 adapters — local_stub vs runpod_mock schema parity.

PRD §Architecture Invariant: each backend must produce envelopes with
identical wire-level schema structure (same keys, same types) even though
values may differ.

For L3, the plug-swappable adapters are:
    - PyCalphadEquilibriumAdapter (sovereign open path)
    - EspeiBayesianFitAdapter      (sovereign open path)
    - SovereignCalphadPipeline     (composite)

PhaseForgePlus and Thermo-Calc are SPECIAL-CASE adapters (license-gated /
quarantine) and are exercised in their own unit tests.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from zer0pa_materials_workbench.adapters.l3 import (
    EspeiBayesianFitAdapter,
    L3CalphadRequest,
    PyCalphadEquilibriumAdapter,
    SovereignCalphadPipeline,
)
from zer0pa_materials_workbench.envelope import Envelope, L3CalphadOutput

REPO_ROOT = Path(__file__).resolve().parents[3]
CU_MG_TDB = REPO_ROOT / "fixtures" / "tdb" / "Cu-Mg-toy.tdb"


def _req(suffix: str = "stub") -> L3CalphadRequest:
    return L3CalphadRequest(
        run_id=f"run:swap/l3/{suffix}",
        candidate_id=f"candidate:Cu-Mg:{suffix}",
        campaign_id="campaign:swap/001",
        rights_claim_id="rights:swap/001",
        tdb_path=str(CU_MG_TDB),
        components=["CU", "MG"],
    )


# ---------------------------------------------------------------------------
# Equilibrium swap
# ---------------------------------------------------------------------------


class LocalEquilibriumRunner:
    """Local stub of PyCalphadEquilibriumAdapter."""

    def run(self, request: L3CalphadRequest) -> dict:
        return PyCalphadEquilibriumAdapter().run(request)


class RunpodMockEquilibriumRunner:
    """Simulates a runpod_mock equilibrium response.

    The wire shape MUST be identical to local. Only the backend label
    differs (mocked here by overriding tool_adapter.backend).
    """

    def run(self, request: L3CalphadRequest) -> dict:
        result = PyCalphadEquilibriumAdapter().run(request)
        result["tool_adapter"]["backend"] = "runpod_mock"
        return result


@pytest.fixture
def local_equilibrium_envelope() -> dict:
    return LocalEquilibriumRunner().run(_req("local"))


@pytest.fixture
def runpod_equilibrium_envelope() -> dict:
    return RunpodMockEquilibriumRunner().run(_req("runpod"))


class TestEquilibriumSchemaParity:
    def test_local_validates(self, local_equilibrium_envelope):
        clean = {k: v for k, v in local_equilibrium_envelope.items() if not k.startswith("_")}
        env = Envelope.model_validate(clean)
        assert env.layer == "L3"

    def test_runpod_validates(self, runpod_equilibrium_envelope):
        clean = {k: v for k, v in runpod_equilibrium_envelope.items() if not k.startswith("_")}
        env = Envelope.model_validate(clean)
        assert env.layer == "L3"

    def test_top_level_keys_match(self, local_equilibrium_envelope, runpod_equilibrium_envelope):
        local_keys = set(local_equilibrium_envelope.keys())
        runpod_keys = set(runpod_equilibrium_envelope.keys())
        assert local_keys == runpod_keys

    def test_output_keys_match(self, local_equilibrium_envelope, runpod_equilibrium_envelope):
        local_out = set(local_equilibrium_envelope["output"].keys())
        runpod_out = set(runpod_equilibrium_envelope["output"].keys())
        assert local_out == runpod_out

    def test_both_layer_l3(self, local_equilibrium_envelope, runpod_equilibrium_envelope):
        assert local_equilibrium_envelope["layer"] == "L3"
        assert runpod_equilibrium_envelope["layer"] == "L3"

    def test_backend_labels_differ(self, local_equilibrium_envelope, runpod_equilibrium_envelope):
        assert local_equilibrium_envelope["tool_adapter"]["backend"] == "stub"
        assert runpod_equilibrium_envelope["tool_adapter"]["backend"] == "runpod_mock"

    def test_both_outputs_validate(self, local_equilibrium_envelope, runpod_equilibrium_envelope):
        L3CalphadOutput.model_validate(local_equilibrium_envelope["output"])
        L3CalphadOutput.model_validate(runpod_equilibrium_envelope["output"])


# ---------------------------------------------------------------------------
# ESPEI fit swap
# ---------------------------------------------------------------------------


class LocalEspeiRunner:
    def run(self, request: L3CalphadRequest) -> dict:
        return EspeiBayesianFitAdapter().run(request)


class RunpodMockEspeiRunner:
    def run(self, request: L3CalphadRequest) -> dict:
        result = EspeiBayesianFitAdapter().run(request)
        result["tool_adapter"]["backend"] = "runpod_mock"
        return result


@pytest.fixture
def local_espei_envelope() -> dict:
    return LocalEspeiRunner().run(_req("espei-local"))


@pytest.fixture
def runpod_espei_envelope() -> dict:
    return RunpodMockEspeiRunner().run(_req("espei-runpod"))


class TestEspeiSchemaParity:
    def test_local_validates(self, local_espei_envelope):
        clean = {k: v for k, v in local_espei_envelope.items() if not k.startswith("_")}
        Envelope.model_validate(clean)

    def test_runpod_validates(self, runpod_espei_envelope):
        clean = {k: v for k, v in runpod_espei_envelope.items() if not k.startswith("_")}
        Envelope.model_validate(clean)

    def test_top_level_keys_match(self, local_espei_envelope, runpod_espei_envelope):
        assert set(local_espei_envelope.keys()) == set(runpod_espei_envelope.keys())

    def test_output_keys_match(self, local_espei_envelope, runpod_espei_envelope):
        assert set(local_espei_envelope["output"].keys()) == set(
            runpod_espei_envelope["output"].keys()
        )

    def test_both_diagnostics_keys_match(self, local_espei_envelope, runpod_espei_envelope):
        local_diag = set(local_espei_envelope["output"]["espei_diagnostics"].keys())
        runpod_diag = set(runpod_espei_envelope["output"]["espei_diagnostics"].keys())
        assert local_diag == runpod_diag

    def test_both_have_information_geometry_note(self, local_espei_envelope, runpod_espei_envelope):
        assert "_information_geometry_note" in local_espei_envelope
        assert "_information_geometry_note" in runpod_espei_envelope


# ---------------------------------------------------------------------------
# Sovereign pipeline swap
# ---------------------------------------------------------------------------


class TestSovereignPipelineSchemaStability:
    """Sovereign pipeline schema must be stable across calls."""

    def test_two_calls_same_request_same_keys(self):
        pipeline = SovereignCalphadPipeline()
        envs_a = pipeline.run_with_chain(_req("a"))
        envs_b = pipeline.run_with_chain(_req("b"))
        # Different requests but same chain shape.
        assert len(envs_a) == len(envs_b)
        for a, b in zip(envs_a, envs_b, strict=False):
            assert set(a.keys()) == set(b.keys())
            assert set(a["output"].keys()) == set(b["output"].keys())

    def test_pipeline_envelopes_validate(self):
        pipeline = SovereignCalphadPipeline()
        envs = pipeline.run_with_chain(_req())
        for env in envs:
            clean = {k: v for k, v in env.items() if not k.startswith("_")}
            Envelope.model_validate(clean)


# ---------------------------------------------------------------------------
# Adapter schema stability
# ---------------------------------------------------------------------------


class TestEquilibriumAdapterSchemaStability:
    def test_two_calls_same_request_same_schema(self):
        adapter = PyCalphadEquilibriumAdapter()
        r1 = adapter.run(_req())
        r2 = adapter.run(_req())
        assert set(r1.keys()) == set(r2.keys())
        assert set(r1["output"].keys()) == set(r2["output"].keys())


class TestEspeiAdapterSchemaStability:
    def test_two_calls_same_request_same_schema(self):
        adapter = EspeiBayesianFitAdapter()
        r1 = adapter.run(_req())
        r2 = adapter.run(_req())
        assert set(r1.keys()) == set(r2.keys())
        assert set(r1["output"].keys()) == set(r2["output"].keys())
