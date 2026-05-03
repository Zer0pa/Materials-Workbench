"""LangGraphExtractionWorkflow — property extraction via LangGraph + GPT-4.1 Mini.

Per Brief #2 Gap E: GPT-4.1 Mini at F1=0.889, ~$0.01/paper at scale.

Backend selection via MaterialsConfig.PHASE0_EXTRACTION_BACKEND:
    "local_stub" (default)  — reads from fixtures/extractions/ and returns
                              Phase0ExtractedProperty with full grounding.
    "langgraph"             — real LangGraph + OpenAI API (parked).
    "runpod_mock"           — RunPod mock (parked).
    "runpod_rest"           — RunPod real (parked).

Stub backend reads the fixture JSON files and returns them directly; the
fixture files already conform to Phase0Output schema (validated in A2).
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from zer0pa_materials_workbench.adapters.phase0.base import Phase0Adapter, _run_id
from zer0pa_materials_workbench.audit.sources import SourceManifest
from zer0pa_materials_workbench.envelope.config import MaterialsConfig
from zer0pa_materials_workbench.envelope.hashing import sha256_of

_FIXTURES_EXTRACTIONS = Path(__file__).parents[4] / "fixtures" / "extractions"

# Map of supported fixture keys to their subdirectory names.
_FIXTURE_MAP: dict[str, str] = {
    "LLZO": "LLZO",
    "Li6PS5Cl": "Li6PS5Cl",
    "Li-Mg-Zr-Cl-seed": "Li-Mg-Zr-Cl-seed",
}


class LangGraphExtractionWorkflow(Phase0Adapter):
    """Property extraction workflow (LangGraph + GPT-4.1 Mini).

    Args:
        config: MaterialsConfig instance (reads PHASE0_EXTRACTION_BACKEND).
    """

    adapter_name = "langgraph_extraction_workflow"

    def __init__(self, config: MaterialsConfig | None = None) -> None:
        super().__init__(config)
        self._last_manifest: SourceManifest | None = None

    def _execute(self, input: dict[str, Any]) -> dict[str, Any]:
        backend = getattr(self.config, "PHASE0_EXTRACTION_BACKEND", "local_stub")
        if backend == "local_stub":
            return self._query_stub(input)
        raise NotImplementedError(
            f"Backend {backend!r} is parked. Use PHASE0_EXTRACTION_BACKEND=local_stub."
        )

    def _query_stub(self, input: dict[str, Any]) -> dict[str, Any]:
        """Read a fixture extraction JSON and wrap it in a Phase 0 Envelope."""
        fixture_key = input.get("fixture", input.get("material", "LLZO"))
        doi = input.get("doi", "")
        run_id = _run_id()
        query_id = uuid.uuid4().hex[:12]

        # Load fixture or fall back to LLZO.
        subdir = _FIXTURE_MAP.get(str(fixture_key), "LLZO")
        fixture_path = _FIXTURES_EXTRACTIONS / subdir / "extraction.json"

        if fixture_path.exists():
            with open(fixture_path) as f:
                raw = json.load(f)
        else:
            # Minimal fallback so the adapter is always functional.
            raw = {
                "extracted_properties": [],
                "units_normalised": True,
                "contradictions_blocking": [],
            }

        # The fixture JSON already has research_boundary at the top but the
        # output slot must carry only the Phase0Output fields.
        output_payload: dict[str, Any] = {
            "extracted_properties": raw.get("extracted_properties", []),
            "units_normalised": raw.get("units_normalised", True),
            "contradictions_blocking": raw.get("contradictions_blocking", []),
        }

        input_payload = {
            "fixture": fixture_key,
            "doi": doi,
            "backend": "local_stub",
            "model": "gpt-4.1-mini-stub",
        }

        input_hash = sha256_of(input_payload)
        output_hash = sha256_of(output_payload)

        # Emit SourceManifest.
        self._last_manifest = self._make_source_manifest(
            source_id=f"langgraph:stub:{query_id}",
            source_type="paper",
            locator=doi or f"fixture:{subdir}",
            license_spdx="CC-BY-4.0",
            summary=(
                f"LangGraph stub extraction for {fixture_key}; "
                f"{len(output_payload['extracted_properties'])} properties extracted"
            ),
            content_hash=output_hash,
            query_params=input_payload,
        )

        return self._build_envelope(
            run_id=run_id,
            input_hash=input_hash,
            output_hash=output_hash,
            output=output_payload,
            tool_adapter_name="LangGraphExtractionWorkflow/stub",
            backend="stub",
            input_data=input_payload,
        )

    def get_last_manifest(self) -> SourceManifest | None:
        return self._last_manifest
