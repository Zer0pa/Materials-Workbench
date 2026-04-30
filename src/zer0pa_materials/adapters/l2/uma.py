"""Meta UMA calculator adapter — L2 MLIP (FAIR Chemistry License v1).

License position (PRD §L2 license correction and Section B Issue 1):
    fairchem library:   Apache-2.0
    UMA weights:        FAIR Chemistry License v1 (custom)
        - Geographic:   Available globally except comprehensively sanctioned
                        jurisdictions, China, Russia, and Belarus.
                        South Africa is UNRESTRICTED.
        - AUP:          Military/warfare, ITAR-controlled, weapons excluded.
                        Energy/battery discovery: NOT restricted.
        - Ownership:    "as between you and Meta, you are and will be the owner
                        of such derivative works and modifications."

DEFAULT STATE: BLOCKED.
The adapter MUST NOT be used until the lead agent has:
    1. Registered the Zer0pa HuggingFace organisation with accurate info.
    2. Accepted the FAIR Chemistry License v1 AUP explicitly.
    3. Called ``enable_uma(hf_org, hf_token, aup_accepted_at)`` on this instance.

Calling ``predict`` before enabling raises ``LicenseGateError``.
``blocked_manifests()`` always returns a BlockedSourceManifest regardless of
enabled state (the weights remain a real-weight dependency).
"""

from __future__ import annotations

import datetime as _dt
import hashlib
from typing import Any

from zer0pa_materials.adapters.l2.base import L2MlipAdapter, L2PredictRequest
from zer0pa_materials.audit.sources import BlockedSourceManifest
from zer0pa_materials.boundary import RESEARCH_BOUNDARY
from zer0pa_materials.envelope.hashing import sha256_of, structure_hash


class LicenseGateError(RuntimeError):
    """Raised when UMA adapter is called without verifying the FAIR Chemistry License."""

    def __init__(self, reason: str = "") -> None:
        msg = (
            "UMA adapter is BLOCKED pending FAIR Chemistry License v1 verification. "
            "Call enable_uma(hf_org, hf_token, aup_accepted_at) before predict. "
            + (reason or "")
        )
        super().__init__(msg)


