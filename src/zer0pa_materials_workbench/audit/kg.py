"""SQLite-backed property graph for the Zer0pa Materials Workbench KG (PRD §Audit Trail And KG).

The PRD's open question for the executor allows SQLite/property-graph with
RDF export (see PRD §Open Questions For Overnight Executor #2). We adopt
that design: SQLite is the runtime store; RDF/Turtle is the export.

Schema
------

::

    CREATE TABLE kg_node (
        node_id          TEXT PRIMARY KEY,
        node_type        TEXT NOT NULL,
        properties_json  TEXT NOT NULL,
        ontology_term    TEXT NOT NULL,
        created_at       TEXT NOT NULL,
        run_id           TEXT NOT NULL
    );

    CREATE TABLE kg_edge (
        edge_id          TEXT PRIMARY KEY,
        src_id           TEXT NOT NULL,
        dst_id           TEXT NOT NULL,
        edge_type        TEXT NOT NULL,
        properties_json  TEXT NOT NULL,
        created_at       TEXT NOT NULL,
        run_id           TEXT NOT NULL,
        FOREIGN KEY (src_id) REFERENCES kg_node(node_id),
        FOREIGN KEY (dst_id) REFERENCES kg_node(node_id)
    );

    CREATE INDEX kg_edge_src_idx ON kg_edge(src_id, edge_type);
    CREATE INDEX kg_edge_dst_idx ON kg_edge(dst_id, edge_type);
    CREATE INDEX kg_node_type_idx ON kg_node(node_type);

    CREATE TABLE kg_resume (
        run_id            TEXT PRIMARY KEY,
        last_event_hash   TEXT NOT NULL,
        last_node_id      TEXT,
        last_edge_id      TEXT,
        captured_at       TEXT NOT NULL
    );

Type discipline
---------------

Node types are constrained to the 27 types from PRD §Audit Trail And KG.
Edge types are constrained to the 25 edge types. Both lists are exposed
as :class:`KGNodeType` / :class:`KGEdgeType` ``StrEnum``\\s. Inserts that
use a non-canonical type are rejected at the application layer (we do
not use SQLite ``CHECK`` constraints because string equality there is
weaker than a Python enum dispatch).
"""

from __future__ import annotations

import datetime as _dt
import json
import sqlite3
from collections.abc import Iterable
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from zer0pa_materials_workbench.ontology.emmo import (
    iri_for_kg_node,
)

__all__ = [
    "KGEdge",
    "KGEdgeType",
    "KGNode",
    "KGNodeType",
    "KGResumeMarker",
    "KGTypeError",
    "MaterialsKG",
]


# ----------------------------------------------------------------------------
# Type enums
# ----------------------------------------------------------------------------


class KGNodeType(StrEnum):
    """The 27 KG node types from PRD §Audit Trail And KG."""

    Campaign = "Campaign"
    CustomerTenant = "CustomerTenant"
    Objective = "Objective"
    AcceptanceGate = "AcceptanceGate"
    Hypothesis = "Hypothesis"
    CandidateMaterial = "CandidateMaterial"
    Composition = "Composition"
    Structure = "Structure"
    Phase = "Phase"
    PropertyObservation = "PropertyObservation"
    SimulationJob = "SimulationJob"
    SimulationResult = "SimulationResult"
    ModelCheckpoint = "ModelCheckpoint"
    Dataset = "Dataset"
    LiteratureSource = "LiteratureSource"
    OPTIMADEResource = "OPTIMADEResource"
    SynthesisRecipe = "SynthesisRecipe"
    Artifact = "Artifact"
    SourceManifest = "SourceManifest"
    Falsifier = "Falsifier"
    DisagreementMetric = "DisagreementMetric"
    Decision = "Decision"
    Actor = "Actor"
    Tool = "Tool"
    ComputeEnvironment = "ComputeEnvironment"
    License = "License"
    RightsClaim = "RightsClaim"
    OntologyTerm = "OntologyTerm"


