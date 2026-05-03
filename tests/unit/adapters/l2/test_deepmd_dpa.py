"""Unit tests for DeepmdDpaCalculatorAdapter (DPA-3.1-3M stub)."""

from __future__ import annotations

import pytest

from zer0pa_materials_workbench.adapters.l2.base import L2PredictRequest
from zer0pa_materials_workbench.adapters.l2.deepmd_dpa import DeepmdDpaCalculatorAdapter
from zer0pa_materials_workbench.boundary import RESEARCH_BOUNDARY
from zer0pa_materials_workbench.envelope.envelope import Envelope

SI_STRUCTURE = {
    "lattice_vectors": [[3.84, 0.0, 0.0], [0.0, 3.84, 0.0], [0.0, 0.0, 3.84]],
    "species": ["Si", "Si"],
    "fractional_coords": [[0.0, 0.0, 0.0], [0.5, 0.5, 0.5]],
}

NACL_STRUCTURE = {
    "lattice_vectors": [[5.64, 0.0, 0.0], [0.0, 5.64, 0.0], [0.0, 0.0, 5.64]],
    "species": ["Na", "Cl"],
    "fractional_coords": [[0.0, 0.0, 0.0], [0.5, 0.5, 0.5]],
}


@pytest.fixture
def adapter():
    return DeepmdDpaCalculatorAdapter()


@pytest.fixture
def req():
    return L2PredictRequest(
        run_id="run:test/dpa/si",
        candidate_id="candidate:Si:001",
        campaign_id="campaign:test/001",
        rights_claim_id="rights:test/001",
    )


class TestDeepmdDpaAdapterInit:
    def test_model_id(self, adapter):
        assert adapter.model_id == "DPA-3.1-3M"

    def test_backend_stub(self, adapter):
        assert adapter.backend == "stub"

    def test_license_cc_by_40(self, adapter):
        # PRD mandate: do NOT use inherited "MIT"
        assert adapter.WEIGHTS_LICENSE == "CC-BY-4.0"
        assert adapter.LIBRARY_LICENSE == "LGPL-3.0"


class TestDeepmdDpaPredictShape:
    def test_predict_returns_dict(self, adapter, req):
        result = adapter.predict(SI_STRUCTURE, req)
        assert isinstance(result, dict)

    def test_predict_layer_is_L2(self, adapter, req):
        result = adapter.predict(SI_STRUCTURE, req)
        assert result["layer"] == "L2"

    def test_predict_boundary_verbatim(self, adapter, req):
        result = adapter.predict(SI_STRUCTURE, req)
        assert result["research_boundary"] == RESEARCH_BOUNDARY

    def test_predict_envelope_validates(self, adapter, req):
        result = adapter.predict(SI_STRUCTURE, req)
        # Remove adapter-private keys before Envelope validation.
        result_clean = {k: v for k, v in result.items() if not k.startswith("_")}
        env = Envelope.model_validate(result_clean)
        assert env.layer == "L2"

    def test_predict_has_one_prediction(self, adapter, req):
        result = adapter.predict(SI_STRUCTURE, req)
        preds = result["output"]["predictions"]
        assert len(preds) == 1
        assert preds[0]["model"] == "DPA-3.1-3M"

    def test_predict_energy_in_range(self, adapter, req):
        result = adapter.predict(SI_STRUCTURE, req)
        e = result["output"]["predictions"][0]["energy_eV_per_atom"]
        assert -8.0 <= e <= -2.0

    def test_predict_force_rmse_positive(self, adapter, req):
        result = adapter.predict(SI_STRUCTURE, req)
        f = result["output"]["predictions"][0]["force_rmse_eV_per_Ang"]
        assert 0.01 <= f <= 0.12

    def test_predict_audit_record_id_format(self, adapter, req):
        result = adapter.predict(SI_STRUCTURE, req)
        assert result["audit"]["audit_record_id"].startswith("audit:")

    def test_predict_hashes_format(self, adapter, req):
        result = adapter.predict(SI_STRUCTURE, req)
        assert result["audit"]["input_hash"].startswith("sha256:")
        assert result["audit"]["output_hash"].startswith("sha256:")


class TestDeepmdDpaDeterminism:
    def test_same_structure_same_energy(self, adapter, req):
        r1 = adapter.predict(SI_STRUCTURE, req)
        r2 = adapter.predict(SI_STRUCTURE, req)
        e1 = r1["output"]["predictions"][0]["energy_eV_per_atom"]
        e2 = r2["output"]["predictions"][0]["energy_eV_per_atom"]
        assert e1 == pytest.approx(e2)

    def test_different_structures_different_energy(self, adapter, req):
        r1 = adapter.predict(SI_STRUCTURE, req)
        r2 = adapter.predict(NACL_STRUCTURE, req)
        e1 = r1["output"]["predictions"][0]["energy_eV_per_atom"]
        e2 = r2["output"]["predictions"][0]["energy_eV_per_atom"]
        # Very unlikely to be equal given different hashes.
        assert e1 != pytest.approx(e2, rel=1e-6)


class TestDeepmdDpaBlockedManifests:
    def test_blocked_manifests_nonempty(self, adapter):
        manifests = adapter.blocked_manifests()
        assert len(manifests) >= 1

    def test_blocked_manifest_has_id(self, adapter):
        m = adapter.blocked_manifests()[0]
        assert m["source_manifest_id"] == "src:deepmd:dpa-3.1-3m-weights"

    def test_blocked_manifest_reason(self, adapter):
        m = adapter.blocked_manifests()[0]
        assert m["blocker_reason"] == "unavailable_credentials"

    def test_blocked_manifest_mentions_ccby(self, adapter):
        m = adapter.blocked_manifests()[0]
        assert "CC-BY-4.0" in m["blocker_detail"]

    def test_blocked_manifest_mentions_lgpl(self, adapter):
        m = adapter.blocked_manifests()[0]
        assert "LGPL-3.0" in m["blocker_detail"]

    def test_blocked_manifest_retry_strategy_nonempty(self, adapter):
        m = adapter.blocked_manifests()[0]
        assert len(m["retry_strategy"]) > 10
