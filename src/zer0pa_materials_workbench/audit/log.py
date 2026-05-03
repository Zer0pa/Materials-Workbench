"""Append-only JSONL audit log family with SHA-256 hash chain (PRD §Audit Trail And KG).

Eleven categories, one file per category, all under ``${AUDIT_DIR}/``:

* ``runs.jsonl`` — run metadata
* ``events.jsonl`` — append-only layer events and decisions
* ``artifacts.jsonl`` — artifact URI/hash/size/schema (delegates row shape to
  :class:`zer0pa_materials_workbench.envelope.ArtifactManifest` plus the chain wrapper)
* ``sources.jsonl`` — source manifests (PRD §Deep Research Policy)
* ``models.jsonl`` — tool/model/adapter versions and license gates
* ``parameters.jsonl`` — explicit parameters and defaults
* ``disagreement.jsonl`` — cross-model and cross-solver disagreement metrics
* ``falsifiers.jsonl`` — falsifier definitions, triggers, statuses
* ``rights.jsonl`` — tenant, ownership, reuse scope, export rights
* ``decisions.jsonl`` — routing and architecture decisions
* ``reasoner_tuples.jsonl`` — self-bootstrapping tuple queue

Hash-chain semantics
--------------------

Every row carries:

* ``prev_hash`` — sha256 of the *previous* row's full canonical-JSON bytes
  (computed against everything in the row including its own ``event_hash``).
  The first row in a file uses ``"sha256:" + 64 * "0"``.
* ``event_hash`` — sha256 of ``prev_hash || canonical_json(payload)`` where
  ``payload`` is the row minus ``prev_hash`` and ``event_hash`` themselves.
  This is the field downstream rows reference as their ``prev_hash``.

The validator (:class:`AuditLog.validate_chain`) recomputes the chain from
scratch and reports the first divergence. It MUST detect:

1. row tampering (any byte changed in any payload),
2. row reordering,
3. row insertion,
4. row deletion.

All four are tested in ``tests/unit/audit/test_audit_log.py``.

Concurrency
-----------

Atomic append uses ``fcntl.flock`` on POSIX (the lock file lives next to
the JSONL file with a ``.lock`` suffix). On non-POSIX systems we fall back
to a temp-file + rename strategy with a short retry. Either way, complete
rows never interleave; the chain is always intact after an append returns.
"""

from __future__ import annotations

import datetime as _dt
import errno
import os
import re
import sys
import tempfile
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Literal

import orjson
from pydantic import BaseModel, ConfigDict, Field, field_validator

from zer0pa_materials_workbench.envelope.hashing import sha256_of

__all__ = [
    "AUDIT_CATEGORIES",
    "AUDIT_FILENAMES",
    "GENESIS_PREV_HASH",
    "AuditCategory",
    "AuditLog",
    "AuditRow",
    "ChainValidationResult",
]


# ----------------------------------------------------------------------------
# Categories and filenames
# ----------------------------------------------------------------------------


AuditCategory = Literal[
    "runs",
    "events",
    "artifacts",
    "sources",
    "models",
    "parameters",
    "disagreement",
    "falsifiers",
    "rights",
    "decisions",
    "reasoner_tuples",
]

AUDIT_CATEGORIES: tuple[AuditCategory, ...] = (
    "runs",
    "events",
    "artifacts",
    "sources",
    "models",
    "parameters",
    "disagreement",
    "falsifiers",
    "rights",
    "decisions",
    "reasoner_tuples",
)

AUDIT_FILENAMES: dict[AuditCategory, str] = {c: f"{c}.jsonl" for c in AUDIT_CATEGORIES}


# Sha256 with 64 hex zeros — the genesis "prev hash" for the first row in
# every category's chain. Format mirrors the envelope's ``sha256:<hex>``.
GENESIS_PREV_HASH: str = "sha256:" + ("0" * 64)


# Used by both the genesis sentinel and rows produced by `append_event`.
_HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


# ----------------------------------------------------------------------------
# Row model
# ----------------------------------------------------------------------------


