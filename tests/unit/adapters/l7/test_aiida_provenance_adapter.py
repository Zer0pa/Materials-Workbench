"""Test the AiiDAProvenanceAdapter."""

from __future__ import annotations

from zer0pa_materials_workbench.adapters.l7 import AiiDAProvenanceAdapter
from zer0pa_materials_workbench.adapters.l7.base import L7CampaignParams


def _params() -> L7CampaignParams:
    return L7CampaignParams(
        campaign_id="campaign:test/c1", candidate_id="candidate:test/c1"
    )


def test_build_provenance_has_root_and_leaves():
    adapter = AiiDAProvenanceAdapter()
    g = adapter.build_provenance(candidate_id="candidate:test/c1")
    assert g.root_source.startswith("hypothesis:") or g.root_source.startswith("optimade:")
    assert len(g.leaf_outputs) >= 1


def test_every_leaf_has_derived_from_to_root():
    adapter = AiiDAProvenanceAdapter()
    g = adapter.build_provenance(candidate_id="candidate:test/c1")
    for leaf in g.leaf_outputs:
        assert any(
            t.src == leaf and t.edge == "WAS_DERIVED_FROM"
            for t in g.triples
        )


def test_envelope_has_provenance_falsifier_pass():
    env = AiiDAProvenanceAdapter().execute(_params())
    items_by_name = {fi.name: fi for fi in env.falsifier.items}
    assert "l7.aiida_atomate2_provenance_complete" in items_by_name
    assert items_by_name["l7.aiida_atomate2_provenance_complete"].status == "pass"