class UmaCalculatorAdapter(L2MlipAdapter):
    """Meta UMA adapter — default BLOCKED, must be explicitly enabled.

    The adapter enforces the license gate: ``predict`` raises ``LicenseGateError``
    unless ``enable_uma`` has been called with valid arguments.

    Design invariant (RESISTANCE.md §UMA gate):
        The gate is a code-level check, not a config flag. A missing
        environment variable alone cannot unblock the adapter; the operator
        must explicitly call ``enable_uma`` with positional auditable
        arguments. This prevents accidental enablement via config drift.

    Attributes
    ----------
    MODEL_ID:
        ``"UMA-s"`` — the UMA model variant this adapter targets.
    _enabled:
        Internal flag; ``False`` on construction.
    _hf_org:
        HuggingFace organisation ID confirmed at registration.
    _hf_token:
        HF token used at enable time (not logged verbatim).
    _aup_accepted_at:
        ISO-8601 timestamp of AUP acceptance.
    """

    MODEL_ID = "UMA-s"
    LIBRARY_LICENSE = "Apache-2.0"
    WEIGHTS_LICENSE = "FAIR Chemistry License v1"

    def __init__(self) -> None:
        self._enabled: bool = False
        self._hf_org: str | None = None
        self._hf_token_hint: str | None = None  # only last-4 stored
        self._aup_accepted_at: str | None = None

    # --------------------------------------------------------------- gate

    @property
    def is_enabled(self) -> bool:
        """True iff ``enable_uma`` was called with valid arguments."""
        return self._enabled

    def enable_uma(
        self,
        hf_org: str,
        hf_token: str,
        aup_accepted_at: str | _dt.datetime,
    ) -> None:
        """Unblock the UMA adapter after license verification.

        Parameters
        ----------
        hf_org:
            HuggingFace organisation name (must be non-empty).
        hf_token:
            HuggingFace access token (must start with ``"hf_"``).
        aup_accepted_at:
            ISO-8601 timestamp when the AUP was accepted, e.g.
            ``"2026-04-30T12:00:00+00:00"``.  A ``datetime`` is also accepted.

        Raises
        ------
        ValueError
            If any argument fails validation.
        """
        if not hf_org or not hf_org.strip():
            raise ValueError("hf_org must be a non-empty HuggingFace org name.")
        if not hf_token or not hf_token.startswith("hf_"):
            raise ValueError("hf_token must be a valid HuggingFace token (starts with 'hf_').")
        if isinstance(aup_accepted_at, _dt.datetime):
            if aup_accepted_at.tzinfo is None:
                raise ValueError("aup_accepted_at datetime must be tz-aware.")
            aup_str = aup_accepted_at.isoformat(timespec="microseconds")
        else:
            try:
                parsed = _dt.datetime.fromisoformat(aup_accepted_at)
            except ValueError as exc:
                raise ValueError(f"aup_accepted_at must be ISO-8601: {exc}") from exc
            if parsed.tzinfo is None:
                raise ValueError("aup_accepted_at must include timezone offset.")
            aup_str = aup_accepted_at

        self._enabled = True
        self._hf_org = hf_org
        self._hf_token_hint = f"hf_...{hf_token[-4:]}"
        self._aup_accepted_at = aup_str

    # --------------------------------------------------------------- predict

    def predict(
        self,
        structure: dict[str, Any],
        request: L2PredictRequest,
    ) -> dict[str, Any]:
        """Run UMA prediction (stub).

        Raises
        ------
        LicenseGateError
            If the adapter has not been enabled via ``enable_uma``.
        """
        if not self._enabled:
            raise LicenseGateError()

        # Stub: deterministic from structure hash with UMA-specific seed offset.
        s_hash = structure_hash(structure)
        # Use offset 8 for UMA — different from DPA (0) and MACE (4).
        from zer0pa_materials.adapters.l2.deepmd_dpa import _synthetic_energy, _synthetic_force_rmse
        energy = _synthetic_energy(s_hash, 8)
        force_rmse = _synthetic_force_rmse(s_hash, 8)

        output = {
            "predictions": [
                {
                    "model": self.MODEL_ID,
                    "energy_eV_per_atom": energy,
                    "force_rmse_eV_per_Ang": force_rmse,
                }
            ],
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
                "name": "UmaCalculatorAdapter",
                "version": "0.1.0",
                "backend": "stub",
                "engine": self.MODEL_ID,
            },
            "output": output,
            "confidence": {"score": 0.5, "band": "medium", "basis": ["stub"]},
            "disagreement": {"metrics": []},
            "falsifier": {"status": "pass", "items": []},
            "audit": {
                "audit_record_id": f"audit:{request.run_id}/uma",
                "input_hash": dummy_hash,
                "output_hash": out_hash,
                "source_manifest_refs": [
                    "src:uma:weights-fair-chem-v1",
                    f"src:uma:hf-org:{self._hf_org}",
                ],
            },
            "rights": {
                "rights_claim_id": request.rights_claim_id,
                "reuse_scope": "tenant_only",
            },
            "back_edges": [],
            # UMA-specific audit metadata (not in L2MlipOutput schema, stored
            # as adapter-side record only).
            "_uma_gate": {
                "hf_org": self._hf_org,
                "hf_token_hint": self._hf_token_hint,
                "aup_accepted_at": self._aup_accepted_at,
            },
        }

    def blocked_manifests(self) -> list[dict[str, Any]]:
        """Return BlockedSourceManifest for UMA weights (always, regardless of gate state)."""
        m = BlockedSourceManifest(
            source_manifest_id="src:uma:weights-fair-chem-v1",
            attempted_locator="https://huggingface.co/facebook/uma",
            blocker_reason="license_unverified",
            blocker_detail=(
                "UMA weights require FAIR Chemistry License v1 acceptance and "
                "verified HuggingFace org registration. "
                "Library (fairchem): Apache-2.0. "
                "Weights: custom FAIR Chemistry License v1. "
                "Geographic restrictions: China, Russia, Belarus, OFAC-sanctioned. "
                "South Africa: unrestricted. "
                "AUP: military/warfare, ITAR, weapons excluded. "
                "Energy/battery materials: NOT restricted. "
                "Gate unblocked by calling enable_uma(hf_org, hf_token, aup_accepted_at). "
                f"Current gate state: {'enabled' if self._enabled else 'BLOCKED'}."
            ),
            retry_strategy=(
                "1. Register Zer0pa HuggingFace org with accurate organisational info. "
                "2. Navigate to HuggingFace UMA model page and accept FAIR Chemistry License v1. "
                "3. Generate HF access token with read scope. "
                "4. Call adapter.enable_uma(hf_org=<org>, hf_token=<token>, "
                "aup_accepted_at=<iso-utc-timestamp>). "
                "5. Re-run L2 pipeline."
            ),
        )
        return [m.model_dump(mode="json")]
