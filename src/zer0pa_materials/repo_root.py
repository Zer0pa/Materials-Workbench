"""Central repo-root resolution.

Single source of truth for "where is this repository?" used by every CLI
command, audit-log default path, fixture loader, and Runpod cutover artifact
emitter. Fixes the prior pattern of hard-coding ``/Users/zer0palab/Materials
Pipeline/...`` (which broke fresh clones) and the prior pattern of writing
artifacts to ``/tmp`` (which lost them outside the repo).

Resolution strategy (first match wins):

1. ``ZER0PA_MATERIALS_REPO_ROOT`` environment variable.
2. Walk up from this module's file path looking for a ``pyproject.toml``
   whose ``[project].name`` is ``zer0pa-materials``.
3. Walk up from the current working directory using the same predicate.

Boundary
--------
Research infrastructure for in silico materials science discovery. Outputs are
research artifacts. No regulatory certification claims. No clinical or
human-subject use. ITAR / weapons applications are out of scope (Meta UMA
Acceptable Use Policy and operator policy).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Final

_PYPROJECT_NEEDLE: Final[str] = 'name = "zer0pa-materials"'


class RepoRootNotFoundError(RuntimeError):
    """Raised when no zer0pa-materials repo root can be located."""


def _is_zer0pa_materials_root(candidate: Path) -> bool:
    pyproject = candidate / "pyproject.toml"
    if not pyproject.is_file():
        return False
    try:
        return _PYPROJECT_NEEDLE in pyproject.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False


def _walk_up(start: Path) -> Path | None:
    cur = start.resolve()
    for parent in (cur, *cur.parents):
        if _is_zer0pa_materials_root(parent):
            return parent
    return None


def repo_root() -> Path:
    """Return the absolute path to the zer0pa-materials repo root.

    Raises:
        RepoRootNotFoundError: if no candidate matches.
    """
    env = os.environ.get("ZER0PA_MATERIALS_REPO_ROOT")
    if env:
        candidate = Path(env).expanduser().resolve()
        if _is_zer0pa_materials_root(candidate):
            return candidate
        raise RepoRootNotFoundError(
            f"ZER0PA_MATERIALS_REPO_ROOT={env!r} does not look like a "
            "zer0pa-materials repo (no pyproject.toml with that name)."
        )

    found = _walk_up(Path(__file__).resolve())
    if found is not None:
        return found
    found = _walk_up(Path.cwd())
    if found is not None:
        return found
    raise RepoRootNotFoundError(
        "Could not locate zer0pa-materials repo root. Set "
        "ZER0PA_MATERIALS_REPO_ROOT or run from inside the repo."
    )


def fixtures_root() -> Path:
    """Return the absolute path to ``<repo>/fixtures/``."""
    return repo_root() / "fixtures"


def audit_root(*, runtime: bool = True) -> Path:
    """Return the audit directory.

    Args:
        runtime: when True (default), return ``<repo>/audit/runtime/`` —
            the standard append-only-log path for live runs. When False,
            return ``<repo>/audit/`` (parent of all audit subdirectories,
            including any committed evidence snapshots).
    """
    base = repo_root() / "audit"
    return base / "runtime" if runtime else base


def artifacts_root() -> Path:
    """Return ``<repo>/artifacts/runtime/`` for in-repo artifact emission."""
    return repo_root() / "artifacts" / "runtime"


def phase_dir(phase_name: str) -> Path:
    """Return ``<repo>/phases/<phase_name>/``."""
    return repo_root() / "phases" / phase_name


def fixture(*relative_parts: str) -> Path:
    """Compose an absolute fixture path from repo-relative components.

    Examples:
        ``fixture("structures", "H2", "structure.cif")``
        → ``<repo>/fixtures/structures/H2/structure.cif``
    """
    return fixtures_root().joinpath(*relative_parts)


def read_fixture(*relative_parts: str, encoding: str = "utf-8") -> str:
    """Read a text fixture at ``<repo>/fixtures/<relative_parts>``."""
    return fixture(*relative_parts).read_text(encoding=encoding)
