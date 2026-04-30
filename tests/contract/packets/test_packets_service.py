"""Contract tests for the MVP Evidence Packet FastAPI service.

Boundary
--------
Research infrastructure for in silico materials science discovery. Outputs are
research artifacts. No regulatory certification claims. No clinical or
human-subject use. ITAR / weapons applications are out of scope (Meta UMA
Acceptable Use Policy and operator policy).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from zer0pa_materials.services.packets_service import (
    PACKETS_SERVICE_NAME,
    PACKETS_SERVICE_VERSION,
    create_packets_app,
)


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(create_packets_app())


def test_healthz(client: TestClient) -> None:
    r = client.get("/v1/packets/healthz")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["service"] == PACKETS_SERVICE_NAME
    assert body["version"] == PACKETS_SERVICE_VERSION


def test_list_battery_fixtures(client: TestClient) -> None:
    r = client.get("/v1/packets/fixtures/battery")
    assert r.status_code == 200
    body = r.json()
    assert "LLZO" in body["fixtures"]
    assert "Li6PS5Cl" in body["fixtures"]
    assert "Li-Mg-Zr-Cl-seed" in body["fixtures"]
    assert body["count"] == 3


def test_list_thermoelectric_fixtures(client: TestClient) -> None:
    r = client.get("/v1/packets/fixtures/thermoelectric")
    assert r.status_code == 200
    body = r.json()
    assert set(body["fixtures"]) == {"Si", "Bi2Te3", "PbTe", "SnSe"}
    assert body["count"] == 4


def test_assemble_battery_llzo(client: TestClient) -> None:
    payload = {"fixture_key": "LLZO", "interface_mode": "li_metal"}
    r = client.post("/v1/packets/assemble/battery", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["objective"] == "battery_solid_electrolyte"
    assert body["promotion_decision"] == "promote"
    assert "ionic_transport_full_evidence" in body["bundle"]["sections"]


def test_assemble_battery_li6ps5cl_rejects(client: TestClient) -> None:
    payload = {"fixture_key": "Li6PS5Cl", "interface_mode": "li_metal"}
    r = client.post("/v1/packets/assemble/battery", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["promotion_decision"] == "reject"


def test_assemble_battery_seed_coating_promotes(client: TestClient) -> None:
    payload = {
        "fixture_key": "Li-Mg-Zr-Cl-seed",
        "interface_mode": "coating_interlayer",
    }
    r = client.post("/v1/packets/assemble/battery", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["promotion_decision"] == "promote"


def test_assemble_battery_seed_li_metal_rejects(client: TestClient) -> None:
    payload = {"fixture_key": "Li-Mg-Zr-Cl-seed", "interface_mode": "li_metal"}
    r = client.post("/v1/packets/assemble/battery", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["promotion_decision"] == "reject"


def test_assemble_thermoelectric_bi2te3(client: TestClient) -> None:
    payload = {"fixture_key": "Bi2Te3"}
    r = client.post("/v1/packets/assemble/thermoelectric", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["objective"] == "thermoelectric_zt"
    assert "zt_assembly" in body["bundle"]["sections"]


def test_validate_endpoint(client: TestClient) -> None:
    # First assemble a packet, then validate it.
    payload = {"fixture_key": "LLZO"}
    r = client.post("/v1/packets/assemble/battery", json=payload)
    assert r.status_code == 200
    packet_dict = r.json()
    rv = client.post("/v1/packets/validate", json={"packet": packet_dict})
    assert rv.status_code == 200
    rep = rv.json()
    assert rep["overall_status"] == "pass"


def test_validate_endpoint_rejects_invalid_packet(client: TestClient) -> None:
    """Posting an empty packet is a 422."""
    rv = client.post("/v1/packets/validate", json={"packet": {}})
    assert rv.status_code == 422


def test_export_ro_crate(client: TestClient, tmp_path: Path) -> None:
    payload = {"fixture_key": "LLZO"}
    r = client.post("/v1/packets/assemble/battery", json=payload)
    packet_dict = r.json()
    out_dir = str(tmp_path / "crate")
    re = client.post(
        "/v1/packets/export-ro-crate",
        json={"packet": packet_dict, "out_dir": out_dir},
    )
    assert re.status_code == 200
    body = re.json()
    assert Path(body["crate_root"]).exists()
    assert Path(body["metadata_path"]).exists()
    assert body["section_count"] == 15
    # 15 sections + 1 packet root = 16 entries.
    assert body["entry_count"] == 16


def test_assemble_unknown_fixture_404(client: TestClient) -> None:
    r = client.post(
        "/v1/packets/assemble/battery",
        json={"fixture_key": "NotARealFixture"},
    )
    # Pydantic Literal validation triggers 422 before our handler raises.
    assert r.status_code in (404, 422)
