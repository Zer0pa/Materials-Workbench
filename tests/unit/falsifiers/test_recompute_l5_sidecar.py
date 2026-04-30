"""Adversarial tests: L5 artifact sidecar verification (Wave D hardened gate 6).

Boundary
--------
Research infrastructure for in silico materials science discovery. Outputs are
research artifacts. No regulatory certification claims. No clinical or
human-subject use. ITAR / weapons applications are out of scope (Meta UMA
Acceptable Use Policy and operator policy).

Discipline
----------
The OLD ``artifact_units_sidecar_present`` checks the envelope's
``_artifact_sidecars`` list — it accepts any dict with non-empty
``units`` and ``sha256`` fields. A buggy / malicious adapter can paint
those fields without writing the artifact to disk. The new
``verify_l5_artifact_sidecar``:

1. Resolves each artifact's URI to disk (under ``repo_root()``).
2. Reads the bytes and recomputes ``sha256:<hex>``.
3. Compares the recompute to the sidecar's claim.
4. Verifies a ``<artifact>.units.json`` sidecar file exists on disk
   alongside the artifact, with the correct units keys and matching
   recorded hash.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from zer0pa_materials.falsifiers.l5_falsifiers import (
    artifact_units_sidecar_present,
    verify_l5_artifact_sidecar,
)


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _write_artifact_with_sidecar(
    tmp_path: Path,
    name: str,
    bytes_content: bytes,
    units: dict[str, str],
) -> tuple[Path, str]:
    """Write a real artifact + units sidecar JSON.

    Returns ``(artifact_path, sha256_hex)``.
    """
    artifact_path = tmp_path / name
    artifact_path.write_bytes(bytes_content)
    sha = "sha256:" + hashlib.sha256(bytes_content).hexdigest()
    sidecar = {"units": units, "hash": sha}
    sidecar_path = artifact_path.with_suffix(artifact_path.suffix + ".units.json")
    sidecar_path.write_text(json.dumps(sidecar))
    return artifact_path, sha


def _envelope_with_sidecars(*sidecar_dicts: dict) -> dict:
    return {
        "layer": "L5",
        "output": {
            "elastic_patch_residual": 1e-12,
        },
        "_artifact_sidecars": list(sidecar_dicts),
    }


# ---------------------------------------------------------------------------
# Test 1: forged sidecar — claims an artifact that does not exist on disk
# ---------------------------------------------------------------------------


class TestArtifactFileMissing:
    def test_old_gate_passes_forged_sidecar(self, tmp_path):
        # Old gate: just looks at the dict shape.
        env = _envelope_with_sidecars(
            {
                "format": "vtk",
                "uri": str(tmp_path / "nonexistent.vtk"),
                "sha256": "sha256:" + "a" * 64,  # made up
                "units": {"temperature": "K"},
            }
        )
        old = artifact_units_sidecar_present(env)
        assert old.status == "pass", (
            "old gate accepts the forged sidecar; this is the weakness "
            "Wave D fixes"
        )

    def test_new_gate_fails_when_artifact_missing(self, tmp_path):
        env = _envelope_with_sidecars(
            {
                "format": "vtk",
                "uri": str(tmp_path / "nonexistent.vtk"),
                "sha256": "sha256:" + "a" * 64,
                "units": {"temperature": "K"},
            }
        )
        new = verify_l5_artifact_sidecar(env)
        assert new.status == "fail"
        failures = new.actual["failures"]
        assert any(f["reason"] == "artifact_file_missing" for f in failures)


# ---------------------------------------------------------------------------
# Test 2: forged hash — artifact exists but recorded sha doesn't match
# ---------------------------------------------------------------------------


class TestForgedSha256:
    def test_new_gate_fails_when_recorded_sha_mismatches(self, tmp_path):
        artifact_path = tmp_path / "real.vtk"
        artifact_path.write_bytes(b"# vtk DataFile Version 4.0\n")
        # Sidecar JSON is also written so we isolate the sha mismatch
        # check.
        true_sha = "sha256:" + hashlib.sha256(artifact_path.read_bytes()).hexdigest()
        sidecar_path = artifact_path.with_suffix(".vtk.units.json")
        sidecar_path.write_text(json.dumps({"units": {"x": "m"}, "hash": true_sha}))

        env = _envelope_with_sidecars(
            {
                "format": "vtk",
                "uri": str(artifact_path),
                "sha256": "sha256:" + "0" * 64,  # forged
                "units": {"x": "m"},
            }
        )
        old = artifact_units_sidecar_present(env)
        # Old gate sees the populated dict and passes.
        assert old.status == "pass"

        new = verify_l5_artifact_sidecar(env)
        assert new.status == "fail"
        failures = new.actual["failures"]
        assert any(f["reason"] == "recomputed_hash_mismatch" for f in failures)


# ---------------------------------------------------------------------------
# Test 3: missing sidecar JSON file
# ---------------------------------------------------------------------------


class TestMissingSidecarFile:
    def test_new_gate_fails_when_sidecar_file_missing(self, tmp_path):
        artifact_path = tmp_path / "real.vtk"
        artifact_path.write_bytes(b"# vtk DataFile Version 4.0\n")
        true_sha = "sha256:" + hashlib.sha256(artifact_path.read_bytes()).hexdigest()
        # No sidecar JSON written.

        env = _envelope_with_sidecars(
            {
                "format": "vtk",
                "uri": str(artifact_path),
                "sha256": true_sha,
                "units": {"x": "m"},
            }
        )
        new = verify_l5_artifact_sidecar(env)
        assert new.status == "fail"
        failures = new.actual["failures"]
        assert any(f["reason"] == "units_sidecar_file_missing" for f in failures)


# ---------------------------------------------------------------------------
# Test 4: sidecar exists but its recorded hash does not match
# ---------------------------------------------------------------------------


class TestSidecarHashMismatch:
    def test_new_gate_fails_on_sidecar_hash_mismatch(self, tmp_path):
        artifact_path = tmp_path / "real.vtk"
        artifact_path.write_bytes(b"# vtk DataFile Version 4.0\n")
        true_sha = "sha256:" + hashlib.sha256(artifact_path.read_bytes()).hexdigest()
        # The sidecar's recorded hash doesn't match the bytes.
        sidecar_path = artifact_path.with_suffix(".vtk.units.json")
        sidecar_path.write_text(
            json.dumps({"units": {"x": "m"}, "hash": "sha256:" + "9" * 64})
        )
        env = _envelope_with_sidecars(
            {
                "format": "vtk",
                "uri": str(artifact_path),
                # Envelope's sha256 is correct so we hit the sidecar
                # hash check, not the envelope-vs-bytes check.
                "sha256": true_sha,
                "units": {"x": "m"},
            }
        )
        new = verify_l5_artifact_sidecar(env)
        assert new.status == "fail"
        failures = new.actual["failures"]
        assert any(f["reason"] == "sidecar_hash_mismatch" for f in failures)


# ---------------------------------------------------------------------------
# Test 5: clean envelope — artifact + sidecar consistent on disk
# ---------------------------------------------------------------------------


class TestCleanArtifactPasses:
    def test_consistent_artifact_and_sidecar_pass(self, tmp_path):
        artifact_path, sha = _write_artifact_with_sidecar(
            tmp_path,
            "clean.vtk",
            b"# vtk DataFile Version 4.0\n",
            units={"temperature": "K", "stress": "Pa"},
        )
        env = _envelope_with_sidecars(
            {
                "format": "vtk",
                "uri": str(artifact_path),
                "sha256": sha,
                "units": {"temperature": "K", "stress": "Pa"},
            }
        )
        new = verify_l5_artifact_sidecar(env)
        assert new.status == "pass"
        assert len(new.actual["verified"]) == 1


# ---------------------------------------------------------------------------
# Test 6: no artifacts emitted — vacuous pass
# ---------------------------------------------------------------------------


class TestNoArtifactsVacuousPass:
    def test_empty_artifacts_pass(self):
        env = {"layer": "L5", "output": {}, "_artifact_sidecars": []}
        new = verify_l5_artifact_sidecar(env)
        assert new.status == "pass"
