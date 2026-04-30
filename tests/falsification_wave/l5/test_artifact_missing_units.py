"""Falsification wave: artifact missing units sidecar.

PRD §L5 Falsifiers: "VTK/Exodus/FMI artifacts must include units sidecars
and hashes."

This test verifies that a synthetic L5 envelope carrying a VTK artifact
WITHOUT a units sidecar triggers ``artifact_units_sidecar_present`` → fail.
"""

from __future__ import annotations

import pytest

from zer0pa_materials.falsifiers.l5_falsifiers import (
    artifact_units_sidecar_present,
    analytic_heat_slab_error,
    elastic_patch_residual,
    openfoam_poiseuille_profile_error,
    cfd_mass_balance_error,
    cfd_heat_balance_error,
    tensor_spd_check,
)
from zer0pa_materials.boundary import RESEARCH_BOUNDARY


# ---------------------------------------------------------------------------
# Synthetic envelopes
# ---------------------------------------------------------------------------

def _base_output() -> dict:
    """L5 output with all non-artifact gates passing."""
    return {
        "tensors": [
            {"name": "stiffness_C_3x3", "spd": True, "eigvals_min": 50.0}
        ],
        "analytic_heat_slab_error": 1e-12,
        "elastic_patch_residual": 1e-15,
        "fenicsx_vs_dealii_strain_energy_disagreement_pct": 0.5,
        "openfoam_poiseuille_error_pct": 0.001,
        "cfd_mass_balance_error": 1e-12,
        "cfd_heat_balance_error": 1e-12,
        "artifact_uris": [],
    }


def _make_envelope(output: dict, artifact_sidecars=None) -> dict:
    env = {
        "research_boundary": RESEARCH_BOUNDARY,
        "contract_version": "zer0pa.materials.layer-envelope.v1",
        "layer": "L5",
        "run_id": "run:falsification/l5/missing_units",
        "candidate_id": "candidate:missing_units",
        "campaign_id": "campaign:falsification/001",
        "tool_adapter": {
            "name": "FalsificationStub",
            "version": "0.0.1",
            "backend": "stub",
            "engine": "test",
        },
        "output": output,
        "confidence": {"score": 0.5, "band": "medium", "basis": ["test"]},
        "disagreement": {"metrics": []},
        "falsifier": {"status": "pass", "items": []},
        "audit": {
            "audit_record_id": "audit:test/missing_units",
            "input_hash": "sha256:" + "a" * 64,
            "output_hash": "sha256:" + "b" * 64,
            "source_manifest_refs": [],
        },
        "rights": {
            "rights_claim_id": "rights:falsification/001",
            "reuse_scope": "tenant_only",
        },
        "back_edges": [],
    }
    if artifact_sidecars is not None:
        env["_artifact_sidecars"] = artifact_sidecars
    return env


# ---------------------------------------------------------------------------
# VTK artifact missing units — should fail
# ---------------------------------------------------------------------------

class TestVTKMissingUnits:
    """VTK artifact without units sidecar must trigger the falsifier."""

    @pytest.fixture
    def env_vtk_no_units(self):
        artifact = {
            "format": "vtk",
            "run_id": "run:test/001",
            "data": {"velocity": [1.0, 0.0, 0.0]},
            # No "units" key — deliberate violation
            "sha256": "sha256:" + "a" * 64,
        }
        return _make_envelope(_base_output(), artifact_sidecars=[artifact])

    def test_sidecar_check_fails(self, env_vtk_no_units):
        item = artifact_units_sidecar_present(env_vtk_no_units)
        assert item.status == "fail", (
            f"Expected 'fail' but got {item.status!r}"
        )

    def test_failure_mentions_vtk_missing_units(self, env_vtk_no_units):
        item = artifact_units_sidecar_present(env_vtk_no_units)
        assert "vtk:missing_units" in item.actual["failures"]


# ---------------------------------------------------------------------------
# VTK artifact missing hash — should fail
# ---------------------------------------------------------------------------

class TestVTKMissingHash:
    @pytest.fixture
    def env_vtk_no_hash(self):
        artifact = {
            "format": "vtk",
            "run_id": "run:test/001",
            "data": {"velocity": [1.0]},
            "units": {"velocity_unit": "m/s"},
            # No "sha256" key — deliberate violation
        }
        return _make_envelope(_base_output(), artifact_sidecars=[artifact])

    def test_sidecar_check_fails(self, env_vtk_no_hash):
        item = artifact_units_sidecar_present(env_vtk_no_hash)
        assert item.status == "fail"

    def test_failure_mentions_missing_sha256(self, env_vtk_no_hash):
        item = artifact_units_sidecar_present(env_vtk_no_hash)
        assert "vtk:missing_sha256" in item.actual["failures"]


