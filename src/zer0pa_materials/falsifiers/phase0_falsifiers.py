"""Phase 0 falsifiers (PRD §Phase 0 / L6 Falsifiers).

Functions:
    reject_ungrounded_property(prop)       -- fails if no DOI + span grounding.
    reject_unit_unparseable(prop)          -- fails if parse_quantity raises.
    reject_unresolved_contradiction(props) -- fails if incompatible values clash.
    assert_kg_nodes_for(envelope, kg)      -- verifies KG writes are present.
"""

from __future__ import annotations

from typing import Any

from zer0pa_materials.audit.kg import KGEdgeType, KGNodeType, MaterialsKG
from zer0pa_materials.boundary import RESEARCH_BOUNDARY
from zer0pa_materials.envelope.envelope import Envelope
from zer0pa_materials.envelope.falsifier import FalsifierItem, FalsifierStatus
from zer0pa_materials.envelope.layer_outputs import Phase0ExtractedProperty
from zer0pa_materials.envelope.units import DimensionalityError, parse_quantity


# ---------------------------------------------------------------------------
# reject_ungrounded_property
# ---------------------------------------------------------------------------


class UngroundedPropertyError(ValueError):
    """Raised when a Phase 0 property lacks required DOI / span grounding."""


def reject_ungrounded_property(prop: Phase0ExtractedProperty) -> FalsifierItem:
    """Return a FAIL FalsifierItem if the property has no valid grounding.

    Grounding is valid when ``prop.grounding`` is not None AND
    ``prop.grounding.doi`` is a non-empty string AND at least one of
    ``page``, ``table``, ``figure`` is not None.

    Raises:
        UngroundedPropertyError — when grounding is missing. Callers that
        treat this as a hard gate should catch and record in the audit log.
    """
    g = prop.grounding if hasattr(prop, "grounding") else None

    has_doi = bool(g and g.doi and g.doi.strip())
    has_span = bool(g and (g.page is not None or g.table is not None or g.figure is not None))

    if not has_doi or not has_span:
        raise UngroundedPropertyError(
            f"Property {prop.property_name!r} lacks required grounding: "
            f"has_doi={has_doi}, has_span={has_span}. "
            "Each extracted property must cite a DOI plus at least one of "
            "page / table / figure."
        )

    return FalsifierItem(
        name="phase0.grounding_required",
        threshold="doi non-empty AND at least one of page/table/figure",
        actual={"doi": g.doi, "page": g.page, "table": g.table, "figure": g.figure},
        status="pass",
    )


# ---------------------------------------------------------------------------
# reject_unit_unparseable
# ---------------------------------------------------------------------------


class UnparseableUnitError(ValueError):
    """Raised when parse_quantity cannot handle a property's value_with_unit."""


def reject_unit_unparseable(prop: Phase0ExtractedProperty) -> FalsifierItem:
    """Return a FAIL FalsifierItem if the property's unit cannot be parsed.

    Attempts ``parse_quantity(f"{prop.value} {prop.unit}")`` using the
    canonical pint registry. If that raises, raises UnparseableUnitError.

    Raises:
        UnparseableUnitError — when the unit string is not parseable.
    """
    try:
        parse_quantity(f"{prop.value} {prop.unit}")
    except (DimensionalityError, Exception) as exc:
        raise UnparseableUnitError(
            f"Property {prop.property_name!r} unit {prop.unit!r} is not parseable "
            f"by the canonical pint registry: {exc}"
        ) from exc

    return FalsifierItem(
        name="phase0.units_normalised",
        threshold="parse_quantity succeeds",
        actual=f"{prop.value} {prop.unit}",
        status="pass",
    )


# ---------------------------------------------------------------------------
# reject_unresolved_contradiction
# ---------------------------------------------------------------------------


class UnresolvedContradictionError(ValueError):
    """Raised when two extractions claim incompatible values without differing conditions."""


