"""Falsifier ledger and shared falsifier primitives.

Wave D additions
----------------
The Wave D audit caught a systemic falsifier weakness — many gates trust
fields rather than recompute from raw evidence. The hardened gates and
their shared recompute helpers live alongside the originals so both
surfaces remain importable. See
:mod:`zer0pa_materials.falsifiers.raw_evidence` for the recompute
primitives and ``phases/Falsification-wave/PHASE-REPORT-WAVE-D-DELTA.md``
for the audit + fix delta.

The new (hardened) gates are:

* :func:`l2_falsifiers.dpa_mace_disagreement_routing_recomputed` —
  recomputes DPA/MACE disagreement from per-model predictions.
* :func:`phase0_falsifiers.verify_source_manifest_linkage` —
  resolves every ``audit.source_manifest_refs`` against ``sources.jsonl``.
* :func:`l6_falsifiers.recompute_novelty` and
  :func:`l6_falsifiers.novelty_status_gate_recomputed` —
  re-run structure_hash, reference dedupe, and per-batch dedupe before
  trusting a novelty claim.
* :func:`ionic_falsifiers.verify_ionic_service_back_edge` — resolves
  the ionic back-edge against the live audit log.
* :func:`ionic_falsifiers.neb_barrier_range_check` — applies a
  literature plausibility band on ``migration_barrier_eV`` and an
  Arrhenius consistency check.
* :func:`l5_falsifiers.verify_l5_artifact_sidecar` — re-reads the
  artifact bytes from disk and recomputes sha256 against the sidecar.
* :func:`l3_falsifiers.verify_l3_sovereign_block_enforced` — requires a
  prior decision row for any restricted-backend envelope.
* :mod:`uma_manifest` — verifiable UMA AUP/license manifest.
"""

from zer0pa_materials.falsifiers.phase0_falsifiers import (
    KGWriteError,
    UngroundedPropertyError,
    UnparseableUnitError,
    UnresolvedContradictionError,
    assert_kg_nodes_for,
    reject_ungrounded_property,
    reject_unit_unparseable,
    reject_unresolved_contradiction,
    verify_source_manifest_linkage,
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
    novelty_status_gate_recomputed,
    pymatgen_structure_matcher,
    recompute_novelty,
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
    verify_l3_sovereign_block_enforced,
)
from zer0pa_materials.falsifiers.l2_falsifiers import (
    committee_uncertainty_threshold,
    dpa_mace_disagreement_routing,
    dpa_mace_disagreement_routing_recomputed,
    force_rmse_threshold,
    single_model_promotion_block,
    space_group_drift_threshold,
    uma_license_gate,
    volume_drift_threshold,
)
from zer0pa_materials.falsifiers.ionic_falsifiers import (
    ARRHENIUS_BARRIER_BAND_AT_1E_3_EV,
    MAX_PLAUSIBLE_BARRIER_EV,
    MIN_PLAUSIBLE_BARRIER_EV,
    neb_barrier_range_check,
    requires_ionic_transport_service,
    verify_ionic_service_back_edge,
)
from zer0pa_materials.falsifiers.l5_falsifiers import (
    artifact_units_sidecar_present,
    verify_l5_artifact_sidecar,
)
from zer0pa_materials.falsifiers.uma_manifest import (
    UmaAupLicenseManifest,
    UmaManifestVerificationError,
    enable_uma_with_manifest,
    verify_uma_manifest,
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
    "verify_source_manifest_linkage",
    # l3
    "tdb_parses_in_pycalphad",
    "phase_boundary_drift",
    "phase_set_jaccard_distance",
    "phase_fraction_js_divergence",
    "espei_posterior_diagnostics",
    "tdb_quarantine_breach",
    "phaseforgeplus_license_gate",
    "commercial_tdb_provider_disabled_by_default",
    "verify_l3_sovereign_block_enforced",
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
    "novelty_status_gate_recomputed",
    "recompute_novelty",
    # l2
    "dpa_mace_disagreement_routing",
    "dpa_mace_disagreement_routing_recomputed",
    "single_model_promotion_block",
    "force_rmse_threshold",
    "volume_drift_threshold",
    "space_group_drift_threshold",
    "uma_license_gate",
    "committee_uncertainty_threshold",
    # ionic
    "requires_ionic_transport_service",
    "verify_ionic_service_back_edge",
    "neb_barrier_range_check",
    "MIN_PLAUSIBLE_BARRIER_EV",
    "MAX_PLAUSIBLE_BARRIER_EV",
    "ARRHENIUS_BARRIER_BAND_AT_1E_3_EV",
    # l5
    "artifact_units_sidecar_present",
    "verify_l5_artifact_sidecar",
    # uma manifest
    "UmaAupLicenseManifest",
    "UmaManifestVerificationError",
    "verify_uma_manifest",
    "enable_uma_with_manifest",
]
