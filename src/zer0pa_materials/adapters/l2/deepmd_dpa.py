"""DeePMD DPA-3.1-3M calculator adapter — L2 MLIP (LAMBench rank #1).

License positions (PRD mandate — do NOT use inherited "MIT"):
    DPA-3.1-3M weights:  CC-BY-4.0
    DeePMD-kit library:  LGPL-3.0

Real backend parked behind ``L2_BACKEND=runpod_rest``.  Until then, the
adapter returns deterministic synthetic energies/forces derived from the
structure's ``structure_hash`` so tests are reproducible without any model
weights.

BlockedSourceManifest is always emitted for the real weights dependency:
    src:deepmd:dpa-3.1-3m-weights  — CC-BY-4.0 weights file on HF
"""

from __future__ import annotations

import hashlib
import struct
from typing import Any

from zer0pa_materials.adapters.l2.base import L2MlipAdapter, L2PredictRequest
from zer0pa_materials.audit.sources import BlockedSourceManifest
from zer0pa_materials.boundary import RESEARCH_BOUNDARY
from zer0pa_materials.envelope.hashing import sha256_of, structure_hash


# ---- Synthetic determinism seed for DPA-3 stub --------------------------------
# We use a different byte-offset than MACE so the two adapters produce
# distinguishable values — enabling realistic synthetic disagreement in tests.
_DPA_SEED_OFFSET = 0
_MACE_SEED_OFFSET = 4  # kept here for documentation only; applied in mace_mp.py


def _synthetic_energy(h: str, seed_offset: int = _DPA_SEED_OFFSET) -> float:
    """Return a deterministic synthetic energy from a sha256 hash string.

    Interprets the first 8 bytes (after ``seed_offset``) of the hash's hex
    digest as a big-endian double, scaled to a chemically plausible range of
    −8 to −2 eV/atom.
    """
    hex_body = h.split(":", 1)[1]  # strip "sha256:"
    raw = bytes.fromhex(hex_body[seed_offset * 2 : seed_offset * 2 + 16])
    uint64_val = struct.unpack(">Q", raw)[0]
    # Map [0, 2^64) to [-8, -2] eV/atom.
    return -8.0 + (uint64_val / (2**64)) * 6.0


def _synthetic_force_rmse(h: str, seed_offset: int = _DPA_SEED_OFFSET) -> float:
    """Return a deterministic synthetic force RMSE in eV/Å (0.01–0.12 range)."""
    hex_body = h.split(":", 1)[1]
    raw = bytes.fromhex(hex_body[(seed_offset + 8) * 2 : (seed_offset + 16) * 2])
    uint64_val = struct.unpack(">Q", raw)[0]
    return 0.01 + (uint64_val / (2**64)) * 0.11


class DeepmdDpaCalculatorAdapter(L2MlipAdapter):
    """Stub adapter for DPA-3.1-3M (DeePMD-kit).

    In stub mode (``L2_BACKEND != "runpod_rest"``) the adapter returns
    deterministic synthetic energies/forces from the structure hash.  The
    real runpod_rest backend is implemented in the REST service layer.

    Attributes
    ----------
    model_id:
        The DPA model version string, e.g. ``"DPA-3.1-3M"``.
    backend:
        Always ``"stub"`` in this implementation.
    """

    MODEL_ID = "DPA-3.1-3M"
    WEIGHTS_LICENSE = "CC-BY-4.0"
    LIBRARY_LICENSE = "LGPL-3.0"

    def __init__(self) -> None:
        self.model_id = self.MODEL_ID
        self.backend = "stub"

    # ------------------------------------------------------------------ predict

    def predict(
        self,
        structure: dict[str, Any],
        request: L2PredictRequest,
    ) -> dict[str, Any]:
        """Return a single-model L2 envelope (DPA-3 only).

        The returned envelope's ``output.predictions`` has exactly one entry
        so callers (``L2EnsembleRunner``) can merge multiple single-model
        envelopes into one ensemble envelope.
        """
        s_hash = structure_hash(structure)
        energy = _synthetic_energy(s_hash, _DPA_SEED_OFFSET)
        force_rmse = _synthetic_force_rmse(s_hash, _DPA_SEED_OFFSET)

        output = {
            "predictions": [
                {
                    "model": self.MODEL_ID,
                    "energy_eV_per_atom": energy,
                    "force_rmse_eV_per_Ang": force_rmse,
                }
            ],
            # Single-model envelope: disagreement = 0 (ensemble runner fills these).
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
                "name": "DeepmdDpaCalculatorAdapter",
                "version": "0.1.0",
                "backend": self.backend,
                "engine": self.MODEL_ID,
            },
            "output": output,
            "confidence": {"score": 0.5, "band": "medium", "basis": ["stub"]},
            "disagreement": {"metrics": []},
            "falsifier": {"status": "pass", "items": []},
            "audit": {
                "audit_record_id": f"audit:{request.run_id}/dpa",
                "input_hash": dummy_hash,
                "output_hash": out_hash,
                "source_manifest_refs": ["src:deepmd:dpa-3.1-3m-weights"],
            },
            "rights": {
                "rights_claim_id": request.rights_claim_id,
                "reuse_scope": "tenant_only",
            },
            "back_edges": [],
        }

    # -------------------------------------------------------- blocked_manifests

    def blocked_manifests(self) -> list[dict[str, Any]]:
        """Return BlockedSourceManifest for DPA-3.1-3M weights."""
        m = BlockedSourceManifest(
            source_manifest_id="src:deepmd:dpa-3.1-3m-weights",
            attempted_locator="https://huggingface.co/deepmodeling/DPA-3.1-3M",
            blocker_reason="unavailable_credentials",
            blocker_detail=(
                "DPA-3.1-3M weights require HuggingFace account access. "
                "Real backend parked behind L2_BACKEND=runpod_rest. "
                "Weights license: CC-BY-4.0. Library (DeePMD-kit): LGPL-3.0."
            ),
            retry_strategy=(
                "Set L2_BACKEND=runpod_rest, configure RUNPOD_BASE_URL and "
                "RUNPOD_API_TOKEN, then deploy deepmd_dpa_service container."
            ),
        )
        return [m.model_dump(mode="json")]
