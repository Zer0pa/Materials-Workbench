"""Contract tests for L5 REST service — FastAPI TestClient on all endpoints."""

from __future__ import annotations

import pytest

# Guard: skip if fastapi is not installed.
fastapi = pytest.importorskip("fastapi", reason="fastapi required for contract tests")
httpx = pytest.importorskip("httpx", reason="httpx required for contract tests")

from fastapi.testclient import TestClient

from zer0pa_materials_workbench.boundary import RESEARCH_BOUNDARY

CONTINUUM_PAYLOAD = {
    "run_id": "run:contract/l5/si",
    "candidate_id": "candidate:Si:001",
    "campaign_id": "campaign:contract/001",
    "rights_claim_id": "rights:contract/001",
    "n_heat_elements": 10,
    "n_patch_elements": 4,
    "E_GPa": 200.0,
    "nu": 0.3,
    "kappa_W_per_mK": 10.0,
}

HOMOGENISE_PAYLOAD = {
    "run_id": "run:contract/l5/homo",
    "candidate_id": "candidate:homo:001",
    "campaign_id": "campaign:contract/001",
    "rights_claim_id": "rights:contract/001",
    "trajectory": [
        {"phase": "matrix", "volume_fraction": 0.8, "time_step": 0},
        {"phase": "precipitate", "volume_fraction": 0.2, "time_step": 0},
    ],
}


@pytest.fixture(scope="module")
def client():
    from zer0pa_materials_workbench.services.l5_service import _make_app
    app = _make_app()
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# GET /v1/l5/healthz
# ---------------------------------------------------------------------------

class TestHealthz:
    def test_healthz_200(self, client):
        resp = client.get("/v1/l5/healthz")
        assert resp.status_code == 200

    def test_healthz_status_ok(self, client):
        data = client.get("/v1/l5/healthz").json()
        assert data["status"] == "ok"

    def test_healthz_has_boundary(self, client):
        data = client.get("/v1/l5/healthz").json()
        assert data["research_boundary"] == RESEARCH_BOUNDARY

    def test_healthz_service_name(self, client):
        data = client.get("/v1/l5/healthz").json()
        assert data["service"] == "l5_continuum"

    def test_healthz_backend_field(self, client):
        data = client.get("/v1/l5/healthz").json()
        assert "backend" in data


# ---------------------------------------------------------------------------
# POST /v1/l5/continuum-runs
# ---------------------------------------------------------------------------

