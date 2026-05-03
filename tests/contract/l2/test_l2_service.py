"""Contract tests for L2 REST service — FastAPI TestClient on all endpoints."""

from __future__ import annotations

import pytest

# Guard: skip if fastapi is not installed.
fastapi = pytest.importorskip("fastapi", reason="fastapi required for contract tests")
httpx = pytest.importorskip("httpx", reason="httpx required for contract tests")

from fastapi.testclient import TestClient

from zer0pa_materials_workbench.boundary import RESEARCH_BOUNDARY

SI_STRUCTURE = {
    "lattice_vectors": [[3.84, 0.0, 0.0], [0.0, 3.84, 0.0], [0.0, 0.0, 3.84]],
    "species": ["Si", "Si"],
    "fractional_coords": [[0.0, 0.0, 0.0], [0.5, 0.5, 0.5]],
}

PREDICT_PAYLOAD = {
    "run_id": "run:contract/l2/si",
    "candidate_id": "candidate:Si:001",
    "campaign_id": "campaign:contract/001",
    "rights_claim_id": "rights:contract/001",
    "structure": SI_STRUCTURE,
}


@pytest.fixture(scope="module")
def client():
    from zer0pa_materials_workbench.services.l2_service import _make_app
    app = _make_app()
    with TestClient(app) as c:
        yield c


class TestHealthz:
    def test_healthz_200(self, client):
        resp = client.get("/v1/l2/healthz")
        assert resp.status_code == 200

    def test_healthz_status_ok(self, client):
        data = client.get("/v1/l2/healthz").json()
        assert data["status"] == "ok"

    def test_healthz_has_boundary(self, client):
        data = client.get("/v1/l2/healthz").json()
        assert data["research_boundary"] == RESEARCH_BOUNDARY

    def test_healthz_service_name(self, client):
        data = client.get("/v1/l2/healthz").json()
        assert data["service"] == "l2_mlip"


class TestPredictEndpoint:
    def test_predict_200(self, client):
        resp = client.post("/v1/l2/predict", json=PREDICT_PAYLOAD)
        assert resp.status_code == 200

    def test_predict_returns_envelope(self, client):
        data = client.post("/v1/l2/predict", json=PREDICT_PAYLOAD).json()
        assert "envelope" in data

    def test_predict_envelope_layer_is_L2(self, client):
        data = client.post("/v1/l2/predict", json=PREDICT_PAYLOAD).json()
        assert data["envelope"]["layer"] == "L2"

    def test_predict_envelope_boundary_verbatim(self, client):
        data = client.post("/v1/l2/predict", json=PREDICT_PAYLOAD).json()
        assert data["envelope"]["research_boundary"] == RESEARCH_BOUNDARY

    def test_predict_has_dpa_and_mace(self, client):
        data = client.post("/v1/l2/predict", json=PREDICT_PAYLOAD).json()
        models = {p["model"] for p in data["envelope"]["output"]["predictions"]}
        assert "DPA-3.1-3M" in models
        assert "MACE-MPA-0" in models

    def test_predict_routing_decision_present(self, client):
        data = client.post("/v1/l2/predict", json=PREDICT_PAYLOAD).json()
        routing = data["envelope"]["output"]["routing_decision"]
        assert routing in {"promote", "queue_dft", "hard_reject"}

    def test_predict_invalid_payload_422(self, client):
        resp = client.post("/v1/l2/predict", json={"bad": "payload"})
        assert resp.status_code == 422

    def test_predict_response_has_boundary(self, client):
        data = client.post("/v1/l2/predict", json=PREDICT_PAYLOAD).json()
        assert data["research_boundary"] == RESEARCH_BOUNDARY


class TestRelaxEndpoint:
    def test_relax_200(self, client):
        resp = client.post("/v1/l2/relax", json=PREDICT_PAYLOAD)
        assert resp.status_code == 200

    def test_relax_returns_envelope(self, client):
        data = client.post("/v1/l2/relax", json=PREDICT_PAYLOAD).json()
        assert "envelope" in data

    def test_relax_layer_is_L2(self, client):
        data = client.post("/v1/l2/relax", json=PREDICT_PAYLOAD).json()
        assert data["envelope"]["layer"] == "L2"

    def test_relax_has_relaxation_meta(self, client):
        data = client.post("/v1/l2/relax", json=PREDICT_PAYLOAD).json()
        meta = data["envelope"].get("_ensemble_meta", {})
        assert "relaxation" in meta

    def test_relax_volume_drift_present(self, client):
        data = client.post("/v1/l2/relax", json=PREDICT_PAYLOAD).json()
        meta = data["envelope"].get("_ensemble_meta", {})
        assert "volume_drift_pct" in meta

    def test_relax_space_group_agrees_present(self, client):
        data = client.post("/v1/l2/relax", json=PREDICT_PAYLOAD).json()
        meta = data["envelope"].get("_ensemble_meta", {})
        assert "space_group_agrees" in meta


class TestFinetuneEndpoint:
    @pytest.fixture
    def finetune_payload(self):
        return {
            "run_id": "run:contract/l2/finetune",
            "campaign_id": "campaign:contract/001",
            "rights_claim_id": "rights:contract/001",
            "base_model": "DPA-3.1-3M",
            "dft_configs": [
                {
                    "structure": SI_STRUCTURE,
                    "energy_eV": -10.2,
                    "forces": [[0.01, 0.0, 0.0], [0.0, 0.01, 0.0]],
                }
            ] * 10,
            "target_property": "ionic_conductivity",
            "gpu_budget_hours": 2.0,
        }

    def test_finetune_200(self, client, finetune_payload):
        resp = client.post("/v1/l2/finetune", json=finetune_payload)
        assert resp.status_code == 200

    def test_finetune_returns_job_id(self, client, finetune_payload):
        data = client.post("/v1/l2/finetune", json=finetune_payload).json()
        assert "job_id" in data

    def test_finetune_status_queued(self, client, finetune_payload):
        data = client.post("/v1/l2/finetune", json=finetune_payload).json()
        assert data["status"] == "queued"

    def test_finetune_backend_is_stub(self, client, finetune_payload):
        data = client.post("/v1/l2/finetune", json=finetune_payload).json()
        assert data["backend"] == "stub"

    def test_finetune_has_blocked_manifests(self, client, finetune_payload):
        data = client.post("/v1/l2/finetune", json=finetune_payload).json()
        assert len(data["blocked_manifests"]) >= 1

    def test_finetune_n_dft_configs(self, client, finetune_payload):
        data = client.post("/v1/l2/finetune", json=finetune_payload).json()
        assert data["n_dft_configs"] == 10

    def test_finetune_gpu_budget_respected(self, client, finetune_payload):
        data = client.post("/v1/l2/finetune", json=finetune_payload).json()
        assert data["gpu_budget_hours"] <= 4.0

    def test_finetune_boundary_present(self, client, finetune_payload):
        data = client.post("/v1/l2/finetune", json=finetune_payload).json()
        assert data["research_boundary"] == RESEARCH_BOUNDARY

    def test_finetune_invalid_gpu_budget_422(self, client, finetune_payload):
        payload = dict(finetune_payload)
        payload["gpu_budget_hours"] = 10.0  # > 4.0 limit
        resp = client.post("/v1/l2/finetune", json=payload)
        assert resp.status_code == 422
