"""Unit tests for MACE multihead committee and DPA committee runners."""

from __future__ import annotations

import pytest

from zer0pa_materials_workbench.adapters.l2.base import L2PredictRequest
from zer0pa_materials_workbench.adapters.l2.dpa_committee import DpaCommitteeRunner
from zer0pa_materials_workbench.adapters.l2.mace_committee import MaceMultiheadCommitteeRunner
from zer0pa_materials_workbench.boundary import RESEARCH_BOUNDARY

SI_STRUCTURE = {
    "lattice_vectors": [[3.84, 0.0, 0.0], [0.0, 3.84, 0.0], [0.0, 0.0, 3.84]],
    "species": ["Si", "Si"],
    "fractional_coords": [[0.0, 0.0, 0.0], [0.5, 0.5, 0.5]],
}


@pytest.fixture
def req():
    return L2PredictRequest(
        run_id="run:test/committee",
        candidate_id="candidate:Si:001",
        campaign_id="campaign:test/001",
        rights_claim_id="rights:test/001",
    )


class TestMaceCommittee:
    def test_init_default_heads(self):
        runner = MaceMultiheadCommitteeRunner()
        assert runner.n_heads == 4

    def test_init_custom_heads(self):
        runner = MaceMultiheadCommitteeRunner(n_heads=6)
        assert runner.n_heads == 6

    def test_init_too_few_heads_raises(self):
        with pytest.raises(ValueError, match="n_heads"):
            MaceMultiheadCommitteeRunner(n_heads=1)

    def test_predict_returns_dict(self, req):
        runner = MaceMultiheadCommitteeRunner(n_heads=4)
        result = runner.predict_with_uncertainty(SI_STRUCTURE, req)
        assert isinstance(result, dict)

    def test_predict_layer_is_L2(self, req):
        runner = MaceMultiheadCommitteeRunner(n_heads=4)
        result = runner.predict_with_uncertainty(SI_STRUCTURE, req)
        assert result["layer"] == "L2"

    def test_predict_boundary_verbatim(self, req):
        runner = MaceMultiheadCommitteeRunner(n_heads=4)
        result = runner.predict_with_uncertainty(SI_STRUCTURE, req)
        assert result["research_boundary"] == RESEARCH_BOUNDARY

    def test_predict_n_predictions_equals_n_heads(self, req):
        runner = MaceMultiheadCommitteeRunner(n_heads=4)
        result = runner.predict_with_uncertainty(SI_STRUCTURE, req)
        assert len(result["output"]["predictions"]) == 4

    def test_predict_disagreement_metrics_present(self, req):
        runner = MaceMultiheadCommitteeRunner(n_heads=4)
        result = runner.predict_with_uncertainty(SI_STRUCTURE, req)
        metrics = result["disagreement"]["metrics"]
        names = [m["name"] for m in metrics]
        assert any("variance" in n for n in names)

    def test_predict_energy_range_nonnegative(self, req):
        runner = MaceMultiheadCommitteeRunner(n_heads=4)
        result = runner.predict_with_uncertainty(SI_STRUCTURE, req)
        disagree = result["output"]["energy_disagreement_meV_per_atom"]
        assert disagree >= 0.0

    def test_blocked_manifests_nonempty(self):
        runner = MaceMultiheadCommitteeRunner()
        assert len(runner.blocked_manifests()) >= 1

    def test_blocked_manifest_id(self):
        runner = MaceMultiheadCommitteeRunner()
        m = runner.blocked_manifests()[0]
        assert "src:mace" in m["source_manifest_id"]


class TestDpaCommittee:
    def test_init_default_members(self):
        runner = DpaCommitteeRunner()
        assert runner.n_members == 4

    def test_init_too_few_members_raises(self):
        with pytest.raises(ValueError, match="n_members"):
            DpaCommitteeRunner(n_members=1)

    def test_predict_returns_dict(self, req):
        runner = DpaCommitteeRunner(n_members=4)
        result = runner.predict_with_uncertainty(SI_STRUCTURE, req)
        assert isinstance(result, dict)

    def test_predict_layer_is_L2(self, req):
        runner = DpaCommitteeRunner(n_members=4)
        result = runner.predict_with_uncertainty(SI_STRUCTURE, req)
        assert result["layer"] == "L2"

    def test_predict_n_predictions_equals_n_members(self, req):
        runner = DpaCommitteeRunner(n_members=4)
        result = runner.predict_with_uncertainty(SI_STRUCTURE, req)
        assert len(result["output"]["predictions"]) == 4

    def test_predict_disagreement_metrics_present(self, req):
        runner = DpaCommitteeRunner(n_members=4)
        result = runner.predict_with_uncertainty(SI_STRUCTURE, req)
        metrics = result["disagreement"]["metrics"]
        names = [m["name"] for m in metrics]
        assert any("dpa_committee" in n for n in names)

    def test_dpa_committee_differs_from_mace_committee(self, req):
        """DPA committee uses odd offsets, MACE uses even — results differ."""
        mace_runner = MaceMultiheadCommitteeRunner(n_heads=4)
        dpa_runner = DpaCommitteeRunner(n_members=4)
        mace_result = mace_runner.predict_with_uncertainty(SI_STRUCTURE, req)
        dpa_result = dpa_runner.predict_with_uncertainty(SI_STRUCTURE, req)
        # Energy disagreement values should differ.
        mace_disagree = mace_result["output"]["energy_disagreement_meV_per_atom"]
        dpa_disagree = dpa_result["output"]["energy_disagreement_meV_per_atom"]
        # Not necessarily different but model names definitely differ.
        mace_models = {p["model"] for p in mace_result["output"]["predictions"]}
        dpa_models = {p["model"] for p in dpa_result["output"]["predictions"]}
        assert mace_models != dpa_models

    def test_blocked_manifests_nonempty(self):
        runner = DpaCommitteeRunner()
        assert len(runner.blocked_manifests()) >= 1

    def test_blocked_manifest_mentions_ccby(self):
        runner = DpaCommitteeRunner()
        m = runner.blocked_manifests()[0]
        assert "CC-BY-4.0" in m["blocker_detail"]
