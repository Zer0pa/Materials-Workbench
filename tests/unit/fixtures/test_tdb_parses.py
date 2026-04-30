"""Verify the toy TDBs pass a syntactic-shape parser (no pycalphad assumed).

If pycalphad is installed, also try the full parse via
``pycalphad.io.tdb.read_tdb``. If pycalphad is NOT installed, the
syntactic-shape parser is the load-bearing check (parked-pending state
is documented in the manifests).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from tests.unit.fixtures.conftest import (
    FIXTURES_ROOT,
    _tdb_syntactically_well_formed,
)


TDB_PATHS = sorted(
    p for p in (FIXTURES_ROOT / "tdb").rglob("*.tdb")
)


PYCALPHAD_AVAILABLE = importlib.util.find_spec("pycalphad") is not None


@pytest.mark.parametrize("tdb_path", TDB_PATHS, ids=[p.name for p in TDB_PATHS])
def test_tdb_syntactic_shape_well_formed(tdb_path: Path) -> None:
    text = tdb_path.read_text()
    assert _tdb_syntactically_well_formed(text), (
        f"{tdb_path.name}: failed syntactic-shape parse"
    )


@pytest.mark.parametrize("tdb_path", TDB_PATHS, ids=[p.name for p in TDB_PATHS])
@pytest.mark.skipif(not PYCALPHAD_AVAILABLE, reason="pycalphad not installed")
def test_tdb_parses_in_pycalphad(tdb_path: Path) -> None:
    """Full pycalphad parse — only runs when pycalphad is on the import path."""
    from pycalphad import Database  # type: ignore[import-not-found]

    db = Database(str(tdb_path))
    # Sanity: at least one element registered and at least one phase defined.
    assert len(db.elements) >= 2
    assert len(db.phases) >= 1


def test_broken_tdb_rejected_by_syntactic_shape() -> None:
    """The negative fixture's broken TDB MUST fail the shape check."""
    broken_path = FIXTURES_ROOT / "negatives" / "unreadable_tdb" / "broken.tdb"
    text = broken_path.read_text()
    assert not _tdb_syntactically_well_formed(text)


def test_tdb_count() -> None:
    """Exactly two TDB fixtures: Cu-Mg-toy and Li-halide-toy."""
    names = {p.name for p in TDB_PATHS}
    assert names == {"Cu-Mg-toy.tdb", "Li-halide-toy.tdb"}, (
        f"unexpected TDB set: {names}"
    )
