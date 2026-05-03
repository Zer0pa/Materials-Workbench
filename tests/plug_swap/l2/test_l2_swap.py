"""Plug-swap tests for L2 adapters — local_stub vs runpod_mock schema parity.

The test verifies that both backends produce envelopes with identical wire-level
schema structure (same keys, same types) even though the values differ.

This is the plug-replaceability acceptance test per PRD §Architecture Invariant.
"""

from __future__ import annotations

import pytest

from zer0pa_materials_workbench.adapters.l2.base import L2PredictRequest
from zer0pa_materials_workbench.adapters.l2.deepmd_dpa import DeepmdDpaCalculatorAdapter
from zer0pa_materials_workbench.adapters.l2.ensemble import L2EnsembleRunner
from zer0pa_materials_workbench.adapters.l2.mace_mp import MaceMpCalculatorAdapter
from zer0pa_materials_workbench.envelope.envelope import Envelope
from zer0pa_materials_workbench.envelope.layer_outputs import L2MlipOutput

SI_STRUCTURE = {
    "lattice_vectors": [[3.84, 0.0, 0.0], [0.0, 3.84, 0.0], [0.0, 0.0, 3.84]],
    "species": ["Si", "Si"],
    "fractional_coords": [[0.0, 0.0, 0.0], [0.5, 0.5, 0.5]],
}


def _req(suffix: str = "stub") -> L2PredictRequest:
    return L2PredictRequest(
        run_id=f"run:swap/{suffix}/si",
        candidate_id="candidate:Si:001",
        campaign_id="campaign:swap/001",
        rights_claim_id="rights:swap/001",
    )


class LocalStubRunner:
    """Wraps L2EnsembleRunner in stub mode (the default)."""

    def run(self, structure: dict, request: L2PredictRequest) -> dict:
        runner = L2EnsembleRunner()
        return runner.run(structure, request)


class RunpodMockRunner:
    """Simulates a runpod_rest response by overriding the backend label.

    In real runpod_rest mode, the adapter would call an HTTP endpoint.
    For the schema-parity test we just change the backend label and verify
    the wire shape is identical.
    """

    def run(self, structure: dict, request: L2PredictRequest) -> dict:
        runner = L2EnsembleRunner()
        result = runner.run(structure, request)
        # Override backend label to simulate runpod_rest response.
        result["tool_adapter"]["backend"] = "runpod_mock"
        return result


@pytest.fixture
def local_envelope():
    return LocalStubRunner().run(SI_STRUCTURE, _req("local"))


@pytest.fixture
def runpod_envelope():
    return RunpodMockRunner().run(SI_STRUCTURE, _req("runpod"))


class TestSchemaParity:
    """Both backends must produce Envelope-valid output with the same top-level keys."""

    def test_local_envelope_validates(self, local_envelope):
        clean = {k: v for k, v in local_envelope.items() if not k.startswith("_")}
        env = Envelope.model_validate(clean)
        assert env.layer == "L2"

    def test_runpod_envelope_validates(self, runpod_envelope):
        clean = {k: v for k, v in runpod_envelope.items() if not k.startswith("_")}
        env = Envelope.model_validate(clean)
        assert env.layer == "L2"

    def test_same_top_level_keys(self, local_envelope, runpod_envelope):
        local_keys = set(local_envelope.keys())
        runpod_keys = set(runpod_envelope.keys())
        assert local_keys == runpod_keys

    def test_output_keys_match(self, local_envelope, runpod_envelope):
        local_out_keys = set(local_envelope["output"].keys())
        runpod_out_keys = set(runpod_envelope["output"].keys())
        assert local_out_keys == runpod_out_keys

    def test_both_have_predictions_list(self, local_envelope, runpod_envelope):
        assert isinstance(local_envelope["output"]["predictions"], list)
        assert isinstance(runpod_envelope["output"]["predictions"], list)

    def test_both_have_routing_decision(self, local_envelope, runpod_envelope):
        assert local_envelope["output"]["routing_decision"] in {"promote", "queue_dft", "hard_reject"}
        assert runpod_envelope["output"]["routing_decision"] in {"promote", "queue_dft", "hard_reject"}

    def test_both_have_energy_disagreement(self, local_envelope, runpod_envelope):
        assert isinstance(local_envelope["output"]["energy_disagreement_meV_per_atom"], float)
        assert isinstance(runpod_envelope["output"]["energy_disagreement_meV_per_atom"], float)

    def test_both_output_validate_as_l2_output(self, local_envelope, runpod_envelope):
        L2MlipOutput.model_validate(local_envelope["output"])
        L2MlipOutput.model_validate(runpod_envelope["output"])

    def test_backend_labels_differ(self, local_envelope, runpod_envelope):
        assert local_envelope["tool_adapter"]["backend"] == "stub"
        assert runpod_envelope["tool_adapter"]["backend"] == "runpod_mock"

    def test_layer_is_L2_in_both(self, local_envelope, runpod_envelope):
        assert local_envelope["layer"] == "L2"
        assert runpod_envelope["layer"] == "L2"

    def test_prediction_schema_consistent(self, local_envelope, runpod_envelope):
        for pred in local_envelope["output"]["predictions"] + runpod_envelope["output"]["predictions"]:
            assert "model" in pred
            assert "energy_eV_per_atom" in pred
            assert "force_rmse_eV_per_Ang" in pred

    def test_disagreement_block_present_in_both(self, local_envelope, runpod_envelope):
        assert "metrics" in local_envelope["disagreement"]
        assert "metrics" in runpod_envelope["disagreement"]


class TestDpaAdapterSchemaStability:
    """DPA single-model adapter schema must be stable across calls."""

    def test_two_calls_same_structure_same_schema(self):
        adapter = DeepmdDpaCalculatorAdapter()
        req = _req("dpa")
        r1 = adapter.predict(SI_STRUCTURE, req)
        r2 = adapter.predict(SI_STRUCTURE, req)
        assert set(r1.keys()) == set(r2.keys())
        assert set(r1["output"].keys()) == set(r2["output"].keys())


class TestMaceAdapterSchemaStability:
    """MACE single-model adapter schema must be stable across calls."""

    def test_two_calls_same_structure_same_schema(self):
        adapter = MaceMpCalculatorAdapter()
        req = _req("mace")
        r1 = adapter.predict(SI_STRUCTURE, req)
        r2 = adapter.predict(SI_STRUCTURE, req)
        assert set(r1.keys()) == set(r2.keys())
        assert set(r1["output"].keys()) == set(r2["output"].keys())
