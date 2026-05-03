"""Falsification wave test: fixtures/negatives/unstable_phonon/ must trigger EXACTLY
the dynamical_stability falsifier.

PRD §L1.5 Falsifiers: "Non-acoustic imaginary mode magnitude > 0.25 THz after
acoustic sum rule and NAC review fails dynamical stability."

The fixture at ``fixtures/negatives/unstable_phonon/phonon_spectrum.json``
encodes:
  - imaginary_mode_max_THz: 1.42 (well above 0.25 THz threshold)
  - mlip_vs_dft_force_rmse_eV_per_Ang: 0.012 (below 0.05 eV/Å — PASS)
  - qmesh_convergence_pct: 4.5 (below 10% — PASS)

The design ensures that ONLY the dynamical_stability falsifier fires,
and no other falsifier. This is the adversarial gate.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from zer0pa_materials_workbench.adapters.l1_5.base import L15JobParams, make_l15_envelope
from zer0pa_materials_workbench.envelope import (
    Envelope,
    L15PhononOutput,
)
from zer0pa_materials_workbench.falsifiers.l1_5_falsifiers import (
    dynamical_stability,
    mlip_dft_force_rmse,
    phonon_does_not_substitute_for_ionic,
    q_mesh_convergence,
)

# Path to the negative fixture
FIXTURE_DIR = (
    Path(__file__).parents[3] / "fixtures" / "negatives" / "unstable_phonon"
)
FIXTURE_PATH = FIXTURE_DIR / "phonon_spectrum.json"


@pytest.fixture(scope="module")
def unstable_fixture_data() -> dict:
    """Load the unstable phonon negative fixture."""
    assert FIXTURE_PATH.exists(), (
        f"Unstable phonon fixture not found at {FIXTURE_PATH}. "
        "The fixture must exist before the falsification wave runs."
    )
    with FIXTURE_PATH.open() as f:
        return json.load(f)


@pytest.fixture(scope="module")
def unstable_envelope(unstable_fixture_data: dict) -> Envelope:
    """Build a minimal L1.5 envelope from the unstable phonon fixture data."""
    output = L15PhononOutput(
        imaginary_mode_max_THz=unstable_fixture_data["imaginary_mode_max_THz"],
        mlip_vs_dft_force_rmse_eV_per_Ang=unstable_fixture_data.get(
            "mlip_vs_dft_force_rmse_eV_per_Ang"
        ),
        qmesh_convergence_pct=unstable_fixture_data.get("qmesh_convergence_pct"),
        seebeck_uV_per_K=unstable_fixture_data.get("seebeck_uV_per_K"),
        electrical_conductivity_S_per_cm=unstable_fixture_data.get(
            "electrical_conductivity_S_per_cm"
        ),
        thermal_conductivity_W_per_mK=unstable_fixture_data.get("thermal_conductivity_W_per_mK"),
        zt=unstable_fixture_data.get("zt"),
    )
    params = L15JobParams(
        structure_hash="sha256:unstable_phonon_negative_fixture_hash00001",
        material_id=None,
        candidate_id="candidate:unstable-phonon/negative-fixture",
        campaign_id="campaign:falsification-wave",
    )
    return make_l15_envelope(
        output=output,
        params=params,
        adapter_name="TestFalsificationAdapter",
        adapter_version="0.0.1",
        backend="stub",
        engine="test",
    )


class TestUnstablePhononFixtureValues:
    """Verify the fixture data encodes the intended adversarial values."""

    def test_fixture_exists(self, unstable_fixture_data: dict) -> None:
        assert "imaginary_mode_max_THz" in unstable_fixture_data

    def test_imaginary_mode_above_threshold(self, unstable_fixture_data: dict) -> None:
        """The fixture's imaginary mode MUST be above 0.25 THz."""
        assert unstable_fixture_data["imaginary_mode_max_THz"] > 0.25, (
            f"Fixture imaginary mode {unstable_fixture_data['imaginary_mode_max_THz']} THz "
            "is NOT above the 0.25 THz threshold — the falsifier will not fire."
        )

    def test_mlip_rmse_below_threshold(self, unstable_fixture_data: dict) -> None:
        """MLIP RMSE must be BELOW 0.05 eV/Å so ONLY the phonon falsifier fires."""
        rmse = unstable_fixture_data.get("mlip_vs_dft_force_rmse_eV_per_Ang")
        if rmse is not None:
            assert rmse <= 0.05, (
                f"Fixture MLIP RMSE {rmse} eV/Å exceeds 0.05 — "
                "this would fire the MLIP falsifier in addition to the phonon one."
            )

    def test_qmesh_convergence_below_threshold(self, unstable_fixture_data: dict) -> None:
        """q-mesh convergence must be BELOW 10% so ONLY the phonon falsifier fires."""
        conv = unstable_fixture_data.get("qmesh_convergence_pct")
        if conv is not None:
            assert conv < 10.0, (
                f"Fixture q-mesh convergence {conv}% exceeds 10% — "
                "this would fire the convergence falsifier in addition to the phonon one."
            )

    def test_no_ionic_conductivity_in_fixture(self, unstable_fixture_data: dict) -> None:
        """Fixture must not claim ionic conductivity."""
        ionic = unstable_fixture_data.get("ionic_conductivity_S_per_cm")
        assert ionic is None


