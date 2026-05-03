"""Phase0Adapter — common base class for all Phase 0 adapters.

Every adapter that produces Phase 0 outputs must inherit from this class.
The contract:

    1. ``query(input)`` must return an ``Envelope[Phase0Output]`` (wire-typed
       as ``Envelope`` with ``layer="phase0"``).
    2. ``assert_boundary`` is called on the emitted dict before it is returned.
    3. A ``SourceManifest`` or ``BlockedSourceManifest`` is emitted to the
       audit log on every call.
    4. Backend selection is read from ``MaterialsConfig`` — adapters never
       read ``os.environ`` directly.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

from zer0pa_materials_workbench.audit.sources import BlockedSourceManifest, SourceManifest
from zer0pa_materials_workbench.boundary import RESEARCH_BOUNDARY, assert_boundary
from zer0pa_materials_workbench.envelope.config import MaterialsConfig
from zer0pa_materials_workbench.envelope.envelope import Envelope


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_id() -> str:
    return f"run:phase0:{uuid.uuid4().hex[:12]}"


class Phase0Adapter(ABC):
    """Abstract base for Phase 0 adapters.

    Concrete adapters override ``_query_stub`` (and optionally ``_query_real``)
    and call ``_build_envelope`` to produce the compliant Envelope.
    """

    #: Human-readable adapter name; used in SourceManifest.
    adapter_name: str = "phase0_base"

    def __init__(self, config: MaterialsConfig | None = None) -> None:
        self.config: MaterialsConfig = config or MaterialsConfig()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def query(self, input: dict[str, Any]) -> Envelope:
        """Run the adapter and return a boundary-checked Phase 0 Envelope."""
        env_dict = self._execute(input)
        assert_boundary(env_dict)
        return Envelope.model_validate(env_dict)

    # ------------------------------------------------------------------
    # Subclass contract
    # ------------------------------------------------------------------

    @abstractmethod
    def _execute(self, input: dict[str, Any]) -> dict[str, Any]:
        """Dispatch to stub or real backend; return raw envelope dict."""

    # ------------------------------------------------------------------
    # Helpers for concrete adapters
    # ------------------------------------------------------------------

    def _build_envelope(
        self,
        run_id: str,
        input_hash: str,
        output_hash: str,
        output: dict[str, Any],
        tool_adapter_name: str,
        backend: str,
        *,
        input_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Assemble the canonical envelope dict (matches Envelope schema exactly)."""
        return {
            "contract_version": "zer0pa.materials.layer-envelope.v1",
            "layer": "phase0",
            "run_id": run_id,
            "campaign_id": "campaign:phase0-stub",
            "candidate_id": "candidate:phase0-stub",
            "research_boundary": RESEARCH_BOUNDARY,
            "tool_adapter": {
                "name": tool_adapter_name,
                "version": "0.1.0-stub",
                "backend": backend,
                "engine": "stub",
            },
            "input_refs": [],
            "output": output,
            "confidence": {
                "band": "low",
                "score": 0.0,
            },
            "disagreement": {"metrics": []},
            "falsifier": {"status": "pass", "items": []},
            "audit": {
                "audit_record_id": f"audit:phase0:{uuid.uuid4().hex[:12]}",
                "input_hash": input_hash,
                "output_hash": output_hash,
                "source_manifest_refs": [],
            },
            "rights": {
                "rights_claim_id": f"rights:phase0:{uuid.uuid4().hex[:12]}",
                "reuse_scope": "tenant_only",
            },
            "back_edges": [],
        }

    @staticmethod
    def _make_source_manifest(
        source_id: str,
        source_type: str,
        locator: str,
        license_spdx: str,
        summary: str,
        content_hash: str,
        query_params: dict[str, Any] | None = None,
    ) -> SourceManifest:
        return SourceManifest(
            source_manifest_id=f"src:{source_id}",
            source_type=source_type,  # type: ignore[arg-type]
            locator=locator,
            license_spdx=license_spdx,
            summary=summary,
            decision_impact="phase0 extraction input",
            retrieval_date=_now_iso(),
            hash=content_hash,
        )

    @staticmethod
    def _make_blocked_manifest(
        source_id: str,
        locator: str,
        blocker_reason: str,
        retry_strategy: str,
    ) -> BlockedSourceManifest:
        return BlockedSourceManifest(
            source_manifest_id=f"src:{source_id}",
            attempted_locator=locator,
            blocker_reason=blocker_reason,  # type: ignore[arg-type]
            blocker_detail=f"Blocked: {blocker_reason}. See retry_strategy for next steps.",
            retry_strategy=retry_strategy,
        )
