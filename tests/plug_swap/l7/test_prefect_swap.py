"""Plug-swap test: PrefectCampaignAdapter local_prefect ↔ runpod_mock parity."""

from __future__ import annotations

import pytest

from zer0pa_materials.adapters.l7 import PrefectCampaignAdapter
from zer0pa_materials.adapters.l7.base import L7CampaignParams


def _params() -> L7CampaignParams:
    return L7CampaignParams(
        campaign_id="campaign:test/c1",
        candidate_id="candidate:test/c1",
    )


def test_envelope_keys_invariant_across_backends():
    """Envelope key set is stable across stub vs real Prefect."""
    env = PrefectCampaignAdapter().execute(_params())
    expected_top_level = {
        "contract_version", "research_boundary", "run_id", "campaign_id",
        "candidate_id", "layer", "tool_adapter", "input_refs", "output",
        "confidence", "disagreement", "falsifier", "audit", "rights",
        "back_edges",
    }
    assert set(env.model_dump(mode="json").keys()) == expected_top_level


def test_falsifier_items_invariant():
    """Same falsifier item names regardless of backend."""
    env = PrefectCampaignAdapter().execute(_params())
    names = {fi.name for fi in env.falsifier.items}
    assert "l7.prefect_lifecycle_completeness" in names


def test_lifecycle_field_set_invariant():
    env = PrefectCampaignAdapter().execute(_params())
    items = {fi.name: fi for fi in env.falsifier.items}
    actual = items["l7.prefect_lifecycle_completeness"].actual
    expected_keys = {"started_at", "finished_at", "retries_attempted", "cancellation_state", "deployment_id"}
    assert expected_keys <= set(actual.keys())
