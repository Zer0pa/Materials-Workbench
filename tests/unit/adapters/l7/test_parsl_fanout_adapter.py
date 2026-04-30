"""Test the ParslFanoutAdapter."""

from __future__ import annotations

import pytest

from zer0pa_materials.adapters.l7 import ParslFanoutAdapter
from zer0pa_materials.adapters.l7.base import L7CampaignParams


def _params() -> L7CampaignParams:
    return L7CampaignParams(
        campaign_id="campaign:test/c1",
        candidate_id="candidate:test/c1",
    )


def test_fan_out_emits_one_envelope_per_candidate():
    adapter = ParslFanoutAdapter()
    cids = ["candidate:test/c1", "candidate:test/c2", "candidate:test/c3"]
    envs = adapter.fan_out(_params(), cids, parent_audit_ref="audit:l7:test:parent")
    assert len(envs) == 3
    assert {e.candidate_id for e in envs} == set(cids)


def test_back_edges_link_to_parent():
    adapter = ParslFanoutAdapter()
    envs = adapter.fan_out(_params(), ["candidate:test/c1"], parent_audit_ref="audit:l7:parent")
    env = envs[0]
    assert any(
        be.relation == "DERIVED_FROM" and be.audit_record_id == "audit:l7:parent"
        for be in env.back_edges
    )


def test_unit_execute_returns_single_envelope():
    env = ParslFanoutAdapter().execute(_params())
    assert env.layer == "L7"
