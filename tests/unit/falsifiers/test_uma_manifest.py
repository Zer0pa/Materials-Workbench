"""Tests for the verifiable UMA AUP/license manifest (Wave D).

Boundary
--------
Research infrastructure for in silico materials science discovery. Outputs are
research artifacts. No regulatory certification claims. No clinical or
human-subject use. ITAR / weapons applications are out of scope (Meta UMA
Acceptable Use Policy and operator policy).

Coverage
--------
* Schema validation: required fields, ISO timestamps, alpha-2 jurisdiction.
* Hash recompute: tampered payload → recompute mismatch → fail.
* Restricted-jurisdiction handling: CN / RU / BY / OFAC fail by policy.
* Future-dated timestamps fail.
* The starter manifest at ``phases/UMA-license/manifest.json`` rejects
  by design (placeholders for the operator to fill).
* The template manifest at ``phases/UMA-license/manifest.template.json``
  passes (safe defaults for ZA jurisdiction, ownership acknowledged).
* The wrapper :func:`enable_uma_with_manifest` refuses to unblock the
  adapter when the manifest fails.
* The wrapper unblocks correctly when the manifest passes.
"""

from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path

import pytest

from zer0pa_materials_workbench.boundary import RESEARCH_BOUNDARY
from zer0pa_materials_workbench.falsifiers.uma_manifest import (
    DEFAULT_MANIFEST_VERSION,
    RESTRICTED_JURISDICTIONS,
    UmaAupLicenseManifest,
    UmaManifestVerificationError,
    compute_manifest_hash,
    enable_uma_with_manifest,
    verify_uma_manifest,
)
from zer0pa_materials_workbench.repo_root import phase_dir

# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------


def _valid_payload(**overrides) -> dict:
    """Return a manifest payload that passes verification by default."""
    base = {
        "manifest_version": DEFAULT_MANIFEST_VERSION,
        "research_boundary": RESEARCH_BOUNDARY,
        "library_license_spdx": "MIT",
        "weights_license": "FAIR-Chemistry-License-v1",
        "hf_organization": "zer0pa-research",
        "hf_organization_verified_at": "2026-04-29T00:00:00+00:00",
        "aup_accepted_at": "2026-04-29T00:00:00+00:00",
        "aup_accepted_by": "architects@zer0pa.ai",
        "geographic_jurisdiction": "ZA",
        "geographic_jurisdiction_verified_against_aup": True,
        "fairchem_repo_commit": "0123456789abcdef0123456789abcdef01234567",
        "derivative_works_ownership_acknowledged": True,
        "audit_record_id": "audit:uma/license/v1",
    }
    base.update(overrides)
    base["hash"] = compute_manifest_hash(base)
    return base


def _write_manifest(tmp_path: Path, payload: dict) -> Path:
    out = tmp_path / "manifest.json"
    out.write_text(json.dumps(payload), encoding="utf-8")
    return out


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------


class TestSchema:
    def test_valid_payload_validates(self):
        payload = _valid_payload()
        m = UmaAupLicenseManifest.model_validate(payload)
        assert m.manifest_version == "zer0pa.uma.aup.v1"
        assert m.weights_license == "FAIR-Chemistry-License-v1"

    def test_research_boundary_must_match_verbatim(self):
        with pytest.raises(Exception):
            UmaAupLicenseManifest.model_validate(
                _valid_payload(research_boundary="research only")
            )

    def test_jurisdiction_must_be_alpha2(self):
        with pytest.raises(Exception):
            UmaAupLicenseManifest.model_validate(
                _valid_payload(geographic_jurisdiction="ZAF")  # 3-letter
            )

    def test_audit_record_id_must_start_with_audit(self):
        with pytest.raises(Exception):
            UmaAupLicenseManifest.model_validate(
                _valid_payload(audit_record_id="not-a-urn")
            )


# ---------------------------------------------------------------------------
# Hash recompute
# ---------------------------------------------------------------------------


class TestHashRecompute:
    def test_pass_on_consistent_payload(self, tmp_path):
        path = _write_manifest(tmp_path, _valid_payload())
        item = verify_uma_manifest(path)
        assert item.status == "pass"

    def test_fail_on_tampered_field(self, tmp_path):
        payload = _valid_payload()
        # Tamper with hf_organization but leave hash unchanged.
        payload["hf_organization"] = "tampered-org"
        path = _write_manifest(tmp_path, payload)
        item = verify_uma_manifest(path)
        assert item.status == "fail"
        assert "hash mismatch" in (item.rationale or "").lower()


