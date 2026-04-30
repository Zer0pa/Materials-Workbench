"""Contract tests for L6 FastAPI service."""

import pytest
from fastapi.testclient import TestClient

from zer0pa_materials.boundary import RESEARCH_BOUNDARY
from zer0pa_materials.services.l6_service import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


class TestL6Healthz:
    def test_healthz_200(self, client):
        assert client.get("/v1/l6/healthz").status_code == 200

    def test_healthz_status_ok(self, client):
        assert client.get("/v1/l6/healthz").json()["status"] == "ok"

    def test_healthz_layer(self, client):
        assert client.get("/v1/l6/healthz").json()["layer"] == "L6"

    def test_healthz_boundary(self, client):
        assert client.get("/v1/l6/healthz").json()["research_boundary"] == RESEARCH_BOUNDARY


class TestL6Generate:
    def test_generate_200(self, client):
        r = client.post("/v1/l6/generate", json={
            "chemical_system": "Li-La-Zr-O",
            "n_candidates": 2,
        })
        assert r.status_code == 200

    def test_generate_returns_list(self, client):
        r = client.post("/v1/l6/generate", json={"chemical_system": "Li-La-Zr-O"})
        assert isinstance(r.json(), list)

    def test_generate_all_envelopes_layer_l6(self, client):
        r = client.post("/v1/l6/generate", json={"chemical_system": "Li-La-Zr-O", "n_candidates": 1})
        for env in r.json():
            assert env["layer"] == "L6"

    def test_generate_novelty_pending(self, client):
        """PRD discipline: no premature novelty from service."""
        r = client.post("/v1/l6/generate", json={"chemical_system": "Li-La-Zr-O"})
        for env in r.json():
            assert env["output"]["novelty_status"] == "pending"

    def test_generate_boundary_verbatim(self, client):
        r = client.post("/v1/l6/generate", json={"chemical_system": "Li-La-Zr-O"})
        for env in r.json():
            assert env["research_boundary"] == RESEARCH_BOUNDARY

    def test_generate_mattergen_only(self, client):
        r = client.post("/v1/l6/generate", json={
            "chemical_system": "Li-La-Zr-O",
            "adapters": ["mattergen"],
            "n_candidates": 2,
        })
        assert r.status_code == 200
        assert len(r.json()) == 2

    def test_generate_diffcsp_only(self, client):
        r = client.post("/v1/l6/generate", json={
            "chemical_system": "Li-P-S-Cl",
            "adapters": ["diffcsp"],
            "n_candidates": 1,
        })
        assert r.status_code == 200
        assert len(r.json()) == 1

    def test_generate_crystallm_only(self, client):
        r = client.post("/v1/l6/generate", json={
            "chemical_system": "Li-Mg-Zr-Cl",
            "adapters": ["crystallm"],
        })
        assert r.status_code == 200
        assert len(r.json()) == 1

    def test_generate_structure_hash_format(self, client):
        import re
        r = client.post("/v1/l6/generate", json={"adapters": ["mattergen"], "n_candidates": 1})
        for env in r.json():
            assert re.match(r"^sha256:[0-9a-f]{64}$", env["output"]["structure_hash"])

    def test_generate_dedup_five_sources(self, client):
        r = client.post("/v1/l6/generate", json={"adapters": ["mattergen"], "n_candidates": 1})
        for env in r.json():
            sources = {d["source"] for d in env["output"]["dedup_results"]}
            assert sources == {"MP", "JARVIS", "Alexandria", "GNoME", "OPTIMADE"}


class TestL6NoveltyStatusGate:
    """Verify the service never emits novelty_status=novel."""

    def test_no_premature_novelty_from_any_adapter(self, client):
        r = client.post("/v1/l6/generate", json={
            "chemical_system": "Li-La-Zr-O",
            "adapters": ["mattergen", "diffcsp", "crystallm"],
            "n_candidates": 2,
        })
        for env in r.json():
            ns = env["output"]["novelty_status"]
            assert ns != "novel", (
                f"Premature novelty_status='novel' in {env['candidate_id']}. "
                "PRD: 'novel' requires L1+ionic+L2 back-edges."
            )