# ---------------------------------------------------------------------------
# Exodus artifact missing units — should fail
# ---------------------------------------------------------------------------

class TestExodusMissingUnits:
    @pytest.fixture
    def env_exodus_no_units(self):
        artifact = {
            "format": "exodus",
            "run_id": "run:test/001",
            "mesh_data": {"nodes": 4},
            # No "units" key — deliberate violation
            "sha256": "sha256:" + "a" * 64,
        }
        return _make_envelope(_base_output(), artifact_sidecars=[artifact])

    def test_sidecar_check_fails(self, env_exodus_no_units):
        item = artifact_units_sidecar_present(env_exodus_no_units)
        assert item.status == "fail"

    def test_failure_mentions_exodus_missing_units(self, env_exodus_no_units):
        item = artifact_units_sidecar_present(env_exodus_no_units)
        assert "exodus:missing_units" in item.actual["failures"]


# ---------------------------------------------------------------------------
# FMI artifact missing units — should fail
# ---------------------------------------------------------------------------

class TestFMIMissingUnits:
    @pytest.fixture
    def env_fmi_no_units(self):
        artifact = {
            "format": "fmi",
            "run_id": "run:test/001",
            "model_description": {"modelName": "PipeFlow"},
            # No "units" key — deliberate violation
            "sha256": "sha256:" + "a" * 64,
        }
        return _make_envelope(_base_output(), artifact_sidecars=[artifact])

    def test_sidecar_check_fails(self, env_fmi_no_units):
        item = artifact_units_sidecar_present(env_fmi_no_units)
        assert item.status == "fail"


# ---------------------------------------------------------------------------
# Valid artifact — should pass
# ---------------------------------------------------------------------------

class TestValidArtifact:
    @pytest.fixture
    def env_vtk_valid(self):
        artifact = {
            "format": "vtk",
            "run_id": "run:test/001",
            "data": {"velocity": [1.0, 0.0, 0.0]},
            "units": {"velocity_unit": "m/s", "stress_unit": "GPa"},
            "sha256": "sha256:" + "a" * 64,
        }
        return _make_envelope(_base_output(), artifact_sidecars=[artifact])

    def test_sidecar_check_passes(self, env_vtk_valid):
        item = artifact_units_sidecar_present(env_vtk_valid)
        assert item.status == "pass"

    def test_n_artifacts_counted(self, env_vtk_valid):
        item = artifact_units_sidecar_present(env_vtk_valid)
        assert item.actual["n_artifacts"] == 1


# ---------------------------------------------------------------------------
# EXACTLY one gate fires on missing-units envelope
# ---------------------------------------------------------------------------

class TestOnlyArtifactGateFires:
    """When only the units sidecar is missing, only that gate must fail.

    All other L5 gates must pass (base_output has passing values).
    """

    @pytest.fixture
    def env_only_units_missing(self):
        artifact = {"format": "vtk", "sha256": "sha256:" + "a" * 64, "data": {}}
        return _make_envelope(_base_output(), artifact_sidecars=[artifact])

    def test_only_sidecar_fails(self, env_only_units_missing):
        item = artifact_units_sidecar_present(env_only_units_missing)
        assert item.status == "fail"

    def test_heat_slab_passes(self, env_only_units_missing):
        item = analytic_heat_slab_error(env_only_units_missing)
        assert item.status == "pass"

    def test_patch_residual_passes(self, env_only_units_missing):
        item = elastic_patch_residual(env_only_units_missing)
        assert item.status == "pass"

    def test_poiseuille_passes(self, env_only_units_missing):
        item = openfoam_poiseuille_profile_error(env_only_units_missing)
        assert item.status == "pass"

    def test_mass_balance_passes(self, env_only_units_missing):
        item = cfd_mass_balance_error(env_only_units_missing)
        assert item.status == "pass"

    def test_heat_balance_passes(self, env_only_units_missing):
        item = cfd_heat_balance_error(env_only_units_missing)
        assert item.status == "pass"

    def test_spd_check_passes_for_valid_tensor(self):
        """SPD gate must pass for a well-formed isotropic tensor."""
        import numpy as np
        lam = 200.0 * 0.3 / (1.3 * 0.4)
        mu = 200.0 / (2.0 * 1.3)
        C11 = lam + 2 * mu
        C12 = lam
        C = [[C11, C12, C12], [C12, C11, C12], [C12, C12, C11]]
        item = tensor_spd_check(C)
        assert item.status == "pass"
