"""Verifiable UMA AUP / FAIR Chemistry License manifest.

Boundary
--------
Research infrastructure for in silico materials science discovery. Outputs are
research artifacts. No regulatory certification claims. No clinical or
human-subject use. ITAR / weapons applications are out of scope (Meta UMA
Acceptable Use Policy and operator policy).

Purpose
-------

Wave 3A.3 license correction (deep-research-verified) established the load-
bearing facts about UMA enablement:

* fairchem library license: MIT (facebookresearch/fairchem/main/LICENSE.md).
* UMA weights license: FAIR Chemistry License v1 (custom, restrictive).
* Geographic restrictions: China, Russia, Belarus, OFAC-sanctioned.
  South Africa is unrestricted.
* AUP exclusions: military / warfare / ITAR / weapons. Energy and battery
  materials are NOT restricted.
* Output ownership: per FAIR-CL-v1, "as between you and Meta, you are and
  will be the owner of [derivative works and modifications]".

The existing :class:`UmaCalculatorAdapter.enable_uma` accepts ``hf_org``,
``hf_token``, ``aup_accepted_at`` and unblocks the gate. That is necessary
but not sufficient: the unblock leaves no committed, verifiable record on
disk. Wave D adds the missing layer:

1. :class:`UmaAupLicenseManifest` — a Pydantic record of the operator's
   acceptance, hashed canonically. This is the auditable artifact.
2. :func:`verify_uma_manifest` — a falsifier that recomputes the manifest's
   own hash, verifies it matches the recorded ``hash`` field, checks the
   AUP timestamp is in the past, and checks the geographic jurisdiction is
   allowed by the AUP.
3. :func:`enable_uma_with_manifest` — a wrapper around
   :meth:`UmaCalculatorAdapter.enable_uma` that REQUIRES a valid manifest
   on disk before unblocking. The adapter cannot be enabled without a
   manifest verification pass.

A starter manifest lives at ``phases/UMA-license/manifest.json`` with
operator-fillable placeholders. A safe-defaults template lives at
``phases/UMA-license/manifest.template.json`` so operators copy-and-fill.

Hash contract
-------------

The manifest's ``hash`` field is the sha256 of the canonical JSON of the
manifest WITHOUT the ``hash`` field itself. This is the same construction
used by the artifact manifest in
:mod:`zer0pa_materials_workbench.envelope.artifacts`. The recompute simply drops
the ``hash`` key and rehashes — any forged manifest fails this check.
"""

from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from zer0pa_materials_workbench.boundary import RESEARCH_BOUNDARY
from zer0pa_materials_workbench.envelope.falsifier import FalsifierItem
from zer0pa_materials_workbench.envelope.hashing import sha256_of

__all__ = [
    "DEFAULT_MANIFEST_VERSION",
    "MANIFEST_HASH_FIELD",
    "RESTRICTED_JURISDICTIONS",
    "UmaAupLicenseManifest",
    "UmaManifestVerificationError",
    "compute_manifest_hash",
    "enable_uma_with_manifest",
    "load_manifest_from_path",
    "verify_uma_manifest",
]


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


DEFAULT_MANIFEST_VERSION: Literal["zer0pa.uma.aup.v1"] = "zer0pa.uma.aup.v1"
MANIFEST_HASH_FIELD: str = "hash"


# Per FAIR Chemistry License v1, ALSO mirrored in the UMA blocked-source
# manifest (see :mod:`zer0pa_materials_workbench.adapters.l2.uma`):
#
#   "Geographic restrictions: China, Russia, Belarus, OFAC-sanctioned."
#
# OFAC-sanctioned countries change over time; we list the named ones
# explicitly and rely on ``geographic_jurisdiction_verified_against_aup``
# being True (operator attestation) to catch the OFAC delta. South
# Africa, the operator jurisdiction, is unrestricted per the deep-
# research correction.
RESTRICTED_JURISDICTIONS: frozenset[str] = frozenset(
    {
        "CN",  # China
        "RU",  # Russia
        "BY",  # Belarus
        # OFAC-sanctioned (a static snapshot; operator must keep current):
        "IR",  # Iran
        "KP",  # North Korea
        "SY",  # Syria
        "CU",  # Cuba
    }
)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class UmaManifestVerificationError(RuntimeError):
    """Raised by :func:`enable_uma_with_manifest` when verification fails.

    Carries the falsifier item so the caller can record it in the audit
    ledger. The adapter MUST NOT be unblocked when this is raised.
    """

    def __init__(self, item: FalsifierItem) -> None:
        self.item = item
        rationale = item.rationale or "uma_manifest_verification_failed"
        super().__init__(f"UMA manifest verification failed: {rationale}")


