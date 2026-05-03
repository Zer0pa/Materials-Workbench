"""Unit tests for ``SovereignCalphadPipeline``.

Coverage:
    - Pipeline runs end-to-end on synthetic data
    - Returns at least 5 envelopes (DFT/MLIP, prior, ESPEI, eq@300K, eq@700K, summary)
    - Each step's envelope validates against L3CalphadOutput
    - Information-geometry note propagates from ESPEI to summary
    - Battery-relevant temperature grid (300, 700) honored
    - Custom temperature grid override works
    - Back-edges record provenance
    - Blocked manifests aggregate from constituent adapters
"""

from __future__ import annotations

from pathlib import Path

import pytest

from zer0pa_materials_workbench.adapters.l3 import (
    L3CalphadRequest,
    SovereignCalphadPipeline,
)
from zer0pa_materials_workbench.envelope import Envelope, L3CalphadOutput

REPO_ROOT = Path(__file__).resolve().parents[4]
CU_MG_TDB = REPO_ROOT / "fixtures" / "tdb" / "Cu-Mg-toy.tdb"


def _req(suffix: str = "001") -> L3CalphadRequest:
    return L3CalphadRequest(
        run_id=f"run:l3/sovereign/{suffix}",
        candidate_id=f"candidate:novel-quaternary:{suffix}",
        campaign_id="campaign:l3-sovereign/001",
        rights_claim_id="rights:l3-sovereign/001",
        tdb_path=str(CU_MG_TDB),
        components=["CU", "MG"],
    )


class TestPipelineEndToEnd:
    @pytest.fixture(scope="class")
    def envelopes(self) -> list[dict]:
        pipeline = SovereignCalphadPipeline()
        return pipeline.run_with_chain(_req())

    def test_pipeline_returns_list(self, envelopes):
        assert isinstance(envelopes, list)

    def test_pipeline_produces_at_least_5_envelopes(self, envelopes):
        # DFT/MLIP, prior, ESPEI, eq@300, eq@700, summary -> 6
        assert len(envelopes) >= 5

    def test_every_envelope_validates(self, envelopes):
        for env in envelopes:
            clean = {k: v for k, v in env.items() if not k.startswith("_")}
            Envelope.model_validate(clean)

    def test_every_output_validates(self, envelopes):
        for env in envelopes:
            L3CalphadOutput.model_validate(env["output"])

    def test_every_layer_is_l3(self, envelopes):
        for env in envelopes:
            assert env["layer"] == "L3"

    def test_first_envelope_is_dft_mlip(self, envelopes):
        assert "dft-mlip" in envelopes[0]["tool_adapter"]["engine"]

    def test_second_envelope_is_prior(self, envelopes):
        # PhaseForgePlus prior step.
        assert "PhaseForgePlus" in envelopes[1]["tool_adapter"]["name"] or "phaseforgeplus" in envelopes[1]["tool_adapter"]["engine"].lower()

    def test_third_envelope_is_espei(self, envelopes):
        assert "Espei" in envelopes[2]["tool_adapter"]["name"] or "espei" in envelopes[2]["tool_adapter"]["engine"].lower()

    def test_summary_envelope_is_last(self, envelopes):
        last = envelopes[-1]
        assert last["tool_adapter"]["name"] == "SovereignCalphadPipeline"

    def test_summary_back_edges_populated(self, envelopes):
        summary = envelopes[-1]
        assert isinstance(summary["back_edges"], list)
        assert len(summary["back_edges"]) >= 4  # one per pre-summary step


class TestInformationGeometryPropagation:
    def test_espei_envelope_has_note(self):
        pipeline = SovereignCalphadPipeline()
        envs = pipeline.run_with_chain(_req())
        # ESPEI envelope is the third (index 2).
        espei_env = envs[2]
        assert "_information_geometry_note" in espei_env

    def test_summary_propagates_note(self):
        pipeline = SovereignCalphadPipeline()
        envs = pipeline.run_with_chain(_req())
        summary = envs[-1]
        assert "_information_geometry_note" in summary

    def test_summary_note_matches_espei_note(self):
        pipeline = SovereignCalphadPipeline()
        envs = pipeline.run_with_chain(_req())
        espei_env = envs[2]
        summary = envs[-1]
        assert summary["_information_geometry_note"] == espei_env["_information_geometry_note"]


