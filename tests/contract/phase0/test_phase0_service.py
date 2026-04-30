"""Contract tests for Phase 0 FastAPI service."""

import pytest
from fastapi.testclient import TestClient

from zer0pa_materials.boundary import RESEARCH_BOUNDARY
from zer0pa_materials.services.phase0_service import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


class TestHealthz:
    def test_healthz_200(self, client):
        r = client.get("/v1/phase0/healthz")
        assert r.status_code == 200

    def test_healthz_status_ok(self, client):
        assert client.get("/v1/phase0/healthz").json()["status"] == "ok"

    def test_healthz_layer(self, client):
        assert client.get("/v1/phase0/healthz").json()["layer"] == "phase0"

    def test_healthz_boundary(self, client):
        assert client.get("/v1/phase0/healthz").json()["research_boundary"] == RESEARCH_BOUNDARY


class TestExtract:
    def test_extract_200(self, client):
        r = client.post("/v1/phase0/extract", json={"fixture": "LLZO"})
        assert r.status_code == 200

    def test_extract_returns_envelope_schema(self, client):
        r = client.post("/v1/phase0/extract", json={"fixture": "LLZO"})
        data = r.json()
        assert data["layer"] == "phase0"
        assert "research_boundary" in data

    def test_extract_boundary_verbatim(self, client):
        r = client.post("/v1/phase0/extract", json={"fixture": "LLZO"})
        assert r.json()["research_boundary"] == RESEARCH_BOUNDARY

    def test_extract_output_has_properties(self, client):
        r = client.post("/v1/phase0/extract", json={"fixture": "LLZO"})
        output = r.json()["output"]
        assert "extracted_properties" in output

    def test_extract_li6ps5cl_fixture(self, client):
        r = client.post("/v1/phase0/extract", json={"fixture": "Li6PS5Cl"})
        assert r.status_code == 200
        assert r.json()["layer"] == "phase0"

    def test_extract_seed_fixture(self, client):
        r = client.post("/v1/phase0/extract", json={"fixture": "Li-Mg-Zr-Cl-seed"})
        assert r.status_code == 200

    def test_extract_with_doi(self, client):
        r = client.post("/v1/phase0/extract", json={
            "fixture": "LLZO",
            "doi": "10.1002/anie.200701144",
        })
        assert r.status_code == 200


class TestOptimadeQuery:
    def test_optimade_query_200(self, client):
        r = client.post("/v1/phase0/optimade/query", json={"elements": ["Li"]})
        assert r.status_code == 200

    def test_optimade_query_layer(self, client):
        r = client.post("/v1/phase0/optimade/query", json={"elements": ["La"]})
        assert r.json()["layer"] == "phase0"

    def test_optimade_query_hits_present(self, client):
        r = client.post("/v1/phase0/optimade/query", json={"elements": ["Li"]})
        assert r.json()["output"]["hit_count"] >= 1

    def test_optimade_query_empty_elements(self, client):
        r = client.post("/v1/phase0/optimade/query", json={})
        assert r.status_code == 200

    def test_optimade_query_with_filter(self, client):
        r = client.post("/v1/phase0/optimade/query", json={"filter": "nsites < 10"})
        assert r.status_code == 200


class TestPhase0KGWrites:
    """Test that KG nodes are written when the adapter emits an extraction envelope."""

    def test_kg_nodes_can_be_written(self):
        """Verify KG write round-trip for a Phase 0 extraction."""
        import tempfile, os
        from pathlib import Path
        from zer0pa_materials.adapters.phase0.langgraph_extraction import LangGraphExtractionWorkflow
        from zer0pa_materials.audit.kg import MaterialsKG, KGNodeType, KGEdgeType, KGNode, KGEdge

        with tempfile.TemporaryDirectory() as tmpdir:
            kg = MaterialsKG(Path(tmpdir) / "kg.db")
            adapter = LangGraphExtractionWorkflow()
            env = adapter.query({"fixture": "LLZO"})

            run_id = env.run_id
            lit_node_id = f"node:lit:{run_id}"
            prop_node_id = f"node:prop:{run_id}"

            # Write LiteratureSource node.
            lit_node = kg.add_node(
                node_id=lit_node_id,
                node_type=KGNodeType.LiteratureSource,
                properties={"doi": "10.1002/anie.200701144"},
                ontology_term="https://emmo.info/emmo#EMMO_Publication",
                run_id=run_id,
            )

            # Write PropertyObservation node.
            prop_node = kg.add_node(
                node_id=prop_node_id,
                node_type=KGNodeType.PropertyObservation,
                properties={"property_name": "ionic_conductivity"},
                ontology_term="https://emmo.info/emmo#EMMO_Property",
                run_id=run_id,
            )

            # Write edge: LiteratureSource -[CITES]-> PropertyObservation
            kg.add_edge(
                edge_id=f"edge:cites:{run_id}",
                src_id=lit_node_id,
                dst_id=prop_node_id,
                edge_type=KGEdgeType.CITES,
                run_id=run_id,
            )

            from zer0pa_materials.falsifiers.phase0_falsifiers import assert_kg_nodes_for
            items = assert_kg_nodes_for(env, kg)
            assert all(i.status == "pass" for i in items)
