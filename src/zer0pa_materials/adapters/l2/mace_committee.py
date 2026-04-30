"""MACE multihead-committee runner for native MACE uncertainty.

This adapter runs multiple MACE model heads (e.g., MACE-MPA-0 multihead
ensemble) and reports the committee variance as the uncertainty estimate.

In stub mode, the committee is simulated by evaluating the structure hash
with multiple deterministic seeds and reporting the spread as the variance.

License:
    MACE committee checkpoint:  MIT (verify per checkpoint release)
    mace package:               MIT
"""

from __future__ import annotations

import hashlib
from typing import Any

from zer0pa_materials.adapters.l2.base import L2PredictRequest
from zer0pa_materials.adapters.l2.deepmd_dpa import _synthetic_energy, _synthetic_force_rmse
from zer0pa_materials.audit.sources import BlockedSourceManifest
from zer0pa_materials.boundary import RESEARCH_BOUNDARY
from zer0pa_materials.envelope.hashing import sha256_of, structure_hash


class MaceMultiheadCommitteeRunner:
    """MACE multihead committee for native uncertainty quantification.

    Runs ``n_heads`` MACE heads (stub: different seed offsets) and computes
    committee variance as the uncertainty signal. The variance is emitted in
    the ``disagreement.metrics`` block.

    Parameters
    ----------
    n_heads:
        Number of committee heads (default 4). Each head uses a different
        deterministic seed offset in stub mode.
    """

    MODEL_ID = "MACE-MPA-0-committee"
    CHECKPOINT_LICENSE = "MIT"

    def __init__(self, n_heads: int = 4) -> None:
        if n_heads < 2:
            raise ValueError("n_heads must be >= 2 for committee uncertainty.")
        self.n_heads = n_heads
        self.backend = "stub"

    def predict_with_uncertainty(
        self,
        structure: dict[str, Any],
        request: L2PredictRequest,
    ) -> dict[str, Any]:
        """Run committee heads and return envelope with committee variance.

        Returns
        -------
        dict
            Envelope dict with ``output.predictions`` containing one entry per
            head and ``disagreement.metrics`` containing the committee variance.
        """
        s_hash = structure_hash(structure)

        # Evaluate each head at a different seed offset.
        energies = [_synthetic_energy(s_hash, i * 2) for i in range(self.n_heads)]
        force_rmses = [_synthetic_force_rmse(s_hash, i * 2) for i in range(self.n_heads)]

        mean_e = sum(energies) / self.n_heads
        # Variance of energy across committee heads (meV/atom).
        variance_e = sum((e - mean_e) ** 2 for e in energies) / self.n_heads * 1000.0
        # Energy range as simple uncertainty proxy.
        energy_range = (max(energies) - min(energies)) * 1000.0  # meV/atom

        predictions = [
            {
                "model": f"{self.MODEL_ID}-head{i}",
                "energy_eV_per_atom": energies[i],
                "force_rmse_eV_per_Ang": force_rmses[i],
            }
            for i in range(self.n_heads)
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
                "name": "MaceMultiheadCommitteeRunner",
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
                        "name": "mace_committee_energy_variance",
                        "value": variance_e,
                        "unit": "meV^2/atom",
                        "references": [f"committee_n_heads={self.n_heads}"],
                    },
                    {
                        "name": "mace_committee_energy_range",
                        "value": energy_range,
                        "unit": "meV/atom",
                        "references": [f"committee_n_heads={self.n_heads}"],
                    },
                ]
            },
            "falsifier": {"status": "pass", "items": []},
            "audit": {
                "audit_record_id": f"audit:{request.run_id}/mace-committee",
                "input_hash": dummy_hash,
                "output_hash": out_hash,
                "source_manifest_refs": ["src:mace:mpa0-committee-checkpoint"],
            },
            "rights": {
                "rights_claim_id": request.rights_claim_id,
                "reuse_scope": "tenant_only",
            },
            "back_edges": [],
        }

    def blocked_manifests(self) -> list[dict[str, Any]]:
        """Return BlockedSourceManifest for MACE committee checkpoint."""
        m = BlockedSourceManifest(
            source_manifest_id="src:mace:mpa0-committee-checkpoint",
            attempted_locator="https://github.com/ACEsuit/mace/releases/mace-mpa-0-committee",
            blocker_reason="unavailable_credentials",
            blocker_detail=(
                "MACE-MPA-0 multihead committee checkpoint requires download. "
                "Checkpoint license: MIT (verify per release). "
                "mace package: MIT."
            ),
            retry_strategy=(
                "Download MACE-MPA-0 committee checkpoint and configure "
                "L2_BACKEND=runpod_rest with mace_committee_service container."
            ),
        )
        return [m.model_dump(mode="json")]