class TestDynamicalStabilityFires:
    """The dynamical_stability falsifier MUST fire (fail) for the unstable fixture."""

    def test_dynamical_stability_fails(self, unstable_envelope: Envelope) -> None:
        item = dynamical_stability(unstable_envelope)
        assert item.status == "fail", (
            f"dynamical_stability returned {item.status!r} for the unstable phonon fixture. "
            f"Expected 'fail'. Actual imaginary mode: {item.actual} THz."
        )

    def test_dynamical_stability_actual_matches_fixture(
        self, unstable_envelope: Envelope, unstable_fixture_data: dict
    ) -> None:
        """The falsifier must record the exact fixture value as its actual."""
        item = dynamical_stability(unstable_envelope)
        assert abs(float(item.actual) - unstable_fixture_data["imaginary_mode_max_THz"]) < 1e-9

    def test_dynamical_stability_rationale_present(
        self, unstable_envelope: Envelope
    ) -> None:
        """A fail result must include a rationale."""
        item = dynamical_stability(unstable_envelope)
        assert item.rationale is not None
        assert len(item.rationale) > 10


class TestOtherFalsifiersPass:
    """ALL other falsifiers must PASS for the unstable phonon fixture.

    This ensures that dynamical_stability is the SOLE trigger for the negative fixture.
    """

    def test_mlip_dft_force_rmse_passes(self, unstable_envelope: Envelope) -> None:
        item = mlip_dft_force_rmse(unstable_envelope)
        # blocked is also acceptable if the field is not present;
        # what matters is it does NOT fail
        assert item.status in ("pass", "blocked"), (
            f"mlip_dft_force_rmse fired with {item.status!r} for the unstable phonon fixture. "
            "This falsifier should PASS (or be blocked if field absent)."
        )

    def test_q_mesh_convergence_passes(self, unstable_envelope: Envelope) -> None:
        item = q_mesh_convergence(unstable_envelope)
        assert item.status in ("pass", "blocked"), (
            f"q_mesh_convergence fired with {item.status!r} for the unstable phonon fixture. "
            "This falsifier should PASS (or be blocked if field absent)."
        )

    def test_phonon_not_ionic_passes(self, unstable_envelope: Envelope) -> None:
        item = phonon_does_not_substitute_for_ionic(unstable_envelope)
        assert item.status == "pass", (
            f"phonon_does_not_substitute_for_ionic returned {item.status!r}. "
            "This falsifier must always pass for L1.5 envelopes."
        )


class TestEnvelopeFalsifierRollup:
    """The envelope's rolled-up falsifier status must be 'fail'."""

    def test_envelope_falsifier_status_is_fail(
        self, unstable_envelope: Envelope
    ) -> None:
        """The envelope built from the negative fixture must have status=fail."""
        # Check the imaginary mode falsifier item in the envelope (FalsifierBlock.items are FalsifierItem objects)
        imag_item = next(
            (i for i in unstable_envelope.falsifier.items
             if i.name == "l15.imaginary_mode_threshold"),
            None,
        )
        assert imag_item is not None, "l15.imaginary_mode_threshold item missing from envelope"
        assert imag_item.status == "fail", (
            f"Expected l15.imaginary_mode_threshold to be 'fail', got {imag_item.status!r}"
        )

    def test_envelope_overall_status_is_fail(
        self, unstable_envelope: Envelope
    ) -> None:
        """The rolled-up envelope falsifier status must be 'fail'."""
        assert unstable_envelope.falsifier.status == "fail"
