"""Contract tests for the L1 DFT REST stub service (FastAPI TestClient)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from zer0pa_materials_workbench import read_fixture
from zer0pa_materials_workbench.envelope import cif_hash_from_text
from zer0pa_materials_workbench.services.l1_service import app

H2_CIF = read_fixture("structures", "H2", "structure.cif")
H2_HASH = cif_hash_from_text(H2_CIF)


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_healthz_returns_200(client: TestClient) -> None:
    resp = client.get("/v1/l1/healthz")
    assert resp.status_code == 200


def test_healthz_body(client: TestClient) -> None:
    resp = client.get("/v1/l1/healthz")
    data = resp.json()
    assert data["status"] == "ok"
    assert "research_boundary" in data
    assert "backend" in data


def test_submit_job_returns_201(client: TestClient) -> None:
    payload = {
        "structure_cif": H2_CIF,
        "structure_hash": H2_HASH,
        "functional": "PBE",
        "kpoint_mesh": [1, 1, 1],
        "campaign_id": "campaign:test-l1-svc",
        "candidate_id": "candidate:test-l1-svc",
    }
    resp = client.post("/v1/l1/dft/jobs", json=payload)
    assert resp.status_code == 201


def test_submit_job_response_body(client: TestClient) -> None:
    payload = {
        "structure_cif": H2_CIF,
        "structure_hash": H2_HASH,
        "campaign_id": "campaign:test-l1-svc",
        "candidate_id": "candidate:test-l1-svc",
    }
    resp = client.post("/v1/l1/dft/jobs", json=payload)
    data = resp.json()
    assert data["status"] == "completed"
    assert "job_id" in data
    assert data["envelope"] is not None


def test_submit_job_envelope_has_layer(client: TestClient) -> None:
    payload = {
        "structure_cif": H2_CIF,
        "structure_hash": H2_HASH,
        "campaign_id": "campaign:test-l1-svc",
        "candidate_id": "candidate:test-l1-svc",
    }
    resp = client.post("/v1/l1/dft/jobs", json=payload)
    envelope = resp.json()["envelope"]
    assert envelope["layer"] == "L1"


def test_submit_job_envelope_has_boundary(client: TestClient) -> None:
    from zer0pa_materials_workbench.boundary import RESEARCH_BOUNDARY
    payload = {
        "structure_cif": H2_CIF,
        "structure_hash": H2_HASH,
        "campaign_id": "campaign:test-l1-svc",
        "candidate_id": "candidate:test-l1-svc",
    }
    resp = client.post("/v1/l1/dft/jobs", json=payload)
    envelope = resp.json()["envelope"]
    assert envelope["research_boundary"] == RESEARCH_BOUNDARY


def test_get_job_status(client: TestClient) -> None:
    payload = {
        "structure_cif": H2_CIF,
        "structure_hash": H2_HASH,
        "campaign_id": "campaign:test-l1-svc",
        "candidate_id": "candidate:test-l1-svc",
    }
    post_resp = client.post("/v1/l1/dft/jobs", json=payload)
    job_id = post_resp.json()["job_id"]

    get_resp = client.get(f"/v1/jobs/{job_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["status"] == "completed"


def test_get_job_not_found(client: TestClient) -> None:
    resp = client.get("/v1/jobs/job:l1:nonexistent")
    assert resp.status_code == 404


def test_get_artifacts(client: TestClient) -> None:
    payload = {
        "structure_cif": H2_CIF,
        "structure_hash": H2_HASH,
        "campaign_id": "campaign:test-l1-svc",
        "candidate_id": "candidate:test-l1-svc",
    }
    post_resp = client.post("/v1/l1/dft/jobs", json=payload)
    job_id = post_resp.json()["job_id"]

    art_resp = client.get(f"/v1/jobs/{job_id}/artifacts")
    assert art_resp.status_code == 200
    artifacts = art_resp.json()
    assert len(artifacts) >= 1
    assert any(a["kind"] == "envelope" for a in artifacts)


def test_cancel_completed_job_returns_409(client: TestClient) -> None:
    payload = {
        "structure_cif": H2_CIF,
        "structure_hash": H2_HASH,
        "campaign_id": "campaign:test-l1-svc",
        "candidate_id": "candidate:test-l1-svc",
    }
    post_resp = client.post("/v1/l1/dft/jobs", json=payload)
    job_id = post_resp.json()["job_id"]

    cancel_resp = client.post(f"/v1/jobs/{job_id}/cancel")
    assert cancel_resp.status_code == 409


def test_cancel_nonexistent_job_404(client: TestClient) -> None:
    resp = client.post("/v1/jobs/job:l1:nothere/cancel")
    assert resp.status_code == 404
