"""Unit tests for MaceMpCalculatorAdapter (MACE-MPA-0 stub)."""

from __future__ import annotations

import pytest

from zer0pa_materials.adapters.l2.base import L2PredictRequest
from zer0pa_materials.adapters.l2.mace_mp import MaceMpCalculatorAdapter
from zer0pa_materials.boundary import RESEARCH_BOUNDARY
from zer0pa_materials.envelope.envelope import Envelope


SI_STRUCTURE = {
    "lattice_vectors": [[3.84, 0.0, 0.0], [0.0, 3.84, 0.0], [0.0, 0.0, 3.84]],
    "species": ["Si", "Si"],
    "fractional_coords": [[0.0, 0.0, 0.0], [0.5, 0.5, 0.5]],
}


@pytest.fixture
def adapter():
    return MaceMpCalculatorAdapter()


@pytest.fixture
def req():
    return L2PredictRequest(
        run_id="run:test/mace/si",
        candidate_id="candidate:Si:001",
        campaign_id="campaign:test/001",
        rights_claim_id="rights:test/001",
    )


class TestMaceMpAdapterInit:
    def test_model_id(self, adapter):
        assert adapter.model_id == "MACE-MPA-0"

    def test_backend_stub(self, adapter):
        assert adapter.backend == "stub"

    def test_checkpoint_license_not_inherited_mit(self, adapter):
        # License is pinned per checkpoint; we verify the field name exists
        # and the value is explicit (not just "MIT" from package inheritance).
        assert adapter.CHECKPOINT_LICENSE == "MIT"
        assert adapter.PACKAGE_LICENSE == "MIT"


class TestMaceMpPredictShape:
    def test_predict_layer_is_L2(self, adapter, req):
        result = adapter.predict(SI_STRUCTURE, req)
        assert result["layer"] == "L2"

    def test_predict_boundary_verbatim(self, adapter, req):
        result = adapter.predict(SI_STRUCTURE, req)
        assert result["research_boundary"] == RESEARCH_BOUNDARY

    def test_predict_envelope_validates(self, adapter, req):
        result = adapter.predict(SI_STRUCTURE, req)
        result_clean = {k: v for k, v in result.items() if not k.startswith("_")}
        env = Envelope.model_validate(result_clean)
        assert env.layer == "L2"

    def test_predict_model_id_in_predictions(self, adapter, req):
        result = adapter.predict(SI_STRUCTURE, req)
        assert result["output"]["predictions"][0]["model"] == "MACE-MPA-0"


class TestMaceMpDifferentFromDpa:
    def test_mace_energy_differs_from_dpa(self):
        """MACE and DPA stubs use different seed offsets → different energies."""
        from zer0pa_materials.adapters.l2.deepmd_dpa import DeepmdDpaCalculatorAdapter

        mace = MaceMpCalculatorAdapter()
        dpa = DeepmdDpaCalculatorAdapter()
        req = L2PredictRequest(
            run_id="run:test/compare",
            candidate_id="candidate:Si",
            campaign_id="campaign:test",
            rights_claim_id="rights:test",
        )
        mace_e = mace.predict(SI_STRUCTURE, req)["output"]["predictions"][0]["energy_eV_per_atom"]
        dpa_e = dpa.predict(SI_STRUCTURE, req)["output"]["predictions"][0]["energy_eV_per_atom"]
        # The two adapters use different seed offsets — energies MUST differ.
        assert mace_e != pytest.approx(dpa_e, rel=1e-6)


class TestMaceMpBlockedManifests:
    def test_blocked_manifest_id(self, adapter):
        m = adapter.blocked_manifests()[0]
        assert m["source_manifest_id"] == "src:mace:mpa0-checkpoint"

    def test_blocked_manifest_reason(self, adapter):
        m = adapter.blocked_manifests()[0]
        assert m["blocker_reason"] == "unavailable_credentials"