class AuditRow(BaseModel):
    """One row in any audit JSONL file.

    The ``payload`` is the category-specific content. Shape is intentionally
    permissive at the chain layer — strict per-category Pydantic models live
    elsewhere (e.g. :class:`zer0pa_materials_workbench.audit.sources.SourceManifest`)
    and pass through here as already-validated dicts.
    """

    model_config = ConfigDict(extra="forbid")

    category: AuditCategory = Field(..., description="Category enum (matches filename).")
    recorded_at: str = Field(
        ...,
        description="ISO-8601 UTC timestamp with offset, e.g. '2026-04-30T01:23:45+00:00'.",
    )
    prev_hash: str = Field(..., description="sha256:<hex> of the prior row's canonical bytes.")
    event_hash: str = Field(..., description="sha256:<hex> of (prev_hash || canonical(payload)).")
    payload: dict[str, Any] = Field(..., description="Category-specific payload.")

    @field_validator("recorded_at")
    @classmethod
    def _v_iso(cls, v: str) -> str:
        try:
            parsed = _dt.datetime.fromisoformat(v)
        except ValueError as exc:
            raise ValueError(f"recorded_at must be ISO-8601: {exc}") from exc
        if parsed.tzinfo is None:
            raise ValueError("recorded_at must include a timezone offset (UTC preferred).")
        return v

    @field_validator("prev_hash", "event_hash")
    @classmethod
    def _v_hash(cls, v: str) -> str:
        if not _HASH_RE.match(v):
            raise ValueError(f"hash must match {_HASH_RE.pattern!r}; got {v!r}")
        return v


# ----------------------------------------------------------------------------
# Validation result
# ----------------------------------------------------------------------------


class ChainValidationResult(BaseModel):
    """Outcome of :meth:`AuditLog.validate_chain`.

    On success: ``ok=True``, ``errors=[]``, ``checked_rows`` equals total rows.
    On failure: ``ok=False`` and ``errors`` lists every divergence, in row
    order. ``first_bad_index`` is the 0-based index of the first divergent
    row (or ``None`` if structural before any payload could be parsed).
    """

    model_config = ConfigDict(extra="forbid")

    ok: bool
    checked_rows: int
    first_bad_index: int | None = None
    errors: list[str] = Field(default_factory=list)


# ----------------------------------------------------------------------------
# Hash-chain primitives
# ----------------------------------------------------------------------------


def _utc_now_iso() -> str:
    """Return the current time as an ISO-8601 UTC string with offset."""
    return _dt.datetime.now(tz=_dt.timezone.utc).isoformat(timespec="microseconds")


def _compute_event_hash_v2(prev_hash: str, recorded_at: str, payload: dict[str, Any]) -> str:
    """Hash function for chain rows.

    ``event_hash = sha256(canonical_json({"_chain": prev_hash,
                                          "_recorded_at": recorded_at,
                                          "_payload": payload}))``

    Three commitments (chain head, timestamp, payload) are bound together
    so:

    * Changing any byte of any earlier payload changes that row's
      event_hash, which changes the next row's prev_hash, and so on. This
      gives forgery resistance.
    * Binding the timestamp means two rows with identical payloads but
      different recorded_at values cannot be swapped without detection.

    The ``_v2`` suffix is reserved for a future migration; the current
    chain uses this construction exclusively.
    """
    return sha256_of(
        {
            "_chain": prev_hash,
            "_recorded_at": recorded_at,
            "_payload": payload,
        }
    )


# ----------------------------------------------------------------------------
# Concurrency: file lock
# ----------------------------------------------------------------------------


@contextmanager
def _file_lock(lock_path: Path, timeout_s: float = 10.0) -> Iterator[None]:
    """Acquire an exclusive advisory lock on ``lock_path``.

    POSIX uses ``fcntl.flock``. On Windows we fall back to a busy-wait loop
    on ``os.open(O_CREAT|O_EXCL)``.
    """
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout_s
    if sys.platform != "win32":
        import fcntl

        fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR, 0o600)
        try:
            while True:
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except OSError as exc:
                    if exc.errno not in (errno.EACCES, errno.EAGAIN):
                        raise
                    if time.monotonic() > deadline:
                        raise TimeoutError(f"Could not acquire lock {lock_path}") from exc
                    time.sleep(0.01)
            yield
        finally:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            finally:
                os.close(fd)
    else:  # pragma: no cover — Windows path
        while True:
            try:
                fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o600)
                try:
                    yield
                finally:
                    os.close(fd)
                    try:
                        os.remove(lock_path)
                    except FileNotFoundError:
                        pass
                return
            except FileExistsError:
                if time.monotonic() > deadline:
                    raise TimeoutError(f"Could not acquire lock {lock_path}")
                time.sleep(0.01)


