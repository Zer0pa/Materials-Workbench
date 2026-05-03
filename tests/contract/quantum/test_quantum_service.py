"""Contract tests for the Quantum VQE REST stub service."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from zer0pa_materials_workbench.services.quantum_service import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_healthz_returns_200(client: TestClient) -> None:
    resp = client.get("/v1/quantum/healthz")
    assert resp.status_code == 200


def test_healthz_body(client: TestClient) -> None:
    resp = client.get("/v1/quantum/healthz")
    data = resp.json()
    assert data["status"] == "ok"
    assert "research_boundary" in data


def test_submit_h2_vqe_job(client: TestClient) -> None:
    payload = {
        "system": "H2",
        "slot": "L1-VQE",
        "campaign_id": "campaign:test-vqe-svc",
        "candidate_id": "candidate:test-vqe-svc",
    }
    resp = client.post("/v1/l1/quantum/vqe/jobs", json=payload)
    assert resp.status_code == 201


def test_submit_h2_job_completes(client: TestClient) -> None:
    payload = {
        "system": "H2",
        "slot": "L1-VQE",
        "campaign_id": "campaign:test-vqe-svc",
        "candidate_id": "candidate:test-vqe-svc",
    }
    resp = client.post("/v1/l1/quantum/vqe/jobs", json=payload)
    data = resp.json()
    assert data["status"] == "completed"
    assert data["envelope"] is not None


def test_submit_h2_job_envelope_layer(client: TestClient) -> None:
    payload = {
        "system": "H2",
        "slot": "L1-VQE",
        "campaign_id": "campaign:test-vqe-svc",
        "candidate_id": "candidate:test-vqe-svc",
    }
    resp = client.post("/v1/l1/quantum/vqe/jobs", json=payload)
    envelope = resp.json()["envelope"]
    assert envelope["layer"] == "L1"


def test_submit_lih_vqe_job(client: TestClient) -> None:
    payload = {
        "system": "LiH",
        "slot": "L1-VQE",
        "campaign_id": "campaign:test-vqe-svc-lih",
        "candidate_id": "candidate:test-vqe-svc-lih",
    }
    resp = client.post("/v1/l1/quantum/vqe/jobs", json=payload)
    assert resp.status_code == 201
    assert resp.json()["status"] == "completed"


def test_submit_unimplemented_slot_returns_blocked(client: TestClient) -> None:
    payload = {
        "system": "H2",
        "slot": "L4-QAOA",
        "campaign_id": "campaign:test-vqe-svc",
        "candidate_id": "candidate:test-vqe-svc",
    }
    resp = client.post("/v1/l1/quantum/vqe/jobs", json=payload)
    data = resp.json()
    assert data["status"] == "blocked"
    assert "L4-QAOA" in data.get("message", "")


def test_submit_l7_qaa_returns_blocked(client: TestClient) -> None:
    payload = {
        "system": "H2",
        "slot": "L7-QAA",
        "campaign_id": "campaign:test-vqe-svc",
        "candidate_id": "candidate:test-vqe-svc",
    }
    resp = client.post("/v1/l1/quantum/vqe/jobs", json=payload)
    data = resp.json()
    assert data["status"] == "blocked"