# ---------------------------------------------------------------------------
# Restricted jurisdictions
# ---------------------------------------------------------------------------


class TestRestrictedJurisdictions:
    @pytest.mark.parametrize("jurisdiction", sorted(RESTRICTED_JURISDICTIONS))
    def test_restricted_jurisdiction_fails(self, tmp_path, jurisdiction):
        payload = _valid_payload(geographic_jurisdiction=jurisdiction)
        path = _write_manifest(tmp_path, payload)
        item = verify_uma_manifest(path)
        assert item.status == "fail"
        assert "restricted" in (item.rationale or "").lower()

    def test_unrestricted_jurisdiction_passes(self, tmp_path):
        payload = _valid_payload(geographic_jurisdiction="ZA")
        path = _write_manifest(tmp_path, payload)
        item = verify_uma_manifest(path)
        assert item.status == "pass"

    def test_unrestricted_but_not_attested_fails(self, tmp_path):
        payload = _valid_payload(
            geographic_jurisdiction="ZA",
            geographic_jurisdiction_verified_against_aup=False,
        )
        path = _write_manifest(tmp_path, payload)
        item = verify_uma_manifest(path)
        assert item.status == "fail"
        assert "did not attest" in (item.rationale or "").lower()


# ---------------------------------------------------------------------------
# Timestamp sanity
# ---------------------------------------------------------------------------


class TestTimestamps:
    def test_future_aup_timestamp_fails(self, tmp_path):
        future = (
            _dt.datetime.now(tz=_dt.timezone.utc) + _dt.timedelta(days=365)
        ).isoformat(timespec="microseconds")
        payload = _valid_payload(aup_accepted_at=future)
        path = _write_manifest(tmp_path, payload)
        item = verify_uma_manifest(path)
        assert item.status == "fail"
        assert "future" in (item.rationale or "").lower()


# ---------------------------------------------------------------------------
# Ownership / license invariants
# ---------------------------------------------------------------------------


class TestOwnership:
    def test_ownership_not_acknowledged_fails(self, tmp_path):
        payload = _valid_payload(derivative_works_ownership_acknowledged=False)
        path = _write_manifest(tmp_path, payload)
        item = verify_uma_manifest(path)
        assert item.status == "fail"
        assert "ownership" in (item.rationale or "").lower()


# ---------------------------------------------------------------------------
# Repo-committed manifests
# ---------------------------------------------------------------------------


class TestCommittedManifests:
    def test_starter_manifest_fails(self):
        path = phase_dir("UMA-license") / "manifest.json"
        assert path.exists()
        item = verify_uma_manifest(path)
        # Starter is intentionally unfilled — operator must fill it.
        assert item.status == "fail"

    def test_template_manifest_passes(self):
        path = phase_dir("UMA-license") / "manifest.template.json"
        assert path.exists()
        item = verify_uma_manifest(path)
        assert item.status == "pass"


# ---------------------------------------------------------------------------
# Adapter wrapper
# ---------------------------------------------------------------------------


class _StubUmaAdapter:
    """Minimal stand-in for UmaCalculatorAdapter for the wrapper test."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str]] = []

    def enable_uma(
        self,
        hf_org: str,
        hf_token: str,
        aup_accepted_at: str,
    ) -> None:
        self.calls.append((hf_org, hf_token, aup_accepted_at))


class TestEnableUmaWithManifest:
    def test_unblocks_when_manifest_passes(self, tmp_path):
        path = _write_manifest(tmp_path, _valid_payload())
        adapter = _StubUmaAdapter()
        item = enable_uma_with_manifest(adapter, path, hf_token="hf_test1234")
        assert item.status == "pass"
        # Adapter was called with the manifest's hf_organization and AUP time.
        assert len(adapter.calls) == 1
        org, token, aup = adapter.calls[0]
        assert org == "zer0pa-research"
        assert token == "hf_test1234"

    def test_does_not_unblock_when_manifest_fails(self, tmp_path):
        # Tamper with hash to force a fail.
        payload = _valid_payload()
        payload["hf_organization"] = "tampered"
        path = _write_manifest(tmp_path, payload)
        adapter = _StubUmaAdapter()
        with pytest.raises(UmaManifestVerificationError):
            enable_uma_with_manifest(adapter, path, hf_token="hf_test1234")
        assert adapter.calls == []  # adapter never enabled

    def test_requires_hf_token(self, tmp_path):
        path = _write_manifest(tmp_path, _valid_payload())
        adapter = _StubUmaAdapter()
        with pytest.raises(ValueError, match="hf_token"):
            enable_uma_with_manifest(adapter, path, hf_token=None)
