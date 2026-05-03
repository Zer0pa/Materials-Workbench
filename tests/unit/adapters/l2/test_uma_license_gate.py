"""Unit tests for UmaCalculatorAdapter license gate (RESISTANCE.md §UMA gate).

Critical tests:
    1. Default state is BLOCKED.
    2. Calling predict before enabling raises LicenseGateError.
    3. enable_uma with valid args unblocks.
    4. enable_uma with invalid args raises ValueError.
    5. BlockedSourceManifest is always emitted (regardless of gate state).
"""

from __future__ import annotations

import datetime as _dt

import pytest

from zer0pa_materials_workbench.adapters.l2.base import L2PredictRequest
from zer0pa_materials_workbench.adapters.l2.uma import LicenseGateError, UmaCalculatorAdapter
from zer0pa_materials_workbench.boundary import RESEARCH_BOUNDARY

SI_STRUCTURE = {
    "lattice_vectors": [[3.84, 0.0, 0.0], [0.0, 3.84, 0.0], [0.0, 0.0, 3.84]],
    "species": ["Si", "Si"],
    "fractional_coords": [[0.0, 0.0, 0.0], [0.5, 0.5, 0.5]],
}

VALID_AUP_TS = "2026-04-30T12:00:00+00:00"


@pytest.fixture
def adapter():
    return UmaCalculatorAdapter()


@pytest.fixture
def req():
    return L2PredictRequest(
        run_id="run:test/uma/si",
        candidate_id="candidate:Si:001",
        campaign_id="campaign:test/001",
        rights_claim_id="rights:test/001",
    )


class TestUmaDefaultBlocked:
    def test_default_is_not_enabled(self, adapter):
        assert adapter.is_enabled is False

    def test_predict_raises_license_gate_error(self, adapter, req):
        with pytest.raises(LicenseGateError):
            adapter.predict(SI_STRUCTURE, req)

    def test_license_gate_error_message(self, adapter, req):
        with pytest.raises(LicenseGateError) as exc_info:
            adapter.predict(SI_STRUCTURE, req)
        assert "BLOCKED" in str(exc_info.value)

    def test_blocked_manifests_emitted_when_blocked(self, adapter):
        manifests = adapter.blocked_manifests()
        assert len(manifests) >= 1
        assert manifests[0]["source_manifest_id"] == "src:uma:weights-fair-chem-v1"
        assert manifests[0]["blocker_reason"] == "license_unverified"


class TestUmaEnableGate:
    def test_enable_with_valid_args(self, adapter):
        adapter.enable_uma(
            hf_org="zer0pa-materials-workbench",
            hf_token="hf_testtoken123",
            aup_accepted_at=VALID_AUP_TS,
        )
        assert adapter.is_enabled is True

    def test_enable_with_datetime_object(self, adapter):
        dt = _dt.datetime(2026, 4, 30, 12, 0, 0, tzinfo=_dt.timezone.utc)
        adapter.enable_uma(
            hf_org="zer0pa-materials-workbench",
            hf_token="hf_testtoken123",
            aup_accepted_at=dt,
        )
        assert adapter.is_enabled is True

    def test_enable_invalid_empty_org_raises(self, adapter):
        with pytest.raises(ValueError, match="hf_org"):
            adapter.enable_uma(
                hf_org="",
                hf_token="hf_testtoken123",
                aup_accepted_at=VALID_AUP_TS,
            )

    def test_enable_invalid_token_prefix_raises(self, adapter):
        with pytest.raises(ValueError, match="hf_token"):
            adapter.enable_uma(
                hf_org="zer0pa",
                hf_token="sk-notahftoken",
                aup_accepted_at=VALID_AUP_TS,
            )

    def test_enable_naive_datetime_raises(self, adapter):
        naive_dt = _dt.datetime(2026, 4, 30, 12, 0, 0)  # no tz
        with pytest.raises(ValueError):
            adapter.enable_uma(
                hf_org="zer0pa",
                hf_token="hf_testtoken123",
                aup_accepted_at=naive_dt,
            )

    def test_enable_invalid_timestamp_string_raises(self, adapter):
        with pytest.raises(ValueError):
            adapter.enable_uma(
                hf_org="zer0pa",
                hf_token="hf_testtoken123",
                aup_accepted_at="not-a-timestamp",
            )

    def test_enable_without_tz_in_string_raises(self, adapter):
        with pytest.raises(ValueError):
            adapter.enable_uma(
                hf_org="zer0pa",
                hf_token="hf_testtoken123",
                aup_accepted_at="2026-04-30T12:00:00",  # no tz
            )


class TestUmaAfterEnable:
    @pytest.fixture
    def enabled_adapter(self, adapter):
        adapter.enable_uma(
            hf_org="zer0pa-materials-workbench",
            hf_token="hf_testtoken123",
            aup_accepted_at=VALID_AUP_TS,
        )
        return adapter

    def test_predict_does_not_raise(self, enabled_adapter, req):
        result = enabled_adapter.predict(SI_STRUCTURE, req)
        assert result is not None

    def test_predict_layer_is_L2(self, enabled_adapter, req):
        result = enabled_adapter.predict(SI_STRUCTURE, req)
        assert result["layer"] == "L2"

    def test_predict_boundary_verbatim(self, enabled_adapter, req):
        result = enabled_adapter.predict(SI_STRUCTURE, req)
        assert result["research_boundary"] == RESEARCH_BOUNDARY

    def test_predict_has_uma_model(self, enabled_adapter, req):
        result = enabled_adapter.predict(SI_STRUCTURE, req)
        pred_models = [p["model"] for p in result["output"]["predictions"]]
        assert any("UMA" in m for m in pred_models)

    def test_predict_uma_gate_block_in_envelope(self, enabled_adapter, req):
        result = enabled_adapter.predict(SI_STRUCTURE, req)
        gate = result.get("_uma_gate", {})
        assert gate.get("hf_org") == "zer0pa-materials-workbench"
        assert gate.get("aup_accepted_at") == VALID_AUP_TS

    def test_blocked_manifests_still_emitted_after_enable(self, enabled_adapter):
        """BlockedSourceManifest MUST be emitted regardless of gate state
        because the weights remain a real-weight dependency."""
        manifests = enabled_adapter.blocked_manifests()
        assert len(manifests) >= 1
        assert "src:uma" in manifests[0]["source_manifest_id"]


class TestUmaBlockedManifestContent:
    def test_manifest_mentions_fair_chem_license(self, adapter):
        m = adapter.blocked_manifests()[0]
        assert "FAIR Chemistry License" in m["blocker_detail"]

    def test_manifest_mentions_south_africa_unrestricted(self, adapter):
        m = adapter.blocked_manifests()[0]
        assert "South Africa" in m["blocker_detail"]

    def test_manifest_mentions_mit_library(self, adapter):
        # CORRECTION 2026-04-30: live verification of facebookresearch/fairchem
        # LICENSE shows MIT, not Apache-2.0 as Brief #2 originally stated.
        m = adapter.blocked_manifests()[0]
        assert "MIT" in m["blocker_detail"]

    def test_manifest_retry_strategy_mentions_enable_uma(self, adapter):
        m = adapter.blocked_manifests()[0]
        assert "enable_uma" in m["retry_strategy"]

    def test_manifest_blocked_at_is_iso_utc(self, adapter):
        m = adapter.blocked_manifests()[0]
        ts = m.get("blocked_at", "")
        assert "T" in ts  # ISO format
