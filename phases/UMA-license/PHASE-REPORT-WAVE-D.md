# Phase report — UMA AUP / FAIR Chemistry License manifest (Wave D)

## Boundary (verbatim)

Research infrastructure for in silico materials science discovery. Outputs are research artifacts. No regulatory certification claims. No clinical or human-subject use. ITAR / weapons applications are out of scope (Meta UMA Acceptable Use Policy and operator policy).

## Scope

This phase delivers the verifiable record layer for Meta UMA enablement. Wave 3A.3 confirmed the load-bearing license facts (fairchem library = MIT; UMA weights = FAIR Chemistry License v1; geographic = ZA unrestricted; AUP = no military / weapons / ITAR; output ownership = operator). The existing `UmaCalculatorAdapter.enable_uma` call is necessary but not sufficient: it leaves no committed, verifiable artifact on disk. Wave D adds the missing artifact and the verification falsifier.

## Deliverables

| Artifact | Path | Purpose |
|---|---|---|
| Schema + falsifier + wrapper | `src/zer0pa_materials/falsifiers/uma_manifest.py` | `UmaAupLicenseManifest` Pydantic model, `verify_uma_manifest`, `enable_uma_with_manifest` wrapper |
| Starter manifest | `phases/UMA-license/manifest.json` | Operator-fillable; INTENTIONALLY rejects until filled. |
| Template manifest | `phases/UMA-license/manifest.template.json` | Safe defaults (ZA jurisdiction, ownership ack, valid timestamps). The operator copies this and fills the placeholder fields. |
| Tests | `tests/unit/falsifiers/test_uma_manifest.py` | 22 tests covering schema, hash recompute, restricted jurisdictions, future timestamps, ownership, repo-committed manifests, wrapper behaviour. |

## Schema

```python
class UmaAupLicenseManifest(BaseModel):
    manifest_version: Literal["zer0pa.uma.aup.v1"]
    research_boundary: str             # verbatim RESEARCH_BOUNDARY
    library_license_spdx: Literal["MIT"]
    weights_license: Literal["FAIR-Chemistry-License-v1"]
    hf_organization: str
    hf_organization_verified_at: datetime
    aup_accepted_at: datetime
    aup_accepted_by: str
    geographic_jurisdiction: str       # ISO 3166-1 alpha-2; default "ZA"
    geographic_jurisdiction_verified_against_aup: bool
    fairchem_repo_commit: str | None
    derivative_works_ownership_acknowledged: bool
    audit_record_id: str               # links to sources.jsonl
    hash: str                          # sha256 of manifest minus 'hash'
```

## Hash contract

`hash` = `sha256_of(canonical_json(manifest_payload - {"hash"}))`. Tampering with any field breaks the recompute. The verifier always reads the file fresh and recomputes; a stored hash is never trusted.

## Restricted jurisdictions

`RESTRICTED_JURISDICTIONS = frozenset({"CN", "RU", "BY", "IR", "KP", "SY", "CU"})`. Per FAIR Chemistry License v1: China, Russia, Belarus, plus the named OFAC-sanctioned countries in the spec snapshot. South Africa (`"ZA"`) is unrestricted. The verifier rejects any manifest with a restricted jurisdiction regardless of the `verified` flag. For non-restricted jurisdictions, `geographic_jurisdiction_verified_against_aup` MUST be True.

## Verification path

```python
from zer0pa_materials.falsifiers.uma_manifest import (
    enable_uma_with_manifest, verify_uma_manifest
)
from zer0pa_materials.adapters.l2.uma import UmaCalculatorAdapter

adapter = UmaCalculatorAdapter()
# Refuses to unblock unless manifest verifies
enable_uma_with_manifest(
    adapter,
    "phases/UMA-license/manifest.json",
    hf_token="hf_...",
)
```

## Falsifier results

`verify_uma_manifest(manifest_path)` returns a `FalsifierItem`:

* `status="pass"` — file exists, schema validates, hash recomputes, jurisdiction allowed, ownership acknowledged, timestamps in the past.
* `status="fail"` — any invariant violated, with `rationale` set.
* `status="blocked"` — file unreadable.

## Operator workflow

1. Copy `phases/UMA-license/manifest.template.json` to `phases/UMA-license/manifest.json`.
2. Replace the `TEMPLATE-REPLACE-WITH-*` placeholders with real values.
3. Recompute the hash:
   ```python
   from zer0pa_materials.falsifiers.uma_manifest import compute_manifest_hash
   payload["hash"] = compute_manifest_hash(payload)
   ```
4. Validate:
   ```python
   from zer0pa_materials.falsifiers.uma_manifest import verify_uma_manifest
   item = verify_uma_manifest("phases/UMA-license/manifest.json")
   assert item.status == "pass"
   ```
5. Enable the adapter via the wrapper. The adapter MUST NOT be unblocked any other way.

## Verification results

* 22/22 manifest tests pass (`tests/unit/falsifiers/test_uma_manifest.py`).
* Starter manifest (`manifest.json`) verifies as `fail` (intentional — placeholder ownership and verified flags).
* Template manifest (`manifest.template.json`) verifies as `pass` (safe-defaults proof point).

## Cross-wave integration

The schema's `audit_record_id` field is intended to point at a `sources.jsonl` row written when the manifest is finalised. That row's `decision_impact` should reference the L2 ensemble's UMA usage. Operators wiring a real run should:

1. Append a `SourceManifest` row recording the manifest's path and sha256.
2. Use the row's `event_hash` to populate `audit_record_id` in the manifest.
3. Recompute the manifest's `hash` after that field is filled.
4. Persist.

This was kept manual (one-off operator action) rather than baked into the wrapper so the audit-trail discipline stays explicit.
