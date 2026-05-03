"""Falsification-wave test: ungrounded_property fixture triggers EXACTLY reject_ungrounded_property.

The fixture at fixtures/negatives/ungrounded_property/ has grounding=null.
This test verifies that:
    1. The fixture triggers UngroundedPropertyError when passed to reject_ungrounded_property.
    2. No other Phase 0 falsifiers trigger on the same fixture (single-target invariant).
"""

import json
from pathlib import Path

import pytest

from zer0pa_materials_workbench.envelope.layer_outputs import Phase0ExtractedProperty, Phase0PropertyGrounding
from zer0pa_materials_workbench.falsifiers.phase0_falsifiers import (
    UngroundedPropertyError,
    UnparseableUnitError,
    UnresolvedContradictionError,
    reject_ungrounded_property,
    reject_unit_unparseable,
    reject_unresolved_contradiction,
)

_FIXTURE_PATH = (
    Path(__file__).parents[3]
    / "fixtures" / "negatives" / "ungrounded_property" / "extraction.json"
)


@pytest.fixture
def ungrounded_extraction() -> dict:
    return json.loads(_FIXTURE_PATH.read_text())


@pytest.fixture
def ungrounded_prop(ungrounded_extraction) -> Phase0ExtractedProperty:
    raw = ungrounded_extraction["extracted_properties"][0]
    # grounding is null in the fixture → we must handle this.
    grounding_raw = raw.get("grounding")
    if grounding_raw is None:
        # Simulate a property with genuinely missing grounding.
        grounding = Phase0PropertyGrounding(doi=None, page=None, table=None, figure=None)
    else:
        grounding = Phase0PropertyGrounding(**grounding_raw)
    return Phase0ExtractedProperty(
        property_name=raw["property_name"],
        value=raw["value"],
        unit=raw["unit"],
        grounding=grounding,
        contradiction_flag=raw.get("contradiction_flag", False),
    )


class TestUngroundedPropertyFixture:
    def test_reject_ungrounded_property_raises(self, ungrounded_prop):
        """The fixture must trigger EXACTLY UngroundedPropertyError."""
        with pytest.raises(UngroundedPropertyError):
            reject_ungrounded_property(ungrounded_prop)

    def test_reject_unit_unparseable_does_not_raise(self, ungrounded_prop):
        """The unit 'S/cm' is valid — unit falsifier must NOT trigger."""
        item = reject_unit_unparseable(ungrounded_prop)
        assert item.status == "pass"

    def test_reject_contradiction_does_not_raise(self, ungrounded_prop):
        """Single property — no contradiction possible."""
        item = reject_unresolved_contradiction([ungrounded_prop])
        assert item.status == "pass"

    def test_fixture_has_exactly_one_property(self, ungrounded_extraction):
        assert len(ungrounded_extraction["extracted_properties"]) == 1

    def test_fixture_grounding_is_null(self, ungrounded_extraction):
        grounding = ungrounded_extraction["extracted_properties"][0]["grounding"]
        assert grounding is None, (
            "The ungrounded_property fixture must have grounding=null to trigger "
            "the falsifier. Fixture integrity check failed."
        )

    def test_single_target_exactly(self, ungrounded_prop):
        """Only reject_ungrounded_property must fire; others must pass or be irrelevant."""
        triggered = []
        # Check ungrounded.
        try:
            reject_ungrounded_property(ungrounded_prop)
        except UngroundedPropertyError:
            triggered.append("reject_ungrounded_property")

        # Check unit (must NOT trigger).
        try:
            reject_unit_unparseable(ungrounded_prop)
        except UnparseableUnitError:
            triggered.append("reject_unit_unparseable")

        # Check contradiction (must NOT trigger).
        try:
            reject_unresolved_contradiction([ungrounded_prop])
        except UnresolvedContradictionError:
            triggered.append("reject_unresolved_contradiction")

        assert triggered == ["reject_ungrounded_property"], (
            f"Expected exactly ['reject_ungrounded_property'] to trigger, got {triggered}"
        )

    def test_manifest_negative_falsifier_target(self):
        manifest_path = _FIXTURE_PATH.parent / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        assert manifest["negative_falsifier_target"] == "ungrounded_property"
