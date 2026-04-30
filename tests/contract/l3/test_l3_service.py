"""Contract tests for the L3 REST service — FastAPI TestClient on all endpoints."""

from __future__ import annotations

from pathlib import Path

import pytest

# Guard: skip if fastapi is not installed.
fastapi = pytest.importorskip("fastapi", reason="fastapi required for contract tests")
httpx = pytest.importorskip("httpx", reason="httpx required for contract tests")

from fastapi.testclient import TestClient

from zer0pa_materials.boundary import RESEARCH_BOUNDARY


REPO_ROOT = Path(__file__).resolve().parents[3]
CU_MG_TDB = REPO_ROOT / "fixtures" / "tdb" / "Cu-Mg-toy.tdb"


EQUILIBRIUM_PAYLOAD = {
    "run_id": "run:contract/l3/eq",
    "candidate_id": "candidate:Cu-Mg:001",
    "campaign_id": "campaign:contract/001",
    "rights_claim_id": "rights:contract/001",
    "tdb_path": str(CU_MG_TDB),
    "components": ["CU", "MG"],
    "temperature_K": 1200.0,
    "composition": {"CU": 0.7, "MG": 0.3},
}

FIT_PAYLOAD = {
    "run_id": "run:contract/l3/fit",
    "candidate_id": "candidate:Cu-Mg:002",
    "campaign_id": "campaign:contract/001",
    "rights_claim_id": "rights:contract/001",
    "tdb_path": str(CU_MG_TDB),
    "components": ["CU", "MG"],
    "n_walkers": 16,
    "n_steps": 200,
    "n_burn_in": 50,
}

SOVEREIGN_PAYLOAD = {
    "run_id": "run:contract/l3/sovereign",
    "candidate_id": "candidate:novel:001",
    "campaign_id": "campaign:contract/001",
    "rights_claim_id": "rights:contract/001",
    "tdb_path": str(CU_MG_TDB),
    "components": ["CU", "MG"],
    "temperature_grid_K": [300.0, 700.0],
}

QUARANTINE_PAYLOAD = {
    "run_id": "run:contract/l3/quarantine",
    "candidate_id": "candidate:customer:001",
    "campaign_id": "campaign:customer-engagement/001",
    "rights_claim_id": "rights:customer-engagement/001",
    "tdb_path": str(CU_MG_TDB),
    "customer_id": "customer:acme:001",
    "license_proof_uri": "https://acme.example.com/license-proof.pdf",
}


@pytest.fixture(scope="module")
def client():
    from zer0pa_materials.services.l3_service import _make_app
    app = _make_app()
    with TestClient(app) as c:
        yield c


class TestHealthz:
    def test_healthz_200(self, client):
        resp = client.get("/v1/l3/healthz")
        assert resp.status_code == 200

    def test_healthz_status_ok(self, client):
        data = client.get("/v1/l3/healthz").json()
        assert data["status"] == "ok"

    def test_healthz_service_name(self, client):
        data = client.get("/v1/l3/healthz").json()
        assert data["service"] == "l3_calphad"

    def test_healthz_has_boundary(self, client):
        data = client.get("/v1/l3/healthz").json()
        assert data["research_boundary"] == RESEARCH_BOUNDARY

    def test_healthz_reports_pycalphad_flag(self, client):
        data = client.get("/v1/l3/healthz").json()
        assert "pycalphad_available" in data

    def test_healthz_reports_espei_flag(self, client):
        data = client.get("/v1/l3/healthz").json()
        assert "espei_available" in data


class TestEquilibriumEndpoint:
    def test_equilibrium_200(self, client):
        resp = client.post("/v1/l3/equilibrium", json=EQUILIBRIUM_PAYLOAD)
        assert resp.status_code == 200

    def test_equilibrium_returns_envelope(self, client):
        data = client.post("/v1/l3/equilibrium", json=EQUILIBRIUM_PAYLOAD).json()
        assert "envelope" in data

    def test_equilibrium_layer_is_l3(self, client):
        data = client.post("/v1/l3/equilibrium", json=EQUILIBRIUM_PAYLOAD).json()
        assert data["envelope"]["layer"] == "L3"

    def test_equilibrium_phases_returned(self, client):
        data = client.post("/v1/l3/equilibrium", json=EQUILIBRIUM_PAYLOAD).json()
        phases = data["envelope"]["output"]["equilibrium_phases"]
        assert len(phases) >= 1

    def test_equilibrium_invalid_payload_422(self, client):
        resp = client.post("/v1/l3/equilibrium", json={"bad": "payload"})
        assert resp.status_code == 422

    def test_equilibrium_response_has_boundary(self, client):
        data = client.post("/v1/l3/equilibrium", json=EQUILIBRIUM_PAYLOAD).json()
        assert data["research_boundary"] == RESEARCH_BOUNDARY


