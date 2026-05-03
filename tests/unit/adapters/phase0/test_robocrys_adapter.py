"""Unit tests for RobocrystallographerStructureNarrator."""

import pytest

from zer0pa_materials_workbench.adapters.phase0.robocrys import RobocrystallographerStructureNarrator
from zer0pa_materials_workbench.audit.sources import SourceManifest
from zer0pa_materials_workbench.boundary import RESEARCH_BOUNDARY
from zer0pa_materials_workbench.envelope.envelope import Envelope


@pytest.fixture
def adapter() -> RobocrystallographerStructureNarrator:
    return RobocrystallographerStructureNarrator()


class TestRobocrysAdapterBasic:
    def test_returns_envelope(self, adapter):
        env = adapter.query({"structure_key": "LLZO_cubic"})
        assert isinstance(env, Envelope)

    def test_layer_phase0(self, adapter):
        env = adapter.query({"structure_key": "LLZO_cubic"})
        assert env.layer == "phase0"

    def test_boundary_verbatim(self, adapter):
        env = adapter.query({"structure_key": "LLZO_cubic"})
        assert env.research_boundary == RESEARCH_BOUNDARY

    def test_description_present_in_output(self, adapter):
        env = adapter.query({"structure_key": "LLZO_cubic"})
        assert "structure_description" in env.output
        assert len(env.output["structure_description"]) > 10

    def test_llzo_cubic_description_mentions_garnet(self, adapter):
        env = adapter.query({"structure_key": "LLZO_cubic"})
        assert "garnet" in env.output["structure_description"].lower()

    def test_li6ps5cl_description_mentions_argyrodite(self, adapter):
        env = adapter.query({"structure_key": "Li6PS5Cl"})
        assert "argyrodite" in env.output["structure_description"].lower()

    def test_unknown_key_returns_fallback(self, adapter):
        env = adapter.query({"structure_key": "UnknownXYZ"})
        assert "stub description" in env.output["structure_description"].lower()

    def test_source_manifest_emitted(self, adapter):
        adapter.query({"structure_key": "Si"})
        m = adapter.get_last_manifest()
        assert isinstance(m, SourceManifest)

    def test_source_manifest_license_mit(self, adapter):
        adapter.query({"structure_key": "Si"})
        m = adapter.get_last_manifest()
        assert m.license_spdx == "MIT"

    def test_extracted_properties_empty(self, adapter):
        env = adapter.query({"structure_key": "LLZO_cubic"})
        # Narrator produces no numeric extractions.
        assert env.output["extracted_properties"] == []

    def test_material_kwarg(self, adapter):
        env = adapter.query({"material": "NaCl"})
        assert isinstance(env, Envelope)

    def test_round_trip(self, adapter):
        env = adapter.query({"structure_key": "LLZO_cubic"})
        env2 = Envelope.model_validate(env.model_dump(mode="json"))
        assert env2.layer == "phase0"
