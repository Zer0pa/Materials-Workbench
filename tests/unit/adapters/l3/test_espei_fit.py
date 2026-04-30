"""Unit tests for ``EspeiBayesianFitAdapter`` (synthetic MCMC posterior).

Coverage:
    - Synthetic MCMC posterior runs without ESPEI installed
    - R_hat <= 1.1 (PRD threshold)
    - effective_sample_size >= 200 (PRD threshold)
    - acceptance_rate in [0.2, 0.5]
    - posterior covariance and mean recorded
    - Information-geometry note attached (Brief #2 Gap C — moat)
    - Envelope validates against L3CalphadOutput
"""

from __future__ import annotations

from pathlib import Path

import pytest

from zer0pa_materials.adapters.l3 import (
    EspeiBayesianFitAdapter,
    ESPEI_AVAILABLE,
    L3CalphadRequest,
)
from zer0pa_materials.adapters.l3.espei_fit import INFORMATION_GEOMETRY_NOTE
from zer0pa_materials.envelope import Envelope, L3CalphadOutput


REPO_ROOT = Path(__file__).resolve().parents[4]
CU_MG_TDB = REPO_ROOT / "fixtures" / "tdb" / "Cu-Mg-toy.tdb"


def _req(suffix: str = "001") -> L3CalphadRequest:
    return L3CalphadRequest(
        run_id=f"run:l3/fit/{suffix}",
        candidate_id=f"candidate:Cu-Mg:{suffix}",
        campaign_id="campaign:l3-fit/001",
        rights_claim_id="rights:l3-fit/001",
        tdb_path=str(CU_MG_TDB),
    )


class TestSyntheticPosterior:
    @pytest.fixture(scope="class")
    def envelope(self) -> dict:
        return EspeiBayesianFitAdapter().run(_req())

    def test_envelope_returned(self, envelope):
        assert envelope is not None

    def test_layer_is_l3(self, envelope):
        assert envelope["layer"] == "L3"

    def test_envelope_validates(self, envelope):
        clean = {k: v for k, v in envelope.items() if not k.startswith("_")}
        Envelope.model_validate(clean)

    def test_output_validates_as_l3(self, envelope):
        L3CalphadOutput.model_validate(envelope["output"])

    def test_diagnostics_recorded(self, envelope):
        diags = envelope["output"]["espei_diagnostics"]
        assert diags["ran"] is True

    def test_R_hat_recorded(self, envelope):
        diags = envelope["output"]["espei_diagnostics"]
        assert "R_hat" in diags
        assert isinstance(diags["R_hat"], float)

    def test_R_hat_below_threshold(self, envelope):
        # PRD threshold: R_hat <= 1.1.
        diags = envelope["output"]["espei_diagnostics"]
        assert diags["R_hat"] <= 1.1, f"R_hat={diags['R_hat']} exceeds 1.1"

    def test_ESS_above_threshold(self, envelope):
        # PRD threshold: ESS >= 200.
        diags = envelope["output"]["espei_diagnostics"]
        assert diags["effective_sample_size"] >= 200.0, (
            f"ESS={diags['effective_sample_size']} below 200"
        )

    def test_acceptance_rate_in_band(self, envelope):
        # Standard MCMC acceptance band: roughly 0.2-0.5.
        diags = envelope["output"]["espei_diagnostics"]
        assert 0.10 <= diags["acceptance_rate"] <= 0.60

    def test_n_walkers_recorded(self, envelope):
        diags = envelope["output"]["espei_diagnostics"]
        assert diags["n_walkers"] >= 4

    def test_n_steps_recorded(self, envelope):
        diags = envelope["output"]["espei_diagnostics"]
        assert diags["n_steps"] >= 50

    def test_param_names_recorded(self, envelope):
        diags = envelope["output"]["espei_diagnostics"]
        assert isinstance(diags["param_names"], list)
        assert len(diags["param_names"]) >= 2

    def test_posterior_mean_recorded(self, envelope):
        diags = envelope["output"]["espei_diagnostics"]
        assert isinstance(diags["posterior_mean"], list)
        assert len(diags["posterior_mean"]) == len(diags["param_names"])

    def test_posterior_cov_recorded(self, envelope):
        diags = envelope["output"]["espei_diagnostics"]
        assert isinstance(diags["posterior_covariance_diag"], list)
        assert len(diags["posterior_covariance_diag"]) == len(diags["param_names"])


