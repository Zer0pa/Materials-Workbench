"""Unit tests for DiffCspGeneratorAdapter."""

import re
import pytest

from zer0pa_materials.adapters.l6.diffcsp import DiffCspGeneratorAdapter
from zer0pa_materials.boundary import RESEARCH_BOUNDARY
from zer0pa_materials.envelope.envelope import Envelope


@pytest.fixture
def adapter() -> DiffCspGeneratorAdapter:
    return DiffCspGeneratorAdapter(n_candidates=2)


class TestDiffCspBasic:
    def test_returns_envelopes(self, adapter):
        envs = adapter.generate({"chemical_system": "Li-P-S-Cl"})
        assert all(isinstance(e, Envelope) for e in envs)

    def test_layer_l6(self, adapter):
        for env in adapter.generate({}):
            assert env.layer == "L6"

    def test_boundary_verbatim(self, adapter):
        for env in adapter.generate({}):
            assert env.research_boundary == RESEARCH_BOUNDARY

    def test_novelty_status_pending(self, adapter):
        for env in adapter.generate({}):
            assert env.output["novelty_status"] == "pending"

    def test_structure_hash_format(self, adapter):
        for env in adapter.generate({}):
            assert re.match(r"^sha256:[0-9a-f]{64}$", env.output["structure_hash"])

    def test_cif_text_present(self, adapter):
        for env in adapter.generate({}):
            assert "_cell_length_a" in env.output["cif_text"]

    def test_dedup_five_sources(self, adapter):
        for env in adapter.generate({}):
            sources = {r["source"] for r in env.output["dedup_results"]}
            assert sources == {"MP", "JARVIS", "Alexandria", "GNoME", "OPTIMADE"}

    def test_unique_candidate_ids(self, adapter):
        envs = adapter.generate({})
        ids = [e.candidate_id for e in envs]
        assert len(ids) == len(set(ids))

    def test_cif_valid_true(self, adapter):
        for env in adapter.generate({}):
            assert env.output["cif_valid"] is True

    def test_generator_field(self, adapter):
        for env in adapter.generate({}):
            assert "DiffCSP" in env.output["generator"]
