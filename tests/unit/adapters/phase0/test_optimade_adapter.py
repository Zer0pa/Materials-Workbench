"""Unit tests for OptimadeFederatedQueryAdapter."""

import pytest

from zer0pa_materials_workbench.adapters.phase0.optimade import OptimadeFederatedQueryAdapter
from zer0pa_materials_workbench.audit.sources import SourceManifest
from zer0pa_materials_workbench.boundary import RESEARCH_BOUNDARY
from zer0pa_materials_workbench.envelope.envelope import Envelope


@pytest.fixture
def adapter() -> OptimadeFederatedQueryAdapter:
    return OptimadeFederatedQueryAdapter()


class TestOptimadeAdapterBasic:
    def test_returns_envelope(self, adapter):
        env = adapter.query({"elements": ["Li"]})
        assert isinstance(env, Envelope)

    def test_layer_is_phase0(self, adapter):
        env = adapter.query({"elements": ["Li"]})
        assert env.layer == "phase0"

    def test_boundary_present(self, adapter):
        env = adapter.query({"elements": ["La"]})
        assert env.research_boundary == RESEARCH_BOUNDARY

    def test_no_elements_returns_all_hits(self, adapter):
        env = adapter.query({})
        assert env.output["hit_count"] == 2

    def test_element_filter_li(self, adapter):
        env = adapter.query({"elements": ["Li"]})
        assert env.output["hit_count"] >= 1

    def test_element_filter_returns_subset(self, adapter):
        env_all = adapter.query({})
        env_li = adapter.query({"elements": ["Si"]})  # Si not in hits
        assert env_li.output["hit_count"] == 0

    def test_optimade_version_in_output(self, adapter):
        env = adapter.query({"elements": ["Li"]})
        assert env.output["optimade_version"] == "1.3"

    def test_source_manifest_emitted(self, adapter):
        adapter.query({"elements": ["Li"]})
        manifest = adapter.get_last_manifest()
        assert isinstance(manifest, SourceManifest)
        assert manifest.source_manifest_id.startswith("src:optimade:stub:")

    def test_source_manifest_license_ccby(self, adapter):
        adapter.query({"elements": ["Li"]})
        manifest = adapter.get_last_manifest()
        assert manifest.license_spdx == "CC-BY-4.0"

    def test_envelope_ids_are_valid_urns(self, adapter):
        env = adapter.query({"elements": ["La"]})
        assert env.run_id.startswith("run:")
        assert env.audit.audit_record_id.startswith("audit:")
        assert env.rights.rights_claim_id.startswith("rights:")

    def test_input_hash_format(self, adapter):
        env = adapter.query({"elements": ["La"]})
        import re
        assert re.match(r"^sha256:[0-9a-f]{64}$", env.audit.input_hash)

    def test_output_hash_format(self, adapter):
        env = adapter.query({"elements": ["La"]})
        import re
        assert re.match(r"^sha256:[0-9a-f]{64}$", env.audit.output_hash)

    def test_no_network_calls_in_stub(self, adapter, monkeypatch):
        """Stub must not make real HTTP calls."""
        import httpx
        calls = []
        def fake_get(*args, **kwargs):
            calls.append(args)
            raise AssertionError("network call in stub")
        monkeypatch.setattr(httpx, "get", fake_get)
        adapter.query({"elements": ["Li"]})
        assert calls == []

    def test_real_backend_raises_not_implemented(self, adapter):
        with pytest.raises(NotImplementedError, match="optimade_live"):
            adapter._query_real({"elements": ["Li"]})

    def test_filter_string_passed_through(self, adapter):
        env = adapter.query({"filter": "nsites < 10"})
        assert "nsites < 10" in env.output["query_filter"]

    def test_hits_structure_has_id_type_attributes(self, adapter):
        env = adapter.query({"elements": ["Li"]})
        for hit in env.output["optimade_hits"]:
            assert "id" in hit
            assert "type" in hit
            assert "attributes" in hit


class TestOptimadeAdapterEnvelopeContract:
    """Verify the emitted envelope passes the canonical schema contract."""

    def test_envelope_round_trips_json(self, adapter):
        env = adapter.query({"elements": ["Li"]})
        from zer0pa_materials_workbench.envelope.envelope import Envelope
        env2 = Envelope.model_validate(env.model_dump(mode="json"))
        assert env2.layer == env.layer

    def test_tool_adapter_name_contains_stub(self, adapter):
        env = adapter.query({"elements": ["Li"]})
        assert "stub" in env.tool_adapter.name.lower()

    def test_backend_is_stub(self, adapter):
        env = adapter.query({"elements": ["Li"]})
        assert env.tool_adapter.backend == "stub"
