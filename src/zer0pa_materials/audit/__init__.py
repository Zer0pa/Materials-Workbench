"""Audit hash chain, KG, source manifests, rights claims (A1).

Public surface:

* :class:`AuditLog` — hash-chained, append-only JSONL log family.
* :class:`AuditRow` — chain-row primitive.
* :data:`AUDIT_CATEGORIES` — the 11 audit-category names.
* :class:`SourceManifest` / :class:`BlockedSourceManifest` — PRD §Deep Research Policy.
* :class:`RightsClaim`, :func:`assert_rights_for`, :class:`RightsViolationError`,
  :data:`RIGHTS_TABLE` — PRD §Data Sovereignty.
* :class:`Decision`, :func:`reconstruct_supersession_chain` — PRD §Audit Trail And KG.
* :class:`MaterialsKG`, :class:`KGNodeType`, :class:`KGEdgeType`,
  :class:`KGNode`, :class:`KGEdge`, :class:`KGTypeError` — SQLite-backed KG.
* :func:`export_kg_to_turtle`, :func:`round_trip_validate` — RDF/PROV-O export.
* :func:`write_ro_crate_metadata`, :class:`RoCrateEntry` — RO-Crate 1.1 manifest.
* :func:`snapshot_state`, :func:`reconstruct_from_repo`,
  :class:`StateSnapshot`, :class:`CampaignState` — episodic memory.
"""

from zer0pa_materials.audit.decisions import (
    DECISION_ID_RE,
    Decision,
    DecisionMaker,
    reconstruct_supersession_chain,
)
from zer0pa_materials.audit.episodic import (
    CampaignState,
    CategoryState,
    StateSnapshot,
    reconstruct_from_repo,
    snapshot_state,
)
from zer0pa_materials.audit.kg import (
    KGEdge,
    KGEdgeType,
    KGNode,
    KGNodeType,
    KGResumeMarker,
    KGTypeError,
    MaterialsKG,
)
from zer0pa_materials.audit.log import (
    AUDIT_CATEGORIES,
    AUDIT_FILENAMES,
    GENESIS_PREV_HASH,
    AuditCategory,
    AuditLog,
    AuditRow,
    ChainValidationResult,
)
from zer0pa_materials.audit.rdf_export import (
    export_kg_graph,
    export_kg_to_turtle,
    round_trip_validate,
)
from zer0pa_materials.audit.rights import (
    RIGHTS_CLAIM_ID_RE,
    RIGHTS_TABLE,
    ContractMode,
    DataClass,
    Ownership,
    RedactionPolicy,
    ReuseScope,
    RightsClaim,
    RightsViolationError,
    assert_rights_for,
    default_reuse_scope_for,
    is_reuse_scope_compatible,
)
from zer0pa_materials.audit.ro_crate import RoCrateEntry, write_ro_crate_metadata
from zer0pa_materials.audit.sources import (
    SOURCE_MANIFEST_ID_RE,
    BlockedSourceManifest,
    BlockerReason,
    Redaction,
    SourceManifest,
    SourceType,
)

__all__ = [
    # log
    "AuditLog",
    "AuditRow",
    "AuditCategory",
    "AUDIT_CATEGORIES",
    "AUDIT_FILENAMES",
    "GENESIS_PREV_HASH",
    "ChainValidationResult",
    # sources
    "SourceManifest",
    "BlockedSourceManifest",
    "SourceType",
    "Redaction",
    "BlockerReason",
    "SOURCE_MANIFEST_ID_RE",
    # rights
    "RightsClaim",
    "RightsViolationError",
    "assert_rights_for",
    "is_reuse_scope_compatible",
    "default_reuse_scope_for",
    "RIGHTS_TABLE",
    "RIGHTS_CLAIM_ID_RE",
    "DataClass",
    "Ownership",
    "ReuseScope",
    "ContractMode",
    "RedactionPolicy",
    # kg
    "MaterialsKG",
    "KGNodeType",
    "KGEdgeType",
    "KGNode",
    "KGEdge",
    "KGResumeMarker",
    "KGTypeError",
    # rdf
    "export_kg_to_turtle",
    "export_kg_graph",
    "round_trip_validate",
    # ro-crate
    "write_ro_crate_metadata",
    "RoCrateEntry",
    # decisions
    "Decision",
    "DecisionMaker",
    "DECISION_ID_RE",
    "reconstruct_supersession_chain",
    # episodic
    "snapshot_state",
    "reconstruct_from_repo",
    "StateSnapshot",
    "CategoryState",
    "CampaignState",
]