class KGEdgeType(StrEnum):
    """The 25 KG edge types from PRD §Audit Trail And KG."""

    DERIVED_FROM = "DERIVED_FROM"
    USED = "USED"
    GENERATED = "GENERATED"
    ATTRIBUTED_TO = "ATTRIBUTED_TO"
    HAS_STRUCTURE = "HAS_STRUCTURE"
    HAS_COMPOSITION = "HAS_COMPOSITION"
    HAS_PROPERTY = "HAS_PROPERTY"
    PREDICTED_BY = "PREDICTED_BY"
    MEASURED_BY = "MEASURED_BY"
    HAS_UNCERTAINTY = "HAS_UNCERTAINTY"
    AGREES_WITH = "AGREES_WITH"
    CONTRADICTS = "CONTRADICTS"
    PASSES_GATE = "PASSES_GATE"
    FAILS_GATE = "FAILS_GATE"
    ROUTED_TO = "ROUTED_TO"
    CITES = "CITES"
    MAPS_TO_ONTOLOGY = "MAPS_TO_ONTOLOGY"
    LICENSED_UNDER = "LICENSED_UNDER"
    OWNED_BY = "OWNED_BY"
    PERMITTED_FOR = "PERMITTED_FOR"
    REDACTED_AS = "REDACTED_AS"
    SUPERSEDES = "SUPERSEDES"
    CALIBRATED_ON = "CALIBRATED_ON"
    FINETUNED_FROM = "FINETUNED_FROM"
    MEMBER_OF_ENSEMBLE = "MEMBER_OF_ENSEMBLE"


class KGTypeError(ValueError):
    """Raised when a node/edge insert uses a non-canonical type."""


# ----------------------------------------------------------------------------
# Models
# ----------------------------------------------------------------------------


def _utc_now() -> str:
    return _dt.datetime.now(tz=_dt.timezone.utc).isoformat(timespec="microseconds")


class KGNode(BaseModel):
    """A KG node row."""

    model_config = ConfigDict(extra="forbid")

    node_id: str = Field(..., min_length=1)
    node_type: KGNodeType
    properties: dict[str, Any] = Field(default_factory=dict)
    ontology_term: str = Field(..., min_length=1)
    created_at: str = Field(default_factory=_utc_now)
    run_id: str

    @field_validator("ontology_term")
    @classmethod
    def _v_iri(cls, v: str) -> str:
        # Permissive IRI check: must be non-empty, must look like a URI scheme.
        if "://" not in v:
            raise ValueError(f"ontology_term must be a URI/IRI, got {v!r}")
        return v


class KGEdge(BaseModel):
    """A KG edge row."""

    model_config = ConfigDict(extra="forbid")

    edge_id: str = Field(..., min_length=1)
    src_id: str = Field(..., min_length=1)
    dst_id: str = Field(..., min_length=1)
    edge_type: KGEdgeType
    properties: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=_utc_now)
    run_id: str


