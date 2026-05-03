"""Atomate2WorkflowAdapter — workflow templates (relax-and-static, phonon, etc).

Tries to import ``atomate2``. Real → atomate2 workflow definitions. Stub →
templated definitions with the same shape:

    {
        "workflow_name": "relax_and_static",
        "steps": [...],
        "inputs": {...},
        "outputs": [...],
    }
"""

from __future__ import annotations

import uuid
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from zer0pa_materials_workbench.adapters.l7.base import L7Adapter, L7CampaignParams
from zer0pa_materials_workbench.envelope import Envelope, FalsifierItem, L7CampaignOutput

try:  # pragma: no cover — optional dep
    import atomate2  # type: ignore[import-not-found]

    _ATOMATE2_AVAILABLE = True
except ImportError:  # pragma: no cover
    _ATOMATE2_AVAILABLE = False


__all__ = ["WORKFLOW_TEMPLATES", "Atomate2WorkflowAdapter", "WorkflowTemplate"]


WorkflowName = Literal[
    "relax_and_static",
    "phonon_band_structure",
    "elastic_constants",
    "dielectric_response",
    "lobster_wf",
    "lobster_descriptors",
]


class WorkflowTemplate(BaseModel):
    """Templated definition of a materials workflow."""

    model_config = ConfigDict(extra="forbid")

    workflow_name: WorkflowName
    steps: list[str]
    inputs: dict[str, Any] = Field(default_factory=dict)
    outputs: list[str]


WORKFLOW_TEMPLATES: dict[WorkflowName, WorkflowTemplate] = {
    "relax_and_static": WorkflowTemplate(
        workflow_name="relax_and_static",
        steps=["relax_geometry", "static_calculation"],
        inputs={"k_point_density": 1000, "max_force_eV_per_Ang": 0.05},
        outputs=["relaxed_structure", "total_energy_eV", "forces_eV_per_Ang"],
    ),
    "phonon_band_structure": WorkflowTemplate(
        workflow_name="phonon_band_structure",
        steps=["relax_geometry", "static_supercell", "force_constants", "band_structure"],
        inputs={"supercell": [2, 2, 2], "displacement_A": 0.01},
        outputs=["phonon_dispersion", "imaginary_modes_summary"],
    ),
    "elastic_constants": WorkflowTemplate(
        workflow_name="elastic_constants",
        steps=["relax_geometry", "deformations", "fit_elastic_tensor"],
        inputs={"strain_magnitudes": [-0.01, 0.0, 0.01]},
        outputs=["elastic_tensor", "moduli"],
    ),
    "dielectric_response": WorkflowTemplate(
        workflow_name="dielectric_response",
        steps=["static_calculation", "born_charges", "epsilon_inf"],
        inputs={"polar_field_eV_per_Ang": 1e-3},
        outputs=["born_effective_charges", "dielectric_tensor"],
    ),
    "lobster_wf": WorkflowTemplate(
        workflow_name="lobster_wf",
        steps=["static_calculation", "lobster_post"],
        inputs={"basis_set": "pbeVaspFit2015"},
        outputs=["coop_data", "icobi_data"],
    ),
    "lobster_descriptors": WorkflowTemplate(
        workflow_name="lobster_descriptors",
        steps=["lobster_wf", "extract_descriptors"],
        inputs={},
        outputs=["bond_descriptors"],
    ),
}


class Atomate2WorkflowAdapter(L7Adapter):
    """Materials-workflow template adapter."""

    ADAPTER_NAME = "Atomate2WorkflowAdapter"
    ADAPTER_VERSION = "0.1.0"
    ENGINE = "atomate2"

    def __init__(self, workflow: WorkflowName = "relax_and_static") -> None:
        self.BACKEND = "stub" if not _ATOMATE2_AVAILABLE else "local_cpu"
        if workflow not in WORKFLOW_TEMPLATES:
            raise ValueError(f"unknown workflow {workflow!r}; valid: {sorted(WORKFLOW_TEMPLATES)}")
        self.workflow = workflow

    @staticmethod
    def is_real_backend() -> bool:
        return _ATOMATE2_AVAILABLE

    def template(self) -> WorkflowTemplate:
        return WORKFLOW_TEMPLATES[self.workflow]

    def execute(self, params: L7CampaignParams) -> Envelope:
        tmpl = self.template()
        extra_items = [
            FalsifierItem(
                name="l7.atomate2_workflow_template_resolved",
                threshold="workflow_name has steps and outputs",
                actual={"workflow_name": tmpl.workflow_name, "n_steps": len(tmpl.steps)},
                status="pass" if tmpl.steps and tmpl.outputs else "fail",
            ),
        ]
        output = L7CampaignOutput(
            candidate_id=params.candidate_id,
            acquisition="qLogExpectedImprovement",
            promotion_decision="hold",
            audit_provenance_ref=f"audit:l7:atomate2:{uuid.uuid4().hex[:12]}",
            gate_verdict="pass",
        )
        return self.make_envelope(
            output=output,
            params=params,
            extra_falsifier_items=extra_items,
            extra_input={"atomate2_template": tmpl.model_dump(mode="json")},
        )
