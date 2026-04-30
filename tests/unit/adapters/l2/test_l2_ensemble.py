"""Unit tests for L2EnsembleRunner — DPA + MACE mandatory by construction."""

from __future__ import annotations

import pytest

from zer0pa_materials.adapters.l2.base import L2PredictRequest
from zer0pa_materials.adapters.l2.ensemble import L2EnsembleRunner, _decide_routing
from zer0pa_materials.boundary import RESEARCH_BOUNDARY
from zer0pa_materials.envelope.envelope import Envelope
from zer0pa_materials.envelope.layer_outputs import L2MlipOutput


SI_STRUCTURE = {
    "lattice_vectors": [[3.84, 0.0, 0.0], [0.0, 3.84, 0.0], [0.0, 0.0, 3.84]],
    "species": ["Si", "Si"],
    "fractional_coords": [[0.0, 0.0, 0.0], [0.5, 0.5, 0.5]],
}

LLZO_STRUCTURE = {
    "lattice_vectors": [[12.97, 0.0, 0.0], [0.0, 12.97, 0.0], [0.0, 0.0, 12.97]],
    "species": ["Li"] * 7 + ["La"] * 3 + ["Zr"] * 2 + ["O"] * 12,
    "fractional_coords": [[i * 0.04, i * 0.04, i * 0.04] for i in range(24)],
}


@pytest.fixture
def runner():
    return L2EnsembleRunner()


@pytest.fixture
def req():
    return L2PredictRequest(
        run_id="run:test/ensemble/si",
        candidate_id="candidate:Si:001",
        campaign_id="campaign:test/001",
        rights_claim_id="rights:test/001",
    )


class TestRoutingDecisionFunction:
    def test_low_disagreement_promotes(self):
        assert _decide_routing(10.0, 0.05) == "promote"

    def test_energy_above_25_queues(self):
        assert _decide_routing(30.0, 0.05) == "queue_dft"

    def test_force_above_015_queues(self):
        assert _decide_routing(10.0, 0.20) == "queue_dft"

    def test_energy_above_75_hard_rejects(self):
        assert _decide_routing(80.0, 0.05) == "hard_reject"

    def test_force_above_035_hard_rejects(self):
        assert _decide_routing(10.0, 0.40) == "hard_reject"

    def test_hard_reject_takes_priority_over_queue(self):
        # Both thresholds exceeded: hard_reject wins.
        assert _decide_routing(80.0, 0.40) == "hard_reject"

    def test_exactly_at_25_promotes(self):
        assert _decide_routing(25.0, 0.05) == "promote"

    def test_exactly_at_75_promotes(self):
        # > 75 is hard_reject; == 75 is still queue_dft (25 < 75).
        assert _decide_routing(75.0, 0.05) == "queue_dft"


class TestEnsembleRunnerShape:
    def test_run_returns_dict(self, runner, req):
        result = runner.run(SI_STRUCTURE, req)
        assert isinstance(result, dict)

    def test_run_layer_is_L2(self, runner, req):
        result = runner.run(SI_STRUCTURE, req)
        assert result["layer"] == "L2"

    def test_run_boundary_verbatim(self, runner, req):
        result = runner.run(SI_STRUCTURE, req)
        assert result["research_boundary"] == RESEARCH_BOUNDARY

    def test_run_output_has_predictions(self, runner, req):
        result = runner.run(SI_STRUCTURE, req)
        assert "predictions" in result["output"]

    def test_run_both_dpa_and_mace_present(self, runner, req):
        result = runner.run(SI_STRUCTURE, req)
        models = {p["model"] for p in result["output"]["predictions"]}
        assert "DPA-3.1-3M" in models
        assert "MACE-MPA-0" in models

    def test_run_at_least_two_predictions(self, runner, req):
        result = runner.run(SI_STRUCTURE, req)
        assert len(result["output"]["predictions"]) >= 2

    def test_run_energy_disagreement_computed(self, runner, req):
        result = runner.run(SI_STRUCTURE, req)
        disagree = result["output"]["energy_disagreement_meV_per_atom"]
        assert disagree >= 0.0

    def test_run_force_rmse_disagreement_computed(self, runner, req):
        result = runner.run(SI_STRUCTURE, req)
        disagree = result["output"]["force_rmse_disagreement_eV_per_Ang"]
        assert disagree >= 0.0

    def test_run_routing_decision_present(self, runner, req):
        result = runner.run(SI_STRUCTURE, req)
        assert result["output"]["routing_decision"] in {"promote", "queue_dft", "hard_reject"}

    def test_run_falsifier_block_present(self, runner, req):
        result = runner.run(SI_STRUCTURE, req)
        assert "falsifier" in result
        assert "status" in result["falsifier"]
        assert "items" in result["falsifier"]

    def test_run_disagreement_metrics_present(self, runner, req):
        result = runner.run(SI_STRUCTURE, req)
        metrics = result["disagreement"]["metrics"]
        assert len(metrics) >= 1

    def test_run_ensemble_envelope_validates(self, runner, req):
        result = runner.run(SI_STRUCTURE, req)
        result_clean = {k: v for k, v in result.items() if not k.startswith("_")}
        env = Envelope.model_validate(result_clean)
        assert env.layer == "L2"

    def test_run_l2_output_validates(self, runner, req):
        result = runner.run(SI_STRUCTURE, req)
        l2out = L2MlipOutput.model_validate(result["output"])
        assert len(l2out.predictions) >= 2


