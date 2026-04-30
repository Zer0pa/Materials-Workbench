"""Unit tests for ``PhaseForgePlusMlipPriorAdapter`` (PRD §L3 license-gate).

Coverage:
    - Default-blocked: BlockedSourceManifest emitted, falsifier returns "blocked"
    - enable_with_verified_license() flips the gate
    - Pre-enable: synthetic prior is still served (numerically valid)
    - Post-enable: license_spdx, verified_at recorded in _phaseforgeplus_meta
    - Falsifier l3.phaseforgeplus_license_gate triggers correctly
"""

from __future__ import annotations

import datetime as _dt

import pytest

from zer0pa_materials.adapters.l3 import L3CalphadRequest, PhaseForgePlusMlipPriorAdapter
from zer0pa_materials.envelope import Envelope, L3CalphadOutput
from zer0pa_materials.falsifiers.l3_falsifiers import phaseforgeplus_license_gate


def _req(suffix: str = "001") -> L3CalphadRequest:
    return L3CalphadRequest(
        run_id=f"run:l3/pfp/{suffix}",
        candidate_id=f"candidate:novel-quaternary:{suffix}",
        campaign_id="campaign:l3-pfp/001",
        rights_claim_id="rights:l3-pfp/001",
    )


class TestDefaultBlocked:
    @pytest.fixture
    def adapter(self) -> PhaseForgePlusMlipPriorAdapter:
        return PhaseForgePlusMlipPriorAdapter()

    def test_default_disabled(self, adapter):
        assert adapter.enabled is False

    def test_default_no_license_spdx(self, adapter):
        assert adapter.license_spdx is None

    def test_default_no_license_proof(self, adapter):
        assert adapter.license_proof_uri is None

    def test_default_no_verified_at(self, adapter):
        assert adapter.verified_at is None

    def test_blocked_manifest_emitted(self, adapter):
        manifests = adapter.blocked_manifests()
        assert len(manifests) == 1
        m = manifests[0]
        assert m["source_manifest_id"] == "src:phaseforgeplus:library"
        assert m["blocker_reason"] == "license_unverified"

    def test_blocked_manifest_has_retry_strategy(self, adapter):
        manifests = adapter.blocked_manifests()
        assert "enable_with_verified_license" in manifests[0]["retry_strategy"]


class TestRunWhileBlocked:
    """Even when blocked, the adapter still serves a synthetic prior."""

    @pytest.fixture
    def envelope(self) -> dict:
        return PhaseForgePlusMlipPriorAdapter().run(_req())

    def test_returns_envelope(self, envelope):
        assert envelope is not None

    def test_layer_is_l3(self, envelope):
        assert envelope["layer"] == "L3"

    def test_envelope_validates(self, envelope):
        clean = {k: v for k, v in envelope.items() if not k.startswith("_")}
        Envelope.model_validate(clean)

    def test_output_validates(self, envelope):
        L3CalphadOutput.model_validate(envelope["output"])

    def test_backend_is_stub(self, envelope):
        assert envelope["tool_adapter"]["backend"] == "stub"

    def test_engine_marks_blocked(self, envelope):
        assert "blocked" in envelope["tool_adapter"]["engine"]

    def test_falsifier_block_marks_blocked(self, envelope):
        assert envelope["falsifier"]["status"] == "blocked"

    def test_pfp_meta_present(self, envelope):
        assert "_phaseforgeplus_meta" in envelope

    def test_pfp_meta_enabled_false(self, envelope):
        assert envelope["_phaseforgeplus_meta"]["enabled"] is False

    def test_prior_mean_present_in_diagnostics(self, envelope):
        # Synthetic prior is recorded so downstream ESPEI can consume it.
        diags = envelope["output"]["espei_diagnostics"]
        assert "prior_mean" in diags
        assert isinstance(diags["prior_mean"], list)
        assert len(diags["prior_mean"]) == 4

    def test_prior_cov_diag_present(self, envelope):
        diags = envelope["output"]["espei_diagnostics"]
        assert "prior_cov_diag" in diags
        assert all(v > 0.0 for v in diags["prior_cov_diag"])

    def test_license_status_marked_blocked(self, envelope):
        diags = envelope["output"]["espei_diagnostics"]
        assert diags["license_status"] == "unverified_blocked"

    def test_license_gate_falsifier_returns_blocked(self, envelope):
        result = phaseforgeplus_license_gate(envelope)
        assert result.status == "blocked"


