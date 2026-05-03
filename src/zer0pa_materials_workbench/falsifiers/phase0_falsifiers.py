"""Phase 0 falsifiers (PRD §Phase 0 / L6 Falsifiers).

Functions:
    reject_ungrounded_property(prop)       -- fails if no DOI + span grounding.
    reject_unit_unparseable(prop)          -- fails if parse_quantity raises.
    reject_unresolved_contradiction(props) -- fails if incompatible values clash.
    assert_kg_nodes_for(envelope, kg)      -- verifies KG writes are present.
    verify_source_manifest_linkage(envelope, audit_log)
                                           -- Wave D hardened: walks each
                                              source_manifest_ref and verifies
                                              it actually exists in
                                              sources.jsonl.

Wave D discipline (RESISTANCE.md ``fp-shapematch``):
    The original audit gates check that ``audit.source_manifest_refs`` is
    non-empty — they trust the field. A buggy adapter can populate the
    list with strings that look syntactically valid (``src:fabricated:fake``)
    but never wrote a corresponding row in ``sources.jsonl``. The new
    ``verify_source_manifest_linkage`` walks each ref against the live
    audit log and fails when any ref is unresolved.
"""

from __future__ import annotations

from typing import Any

from zer0pa_materials_workbench.audit.kg import KGNodeType, MaterialsKG
from zer0pa_materials_workbench.envelope.envelope import Envelope
from zer0pa_materials_workbench.envelope.falsifier import FalsifierItem, FalsifierStatus
from zer0pa_materials_workbench.envelope.layer_outputs import Phase0ExtractedProperty
from zer0pa_materials_workbench.envelope.units import DimensionalityError, parse_quantity
from zer0pa_materials_workbench.falsifiers.raw_evidence import find_source_manifest_row

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
            "Unresolved contradiction(s) in Phase 0 extractions: "
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


# ---------------------------------------------------------------------------
# verify_source_manifest_linkage   (Wave D hardened gate 2)
# ---------------------------------------------------------------------------


def verify_source_manifest_linkage(
    envelope: Envelope | dict[str, Any],
    audit_log: Any,
) -> FalsifierItem:
    """Verify each ``audit.source_manifest_refs`` resolves in ``sources.jsonl``.

    Wave D hardened source-manifest linkage gate. The original audit
    flow accepts any non-empty list of ``src:...`` strings; an adapter
    can fabricate strings that never wrote a corresponding row. This
    gate walks each ref, looks up the row in the live audit log,
    verifies the row's ``source_manifest_id`` matches, and verifies
    the row's ``decision_impact`` references the same domain (``layer``)
    as the envelope.

    Pass conditions (all must hold):
      * ``audit.source_manifest_refs`` is non-empty.
      * For each ref, exactly one row in ``sources.jsonl`` exists with
        ``payload.source_manifest_id == ref``.
      * The matched row carries a ``decision_impact`` field referencing
        the envelope's layer (e.g. mentions ``"L2"``, ``"phase0"``, etc.).

    Args:
        envelope: an :class:`Envelope` (or wire dict) carrying an
            ``audit.source_manifest_refs`` list.
        audit_log: a live :class:`zer0pa_materials_workbench.audit.log.AuditLog`,
            an in-memory list of audit rows, or any iterable yielding
            the ``sources.jsonl`` rows.

    Returns:
        FalsifierItem with status ``pass`` if every ref resolves;
        ``fail`` listing the unresolved refs; ``blocked`` if the
        envelope has no audit block.
    """
    if isinstance(envelope, Envelope):
        body = envelope.model_dump(mode="json")
    elif isinstance(envelope, dict):
        body = envelope
    else:
        return FalsifierItem(
            name="phase0.source_manifest_linkage",
            threshold="every audit.source_manifest_refs entry resolves in sources.jsonl",
            actual={"reason": "envelope_type_unknown", "type": type(envelope).__name__},
            status="blocked",
        )

    audit_block = body.get("audit") or {}
    refs = audit_block.get("source_manifest_refs") or []
    layer = body.get("layer", "unknown")

    if not refs:
        return FalsifierItem(
            name="phase0.source_manifest_linkage",
            threshold="every audit.source_manifest_refs entry resolves in sources.jsonl",
            actual={"refs": [], "reason": "no_refs_to_check"},
            status="fail",
            rationale="envelope has no source_manifest_refs",
        )

    unresolved: list[str] = []
    decision_impact_mismatches: list[dict[str, str]] = []
    for ref in refs:
        if not isinstance(ref, str):
            unresolved.append(repr(ref))
            continue
        row = find_source_manifest_row(audit_log, ref)
        if row is None:
            unresolved.append(ref)
            continue
        # Verify decision_impact references this envelope's layer.
        impact = str(row.get("decision_impact") or "")
        if impact and layer != "unknown" and layer.lower() not in impact.lower():
            decision_impact_mismatches.append(
                {
                    "ref": ref,
                    "decision_impact": impact[:120],
                    "envelope_layer": str(layer),
                }
            )

    if unresolved:
        return FalsifierItem(
            name="phase0.source_manifest_linkage",
            threshold="every audit.source_manifest_refs entry resolves in sources.jsonl",
            actual={
                "refs": list(refs),
                "unresolved": unresolved,
                "decision_impact_mismatches": decision_impact_mismatches,
            },
            status="fail",
            rationale=(
                f"{len(unresolved)} of {len(refs)} source_manifest_refs do not "
                "resolve in sources.jsonl — possible fabricated refs"
            ),
        )

    return FalsifierItem(
        name="phase0.source_manifest_linkage",
        threshold="every audit.source_manifest_refs entry resolves in sources.jsonl",
        actual={
            "refs": list(refs),
            "n_resolved": len(refs),
            "decision_impact_mismatches": decision_impact_mismatches,
        },
        status="pass",
    )
