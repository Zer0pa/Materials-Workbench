"""Unit tests for DealIIStructuralAdapter (structural mechanics stub)."""

from __future__ import annotations

import pytest

from zer0pa_materials_workbench.adapters.l5.base import L5ContinuumRequest
from zer0pa_materials_workbench.adapters.l5.dealii import DealIIStructuralAdapter, _analytic_strain_energy
from zer0pa_materials_workbench.boundary import RESEARCH_BOUNDARY
from zer0pa_materials_workbench.envelope.envelope import Envelope


@pytest.fixture
def req() -> L5ContinuumRequest:
    return L5ContinuumRequest(
        run_id="run:l5/test/dealii/001",
        candidate_id="candidate:Si:001",
        campaign_id="campaign:test/001",
        rights_claim_id="rights:test/001",
    )


@pytest.fixture
def adapter() -> DealIIStructuralAdapter:
    return DealIIStructuralAdapter()


class TestDealIIInit:
    def test_model_id(self, adapter):
        assert "DealII" in adapter.MODEL_ID

    def test_backend_stub(self, adapter):
        assert adapter.backend == "stub"

    def test_library_license(self, adapter):
        assert adapter.LIBRARY_LICENSE == "LGPL-2.1"


class TestAnalyticStrainEnergy:
    def test_energy_positive(self):
        U = _analytic_strain_energy()
        assert U > 0.0

    def test_energy_scales_with_E(self):
        U_low = _analytic_strain_energy(E=100.0)
        U_high = _analytic_strain_energy(E=300.0)
        assert U_high > U_low

    def test_energy_increases_with_higher_nu(self):
        # Higher Poisson ratio → higher plane-stress effective modulus E/(1-ν²).
        # 1/(1-ν²) increases monotonically with ν in (0, 0.5).
        U_low_nu = _analytic_strain_energy(nu=0.1)
        U_high_nu = _analytic_strain_energy(nu=0.4)
        assert U_high_nu > U_low_nu


class TestDealIIAdapterRun:
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

    def test_run_default_disagreement_below_2pct(self, adapter, req):
        """PRD gate: FEniCSx vs deal.II strain energy disagreement < 2%."""
        result = adapter.run(req)
        disagree = result["output"]["fenicsx_vs_dealii_strain_energy_disagreement_pct"]
        assert disagree is not None
        assert disagree < 2.0, f"Disagreement {disagree:.3f}% >= 2%"

    def test_run_override_above_2pct_fails_gate(self):
        """Disagreement override > 2% correctly exceeds the gate."""
        adapter = DealIIStructuralAdapter(disagreement_override_pct=3.0)
        req = L5ContinuumRequest(
            run_id="run:l5/test/dealii/fail",
            candidate_id="candidate:fail",
            campaign_id="campaign:fail",
            rights_claim_id="rights:fail",
        )
        result = adapter.run(req)
        disagree = result["output"]["fenicsx_vs_dealii_strain_energy_disagreement_pct"]
        assert disagree >= 2.0

    def test_run_has_dealii_meta(self, adapter, req):
        result = adapter.run(req)
        assert "_dealii_meta" in result["output"]
        meta = result["output"]["_dealii_meta"]
        assert "U_analytic_GPa_m2" in meta
        assert "U_dealii_GPa_m2" in meta

    def test_disagreement_is_non_negative(self, adapter, req):
        result = adapter.run(req)
        disagree = result["output"]["fenicsx_vs_dealii_strain_energy_disagreement_pct"]
        assert disagree >= 0.0

    def test_blocked_manifests_returns_list(self, adapter):
        manifests = adapter.blocked_manifests()
        assert isinstance(manifests, list)
        assert len(manifests) == 1

    def test_blocked_manifest_id(self, adapter):
        m = adapter.blocked_manifests()[0]
        assert m["source_manifest_id"] == "src:dealii:structural"

    def test_tool_adapter_name(self, adapter, req):
        result = adapter.run(req)
        assert result["tool_adapter"]["name"] == "DealIIStructuralAdapter"

    def test_determinism_same_run_id(self, adapter):
        req1 = L5ContinuumRequest(
            run_id="run:l5/determinism/001",
            candidate_id="candidate:det",
            campaign_id="campaign:det",
            rights_claim_id="rights:det",
        )
        req2 = L5ContinuumRequest(
            run_id="run:l5/determinism/001",
            candidate_id="candidate:det",
            campaign_id="campaign:det",
            rights_claim_id="rights:det",
        )
        d1 = adapter.run(req1)["output"]["fenicsx_vs_dealii_strain_energy_disagreement_pct"]
        d2 = adapter.run(req2)["output"]["fenicsx_vs_dealii_strain_energy_disagreement_pct"]
        assert d1 == d2
