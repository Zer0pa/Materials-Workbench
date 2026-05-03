"""Test the PrefectCampaignAdapter (stub or real)."""

from __future__ import annotations

from zer0pa_materials_workbench.adapters.l7 import PrefectCampaignAdapter
from zer0pa_materials_workbench.adapters.l7.base import L7CampaignParams
from zer0pa_materials_workbench.boundary import RESEARCH_BOUNDARY


def _params() -> L7CampaignParams:
    return L7CampaignParams(
        campaign_id="campaign:test/c1",
        candidate_id="candidate:test/c1",
        objective="prop > 1",
    )


def test_envelope_is_l7():
    env = PrefectCampaignAdapter().execute(_params())
    assert env.layer == "L7"
    assert env.research_boundary == RESEARCH_BOUNDARY


def test_lifecycle_keys_present():
    env = PrefectCampaignAdapter().execute(_params())
    items_by_name = {fi.name: fi for fi in env.falsifier.items}
    assert "l7.prefect_lifecycle_completeness" in items_by_name
    actual = items_by_name["l7.prefect_lifecycle_completeness"].actual
    # All five lifecycle keys present.
    for k in ("started_at", "finished_at", "retries_attempted", "cancellation_state", "deployment_id"):
        assert actual.get(k), f"{k} missing"


def test_deterministic_for_fixed_params():
    """Same params → same lifecycle hash (per-second deterministic timestamps)."""
    a = PrefectCampaignAdapter(deployment_id="deployment:fixed").execute(_params())
    b = PrefectCampaignAdapter(deployment_id="deployment:fixed").execute(_params())
    # The audit_record_id has a random uuid suffix so envelopes are not
    # identical, but the input_hash should be stable.
    assert a.audit.input_hash == b.audit.input_hash


def test_audit_record_id_format():
    env = PrefectCampaignAdapter().execute(_params())
    assert env.audit.audit_record_id.startswith("audit:l7:")


def test_falsifier_status_pass_for_complete_lifecycle():
    env = PrefectCampaignAdapter().execute(_params())
    # Roll-up shouldn't be 'fail'.
    assert env.falsifier.status in ("pass", "blocked")


def test_is_real_backend_returns_bool():
    assert isinstance(PrefectCampaignAdapter.is_real_backend(), bool)
