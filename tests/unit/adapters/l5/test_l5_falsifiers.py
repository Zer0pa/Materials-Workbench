"""Unit tests for L5 falsifiers — each gate triggers correctly.

SPD check: writes a non-SPD synthetic tensor, verifies rejection.
All other gates: verifies pass/fail/blocked transitions.
"""

from __future__ import annotations

import pytest
import numpy as np

from zer0pa_materials.falsifiers.l5_falsifiers import (
    tensor_spd_check,
    analytic_heat_slab_error,
    elastic_patch_residual,
    fenicsx_dealii_strain_energy_disagreement,
    openfoam_poiseuille_profile_error,
    cfd_mass_balance_error,
    cfd_heat_balance_error,
    artifact_units_sidecar_present,
)
from zer0pa_materials.adapters.l5.base import L5ContinuumRequest
from zer0pa_materials.adapters.l5.fenicsx import FEniCSxContinuumAdapter
from zer0pa_materials.adapters.l5.dealii import DealIIStructuralAdapter
from zer0pa_materials.adapters.l5.openfoam import OpenFOAMProcessAdapter
from zer0pa_materials.boundary import RESEARCH_BOUNDARY


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_env_with_output(output: dict) -> dict:
    """Build a minimal envelope dict with the given output."""
    return {
        "research_boundary": RESEARCH_BOUNDARY,
        "contract_version": "zer0pa.materials.layer-envelope.v1",
        "layer": "L5",
        "run_id": "run:test/001",
        "candidate_id": "candidate:test",
        "campaign_id": "campaign:test",
        "tool_adapter": {
            "name": "TestAdapter",
            "version": "0.0.1",
            "backend": "stub",
            "engine": "test",
        },
        "output": output,
        "confidence": {"score": 0.5, "band": "medium", "basis": ["test"]},
        "disagreement": {"metrics": []},
        "falsifier": {"status": "pass", "items": []},
        "audit": {
            "audit_record_id": "audit:test/001",
            "input_hash": "sha256:" + "a" * 64,
            "output_hash": "sha256:" + "b" * 64,
            "source_manifest_refs": [],
        },
        "rights": {
            "rights_claim_id": "rights:test/001",
            "reuse_scope": "tenant_only",
        },
        "back_edges": [],
    }


