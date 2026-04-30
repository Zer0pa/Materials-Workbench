"""Thermo-Calc TDB QUARANTINE adapter (PRD §L3 — sovereignty policy).

THIS ADAPTER IS LOAD-BEARING FOR THE QUARANTINE CONTRACT.

PRD §L3 verbatim:
    Commercial Thermo-Calc TDBs are allowed only as quarantined read-only
    inputs for customer projects with valid license coverage. Commercial
    TDB data MUST NEVER be committed, copied into fixtures, redistributed,
    or used as general training data.

Quarantine semantics
--------------------

* The adapter is **default-blocked**. Every call without an active customer
  license raises :exc:`CommercialTdbQuarantineError`.

* When enabled per-customer via :meth:`enable_with_customer_license`, the
  adapter reads the TDB on disk (the operator must have it locally; we do
  NOT fetch or distribute commercial content) and returns:

    - a sha256 hash of the TDB content
    - a count of phases / elements parsed (metadata only)
    - the active customer license URN
    - **NO TDB plaintext**

  The envelope's ``output.tdb_ref`` is a hash-reference, not a path that
  callers could exfiltrate. ``output.equilibrium_phases`` reports the phase
  names (these are CALPHAD nomenclature, not commercial content). Phase
  numerical parameters are NEVER copied into the output.

* When disabled (default), :meth:`run` raises
  :exc:`CommercialTdbQuarantineError` with a structured message pointing
  the operator to :meth:`enable_with_customer_license`. Adapters that
  produce envelopes from blocked state instead would let downstream code
  silently treat blocked state as a valid run; that is the falsifier
  scenario this module exists to prevent.

* The accompanying falsifier
  :func:`zer0pa_materials.falsifiers.l3_falsifiers.tdb_quarantine_breach`
  scans an envelope's metadata and fails if a commercial-provider TDB is
  marked ``redistributable=True``, ``committed_to_repo=True``, or
  ``included_in_training_corpus=True``.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import re
from pathlib import Path
from typing import Any

from zer0pa_materials.adapters.l3.base import (
    L3CalphadAdapter,
    L3CalphadRequest,
    CommercialTdbQuarantineError,
)
from zer0pa_materials.audit.sources import BlockedSourceManifest
from zer0pa_materials.boundary import RESEARCH_BOUNDARY
from zer0pa_materials.envelope.hashing import sha256_of


__all__ = [
    "ThermoCalcTdbReadOnlyAdapter",
]


# Pattern to identify a commercial-provider hint in a TDB path or metadata.
_COMMERCIAL_PROVIDER_RE = re.compile(
    r"thermo.?calc|TC[FNSXP][A-Z]?\d*|TCFE|TCNI|TCTI|TCAL|TCNF|TCS",
    flags=re.IGNORECASE,
)


def _looks_commercial(provider_or_path: str) -> bool:
    """Return True if the provider string or path hints at a commercial TDB."""
    if not provider_or_path:
        return False
    return bool(_COMMERCIAL_PROVIDER_RE.search(provider_or_path))


def _parse_phase_names_quarantined(tdb_text: str) -> tuple[list[str], list[str]]:
    """Parse phase and element names from TDB text WITHOUT copying plaintext.

    Returns a tuple of (phase_names, element_names). Phase and element names
    are CALPHAD nomenclature (LIQUID, FCC_A1, FE, NI), not commercial content.

    All numerical parameters and Redlich-Kister coefficients are discarded
    in this parser — the adapter ONLY exposes phase set + element set.
    """
    phase_names: list[str] = []
    element_names: list[str] = []
    for raw_line in tdb_text.splitlines():
        line = raw_line.strip().upper()
        if not line or line.startswith("$"):
            continue
        # ELEMENT <name> <ref-state> <mass> <H298> <S298> !
        if line.startswith("ELEMENT"):
            parts = line.split()
            if len(parts) >= 2:
                el = parts[1]
                if el and el not in {"/-", "VA"} and el not in element_names:
                    element_names.append(el)
            continue
        # PHASE <name> <type> <n_sub> <ratios> !
        if line.startswith("PHASE"):
            parts = line.split()
            if len(parts) >= 2:
                ph = parts[1].rstrip(":")
                if ph and ph not in phase_names:
                    phase_names.append(ph)
            continue
    return phase_names, element_names


class ThermoCalcTdbReadOnlyAdapter(L3CalphadAdapter):
    """QUARANTINE adapter for commercial Thermo-Calc TDBs.

    Default-blocked. Enabling requires a customer license proof URI + a
    customer ID. Once enabled, the adapter reads the TDB on disk and emits
    a hash + metadata (phase set, element set, file size, file hash) but
    NEVER copies the TDB plaintext content into outputs.

    Attributes
    ----------
    enabled:
        ``False`` until :meth:`enable_with_customer_license` succeeds.
    customer_id:
        URN identifier of the licensed customer (e.g., ``"customer:foo:001"``).
    license_proof_uri:
        URI to the license proof artifact stored outside the repo.
    enabled_at:
        ISO-8601 UTC timestamp of when the adapter was enabled.
    """

    NAME = "ThermoCalcTdbReadOnlyAdapter"
    VERSION = "0.1.0"

    def __init__(self) -> None:
        self.enabled: bool = False
        self.customer_id: str | None = None
        self.license_proof_uri: str | None = None
        self.enabled_at: str | None = None

    # -------------------------------------------------- gating

    def enable_with_customer_license(
        self,
        customer_id: str,
        license_proof_uri: str,
        enabled_at: str | None = None,
    ) -> None:
        """Enable QUARANTINE-mode reading for a specific customer.

        Parameters
        ----------
        customer_id:
            URN starting with ``"customer:"`` identifying the licensed
            customer. Required.
        license_proof_uri:
            URI of the license proof artifact (must be hosted OUTSIDE the
            repo — the repo never carries license proof for commercial
            artifacts).
        enabled_at:
            ISO-8601 UTC timestamp of enablement. Defaults to ``now()``.
        """
        if not customer_id or not customer_id.startswith("customer:"):
            raise ValueError(
                "customer_id must start with 'customer:' (e.g. 'customer:acme:001')"
            )
        if not license_proof_uri.strip():
            raise ValueError("license_proof_uri must be a non-empty string")
        if enabled_at is None:
            enabled_at = _dt.datetime.now(tz=_dt.timezone.utc).isoformat(
                timespec="microseconds"
            )
        self.customer_id = customer_id
        self.license_proof_uri = license_proof_uri
        self.enabled_at = enabled_at
        self.enabled = True

    def disable(self) -> None:
        """Reset the adapter to the blocked state (use after a campaign closes)."""
        self.enabled = False
        self.customer_id = None
        self.license_proof_uri = None
        self.enabled_at = None

    # -------------------------------------------------- run

    def run(
        self,
        request: L3CalphadRequest,
    ) -> dict[str, Any]:
        """Read a commercial TDB under QUARANTINE.

        Raises
        ------
        CommercialTdbQuarantineError
            If the adapter is not enabled with a customer license, or if
            ``request.tdb_path`` is missing/non-existent.
        """
        if not self.enabled:
            raise CommercialTdbQuarantineError(
                "ThermoCalcTdbReadOnlyAdapter is BLOCKED by default. "
                "Quarantine policy (PRD §L3): commercial TDBs may only be "
                "read under an active customer license. Call "
                "enable_with_customer_license(customer_id='customer:...', "
                "license_proof_uri='...') before invoking run()."
            )

        if not request.tdb_path:
            raise CommercialTdbQuarantineError(
                "request.tdb_path is required when reading a commercial TDB "
                "under quarantine. Provide an absolute path to a customer-"
                "supplied TDB file."
            )
        tdb_file = Path(request.tdb_path)
        if not tdb_file.is_file():
            raise CommercialTdbQuarantineError(
                f"Commercial TDB not found at: {request.tdb_path}. "
                "The adapter never auto-fetches commercial content."
            )

        # Read the TDB once for hashing + phase/element parsing.
        # We discard the text after parsing to avoid keeping plaintext in
        # memory longer than necessary.
        tdb_bytes = tdb_file.read_bytes()
        tdb_hash = "sha256:" + hashlib.sha256(tdb_bytes).hexdigest()
        try:
            tdb_text = tdb_bytes.decode("utf-8", errors="replace")
        except Exception:
            tdb_text = ""
        phase_names, element_names = _parse_phase_names_quarantined(tdb_text)
        # Drop the plaintext.
        del tdb_text
        del tdb_bytes

        # Detect commercial provider hint in the path (audit signal).
        commercial_hint = _looks_commercial(str(tdb_file))

        output: dict[str, Any] = {
            # tdb_ref is a hash-only reference. Callers cannot reconstruct
            # the TDB content from this URI.
            "tdb_ref": f"hash://{tdb_hash}",
            "equilibrium_phases": phase_names,
            "phase_fraction_posterior": {},  # No equilibrium computed.
            "espei_diagnostics": {
                "ran": False,
                "reason": "quarantine_metadata_only",
            },
            "fixture_phase_boundary_drift_K": None,
            "phase_set_jaccard_distance": None,
            "phase_fraction_js_divergence": None,
        }
        out_hash = "sha256:" + sha256_of(output).split("sha256:", 1)[1]

        envelope: dict[str, Any] = {
            "research_boundary": RESEARCH_BOUNDARY,
            "contract_version": "zer0pa.materials.layer-envelope.v1",
            "layer": "L3",
            "run_id": request.run_id,
            "candidate_id": request.candidate_id,
            "campaign_id": request.campaign_id,
            "tool_adapter": {
                "name": self.NAME,
                "version": self.VERSION,
                # The Envelope.Backend literal is {stub, local_cpu, runpod_mock,
                # runpod_rest}. Quarantined commercial reads are local_cpu
                # operations on a customer-supplied file; the
                # ``thermo_calc_quarantined`` discriminator lives in
                # ``_quarantine_meta`` and ``engine``.
                "backend": "local_cpu",
                "engine": "thermo-calc-quarantined-read-only",
            },
            "output": output,
            "confidence": {
                "score": 0.5,  # Metadata-only; downstream pycalphad consumes the file.
                "band": "low",
                "basis": [
                    "quarantine_mode=metadata_only",
                    f"customer_id={self.customer_id}",
                    f"commercial_hint={commercial_hint}",
                ],
            },
            "disagreement": {"metrics": []},
            "falsifier": {"status": "pass", "items": []},
            "audit": {
                "audit_record_id": f"audit:{request.run_id}/thermocalc-quarantine",
                "input_hash": tdb_hash,
                "output_hash": out_hash,
                "source_manifest_refs": [],  # Commercial source is per-customer.
            },
            "rights": {
                "rights_claim_id": request.rights_claim_id,
                "reuse_scope": "tenant_only",
            },
            "back_edges": [],
            # Quarantine metadata — DOWNSTREAM AUDITORS / FALSIFIERS CONSUME THIS.
            "_quarantine_meta": {
                "tdb_provider": "ThermoCalc",
                "license": "proprietary",
                "redistributable": False,
                "committed_to_repo": False,
                "included_in_training_corpus": False,
                "customer_id": self.customer_id,
                "license_proof_uri": self.license_proof_uri,
                "enabled_at": self.enabled_at,
                "tdb_hash": tdb_hash,
                "n_phases_metadata": len(phase_names),
                "n_elements_metadata": len(element_names),
                "tdb_size_bytes": tdb_file.stat().st_size,
                "commercial_provider_hint": commercial_hint,
            },
        }
        return envelope

    # -------------------------------------------------- blocked_manifests

    def blocked_manifests(self) -> list[dict[str, Any]]:
        """Return BlockedSourceManifest entries for the quarantine adapter.

        Always emits a manifest. When disabled, the manifest reflects the
        default-blocked posture. When enabled, the manifest reflects the
        per-customer license context (so the audit ledger records that
        commercial content was accessed under the named customer's license).
        """
        if self.enabled:
            return [
                BlockedSourceManifest(
                    source_manifest_id=f"src:thermocalc:tdb:{self.customer_id}",
                    attempted_locator=self.license_proof_uri or "customer-supplied",
                    blocker_reason="policy",
                    blocker_detail=(
                        "Commercial Thermo-Calc TDB read under customer "
                        f"license: {self.customer_id}. PRD §L3: NEVER "
                        "committed, copied to fixtures, redistributed, or "
                        "used as training data. Per-customer scope only."
                    ),
                    retry_strategy=(
                        "Continue reading the TDB under the active customer "
                        "license. When the customer engagement closes, call "
                        "ThermoCalcTdbReadOnlyAdapter.disable() to reset to "
                        "the blocked state."
                    ),
                ).model_dump(mode="json")
            ]
        return [
            BlockedSourceManifest(
                source_manifest_id="src:thermocalc:tdb:blocked",
                attempted_locator="(no license — adapter is in default-blocked state)",
                blocker_reason="license_unverified",
                blocker_detail=(
                    "ThermoCalcTdbReadOnlyAdapter is default-blocked per "
                    "PRD §L3 quarantine policy. Commercial Thermo-Calc TDBs "
                    "(TCFE, TCNI, TCTI, TCAL, etc.) require a per-customer "
                    "license. Files are NEVER committed to this repo, "
                    "copied to fixtures, redistributed, or used as training "
                    "corpus."
                ),
                retry_strategy=(
                    "For a customer with a valid license: call "
                    "ThermoCalcTdbReadOnlyAdapter.enable_with_customer_license("
                    "customer_id='customer:<urn>', license_proof_uri='<url>'). "
                    "License proof URIs MUST live outside this repo."
                ),
            ).model_dump(mode="json")
        ]
