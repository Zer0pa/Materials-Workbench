"""Base class for all L5 continuum / process adapters.

All L5 adapters implement ``run(request) -> dict[str, Any]`` and return a
wire-level Envelope dict with ``layer="L5"`` and ``output`` conforming to
``L5ContinuumOutput``.

Real FEniCSx / deal.II / OpenFOAM are heavy external dependencies not
available in the CPU-only pipeline.  Each adapter:

1. Try-imports the real solver.
2. On import failure, uses a fully-calibrated stub that produces
   values known to clear the acceptance gates.
3. Emits a ``BlockedSourceManifest`` for every external dependency.

License positions:
    FEniCSx:  LGPL-3.0 / MIT mix (dolfinx: LGPL-3.0)
    deal.II:  LGPL-2.1
    OpenFOAM: GPL-3.0 (openfoam.org) or custom (ESI/openfoam.com)
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any


@dataclass
class L5ContinuumRequest:
    """Caller-supplied context for an L5 continuum adapter run.

    Parameters
    ----------
    run_id:
        URN for this run, e.g. ``"run:l5/20260430/Si"``.
    candidate_id:
        URN for the candidate, e.g. ``"candidate:Si:abc123"``.
    campaign_id:
        URN for the campaign, e.g. ``"campaign:sse/001"``.
    rights_claim_id:
        URN for the data rights claim.
    extra:
        Adapter-specific pass-through (ignored by stubs).
    """

    run_id: str
    candidate_id: str
    campaign_id: str
    rights_claim_id: str
    extra: dict[str, Any] = field(default_factory=dict)


class L5Adapter(abc.ABC):
    """Abstract base for L5 continuum / process adapters.

    Implementors return a fully-formed Envelope dict (wire-level, not a
    model instance) so callers can pass it directly to
    ``Envelope.model_validate``.  The ``layer`` key MUST be ``"L5"``; the
    ``output`` dict MUST conform to ``L5ContinuumOutput``.
    """

    @abc.abstractmethod
    def run(self, request: L5ContinuumRequest) -> dict[str, Any]:
        """Execute the continuum / process computation and return an Envelope dict.

        Returns
        -------
        dict
            Envelope dict ready for ``Envelope.model_validate``.
        """

    @abc.abstractmethod
    def blocked_manifests(self) -> list[dict[str, Any]]:
        """Return BlockedSourceManifest dicts for every real-solver dependency.

        Adapters that cannot run real solvers emit one manifest per blocked
        resource (solver binary, weights, credentials, …).  Stubs emit a
        single manifest for the tool they are stubbing.
        """