class TestBatteryTemperatureGrid:
    def test_default_grid_300_700(self):
        pipeline = SovereignCalphadPipeline()
        assert pipeline.temperature_grid_K == (300.0, 700.0)

    def test_default_grid_produces_two_equilibrium_envelopes(self):
        pipeline = SovereignCalphadPipeline()
        envs = pipeline.run_with_chain(_req())
        # Two equilibrium calls (one per temperature in the default grid).
        meta = envs[-1]["_pipeline_meta"]
        assert meta["n_equilibrium_calls"] == 2

    def test_custom_grid_honored(self):
        pipeline = SovereignCalphadPipeline(temperature_grid_K=(298.0,))
        envs = pipeline.run_with_chain(_req())
        meta = envs[-1]["_pipeline_meta"]
        assert meta["n_equilibrium_calls"] == 1

    def test_three_temperature_grid(self):
        pipeline = SovereignCalphadPipeline(temperature_grid_K=(300.0, 500.0, 800.0))
        envs = pipeline.run_with_chain(_req())
        meta = envs[-1]["_pipeline_meta"]
        assert meta["n_equilibrium_calls"] == 3
        per_T = meta["per_temp_phase_fractions"]
        assert "300K" in per_T
        assert "500K" in per_T
        assert "800K" in per_T


class TestRunReturnsSummary:
    def test_run_returns_single_envelope(self):
        pipeline = SovereignCalphadPipeline()
        envelope = pipeline.run(_req())
        assert envelope["tool_adapter"]["name"] == "SovereignCalphadPipeline"

    def test_run_envelope_validates(self):
        pipeline = SovereignCalphadPipeline()
        envelope = pipeline.run(_req())
        clean = {k: v for k, v in envelope.items() if not k.startswith("_")}
        Envelope.model_validate(clean)


class TestUncertaintyForwarded:
    def test_summary_forwards_R_hat(self):
        pipeline = SovereignCalphadPipeline()
        envs = pipeline.run_with_chain(_req())
        summary = envs[-1]
        # ESPEI's R_hat must be in the summary's pipeline meta.
        meta = summary["_pipeline_meta"]
        assert meta["espei_R_hat"] is not None
        assert meta["espei_R_hat"] <= 1.1

    def test_summary_forwards_ESS(self):
        pipeline = SovereignCalphadPipeline()
        envs = pipeline.run_with_chain(_req())
        summary = envs[-1]
        meta = summary["_pipeline_meta"]
        assert meta["espei_ESS"] is not None
        assert meta["espei_ESS"] >= 200

    def test_summary_diagnostics_block_carries_uncertainty(self):
        pipeline = SovereignCalphadPipeline()
        envs = pipeline.run_with_chain(_req())
        summary = envs[-1]
        diags = summary["output"]["espei_diagnostics"]
        # The summary forwards the ESPEI step's diagnostics.
        assert diags["ran"] is True
        assert "R_hat" in diags
        assert "effective_sample_size" in diags


class TestBlockedManifestsAggregate:
    def test_blocked_manifests_collected(self):
        pipeline = SovereignCalphadPipeline()
        manifests = pipeline.blocked_manifests()
        # PhaseForgePlus is default-blocked -> at least one manifest.
        assert any(
            "phaseforgeplus" in m["source_manifest_id"].lower() for m in manifests
        )


class TestBackEdgesProvenance:
    def test_pipeline_back_edges_have_step_names(self):
        pipeline = SovereignCalphadPipeline()
        envs = pipeline.run_with_chain(_req())
        summary = envs[-1]
        # _pipeline_back_edges carries step metadata (parallel to back_edges).
        step_names = [be["step_name"] for be in summary["_pipeline_back_edges"]]
        assert "dft_mlip" in step_names
        assert "prior" in step_names
        assert "espei" in step_names
        # Equilibrium steps include temperature.
        assert any(s.startswith("equilibrium_") for s in step_names)

    def test_back_edges_record_audit_record_ids(self):
        pipeline = SovereignCalphadPipeline()
        envs = pipeline.run_with_chain(_req())
        summary = envs[-1]
        # Per the Envelope.BackEdge schema, every back_edge has audit_record_id.
        for be in summary["back_edges"]:
            assert "audit_record_id" in be
            assert be["audit_record_id"].startswith("audit:")
            assert be["layer"] == "L3"
            assert be["relation"] == "DERIVED_FROM"
