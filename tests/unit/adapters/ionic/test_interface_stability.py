"""Unit tests for the InterfaceStabilityAdapter."""

from __future__ import annotations

from zer0pa_materials_workbench.adapters.ionic.base import (
    IONIC_TRANSPORT_SERVICE_REF,
    IonicJobParams,
)
from zer0pa_materials_workbench.adapters.ionic.interface_stability import (
    INTERFACE_STABILITY_BLOCKED_MANIFEST,
    InterfaceStabilityAdapter,
    classify_interface,
)


def test_llzo_li_metal_stable() -> None:
    p = IonicJobParams(
        structure_hash="sha256:" + "a" * 64,
        fixture_id="fixture:LLZO_cubic:d45cb2bf",
        interface_mode="li_metal",
    )
    env = InterfaceStabilityAdapter().compute(p)
    assert env.output["interface_stability"] == "li_metal_stable"


def test_li6ps5cl_li_metal_needs_coating() -> None:
    p = IonicJobParams(
        structure_hash="sha256:" + "b" * 64,
        fixture_id="fixture:Li6PS5Cl:8d7b2175",
        interface_mode="li_metal",
    )
    env = InterfaceStabilityAdapter().compute(p)
    assert env.output["interface_stability"] == "li_metal_unstable_coating_required"


def test_li6ps5cl_cathode_facing_unstable() -> None:
    p = IonicJobParams(
        structure_hash="sha256:" + "b" * 64,
        fixture_id="fixture:Li6PS5Cl:8d7b2175",
        interface_mode="cathode_facing",
    )
    env = InterfaceStabilityAdapter().compute(p)
    assert env.output["interface_stability"] == "cathode_facing_unstable"


def test_seed_li_metal_needs_coating() -> None:
    p = IonicJobParams(
        structure_hash="sha256:" + "c" * 64,
        fixture_id="fixture:Li-Mg-Zr-Cl-seed:ea01c76f",
        interface_mode="li_metal",
    )
    env = InterfaceStabilityAdapter().compute(p)
    assert env.output["interface_stability"] == "li_metal_unstable_coating_required"


def test_unknown_fixture_returns_unknown() -> None:
    p = IonicJobParams(structure_hash="sha256:" + "0" * 64, fixture_id=None)
    env = InterfaceStabilityAdapter().compute(p)
    assert env.output["interface_stability"] == "unknown"


def test_classify_interface_helper() -> None:
    cls = classify_interface("fixture:LLZO_cubic:d45cb2bf", "li_metal")
    assert cls == "li_metal_stable"


def test_classify_interface_unknown_fixture_returns_unknown() -> None:
    assert classify_interface(None, "li_metal") == "unknown"


def test_classify_interface_unknown_mode_returns_unknown() -> None:
    cls = classify_interface("fixture:LLZO_cubic:d45cb2bf", "weird-mode")
    assert cls == "unknown"


def test_envelope_layer_is_ionic() -> None:
    p = IonicJobParams(
        structure_hash="sha256:" + "a" * 64,
        fixture_id="fixture:LLZO_cubic:d45cb2bf",
    )
    env = InterfaceStabilityAdapter().compute(p)
    assert env.layer == "ionic"


def test_envelope_carries_service_ref() -> None:
    p = IonicJobParams(
        structure_hash="sha256:" + "a" * 64,
        fixture_id="fixture:LLZO_cubic:d45cb2bf",
    )
    env = InterfaceStabilityAdapter().compute(p)
    assert IONIC_TRANSPORT_SERVICE_REF in env.input_refs


def test_blocked_source_manifest_exists() -> None:
    assert (
        INTERFACE_STABILITY_BLOCKED_MANIFEST.source_manifest_id
        == "src:blocked:interface-stability-real-backend"
    )


def test_coating_interlayer_mode_returns_li_metal_class() -> None:
    """Coating mode reports the underlying Li-metal classification."""
    p = IonicJobParams(
        structure_hash="sha256:" + "b" * 64,
        fixture_id="fixture:Li6PS5Cl:8d7b2175",
        interface_mode="coating_interlayer",
    )
    env = InterfaceStabilityAdapter().compute(p)
    assert env.output["interface_stability"] == "li_metal_unstable_coating_required"


def test_envelope_records_interface_mode_in_assumptions() -> None:
    p = IonicJobParams(
        structure_hash="sha256:" + "a" * 64,
        fixture_id="fixture:LLZO_cubic:d45cb2bf",
        interface_mode="coating_interlayer",
    )
    env = InterfaceStabilityAdapter().compute(p)
    assumptions = env.output["defect_disorder_assumptions"]
    assert any("interface_mode=coating_interlayer" in a for a in assumptions)
