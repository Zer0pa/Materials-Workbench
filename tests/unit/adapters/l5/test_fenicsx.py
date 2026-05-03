"""Unit tests for FEniCSxContinuumAdapter (heat slab + elasticity patch test)."""

from __future__ import annotations

import numpy as np
import pytest

from zer0pa_materials_workbench.adapters.l5.base import L5ContinuumRequest
from zer0pa_materials_workbench.adapters.l5.fenicsx import (
    _DOLFINX_AVAILABLE,
    FEniCSxContinuumAdapter,
    _analytic_heat_slab_error,
    _elastic_patch_residual,
    _synthetic_conductivity_tensor_3x3,
    _synthetic_stiffness_tensor_3x3,
)
from zer0pa_materials_workbench.boundary import RESEARCH_BOUNDARY
from zer0pa_materials_workbench.envelope.envelope import Envelope


@pytest.fixture
def req() -> L5ContinuumRequest:
    return L5ContinuumRequest(
        run_id="run:l5/test/fenicsx/001",
        candidate_id="candidate:Si:001",
        campaign_id="campaign:test/001",
        rights_claim_id="rights:test/001",
    )


@pytest.fixture
def adapter() -> FEniCSxContinuumAdapter:
    return FEniCSxContinuumAdapter()


# ---------------------------------------------------------------------------
# dolfinx availability gate (informational)
# ---------------------------------------------------------------------------

class TestDolfinxAvailability:
    def test_dolfinx_flag_is_bool(self):
        assert isinstance(_DOLFINX_AVAILABLE, bool)

    def test_adapter_backend_matches_availability(self, adapter):
        if _DOLFINX_AVAILABLE:
            assert adapter.backend == "local_cpu"
        else:
            assert adapter.backend == "stub"


# ---------------------------------------------------------------------------
# PRD gate: analytic heat slab error < 1e-6
# ---------------------------------------------------------------------------

class TestAnalyticHeatSlab:
    def test_heat_slab_error_below_threshold(self):
        """PRD gate: analytic heat slab error < 1e-6."""
        err = _analytic_heat_slab_error()
        assert err < 1e-6, f"Heat slab error {err:.3e} >= 1e-6"

    def test_heat_slab_error_non_negative(self):
        err = _analytic_heat_slab_error()
        assert err >= 0.0

    def test_heat_slab_error_at_different_mesh_sizes(self):
        for n in [5, 10, 20]:
            err = _analytic_heat_slab_error(n_elements=n)
            assert err < 1e-6, f"n={n}: error {err:.3e} >= 1e-6"

    def test_heat_slab_error_with_symmetric_temps(self):
        err = _analytic_heat_slab_error(T0=300.0, T1=300.0)
        # Uniform T: trivially exact.
        assert err < 1e-10


# ---------------------------------------------------------------------------
# PRD gate: elastic patch residual < 1e-8
# ---------------------------------------------------------------------------

class TestElasticPatchResidual:
    def test_patch_residual_below_threshold(self):
        """PRD gate: elastic patch residual < 1e-8."""
        res = _elastic_patch_residual()
        assert res < 1e-8, f"Patch residual {res:.3e} >= 1e-8"

    def test_patch_residual_non_negative(self):
        res = _elastic_patch_residual()
        assert res >= 0.0

    def test_patch_residual_various_meshes(self):
        for n in [2, 4, 8]:
            res = _elastic_patch_residual(n_elements=n)
            assert res < 1e-8, f"n={n}: residual {res:.3e} >= 1e-8"


# ---------------------------------------------------------------------------
# Stiffness / conductivity tensors: SPD check
# ---------------------------------------------------------------------------

class TestSyntheticTensors:
    def test_stiffness_is_3x3(self):
        C = _synthetic_stiffness_tensor_3x3()
        arr = np.array(C)
        assert arr.shape == (3, 3)

    def test_stiffness_is_symmetric(self):
        C = _synthetic_stiffness_tensor_3x3()
        arr = np.array(C)
        assert np.allclose(arr, arr.T, atol=1e-12)

    def test_stiffness_is_spd(self):
        C = _synthetic_stiffness_tensor_3x3()
        eigvals = np.linalg.eigvalsh(np.array(C))
        assert eigvals.min() > 0.0, f"Smallest eigenvalue = {eigvals.min():.3e}"

    def test_conductivity_is_3x3(self):
        K = _synthetic_conductivity_tensor_3x3()
        arr = np.array(K)
        assert arr.shape == (3, 3)

    def test_conductivity_is_spd(self):
        K = _synthetic_conductivity_tensor_3x3()
        eigvals = np.linalg.eigvalsh(np.array(K))
        assert eigvals.min() > 0.0

    def test_stiffness_scales_with_E(self):
        C_low = np.array(_synthetic_stiffness_tensor_3x3(E=100.0))
        C_high = np.array(_synthetic_stiffness_tensor_3x3(E=300.0))
        # Higher E → larger stiffness.
        assert C_high[0, 0] > C_low[0, 0]


# ---------------------------------------------------------------------------
# Adapter run: envelope shape + gate values
# ---------------------------------------------------------------------------

class TestFEniCSxAdapterRun:
    def test_run_returns_dict(self, adapter, req):
        result = adapter.run(req)
        assert isinstance(result, dict)

    def test_run_layer_is_L5(self, adapter, req):
        result = adapter.run(req)
        assert result["layer"] == "L5"

    def test_run_boundary_verbatim(self, adapter, req):
        result = adapter.run(req)
        assert result["research_boundary"] == RESEARCH_BOUNDARY

    def test_run_envelope_validates(self, adapter, req):
        result = adapter.run(req)
        clean = {k: v for k, v in result.items() if not k.startswith("_")}
        env = Envelope.model_validate(clean)
        assert env.layer == "L5"

    def test_run_has_two_tensors(self, adapter, req):
        result = adapter.run(req)
        tensors = result["output"]["tensors"]
        assert len(tensors) == 2
        names = {t["name"] for t in tensors}
        assert "stiffness_C_3x3" in names
        assert "conductivity_K_3x3" in names

    def test_run_both_tensors_spd(self, adapter, req):
        result = adapter.run(req)
        for t in result["output"]["tensors"]:
            assert t["spd"] is True, f"Tensor {t['name']} not SPD"

    def test_run_heat_slab_error_below_gate(self, adapter, req):
        result = adapter.run(req)
        err = result["output"]["analytic_heat_slab_error"]
        assert err < 1e-6

    def test_run_patch_residual_below_gate(self, adapter, req):
        result = adapter.run(req)
        res = result["output"]["elastic_patch_residual"]
        assert res < 1e-8

    def test_run_has_fenicsx_meta(self, adapter, req):
        result = adapter.run(req)
        assert "_fenicsx_meta" in result["output"]
        meta = result["output"]["_fenicsx_meta"]
        assert "mesh_size" in meta
        assert "solver_iterations" in meta

    def test_run_audit_record_id_has_prefix(self, adapter, req):
        result = adapter.run(req)
        assert result["audit"]["audit_record_id"].startswith("audit:")

    def test_blocked_manifests_returns_list(self, adapter):
        manifests = adapter.blocked_manifests()
        assert isinstance(manifests, list)
        assert len(manifests) == 1

    def test_blocked_manifest_id(self, adapter):
        m = adapter.blocked_manifests()[0]
        assert m["source_manifest_id"] == "src:fenicsx:dolfinx"

    def test_tool_adapter_engine(self, adapter, req):
        result = adapter.run(req)
        assert result["tool_adapter"]["engine"] == "dolfinx"
