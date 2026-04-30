"""MACE-MPA-0 calculator adapter — L2 MLIP (LAMBench rank #8).

License positions:
    MACE-MPA-0 checkpoint:  pinned by checkpoint (NOT inherited "MIT" from
                             the mace package — the checkpoint itself ships
                             under MIT in this case, but callers MUST verify
                             per checkpoint release).
    mace package:           MIT

Real backend parked behind ``L2_BACKEND=runpod_rest``.

The stub uses a different deterministic noise seed (offset 4 vs DPA-3 offset 0)
so the two adapters produce distinguishable predictions — enabling realistic
synthetic disagreement tests.
"""

from __future__ import annotations

import hashlib
import struct
from typing import Any

from zer0pa_materials.adapters.l2.base import L2MlipAdapter, L2PredictRequest
from zer0pa_materials.adapters.l2.deepmd_dpa import _synthetic_energy, _synthetic_force_rmse
from zer0pa_materials.audit.sources import BlockedSourceManifest
from zer0pa_materials.boundary import RESEARCH_BOUNDARY
from zer0pa_materials.envelope.hashing import sha256_of, structure_hash


# MACE uses seed_offset=4 so its values differ from DPA-3 (offset=0).
_MACE_SEED_OFFSET = 4


class MaceMpCalculatorAdapter(L2MlipAdapter):
    """Stub adapter for MACE-MPA-0.

    Uses a different deterministic seed offset from the DPA-3 adapter so the
    two stubs produce numerically distinguishable predictions — necessary for
    the ensemble runner to compute a non-zero synthetic disagreement.

    Attributes
    ----------
    model_id:
        ``"MACE-MPA-0"`` (pinned checkpoint label).
    backend:
        Always ``"stub"`` in this implementation.
    """

    MODEL_ID = "MACE-MPA-0"
    CHECKPOINT_LICENSE = "MIT"  # MACE-MPA-0 checkpoint; verify per release.
    PACKAGE_LICENSE = "MIT"

    def __init__(self) -> None:
        self.model_id = self.MODEL_ID
        self.backend = "stub"

    def predict(
        self,
        structure: dict[str, Any],
        request: L2PredictRequest,
    ) -> dict[str, Any]:
        """Return a single-model L2 envelope (MACE-MPA-0 only)."""
        s_hash = structure_hash(structure)
        energy = _synthetic_energy(s_hash, _MACE_SEED_OFFSET)
        force_rmse = _synthetic_force_rmse(s_hash, _MACE_SEED_OFFSET)

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
                "name": "MaceMpCalculatorAdapter",
                "version": "0.1.0",
                "backend": self.backend,
                "engine": self.MODEL_ID,
            },
            "output": output,
            "confidence": {"score": 0.5, "band": "medium", "basis": ["stub"]},
            "disagreement": {"metrics": []},
            "falsifier": {"status": "pass", "items": []},
            "audit": {
                "audit_record_id": f"audit:{request.run_id}/mace",
                "input_hash": dummy_hash,
                "output_hash": out_hash,
                "source_manifest_refs": ["src:mace:mpa0-checkpoint"],
            },
            "rights": {
                "rights_claim_id": request.rights_claim_id,
                "reuse_scope": "tenant_only",
            },
            "back_edges": [],
        }

    def blocked_manifests(self) -> list[dict[str, Any]]:
        """Return BlockedSourceManifest for MACE-MPA-0 checkpoint."""
        m = BlockedSourceManifest(
            source_manifest_id="src:mace:mpa0-checkpoint",
            attempted_locator="https://github.com/ACEsuit/mace/releases/mace-mpa-0",
            blocker_reason="unavailable_credentials",
            blocker_detail=(
                "MACE-MPA-0 checkpoint requires download and local install. "
                "Real backend parked behind L2_BACKEND=runpod_rest. "
                "Checkpoint license: MIT (verify per checkpoint release). "
                "mace package license: MIT."
            ),
            retry_strategy=(
                "Set L2_BACKEND=runpod_rest, configure RUNPOD_BASE_URL and "
                "RUNPOD_API_TOKEN, deploy mace_mp_service container."
            ),
        )
        return [m.model_dump(mode="json")]
