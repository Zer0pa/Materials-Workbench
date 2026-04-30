"""Unit tests for the ElectrochemicalWindowAdapter."""

from __future__ import annotations

import pytest

from zer0pa_materials.adapters.ionic.base import (
    IONIC_TRANSPORT_SERVICE_REF,
    IonicJobParams,
)
from zer0pa_materials.adapters.ionic.electrochemical_window import (
    ELECTROCHEMICAL_WINDOW_BLOCKED_MANIFEST,
    ElectrochemicalWindowAdapter,
    fixture_window_V,
)


def test_llzo_window_high_oxidation() -> None:
    p = IonicJobParams(
        structure_hash="sha256:" + "a" * 64,
        fixture_id="fixture:LLZO_cubic:d45cb2bf",
        candidate_id="candidate:LLZO/cubic",
    )
    env = ElectrochemicalWindowAdapter().compute(p)
    red, ox = env.output["electrochemical_window_V_vs_LiLi"]
    assert ox >= 4.0  # LLZO clears the 4 V gate
    assert red < 1.0  # LLZO stable down to low V


def test_li6ps5cl_oxidation_below_threshold() -> None:
    p = IonicJobParams(
        structure_hash="sha256:" + "b" * 64,
        fixture_id="fixture:Li6PS5Cl:8d7b2175",
        candidate_id="candidate:Li6PS5Cl",
    )
    env = ElectrochemicalWindowAdapter().compute(p)
    red, ox = env.output["electrochemical_window_V_vs_LiLi"]
    assert ox < 4.0  # Li6PS5Cl fails the 4 V gate (literature ~2.5)


def test_seed_window_marginal() -> None:
    """Li-Mg-Zr-Cl seed: oxidation ~4.3 V (just above 4 V)."""
    p = IonicJobParams(
        structure_hash="sha256:" + "c" * 64,
        fixture_id="fixture:Li-Mg-Zr-Cl-seed:ea01c76f",
        candidate_id="candidate:Li-Mg-Zr-Cl/seed",
    )
    env = ElectrochemicalWindowAdapter().compute(p)
    red, ox = env.output["electrochemical_window_V_vs_LiLi"]
    assert ox >= 4.0


def test_unknown_fixture_default_window() -> None:
    p = IonicJobParams(structure_hash="sha256:" + "0" * 64, fixture_id=None)
    env = ElectrochemicalWindowAdapter().compute(p)
    red, ox = env.output["electrochemical_window_V_vs_LiLi"]
    # Default window is 2.0–3.5 V, fails the 4 V gate.
    assert ox < 4.0


def test_envelope_layer_is_ionic() -> None:
    p = IonicJobParams(
        structure_hash="sha256:" + "a" * 64,
        fixture_id="fixture:LLZO_cubic:d45cb2bf",
    )
    env = ElectrochemicalWindowAdapter().compute(p)
    assert env.layer == "ionic"


def test_envelope_carries_service_ref() -> None:
    p = IonicJobParams(
        structure_hash="sha256:" + "a" * 64,
        fixture_id="fixture:LLZO_cubic:d45cb2bf",
    )
    env = ElectrochemicalWindowAdapter().compute(p)
    assert IONIC_TRANSPORT_SERVICE_REF in env.input_refs


def test_blocked_source_manifest_exists() -> None:
    assert (
        ELECTROCHEMICAL_WINDOW_BLOCKED_MANIFEST.source_manifest_id
        == "src:blocked:electrochemical-window-real-backend"
    )


def test_fixture_window_helper_known() -> None:
    assert fixture_window_V("fixture:LLZO_cubic:d45cb2bf") == (0.05, 6.00)


def test_fixture_window_helper_unknown_default() -> None:
    assert fixture_window_V(None) == (2.0, 3.5)


def test_oxidative_stability_falsifier_present_and_pass_for_llzo() -> None:
    p = IonicJobParams(
        structure_hash="sha256:" + "a" * 64,
        fixture_id="fixture:LLZO_cubic:d45cb2bf",
    )
    env = ElectrochemicalWindowAdapter().compute(p)
    for it in env.falsifier.items:
        if it.name == "ionic.oxidative_stability":
            assert it.status == "pass"
            return
    raise AssertionError("oxidative_stability falsifier item missing")


def test_oxidative_stability_falsifier_fail_for_li6ps5cl() -> None:
    p = IonicJobParams(
        structure_hash="sha256:" + "b" * 64,
        fixture_id="fixture:Li6PS5Cl:8d7b2175",
    )
    env = ElectrochemicalWindowAdapter().compute(p)
    for it in env.falsifier.items:
        if it.name == "ionic.oxidative_stability":
            assert it.status == "fail"
            return
    raise AssertionError("oxidative_stability falsifier item missing")
