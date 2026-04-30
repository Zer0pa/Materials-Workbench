"""Unit tests for the NebMigrationBarrierAdapter."""

from __future__ import annotations

import pytest

from zer0pa_materials.adapters.ionic.base import (
    IONIC_TRANSPORT_SERVICE_REF,
    IonicJobParams,
)
from zer0pa_materials.adapters.ionic.neb import (
    NEB_BLOCKED_MANIFEST,
    NebMigrationBarrierAdapter,
    fixture_barrier_eV,
)


@pytest.fixture
def llzo_params() -> IonicJobParams:
    return IonicJobParams(
        structure_hash="sha256:d45cb2bfe5e76b86b365e1402e118ed32280049a62345c903558c6cfac04ef19",
        fixture_id="fixture:LLZO_cubic:d45cb2bf",
        candidate_id="candidate:LLZO/cubic",
    )


@pytest.fixture
def li6ps5cl_params() -> IonicJobParams:
    return IonicJobParams(
        structure_hash="sha256:8d7b217550c751a08bd6bc85d74a166ff0b4966266552d254ca53527607c40bc",
        fixture_id="fixture:Li6PS5Cl:8d7b2175",
        candidate_id="candidate:Li6PS5Cl/argyrodite",
    )


@pytest.fixture
def seed_params() -> IonicJobParams:
    return IonicJobParams(
        structure_hash="sha256:ea01c76f01f1427a5010cad97a984d3802c869f96b3726501897f5b08e3c138a",
        fixture_id="fixture:Li-Mg-Zr-Cl-seed:ea01c76f",
        candidate_id="candidate:Li-Mg-Zr-Cl/seed",
    )


def test_llzo_barrier_in_literature_range(llzo_params: IonicJobParams) -> None:
    env = NebMigrationBarrierAdapter().compute(llzo_params)
    barrier = env.output["migration_barrier_eV"]
    # LLZO literature canonical: ~0.30 eV; allow ±0.02 eV jitter.
    assert 0.28 <= barrier <= 0.32


def test_llzo_barrier_clears_target(llzo_params: IonicJobParams) -> None:
    """LLZO must clear the 0.35 eV target gate."""
    env = NebMigrationBarrierAdapter().compute(llzo_params)
    assert env.output["migration_barrier_eV"] <= 0.35


def test_li6ps5cl_barrier_in_literature_range(li6ps5cl_params: IonicJobParams) -> None:
    env = NebMigrationBarrierAdapter().compute(li6ps5cl_params)
    barrier = env.output["migration_barrier_eV"]
    # Li6PS5Cl literature canonical: ~0.25 eV; allow ±0.02 eV jitter.
    assert 0.23 <= barrier <= 0.27


def test_li6ps5cl_clears_stretch(li6ps5cl_params: IonicJobParams) -> None:
    """Li6PS5Cl should clear the 0.30 eV stretch (~0.25 eV)."""
    env = NebMigrationBarrierAdapter().compute(li6ps5cl_params)
    assert env.output["migration_barrier_eV"] <= 0.30


def test_seed_barrier_in_synthetic_range(seed_params: IonicJobParams) -> None:
    """Li-Mg-Zr-Cl seed: synthetic ~0.27 eV ±0.02 eV jitter."""
    env = NebMigrationBarrierAdapter().compute(seed_params)
    barrier = env.output["migration_barrier_eV"]
    assert 0.25 <= barrier <= 0.29


def test_unknown_fixture_default_above_target() -> None:
    """Unknown fixtures default above the 0.35 eV target."""
    p = IonicJobParams(
        structure_hash="sha256:" + "0" * 64,
        fixture_id=None,
        candidate_id="candidate:novel",
    )
    env = NebMigrationBarrierAdapter().compute(p)
    # Default 0.40 eV ±0.02 eV jitter, so should be > 0.35.
    assert env.output["migration_barrier_eV"] > 0.35


def test_envelope_carries_service_ref(llzo_params: IonicJobParams) -> None:
    """Every envelope must carry the IonicTransportService reference."""
    env = NebMigrationBarrierAdapter().compute(llzo_params)
    assert IONIC_TRANSPORT_SERVICE_REF in env.input_refs


def test_envelope_layer_is_ionic(llzo_params: IonicJobParams) -> None:
    env = NebMigrationBarrierAdapter().compute(llzo_params)
    assert env.layer == "ionic"


def test_envelope_has_assumptions(llzo_params: IonicJobParams) -> None:
    env = NebMigrationBarrierAdapter().compute(llzo_params)
    assert len(env.output["defect_disorder_assumptions"]) >= 1


def test_envelope_has_confidence(llzo_params: IonicJobParams) -> None:
    """Known fixture -> high confidence (>= 0.5)."""
    env = NebMigrationBarrierAdapter().compute(llzo_params)
    assert env.output["confidence"] >= 0.5


def test_unknown_fixture_low_confidence() -> None:
    p = IonicJobParams(structure_hash="sha256:" + "f" * 64, fixture_id=None)
    env = NebMigrationBarrierAdapter().compute(p)
    assert env.output["confidence"] < 0.5


def test_envelope_falsifier_items_present(llzo_params: IonicJobParams) -> None:
    env = NebMigrationBarrierAdapter().compute(llzo_params)
    item_names = {it.name for it in env.falsifier.items}
    assert "ionic.activation_barrier_target" in item_names
    assert "ionic.activation_barrier_stretch" in item_names


def test_blocked_source_manifest_exists() -> None:
    """A BlockedSourceManifest is provided for the parked real backend."""
    assert NEB_BLOCKED_MANIFEST.source_manifest_id == "src:blocked:neb-real-backend"
    assert NEB_BLOCKED_MANIFEST.blocker_reason == "unavailable_credentials"


def test_fixture_barrier_eV_helper() -> None:
    barrier = fixture_barrier_eV(
        "fixture:LLZO_cubic:d45cb2bf", "sha256:" + "a" * 64
    )
    assert 0.28 <= barrier <= 0.32


def test_fixture_barrier_unknown_returns_default() -> None:
    barrier = fixture_barrier_eV(None, "sha256:" + "b" * 64)
    assert barrier > 0.35  # default 0.40 ± jitter


def test_envelope_validates(llzo_params: IonicJobParams) -> None:
    """The envelope round-trips through Pydantic without error."""
    env = NebMigrationBarrierAdapter().compute(llzo_params)
    cd = env.canonical_dict()
    assert cd["layer"] == "ionic"
    assert "research_boundary" in cd


def test_deterministic_output(llzo_params: IonicJobParams) -> None:
    """Same inputs produce same barrier (modulo audit_record_id and run_id)."""
    a = NebMigrationBarrierAdapter().compute(llzo_params)
    b = NebMigrationBarrierAdapter().compute(llzo_params)
    assert a.output["migration_barrier_eV"] == b.output["migration_barrier_eV"]
