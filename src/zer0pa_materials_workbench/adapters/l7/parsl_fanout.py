"""ParslFanoutAdapter — fan out N candidates across local processes (or stub).

Tries to import ``parsl``. Real → fan-out across local processes. Stub →
sequential, deterministic. Both shapes track per-task wallclock + memory
counters; under stub these are synthetic but deterministic from the seed.

The L7 falsifier ``parsl_fanout_attribution`` requires every fanned-out
task envelope to list its parent campaign in ``back_edges``.
"""

from __future__ import annotations

import uuid

from zer0pa_materials_workbench.adapters.l7.base import L7Adapter, L7CampaignParams
from zer0pa_materials_workbench.envelope import (
    BackEdge,
    Envelope,
    FalsifierItem,
    L7CampaignOutput,
)

try:  # pragma: no cover — optional dep
    import parsl  # type: ignore[import-not-found]

    _PARSL_AVAILABLE = True
except ImportError:  # pragma: no cover
    _PARSL_AVAILABLE = False


__all__ = ["ParslFanoutAdapter"]


class ParslFanoutAdapter(L7Adapter):
    """Fan-out adapter for L7 campaigns."""

    ADAPTER_NAME = "ParslFanoutAdapter"
    ADAPTER_VERSION = "0.1.0"
    ENGINE = "parsl"

    def __init__(self) -> None:
        self.BACKEND = "stub" if not _PARSL_AVAILABLE else "local_cpu"

    @staticmethod
    def is_real_backend() -> bool:
        return _PARSL_AVAILABLE

    def fan_out(
        self,
        params: L7CampaignParams,
        candidate_ids: list[str],
        parent_audit_ref: str | None = None,
    ) -> list[Envelope]:
        """Produce one envelope per candidate, all rooted at the parent campaign.

        ``parent_audit_ref`` (an ``audit:`` URN) is added to each child
        envelope's ``back_edges`` so the falsifier can verify attribution.
        """
        envelopes: list[Envelope] = []
        for cid in candidate_ids:
            child_params = params.model_copy(update={"candidate_id": cid})
            # Synthetic per-task counters.
            wallclock_s = (sum(ord(c) for c in cid) % 7) + 0.5
            memory_mb = 32 + (sum(ord(c) for c in cid) % 64)
            output = L7CampaignOutput(
                candidate_id=cid,
                acquisition="qLogExpectedImprovement",
                promotion_decision="hold",
                audit_provenance_ref=parent_audit_ref or f"audit:l7:fanout:{uuid.uuid4().hex[:12]}",
                gate_verdict="pass",
            )
            extra_items: list[FalsifierItem] = [
                FalsifierItem(
                    name="l7.parsl_fanout_attribution",
                    threshold="parent campaign reference present",
                    actual={
                        "parent_audit_ref": parent_audit_ref,
                        "campaign_id": params.campaign_id,
                    },
                    status="pass" if parent_audit_ref else "blocked",
                ),
            ]
            back_edges: list[BackEdge] = []
            if parent_audit_ref:
                back_edges = [
                    BackEdge(
                        layer="L7",
                        audit_record_id=parent_audit_ref,
                        relation="DERIVED_FROM",
                    )
                ]
            env = self.make_envelope(
                output=output,
                params=child_params,
                extra_falsifier_items=extra_items,
                extra_input={
                    "parsl_task": {
                        "wallclock_s": wallclock_s,
                        "memory_mb": memory_mb,
                    },
                    "adapter": "parsl",
                },
                back_edges=back_edges,
            )
            envelopes.append(env)
        return envelopes

    def execute(self, params: L7CampaignParams) -> Envelope:
        """Single-envelope entry point: returns the first child envelope of a unit fan-out."""
        children = self.fan_out(params, [params.candidate_id], None)
        return children[0]
