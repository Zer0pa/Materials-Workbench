"""Contract tests for the IonicTransportService FastAPI app.

Every endpoint is exercised through ``fastapi.testclient.TestClient``
so the service's wire interface is fully covered without a live server.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from zer0pa_materials_workbench.services.ionic_transport_service import (
    IONIC_SERVICE_NAME,
    IONIC_SERVICE_VERSION,
    create_ionic_app,
)


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(create_ionic_app())


@pytest.fixture(scope="module")
def llzo_payload() -> dict:
    return {
        "structure_hash": "sha256:d45cb2bfe5e76b86b365e1402e118ed32280049a62345c903558c6cfac04ef19",
        "fixture_id": "fixture:LLZO_cubic:d45cb2bf",
        "candidate_id": "candidate:LLZO/cubic",
        "campaign_id": "campaign:contract-test",
    }


def test_healthz(client: TestClient) -> None:
    r = client.get("/v1/ionic/healthz")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["service"] == IONIC_SERVICE_NAME
    assert body["version"] == IONIC_SERVICE_VERSION


def test_neb_endpoint(client: TestClient, llzo_payload: dict) -> None:
    r = client.post("/v1/ionic/neb", json=llzo_payload)
    assert r.status_code == 200
    body = r.json()
    assert body["layer"] == "ionic"
    assert body["output"]["migration_barrier_eV"] is not None
    assert 0.28 <= body["output"]["migration_barrier_eV"] <= 0.32


def test_md_diffusion_endpoint(client: TestClient, llzo_payload: dict) -> None:
    r = client.post("/v1/ionic/md-diffusion", json=llzo_payload)
    assert r.status_code == 200
    body = r.json()
    assert body["output"]["diffusion_coefficient_cm2_per_s"] > 0
    assert body["output"]["nernst_einstein_conductivity_S_per_cm"] > 0


def test_aimd_diffusion_endpoint(client: TestClient, llzo_payload: dict) -> None:
    r = client.post("/v1/ionic/aimd-diffusion", json=llzo_payload)
    assert r.status_code == 200
    body = r.json()
    assert body["output"]["diffusion_coefficient_cm2_per_s"] > 0


def test_arrhenius_fit_endpoint(client: TestClient) -> None:
    payload = {
        "temperatures_K": [300.0, 400.0, 500.0],
        "conductivities_S_per_cm": [1e-3, 5e-3, 1e-2],
        "candidate_id": "candidate:contract/arrhenius",
        "campaign_id": "campaign:contract-test",
    }
    r = client.post("/v1/ionic/arrhenius-fit", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["output"]["arrhenius"]["activation_energy_eV"] > 0


def test_electrochemical_window_endpoint(
    client: TestClient, llzo_payload: dict
) -> None:
    r = client.post("/v1/ionic/electrochemical-window", json=llzo_payload)
    assert r.status_code == 200
    body = r.json()
    window = body["output"]["electrochemical_window_V_vs_LiLi"]
    assert window[1] >= 4.0  # LLZO oxidation


def test_interface_stability_endpoint(
    client: TestClient, llzo_payload: dict
) -> None:
    r = client.post("/v1/ionic/interface-stability", json=llzo_payload)
    assert r.status_code == 200
    body = r.json()
    assert body["output"]["interface_stability"] == "li_metal_stable"


def test_full_battery_evidence_endpoint(
    client: TestClient, llzo_payload: dict
) -> None:
    r = client.post("/v1/ionic/full-battery-evidence", json=llzo_payload)
    assert r.status_code == 200
    body = r.json()
    assert body["candidate_id"] == llzo_payload["candidate_id"]
    for name in (
        "neb",
        "mlip_md",
        "aimd",
        "arrhenius",
        "electrochemical_window",
        "interface_stability",
        "chain_complete",
        "mlip_vs_aimd_disagreement",
    ):
        assert name in body
    assert body["chain_complete"]["status"] == "pass"


def test_promote_battery_candidate_endpoint(
    client: TestClient, llzo_payload: dict
) -> None:
    r = client.post(
        "/v1/ionic/promote-battery-candidate", json=llzo_payload
    )
    assert r.status_code == 200
    body = r.json()
    assert body["decision"] == "promote"
    assert body["candidate_id"] == llzo_payload["candidate_id"]
    assert "evidence" in body


def test_neb_endpoint_rejects_extra_field(client: TestClient) -> None:
    """``extra='forbid'`` on the payload model rejects unknown fields."""
    payload = {
        "structure_hash": "sha256:" + "a" * 64,
        "candidate_id": "candidate:test",
        "rogue_field": "should-fail",
    }
    r = client.post("/v1/ionic/neb", json=payload)
    assert r.status_code == 422


def test_arrhenius_endpoint_rejects_short_input(client: TestClient) -> None:
    payload = {
        "temperatures_K": [300.0, 400.0],  # too short
        "conductivities_S_per_cm": [1e-3, 5e-3],
        "candidate_id": "candidate:test",
    }
    r = client.post("/v1/ionic/arrhenius-fit", json=payload)
    assert r.status_code == 422


def test_full_battery_evidence_for_li6ps5cl(client: TestClient) -> None:
    payload = {
        "structure_hash": "sha256:8d7b217550c751a08bd6bc85d74a166ff0b4966266552d254ca53527607c40bc",
        "fixture_id": "fixture:Li6PS5Cl:8d7b2175",
        "candidate_id": "candidate:Li6PS5Cl/contract",
    }
    r = client.post("/v1/ionic/full-battery-evidence", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["chain_complete"]["status"] == "pass"
    # Li6PS5Cl envelope has narrower window than LLZO.
    ec = body["electrochemical_window"]["output"]["electrochemical_window_V_vs_LiLi"]
    assert ec[1] < 4.0


def test_full_battery_evidence_for_seed(client: TestClient) -> None:
    payload = {
        "structure_hash": "sha256:ea01c76f01f1427a5010cad97a984d3802c869f96b3726501897f5b08e3c138a",
        "fixture_id": "fixture:Li-Mg-Zr-Cl-seed:ea01c76f",
        "candidate_id": "candidate:seed/contract",
        "interface_mode": "coating_interlayer",
    }
    r = client.post("/v1/ionic/full-battery-evidence", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["chain_complete"]["status"] == "pass"


def test_promote_li6ps5cl_rejects(client: TestClient) -> None:
    payload = {
        "structure_hash": "sha256:8d7b217550c751a08bd6bc85d74a166ff0b4966266552d254ca53527607c40bc",
        "fixture_id": "fixture:Li6PS5Cl:8d7b2175",
        "candidate_id": "candidate:Li6PS5Cl/contract",
    }
    r = client.post("/v1/ionic/promote-battery-candidate", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["decision"] == "reject"


def test_promote_seed_with_coating_promotes(client: TestClient) -> None:
    payload = {
        "structure_hash": "sha256:ea01c76f01f1427a5010cad97a984d3802c869f96b3726501897f5b08e3c138a",
        "fixture_id": "fixture:Li-Mg-Zr-Cl-seed:ea01c76f",
        "candidate_id": "candidate:seed/contract",
        "interface_mode": "coating_interlayer",
    }
    r = client.post("/v1/ionic/promote-battery-candidate", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["decision"] == "promote"