class TestEnableWithLicense:
    @pytest.fixture
    def adapter(self) -> PhaseForgePlusMlipPriorAdapter:
        a = PhaseForgePlusMlipPriorAdapter()
        a.enable_with_verified_license(
            license_proof_uri="https://github.com/dogusariturk/PhaseForgePlus/blob/main/LICENSE",
            license_spdx="MIT",
            verified_at="2026-04-30T12:00:00+00:00",
        )
        return a

    def test_enabled_flag_true(self, adapter):
        assert adapter.enabled is True

    def test_license_spdx_recorded(self, adapter):
        assert adapter.license_spdx == "MIT"

    def test_license_proof_recorded(self, adapter):
        assert "PhaseForgePlus" in adapter.license_proof_uri

    def test_verified_at_recorded(self, adapter):
        assert adapter.verified_at == "2026-04-30T12:00:00+00:00"

    def test_blocked_manifest_empty_when_enabled(self, adapter):
        assert adapter.blocked_manifests() == []

    def test_run_after_enable_changes_backend(self, adapter):
        envelope = adapter.run(_req())
        assert envelope["tool_adapter"]["backend"] == "phaseforgeplus_local_pending"

    def test_run_after_enable_marks_falsifier_pass(self, adapter):
        envelope = adapter.run(_req())
        assert envelope["falsifier"]["status"] == "pass"

    def test_license_gate_falsifier_returns_pass(self, adapter):
        envelope = adapter.run(_req())
        result = phaseforgeplus_license_gate(envelope)
        assert result.status == "pass"

    def test_license_status_marked_verified(self, adapter):
        envelope = adapter.run(_req())
        diags = envelope["output"]["espei_diagnostics"]
        assert diags["license_status"] == "verified"


class TestEnableValidation:
    def test_empty_license_proof_uri_raises(self):
        adapter = PhaseForgePlusMlipPriorAdapter()
        with pytest.raises(ValueError):
            adapter.enable_with_verified_license(
                license_proof_uri="",
                license_spdx="MIT",
            )

    def test_empty_license_spdx_raises(self):
        adapter = PhaseForgePlusMlipPriorAdapter()
        with pytest.raises(ValueError):
            adapter.enable_with_verified_license(
                license_proof_uri="https://example.com/LICENSE",
                license_spdx="",
            )

    def test_default_verified_at_is_iso(self):
        adapter = PhaseForgePlusMlipPriorAdapter()
        adapter.enable_with_verified_license(
            license_proof_uri="https://example.com/LICENSE",
            license_spdx="MIT",
        )
        # Should parse as ISO-8601.
        _dt.datetime.fromisoformat(adapter.verified_at)


class TestPriorDeterminism:
    def test_same_request_same_prior_mean(self):
        env_a = PhaseForgePlusMlipPriorAdapter().run(_req("det"))
        env_b = PhaseForgePlusMlipPriorAdapter().run(_req("det"))
        mean_a = env_a["output"]["espei_diagnostics"]["prior_mean"]
        mean_b = env_b["output"]["espei_diagnostics"]["prior_mean"]
        assert mean_a == mean_b

    def test_different_candidate_different_prior(self):
        env_a = PhaseForgePlusMlipPriorAdapter().run(_req("a"))
        env_b = PhaseForgePlusMlipPriorAdapter().run(_req("b"))
        # Hash-seeded perturbation: different candidate IDs -> different
        # priors (small but nonzero perturbation).
        mean_a = env_a["output"]["espei_diagnostics"]["prior_mean"]
        mean_b = env_b["output"]["espei_diagnostics"]["prior_mean"]
        assert mean_a != mean_b
