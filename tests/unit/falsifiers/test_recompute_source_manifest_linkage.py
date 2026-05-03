"""Adversarial tests: source-manifest linkage (Wave D hardened gate 2).

Boundary
--------
Research infrastructure for in silico materials science discovery. Outputs are
research artifacts. No regulatory certification claims. No clinical or
human-subject use. ITAR / weapons applications are out of scope (Meta UMA
Acceptable Use Policy and operator policy).

Discipline
----------
The OLD audit-acceptance shape checks that ``audit.source_manifest_refs``
is a non-empty list of ``src:...`` strings. A buggy / malicious adapter
can populate that list with strings that LOOK valid but never wrote a
matching row in ``sources.jsonl``. The NEW
``verify_source_manifest_linkage`` walks each ref against the live audit
log and fails when any ref is unresolved.

We use an in-memory list of payloads (the helper accepts any iterable of
audit rows / payload dicts) so the test does not depend on filesystem
state.
"""

from __future__ import annotations

from zer0pa_materials_workbench.falsifiers.phase0_falsifiers import (
    verify_source_manifest_linkage,
)

# ---------------------------------------------------------------------------
# In-memory audit-log fixture
# ---------------------------------------------------------------------------


def _audit_with_sources(*sources: dict) -> dict[str, list]:
    """Return an in-memory audit-log shape consumable by iter_audit_rows.

    The helper supports either:
      * a real ``AuditLog`` instance, or
      * any iterable of payload dicts.

    For these tests we pass a list of dicts directly; the helper sees
    the dict shape and iterates it as plain ``Mapping`` rows.
    """
    return list(sources)


# ---------------------------------------------------------------------------
# Old shape (the simple "non-empty list" check we're replacing)
# ---------------------------------------------------------------------------


def _old_check_non_empty(envelope: dict) -> bool:
    """Mimics the original 'trust-the-field' acceptance check.

    Returns True when ``audit.source_manifest_refs`` is a non-empty
    list of strings — exactly what the original audit pipeline accepted
    before Wave D.
    """
    audit = envelope.get("audit") or {}
    refs = audit.get("source_manifest_refs") or []
    return bool(refs) and all(isinstance(r, str) for r in refs)


# ---------------------------------------------------------------------------
# Test 1: forged ref — name looks valid but never wrote a sources.jsonl row
# ---------------------------------------------------------------------------


class TestForgedSourceManifestRef:
    """Envelope claims ``src:fabricated:fake`` but no such row in the log."""

    def _envelope_with_forged_ref(self) -> dict:
        return {
            "layer": "L2",
            "audit": {
                "audit_record_id": "audit:run/X/L2",
                "input_hash": "sha256:" + "a" * 64,
                "output_hash": "sha256:" + "b" * 64,
                "source_manifest_refs": ["src:fabricated:fake"],
            },
        }

    def test_old_check_accepts_forged_envelope(self):
        env = self._envelope_with_forged_ref()
        assert _old_check_non_empty(env), (
            "old shape-only check must accept the forged ref; this is the "
            "weakness Wave D fixes"
        )

    def test_new_gate_fails_forged_envelope(self):
        env = self._envelope_with_forged_ref()
        # Audit log has nothing matching the ref.
        audit_log = _audit_with_sources()
        item = verify_source_manifest_linkage(env, audit_log)
        assert item.status == "fail"
        assert "src:fabricated:fake" in item.actual["unresolved"]

    def test_new_gate_passes_when_ref_actually_exists(self):
        env = self._envelope_with_forged_ref()
        # Now the audit log has the matching row.
        audit_log = _audit_with_sources(
            {
                "source_manifest_id": "src:fabricated:fake",
                "source_type": "paper",
                "locator": "doi:10.0000/test",
                "decision_impact": "L2 promote routing",
                "license_spdx": "CC-BY-4.0",
            }
        )
        item = verify_source_manifest_linkage(env, audit_log)
        assert item.status == "pass"


# ---------------------------------------------------------------------------
# Test 2: partial resolution — some refs valid, one fabricated
# ---------------------------------------------------------------------------


