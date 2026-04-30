"""Contract tests for the L1.5 phonon and thermoelectric transport service.

Every endpoint is exercised through ``fastapi.testclient.TestClient``
so the service's wire interface is fully covered without a live server.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from zer0pa_materials.services.l1_5_service import (
    L15_SERVICE_NAME,
    L15_SERVICE_VERSION,
    create_l15_app,
)


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(create_l15_app())


@pytest.fixture(scope="module")
def bi2te3_payload() -> dict:
    return {
        "structure_hash": "sha256:bi2te3_contract_test_hash_00000001",
        "fixture_id": "fixture:Bi2Te3:ae87f3b2",
        "material_id": "Bi2Te3",
        "candidate_id": "candidate:Bi2Te3/contract",
        "campaign_id": "campaign:contract-test",
        "temperature_K": 300.0,
    }


@pytest.fixture(scope="module")
def si_payload() -> dict:
    return {
        "structure_hash": "sha256:si_contract_test_hash_000000001",
        "material_id": "Si",
        "candidate_id": "candidate:Si/contract",
        "campaign_id": "campaign:contract-test",
    }


class TestHealthz:
    def test_healthz_returns_ok(self, client: TestClient) -> None:
        r = client.get("/v1/l15/healthz")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert body["service"] == L15_SERVICE_NAME
        assert body["version"] == L15_SERVICE_VERSION

    def test_healthz_has_service_ref(self, client: TestClient) -> None:
        r = client.get("/v1/l15/healthz")
        body = r.json()
        assert "service_ref" in body
        assert body["service_ref"].startswith("service:")


class TestForceBatches:
    def test_force_batches_returns_queued(
        self, client: TestClient, bi2te3_payload: dict
    ) -> None:
        r = client.post("/v1/l15/force-batches", json=bi2te3_payload)
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "queued"
        assert "batch_id" in body


class TestBandsUniform:
    def test_bands_uniform_returns_queued(
        self, client: TestClient, bi2te3_payload: dict
    ) -> None:
        r = client.post("/v1/l15/bands/uniform", json=bi2te3_payload)
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "queued"


class TestPhonopyHarmonic:
    def test_phonopy_harmonic_returns_envelope(
        self, client: TestClient, si_payload: dict
    ) -> None:
        r = client.post("/v1/l15/phonopy-harmonic", json=si_payload)
        assert r.status_code == 200
        body = r.json()
        assert body["layer"] == "L1.5"
        assert "output" in body

    def test_phonopy_harmonic_output_has_imaginary_field(
        self, client: TestClient, si_payload: dict
    ) -> None:
        r = client.post("/v1/l15/phonopy-harmonic", json=si_payload)
        body = r.json()
        assert "imaginary_mode_max_THz" in body["output"]
        assert body["output"]["imaginary_mode_max_THz"] >= 0.0

    def test_phonopy_harmonic_no_ionic_claim(
        self, client: TestClient, si_payload: dict
    ) -> None:
        r = client.post("/v1/l15/phonopy-harmonic", json=si_payload)
        body = r.json()
        assert body["output"].get("ionic_conductivity_S_per_cm") is None

    def test_phonopy_harmonic_boundary_in_envelope(
        self, client: TestClient, si_payload: dict
    ) -> None:
        r = client.post("/v1/l15/phonopy-harmonic", json=si_payload)
        body = r.json()
        assert body["research_boundary"] is not None


class TestPhono3pyBte:
    def test_phono3py_bte_returns_envelope(
        self, client: TestClient, bi2te3_payload: dict
    ) -> None:
        r = client.post("/v1/l15/phono3py-bte", json=bi2te3_payload)
        assert r.status_code == 200
        body = r.json()
        assert body["layer"] == "L1.5"

    def test_phono3py_bte_kappa_positive(
        self, client: TestClient, bi2te3_payload: dict
    ) -> None:
        r = client.post("/v1/l15/phono3py-bte", json=bi2te3_payload)
        body = r.json()
        kappa = body["output"]["thermal_conductivity_W_per_mK"]
        assert kappa is not None
        assert kappa > 0.0

    def test_phono3py_bte_convergence_reported(
        self, client: TestClient, bi2te3_payload: dict
    ) -> None:
        r = client.post("/v1/l15/phono3py-bte", json=bi2te3_payload)
        body = r.json()
        assert body["output"]["qmesh_convergence_pct"] is not None


class TestHiphiveFit:
    def test_hiphive_fit_returns_envelope(
        self, client: TestClient, bi2te3_payload: dict
    ) -> None:
        r = client.post("/v1/l15/hiphive-fit", json=bi2te3_payload)
        assert r.status_code == 200
        body = r.json()
        assert body["layer"] == "L1.5"

    def test_hiphive_fit_mlip_rmse_reported(
        self, client: TestClient, bi2te3_payload: dict
    ) -> None:
        r = client.post("/v1/l15/hiphive-fit", json=bi2te3_payload)
        body = r.json()
        rmse = body["output"]["mlip_vs_dft_force_rmse_eV_per_Ang"]
        assert rmse is not None
        assert rmse > 0.0


class TestBoltzTrap2Transport:
    def test_boltztrap2_returns_envelope(
        self, client: TestClient, bi2te3_payload: dict
    ) -> None:
        r = client.post("/v1/l15/boltztrap2-transport", json=bi2te3_payload)
        assert r.status_code == 200
        body = r.json()
        assert body["layer"] == "L1.5"

    def test_boltztrap2_seebeck_within_range(
        self, client: TestClient, bi2te3_payload: dict
    ) -> None:
        r = client.post("/v1/l15/boltztrap2-transport", json=bi2te3_payload)
        body = r.json()
        seebeck = body["output"]["seebeck_uV_per_K"]
        assert 150.0 <= seebeck <= 280.0


class TestAmsetTransport:
    def test_amset_returns_envelope(
        self, client: TestClient, bi2te3_payload: dict
    ) -> None:
        r = client.post("/v1/l15/amset-transport", json=bi2te3_payload)
        assert r.status_code == 200
        body = r.json()
        assert body["layer"] == "L1.5"

    def test_amset_seebeck_positive(
        self, client: TestClient, bi2te3_payload: dict
    ) -> None:
        r = client.post("/v1/l15/amset-transport", json=bi2te3_payload)
        body = r.json()
        assert body["output"]["seebeck_uV_per_K"] > 0.0


class TestZtAssemble:
    def test_zt_assemble_returns_envelope(
        self, client: TestClient, bi2te3_payload: dict
    ) -> None:
        r = client.post("/v1/l15/zt-assemble", json=bi2te3_payload)
        assert r.status_code == 200
        body = r.json()
        assert body["layer"] == "L1.5"

    def test_zt_assemble_has_zt_assembly(
        self, client: TestClient, bi2te3_payload: dict
    ) -> None:
        r = client.post("/v1/l15/zt-assemble", json=bi2te3_payload)
        body = r.json()
        assert "zt_assembly" in body["output"]
        zt_assembly = body["output"]["zt_assembly"]
        assert "bt2_zt" in zt_assembly
        assert "amset_zt" in zt_assembly

    def test_zt_assemble_both_branches_positive(
        self, client: TestClient, bi2te3_payload: dict
    ) -> None:
        r = client.post("/v1/l15/zt-assemble", json=bi2te3_payload)
        body = r.json()
        zt_assembly = body["output"]["zt_assembly"]
        assert zt_assembly["bt2_zt"] > 0.0
        assert zt_assembly["amset_zt"] > 0.0

    def test_zt_assemble_rank_stability_in_falsifier(
        self, client: TestClient, bi2te3_payload: dict
    ) -> None:
        r = client.post("/v1/l15/zt-assemble", json=bi2te3_payload)
        body = r.json()
        names = [i["name"] for i in body["falsifier"]["items"]]
        assert "l15.zt_rank_stability" in names

    def test_zt_assemble_no_ionic_conductivity(
        self, client: TestClient, bi2te3_payload: dict
    ) -> None:
        r = client.post("/v1/l15/zt-assemble", json=bi2te3_payload)
        body = r.json()
        assert body["output"].get("ionic_conductivity_S_per_cm") is None

    def test_zt_assemble_phonon_not_ionic_falsifier(
        self, client: TestClient, bi2te3_payload: dict
    ) -> None:
        r = client.post("/v1/l15/zt-assemble", json=bi2te3_payload)
        body = r.json()
        names = [i["name"] for i in body["falsifier"]["items"]]
        assert "l15.phonon_does_not_substitute_for_ionic" in names

    def test_zt_assemble_audit_has_hashes(
        self, client: TestClient, bi2te3_payload: dict
    ) -> None:
        r = client.post("/v1/l15/zt-assemble", json=bi2te3_payload)
        body = r.json()
        audit = body["audit"]
        assert audit["input_hash"].startswith("sha256:")
        assert audit["output_hash"].startswith("sha256:")

    def test_zt_assemble_snse_at_high_temp(self, client: TestClient) -> None:
        """SnSe at 800 K should have high Seebeck and ZT."""
        payload = {
            "structure_hash": "sha256:snse_contract_800k_test_00001",
            "material_id": "SnSe",
            "temperature_K": 800.0,
            "candidate_id": "candidate:SnSe/800K",
            "campaign_id": "campaign:contract-test",
        }
        r = client.post("/v1/l15/zt-assemble", json=payload)
        assert r.status_code == 200
        body = r.json()
        seebeck = body["output"]["seebeck_uV_per_K"]
        assert seebeck > 300.0, f"SnSe Seebeck = {seebeck} µV/K, expected > 300"
