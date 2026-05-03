"""L6GeneratorAdapter — common base class for all L6 generative adapters.

Every L6 adapter must:
    1. Inherit from this class.
    2. Implement ``generate(constraints) -> list[Envelope]``.
    3. Call ``assert_boundary`` on every emitted Envelope dict.
    4. Set ``novelty_status="pending"`` — NEVER "novel" until L1+ionic+L2
       falsifiers all pass.
    5. Emit a BlockedSourceManifest with blocker_reason="license_unverified"
       for real (non-stub) backends that require license acceptance.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

from zer0pa_materials_workbench.audit.sources import BlockedSourceManifest
from zer0pa_materials_workbench.boundary import RESEARCH_BOUNDARY, assert_boundary
from zer0pa_materials_workbench.envelope.config import MaterialsConfig
from zer0pa_materials_workbench.envelope.envelope import Envelope


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _candidate_id() -> str:
    return f"candidate:l6:{uuid.uuid4().hex[:12]}"


def _run_id() -> str:
    return f"run:l6:{uuid.uuid4().hex[:12]}"


class L6GeneratorAdapter(ABC):
    """Abstract base for L6 generative adapters.

    Concrete adapters implement ``generate(constraints) -> list[Envelope]``.
    """

    #: Human-readable adapter name.
    adapter_name: str = "l6_base"

    def __init__(self, config: MaterialsConfig | None = None) -> None:
        self.config: MaterialsConfig = config or MaterialsConfig()
        self._blocked_manifests: list[BlockedSourceManifest] = []

    def generate(self, constraints: dict[str, Any]) -> list[Envelope]:
        """Generate candidate structures and return boundary-checked Envelopes."""
        raw_envelopes = self._generate(constraints)
        result = []
        for env_dict in raw_envelopes:
            assert_boundary(env_dict)
            result.append(Envelope.model_validate(env_dict))
        return result

    @abstractmethod
    def _generate(self, constraints: dict[str, Any]) -> list[dict[str, Any]]:
        """Return list of raw envelope dicts."""

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_l6_envelope(
        self,
        candidate_id: str,
        run_id: str,
        input_hash: str,
        output_hash: str,
        output: dict[str, Any],
        tool_adapter_name: str,
        backend: str,
        input_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Assemble the canonical L6 envelope dict (matches Envelope schema exactly)."""
        return {
            "contract_version": "zer0pa.materials.layer-envelope.v1",
            "layer": "L6",
            "run_id": run_id,
            "campaign_id": "campaign:l6-stub",
            "candidate_id": candidate_id,
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
                "audit_record_id": f"audit:l6:{uuid.uuid4().hex[:12]}",
                "input_hash": input_hash,
                "output_hash": output_hash,
                "source_manifest_refs": [],
            },
            "rights": {
                "rights_claim_id": f"rights:l6:{uuid.uuid4().hex[:12]}",
                "reuse_scope": "tenant_only",
            },
            "back_edges": [],
        }

    def _emit_blocked_manifest(
        self,
        source_id: str,
        locator: str,
        blocker_reason: str,
        retry_strategy: str,
    ) -> BlockedSourceManifest:
        m = BlockedSourceManifest(
            source_manifest_id=f"src:{source_id}",
            attempted_locator=locator,
            blocker_reason=blocker_reason,  # type: ignore[arg-type]
            blocker_detail=f"Blocked: {blocker_reason}. See retry_strategy for next steps.",
            retry_strategy=retry_strategy,
        )
        self._blocked_manifests.append(m)
        return m

    def get_blocked_manifests(self) -> list[BlockedSourceManifest]:
        return list(self._blocked_manifests)