class KGResumeMarker(BaseModel):
    """Resume marker for a run; lets a fresh agent pick up where it left off."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    last_event_hash: str
    last_node_id: str | None = None
    last_edge_id: str | None = None
    captured_at: str = Field(default_factory=_utc_now)


# ----------------------------------------------------------------------------
# MaterialsKG
# ----------------------------------------------------------------------------


_DDL = [
    """
    CREATE TABLE IF NOT EXISTS kg_node (
        node_id          TEXT PRIMARY KEY,
        node_type        TEXT NOT NULL,
        properties_json  TEXT NOT NULL,
        ontology_term    TEXT NOT NULL,
        created_at       TEXT NOT NULL,
        run_id           TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS kg_edge (
        edge_id          TEXT PRIMARY KEY,
        src_id           TEXT NOT NULL,
        dst_id           TEXT NOT NULL,
        edge_type        TEXT NOT NULL,
        properties_json  TEXT NOT NULL,
        created_at       TEXT NOT NULL,
        run_id           TEXT NOT NULL,
        FOREIGN KEY (src_id) REFERENCES kg_node(node_id),
        FOREIGN KEY (dst_id) REFERENCES kg_node(node_id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS kg_edge_src_idx ON kg_edge(src_id, edge_type)",
    "CREATE INDEX IF NOT EXISTS kg_edge_dst_idx ON kg_edge(dst_id, edge_type)",
    "CREATE INDEX IF NOT EXISTS kg_node_type_idx ON kg_node(node_type)",
    """
    CREATE TABLE IF NOT EXISTS kg_resume (
        run_id            TEXT PRIMARY KEY,
        last_event_hash   TEXT NOT NULL,
        last_node_id      TEXT,
        last_edge_id      TEXT,
        captured_at       TEXT NOT NULL
    )
    """,
]


class MaterialsKG:
    """SQLite-backed property graph for the Zer0pa Materials Workbench KG.

    Open with a path to the SQLite file. ``__init__`` runs the DDL idempotently;
    re-opening an existing DB is a no-op for schema. All operations are
    transactional: ``add_node``/``add_edge`` commit on success.

    Use as a context manager when possible — ``close()`` releases the
    connection cleanly.
    """

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path).resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        # check_same_thread=False because the campaign runner may hop threads;
        # we wrap mutations in transactions so this is safe for our use.
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.execute("PRAGMA journal_mode = WAL")
        for stmt in _DDL:
            self._conn.execute(stmt)
        self._conn.commit()

    # ---- context manager --------------------------------------------------

    def __enter__(self) -> MaterialsKG:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None  # type: ignore[assignment]

    # ---- type validation helpers ------------------------------------------

    @staticmethod
    def _coerce_node_type(node_type: str | KGNodeType) -> KGNodeType:
        if isinstance(node_type, KGNodeType):
            return node_type
        try:
            return KGNodeType(node_type)
        except ValueError as exc:
            valid = sorted(t.value for t in KGNodeType)
            raise KGTypeError(
                f"unknown KG node type {node_type!r}; valid: {valid}"
            ) from exc

    @staticmethod
    def _coerce_edge_type(edge_type: str | KGEdgeType) -> KGEdgeType:
        if isinstance(edge_type, KGEdgeType):
            return edge_type
        try:
            return KGEdgeType(edge_type)
        except ValueError as exc:
            valid = sorted(t.value for t in KGEdgeType)
            raise KGTypeError(
                f"unknown KG edge type {edge_type!r}; valid: {valid}"
            ) from exc

    # ---- node/edge insert -------------------------------------------------

    def add_node(
        self,
        node_id: str,
        node_type: str | KGNodeType,
        properties: dict[str, Any] | None = None,
        run_id: str = "",
        ontology_term: str | None = None,
        created_at: str | None = None,
    ) -> KGNode:
        """Insert one node. Reject non-canonical ``node_type``.

        ``ontology_term`` defaults to the primary IRI from
        :data:`zer0pa_materials_workbench.ontology.emmo.KG_NODE_TO_EMMO`.
        """
        ntype = self._coerce_node_type(node_type)
        iri = ontology_term if ontology_term is not None else iri_for_kg_node(ntype.value)
        node = KGNode(
            node_id=node_id,
            node_type=ntype,
            properties=properties or {},
            ontology_term=iri,
            created_at=created_at or _utc_now(),
            run_id=run_id,
        )
        self._conn.execute(
            """
            INSERT INTO kg_node(node_id, node_type, properties_json, ontology_term, created_at, run_id)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                node.node_id,
                node.node_type.value,
                json.dumps(node.properties, sort_keys=True),
                node.ontology_term,
                node.created_at,
                node.run_id,
            ),
        )
        self._conn.commit()
        return node

    def add_edge(
        self,
        edge_id: str,
        src_id: str,
        dst_id: str,
        edge_type: str | KGEdgeType,
        properties: dict[str, Any] | None = None,
        run_id: str = "",
        created_at: str | None = None,
    ) -> KGEdge:
        """Insert one edge. Reject non-canonical ``edge_type``."""
        etype = self._coerce_edge_type(edge_type)
        edge = KGEdge(
            edge_id=edge_id,
            src_id=src_id,
            dst_id=dst_id,
            edge_type=etype,
            properties=properties or {},
            created_at=created_at or _utc_now(),
            run_id=run_id,
        )
        self._conn.execute(
            """
            INSERT INTO kg_edge(edge_id, src_id, dst_id, edge_type, properties_json, created_at, run_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                edge.edge_id,
                edge.src_id,
                edge.dst_id,
                edge.edge_type.value,
                json.dumps(edge.properties, sort_keys=True),
                edge.created_at,
                edge.run_id,
            ),
        )
        self._conn.commit()
        return edge

    # ---- queries ----------------------------------------------------------

    def get_node(self, node_id: str) -> KGNode | None:
        cur = self._conn.execute(
            "SELECT node_id, node_type, properties_json, ontology_term, created_at, run_id "
            "FROM kg_node WHERE node_id = ?",
            (node_id,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        return KGNode(
            node_id=row[0],
            node_type=KGNodeType(row[1]),
            properties=json.loads(row[2]),
            ontology_term=row[3],
            created_at=row[4],
            run_id=row[5],
        )

    def get_edges_from(
        self, src_id: str, edge_type: str | KGEdgeType | None = None
    ) -> list[KGEdge]:
        if edge_type is None:
            cur = self._conn.execute(
                "SELECT edge_id, src_id, dst_id, edge_type, properties_json, created_at, run_id "
                "FROM kg_edge WHERE src_id = ?",
                (src_id,),
            )
        else:
            etype = self._coerce_edge_type(edge_type)
            cur = self._conn.execute(
                "SELECT edge_id, src_id, dst_id, edge_type, properties_json, created_at, run_id "
                "FROM kg_edge WHERE src_id = ? AND edge_type = ?",
                (src_id, etype.value),
            )
        return [
            KGEdge(
                edge_id=r[0],
                src_id=r[1],
                dst_id=r[2],
                edge_type=KGEdgeType(r[3]),
                properties=json.loads(r[4]),
                created_at=r[5],
                run_id=r[6],
            )
            for r in cur.fetchall()
        ]

    def get_edges_to(
        self, dst_id: str, edge_type: str | KGEdgeType | None = None
    ) -> list[KGEdge]:
        if edge_type is None:
            cur = self._conn.execute(
                "SELECT edge_id, src_id, dst_id, edge_type, properties_json, created_at, run_id "
                "FROM kg_edge WHERE dst_id = ?",
                (dst_id,),
            )
        else:
            etype = self._coerce_edge_type(edge_type)
            cur = self._conn.execute(
                "SELECT edge_id, src_id, dst_id, edge_type, properties_json, created_at, run_id "
                "FROM kg_edge WHERE dst_id = ? AND edge_type = ?",
                (dst_id, etype.value),
            )
        return [
            KGEdge(
                edge_id=r[0],
                src_id=r[1],
                dst_id=r[2],
                edge_type=KGEdgeType(r[3]),
                properties=json.loads(r[4]),
                created_at=r[5],
                run_id=r[6],
            )
            for r in cur.fetchall()
        ]

    def iter_nodes(self) -> Iterable[KGNode]:
        cur = self._conn.execute(
            "SELECT node_id, node_type, properties_json, ontology_term, created_at, run_id FROM kg_node"
        )
        for r in cur.fetchall():
            yield KGNode(
                node_id=r[0],
                node_type=KGNodeType(r[1]),
                properties=json.loads(r[2]),
                ontology_term=r[3],
                created_at=r[4],
                run_id=r[5],
            )

    def iter_edges(self) -> Iterable[KGEdge]:
        cur = self._conn.execute(
            "SELECT edge_id, src_id, dst_id, edge_type, properties_json, created_at, run_id FROM kg_edge"
        )
        for r in cur.fetchall():
            yield KGEdge(
                edge_id=r[0],
                src_id=r[1],
                dst_id=r[2],
                edge_type=KGEdgeType(r[3]),
                properties=json.loads(r[4]),
                created_at=r[5],
                run_id=r[6],
            )

    def count_nodes(self) -> int:
        cur = self._conn.execute("SELECT COUNT(*) FROM kg_node")
        return int(cur.fetchone()[0])

    def count_edges(self) -> int:
        cur = self._conn.execute("SELECT COUNT(*) FROM kg_edge")
        return int(cur.fetchone()[0])

    def count_nodes_by_type(self) -> dict[str, int]:
        cur = self._conn.execute(
            "SELECT node_type, COUNT(*) FROM kg_node GROUP BY node_type"
        )
        return {row[0]: int(row[1]) for row in cur.fetchall()}

    # ---- resume marker ----------------------------------------------------

    def capture_resume(
        self,
        run_id: str,
        last_event_hash: str,
        last_node_id: str | None = None,
        last_edge_id: str | None = None,
    ) -> KGResumeMarker:
        """Upsert the resume marker for ``run_id``."""
        marker = KGResumeMarker(
            run_id=run_id,
            last_event_hash=last_event_hash,
            last_node_id=last_node_id,
            last_edge_id=last_edge_id,
        )
        self._conn.execute(
            """
            INSERT INTO kg_resume(run_id, last_event_hash, last_node_id, last_edge_id, captured_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(run_id) DO UPDATE SET
                last_event_hash = excluded.last_event_hash,
                last_node_id    = excluded.last_node_id,
                last_edge_id    = excluded.last_edge_id,
                captured_at     = excluded.captured_at
            """,
            (
                marker.run_id,
                marker.last_event_hash,
                marker.last_node_id,
                marker.last_edge_id,
                marker.captured_at,
            ),
        )
        self._conn.commit()
        return marker

    def load_resume(self, run_id: str) -> KGResumeMarker | None:
        cur = self._conn.execute(
            "SELECT run_id, last_event_hash, last_node_id, last_edge_id, captured_at "
            "FROM kg_resume WHERE run_id = ?",
            (run_id,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        return KGResumeMarker(
            run_id=row[0],
            last_event_hash=row[1],
            last_node_id=row[2],
            last_edge_id=row[3],
            captured_at=row[4],
        )
