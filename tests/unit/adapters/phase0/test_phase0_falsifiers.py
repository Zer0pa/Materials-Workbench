"""Unit tests for Phase 0 falsifiers."""

import pytest

from zer0pa_materials.envelope.layer_outputs import Phase0ExtractedProperty, Phase0PropertyGrounding
from zer0pa_materials.falsifiers.phase0_falsifiers import (
    UngroundedPropertyError,
    UnparseableUnitError,
    UnresolvedContradictionError,
    reject_ungrounded_property,
    reject_unit_unparseable,
    reject_unresolved_contradiction,
)


def _make_prop(
    property_name: str = "ionic_conductivity",
    value: float = 1e-3,
    unit: str = "S/cm",
    doi: str | None = "10.1000/test",
    page: int | None = 1,
    table: str | None = None,
    figure: str | None = None,
    contradiction_flag: bool = False,
) -> Phase0ExtractedProperty:
    grounding = Phase0PropertyGrounding(doi=doi, page=page, table=table, figure=figure)
    return Phase0ExtractedProperty(
        property_name=property_name,
        value=value,
        unit=unit,
        grounding=grounding,
        contradiction_flag=contradiction_flag,
    )


# ---------------------------------------------------------------------------
# reject_ungrounded_property
# ---------------------------------------------------------------------------

class TestRejectUngroundedProperty:
    def test_pass_with_doi_and_page(self):
        prop = _make_prop(doi="10.1000/test", page=1)
        item = reject_ungrounded_property(prop)
        assert item.status == "pass"

    def test_pass_with_doi_and_table(self):
        prop = _make_prop(doi="10.1000/test", page=None, table="Table 1")
        item = reject_ungrounded_property(prop)
        assert item.status == "pass"

    def test_pass_with_doi_and_figure(self):
        prop = _make_prop(doi="10.1000/test", page=None, figure="Figure 2")
        item = reject_ungrounded_property(prop)
        assert item.status == "pass"

    def test_fail_no_doi(self):
        prop = _make_prop(doi=None, page=1)
        with pytest.raises(UngroundedPropertyError, match="has_doi=False"):
            reject_ungrounded_property(prop)

    def test_fail_no_span(self):
        prop = _make_prop(doi="10.1000/test", page=None, table=None, figure=None)
        with pytest.raises(UngroundedPropertyError, match="has_span=False"):
            reject_ungrounded_property(prop)

    def test_fail_no_doi_no_span(self):
        prop = _make_prop(doi=None, page=None, table=None, figure=None)
        with pytest.raises(UngroundedPropertyError):
            reject_ungrounded_property(prop)

    def test_item_name_is_correct(self):
        prop = _make_prop()
        item = reject_ungrounded_property(prop)
        assert item.name == "phase0.grounding_required"


# ---------------------------------------------------------------------------
# reject_unit_unparseable
# ---------------------------------------------------------------------------

class TestRejectUnitUnparseable:
    def test_pass_s_per_cm(self):
        prop = _make_prop(value=1e-3, unit="S/cm")
        item = reject_unit_unparseable(prop)
        assert item.status == "pass"

    def test_pass_ev(self):
        prop = _make_prop(value=0.34, unit="eV")
        item = reject_unit_unparseable(prop)
        assert item.status == "pass"

    def test_pass_angstrom(self):
        prop = _make_prop(value=12.971, unit="angstrom")
        item = reject_unit_unparseable(prop)
        assert item.status == "pass"

    def test_fail_garbage_unit(self):
        prop = _make_prop(value=1.0, unit="ZZZNOT_A_UNIT_XYZ")
        with pytest.raises(UnparseableUnitError, match="not parseable"):
            reject_unit_unparseable(prop)

    def test_item_name_is_correct(self):
        prop = _make_prop(value=0.5, unit="eV")
        item = reject_unit_unparseable(prop)
        assert item.name == "phase0.units_normalised"


# ---------------------------------------------------------------------------
# reject_unresolved_contradiction
# ---------------------------------------------------------------------------

class TestRejectUnresolvedContradiction:
    def test_pass_single_property(self):
        props = [_make_prop(value=1e-3, unit="S/cm")]
        item = reject_unresolved_contradiction(props)
        assert item.status == "pass"

    def test_pass_two_properties_different_names(self):
        props = [
            _make_prop("ionic_conductivity", value=1e-3, unit="S/cm"),
            _make_prop("activation_energy", value=0.34, unit="eV"),
        ]
        item = reject_unresolved_contradiction(props)
        assert item.status == "pass"

    def test_pass_two_close_values(self):
        # 3e-4 vs 3.5e-4 — only ~17% difference, below 20% default.
        props = [
            _make_prop("ionic_conductivity", value=3e-4, unit="S/cm"),
            _make_prop("ionic_conductivity", value=3.5e-4, unit="S/cm"),
        ]
        item = reject_unresolved_contradiction(props)
        assert item.status == "pass"

    def test_fail_contradictory_values(self):
        props = [
            _make_prop("ionic_conductivity", value=1e-3, unit="S/cm"),
            _make_prop("ionic_conductivity", value=1e-6, unit="S/cm"),
        ]
        with pytest.raises(UnresolvedContradictionError):
            reject_unresolved_contradiction(props)

    def test_pass_when_contradiction_flagged(self):
        # If either prop has contradiction_flag=True, the pair is skipped.
        props = [
            _make_prop("ionic_conductivity", value=1e-3, unit="S/cm", contradiction_flag=True),
            _make_prop("ionic_conductivity", value=1e-6, unit="S/cm"),
        ]
        item = reject_unresolved_contradiction(props)
        assert item.status == "pass"

    def test_pass_different_units_not_compared(self):
        # Different units → not comparable → no contradiction check.
        props = [
            _make_prop("ionic_conductivity", value=1e-3, unit="S/cm"),
            _make_prop("ionic_conductivity", value=1.0, unit="mS/cm"),
        ]
        item = reject_unresolved_contradiction(props)
        assert item.status == "pass"

    def test_item_name_is_correct(self):
        props = [_make_prop(value=1e-3, unit="S/cm")]
        item = reject_unresolved_contradiction(props)
        assert item.name == "phase0.contradictions_resolved"
