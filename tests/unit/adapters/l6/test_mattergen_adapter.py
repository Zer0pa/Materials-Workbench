"""Unit tests for MatterGenGeneratorAdapter."""

import pytest

from zer0pa_materials_workbench.adapters.l6.mattergen import MatterGenGeneratorAdapter
from zer0pa_materials_workbench.audit.sources import BlockedSourceManifest
from zer0pa_materials_workbench.boundary import RESEARCH_BOUNDARY
from zer0pa_materials_workbench.envelope.envelope import Envelope


@pytest.fixture
def adapter() -> MatterGenGeneratorAdapter:
    return MatterGenGeneratorAdapter(n_candidates=3)


class TestMatterGenBasic:
    def test_returns_list_of_envelopes(self, adapter):
        envs = adapter.generate({"chemical_system": "Li-La-Zr-O"})
        assert isinstance(envs, list)
        assert all(isinstance(e, Envelope) for e in envs)

    def test_returns_correct_count(self, adapter):
        envs = adapter.generate({"chemical_system": "Li-La-Zr-O"})
        assert len(envs) == 3

    def test_layer_is_l6(self, adapter):
        envs = adapter.generate({"chemical_system": "Li-La-Zr-O"})
        for env in envs:
            assert env.layer == "L6"

    def test_boundary_present(self, adapter):
        envs = adapter.generate({"chemical_system": "Li-La-Zr-O"})
        for env in envs:
            assert env.research_boundary == RESEARCH_BOUNDARY

    def test_novelty_status_is_pending(self, adapter):
        """Invariant: novelty_status MUST be 'pending' from stub generator."""
        envs = adapter.generate({"chemical_system": "Li-La-Zr-O"})
        for env in envs:
            assert env.output["novelty_status"] == "pending", (
                f"novelty_status must be 'pending', got {env.output['novelty_status']!r}. "
                "PRD discipline: 'novel' is a CLAIM — never set until L1+ionic+L2 pass."
            )

    def test_structure_hash_present(self, adapter):
        envs = adapter.generate({"chemical_system": "Li-La-Zr-O"})
        for env in envs:
            import re
            assert re.match(r"^sha256:[0-9a-f]{64}$", env.output["structure_hash"])

    def test_cif_text_present(self, adapter):
        envs = adapter.generate({"chemical_system": "Li-La-Zr-O"})
        for env in envs:
            assert "cif_text" in env.output
            assert "_cell_length_a" in env.output["cif_text"]

    def test_dedup_results_have_five_sources(self, adapter):
        envs = adapter.generate({"chemical_system": "Li-La-Zr-O"})
        for env in envs:
            sources = {r["source"] for r in env.output["dedup_results"]}
            assert sources == {"MP", "JARVIS", "Alexandria", "GNoME", "OPTIMADE"}

    def test_candidate_ids_unique(self, adapter):
        envs = adapter.generate({"chemical_system": "Li-La-Zr-O"})
        ids = [e.candidate_id for e in envs]
        assert len(ids) == len(set(ids)), "All candidate_ids must be unique."

    def test_structure_hashes_unique(self, adapter):
        envs = adapter.generate({"chemical_system": "Li-La-Zr-O"})
        hashes = [e.output["structure_hash"] for e in envs]
        assert len(hashes) == len(set(hashes)), "Structure hashes must be unique."

    def test_perturbed_candidates_not_matched_in_mp(self, adapter):
        """Candidates with non-zero perturbation should not be marked as MP matches."""
        envs = adapter.generate({"chemical_system": "Li-La-Zr-O"})
        non_zero_delta = [e for e in envs if abs(e.output["perturbation_delta_ang"]) > 1e-6]
        for env in non_zero_delta:
            mp_result = next(r for r in env.output["dedup_results"] if r["source"] == "MP")
            assert mp_result["matched"] is False

    def test_blocked_manifests_absent_in_stub_mode(self, adapter):
        adapter.generate({})
        assert adapter.get_blocked_manifests() == []

    def test_cif_valid_flag_true(self, adapter):
        envs = adapter.generate({})
        for env in envs:
            assert env.output["cif_valid"] is True

    def test_charge_neutral_flag_true(self, adapter):
        envs = adapter.generate({})
        for env in envs:
            assert env.output["charge_neutral"] is True

    def test_lematgen_s_deferred(self, adapter):
        """Stability (S) must be None — deferred to L1."""
        envs = adapter.generate({})
        for env in envs:
            assert env.output["lematgen_s_stable"] is None


class TestMatterGenRealBackendBlocked:
    def test_blocked_manifest_emitted_for_real_backend(self):

        from zer0pa_materials_workbench.envelope.config import MaterialsConfig
        # Monkeypatch env to fake mattergen_runpod backend.
        config = MaterialsConfig()
        adapter = MatterGenGeneratorAdapter(config=config, n_candidates=1)
        # Directly call _generate with the backend attribute overridden.
        adapter.config.__dict__["L6_GENERATOR_BACKEND"] = "mattergen_runpod"
        envelopes = adapter._generate({})
        assert len(adapter.get_blocked_manifests()) == 1
        bm = adapter.get_blocked_manifests()[0]
        assert isinstance(bm, BlockedSourceManifest)
        assert bm.blocker_reason == "license_unverified"