class TestContinuumRuns:
    def test_200_status(self, client):
        resp = client.post("/v1/l5/continuum-runs", json=CONTINUUM_PAYLOAD)
        assert resp.status_code == 200

    def test_has_envelope(self, client):
        data = client.post("/v1/l5/continuum-runs", json=CONTINUUM_PAYLOAD).json()
        assert "envelope" in data

    def test_envelope_layer_is_L5(self, client):
        data = client.post("/v1/l5/continuum-runs", json=CONTINUUM_PAYLOAD).json()
        assert data["envelope"]["layer"] == "L5"

    def test_envelope_boundary_verbatim(self, client):
        data = client.post("/v1/l5/continuum-runs", json=CONTINUUM_PAYLOAD).json()
        assert data["envelope"]["research_boundary"] == RESEARCH_BOUNDARY

    def test_has_dealii_envelope(self, client):
        data = client.post("/v1/l5/continuum-runs", json=CONTINUUM_PAYLOAD).json()
        assert "dealii_envelope" in data
        assert data["dealii_envelope"]["layer"] == "L5"

    def test_has_openfoam_envelope(self, client):
        data = client.post("/v1/l5/continuum-runs", json=CONTINUUM_PAYLOAD).json()
        assert "openfoam_envelope" in data
        assert data["openfoam_envelope"]["layer"] == "L5"

    def test_has_blocked_manifests(self, client):
        data = client.post("/v1/l5/continuum-runs", json=CONTINUUM_PAYLOAD).json()
        assert "blocked_manifests" in data
        assert isinstance(data["blocked_manifests"], list)

    def test_output_has_tensors(self, client):
        data = client.post("/v1/l5/continuum-runs", json=CONTINUUM_PAYLOAD).json()
        tensors = data["envelope"]["output"]["tensors"]
        assert isinstance(tensors, list)
        assert len(tensors) >= 1

    def test_heat_slab_error_below_gate(self, client):
        data = client.post("/v1/l5/continuum-runs", json=CONTINUUM_PAYLOAD).json()
        err = data["envelope"]["output"]["analytic_heat_slab_error"]
        assert err < 1e-6

    def test_patch_residual_below_gate(self, client):
        data = client.post("/v1/l5/continuum-runs", json=CONTINUUM_PAYLOAD).json()
        res = data["envelope"]["output"]["elastic_patch_residual"]
        assert res < 1e-8

    def test_cross_method_disagreement_below_2pct(self, client):
        data = client.post("/v1/l5/continuum-runs", json=CONTINUUM_PAYLOAD).json()
        disagree = data["envelope"]["output"]["fenicsx_vs_dealii_strain_energy_disagreement_pct"]
        assert disagree is not None
        assert disagree < 2.0

    def test_poiseuille_error_below_5pct(self, client):
        data = client.post("/v1/l5/continuum-runs", json=CONTINUUM_PAYLOAD).json()
        err = data["envelope"]["output"]["openfoam_poiseuille_error_pct"]
        assert err is not None
        assert err < 5.0

    def test_cfd_mass_balance_below_threshold(self, client):
        data = client.post("/v1/l5/continuum-runs", json=CONTINUUM_PAYLOAD).json()
        err = data["envelope"]["output"]["cfd_mass_balance_error"]
        assert err is not None
        assert err < 1e-4

    def test_cfd_heat_balance_below_threshold(self, client):
        data = client.post("/v1/l5/continuum-runs", json=CONTINUUM_PAYLOAD).json()
        err = data["envelope"]["output"]["cfd_heat_balance_error"]
        assert err is not None
        assert err < 1e-4

    def test_blocked_manifests_have_required_keys(self, client):
        data = client.post("/v1/l5/continuum-runs", json=CONTINUUM_PAYLOAD).json()
        for m in data["blocked_manifests"]:
            assert "source_manifest_id" in m
            assert "blocker_reason" in m
            assert "retry_strategy" in m

    def test_research_boundary_in_response(self, client):
        data = client.post("/v1/l5/continuum-runs", json=CONTINUUM_PAYLOAD).json()
        assert data["research_boundary"] == RESEARCH_BOUNDARY


# ---------------------------------------------------------------------------
# POST /v1/l5/homogenise
# ---------------------------------------------------------------------------

class TestHomogenise:
    def test_200_status(self, client):
        resp = client.post("/v1/l5/homogenise", json=HOMOGENISE_PAYLOAD)
        assert resp.status_code == 200

    def test_has_effective_properties(self, client):
        data = client.post("/v1/l5/homogenise", json=HOMOGENISE_PAYLOAD).json()
        assert "effective_properties" in data

    def test_effective_stiffness_present(self, client):
        data = client.post("/v1/l5/homogenise", json=HOMOGENISE_PAYLOAD).json()
        props = data["effective_properties"]
        assert "effective_stiffness_3x3" in props

    def test_effective_conductivity_present(self, client):
        data = client.post("/v1/l5/homogenise", json=HOMOGENISE_PAYLOAD).json()
        props = data["effective_properties"]
        assert "effective_conductivity_3x3" in props

    def test_stiffness_spd_true(self, client):
        data = client.post("/v1/l5/homogenise", json=HOMOGENISE_PAYLOAD).json()
        assert data["effective_properties"]["stiffness_spd"] is True

    def test_conductivity_spd_true(self, client):
        data = client.post("/v1/l5/homogenise", json=HOMOGENISE_PAYLOAD).json()
        assert data["effective_properties"]["conductivity_spd"] is True

    def test_boundary_in_response(self, client):
        data = client.post("/v1/l5/homogenise", json=HOMOGENISE_PAYLOAD).json()
        assert data["research_boundary"] == RESEARCH_BOUNDARY

    def test_backend_field(self, client):
        data = client.post("/v1/l5/homogenise", json=HOMOGENISE_PAYLOAD).json()
        assert "backend" in data

    def test_run_id_echoed(self, client):
        data = client.post("/v1/l5/homogenise", json=HOMOGENISE_PAYLOAD).json()
        assert data["run_id"] == HOMOGENISE_PAYLOAD["run_id"]

    def test_empty_trajectory_422(self, client):
        bad_payload = {**HOMOGENISE_PAYLOAD, "trajectory": []}
        resp = client.post("/v1/l5/homogenise", json=bad_payload)
        # FastAPI validates min_length=1 → 422.
        assert resp.status_code == 422