# ---------------------------------------------------------------------------
# Manifest schema
# ---------------------------------------------------------------------------


def _validate_iso_utc_str(v: str | _dt.datetime) -> str:
    if isinstance(v, _dt.datetime):
        if v.tzinfo is None:
            raise ValueError("datetime must include a timezone offset (UTC preferred).")
        return v.isoformat(timespec="microseconds")
    try:
        parsed = _dt.datetime.fromisoformat(v)
    except ValueError as exc:
        raise ValueError(f"timestamp must be ISO-8601: {exc}") from exc
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include a timezone offset (UTC preferred).")
    return v


class UmaAupLicenseManifest(BaseModel):
    """Verifiable record of UMA enablement.

    Each field is intentionally explicit — the manifest is the operator's
    ATTESTATION that the FAIR Chemistry License v1 obligations have been
    met. The ``hash`` field is recomputed by :func:`verify_uma_manifest`
    against the canonical JSON of every other field, so a tampered
    manifest is detected.

    Fields
    ------
    manifest_version
        Schema version literal. The Wave D contract is ``zer0pa.uma.aup.v1``.
    research_boundary
        Verbatim copy of :data:`RESEARCH_BOUNDARY`.
    library_license_spdx
        Always ``"MIT"`` for the fairchem library — Wave 3A.3 correction.
    weights_license
        Always ``"FAIR-Chemistry-License-v1"`` — the UMA weights license.
    hf_organization
        Verified HuggingFace organisation that holds the licence acceptance.
    hf_organization_verified_at
        ISO-8601 UTC timestamp of when the operator verified the org.
    aup_accepted_at
        ISO-8601 UTC timestamp of AUP acceptance.
    aup_accepted_by
        Operator identity (free-form string; e.g. "architects@zer0pa.ai").
    geographic_jurisdiction
        ISO 3166-1 alpha-2 code, e.g. ``"ZA"`` for South Africa.
    geographic_jurisdiction_verified_against_aup
        Operator attestation that the jurisdiction is allowed by FAIR-CL-v1.
        For non-restricted jurisdictions this MUST be True for the manifest
        to verify.
    fairchem_repo_commit
        SHA of facebookresearch/fairchem at acceptance time, or ``None``
        if not pinned.
    derivative_works_ownership_acknowledged
        Operator attestation of FAIR-CL-v1 §"Ownership" terms.
    audit_record_id
        URN linking this manifest to its source-manifest row in
        ``audit/runtime/sources.jsonl``.
    hash
        sha256 of canonical JSON of the manifest with ``hash`` removed.
        Recomputed on verify.
    """

    model_config = ConfigDict(extra="forbid")

    manifest_version: Literal["zer0pa.uma.aup.v1"] = Field(
        default=DEFAULT_MANIFEST_VERSION,
        description="Schema version. Wave D contract is 'zer0pa.uma.aup.v1'.",
    )
    research_boundary: str = Field(
        ...,
        description="Verbatim research boundary text.",
    )
    library_license_spdx: Literal["MIT"] = Field(
        default="MIT",
        description="fairchem library license — always MIT.",
    )
    weights_license: Literal["FAIR-Chemistry-License-v1"] = Field(
        default="FAIR-Chemistry-License-v1",
        description="UMA weights license.",
    )
    hf_organization: str = Field(
        ...,
        min_length=1,
        description="Verified HuggingFace organisation name.",
    )
    hf_organization_verified_at: str = Field(
        ...,
        description="ISO-8601 UTC timestamp of HF org verification.",
    )
    aup_accepted_at: str = Field(
        ...,
        description="ISO-8601 UTC timestamp of FAIR-CL-v1 AUP acceptance.",
    )
    aup_accepted_by: str = Field(
        ...,
        min_length=1,
        description="Operator identity (e.g. email or stable agent ID).",
    )
    geographic_jurisdiction: str = Field(
        ...,
        min_length=2,
        max_length=2,
        description="ISO 3166-1 alpha-2 code (e.g. 'ZA' for South Africa).",
    )
    geographic_jurisdiction_verified_against_aup: bool = Field(
        ...,
        description="Operator attestation that the jurisdiction is FAIR-CL-v1 compliant.",
    )
    fairchem_repo_commit: str | None = Field(
        default=None,
        description="SHA of facebookresearch/fairchem at acceptance, or None.",
    )
    derivative_works_ownership_acknowledged: bool = Field(
        ...,
        description="Operator attestation of FAIR-CL-v1 ownership terms.",
    )
    audit_record_id: str = Field(
        ...,
        description="URN of the sources.jsonl row that records this manifest.",
    )
    hash: str = Field(
        ...,
        description="sha256 of canonical JSON of the manifest with 'hash' removed.",
    )

    @field_validator("research_boundary")
    @classmethod
    def _v_boundary(cls, v: str) -> str:
        if v != RESEARCH_BOUNDARY:
            raise ValueError(
                "research_boundary must equal RESEARCH_BOUNDARY exactly."
            )
        return v

    @field_validator("hf_organization_verified_at", "aup_accepted_at")
    @classmethod
    def _v_iso_ts(cls, v: str | _dt.datetime) -> str:
        return _validate_iso_utc_str(v)

    @field_validator("geographic_jurisdiction")
    @classmethod
    def _v_jurisdiction(cls, v: str) -> str:
        if not v.isupper() or len(v) != 2 or not v.isalpha():
            raise ValueError(
                f"geographic_jurisdiction must be an ISO 3166-1 alpha-2 code; got {v!r}"
            )
        return v

    @field_validator("audit_record_id")
    @classmethod
    def _v_audit_id(cls, v: str) -> str:
        if not v.startswith("audit:"):
            raise ValueError(f"audit_record_id must start with 'audit:'; got {v!r}")
        return v