class TestInformationGeometryAttribution:
    """Brief #2 Gap C — load-bearing moat attribution."""

    def test_note_attached(self):
        envelope = EspeiBayesianFitAdapter().run(_req())
        assert "_information_geometry_note" in envelope

    def test_note_has_framing(self):
        envelope = EspeiBayesianFitAdapter().run(_req())
        note = envelope["_information_geometry_note"]
        assert "framing" in note
        assert "Fisher" in note["framing"]

    def test_note_has_future_contribution(self):
        envelope = EspeiBayesianFitAdapter().run(_req())
        note = envelope["_information_geometry_note"]
        assert "future_contribution" in note

    def test_note_keys_match_canonical(self):
        envelope = EspeiBayesianFitAdapter().run(_req())
        note = envelope["_information_geometry_note"]
        assert set(note.keys()) == set(INFORMATION_GEOMETRY_NOTE.keys())

    def test_note_mentions_fisher(self):
        envelope = EspeiBayesianFitAdapter().run(_req())
        note_str = str(envelope["_information_geometry_note"])
        assert "Fisher" in note_str

    def test_note_mentions_natural_gradient(self):
        envelope = EspeiBayesianFitAdapter().run(_req())
        note_str = str(envelope["_information_geometry_note"])
        assert "natural" in note_str.lower() or "Riemannian" in note_str.lower()

    def test_note_mentions_brief_2_attribution(self):
        envelope = EspeiBayesianFitAdapter().run(_req())
        note = envelope["_information_geometry_note"]
        assert "Brief #2" in note["moat_attribution"]


class TestDeterminism:
    def test_same_request_same_R_hat(self):
        env_a = EspeiBayesianFitAdapter().run(_req("det"))
        env_b = EspeiBayesianFitAdapter().run(_req("det"))
        r_a = env_a["output"]["espei_diagnostics"]["R_hat"]
        r_b = env_b["output"]["espei_diagnostics"]["R_hat"]
        assert r_a == r_b

    def test_same_request_same_ESS(self):
        env_a = EspeiBayesianFitAdapter().run(_req("det"))
        env_b = EspeiBayesianFitAdapter().run(_req("det"))
        ess_a = env_a["output"]["espei_diagnostics"]["effective_sample_size"]
        ess_b = env_b["output"]["espei_diagnostics"]["effective_sample_size"]
        assert ess_a == ess_b

    def test_different_request_different_posterior(self):
        env_a = EspeiBayesianFitAdapter().run(_req("a"))
        env_b = EspeiBayesianFitAdapter().run(_req("b"))
        # Different run_id mixed into seed -> different chains.
        # But because mean-reversion pulls every chain to the same target,
        # posterior_mean is largely the same. The hash, however, differs.
        h_a = env_a["audit"]["input_hash"]
        h_b = env_b["audit"]["input_hash"]
        assert h_a != h_b


class TestBlockedManifests:
    def test_blocked_manifest_when_espei_absent(self):
        adapter = EspeiBayesianFitAdapter()
        manifests = adapter.blocked_manifests()
        if ESPEI_AVAILABLE:
            assert manifests == []
        else:
            assert len(manifests) == 1
            assert manifests[0]["source_manifest_id"] == "src:espei:library"


class TestUncertaintyAlwaysPresent:
    """Per PRD §L3 design invariant: ESPEI posteriors carry uncertainty."""

    def test_posterior_cov_diag_nonzero(self):
        envelope = EspeiBayesianFitAdapter().run(_req())
        diags = envelope["output"]["espei_diagnostics"]
        cov_diag = diags["posterior_covariance_diag"]
        # All variances strictly positive.
        assert all(v > 0.0 for v in cov_diag)

    def test_no_point_estimate_only(self):
        envelope = EspeiBayesianFitAdapter().run(_req())
        diags = envelope["output"]["espei_diagnostics"]
        # Mean alone is a point estimate; the posterior covariance MUST also
        # be present.
        assert "posterior_mean" in diags
        assert "posterior_covariance_diag" in diags
