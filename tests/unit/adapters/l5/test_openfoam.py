"""Unit tests for OpenFOAMProcessAdapter (Poiseuille flow stub)."""

from __future__ import annotations

import pytest

from zer0pa_materials_workbench.adapters.l5.base import L5ContinuumRequest
from zer0pa_materials_workbench.adapters.l5.openfoam import (
    OpenFOAMProcessAdapter,
    _heat_balance_error,
    _mass_balance_error,
    _poiseuille_profile_error,
)
from zer0pa_materials_workbench.boundary import RESEARCH_BOUNDARY
from zer0pa_materials_workbench.envelope.envelope import Envelope


@pytest.fixture
def req() -> L5ContinuumRequest:
    return L5ContinuumRequest(
        run_id="run:l5/test/openfoam/001",
        candidate_id="candidate:Si:001",
        campaign_id="campaign:test/001",
        rights_claim_id="rights:test/001",
    )


@pytest.fixture
def adapter() -> OpenFOAMProcessAdapter:
    return OpenFOAMProcessAdapter()


class TestPoiseuilleAnalytics:
    def test_profile_error_below_5pct(self):
        """PRD gate: Poiseuille profile error < 5%."""
        err = _poiseuille_profile_error()
        assert err < 0.05, f"Poiseuille error {err:.3e} >= 5%"

    def test_profile_error_non_negative(self):
        err = _poiseuille_profile_error()
        assert err >= 0.0

    def test_mass_balance_error_below_1e4(self):
        """PRD gate: mass balance error < 1e-4."""
        err = _mass_balance_error()
        assert err < 1e-4, f"Mass balance error {err:.3e} >= 1e-4"

    def test_heat_balance_adiabatic_zero(self):
        """Adiabatic walls: heat balance error should be 0."""
        err = _heat_balance_error(T_in=300.0, T_out=300.0)
        assert err == 0.0

    def test_heat_balance_nonzero_when_DT_nonzero(self):
        err = _heat_balance_error(T_in=300.0, T_out=310.0)
        assert err > 0.0


class TestOpenFOAMAdapterRun:
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

    def test_run_poiseuille_error_pct_below_5(self, adapter, req):
        """PRD gate: Poiseuille error < 5%."""
        result = adapter.run(req)
        err_pct = result["output"]["openfoam_poiseuille_error_pct"]
        assert err_pct is not None
        assert err_pct < 5.0, f"Poiseuille error {err_pct:.3f}% >= 5%"

    def test_run_mass_balance_below_1e4(self, adapter, req):
        """PRD gate: mass balance error < 1e-4."""
        result = adapter.run(req)
        err = result["output"]["cfd_mass_balance_error"]
        assert err is not None
        assert err < 1e-4

    def test_run_heat_balance_below_1e4(self, adapter, req):
        """PRD gate: heat balance error < 1e-4."""
        result = adapter.run(req)
        err = result["output"]["cfd_heat_balance_error"]
        assert err is not None
        assert err < 1e-4

    def test_run_has_openfoam_meta(self, adapter, req):
        result = adapter.run(req)
        assert "_openfoam_meta" in result["output"]
        meta = result["output"]["_openfoam_meta"]
        assert "velocity_unit" in meta
        assert meta["velocity_unit"] == "m/s"
        assert "pressure_unit" in meta
        assert meta["pressure_unit"] == "Pa"

    def test_override_poiseuille_above_5pct(self):
        """Override > 5% correctly exceeds the gate."""
        adapter = OpenFOAMProcessAdapter(poiseuille_error_override=0.10)
        req = L5ContinuumRequest(
            run_id="run:l5/test/openfoam/fail",
            candidate_id="candidate:fail",
            campaign_id="campaign:fail",
            rights_claim_id="rights:fail",
        )
        result = adapter.run(req)
        err_pct = result["output"]["openfoam_poiseuille_error_pct"]
        assert err_pct >= 5.0

    def test_override_mass_balance_above_threshold(self):
        adapter = OpenFOAMProcessAdapter(mass_balance_override=1e-3)
        req = L5ContinuumRequest(
            run_id="run:l5/test/openfoam/mass",
            candidate_id="candidate:mass",
            campaign_id="campaign:mass",
            rights_claim_id="rights:mass",
        )
        result = adapter.run(req)
        err = result["output"]["cfd_mass_balance_error"]
        assert err >= 1e-4

    def test_blocked_manifests_returns_list(self, adapter):
        manifests = adapter.blocked_manifests()
        assert isinstance(manifests, list)
        assert len(manifests) == 1

    def test_blocked_manifest_id(self, adapter):
        m = adapter.blocked_manifests()[0]
        assert m["source_manifest_id"] == "src:openfoam:cfd"

    def test_tool_adapter_engine(self, adapter, req):
        result = adapter.run(req)
        assert result["tool_adapter"]["engine"] == "OpenFOAM"
