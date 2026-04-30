"""MaterialsBertNerAdapter — gated NER via MaterialsBERT (Apache 2.0).

License gate: MaterialsBERT weights require user license acceptance via
HuggingFace. Until license is verified by the operator, every call returns a
``BlockedSourceManifest`` with ``blocker_reason="license_unverified"`` and
the envelope output is a minimal Phase0Output with no extracted properties.

Backend selection:
    "local_stub" (default)  — blocked by license gate until verified.
    If ``license_verified=True`` is passed in the input dict, the stub returns
    deterministic mock NER entities (for test purposes only).

Real backend parked; not network-accessible in unit tests.
"""

from __future__ import annotations

import uuid
from typing import Any

from zer0pa_materials.adapters.phase0.base import Phase0Adapter, _now_iso, _run_id
from zer0pa_materials.audit.sources import BlockedSourceManifest, SourceManifest
from zer0pa_materials.envelope.config import MaterialsConfig
from zer0pa_materials.envelope.hashing import sha256_of

# Deterministic mock NER entities for license-verified stub runs.
_MOCK_NER_ENTITIES = [
    {"entity": "Li7La3Zr2O12", "label": "MATERIAL", "confidence": 0.97},
    {"entity": "1.04e-3 S/cm", "label": "PROPERTY_VALUE", "confidence": 0.91},
    {"entity": "0.34 eV", "label": "PROPERTY_VALUE", "confidence": 0.89},
    {"entity": "ionic conductivity", "label": "PROPERTY_NAME", "confidence": 0.95},
    {"entity": "activation energy", "label": "PROPERTY_NAME", "confidence": 0.93},
]

_RETRY_STRATEGY = (
    "Visit https://huggingface.co/m3rg-iitd/matscibert and accept the model license. "
    "Set MATERIALSBERT_LICENSE_VERIFIED=true in .env and re-run."
)


class MaterialsBertNerAdapter(Phase0Adapter):
    """Gated NER adapter using MaterialsBERT.

    The adapter is blocked by default (license gate). To unblock for testing:
        input["license_verified"] = True

    Args:
        config: MaterialsConfig instance.
    """

    adapter_name = "materialsbert_ner_adapter"

    def __init__(self, config: MaterialsConfig | None = None) -> None:
        super().__init__(config)
        self._last_manifest: SourceManifest | BlockedSourceManifest | None = None

    def _execute(self, input: dict[str, Any]) -> dict[str, Any]:
        license_verified = input.get("license_verified", False)
        if not license_verified:
            return self._blocked_response(input)
        return self._query_stub(input)

    def _blocked_response(self, input: dict[str, Any]) -> dict[str, Any]:
        """Emit BlockedSourceManifest and return minimal Phase0Output."""
        run_id = _run_id()
        query_id = uuid.uuid4().hex[:12]

        input_payload = {**input, "backend": "local_stub", "model": "m3rg-iitd/matscibert"}
        output_payload = {
            "extracted_properties": [],
            "units_normalised": True,
            "contradictions_blocking": [],
            "ner_entities": [],
            "blocked_reason": "license_unverified",
        }

        input_hash = sha256_of(input_payload)
        output_hash = sha256_of(output_payload)

        # Record BlockedSourceManifest (not SourceManifest).
        self._last_manifest = self._make_blocked_manifest(
            source_id=f"materialsbert:blocked:{query_id}",
            locator="https://huggingface.co/m3rg-iitd/matscibert",
            blocker_reason="license_unverified",
            retry_strategy=_RETRY_STRATEGY,
        )

        return self._build_envelope(
            run_id=run_id,
            input_hash=input_hash,
            output_hash=output_hash,
            output=output_payload,
            tool_adapter_name="MaterialsBertNerAdapter/blocked",
            backend="stub",
            input_data=input_payload,
        )

    def _query_stub(self, input: dict[str, Any]) -> dict[str, Any]:
        """Return deterministic mock NER entities (license_verified stub path)."""
        run_id = _run_id()
        query_id = uuid.uuid4().hex[:12]
        text = input.get("text", "")

        input_payload = {
            "text_len": len(text),
            "license_verified": True,
            "backend": "local_stub",
            "model": "m3rg-iitd/matscibert",
        }
        output_payload = {
            "extracted_properties": [],
            "units_normalised": True,
            "contradictions_blocking": [],
            "ner_entities": _MOCK_NER_ENTITIES,
            "entity_count": len(_MOCK_NER_ENTITIES),
        }

        input_hash = sha256_of(input_payload)
        output_hash = sha256_of(output_payload)

        self._last_manifest = self._make_source_manifest(
            source_id=f"materialsbert:stub:{query_id}",
            source_type="model_card",
            locator="https://huggingface.co/m3rg-iitd/matscibert",
            license_spdx="Apache-2.0",
            summary="MaterialsBERT stub NER; license_verified=True path",
            content_hash=output_hash,
            query_params=input_payload,
        )

        return self._build_envelope(
            run_id=run_id,
            input_hash=input_hash,
            output_hash=output_hash,
            output=output_payload,
            tool_adapter_name="MaterialsBertNerAdapter/stub",
            backend="stub",
            input_data=input_payload,
        )

    def get_last_manifest(self) -> SourceManifest | BlockedSourceManifest | None:
        return self._last_manifest

    def is_blocked(self) -> bool:
        """True iff the most recent call was blocked by the license gate."""
        return isinstance(self._last_manifest, BlockedSourceManifest)
