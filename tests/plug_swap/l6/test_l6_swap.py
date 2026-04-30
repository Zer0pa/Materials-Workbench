"""Plug-swap tests: L6 generator adapter schema parity.

All three generator adapters (MatterGen, DiffCSP, CrystaLLM) must produce
Envelopes with identical top-level schema. Swapping adapters must not break
downstream consumers.
"""

import pytest

from zer0pa_materials.adapters.l6.crystallm import CrystaLlmCifGeneratorAdapter
from zer0pa_materials.adapters.l6.diffcsp import DiffCspGeneratorAdapter
from zer0pa_materials.adapters.l6.mattergen import MatterGenGeneratorAdapter
from zer0pa_materials.envelope.envelope import Envelope


@pytest.fixture
def mg_env():
    return MatterGenGeneratorAdapter(n_candidates=1).generate({})[0]


@pytest.fixture
def dc_env():
    return DiffCspGeneratorAdapter(n_candidates=1).generate({})[0]


@pytest.fixture
def cl_env():
    return CrystaLlmCifGeneratorAdapter().generate({})[0]


class TestL6SwapSchemaParity:
    """PRD §Plug-replaceability: all L6 adapters must share the same envelope schema."""

    def test_all_layers_are_l6(self, mg_env, dc_env, cl_env):
        for env in (mg_env, dc_env, cl_env):
            assert env.layer == "L6"

    def test_top_level_keys_identical(self, mg_env, dc_env, cl_env):
        keys_mg = set(mg_env.model_dump(mode="json").keys())
        keys_dc = set(dc_env.model_dump(mode="json").keys())
        keys_cl = set(cl_env.model_dump(mode="json").keys())
        assert keys_mg == keys_dc == keys_cl

    def test_required_output_keys_present_all(self, mg_env, dc_env, cl_env):
        required = {"candidate_uri", "structure_hash", "novelty_status", "dedup_results",
                    "cif_valid", "charge_neutral", "minimum_distance_ok", "cif_text"}
        for env in (mg_env, dc_env, cl_env):
            for key in required:
                assert key in env.output, f"Key {key!r} missing from {env.tool_adapter.name}"

    def test_novelty_status_pending_all(self, mg_env, dc_env, cl_env):
        for env in (mg_env, dc_env, cl_env):
            assert env.output["novelty_status"] == "pending"

    def test_structure_hash_format_all(self, mg_env, dc_env, cl_env):
        import re
        for env in (mg_env, dc_env, cl_env):
            assert re.match(r"^sha256:[0-9a-f]{64}$", env.output["structure_hash"])

    def test_dedup_five_sources_all(self, mg_env, dc_env, cl_env):
        for env in (mg_env, dc_env, cl_env):
            sources = {r["source"] for r in env.output["dedup_results"]}
            assert sources == {"MP", "JARVIS", "Alexandria", "GNoME", "OPTIMADE"}

    def test_round_trips_all(self, mg_env, dc_env, cl_env):
        for env in (mg_env, dc_env, cl_env):
            env2 = Envelope.model_validate(env.model_dump(mode="json"))
            assert env2.layer == "L6"

    def test_l6_json_schema_stable(self):
        """The L6GenerativeOutput JSON Schema must not drift."""
        from zer0pa_materials.envelope.layer_outputs import L6GenerativeOutput
        schema = L6GenerativeOutput.model_json_schema()
        assert "structure_hash" in str(schema)
        assert "novelty_status" in str(schema)
        assert "dedup_results" in str(schema)

    def test_cif_text_parseable_all(self, mg_env, dc_env, cl_env):
        from zer0pa_materials.envelope.hashing import cif_hash_from_text
        for env in (mg_env, dc_env, cl_env):
            cif_text = env.output.get("cif_text", "")
            if cif_text.strip():
                # Must not raise.
                cif_hash_from_text(cif_text)
