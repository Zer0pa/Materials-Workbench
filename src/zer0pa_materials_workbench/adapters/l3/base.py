"""Base classes for L3 CALPHAD adapters (PRD §L3).

PRD §L3 decision: sovereign pycalphad/ESPEI build by default. Commercial
Thermo-Calc TDBs are allowed only as quarantined read-only inputs for
customer projects with valid license coverage.

Quarantine policy (verbatim from PRD):
    Commercial TDB data must never be committed, copied into fixtures,
    redistributed, or used as general training data.

Information-geometry framing (Brief #2 Gap C):
    Gibbs energy is the log-partition function of an exponential family;
    ESPEI's Bayesian MCMC navigates the Fisher information manifold of
    the thermodynamic state space. Concrete improvement target: natural-
    gradient MCMC on the thermodynamic manifold. Today's ESPEI adapter
    only labels this framing; the natural-gradient implementation is a
    future research contribution flagged in PRD.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "CommercialTdbQuarantineError",
    "L3CalphadAdapter",
    "L3CalphadRequest",
]


class CommercialTdbQuarantineError(RuntimeError):
    """Raised when a commercial-TDB quarantine boundary is violated.

    Quarantine policy (PRD §L3):
        Commercial TDB content (e.g., Thermo-Calc TCFE, TCNI, TCTI) must
        never be:
            * committed to the repo
            * copied into fixtures
            * redistributed
            * used as general training data

    The :class:`ThermoCalcTdbReadOnlyAdapter` enforces this at the code
    level; this exception is its raise vehicle. Catching it in test code
    is acceptable; catching it in production code that goes on to do the
    forbidden thing is a falsifier failure.
    """


@dataclass
class L3CalphadRequest:
    """Caller-supplied context for an L3 CALPHAD adapter call.

    Parameters
    ----------
    run_id:
        URN for this run, e.g. ``"run:l3/20260430/Cu-Mg"``.
    candidate_id:
        URN for the candidate, e.g. ``"candidate:Cu-Mg:abc123"``.
    campaign_id:
        URN for the campaign, e.g. ``"campaign:sse/001"``.
    rights_claim_id:
        URN for the data rights claim.
    tdb_path:
        Optional path to a TDB file (sovereign open or quarantined commercial).
    components:
        Optional list of element symbols restricting the calculation.
    extra:
        Adapter-specific pass-through (ignored by stubs).
    """

    run_id: str
    candidate_id: str
    campaign_id: str
    rights_claim_id: str
    tdb_path: str | None = None
    components: list[str] | None = None
    extra: dict[str, Any] = field(default_factory=dict)


class L3CalphadAdapter(abc.ABC):
    """Abstract base for L3 CALPHAD adapters.

    Implementors return a fully-formed Envelope dict (not a model instance)
    so callers can pass it directly to :meth:`Envelope.model_validate`.

    Each subclass MUST:

    1. Implement :meth:`run` returning a wire-level Envelope dict with
       ``layer="L3"`` and ``output`` conforming to ``L3CalphadOutput``.
    2. Implement :meth:`blocked_manifests` returning a list of
       ``BlockedSourceManifest`` dicts for every dependency the adapter
       cannot complete (real weights, license, credentials, …).
    3. NEVER copy commercial TDB content into ``output``. Quarantine adapters
       return a hash + summary metadata only.
    """

    @abc.abstractmethod
    def run(
        self,
        request: L3CalphadRequest,
    ) -> dict[str, Any]:
        """Execute the L3 calculation and return a wire-level Envelope dict.

        Returns
        -------
        dict
            Envelope dict ready for ``Envelope.model_validate``. The ``layer``
            key MUST be ``"L3"``; the ``output`` dict MUST conform to
            ``L3CalphadOutput``.
        """

    @abc.abstractmethod
    def blocked_manifests(self) -> list[dict[str, Any]]:
        """Return BlockedSourceManifest dicts for every blocked dependency.

        Adapters that cannot run real backends emit one manifest per blocked
        resource (model weights, license verification, credentials, etc).
        Adapters that have no blocked dependencies (open-path, sovereign)
        return an empty list.
        """