class TestEnsembleRunnerDisagreement:
    def test_disagreement_is_nonzero_for_si(self, runner, req):
        """DPA and MACE have different seed offsets → non-zero disagreement."""
        result = runner.run(SI_STRUCTURE, req)
        disagree = result["output"]["energy_disagreement_meV_per_atom"]
        # With different seed offsets the two stubs MUST differ.
        assert disagree > 0.0

    def test_dpa_mace_relation_in_meta(self, runner, req):
        result = runner.run(SI_STRUCTURE, req)
        relation = result["_ensemble_meta"].get("dpa_mace_relation")
        assert relation in {"AGREES_WITH", "CONTRADICTS"}

    def test_meta_contains_routing(self, runner, req):
        result = runner.run(SI_STRUCTURE, req)
        meta = result["_ensemble_meta"]
        assert "routing_decision" in meta


class TestEnsembleRunnerFalsifiers:
    def test_falsifier_items_produced(self, runner, req):
        result = runner.run(SI_STRUCTURE, req)
        items = result["falsifier"]["items"]
        # At minimum the 4 L2MlipOutput falsifiers should be present.
        assert len(items) >= 4

    def test_falsifier_names_contain_l2(self, runner, req):
        result = runner.run(SI_STRUCTURE, req)
        names = {f["name"] for f in result["falsifier"]["items"]}
        assert any("l2." in name for name in names)


class TestSingleModelPromotionBlocked:
    """RESISTANCE.md: test that only DPA runs + routing_decision=promote MUST fail."""

    def test_single_model_envelope_fails_falsifier(self):
        """Envelope with single model + routing_decision=promote fails single_model_promotion_block."""
        from zer0pa_materials.falsifiers.l2_falsifiers import single_model_promotion_block

        single_model_envelope = {
            "output": {
                "predictions": [{"model": "DPA-3.1-3M", "energy_eV_per_atom": -5.0, "force_rmse_eV_per_Ang": 0.05}],
                "energy_disagreement_meV_per_atom": 0.0,
                "force_rmse_disagreement_eV_per_Ang": 0.0,
                "routing_decision": "promote",
            }
        }
        result = single_model_promotion_block(single_model_envelope)
        assert result.status == "fail"

    def test_dual_model_promote_passes_falsifier(self):
        from zer0pa_materials.falsifiers.l2_falsifiers import single_model_promotion_block

        dual_model_envelope = {
            "output": {
                "predictions": [
                    {"model": "DPA-3.1-3M", "energy_eV_per_atom": -5.0, "force_rmse_eV_per_Ang": 0.05},
                    {"model": "MACE-MPA-0", "energy_eV_per_atom": -5.01, "force_rmse_eV_per_Ang": 0.05},
                ],
                "energy_disagreement_meV_per_atom": 10.0,
                "force_rmse_disagreement_eV_per_Ang": 0.0,
                "routing_decision": "promote",
            }
        }
        result = single_model_promotion_block(dual_model_envelope)
        assert result.status == "pass"


class TestEnsembleBlockedManifests:
    def test_blocked_manifests_include_dpa_and_mace(self, runner):
        manifests = runner.blocked_manifests()
        ids = {m["source_manifest_id"] for m in manifests}
        assert "src:deepmd:dpa-3.1-3m-weights" in ids
        assert "src:mace:mpa0-checkpoint" in ids
