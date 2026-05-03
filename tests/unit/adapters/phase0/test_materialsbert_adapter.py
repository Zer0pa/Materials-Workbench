"""Unit tests for MaterialsBertNerAdapter."""

import pytest

from zer0pa_materials_workbench.adapters.phase0.materialsbert import MaterialsBertNerAdapter
from zer0pa_materials_workbench.audit.sources import BlockedSourceManifest, SourceManifest
from zer0pa_materials_workbench.boundary import RESEARCH_BOUNDARY
from zer0pa_materials_workbench.envelope.envelope import Envelope


@pytest.fixture
def adapter() -> MaterialsBertNerAdapter:
    return MaterialsBertNerAdapter()


class TestMaterialsBertBlocked:
    """Default path: license not verified → BlockedSourceManifest."""

    def test_returns_envelope_even_when_blocked(self, adapter):
        env = adapter.query({"text": "LLZO has ionic conductivity 1e-3 S/cm."})
        assert isinstance(env, Envelope)

    def test_layer_phase0(self, adapter):
        env = adapter.query({"text": "some text"})
        assert env.layer == "phase0"

    def test_boundary_verbatim(self, adapter):
        env = adapter.query({"text": "some text"})
        assert env.research_boundary == RESEARCH_BOUNDARY

    def test_is_blocked_true_by_default(self, adapter):
        adapter.query({"text": "some text"})
        assert adapter.is_blocked() is True

    def test_blocked_manifest_emitted(self, adapter):
        adapter.query({"text": "some text"})
        m = adapter.get_last_manifest()
        assert isinstance(m, BlockedSourceManifest)

    def test_blocked_manifest_reason(self, adapter):
        adapter.query({"text": "some text"})
        m = adapter.get_last_manifest()
        assert m.blocker_reason == "license_unverified"

    def test_blocked_manifest_retry_strategy(self, adapter):
        adapter.query({"text": "some text"})
        m = adapter.get_last_manifest()
        assert "huggingface" in m.retry_strategy.lower()

    def test_no_ner_entities_when_blocked(self, adapter):
        env = adapter.query({"text": "some text"})
        assert env.output["ner_entities"] == []

    def test_no_extracted_properties_when_blocked(self, adapter):
        env = adapter.query({"text": "some text"})
        assert env.output["extracted_properties"] == []

    def test_blocked_reason_in_output(self, adapter):
        env = adapter.query({"text": "some text"})
        assert env.output["blocked_reason"] == "license_unverified"


class TestMaterialsBertVerified:
    """license_verified=True path: returns mock NER entities."""

    def test_not_blocked_when_verified(self, adapter):
        adapter.query({"text": "Li7La3Zr2O12", "license_verified": True})
        assert adapter.is_blocked() is False

    def test_source_manifest_emitted_when_verified(self, adapter):
        adapter.query({"text": "Li7La3Zr2O12", "license_verified": True})
        m = adapter.get_last_manifest()
        assert isinstance(m, SourceManifest)

    def test_source_manifest_license_apache(self, adapter):
        adapter.query({"text": "Li7La3Zr2O12", "license_verified": True})
        m = adapter.get_last_manifest()
        assert m.license_spdx == "Apache-2.0"

    def test_ner_entities_returned(self, adapter):
        env = adapter.query({"text": "LLZO paper", "license_verified": True})
        assert len(env.output["ner_entities"]) > 0

    def test_ner_entities_have_label(self, adapter):
        env = adapter.query({"text": "LLZO", "license_verified": True})
        for ent in env.output["ner_entities"]:
            assert "label" in ent
            assert "entity" in ent
            assert "confidence" in ent

    def test_round_trip(self, adapter):
        env = adapter.query({"text": "LLZO", "license_verified": True})
        env2 = Envelope.model_validate(env.model_dump(mode="json"))
        assert env2.layer == "phase0"
