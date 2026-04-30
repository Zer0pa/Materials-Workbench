"""Contract tests for L4 REST service — FastAPI TestClient on all endpoints."""

from __future__ import annotations

import pytest

# Skip if fastapi/httpx is not installed
fastapi = pytest.importorskip("fastapi", reason="fastapi required for contract tests")
httpx = pytest.importorskip("httpx", reason="httpx required for contract tests")

from fastapi.testclient import TestClient

from zer0pa_materials.boundary import RESEARCH_BOUNDARY


# ---------------------------------------------------------------------------
# Sample payloads
# ---------------------------------------------------------------------------

PHASE_FIELD_SPEC = {
    "equation": "cahn_hilliard",
    "domain": {
        "dimension": 2,
        "extents": [10.0, 10.0],
        "units": "nm",
        "periodic": [True, True, True],
    },
    "mesh": {"nodes": [16, 16], "refinement_level": 0},
    "materials": [{"phase_name": "alpha", "initial_fraction": 0.5}],
    "time_steps": 10,
    "dt": 0.01,
    "time_units": "s",
    "n_dumps": 6,
    "initial_condition": "fixture_default",
    "initial_seed": 42,
    "extra": {},
}

KMC_SPEC = {
    "lattice": "square",
    "grid_size": [12, 12],
    "energy_model": "potts",
    "n_states": 4,
    "n_steps": 20,
    "n_dumps": 5,
    "temperature_K": 0.0,
    "initial_seed": 42,
    "extra": {},
}

RUN_PAYLOAD = {
    "run_id": "run:contract/l4/ch",
    "candidate_id": "candidate:contract/001",
    "campaign_id": "campaign:contract/001",
    "rights_claim_id": "rights:contract/001",
    "spec": PHASE_FIELD_SPEC,
}

KMC_PAYLOAD = {
    "run_id": "run:contract/l4/kmc",
    "candidate_id": "candidate:contract/001",
    "campaign_id": "campaign:contract/001",
    "rights_claim_id": "rights:contract/001",
    "spec": KMC_SPEC,
}

NEURAL_OP_PAYLOAD = {
    "run_id": "run:contract/l4/neural-op",
    "candidate_id": "candidate:contract/001",
    "campaign_id": "campaign:contract/001",
    "rights_claim_id": "rights:contract/001",
    "spec": PHASE_FIELD_SPEC,
    "architecture": "u_afno",
}


@pytest.fixture(scope="module")
def client():
    from zer0pa_materials.services.l4_service import _make_app
    app = _make_app()
    with TestClient(app) as c:
        yield c


class TestHealthz:
    def test_healthz_200(self, client):
        resp = client.get("/v1/l4/healthz")
        assert resp.status_code == 200

    def test_healthz_status_ok(self, client):
        data = client.get("/v1/l4/healthz").json()
        assert data["status"] == "ok"

    def test_healthz_has_boundary(self, client):
        data = client.get("/v1/l4/healthz").json()
        assert data["research_boundary"] == RESEARCH_BOUNDARY

    def test_healthz_service_name(self, client):
        data = client.get("/v1/l4/healthz").json()
        assert data["service"] == "l4_phase_field"

    def test_healthz_lists_adapters(self, client):
        data = client.get("/v1/l4/healthz").json()
        assert "adapters" in data
        assert "phase_field_ensemble" in data["adapters"]