# ----------------------------------------------------------------------------
# AuditLog
# ----------------------------------------------------------------------------


class AuditLog:
    """The hash-chained, append-only audit log family.

    Construct with the audit-root directory; one ``AuditLog`` instance can
    write to all eleven categories.

    Example::

        log = AuditLog(Path("./audit/runtime"))
        row = log.append_event("decisions", {"decision_id": "decision:abc", ...})
        result = log.validate_chain("decisions")
        assert result.ok
    """

    def __init__(self, audit_dir: str | Path) -> None:
        self.audit_dir = Path(audit_dir).resolve()
        self.audit_dir.mkdir(parents=True, exist_ok=True)

    # ---- path helpers ------------------------------------------------------

    def path_for(self, category: AuditCategory) -> Path:
        if category not in AUDIT_FILENAMES:
            raise ValueError(f"unknown audit category {category!r}")
        return self.audit_dir / AUDIT_FILENAMES[category]

    def lock_path_for(self, category: AuditCategory) -> Path:
        return self.audit_dir / f".{AUDIT_FILENAMES[category]}.lock"

    # ---- append / read primitives ------------------------------------------

    def head_hash(self, category: AuditCategory) -> str:
        """Return the most recent row's event_hash (or genesis if file empty)."""
        target = self.path_for(category)
        if not target.exists() or target.stat().st_size == 0:
            return GENESIS_PREV_HASH
        last_event_hash = GENESIS_PREV_HASH
        with target.open("rb") as f:
            for raw in f:
                raw = raw.strip()
                if not raw:
                    continue
                obj = orjson.loads(raw)
                last_event_hash = obj["event_hash"]
        return last_event_hash

    def append_event(
        self,
        category: AuditCategory,
        payload: dict[str, Any],
        recorded_at: str | None = None,
    ) -> AuditRow:
        """Append one row atomically to ``${category}.jsonl``.

        Steps:
          1. Acquire the lock for the category file.
          2. Read the current head hash (last event_hash, or genesis).
          3. Compute a row whose ``prev_hash = head``, ``event_hash =
             sha256_of(chain || timestamp || payload)``.
          4. Append the row's canonical JSON line.
          5. Release the lock.

        Returns the validated :class:`AuditRow`.
        """
        if category not in AUDIT_FILENAMES:
            raise ValueError(f"unknown audit category {category!r}")
        ts = recorded_at or _utc_now_iso()
        target = self.path_for(category)
        lock_p = self.lock_path_for(category)
        with _file_lock(lock_p):
            prev = self.head_hash(category)
            event = _compute_event_hash_v2(prev, ts, payload)
            row = AuditRow(
                category=category,
                recorded_at=ts,
                prev_hash=prev,
                event_hash=event,
                payload=payload,
            )
            line = orjson.dumps(row.model_dump(mode="json"), option=orjson.OPT_SORT_KEYS)
            self._atomic_append(target, line + b"\n")
        return row

    def iter_rows(self, category: AuditCategory) -> Iterator[AuditRow]:
        """Yield all rows from the category file, in append order."""
        target = self.path_for(category)
        if not target.exists():
            return
        with target.open("rb") as f:
            for raw in f:
                raw = raw.strip()
                if not raw:
                    continue
                yield AuditRow.model_validate_json(raw)

    def tail(self, category: AuditCategory, n: int) -> list[AuditRow]:
        """Return the last ``n`` rows of the category file."""
        if n <= 0:
            return []
        all_rows = list(self.iter_rows(category))
        return all_rows[-n:]

    # ---- chain validation --------------------------------------------------

    def validate_chain(self, category: AuditCategory) -> ChainValidationResult:
        """Recompute the full chain for ``category`` and report divergences.

        Detects every form of tampering:

        * **Row tampering**: any byte changed in a payload changes that row's
          recomputed event_hash; subsequent prev_hashes won't match.
        * **Row reorder**: the recomputed prev_hash for row i is row i-1's
          event_hash; reordering breaks both rows' chain links.
        * **Row insert**: an inserted row will have a wrong prev_hash relative
          to the row above it (or its own event_hash will not match its
          payload).
        * **Row delete**: a deleted row leaves the row that followed pointing
          at a prev_hash that no longer matches the now-prior row's event_hash.

        Returns a :class:`ChainValidationResult`. ``ok=True`` means no
        divergence in any of the above. ``errors`` is the full list (not
        just the first) so a forensic dump shows the entire damage.
        """
        target = self.path_for(category)
        errors: list[str] = []
        first_bad: int | None = None
        if not target.exists():
            return ChainValidationResult(ok=True, checked_rows=0, errors=[])

        rows: list[dict[str, Any]] = []
        with target.open("rb") as f:
            for line_no, raw in enumerate(f):
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    obj = orjson.loads(raw)
                except orjson.JSONDecodeError as exc:
                    errors.append(f"row {line_no}: malformed JSON ({exc})")
                    if first_bad is None:
                        first_bad = line_no
                    continue
                rows.append(obj)

        expected_prev = GENESIS_PREV_HASH
        for idx, obj in enumerate(rows):
            # Structural checks first.
            for required in ("category", "recorded_at", "prev_hash", "event_hash", "payload"):
                if required not in obj:
                    errors.append(f"row {idx}: missing field {required!r}")
                    if first_bad is None:
                        first_bad = idx
                    expected_prev = obj.get("event_hash", expected_prev)
                    continue

            if obj.get("category") != category:
                errors.append(
                    f"row {idx}: category mismatch (got {obj.get('category')!r}, expected {category!r})"
                )
                if first_bad is None:
                    first_bad = idx

            # prev_hash check — must equal the expected chain head.
            if obj.get("prev_hash") != expected_prev:
                errors.append(
                    f"row {idx}: prev_hash mismatch "
                    f"(got {obj.get('prev_hash')!r}, expected {expected_prev!r})"
                )
                if first_bad is None:
                    first_bad = idx

            # Recompute event_hash from the row contents.
            recomputed = _compute_event_hash_v2(
                prev_hash=expected_prev,
                recorded_at=obj.get("recorded_at", ""),
                payload=obj.get("payload", {}),
            )
            if obj.get("event_hash") != recomputed:
                errors.append(
                    f"row {idx}: event_hash mismatch "
                    f"(got {obj.get('event_hash')!r}, expected {recomputed!r})"
                )
                if first_bad is None:
                    first_bad = idx

            # Advance expected_prev to the *recorded* event_hash if it matches
            # what we recomputed; otherwise we still try to keep going so we
            # can report all divergences.
            expected_prev = obj.get("event_hash", recomputed)

        ok = len(errors) == 0
        return ChainValidationResult(
            ok=ok,
            checked_rows=len(rows),
            first_bad_index=first_bad,
            errors=errors,
        )

    # ---- atomic append (private) -------------------------------------------

    def _atomic_append(self, target: Path, line_bytes: bytes) -> None:
        """Append ``line_bytes`` to ``target`` with fsync-then-rename atomicity.

        Strategy: copy the existing file (if any) into a temp file in the same
        directory, append the new bytes, fsync, then rename over the original.
        That is the only way to guarantee a partially-written line never
        appears in the file under crash-recovery semantics.

        Concurrency is handled by the surrounding ``_file_lock`` — multiple
        processes serialise on the lock, so only one ``_atomic_append`` runs
        per file at a time.
        """
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp_dir = target.parent
        with tempfile.NamedTemporaryFile(
            mode="wb",
            delete=False,
            dir=str(tmp_dir),
            prefix=f".{target.name}.tmp-",
            suffix=".jsonl",
        ) as tf:
            tmp_path = Path(tf.name)
            try:
                # 1. copy existing contents (if any).
                if target.exists():
                    with target.open("rb") as src:
                        while True:
                            chunk = src.read(1 << 16)
                            if not chunk:
                                break
                            tf.write(chunk)
                # 2. append the new line.
                tf.write(line_bytes)
                tf.flush()
                os.fsync(tf.fileno())
            except BaseException:
                # Make sure we don't leak the temp file on error.
                tmp_path.unlink(missing_ok=True)
                raise
        # 3. atomic rename. On POSIX this is guaranteed by ``os.replace``.
        os.replace(str(tmp_path), str(target))
