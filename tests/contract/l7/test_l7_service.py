"""Contract tests for the L7 REST stub service (FastAPI)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from zer0pa_materials_workbench.services.l7_service import create_l7_app


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    app = create_l7_app()
    # Reset in-memory state between tests.
    from zer0pa_materials_workbench.services import l7_service as svc

    svc._ACTIVE_CAMPAIGNS.clear()
    return TestClient(app)


@pytest.fixture
def runtime_paths(tmp_path: Path) -> tuple[str, str]:
    return (str(tmp_path / "audit"), str(tmp_path / "kg.sqlite"))


def test_healthz(client):
    resp = client.get("/v1/l7/healthz")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["layer"] == "L7"
    assert "research_boundary" in body


def test_create_campaign(client, runtime_paths):
    audit_dir, kg_path = runtime_paths
    resp = client.post(
        "/v1/l7/campaigns",
        json={
            "campaign_id": "campaign:test/c1",
            "tenant": "test",
            "objective": "ionic > 1e-3 S/cm",
            "audit_dir": audit_dir,
            "kg_path": kg_path,
        },
    )
    assert resp.status_code == 200, resp.text
    env = resp.json()
    assert env["layer"] == "L7"
    assert env["campaign_id"] == "campaign:test/c1"


def test_create_then_state(client, runtime_paths):
    audit_dir, kg_path = runtime_paths
    client.post(
        "/v1/l7/campaigns",
        json={
            "campaign_id": "campaign:test/c2",
            "tenant": "test",
            "objective": "x",
            "audit_dir": audit_dir,
            "kg_path": kg_path,
        },
    )
    resp = client.get("/v1/l7/campaigns/state", params={"campaign_id": "campaign:test/c2"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["campaign_id"] == "campaign:test/c2"


def test_dispatch(client, runtime_paths):
    audit_dir, kg_path = runtime_paths
    client.post(
        "/v1/l7/campaigns",
        json={
            "campaign_id": "campaign:test/c3",
            "tenant": "test",
            "objective": "x",
            "audit_dir": audit_dir,
            "kg_path": kg_path,
        },
    )
    resp = client.post(
        "/v1/l7/campaigns/dispatch",
        json={
            "campaign_id": "campaign:test/c3",
            "candidate_ids": ["candidate:test/x", "candidate:test/y"],
        },
    )
    assert resp.status_code == 200, resp.text
    envs = resp.json()
    assert len(envs) == 2


def test_acquire(client, runtime_paths):
    audit_dir, kg_path = runtime_paths
    client.post(
        "/v1/l7/campaigns",
        json={
            "campaign_id": "campaign:test/c4",
            "tenant": "test",
            "objective": "x",
            "audit_dir": audit_dir,
            "kg_path": kg_path,
        },
    )
    resp = client.post(
        "/v1/l7/campaigns/acquire",
        json={
            "campaign_id": "campaign:test/c4",
            "candidates": [
                {
                    "candidate_id": "candidate:test/x",
                    "predicted_value": 0.5,
                    "posterior_variance": 0.05,
                    "fidelity_options": {"L2_stub": 1.0, "L1_DFT_PBE": 10.0},
                }
            ],
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "acquisition" in body
    assert body["acquisition"]["acquisition_function"] in (
        "qMultiFidelityKnowledgeGradient",
        "qLogExpectedImprovement",
    )


def test_acquire_qei_forbidden_returns_400(client, runtime_paths):
    audit_dir, kg_path = runtime_paths
    client.post(
        "/v1/l7/campaigns",
        json={
            "campaign_id": "campaign:test/c5",
            "tenant": "test",
            "objective": "x",
            "audit_dir": audit_dir,
            "kg_path": kg_path,
        },
    )
    resp = client.post(
        "/v1/l7/campaigns/acquire",
        json={
            "campaign_id": "campaign:test/c5",
            "candidates": [
                {
                    "candidate_id": "candidate:test/x",
                    "predicted_value": 0.5,
                    "posterior_variance": 0.05,
                    "fidelity_options": {"L2_stub": 1.0},
                }
            ],
            "requested_acquisition": "qExpectedImprovement",
            "allow_legacy_qei": False,
        },
    )
    assert resp.status_code == 400


def test_promote_unknown_candidate_emits_envelope(client, runtime_paths):
    audit_dir, kg_path = runtime_paths
    client.post(
        "/v1/l7/campaigns",
        json={
            "campaign_id": "campaign:test/c6",
            "tenant": "test",
            "objective": "x",
            "audit_dir": audit_dir,
            "kg_path": kg_path,
        },
    )
    resp = client.post(
        "/v1/l7/campaigns/promote-candidate",
        json={
            "campaign_id": "campaign:test/c6",
            "candidate_id": "candidate:test/x",
            "rights_claim_id": "rights:test:c1",
            "aggregate_disagreement_score": 0.1,
            "layer_envelopes": [],
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    # No layer envelopes → gate is blocked (not fail) due to expected_layers default.
    assert body["verdict"]["overall"] in ("blocked", "fail")


def test_resume_returns_state(client, runtime_paths):
    audit_dir, kg_path = runtime_paths
    client.post(
        "/v1/l7/campaigns",
        json={
            "campaign_id": "campaign:test/c7",
            "tenant": "test",
            "objective": "x",
            "audit_dir": audit_dir,
            "kg_path": kg_path,
        },
    )
    # Clear in-memory and resume.
    from zer0pa_materials_workbench.services import l7_service as svc

    svc._ACTIVE_CAMPAIGNS.clear()
    resp = client.post(
        "/v1/l7/campaigns/resume",
        json={
            "campaign_id": "campaign:test/c7",
            "audit_dir": audit_dir,
            "kg_path": kg_path,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["campaign_id"] == "campaign:test/c7"


def test_alabos_compile_recipe_only(client):
    resp = client.post(
        "/v1/l7/alabos/compile-protocol",
        json={"candidate_id": "candidate:test/x", "alabos_mode": "recipe_only", "recipe": {}},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["protocol"]["alabos_mode"] == "recipe_only"
    assert body["protocol"]["hardware_executable"] is False


def test_alabos_compile_executable_in_recipe_only_returns_400(client):
    resp = client.post(
        "/v1/l7/alabos/compile-protocol",
        json={
            "candidate_id": "candidate:test/x",
            "alabos_mode": "recipe_only",
            "recipe": {"hardware_executable": True},
        },
    )
    assert resp.status_code == 400


def test_resume_unknown_campaign_404(client, runtime_paths):
    audit_dir, kg_path = runtime_paths
    resp = client.post(
        "/v1/l7/campaigns/resume",
        json={
            "campaign_id": "campaign:nope",
            "audit_dir": audit_dir,
            "kg_path": kg_path,
        },
    )
    assert resp.status_code == 404
