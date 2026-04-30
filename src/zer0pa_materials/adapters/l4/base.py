"""Base class for all L4 phase-field / kMC / neural-operator adapters.

Every concrete adapter implements ``run(spec, request) -> dict`` returning a
fully-formed envelope dict that:
    1. Validates against ``Envelope.model_validate``.
    2. Has ``layer == "L4"``.
    3. Has ``output`` conforming to ``L4PhaseFieldOutput`` (the existing
       schema in :mod:`envelope.layer_outputs`).
    4. Carries the canonical ``MesoscaleRunResult`` payload under
       ``output._mesoscale_result`` for the downstream user.

License posture (PRD §L4):
    PRISMS-PF       LGPL — link/use OK; modifications fall under LGPL.
    MOOSE/MARMOT    LGPL — same.
    MICROSIM        GPL-3 — SUBPROCESS QUARANTINE; never co-imported.
    SPPARKS         GPL — outputs commercialisable; tool itself is copyleft.
    Neural operator MIT — Zer0pa-built; outputs fully owned.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any


@dataclass
class L4PredictRequest:
    """Caller-supplied context for an L4 run.

    Parameters
    ----------
    run_id:
        URN for this specific compute job, e.g. ``"run:l4/20260430/llzo"``.
    candidate_id:
        URN for the scientific candidate, e.g. ``"candidate:LLZO:cubic"``.
    campaign_id:
        URN for the parent campaign, e.g. ``"campaign:sse/001"``.
    rights_claim_id:
        URN for the data-rights claim.
    extra:
        Adapter-specific pass-through (ignored by stubs).
    """

    run_id: str
    candidate_id: str
    campaign_id: str
    rights_claim_id: str
    extra: dict[str, Any] = field(default_factory=dict)


class L4Adapter(abc.ABC):
    """Abstract base for L4 adapters (phase field + kMC + neural operator).

    Every adapter MUST implement:
        - ``run(spec, request) -> dict`` : envelope dict
        - ``blocked_manifests() -> list[dict]`` : BlockedSourceManifest entries

    Adapters MAY override:
        - ``description`` : short text for CLI/UI displays
    """

    name: str = "L4Adapter"
    version: str = "0.1.0"
    backend: str = "stub"
    engine: str = "stub"
    description: str = "Abstract L4 adapter."
    advisory: bool = False  # default; neural operator overrides to True until gates pass

    @abc.abstractmethod
    def run(
        self,
        spec: Any,  # PhaseFieldRunSpec | KmcRunSpec; typed as Any to keep base simple
        request: L4PredictRequest,
    ) -> dict[str, Any]:
        """Execute the L4 run and return a wire-level Envelope dict.

        Parameters
        ----------
        spec:
            Run spec. Phase-field adapters consume ``PhaseFieldRunSpec``;
            kMC adapters consume ``KmcRunSpec``.
        request:
            Caller-supplied run context (run_id, campaign_id, ...).

        Returns
        -------
        dict
            Envelope dict ready for ``Envelope.model_validate``. The
            ``layer`` key MUST be ``"L4"``; the ``output`` dict MUST
            conform to ``L4PhaseFieldOutput``.
        """

    @abc.abstractmethod
    def blocked_manifests(self) -> list[dict[str, Any]]:
        """Return BlockedSourceManifest dicts for every blocked dependency."""
