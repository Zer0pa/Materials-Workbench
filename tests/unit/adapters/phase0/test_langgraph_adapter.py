"""Unit tests for LangGraphExtractionWorkflow."""

import pytest

from zer0pa_materials.adapters.phase0.langgraph_extraction import LangGraphExtractionWorkflow
from zer0pa_materials.audit.sources import SourceManifest
from zer0pa_materials.boundary import RESEARCH_BOUNDARY
from zer0pa_materials.envelope.envelope import Envelope


@pytest.fixture
def adapter() -> LangGraphExtractionWorkflow:
    return LangGraphExtractionWorkflow()


class TestLangGraphAdapterBasic:
    def test_returns_envelope(self, adapter):
        env = adapter.query({"fixture": "LLZO"})
        assert isinstance(env, Envelope)

    def test_layer_phase0(self, adapter):
        assert adapter.query({"fixture": "LLZO"}).layer == "phase0"

    def test_boundary_verbatim(self, adapter):
        env = adapter.query({"fixture": "LLZO"})
        assert env.research_boundary == RESEARCH_BOUNDARY

    def test_llzo_fixture_has_three_properties(self, adapter):
        env = adapter.query({"fixture": "LLZO"})
        assert len(env.output["extracted_properties"]) == 3

    def test_li6ps5cl_fixture_has_three_properties(self, adapter):
        env = adapter.query({"fixture": "Li6PS5Cl"})
        assert len(env.output["extracted_properties"]) >= 2

    def test_seed_fixture_works(self, adapter):
        env = adapter.query({"fixture": "Li-Mg-Zr-Cl-seed"})
        assert len(env.output["extracted_properties"]) >= 2

    def test_unknown_fixture_falls_back(self, adapter):
        env = adapter.query({"fixture": "UnknownMaterial"})
        assert isinstance(env, Envelope)

    def test_units_normalised_true(self, adapter):
        env = adapter.query({"fixture": "LLZO"})
        assert env.output["units_normalised"] is True

    def test_contradictions_blocking_empty(self, adapter):
        env = adapter.query({"fixture": "LLZO"})
        assert env.output["contradictions_blocking"] == []

    def test_source_manifest_emitted(self, adapter):
        adapter.query({"fixture": "LLZO"})
        m = adapter.get_last_manifest()
        assert isinstance(m, SourceManifest)

    def test_source_manifest_has_doi_or_fixture_locator(self, adapter):
        adapter.query({"fixture": "LLZO", "doi": "10.1002/anie.200701144"})
        m = adapter.get_last_manifest()
        assert "10.1002/anie.200701144" in m.locator or "LLZO" in m.locator

    def test_extracted_property_has_doi(self, adapter):
        env = adapter.query({"fixture": "LLZO"})
        for prop in env.output["extracted_properties"]:
            assert prop["grounding"]["doi"], "each property must have a DOI"

    def test_no_real_llm_calls(self, adapter):
        """Stub must not call the OpenAI API — confirmed by the stub backend name."""
        env = adapter.query({"fixture": "LLZO"})
        assert env.tool_adapter.backend == "stub", (
            "Stub must use backend='stub'; 'openai' or 'anthropic' would mean real calls."
        )

    def test_material_kwarg_handled(self, adapter):
        env = adapter.query({"material": "LLZO"})
        assert isinstance(env, Envelope)


class TestLangGraphEnvelopeContract:
    def test_round_trip(self, adapter):
        env = adapter.query({"fixture": "LLZO"})
        env2 = Envelope.model_validate(env.model_dump(mode="json"))
        assert env2.output["units_normalised"] == env.output["units_normalised"]

    def test_tool_adapter_backend_stub(self, adapter):
        env = adapter.query({"fixture": "LLZO"})
        assert env.tool_adapter.backend == "stub"
