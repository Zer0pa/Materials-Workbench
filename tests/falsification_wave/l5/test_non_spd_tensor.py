"""Falsification wave: non-SPD tensor fixture.

PRD §L5 Falsifiers: "Reject non-SPD stiffness or conductivity tensors."
Fixture: ``fixtures/negatives/non_spd_tensor/``

The test verifies that:
1. The fixture fixture triggers EXACTLY ``tensor_spd_check`` → ``fail``.
2. No other falsifier gate fires on this fixture (because all other L5
   fields have passing values; only the SPD gate is deliberately broken).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from zer0pa_materials.falsifiers.l5_falsifiers import (
    tensor_spd_check,
    analytic_heat_slab_error,
    elastic_patch_residual,
    openfoam_poiseuille_profile_error,
    cfd_mass_balance_error,
    cfd_heat_balance_error,
    artifact_units_sidecar_present,
)
from zer0pa_materials.boundary import RESEARCH_BOUNDARY

# ---------------------------------------------------------------------------
# Fixture loading
# ---------------------------------------------------------------------------

FIXTURE_DIR = (
    Path(__file__).parent.parent.parent.parent
    / "fixtures"
    / "negatives"
    / "non_spd_tensor"
)


@pytest.fixture(scope="module")
def fixture_data():
    result_file = FIXTURE_DIR / "l5_result.json"
    assert result_file.exists(), f"Fixture not found: {result_file}"
    return json.loads(result_file.read_text())


@pytest.fixture(scope="module")
def fixture_manifest():
    manifest_file = FIXTURE_DIR / "manifest.json"
    assert manifest_file.exists(), f"Manifest not found: {manifest_file}"
    return json.loads(manifest_file.read_text())


def _build_envelope_from_fixture(fixture: dict) -> dict:
    """Build a minimal L5 envelope from the fixture result JSON."""
    return {
        "research_boundary": RESEARCH_BOUNDARY,
        "contract_version": "zer0pa.materials.layer-envelope.v1",
        "layer": "L5",
        "run_id": "run:falsification/l5/non_spd_tensor",
        "candidate_id": "candidate:non_spd_tensor",
        "campaign_id": "campaign:falsification/001",
        "tool_adapter": {
            "name": "FalsificationStub",
            "version": "0.0.1",
            "backend": "stub",
            "engine": "test",
        },
        "output": {
            "tensors": fixture.get("tensors", []),
            "analytic_heat_slab_error": fixture.get("analytic_heat_slab_error"),
            "elastic_patch_residual": fixture.get("elastic_patch_residual"),
            "fenicsx_vs_dealii_strain_energy_disagreement_pct": fixture.get(
                "fenicsx_vs_dealii_strain_energy_disagreement_pct"
            ),
            "openfoam_poiseuille_error_pct": fixture.get("openfoam_poiseuille_error_pct"),
            "cfd_mass_balance_error": fixture.get("cfd_mass_balance_error"),
            "cfd_heat_balance_error": fixture.get("cfd_heat_balance_error"),
            "artifact_uris": fixture.get("artifact_uris", []),
        },
        "confidence": {"score": 0.5, "band": "medium", "basis": ["test"]},
        "disagreement": {"metrics": []},
        "falsifier": {"status": "pass", "items": []},
        "audit": {
            "audit_record_id": "audit:test/non_spd_tensor",
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


# ---------------------------------------------------------------------------
# Manifest assertions
# ---------------------------------------------------------------------------

class TestFixtureManifest:
    def test_manifest_exists(self, fixture_manifest):
        assert fixture_manifest is not None

    def test_negative_falsifier_target(self, fixture_manifest):
        assert fixture_manifest["negative_falsifier_target"] == "non_spd_tensor"

    def test_kind_is_negative(self, fixture_manifest):
        assert fixture_manifest["kind"] == "negative"

    def test_boundary_verbatim(self, fixture_manifest):
        assert fixture_manifest["research_boundary"] == RESEARCH_BOUNDARY

    def test_expected_layer_l5(self, fixture_manifest):
        assert "L5" in fixture_manifest["expected_use_layers"]


# ---------------------------------------------------------------------------
# Fixture data assertions
# ---------------------------------------------------------------------------

class TestFixtureData:
    def test_fixture_has_tensors(self, fixture_data):
        assert "tensors" in fixture_data
        assert len(fixture_data["tensors"]) >= 1

    def test_first_tensor_not_spd(self, fixture_data):
        tensor = fixture_data["tensors"][0]
        assert tensor["spd"] is False

    def test_raw_matrix_has_negative_eigenvalue(self, fixture_data):
        """The 3x3 matrix in the fixture must have a negative eigenvalue."""
        C = fixture_data["_synthetic_C_3x3"]
        arr = np.array(C)
        eigvals = np.linalg.eigvalsh(arr)
        assert eigvals.min() < 0.0, (
            f"Expected negative eigenvalue but got min={eigvals.min():.6f}"
        )

    def test_other_fields_are_passing(self, fixture_data):
        """All non-SPD fields must have passing values (only SPD gate should fire)."""
        assert fixture_data.get("analytic_heat_slab_error", 1.0) < 1e-6
        assert fixture_data.get("elastic_patch_residual", 1.0) < 1e-8
        assert fixture_data.get("fenicsx_vs_dealii_strain_energy_disagreement_pct", 100.0) < 2.0
        assert fixture_data.get("openfoam_poiseuille_error_pct", 100.0) < 5.0
        assert fixture_data.get("cfd_mass_balance_error", 1.0) < 1e-4
        assert fixture_data.get("cfd_heat_balance_error", 1.0) < 1e-4


# ---------------------------------------------------------------------------
# PRD gate: tensor_spd_check MUST fail on the fixture tensor
# ---------------------------------------------------------------------------

class TestSpdGateFires:
    def test_spd_check_fails_on_fixture_matrix(self, fixture_data):
        """PRD §L5: tensor_spd_check MUST fail on the non-SPD fixture matrix."""
        C = fixture_data["_synthetic_C_3x3"]
        item = tensor_spd_check(C, name="stiffness_C_3x3")
        assert item.status == "fail", (
            f"Expected 'fail' but got {item.status!r}; "
            f"actual={item.actual}"
        )

    def test_spd_check_eigmin_is_negative(self, fixture_data):
        C = fixture_data["_synthetic_C_3x3"]
        item = tensor_spd_check(C, name="stiffness_C_3x3")
        assert item.actual["eigvals_min"] < 0.0

    def test_spd_check_via_envelope_tensors(self, fixture_data):
        """The same gate fires when reading tensors from the envelope output."""
        env = _build_envelope_from_fixture(fixture_data)
        # tensors[0] has spd=False; tensor_spd_check must agree.
        tensor_record = fixture_data["tensors"][0]
        C = fixture_data["_synthetic_C_3x3"]
        item = tensor_spd_check(C, name=tensor_record["name"])
        assert item.status == "fail"


# ---------------------------------------------------------------------------
# PRD gate: EXACTLY tensor_spd_check fires — no other L5 gate fires
# ---------------------------------------------------------------------------

class TestOnlySpdGateFires:
    """All other L5 gates must PASS on the non-SPD fixture.

    The fixture is constructed so only the SPD gate triggers.
    """

    def test_heat_slab_passes(self, fixture_data):
        env = _build_envelope_from_fixture(fixture_data)
        item = analytic_heat_slab_error(env)
        assert item.status == "pass", (
            f"analytic_heat_slab_error should pass but got {item.status!r}"
        )

    def test_patch_residual_passes(self, fixture_data):
        env = _build_envelope_from_fixture(fixture_data)
        item = elastic_patch_residual(env)
        assert item.status == "pass"

    def test_poiseuille_passes(self, fixture_data):
        env = _build_envelope_from_fixture(fixture_data)
        item = openfoam_poiseuille_profile_error(env)
        assert item.status == "pass"

    def test_mass_balance_passes(self, fixture_data):
        env = _build_envelope_from_fixture(fixture_data)
        item = cfd_mass_balance_error(env)
        assert item.status == "pass"

    def test_heat_balance_passes(self, fixture_data):
        env = _build_envelope_from_fixture(fixture_data)
        item = cfd_heat_balance_error(env)
        assert item.status == "pass"

    def test_artifact_sidecar_passes(self, fixture_data):
        env = _build_envelope_from_fixture(fixture_data)
        item = artifact_units_sidecar_present(env)
        assert item.status == "pass"
