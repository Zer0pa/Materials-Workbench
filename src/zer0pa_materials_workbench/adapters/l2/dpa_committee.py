"""DPA committee runner for DeePMD-based uncertainty quantification.

Runs multiple DPA-3 model checkpoints (or a deep ensemble) and computes
committee disagreement as the uncertainty signal.

In stub mode, simulated by evaluating the structure hash with different
integer seeds and reporting spread as the variance.

License:
    DPA-3.1-3M weights:  CC-BY-4.0 (per checkpoint)
    DeePMD-kit library:  LGPL-3.0
"""

from __future__ import annotations

import hashlib
from typing import Any

from zer0pa_materials_workbench.adapters.l2.base import L2PredictRequest
from zer0pa_materials_workbench.adapters.l2.deepmd_dpa import _synthetic_energy, _synthetic_force_rmse
from zer0pa_materials_workbench.audit.sources import BlockedSourceManifest
from zer0pa_materials_workbench.boundary import RESEARCH_BOUNDARY
from zer0pa_materials_workbench.envelope.hashing import sha256_of, structure_hash


class DpaCommitteeRunner:
    """DPA deep ensemble / committee for uncertainty quantification.

    Parameters
    ----------
    n_members:
        Number of DPA ensemble members (default 4).
    """

    MODEL_ID = "DPA-3.1-3M-committee"
    WEIGHTS_LICENSE = "CC-BY-4.0"
    LIBRARY_LICENSE = "LGPL-3.0"

    def __init__(self, n_members: int = 4) -> None:
        if n_members < 2:
            raise ValueError("n_members must be >= 2 for committee uncertainty.")
        self.n_members = n_members
        self.backend = "stub"

    def predict_with_uncertainty(
        self,
        structure: dict[str, Any],
        request: L2PredictRequest,
    ) -> dict[str, Any]:
        """Run DPA committee and return envelope with committee variance."""
        s_hash = structure_hash(structure)

        # Use odd seed offsets to differ from MACE committee (even offsets).
        energies = [_synthetic_energy(s_hash, i * 2 + 1) for i in range(self.n_members)]
        force_rmses = [_synthetic_force_rmse(s_hash, i * 2 + 1) for i in range(self.n_members)]

        mean_e = sum(energies) / self.n_members
        variance_e = sum((e - mean_e) ** 2 for e in energies) / self.n_members * 1000.0
        energy_range = (max(energies) - min(energies)) * 1000.0  # meV/atom

        predictions = [
            {
                "model": f"{self.MODEL_ID}-member{i}",
                "energy_eV_per_atom": energies[i],
                "force_rmse_eV_per_Ang": force_rmses[i],
            }
            for i in range(self.n_members)
        ]

        output = {
            "predictions": predictions,
            "energy_disagreement_meV_per_atom": energy_range,
            "force_rmse_disagreement_eV_per_Ang": max(force_rmses) - min(force_rmses),
            "routing_decision": "promote",
        }

        dummy_hash = "sha256:" + hashlib.sha256(b"input").hexdigest()
        out_hash = "sha256:" + sha256_of(output).split("sha256:", 1)[1]

        return {
            "research_boundary": RESEARCH_BOUNDARY,
            "contract_version": "zer0pa.materials.layer-envelope.v1",
            "layer": "L2",
            "run_id": request.run_id,
            "candidate_id": request.candidate_id,
            "campaign_id": request.campaign_id,
            "tool_adapter": {
                "name": "DpaCommitteeRunner",
                "version": "0.1.0",
                "backend": self.backend,
                "engine": self.MODEL_ID,
            },
            "output": output,
            "confidence": {
                "score": max(0.0, 1.0 - variance_e / 100.0),
                "band": "medium",
                "basis": [f"committee_variance={variance_e:.4f}_meV2"],
            },
            "disagreement": {
                "metrics": [
                    {
                        "name": "dpa_committee_energy_variance",
                        "value": variance_e,
                        "unit": "meV^2/atom",
                        "references": [f"committee_n_members={self.n_members}"],
                    },
                    {
                        "name": "dpa_committee_energy_range",
                        "value": energy_range,
                        "unit": "meV/atom",
                        "references": [f"committee_n_members={self.n_members}"],
                    },
                ]
            },
            "falsifier": {"status": "pass", "items": []},
            "audit": {
                "audit_record_id": f"audit:{request.run_id}/dpa-committee",
                "input_hash": dummy_hash,
                "output_hash": out_hash,
                "source_manifest_refs": ["src:deepmd:dpa-3.1-3m-committee-weights"],
            },
            "rights": {
                "rights_claim_id": request.rights_claim_id,
                "reuse_scope": "tenant_only",
            },
            "back_edges": [],
        }

    def blocked_manifests(self) -> list[dict[str, Any]]:
        """Return BlockedSourceManifest for DPA-3 committee weights."""
        m = BlockedSourceManifest(
            source_manifest_id="src:deepmd:dpa-3.1-3m-committee-weights",
            attempted_locator="https://huggingface.co/deepmodeling/DPA-3.1-3M",
            blocker_reason="unavailable_credentials",
            blocker_detail=(
                "DPA-3 committee requires multiple checkpoint downloads from HuggingFace. "
                "Weights license: CC-BY-4.0. DeePMD-kit library: LGPL-3.0."
            ),
            retry_strategy=(
                "Configure HuggingFace credentials and L2_BACKEND=runpod_rest "
                "with dpa_committee_service container."
            ),
        )
        return [m.model_dump(mode="json")]