class TestFitTdbEndpoint:
    def test_fit_200(self, client):
        resp = client.post("/v1/l3/fit-tdb", json=FIT_PAYLOAD)
        assert resp.status_code == 200

    def test_fit_returns_envelope(self, client):
        data = client.post("/v1/l3/fit-tdb", json=FIT_PAYLOAD).json()
        assert "envelope" in data

    def test_fit_layer_is_l3(self, client):
        data = client.post("/v1/l3/fit-tdb", json=FIT_PAYLOAD).json()
        assert data["envelope"]["layer"] == "L3"

    def test_fit_diagnostics_present(self, client):
        data = client.post("/v1/l3/fit-tdb", json=FIT_PAYLOAD).json()
        diags = data["envelope"]["output"]["espei_diagnostics"]
        assert diags["ran"] is True
        assert "R_hat" in diags
        assert "effective_sample_size" in diags

    def test_fit_information_geometry_note(self, client):
        data = client.post("/v1/l3/fit-tdb", json=FIT_PAYLOAD).json()
        assert "_information_geometry_note" in data["envelope"]

    def test_fit_invalid_n_walkers_422(self, client):
        bad = dict(FIT_PAYLOAD)
        bad["n_walkers"] = 1  # below n_walkers >= 4
        resp = client.post("/v1/l3/fit-tdb", json=bad)
        assert resp.status_code == 422


class TestSovereignPipelineEndpoint:
    def test_sovereign_200(self, client):
        resp = client.post("/v1/l3/sovereign-pipeline", json=SOVEREIGN_PAYLOAD)
        assert resp.status_code == 200

    def test_sovereign_returns_envelopes(self, client):
        data = client.post("/v1/l3/sovereign-pipeline", json=SOVEREIGN_PAYLOAD).json()
        assert "envelopes" in data
        assert isinstance(data["envelopes"], list)

    def test_sovereign_summary_envelope_present(self, client):
        data = client.post("/v1/l3/sovereign-pipeline", json=SOVEREIGN_PAYLOAD).json()
        assert "summary_envelope" in data
        assert data["summary_envelope"]["layer"] == "L3"

    def test_sovereign_n_steps_recorded(self, client):
        data = client.post("/v1/l3/sovereign-pipeline", json=SOVEREIGN_PAYLOAD).json()
        # 6 envelopes: dft_mlip + prior + espei + 2 equilibrium (300, 700) + summary
        assert data["n_steps"] == 6

    def test_sovereign_information_geometry_note(self, client):
        data = client.post("/v1/l3/sovereign-pipeline", json=SOVEREIGN_PAYLOAD).json()
        assert "_information_geometry_note" in data["summary_envelope"]

    def test_sovereign_battery_grid_default(self, client):
        # When temperature_grid_K is omitted, default (300, 700) is used.
        payload = dict(SOVEREIGN_PAYLOAD)
        del payload["temperature_grid_K"]
        data = client.post("/v1/l3/sovereign-pipeline", json=payload).json()
        meta = data["summary_envelope"]["_pipeline_meta"]
        assert meta["temperature_grid_K"] == [300.0, 700.0]


class TestQuarantineEndpoint:
    def test_quarantine_200_with_license(self, client):
        resp = client.post("/v1/l3/quarantine-thermocalc-read", json=QUARANTINE_PAYLOAD)
        assert resp.status_code == 200

    def test_quarantine_returns_envelope(self, client):
        data = client.post(
            "/v1/l3/quarantine-thermocalc-read", json=QUARANTINE_PAYLOAD
        ).json()
        assert data["envelope"]["layer"] == "L3"

    def test_quarantine_meta_present(self, client):
        data = client.post(
            "/v1/l3/quarantine-thermocalc-read", json=QUARANTINE_PAYLOAD
        ).json()
        assert "_quarantine_meta" in data["envelope"]
        meta = data["envelope"]["_quarantine_meta"]
        assert meta["redistributable"] is False
        assert meta["committed_to_repo"] is False
        assert meta["customer_id"] == "customer:acme:001"

    def test_quarantine_invalid_customer_id_422(self, client):
        bad = dict(QUARANTINE_PAYLOAD)
        bad["customer_id"] = "not-a-customer"
        resp = client.post("/v1/l3/quarantine-thermocalc-read", json=bad)
        assert resp.status_code == 422

    def test_quarantine_response_has_boundary(self, client):
        data = client.post(
            "/v1/l3/quarantine-thermocalc-read", json=QUARANTINE_PAYLOAD
        ).json()
        assert data["research_boundary"] == RESEARCH_BOUNDARY

    def test_quarantine_tdb_ref_is_hash_uri(self, client):
        data = client.post(
            "/v1/l3/quarantine-thermocalc-read", json=QUARANTINE_PAYLOAD
        ).json()
        assert data["envelope"]["output"]["tdb_ref"].startswith("hash://")