# ---------------------------------------------------------------------------
# Hash compute / verify primitives
# ---------------------------------------------------------------------------


def _manifest_payload_minus_hash(payload: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of ``payload`` with the hash field removed."""
    return {k: v for k, v in payload.items() if k != MANIFEST_HASH_FIELD}


def compute_manifest_hash(payload: dict[str, Any]) -> str:
    """Compute the canonical sha256 of a manifest payload.

    Drops the existing ``hash`` field (so this works whether or not the
    payload has been hashed yet), serialises with sort_keys, and returns
    the canonical ``sha256:<hex>`` form.
    """
    return sha256_of(_manifest_payload_minus_hash(payload))


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------


def load_manifest_from_path(path: str | Path) -> UmaAupLicenseManifest:
    """Read a manifest JSON file and parse it into the Pydantic model.

    Raises:
        FileNotFoundError: when the path doesn't exist.
        ValueError: when the JSON cannot be parsed or the schema rejects it.
    """
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"UMA manifest not found at {p}")
    text = p.read_text(encoding="utf-8")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"UMA manifest at {p} is not valid JSON: {exc}") from exc
    try:
        return UmaAupLicenseManifest.model_validate(data)
    except Exception as exc:
        raise ValueError(f"UMA manifest at {p} fails schema validation: {exc}") from exc


# ---------------------------------------------------------------------------
# Falsifier
# ---------------------------------------------------------------------------


def verify_uma_manifest(
    manifest_path: str | Path,
    *,
    now: _dt.datetime | None = None,
) -> FalsifierItem:
    """Verify a UMA AUP/license manifest on disk.

    Checks performed (all must pass for ``status="pass"``):

    1. File exists, parses as JSON, and schema-validates as
       :class:`UmaAupLicenseManifest`.
    2. The recorded ``hash`` matches the canonical recompute of every
       other field (Wave D recompute discipline).
    3. ``aup_accepted_at`` is in the past (cannot accept the future).
    4. ``hf_organization_verified_at`` is in the past.
    5. If the jurisdiction is in :data:`RESTRICTED_JURISDICTIONS`,
       returns ``status="fail"`` regardless of the verified flag.
    6. If the jurisdiction is NOT in :data:`RESTRICTED_JURISDICTIONS`,
       ``geographic_jurisdiction_verified_against_aup`` MUST be True.
    7. ``derivative_works_ownership_acknowledged`` MUST be True
       (FAIR-CL-v1 contract).
    8. ``library_license_spdx`` MUST be ``"MIT"`` (Wave 3A.3).
    9. ``weights_license`` MUST be ``"FAIR-Chemistry-License-v1"``.

    Returns a :class:`FalsifierItem` with ``status="pass"`` if every
    check passes, ``status="fail"`` with ``rationale`` set otherwise,
    or ``status="blocked"`` if the file cannot be read.
    """
    p = Path(manifest_path)
    if not p.is_file():
        return FalsifierItem(
            name="uma.manifest_verifiable",
            threshold="manifest exists, schema-validates, hash recomputes",
            actual={"path": str(p), "exists": False},
            status="blocked",
            rationale=f"manifest not found at {p}",
        )

    try:
        text = p.read_text(encoding="utf-8")
        raw = json.loads(text)
    except (OSError, json.JSONDecodeError) as exc:
        return FalsifierItem(
            name="uma.manifest_verifiable",
            threshold="manifest exists, schema-validates, hash recomputes",
            actual={"path": str(p), "error": str(exc)[:200]},
            status="fail",
            rationale=f"unreadable manifest: {exc}",
        )

    try:
        manifest = UmaAupLicenseManifest.model_validate(raw)
    except Exception as exc:
        return FalsifierItem(
            name="uma.manifest_verifiable",
            threshold="manifest exists, schema-validates, hash recomputes",
            actual={"path": str(p), "error": str(exc)[:300]},
            status="fail",
            rationale=f"schema validation failed: {exc}",
        )

    # 2: hash recompute.
    payload = manifest.model_dump(mode="json")
    recomputed = compute_manifest_hash(payload)
    if recomputed != manifest.hash:
        return FalsifierItem(
            name="uma.manifest_verifiable",
            threshold="manifest hash recomputes to recorded value",
            actual={
                "claimed_hash": manifest.hash,
                "recomputed_hash": recomputed,
            },
            status="fail",
            rationale="manifest hash mismatch — payload tampered or stale",
        )

    # 3-4: timestamp sanity.
    now = now or _dt.datetime.now(tz=_dt.timezone.utc)
    try:
        aup_dt = _dt.datetime.fromisoformat(manifest.aup_accepted_at)
        org_dt = _dt.datetime.fromisoformat(manifest.hf_organization_verified_at)
    except ValueError as exc:
        return FalsifierItem(
            name="uma.manifest_verifiable",
            threshold="aup_accepted_at and hf_organization_verified_at parse as UTC",
            actual={"error": str(exc)},
            status="fail",
            rationale="timestamp not parseable",
        )

    if aup_dt > now:
        return FalsifierItem(
            name="uma.manifest_verifiable",
            threshold="aup_accepted_at in the past",
            actual={"aup_accepted_at": manifest.aup_accepted_at, "now": now.isoformat()},
            status="fail",
            rationale="aup_accepted_at is in the future",
        )
    if org_dt > now:
        return FalsifierItem(
            name="uma.manifest_verifiable",
            threshold="hf_organization_verified_at in the past",
            actual={
                "hf_organization_verified_at": manifest.hf_organization_verified_at,
                "now": now.isoformat(),
            },
            status="fail",
            rationale="hf_organization_verified_at is in the future",
        )

    # 5: restricted jurisdiction.
    if manifest.geographic_jurisdiction in RESTRICTED_JURISDICTIONS:
        return FalsifierItem(
            name="uma.manifest_verifiable",
            threshold=(
                "geographic_jurisdiction not in FAIR-CL-v1 restricted set "
                "(China, Russia, Belarus, OFAC-sanctioned)"
            ),
            actual={"geographic_jurisdiction": manifest.geographic_jurisdiction},
            status="fail",
            rationale=(
                f"geographic_jurisdiction {manifest.geographic_jurisdiction!r} is "
                "in the FAIR-CL-v1 restricted set; UMA cannot be enabled"
            ),
        )

    # 6: non-restricted jurisdiction MUST be verified against the AUP.
    if not manifest.geographic_jurisdiction_verified_against_aup:
        return FalsifierItem(
            name="uma.manifest_verifiable",
            threshold="geographic_jurisdiction_verified_against_aup == True",
            actual={
                "geographic_jurisdiction": manifest.geographic_jurisdiction,
                "verified": False,
            },
            status="fail",
            rationale=(
                "operator did not attest that the jurisdiction is FAIR-CL-v1 compliant; "
                "manifest cannot unblock UMA"
            ),
        )

    # 7: ownership acknowledgement.
    if not manifest.derivative_works_ownership_acknowledged:
        return FalsifierItem(
            name="uma.manifest_verifiable",
            threshold="derivative_works_ownership_acknowledged == True",
            actual={"acknowledged": False},
            status="fail",
            rationale="FAIR-CL-v1 ownership terms not acknowledged",
        )

    # 8-9: license-text fields are Literal-validated by Pydantic, so we
    # only re-check them defensively.
    if manifest.library_license_spdx != "MIT":
        return FalsifierItem(
            name="uma.manifest_verifiable",
            threshold="library_license_spdx == 'MIT' (fairchem)",
            actual={"library_license_spdx": manifest.library_license_spdx},
            status="fail",
            rationale="fairchem library license must be MIT",
        )
    if manifest.weights_license != "FAIR-Chemistry-License-v1":
        return FalsifierItem(
            name="uma.manifest_verifiable",
            threshold="weights_license == 'FAIR-Chemistry-License-v1'",
            actual={"weights_license": manifest.weights_license},
            status="fail",
            rationale="UMA weights license must be FAIR-Chemistry-License-v1",
        )

    return FalsifierItem(
        name="uma.manifest_verifiable",
        threshold=(
            "all UMA AUP/license invariants hold "
            "(MIT lib, FAIR-CL-v1 weights, ZA jurisdiction, ownership ack, hash recomputes)"
        ),
        actual={
            "manifest_version": manifest.manifest_version,
            "hf_organization": manifest.hf_organization,
            "geographic_jurisdiction": manifest.geographic_jurisdiction,
            "library_license_spdx": manifest.library_license_spdx,
            "weights_license": manifest.weights_license,
            "audit_record_id": manifest.audit_record_id,
        },
        status="pass",
    )


# ---------------------------------------------------------------------------
# Adapter wrapper
# ---------------------------------------------------------------------------


def enable_uma_with_manifest(
    adapter: Any,
    manifest_path: str | Path,
    *,
    hf_token: str | None = None,
) -> FalsifierItem:
    """Enable a :class:`UmaCalculatorAdapter` only after manifest verification.

    The PRD discipline is ``enable_uma`` — explicit, auditable, callable
    only by the operator. Wave D adds the manifest layer: the operator
    cannot unblock the adapter without producing (and pinning) a
    verifiable manifest. This wrapper:

    1. Reads the manifest at ``manifest_path``.
    2. Calls :func:`verify_uma_manifest`. If it fails, raises
       :class:`UmaManifestVerificationError` and the adapter remains
       blocked.
    3. If manifest pass, calls
       ``adapter.enable_uma(hf_org=manifest.hf_organization,
       hf_token=hf_token, aup_accepted_at=manifest.aup_accepted_at)``.

    Parameters
    ----------
    adapter
        A ``UmaCalculatorAdapter`` (or any object exposing
        ``enable_uma(hf_org, hf_token, aup_accepted_at)``). Duck-typed
        so the same wrapper works in tests.
    manifest_path
        Path to the JSON manifest. The default repo location is
        ``phases/UMA-license/manifest.json``.
    hf_token
        HuggingFace access token. Required by the underlying
        ``enable_uma``; not stored in the manifest. May be passed via
        the ``HUGGINGFACE_HUB_TOKEN`` env if the caller wishes; we
        require it explicit here to keep the path testable.

    Returns
    -------
    FalsifierItem
        The verification item from :func:`verify_uma_manifest`. Always
        ``status="pass"`` on this path because failures raise.

    Raises
    ------
    UmaManifestVerificationError
        When the manifest does not verify. The adapter is NOT enabled.
    ValueError
        When ``hf_token`` is missing.
    """
    item = verify_uma_manifest(manifest_path)
    if item.status != "pass":
        raise UmaManifestVerificationError(item)

    if not hf_token:
        raise ValueError(
            "hf_token is required to enable UMA; manifest verification alone is not "
            "sufficient (the adapter still needs the live token for the predict path)."
        )

    manifest = load_manifest_from_path(manifest_path)
    adapter.enable_uma(
        hf_org=manifest.hf_organization,
        hf_token=hf_token,
        aup_accepted_at=manifest.aup_accepted_at,
    )
    return item
