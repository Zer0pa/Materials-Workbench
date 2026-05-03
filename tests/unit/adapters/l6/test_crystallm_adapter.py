"""Unit tests for CrystaLlmCifGeneratorAdapter."""

import re

import pytest

from zer0pa_materials_workbench.adapters.l6.crystallm import CrystaLlmCifGeneratorAdapter
from zer0pa_materials_workbench.boundary import RESEARCH_BOUNDARY
from zer0pa_materials_workbench.envelope.envelope import Envelope


@pytest.fixture
def adapter() -> CrystaLlmCifGeneratorAdapter:
    return CrystaLlmCifGeneratorAdapter()


class TestCrystaLlmBasic:
    def test_returns_one_envelope(self, adapter):
        envs = adapter.generate({"prompt": "halide electrolyte"})
        assert len(envs) == 1
        assert isinstance(envs[0], Envelope)

    def test_layer_l6(self, adapter):
        assert adapter.generate({})[0].layer == "L6"

    def test_boundary_verbatim(self, adapter):
        env = adapter.generate({})[0]
        assert env.research_boundary == RESEARCH_BOUNDARY

    def test_novelty_status_pending(self, adapter):
        env = adapter.generate({})[0]
        assert env.output["novelty_status"] == "pending"

    def test_structure_hash_format(self, adapter):
        env = adapter.generate({})[0]
        assert re.match(r"^sha256:[0-9a-f]{64}$", env.output["structure_hash"])

    def test_cif_text_present(self, adapter):
        env = adapter.generate({})[0]
        assert "_cell_length_a" in env.output["cif_text"]

    def test_li_mg_zr_cl_system(self, adapter):
        env = adapter.generate({"chemical_system": "Li-Mg-Zr-Cl"})[0]
        assert "Li" in env.output["cif_text"]
        assert "Mg" in env.output["cif_text"]

    def test_dedup_five_sources(self, adapter):
        env = adapter.generate({})[0]
        sources = {r["source"] for r in env.output["dedup_results"]}
        assert sources == {"MP", "JARVIS", "Alexandria", "GNoME", "OPTIMADE"}

    def test_generator_field(self, adapter):
        env = adapter.generate({})[0]
        assert "CrystaLLM" in env.output["generator"]

    def test_round_trip(self, adapter):
        env = adapter.generate({})[0]
        env2 = Envelope.model_validate(env.model_dump(mode="json"))
        assert env2.layer == "L6"
