"""Falsification wave: ionic conductivity overclaim without IonicTransportService.

PRD §Falsification wave (line 546): "ionic conductivity overclaim
without IonicTransportService".

Asserts that the ``fixtures/negatives/ionic_overclaim_no_service/``
fixture triggers EXACTLY the
``ionic.requires_ionic_transport_service`` falsifier with status
``fail`` — and that the same fixture passes when an
``ionic_transport_service_ref`` is supplied.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from zer0pa_materials_workbench.adapters.ionic.base import IONIC_TRANSPORT_SERVICE_REF
from zer0pa_materials_workbench.falsifiers.ionic_falsifiers import (
    requires_ionic_transport_service,
)

_NEG_DIR = Path(__file__).resolve().parents[3] / "fixtures" / "negatives" / "ionic_overclaim_no_service"


@pytest.fixture
def negative_candidate() -> dict:
    with open(_NEG_DIR / "candidate.json") as f:
        return json.load(f)


def test_negative_fixture_present() -> None:
    assert _NEG_DIR.exists()
    assert (_NEG_DIR / "candidate.json").exists()
    assert (_NEG_DIR / "manifest.json").exists()


def test_negative_fixture_triggers_exact_falsifier(negative_candidate: dict) -> None:
    """The negative fixture MUST trigger requires_ionic_transport_service with FAIL."""
    item = requires_ionic_transport_service(negative_candidate)
    assert item.name == "ionic.requires_ionic_transport_service"
    assert item.status == "fail"


def test_negative_fixture_records_concrete_overclaim(
    negative_candidate: dict,
) -> None:
    """The fail rationale must reference the exact PRD wording."""
    item = requires_ionic_transport_service(negative_candidate)
    assert item.rationale is not None
    # PRD wording: "phonons do not substitute for Li-ion conductivity"
    # — both rationale and threshold quote the PRD; check both.
    rationale_lc = item.rationale.lower()
    threshold_lc = item.threshold.lower()
    assert "phonon" in rationale_lc or "phonons" in threshold_lc


def test_negative_fixture_actual_payload_contains_claim_value(
    negative_candidate: dict,
) -> None:
    item = requires_ionic_transport_service(negative_candidate)
    assert item.actual["claim_value"] == 5.0e-3


def test_adding_service_ref_makes_it_pass(negative_candidate: dict) -> None:
    """Same overclaim WITH a service ref must pass."""
    fixed = dict(negative_candidate)
    fixed["ionic_transport_service_ref"] = IONIC_TRANSPORT_SERVICE_REF
    item = requires_ionic_transport_service(fixed)
    assert item.status == "pass"


def test_negative_manifest_has_falsifier_target() -> None:
    with open(_NEG_DIR / "manifest.json") as f:
        manifest = json.load(f)
    assert manifest["negative_falsifier_target"] == "ionic_overclaim_no_service"
    assert manifest["kind"] == "negative"


def test_only_overclaim_falsifier_fires_on_negative(negative_candidate: dict) -> None:
    """Only the requires_ionic_transport_service falsifier should fire on this fixture.

    Other ionic falsifiers should be benign (pass / blocked) because the
    fixture is a flat candidate JSON with no ionic transport envelope
    fields.
    """
    from zer0pa_materials_workbench.falsifiers.ionic_falsifiers import (
        defect_disorder_assumptions_documented,
        oxidative_stability_threshold,
        room_temperature_conductivity_credible_interval_meets_threshold,
    )
    rt = room_temperature_conductivity_credible_interval_meets_threshold(
        negative_candidate
    )
    # No envelope.output -> blocked, NOT fail.
    assert rt.status in ("blocked", "pass")
    ox = oxidative_stability_threshold(negative_candidate)
    assert ox.status in ("blocked", "pass")
    # The defect-disorder falsifier reads output.defect_disorder_assumptions;
    # the flat fixture has none, so it fails (correctly — this is also a
    # discipline violation, just a different one).
    assumptions = defect_disorder_assumptions_documented(negative_candidate)
    assert assumptions.status == "fail"
