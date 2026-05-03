"""Verify Phase 0 extraction fixtures are well-formed.

The PRD §Phase 0 falsifier requires DOI/page/table/figure grounding for
every extracted property and unit normalisation. The three extraction
fixtures (LLZO, Li6PS5Cl, Li-Mg-Zr-Cl-seed) exercise the
``Phase0Output`` schema directly.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.unit.fixtures.conftest import FIXTURES_ROOT
from zer0pa_materials_workbench.envelope.layer_outputs import Phase0Output
from zer0pa_materials_workbench.envelope.units import parse_quantity

EXTRACTION_PATHS = sorted(
    p
    for p in (FIXTURES_ROOT / "extractions").rglob("extraction.json")
)


@pytest.mark.parametrize(
    "extraction_path", EXTRACTION_PATHS, ids=[p.parent.name for p in EXTRACTION_PATHS]
)
def test_extraction_validates_against_phase0_output(extraction_path: Path) -> None:
    """Phase0Output.model_validate must succeed (grounding is structurally required)."""
    payload = json.loads(extraction_path.read_text())
    payload.pop("research_boundary", None)
    out = Phase0Output.model_validate(payload)
    assert out.units_normalised is True
    assert out.contradictions_blocking == []
    assert len(out.extracted_properties) >= 1
    for prop in out.extracted_properties:
        assert prop.grounding.doi, "every property must have a non-empty DOI"


@pytest.mark.parametrize(
    "extraction_path", EXTRACTION_PATHS, ids=[p.parent.name for p in EXTRACTION_PATHS]
)
def test_extraction_units_are_parseable(extraction_path: Path) -> None:
    payload = json.loads(extraction_path.read_text())
    payload.pop("research_boundary", None)
    out = Phase0Output.model_validate(payload)
    for prop in out.extracted_properties:
        # parse_quantity should accept the unit string (canonical pint syntax).
        q = parse_quantity(f"{prop.value} {prop.unit}")
        assert float(q.magnitude) == prop.value


@pytest.mark.parametrize(
    "extraction_path", EXTRACTION_PATHS, ids=[p.parent.name for p in EXTRACTION_PATHS]
)
def test_extraction_falsifier_items_pass_for_well_formed_set(extraction_path: Path) -> None:
    payload = json.loads(extraction_path.read_text())
    payload.pop("research_boundary", None)
    out = Phase0Output.model_validate(payload)
    items = out.falsifier_items()
    statuses = {item.name: item.status for item in items}
    # Well-formed extractions: grounding required, units normalised, no contradictions.
    assert statuses["phase0.grounding_required"] == "pass"
    assert statuses["phase0.units_normalised"] == "pass"
    assert statuses["phase0.contradictions_resolved"] == "pass"


def test_extraction_count() -> None:
    """Exactly three extraction fixtures: LLZO, Li6PS5Cl, Li-Mg-Zr-Cl-seed."""
    names = {p.parent.name for p in EXTRACTION_PATHS}
    assert names == {"LLZO", "Li6PS5Cl", "Li-Mg-Zr-Cl-seed"}, (
        f"unexpected extraction set: {names}"
    )


def test_extraction_no_contradiction_in_synthetic_set() -> None:
    """No two synthetic extraction fixtures should silently disagree."""
    # We don't have cross-paper contradictions here (each extraction stands
    # alone), but the gate exists so future seeds are forced through this
    # check before promotion.
    for path in EXTRACTION_PATHS:
        payload = json.loads(path.read_text())
        payload.pop("research_boundary", None)
        out = Phase0Output.model_validate(payload)
        contradiction_flags = [p.contradiction_flag for p in out.extracted_properties]
        assert not any(contradiction_flags), (
            f"{path.parent.name}: at least one property has contradiction_flag=True"
        )