def reject_unresolved_contradiction(
    props: list[Phase0ExtractedProperty],
    tolerance_pct: float = 20.0,
) -> FalsifierItem:
    """Return FAIL FalsifierItem if any two props for the same (material, property_name)
    have values differing by more than ``tolerance_pct``% without the
    ``contradiction_flag`` being set (which would signal a known discrepancy
    with explicitly differing conditions).

    PRD spec: "fails if two extractions claim incompatible values for
    (material_id, property_name) without differing conditions."

    Args:
        props: list of Phase0ExtractedProperty from the same material system.
        tolerance_pct: percentage difference threshold above which values
                       are treated as contradictory (default 20%).

    Raises:
        UnresolvedContradictionError — when a contradiction is detected that
        is not flagged with contradiction_flag=True.
    """
    # Group by property_name.
    by_name: dict[str, list[Phase0ExtractedProperty]] = {}
    for p in props:
        by_name.setdefault(p.property_name, []).append(p)

    contradictions: list[str] = []
    for prop_name, group in by_name.items():
        if len(group) < 2:
            continue
        # Check all pairs.
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                a, b = group[i], group[j]
                # Skip if either is marked as a known contradiction with differing conditions.
                if a.contradiction_flag or b.contradiction_flag:
                    continue
                # Units must be the same to compare values numerically.
                if a.unit != b.unit:
                    continue
                ref = abs(a.value)
                if ref < 1e-30:
                    continue
                pct_diff = abs(a.value - b.value) / ref * 100.0
                if pct_diff > tolerance_pct:
                    contradictions.append(
                        f"{prop_name}: {a.value} vs {b.value} {a.unit} "
                        f"({pct_diff:.1f}% > {tolerance_pct}%)"
                    )

    if contradictions:
        raise UnresolvedContradictionError(
            f"Unresolved contradiction(s) in Phase 0 extractions: "
            + "; ".join(contradictions)
        )

    return FalsifierItem(
        name="phase0.contradictions_resolved",
        threshold=f"no pair differs by > {tolerance_pct}% without contradiction_flag",
        actual={"property_count": len(props), "groups_checked": len(by_name)},
        status="pass",
    )


# ---------------------------------------------------------------------------
# assert_kg_nodes_for
# ---------------------------------------------------------------------------


class KGWriteError(ValueError):
    """Raised when required KG nodes are missing for a Phase 0 envelope."""


def assert_kg_nodes_for(envelope: Envelope, kg: MaterialsKG) -> list[FalsifierItem]:
    """Verify that the required KG writes for a Phase 0 extraction are present.

    PRD-mandated KG writes for Phase 0:
        - Each citation → LiteratureSource node with DOI URN.
        - Each extracted property → PropertyObservation node with EMMO mapping.
        - Edge: LiteratureSource -[CITES]-> PropertyObservation.
        - Edge: PropertyObservation -[MAPS_TO_ONTOLOGY]-> OntologyTerm.

    This function checks that at least one LiteratureSource node and at least
    one PropertyObservation node exist in the KG. Full structural checks
    (edge completeness, EMMO IRI validity) are enforced in the KG write path
    via KGEdgeType enum validation.

    Args:
        envelope: Phase 0 Envelope (must have layer="phase0").
        kg: MaterialsKG instance to query.

    Returns:
        list[FalsifierItem] — two items: one for LiteratureSource, one for
        PropertyObservation.

    Raises:
        KGWriteError — when required nodes are missing.
    """
    if envelope.layer != "phase0":
        raise ValueError(f"assert_kg_nodes_for requires layer=phase0, got {envelope.layer!r}")

    # Count nodes by type.
    lit_nodes = [
        n for n in kg.iter_nodes()
        if n.node_type == KGNodeType.LiteratureSource
    ]
    prop_nodes = [
        n for n in kg.iter_nodes()
        if n.node_type == KGNodeType.PropertyObservation
    ]

    items: list[FalsifierItem] = []

    lit_status: FalsifierStatus = "pass" if lit_nodes else "fail"
    items.append(
        FalsifierItem(
            name="phase0.kg_literature_source_written",
            threshold="at least one LiteratureSource node",
            actual={"count": len(lit_nodes)},
            status=lit_status,
        )
    )

    prop_status: FalsifierStatus = "pass" if prop_nodes else "fail"
    items.append(
        FalsifierItem(
            name="phase0.kg_property_observation_written",
            threshold="at least one PropertyObservation node",
            actual={"count": len(prop_nodes)},
            status=prop_status,
        )
    )

    if not lit_nodes or not prop_nodes:
        missing = []
        if not lit_nodes:
            missing.append("LiteratureSource")
        if not prop_nodes:
            missing.append("PropertyObservation")
        raise KGWriteError(
            f"Phase 0 KG write missing node type(s): {', '.join(missing)}. "
            "Adapters must write these nodes before promoting the envelope."
        )

    return items
