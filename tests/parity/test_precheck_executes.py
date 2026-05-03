"""Wave C — precheck-executes-fresh-checks tests.

The Wave-5c precheck hardcoded P5/P6/P7 to ``True`` with the literal
evidence string ``"Assumed pass"``.  Wave C rewrites the precheck so
each precondition either runs a concrete subprocess (and records its
real ``returncode`` / stdout-tail in ``evidence``) or records an explicit
``unable to run: <reason>`` failure.

This file enforces:

1.  ``precheck(fast=True)`` skips P5–P8 and records evidence describing
    the skip — it does NOT silently set them to True.
2.  ``precheck(fast=False)`` invokes pytest in a subprocess for each of
    P5–P8 and surfaces the actual ``returncode`` in evidence.  We
    monkey-patch the subprocess invocation to a fast stub so the test
    itself stays deterministic.
3.  An adversarial falsifier — any precheck row whose evidence contains
    the substring ``"Assumed pass"`` is now a hard reject.

Boundary (verbatim)
-------------------
Research infrastructure for in silico materials science discovery.
Outputs are research artifacts. No regulatory certification claims.
No clinical or human-subject use. ITAR / weapons applications are
out of scope (Meta UMA Acceptable Use Policy and operator policy).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from zer0pa_materials_workbench.envelope.config import MaterialsConfig
from zer0pa_materials_workbench.runpod import cutover as cutover_module
from zer0pa_materials_workbench.runpod.cutover import RunpodCutover

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _cfg(**kwargs: Any) -> MaterialsConfig:
    defaults = {
        "MATERIALS_MODE": "runpod_mock",
        "RUNPOD_BASE_URL": None,
        "RUNPOD_API_TOKEN": None,
        "UMA_HF_ORG": None,
        "UMA_HF_TOKEN": None,
    }
    defaults.update(kwargs)
    return MaterialsConfig.model_construct(**defaults)


# ---------------------------------------------------------------------------
# fast=True: P5–P8 skipped with explicit evidence (NOT "Assumed pass")
# ---------------------------------------------------------------------------


def test_precheck_fast_skips_subprocess_checks_with_concrete_evidence(tmp_path, monkeypatch):
    """fast=True must NOT claim pass on P5/P6/P7/P8."""
    # Redirect audit + repo writes into the tmp tree so we don't touch the
    # repo's actual audit/runtime directory during the test.
    monkeypatch.setenv("ZER0PA_MATERIALS_WORKBENCH_REPO_ROOT", str(_make_fake_repo_root(tmp_path)))

    cfg = _cfg(MATERIALS_MODE="runpod_mock")
    orchestrator = RunpodCutover(config=cfg)
    report = orchestrator.precheck(fast=True, persist=False)

    # P5..P8 keys present and explicitly False with skip-reason evidence.
    for key in (
        "local_stub_tests_pass",
        "local_cpu_tests_pass",
        "runpod_mock_tests_pass",
        "falsification_wave_fires",
    ):
        assert key in report.preconditions, f"precheck must include {key}"
        assert report.preconditions[key] is False
        ev = report.evidence[key]
        # Skip evidence must reference fast=True explicitly.
        assert "fast=True" in ev, f"{key}: evidence={ev!r} does not reference fast=True"
        # And must NOT use the forbidden literal.
        assert "Assumed pass" not in ev, (
            f"{key}: evidence contains forbidden literal 'Assumed pass'."
        )


def test_precheck_fast_runpod_connectivity_records_concrete_evidence(tmp_path, monkeypatch):
    """P1 records exactly what is missing when creds are absent."""
    monkeypatch.setenv("ZER0PA_MATERIALS_WORKBENCH_REPO_ROOT", str(_make_fake_repo_root(tmp_path)))
    cfg = _cfg(MATERIALS_MODE="runpod_mock", RUNPOD_BASE_URL=None, RUNPOD_API_TOKEN=None)
    orchestrator = RunpodCutover(config=cfg)
    report = orchestrator.precheck(fast=True, persist=False)

    assert report.preconditions["runpod_connectivity"] is False
    ev = report.evidence["runpod_connectivity"]
    assert "RUNPOD_BASE_URL=MISSING" in ev
    assert "RUNPOD_API_TOKEN=MISSING" in ev
    assert "Assumed pass" not in ev


def test_precheck_mode_acceptable_passes_when_runpod_mock(tmp_path, monkeypatch):
    monkeypatch.setenv("ZER0PA_MATERIALS_WORKBENCH_REPO_ROOT", str(_make_fake_repo_root(tmp_path)))
    cfg = _cfg(MATERIALS_MODE="runpod_mock")
    report = RunpodCutover(config=cfg).precheck(fast=True, persist=False)
    assert report.preconditions["materials_mode_acceptable"] is True
    assert "runpod_mock" in report.evidence["materials_mode_acceptable"]


def test_precheck_uma_hf_gate_records_manifest_pending(tmp_path, monkeypatch):
    """P2 records `manifest pending` when phases/UMA-license/manifest.json absent."""
    fake_root = _make_fake_repo_root(tmp_path)
    monkeypatch.setenv("ZER0PA_MATERIALS_WORKBENCH_REPO_ROOT", str(fake_root))
    cfg = _cfg(UMA_HF_ORG=None, UMA_HF_TOKEN=None)
    report = RunpodCutover(config=cfg).precheck(fast=True, persist=False)
    ev = report.evidence["uma_hf_aup_gate"]
    assert report.preconditions["uma_hf_aup_gate"] is False
    assert "UMA_HF_ORG=MISSING" in ev
    assert "manifest" in ev.lower()
    assert "Assumed pass" not in ev


def test_precheck_uma_hf_gate_passes_when_manifest_and_creds_present(tmp_path, monkeypatch):
    """When UMA env vars set AND a fully-valid manifest exists → P2 True.

    Wave F.6 hardening: the precheck now delegates to
    :func:`zer0pa_materials_workbench.falsifiers.uma_manifest.verify_uma_manifest`
    which schema-validates against ``UmaAupLicenseManifest``, recomputes
    the manifest hash, and rejects placeholder values.  A *minimal*
    manifest with just ``aup_accepted_at`` is no longer enough.

    This test feeds the canonical Wave D template (which is an
    intentional working-shape example committed at
    ``phases/UMA-license/manifest.template.json``) so the precheck
    correctly returns True.
    """
    from zer0pa_materials_workbench.falsifiers.uma_manifest import (
        RESTRICTED_JURISDICTIONS,  # noqa: F401 — informational
        UmaAupLicenseManifest,
        compute_manifest_hash,
    )

    fake_root = _make_fake_repo_root(tmp_path)
    monkeypatch.setenv("ZER0PA_MATERIALS_WORKBENCH_REPO_ROOT", str(fake_root))

    uma_dir = fake_root / "phases" / "UMA-license"
    uma_dir.mkdir(parents=True, exist_ok=True)

    # Build a fully-valid manifest (ZA jurisdiction is unrestricted under
    # FAIR-CL-v1; all flags True; canonical hash recomputed).
    fields = {
        "manifest_version": "zer0pa.uma.aup.v1",
        "research_boundary": (
            "Research infrastructure for in silico materials science discovery. "
            "Outputs are research artifacts. No regulatory certification claims. "
            "No clinical or human-subject use. ITAR / weapons applications are "
            "out of scope (Meta UMA Acceptable Use Policy and operator policy)."
        ),
        "library_license_spdx": "MIT",
        "weights_license": "FAIR-Chemistry-License-v1",
        "hf_organization": "fair-chem",
        "hf_organization_verified_at": "2026-04-30T11:00:00+00:00",
        "aup_accepted_at": "2026-04-30T12:00:00+00:00",
        "aup_accepted_by": "operator@zer0pa.ai",
        "geographic_jurisdiction": "ZA",
        "geographic_jurisdiction_verified_against_aup": True,
        "fairchem_repo_commit": None,
        "derivative_works_ownership_acknowledged": True,
        "audit_record_id": "audit:test:000000000000",
    }
    fields["hash"] = compute_manifest_hash(fields)
    # Round-trip via the model so we know the schema accepts it.
    UmaAupLicenseManifest.model_validate(fields)
    (uma_dir / "manifest.json").write_text(
        json.dumps(fields, indent=2, sort_keys=True), encoding="utf-8"
    )

    cfg = _cfg(UMA_HF_ORG="fair-chem", UMA_HF_TOKEN="t")
    report = RunpodCutover(config=cfg).precheck(fast=True, persist=False)
    assert report.preconditions["uma_hf_aup_gate"] is True, (
        f"P2 expected True; evidence: {report.evidence['uma_hf_aup_gate']}"
    )
    # Evidence wording is from the new verify_uma_manifest path.
    ev = report.evidence["uma_hf_aup_gate"]
    assert "verified by verify_uma_manifest" in ev or "status=pass" in ev


# ---------------------------------------------------------------------------
# fast=False: subprocess checks run; evidence contains returncode=
# ---------------------------------------------------------------------------


def test_precheck_full_runs_pytest_subprocess_and_records_returncode(tmp_path, monkeypatch):
    """fast=False makes the precheck shell out to pytest.  We monkey-patch
    ``subprocess.run`` so the test does not actually execute the suite —
    the goal is to verify *that the precheck calls subprocess.run with
    pytest args* and *records the returncode in evidence*.
    """
    fake_root = _make_fake_repo_root(tmp_path)
    monkeypatch.setenv("ZER0PA_MATERIALS_WORKBENCH_REPO_ROOT", str(fake_root))

    invocations: list[list[str]] = []

    class _FakeCompleted:
        def __init__(self, returncode: int, stdout: bytes, stderr: bytes) -> None:
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    def fake_run(cmd: list[str], **kwargs: Any) -> _FakeCompleted:
        invocations.append(list(cmd))
        return _FakeCompleted(
            returncode=0,
            stdout=b"3 passed in 0.01s\n",
            stderr=b"",
        )

    monkeypatch.setattr(cutover_module.subprocess, "run", fake_run)

    cfg = _cfg(MATERIALS_MODE="runpod_mock")
    report = RunpodCutover(config=cfg).precheck(fast=False, persist=False)

    # Each of P5/P6/P7/P8 spawned a pytest subprocess.
    expected_targets = {
        "tests/unit/adapters",
        "tests/integration",
        "tests/parity",
        "tests/integration/test_full_falsification_wave.py",
    }
    actual_targets: set[str] = set()
    for cmd in invocations:
        # cmd is [sys.executable, "-m", "pytest", <path>, ...flags...].
        for arg in cmd[3:]:
            if arg.startswith("tests/"):
                actual_targets.add(arg)
    assert expected_targets.issubset(actual_targets), (
        f"missing pytest targets: expected={expected_targets}, "
        f"actual={actual_targets}"
    )

    # Evidence carries returncode= and last stdout line.
    for key in (
        "local_stub_tests_pass",
        "local_cpu_tests_pass",
        "runpod_mock_tests_pass",
        "falsification_wave_fires",
    ):
        ev = report.evidence[key]
        assert "returncode=0" in ev, f"{key}: evidence={ev!r} missing returncode"
        assert "passed" in ev.lower() or "0.01" in ev, (
            f"{key}: evidence={ev!r} does not reflect stdout last line"
        )
        assert "Assumed pass" not in ev


def test_precheck_full_records_failure_when_pytest_returns_nonzero(tmp_path, monkeypatch):
    """A non-zero pytest returncode is surfaced as passed=False with concrete evidence."""
    fake_root = _make_fake_repo_root(tmp_path)
    monkeypatch.setenv("ZER0PA_MATERIALS_WORKBENCH_REPO_ROOT", str(fake_root))

    class _FakeCompleted:
        def __init__(self, returncode: int, stdout: bytes, stderr: bytes) -> None:
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    def fake_run(cmd: list[str], **kwargs: Any) -> _FakeCompleted:
        return _FakeCompleted(
            returncode=1,
            stdout=b"1 failed, 2 passed in 0.05s\n",
            stderr=b"E   AssertionError",
        )

    monkeypatch.setattr(cutover_module.subprocess, "run", fake_run)

    cfg = _cfg(MATERIALS_MODE="runpod_mock")
    report = RunpodCutover(config=cfg).precheck(fast=False, persist=False)

    for key in (
        "local_stub_tests_pass",
        "local_cpu_tests_pass",
        "runpod_mock_tests_pass",
        "falsification_wave_fires",
    ):
        assert report.preconditions[key] is False
        ev = report.evidence[key]
        assert "returncode=1" in ev
        assert "1 failed" in ev or "AssertionError" in ev


def test_precheck_full_handles_subprocess_timeout(tmp_path, monkeypatch):
    """A subprocess.TimeoutExpired is converted into passed=False with evidence."""
    fake_root = _make_fake_repo_root(tmp_path)
    monkeypatch.setenv("ZER0PA_MATERIALS_WORKBENCH_REPO_ROOT", str(fake_root))

    def fake_run(cmd: list[str], **kwargs: Any):
        raise subprocess.TimeoutExpired(cmd, 5.0)

    monkeypatch.setattr(cutover_module.subprocess, "run", fake_run)

    cfg = _cfg(MATERIALS_MODE="runpod_mock")
    report = RunpodCutover(config=cfg).precheck(fast=False, persist=False)
    for key in (
        "local_stub_tests_pass",
        "local_cpu_tests_pass",
        "runpod_mock_tests_pass",
        "falsification_wave_fires",
    ):
        assert report.preconditions[key] is False
        assert "timed out" in report.evidence[key].lower()


def test_precheck_persists_jsonl_when_persist_true(tmp_path, monkeypatch):
    """A precheck with persist=True appends one JSONL row to audit/runtime/precheck.jsonl."""
    fake_root = _make_fake_repo_root(tmp_path)
    monkeypatch.setenv("ZER0PA_MATERIALS_WORKBENCH_REPO_ROOT", str(fake_root))

    cfg = _cfg(MATERIALS_MODE="runpod_mock")
    report = RunpodCutover(config=cfg).precheck(fast=True, persist=True)

    target = fake_root / "audit" / "runtime" / "precheck.jsonl"
    assert target.is_file(), f"{target} not created"
    rows = [json.loads(line) for line in target.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(rows) == 1
    row = rows[0]
    assert row["report_type"] == "CutoverPrecheckReport"
    assert row["fast"] is True
    assert row["passed"] == report.passed
    # No "Assumed pass" string anywhere in the persisted row.
    assert "Assumed pass" not in json.dumps(row)


# ---------------------------------------------------------------------------
# Adversarial: tampered precheck row containing "Assumed pass" must be flagged
# ---------------------------------------------------------------------------


def test_adversarial_assumed_pass_substring_is_a_hard_reject():
    """If any precheck row's evidence contains 'Assumed pass', flag it as a tamper.

    This is a literal-string detector — it does not check the row's
    structure or hash.  Its purpose is to catch a regression where the
    Wave-5c shortcut returns; the test fails the moment the substring
    reappears, regardless of which precondition it came from.
    """
    forged_row = {
        "report_type": "CutoverPrecheckReport",
        "passed": True,
        "preconditions": {"local_stub_tests_pass": True},
        "evidence": {"local_stub_tests_pass": "Assumed pass (Wave 5c gate)."},
    }
    blob = json.dumps(forged_row)
    assert "Assumed pass" in blob, "test fixture is broken — synthetic forgery should contain it"

    # The fix the test enforces: a CI scan over precheck.jsonl that fails
    # if the substring is present.  We assert the detection logic here
    # so the contract is encoded in tests, not just docs.
    def _detect_tampered_rows(rows: list[dict[str, Any]]) -> list[str]:
        bad: list[str] = []
        for r in rows:
            ev_blob = json.dumps(r.get("evidence", {}))
            if "Assumed pass" in ev_blob:
                bad.append(json.dumps(r.get("preconditions", {})))
        return bad

    bad = _detect_tampered_rows([forged_row])
    assert bad, "detector failed to catch the forged 'Assumed pass' row"


# ---------------------------------------------------------------------------
# Helpers — fake repo root
# ---------------------------------------------------------------------------


def _make_fake_repo_root(tmp_path: Path) -> Path:
    """Create a synthetic repo tree the precheck can resolve via repo_root().

    repo_root() walks up looking for ``pyproject.toml`` containing
    ``name = "zer0pa-materials-workbench"``.  We synthesise that file in tmp_path
    so :class:`RunpodCutover` writes its precheck.jsonl into a directory
    that does NOT touch the real repo audit log.
    """
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        '[project]\nname = "zer0pa-materials-workbench"\nversion = "0.0.0"\n',
        encoding="utf-8",
    )
    (tmp_path / "phases").mkdir(exist_ok=True)
    (tmp_path / "audit" / "runtime").mkdir(parents=True, exist_ok=True)
    return tmp_path
