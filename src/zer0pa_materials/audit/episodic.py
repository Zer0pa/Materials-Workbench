"""Episodic memory / resume (PRD §Hard Gates / Brain-functionality).

The PRD requires:

    A fresh agent can reconstruct the project from repo artifacts without
    chat history.

This module implements two functions:

* :func:`snapshot_state` — given an audit directory and KG path, compile the
  current campaign state into a :class:`StateSnapshot`. The snapshot records:

  - the head event_hash for every audit category
  - row counts per category
  - chain validation status per category
  - KG node/edge counts (with breakdown by node type)
  - open falsifiers (any falsifier row with status == "fail" or "blocked")
  - pending decisions (decisions whose ``supersedes`` chain has no successor)
  - reasoner tuples in ``hold`` or ``queue_higher_fidelity`` state

* :func:`reconstruct_from_repo` — given just a repository root, find the
  audit dir / KG db path (via :class:`MaterialsConfig`) and return a
  :class:`CampaignState` showing what a fresh agent should pick up next.

Test plan: drop a synthetic event sequence into a tmp dir, call
``reconstruct_from_repo``, assert the reconstructed state matches what the
synthetic sequence implies — *with no chat history*.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from zer0pa_materials.audit.kg import KGNodeType, MaterialsKG
from zer0pa_materials.audit.log import (
    AUDIT_CATEGORIES,
    AuditCategory,
    AuditLog,
    ChainValidationResult,
)

__all__ = [
    "CategoryState",
    "StateSnapshot",
    "CampaignState",
    "snapshot_state",
    "reconstruct_from_repo",
]


def _utc_now() -> str:
    return _dt.datetime.now(tz=_dt.timezone.utc).isoformat(timespec="microseconds")


class CategoryState(BaseModel):
    """Per-audit-category state summary."""

    model_config = ConfigDict(extra="forbid")

    category: AuditCategory
    row_count: int
    head_event_hash: str
    chain_ok: bool
    chain_errors: list[str] = Field(default_factory=list)


class StateSnapshot(BaseModel):
    """Snapshot of the campaign at one moment in time."""

    model_config = ConfigDict(extra="forbid")

    captured_at: str = Field(default_factory=_utc_now)
    audit_dir: str
    kg_db_path: str
    categories: list[CategoryState]
    kg_node_count: int
    kg_edge_count: int
    kg_node_count_by_type: dict[str, int]
    open_falsifiers: list[dict[str, Any]] = Field(default_factory=list)
    pending_decisions: list[dict[str, Any]] = Field(default_factory=list)
    holding_reasoner_tuples: list[dict[str, Any]] = Field(default_factory=list)


class CampaignState(BaseModel):
    """The state a fresh agent reads when resuming.

    Wraps :class:`StateSnapshot` with derived "next-action" hints. The
    agent reads ``next_actions`` to pick what to do next without any chat
    history.
    """

    model_config = ConfigDict(extra="forbid")

    snapshot: StateSnapshot
    repo_root: str
    next_actions: list[str] = Field(
        default_factory=list,
        description="Plain-language hints; the agent's planner consumes them.",
    )


# ----------------------------------------------------------------------------
# Snapshot
# ----------------------------------------------------------------------------


def snapshot_state(audit_dir: str | Path, kg_db_path: str | Path) -> StateSnapshot:
    """Compile a :class:`StateSnapshot` from disk."""
    audit_dir_p = Path(audit_dir).resolve()
    kg_db_path_p = Path(kg_db_path).resolve()
    log = AuditLog(audit_dir_p)

    categories: list[CategoryState] = []
    for cat in AUDIT_CATEGORIES:
        result = log.validate_chain(cat)
        head_hash = log.head_hash(cat)
        rows = list(log.iter_rows(cat))
        categories.append(
            CategoryState(
                category=cat,
                row_count=len(rows),
                head_event_hash=head_hash,
                chain_ok=result.ok,
                chain_errors=result.errors,
            )
        )

    # KG state.
    kg_node_count = 0
    kg_edge_count = 0
    kg_by_type: dict[str, int] = {}
    if kg_db_path_p.exists():
        with MaterialsKG(kg_db_path_p) as kg:
            kg_node_count = kg.count_nodes()
            kg_edge_count = kg.count_edges()
            kg_by_type = kg.count_nodes_by_type()

    # Open falsifiers: any payload in falsifiers.jsonl with status in fail/blocked.
    open_falsifiers: list[dict[str, Any]] = []
    for row in log.iter_rows("falsifiers"):
        status = row.payload.get("status")
        if status in ("fail", "blocked"):
            open_falsifiers.append(
                {
                    "name": row.payload.get("name"),
                    "status": status,
                    "rationale": row.payload.get("rationale"),
                    "event_hash": row.event_hash,
                    "recorded_at": row.recorded_at,
                }
            )

    # Pending decisions: any decision_id that is NOT in any supersedes list.
    decision_payloads: list[dict[str, Any]] = []
    for row in log.iter_rows("decisions"):
        decision_payloads.append(row.payload)
    superseded: set[str] = set()
    for p in decision_payloads:
        for s in p.get("supersedes", []) or []:
            superseded.add(s)
    pending: list[dict[str, Any]] = []
    for p in decision_payloads:
        did = p.get("decision_id")
        if did is None:
            continue
        if did in superseded:
            continue
        pending.append(p)

    # Holding reasoner tuples: status == hold / queue_higher_fidelity.
    holding: list[dict[str, Any]] = []
    for row in log.iter_rows("reasoner_tuples"):
        decision = row.payload.get("decision")
        if decision in ("hold", "queue_higher_fidelity"):
            holding.append(
                {
                    "tuple_id": row.payload.get("tuple_id"),
                    "candidate_id": row.payload.get("candidate_id"),
                    "decision": decision,
                    "event_hash": row.event_hash,
                }
            )

    return StateSnapshot(
        audit_dir=str(audit_dir_p),
        kg_db_path=str(kg_db_path_p),
        categories=categories,
        kg_node_count=kg_node_count,
        kg_edge_count=kg_edge_count,
        kg_node_count_by_type=kg_by_type,
        open_falsifiers=open_falsifiers,
        pending_decisions=pending,
        holding_reasoner_tuples=holding,
    )


# ----------------------------------------------------------------------------
# Reconstruction
# ----------------------------------------------------------------------------


def _resolve_audit_paths(repo_root: Path) -> tuple[Path, Path]:
    """Resolve the audit_dir + kg_db_path, preferring config but tolerating its absence.

    Strategy:

    * If a ``.env`` is present in the repo root and :class:`MaterialsConfig`
      parses it, use its ``AUDIT_DIR`` and ``KG_DB_PATH`` resolved relative
      to the repo root.
    * Otherwise use repo-root-relative defaults: ``audit/runtime/``
      and ``audit/runtime/kg.sqlite``.

    We deliberately do NOT use the cwd-based ``MaterialsConfig()`` constructor
    here, because that would pick up the calling process's ``.env`` instead
    of the repo's. The brain-functionality gate requires that the result
    depend only on ``repo_root``, not on the caller's environment.
    """
    env_file = repo_root / ".env"
    if env_file.exists():
        try:
            from zer0pa_materials.envelope.config import MaterialsConfig

            cfg = MaterialsConfig(_env_file=str(env_file))  # type: ignore[call-arg]
            paths = cfg.runtime_paths()
            audit_dir = paths["audit_dir"]
            if not audit_dir.is_absolute():
                audit_dir = (repo_root / audit_dir).resolve()
            kg_db_path = paths["kg_db_path"]
            if not kg_db_path.is_absolute():
                kg_db_path = (repo_root / kg_db_path).resolve()
            return audit_dir, kg_db_path
        except Exception:
            pass
    # Fallback: repo-root-relative defaults.
    return (repo_root / "audit" / "runtime").resolve(), (
        repo_root / "audit" / "runtime" / "kg.sqlite"
    ).resolve()


def reconstruct_from_repo(repo_root: str | Path) -> CampaignState:
    """Reconstruct campaign state from a repository root, with no chat history.

    This implements the PRD's brain-functionality gate. The function:

    1. resolves audit + KG paths from config or sane defaults,
    2. snapshots the audit + KG state,
    3. derives plain-language ``next_actions`` from the snapshot.

    The result is sufficient for a fresh agent to pick up the project.
    """
    root = Path(repo_root).resolve()
    audit_dir, kg_db_path = _resolve_audit_paths(root)
    snapshot = snapshot_state(audit_dir, kg_db_path)

    next_actions: list[str] = []

    # 1. Any chain validation error is the first thing to fix.
    for cat_state in snapshot.categories:
        if not cat_state.chain_ok:
            next_actions.append(
                f"AUDIT CHAIN INTEGRITY: {cat_state.category} chain has "
                f"{len(cat_state.chain_errors)} divergence(s); inspect "
                f"{audit_dir}/{cat_state.category}.jsonl"
            )

    # 2. Open falsifiers block promotion.
    for f in snapshot.open_falsifiers:
        next_actions.append(
            f"OPEN FALSIFIER: {f.get('name')} status={f.get('status')}"
        )

    # 3. Pending decisions.
    for d in snapshot.pending_decisions:
        next_actions.append(
            f"PENDING DECISION: {d.get('decision_id')} ({d.get('context', '')[:60]})"
        )

    # 4. Holding reasoner tuples.
    for t in snapshot.holding_reasoner_tuples:
        next_actions.append(
            f"HOLDING TUPLE: {t.get('tuple_id')} candidate={t.get('candidate_id')} "
            f"decision={t.get('decision')}"
        )

    # 5. If everything is clean, advise progression.
    if not next_actions:
        next_actions.append(
            "All chains valid; no open falsifiers, pending decisions, or holding "
            "tuples. Proceed to the next phase per PRD §CPU-First Build Sequence."
        )

    return CampaignState(
        snapshot=snapshot,
        repo_root=str(root),
        next_actions=next_actions,
    )
