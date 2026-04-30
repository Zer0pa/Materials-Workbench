"""SevenNet calculator adapter — third-tier optional MLIP stub.

SevenNet (7Net) is a fast screening MLIP. It is NOT part of the mandatory
DPA-3 + MACE ensemble; it is an optional third-model for rapid pre-screening.

License:
    SevenNet:  MIT

Real backend parked behind ``L2_BACKEND=runpod_rest``.
"""

from __future__ import annotations

import hashlib
from typing import Any

from zer0pa_materials.adapters.l2.base import L2MlipAdapter, L2PredictRequest
from zer0pa_materials.adapters.l2.deepmd_dpa import _synthetic_energy, _synthetic_force_rmse
from zer0pa_materials.audit.sources import BlockedSourceManifest
from zer0pa_materials.boundary import RESEARCH_BOUNDARY
from zer0pa_materials.envelope.hashing import sha256_of, structure_hash


class SevenNetCalculatorAdapter(L2MlipAdapter):
    """Stub adapter for SevenNet (7Net) fast MLIP.

    SevenNet is NOT a mandatory ensemble member — it is an optional third
    model for rapid pre-screening before the mandatory DPA-3 + MACE ensemble.

    Uses seed offset 12 to differ from DPA-3 (0), MACE (4), and UMA (8).
    """

    MODEL_ID = "SevenNet-0"
    PACKAGE_LICENSE = "MIT"

    def __init__(self) -> None:
        self.model_id = self.MODEL_ID
        self.backend = "stub"

    def predict(
        self,
        structure: dict[str, Any],
        request: L2PredictRequest,
    ) -> dict[str, Any]:
        """Return a single-model L2 envelope (SevenNet only)."""
        s_hash = structure_hash(structure)
        energy = _synthetic_energy(s_hash, 12)
        force_rmse = _synthetic_force_rmse(s_hash, 12)

        output = {
            "predictions": [
                {
                    "model": self.MODEL_ID,
                    "energy_eV_per_atom": energy,
                    "force_rmse_eV_per_Ang": force_rmse,
                }
            ],
            "energy_disagreement_meV_per_atom": 0.0,
            "force_rmse_disagreement_eV_per_Ang": 0.0,
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
                "name": "SevenNetCalculatorAdapter",
                "version": "0.1.0",
                "backend": self.backend,
                "engine": self.MODEL_ID,
            },
            "output": output,
            "confidence": {"score": 0.4, "band": "low", "basis": ["stub"]},
            "disagreement": {"metrics": []},
            "falsifier": {"status": "pass", "items": []},
            "audit": {
                "audit_record_id": f"audit:{request.run_id}/sevennet",
                "input_hash": dummy_hash,
                "output_hash": out_hash,
                "source_manifest_refs": ["src:sevennet:sevennet-0-checkpoint"],
            },
            "rights": {
                "rights_claim_id": request.rights_claim_id,
                "reuse_scope": "tenant_only",
            },
            "back_edges": [],
        }

    def blocked_manifests(self) -> list[dict[str, Any]]:
        """Return BlockedSourceManifest for SevenNet checkpoint."""
        m = BlockedSourceManifest(
            source_manifest_id="src:sevennet:sevennet-0-checkpoint",
            attempted_locator="https://github.com/MDIL-SNU/SevenNet",
            blocker_reason="unavailable_credentials",
            blocker_detail=(
                "SevenNet-0 checkpoint requires local install. "
                "Package license: MIT. "
                "SevenNet is an optional third-tier MLIP (not mandatory ensemble)."
            ),
            retry_strategy=(
                "Install SevenNet and configure L2_BACKEND=runpod_rest "
                "with sevennet_service container."
            ),
        )
        return [m.model_dump(mode="json")]
