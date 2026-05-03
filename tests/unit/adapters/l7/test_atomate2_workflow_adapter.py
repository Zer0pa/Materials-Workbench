"""Test the Atomate2WorkflowAdapter."""

from __future__ import annotations

import pytest

from zer0pa_materials_workbench.adapters.l7 import Atomate2WorkflowAdapter
from zer0pa_materials_workbench.adapters.l7.atomate2_workflow import WORKFLOW_TEMPLATES
from zer0pa_materials_workbench.adapters.l7.base import L7CampaignParams


def _params() -> L7CampaignParams:
    return L7CampaignParams(campaign_id="campaign:test/c1", candidate_id="candidate:test/c1")


def test_relax_and_static_template():
    adapter = Atomate2WorkflowAdapter(workflow="relax_and_static")
    tmpl = adapter.template()
    assert "relax_geometry" in tmpl.steps
    assert "total_energy_eV" in tmpl.outputs


def test_phonon_template():
    adapter = Atomate2WorkflowAdapter(workflow="phonon_band_structure")
    tmpl = adapter.template()
    assert any("phonon" in s for s in tmpl.steps + tmpl.outputs)


def test_unknown_workflow_raises():
    with pytest.raises(ValueError, match="unknown workflow"):
        Atomate2WorkflowAdapter(workflow="not_a_workflow")  # type: ignore[arg-type]


def test_envelope_falsifier_pass():
    env = Atomate2WorkflowAdapter().execute(_params())
    items = {fi.name: fi for fi in env.falsifier.items}
    assert items["l7.atomate2_workflow_template_resolved"].status == "pass"


def test_all_templates_have_steps_and_outputs():
    for name, tmpl in WORKFLOW_TEMPLATES.items():
        assert tmpl.steps, f"{name} missing steps"
        assert tmpl.outputs, f"{name} missing outputs"