def _good_l5_output(**overrides) -> dict:
    base = {
        "tensors": [
            {"name": "stiffness_C_3x3", "spd": True, "eigvals_min": 10.0},
        ],
        "analytic_heat_slab_error": 1e-12,
        "elastic_patch_residual": 1e-15,
        "fenicsx_vs_dealii_strain_energy_disagreement_pct": 0.5,
        "openfoam_poiseuille_error_pct": 0.001,
        "cfd_mass_balance_error": 1e-12,
        "cfd_heat_balance_error": 1e-12,
        "artifact_uris": [],
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# tensor_spd_check
# ---------------------------------------------------------------------------

class TestTensorSpdCheck:
    def test_identity_passes(self):
        item = tensor_spd_check(np.eye(3).tolist())
        assert item.status == "pass"

    def test_isotropic_stiffness_passes(self):
        # Isotropic stiffness at E=200 GPa, nu=0.3 is SPD.
        lam = 200.0 * 0.3 / ((1.3) * (0.4))
        mu = 200.0 / (2.0 * 1.3)
        C11 = lam + 2 * mu
        C12 = lam
        C = [[C11, C12, C12], [C12, C11, C12], [C12, C12, C11]]
        item = tensor_spd_check(C, name="stiffness")
        assert item.status == "pass"

    def test_non_spd_matrix_fails(self):
        """PRD §L5 Falsifiers: reject non-SPD tensors."""
        # This is the fixture tensor from fixtures/negatives/non_spd_tensor/
        C = [
            [100.0, 90.0, 80.0],
            [ 90.0, 10.0,  5.0],
            [ 80.0,  5.0,  2.0],
        ]
        item = tensor_spd_check(C, name="stiffness_C_3x3")
        assert item.status == "fail"
        assert item.actual["eigvals_min"] < 0.0

    def test_negative_diagonal_fails(self):
        C = [[-1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
        item = tensor_spd_check(C, name="bad_tensor")
        assert item.status == "fail"

    def test_non_square_fails(self):
        item = tensor_spd_check([[1.0, 0.0], [0.0, 1.0], [0.0, 0.0]])
        assert item.status == "fail"

    def test_non_numeric_blocked(self):
        item = tensor_spd_check([["a", "b"], ["c", "d"]])
        assert item.status == "blocked"

    def test_asymmetric_fails(self):
        C = [[1.0, 100.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
        item = tensor_spd_check(C, name="asymm", symmetry_tol=1e-10)
        assert item.status == "fail"

    def test_name_in_actual(self):
        item = tensor_spd_check(np.eye(3).tolist(), name="my_tensor")
        assert item.actual["tensor_name"] == "my_tensor"


# ---------------------------------------------------------------------------
# analytic_heat_slab_error
# ---------------------------------------------------------------------------

class TestAnalyticHeatSlabError:
    def test_pass_below_threshold(self):
        env = _make_env_with_output(_good_l5_output(analytic_heat_slab_error=1e-9))
        item = analytic_heat_slab_error(env)
        assert item.status == "pass"

    def test_fail_above_threshold(self):
        env = _make_env_with_output(_good_l5_output(analytic_heat_slab_error=2e-6))
        item = analytic_heat_slab_error(env)
        assert item.status == "fail"

    def test_exactly_at_threshold_fails(self):
        # < not <=
        env = _make_env_with_output(_good_l5_output(analytic_heat_slab_error=1e-6))
        item = analytic_heat_slab_error(env)
        assert item.status == "fail"

    def test_blocked_if_none(self):
        env = _make_env_with_output(_good_l5_output(analytic_heat_slab_error=None))
        item = analytic_heat_slab_error(env)
        assert item.status == "blocked"

    def test_blocked_if_no_output(self):
        env = {"research_boundary": RESEARCH_BOUNDARY, "layer": "L5"}
        item = analytic_heat_slab_error(env)
        assert item.status == "blocked"

    def test_custom_threshold(self):
        env = _make_env_with_output(_good_l5_output(analytic_heat_slab_error=5e-5))
        item = analytic_heat_slab_error(env, threshold=1e-4)
        assert item.status == "pass"


# ---------------------------------------------------------------------------
# elastic_patch_residual
# ---------------------------------------------------------------------------

class TestElasticPatchResidual:
    def test_pass_below_threshold(self):
        env = _make_env_with_output(_good_l5_output(elastic_patch_residual=1e-12))
        item = elastic_patch_residual(env)
        assert item.status == "pass"

    def test_fail_above_threshold(self):
        env = _make_env_with_output(_good_l5_output(elastic_patch_residual=2e-8))
        item = elastic_patch_residual(env)
        assert item.status == "fail"

    def test_blocked_if_none(self):
        env = _make_env_with_output(_good_l5_output(elastic_patch_residual=None))
        item = elastic_patch_residual(env)
        assert item.status == "blocked"

    def test_name_is_correct(self):
        env = _make_env_with_output(_good_l5_output())
        item = elastic_patch_residual(env)
        assert item.name == "l5.elastic_patch_residual"


# ---------------------------------------------------------------------------
# fenicsx_dealii_strain_energy_disagreement
# ---------------------------------------------------------------------------

class TestFenicsxDealIIDisagreement:
    def test_pass_below_2pct(self):
        env_a = _make_env_with_output(
            _good_l5_output(fenicsx_vs_dealii_strain_energy_disagreement_pct=None)
        )
        env_b = _make_env_with_output(
            _good_l5_output(fenicsx_vs_dealii_strain_energy_disagreement_pct=1.0)
        )
        item = fenicsx_dealii_strain_energy_disagreement(env_a, env_b)
        assert item.status == "pass"

    def test_fail_above_2pct(self):
        env_a = _make_env_with_output(
            _good_l5_output(fenicsx_vs_dealii_strain_energy_disagreement_pct=None)
        )
        env_b = _make_env_with_output(
            _good_l5_output(fenicsx_vs_dealii_strain_energy_disagreement_pct=3.0)
        )
        item = fenicsx_dealii_strain_energy_disagreement(env_a, env_b)
        assert item.status == "fail"

    def test_blocked_if_both_none(self):
        env_a = _make_env_with_output(
            _good_l5_output(fenicsx_vs_dealii_strain_energy_disagreement_pct=None)
        )
        env_b = _make_env_with_output(
            _good_l5_output(fenicsx_vs_dealii_strain_energy_disagreement_pct=None)
        )
        item = fenicsx_dealii_strain_energy_disagreement(env_a, env_b)
        assert item.status == "blocked"

    def test_exact_2pct_fails(self):
        # < not <=
        env_a = _make_env_with_output(_good_l5_output())
        env_b = _make_env_with_output(
            _good_l5_output(fenicsx_vs_dealii_strain_energy_disagreement_pct=2.0)
        )
        item = fenicsx_dealii_strain_energy_disagreement(env_a, env_b)
        assert item.status == "fail"


# ---------------------------------------------------------------------------
# openfoam_poiseuille_profile_error
# ---------------------------------------------------------------------------

class TestPoiseuilleError:
    def test_pass_below_5pct(self):
        env = _make_env_with_output(_good_l5_output(openfoam_poiseuille_error_pct=0.001))
        item = openfoam_poiseuille_profile_error(env)
        assert item.status == "pass"

    def test_fail_above_5pct(self):
        env = _make_env_with_output(_good_l5_output(openfoam_poiseuille_error_pct=7.0))
        item = openfoam_poiseuille_profile_error(env)
        assert item.status == "fail"

    def test_blocked_if_none(self):
        env = _make_env_with_output(_good_l5_output(openfoam_poiseuille_error_pct=None))
        item = openfoam_poiseuille_profile_error(env)
        assert item.status == "blocked"


# ---------------------------------------------------------------------------
# cfd_mass_balance_error
# ---------------------------------------------------------------------------

class TestMassBalance:
    def test_pass_below_1e4(self):
        env = _make_env_with_output(_good_l5_output(cfd_mass_balance_error=1e-10))
        item = cfd_mass_balance_error(env)
        assert item.status == "pass"

    def test_fail_above_1e4(self):
        env = _make_env_with_output(_good_l5_output(cfd_mass_balance_error=1e-3))
        item = cfd_mass_balance_error(env)
        assert item.status == "fail"

    def test_blocked_if_none(self):
        env = _make_env_with_output(_good_l5_output(cfd_mass_balance_error=None))
        item = cfd_mass_balance_error(env)
        assert item.status == "blocked"


# ---------------------------------------------------------------------------
# cfd_heat_balance_error
# ---------------------------------------------------------------------------

class TestHeatBalance:
    def test_pass_below_1e4(self):
        env = _make_env_with_output(_good_l5_output(cfd_heat_balance_error=1e-10))
        item = cfd_heat_balance_error(env)
        assert item.status == "pass"

    def test_fail_above_1e4(self):
        env = _make_env_with_output(_good_l5_output(cfd_heat_balance_error=2e-4))
        item = cfd_heat_balance_error(env)
        assert item.status == "fail"

    def test_blocked_if_none(self):
        env = _make_env_with_output(_good_l5_output(cfd_heat_balance_error=None))
        item = cfd_heat_balance_error(env)
        assert item.status == "blocked"


# ---------------------------------------------------------------------------
# artifact_units_sidecar_present
# ---------------------------------------------------------------------------

class TestArtifactSidecar:
    def test_pass_no_artifacts(self):
        env = _make_env_with_output(_good_l5_output())
        item = artifact_units_sidecar_present(env)
        assert item.status == "pass"

    def test_pass_with_valid_artifacts(self):
        env = _make_env_with_output(_good_l5_output())
        env["_artifact_sidecars"] = [
            {"format": "vtk", "units": {"velocity_unit": "m/s"}, "sha256": "sha256:" + "a" * 64},
        ]
        item = artifact_units_sidecar_present(env)
        assert item.status == "pass"

    def test_fail_missing_units(self):
        env = _make_env_with_output(_good_l5_output())
        env["_artifact_sidecars"] = [
            {"format": "vtk", "sha256": "sha256:" + "a" * 64},
        ]
        item = artifact_units_sidecar_present(env)
        assert item.status == "fail"
        assert "vtk:missing_units" in item.actual["failures"]

    def test_fail_missing_hash(self):
        env = _make_env_with_output(_good_l5_output())
        env["_artifact_sidecars"] = [
            {"format": "vtk", "units": {"v": "m/s"}},
        ]
        item = artifact_units_sidecar_present(env)
        assert item.status == "fail"
        assert "vtk:missing_sha256" in item.actual["failures"]

    def test_fail_empty_units_dict(self):
        env = _make_env_with_output(_good_l5_output())
        env["_artifact_sidecars"] = [
            {"format": "fmi", "units": {}, "sha256": "sha256:" + "a" * 64},
        ]
        item = artifact_units_sidecar_present(env)
        assert item.status == "fail"

    def test_blocked_bad_output(self):
        env = {"research_boundary": RESEARCH_BOUNDARY, "layer": "L5"}
        item = artifact_units_sidecar_present(env)
        assert item.status == "blocked"


# ---------------------------------------------------------------------------
# Integration: run adapters and apply falsifiers
# ---------------------------------------------------------------------------

class TestFalsifierIntegration:
    """Verify that L5 adapter outputs clear all PRD falsifier gates."""

    def _req(self, suffix: str = "001") -> L5ContinuumRequest:
        return L5ContinuumRequest(
            run_id=f"run:l5/falsifier/int/{suffix}",
            candidate_id="candidate:int",
            campaign_id="campaign:int",
            rights_claim_id="rights:int",
        )

    def test_fenicsx_heat_slab_gate_passes(self):
        req = self._req("fenicsx-heat")
        adapter = FEniCSxContinuumAdapter()
        env = adapter.run(req)
        item = analytic_heat_slab_error(env)
        assert item.status == "pass"

    def test_fenicsx_patch_gate_passes(self):
        req = self._req("fenicsx-patch")
        adapter = FEniCSxContinuumAdapter()
        env = adapter.run(req)
        item = elastic_patch_residual(env)
        assert item.status == "pass"

    def test_fenicsx_tensors_are_spd(self):
        from zer0pa_materials.adapters.l5.fenicsx import _synthetic_stiffness_tensor_3x3
        C = _synthetic_stiffness_tensor_3x3()
        item = tensor_spd_check(C, name="stiffness")
        assert item.status == "pass"

    def test_dealii_disagreement_gate_passes(self):
        req = self._req("dealii-disagree")
        fenicsx_env = FEniCSxContinuumAdapter().run(req)
        dealii_env = DealIIStructuralAdapter().run(req)
        item = fenicsx_dealii_strain_energy_disagreement(fenicsx_env, dealii_env)
        assert item.status == "pass"

    def test_openfoam_poiseuille_gate_passes(self):
        req = self._req("openfoam-poi")
        env = OpenFOAMProcessAdapter().run(req)
        item = openfoam_poiseuille_profile_error(env)
        assert item.status == "pass"

    def test_openfoam_mass_balance_gate_passes(self):
        req = self._req("openfoam-mass")
        env = OpenFOAMProcessAdapter().run(req)
        item = cfd_mass_balance_error(env)
        assert item.status == "pass"

    def test_openfoam_heat_balance_gate_passes(self):
        req = self._req("openfoam-heat")
        env = OpenFOAMProcessAdapter().run(req)
        item = cfd_heat_balance_error(env)
        assert item.status == "pass"
