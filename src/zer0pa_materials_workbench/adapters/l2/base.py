"""Base class for all L2 MLIP adapters.

All adapters implement ``predict(structure, request) -> Envelope[L2MlipOutput]``.
The concrete return type is ``Envelope`` with ``layer="L2"`` and the ``output``
dict conforming to ``L2MlipOutput``.

License positions (PRD §L2 license correction — do NOT propagate inherited labels):
    DPA-3.1-3M weights    CC-BY-4.0
    DeePMD-kit library    LGPL-3.0
    MACE checkpoints      pinned per checkpoint (not inherited MIT)
    UMA library           MIT (corrected 2026-04-30; was Apache-2.0 per Brief #2; live LICENSE verified MIT)
    UMA weights           FAIR Chemistry License v1 (custom, restricted geo)
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any


@dataclass
class L2PredictRequest:
    """Caller-supplied context for an L2 predict call.

    Parameters
    ----------
    run_id:
        URN for this run, e.g. ``"run:l2/20260430/Si"``.
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


class L2MlipAdapter(abc.ABC):
    """Abstract base for single-model L2 MLIP adapters.

    Implementors return a fully-formed ``Envelope`` dict (not a model instance)
    so callers can pass it directly to ``Envelope.model_validate``.
    """

    @abc.abstractmethod
    def predict(
        self,
        structure: dict[str, Any],
        request: L2PredictRequest,
    ) -> dict[str, Any]:
        """Run the MLIP on ``structure`` and return a wire-level Envelope dict.

        Parameters
        ----------
        structure:
            Crystal structure dict with keys ``lattice_vectors`` (3x3), ``species``
            (list[str]), ``fractional_coords`` (list[list[float]]) — OPTIMADE-style
            keys, same shape as ``structure_hash`` input.
        request:
            Caller-supplied run context.

        Returns
        -------
        dict
            Envelope dict ready for ``Envelope.model_validate``.  The ``layer``
            key MUST be ``"L2"``; the ``output`` dict MUST conform to
            ``L2MlipOutput``.
        """

    @abc.abstractmethod
    def blocked_manifests(self) -> list[dict[str, Any]]:
        """Return BlockedSourceManifest dicts for every real-weight dependency.

        Adapters that cannot run real weights emit one manifest per blocked
        resource (model weights, license, credentials, …). Stubs emit a single
        manifest for the weights they are stubbing.
        """
