"""Falsifier ledger and shared falsifier primitives."""

from zer0pa_materials.falsifiers.phase0_falsifiers import (
    KGWriteError,
    UngroundedPropertyError,
    UnparseableUnitError,
    UnresolvedContradictionError,
    assert_kg_nodes_for,
    reject_ungrounded_property,
    reject_unit_unparseable,
    reject_unresolved_contradiction,
)
from zer0pa_materials.falsifiers.l6_falsifiers import (
    ChargeNeutralityError,
    DuplicateStructureError,
    InvalidCifError,
    MinDistanceError,
    PrematureNoveltyError,
    ReferenceMatchError,
    charge_neutrality_check,
    min_interatomic_distance,
    novelty_status_gate,
    pymatgen_structure_matcher,
    reference_expansion_dedupe,
    structure_hash_dedupe,
    valid_cif_only,
)
from zer0pa_materials.falsifiers.l3_falsifiers import (
    commercial_tdb_provider_disabled_by_default,
    espei_posterior_diagnostics,
    phase_boundary_drift,
    phase_fraction_js_divergence,
    phase_set_jaccard_distance,
    phaseforgeplus_license_gate,
    tdb_parses_in_pycalphad,
    tdb_quarantine_breach,
)

__all__ = [
    # phase0
    "UngroundedPropertyError",
    "UnparseableUnitError",
    "UnresolvedContradictionError",
    "KGWriteError",
    "reject_ungrounded_property",
    "reject_unit_unparseable",
    "reject_unresolved_contradiction",
    "assert_kg_nodes_for",
    # l3
    "tdb_parses_in_pycalphad",
    "phase_boundary_drift",
    "phase_set_jaccard_distance",
    "phase_fraction_js_divergence",
    "espei_posterior_diagnostics",
    "tdb_quarantine_breach",
    "phaseforgeplus_license_gate",
    "commercial_tdb_provider_disabled_by_default",
    # l6
    "InvalidCifError",
    "ChargeNeutralityError",
    "MinDistanceError",
    "DuplicateStructureError",
    "ReferenceMatchError",
    "PrematureNoveltyError",
    "valid_cif_only",
    "charge_neutrality_check",
    "min_interatomic_distance",
    "structure_hash_dedupe",
    "reference_expansion_dedupe",
    "pymatgen_structure_matcher",
    "novelty_status_gate",
]