class TestPartialResolution:
    """Two refs claimed, one resolves and one is fabricated.

    Old check passes (both look like valid URNs). New gate must fail
    because at least one ref is unresolved.
    """

    def _envelope(self) -> dict:
        return {
            "layer": "L1",
            "audit": {
                "audit_record_id": "audit:run/Y/L1",
                "input_hash": "sha256:" + "c" * 64,
                "output_hash": "sha256:" + "d" * 64,
                "source_manifest_refs": [
                    "src:fixture:llzo-cubic",
                    "src:UNRESOLVED:also-fabricated",
                ],
            },
        }

    def test_old_check_accepts(self):
        assert _old_check_non_empty(self._envelope())

    def test_new_gate_lists_unresolved(self):
        env = self._envelope()
        audit_log = _audit_with_sources(
            {
                "source_manifest_id": "src:fixture:llzo-cubic",
                "source_type": "dataset",
                "decision_impact": "L1 DFT validation",
                "license_spdx": "MIT",
            }
        )
        item = verify_source_manifest_linkage(env, audit_log)
        assert item.status == "fail"
        assert "src:UNRESOLVED:also-fabricated" in item.actual["unresolved"]
        # The resolved ref should NOT appear in unresolved.
        assert "src:fixture:llzo-cubic" not in item.actual["unresolved"]


# ---------------------------------------------------------------------------
# Test 3: empty ref list — old check fails (already), new gate also fails
# ---------------------------------------------------------------------------


class TestEmptyRefList:
    def test_new_gate_fails_with_empty_refs(self):
        env = {
            "layer": "L2",
            "audit": {
                "audit_record_id": "audit:run/empty/L2",
                "input_hash": "sha256:" + "e" * 64,
                "output_hash": "sha256:" + "f" * 64,
                "source_manifest_refs": [],
            },
        }
        audit_log = _audit_with_sources()
        item = verify_source_manifest_linkage(env, audit_log)
        assert item.status == "fail"
        assert "no_refs_to_check" in str(item.actual.get("reason", ""))


# ---------------------------------------------------------------------------
# Test 4: AuditLog integration — uses the real append-only audit log
# ---------------------------------------------------------------------------


class TestAuditLogIntegration:
    """End-to-end: forged ref tested against a live AuditLog instance.

    Uses :class:`zer0pa_materials_workbench.audit.log.AuditLog` and the
    :class:`zer0pa_materials_workbench.audit.sources.SourceManifest` payload to
    write a real chained row. This proves the helper interoperates with
    production code, not just the test harness.
    """

    def test_with_real_audit_log(self, tmp_path):
        from zer0pa_materials_workbench.audit.log import AuditLog
        from zer0pa_materials_workbench.audit.sources import SourceManifest

        log = AuditLog(tmp_path / "audit_runtime")
        # Write the matching source manifest row.
        manifest = SourceManifest(
            source_manifest_id="src:real:registered",
            source_type="dataset",
            locator="https://example.org/data.json",
            retrieval_date="2026-04-30T01:00:00+00:00",
            license_spdx="CC-BY-4.0",
            summary="Wave D test fixture",
            decision_impact="L2 ensemble promotion",
        )
        log.append_event("sources", manifest.model_dump(mode="json"))

        env_real = {
            "layer": "L2",
            "audit": {
                "audit_record_id": "audit:run/Z/L2",
                "input_hash": "sha256:" + "1" * 64,
                "output_hash": "sha256:" + "2" * 64,
                "source_manifest_refs": ["src:real:registered"],
            },
        }
        env_forged = {
            "layer": "L2",
            "audit": {
                "audit_record_id": "audit:run/Z/L2-forged",
                "input_hash": "sha256:" + "3" * 64,
                "output_hash": "sha256:" + "4" * 64,
                "source_manifest_refs": ["src:not:in-the-log"],
            },
        }

        item_real = verify_source_manifest_linkage(env_real, log)
        item_forged = verify_source_manifest_linkage(env_forged, log)
        assert item_real.status == "pass"
        assert item_forged.status == "fail"