class TestRunsEndpoint:
    def test_runs_200(self, client):
        resp = client.post("/v1/l4/runs", json=RUN_PAYLOAD)
        assert resp.status_code == 200

    def test_runs_returns_envelope(self, client):
        data = client.post("/v1/l4/runs", json=RUN_PAYLOAD).json()
        assert "envelope" in data

    def test_runs_envelope_layer_L4(self, client):
        data = client.post("/v1/l4/runs", json=RUN_PAYLOAD).json()
        assert data["envelope"]["layer"] == "L4"

    def test_runs_envelope_boundary(self, client):
        data = client.post("/v1/l4/runs", json=RUN_PAYLOAD).json()
        assert data["envelope"]["research_boundary"] == RESEARCH_BOUNDARY

    def test_runs_disagreement_present(self, client):
        data = client.post("/v1/l4/runs", json=RUN_PAYLOAD).json()
        assert "metrics" in data["envelope"]["disagreement"]
        assert len(data["envelope"]["disagreement"]["metrics"]) >= 1

    def test_runs_invalid_payload_422(self, client):
        resp = client.post("/v1/l4/runs", json={"bad": "payload"})
        assert resp.status_code == 422

    def test_runs_response_has_boundary(self, client):
        data = client.post("/v1/l4/runs", json=RUN_PAYLOAD).json()
        assert data["research_boundary"] == RESEARCH_BOUNDARY

    def test_runs_grand_potential_400(self, client):
        bad_payload = {**RUN_PAYLOAD}
        bad_spec = dict(PHASE_FIELD_SPEC)
        bad_spec["equation"] = "grand_potential"
        bad_payload = {**RUN_PAYLOAD, "spec": bad_spec}
        resp = client.post("/v1/l4/runs", json=bad_payload)
        assert resp.status_code == 400


class TestKmcEndpoint:
    def test_kmc_200(self, client):
        resp = client.post("/v1/l4/kmc/runs", json=KMC_PAYLOAD)
        assert resp.status_code == 200

    def test_kmc_envelope_layer_L4(self, client):
        data = client.post("/v1/l4/kmc/runs", json=KMC_PAYLOAD).json()
        assert data["envelope"]["layer"] == "L4"

    def test_kmc_t0_monotonic_passes(self, client):
        data = client.post("/v1/l4/kmc/runs", json=KMC_PAYLOAD).json()
        assert data["envelope"]["output"]["spparks_potts_energy_monotonic"] is True

    def test_kmc_invalid_payload_422(self, client):
        resp = client.post("/v1/l4/kmc/runs", json={"bad": "payload"})
        assert resp.status_code == 422

    def test_kmc_response_has_boundary(self, client):
        data = client.post("/v1/l4/kmc/runs", json=KMC_PAYLOAD).json()
        assert data["research_boundary"] == RESEARCH_BOUNDARY


class TestNeuralOpPredictEndpoint:
    def test_neural_op_200(self, client):
        resp = client.post("/v1/l4/neural-op/predict", json=NEURAL_OP_PAYLOAD)
        assert resp.status_code == 200

    def test_neural_op_envelope_layer_L4(self, client):
        data = client.post("/v1/l4/neural-op/predict", json=NEURAL_OP_PAYLOAD).json()
        assert data["envelope"]["layer"] == "L4"

    def test_neural_op_meta_advisory(self, client):
        data = client.post("/v1/l4/neural-op/predict", json=NEURAL_OP_PAYLOAD).json()
        assert "advisory" in data["envelope"]["_l4_meta"]

    def test_neural_op_invalid_architecture_400(self, client):
        bad_payload = dict(NEURAL_OP_PAYLOAD)
        bad_payload["architecture"] = "invalid_arch"
        resp = client.post("/v1/l4/neural-op/predict", json=bad_payload)
        assert resp.status_code == 400

    def test_neural_op_deeponet_works(self, client):
        deeponet_payload = dict(NEURAL_OP_PAYLOAD)
        deeponet_payload["architecture"] = "deeponet"
        deeponet_payload["run_id"] = "run:contract/l4/neural-op-deeponet"
        resp = client.post("/v1/l4/neural-op/predict", json=deeponet_payload)
        assert resp.status_code == 200

    def test_neural_op_response_has_boundary(self, client):
        data = client.post("/v1/l4/neural-op/predict", json=NEURAL_OP_PAYLOAD).json()
        assert data["research_boundary"] == RESEARCH_BOUNDARY
