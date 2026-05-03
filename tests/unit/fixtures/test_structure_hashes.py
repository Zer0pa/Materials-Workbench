"""Verify every positive structure fixture parses + hashes deterministically.

Each positive fixture under ``fixtures/structures/<name>/`` ships with a
``structure.cif`` and a ``manifest.json`` that records the deterministic
``structure_hash``. This test recomputes the hash via
``zer0pa_materials_workbench.envelope.hashing.cif_hash_from_text`` and asserts
exact equality. Any future drift in the parser, the canonicalisation, or
the CIF coordinate values is caught here.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.unit.fixtures.conftest import FIXTURES_ROOT
from zer0pa_materials_workbench.envelope.hashing import (
    cif_hash_from_text,
    parse_minimal_cif,
    structure_hash,
)

# Walk fixtures/structures/ and collect every directory that contains a
# structure.cif AND a manifest.json. Some fixtures (LLZO/cubic, LLZO/tetragonal)
# are nested two levels deep.


def _collect_positive_fixtures() -> list[Path]:
    out: list[Path] = []
    root = FIXTURES_ROOT / "structures"
    for cif in sorted(root.rglob("structure.cif")):
        manifest = cif.parent / "manifest.json"
        if manifest.exists():
            out.append(cif.parent)
    return out


POSITIVE_FIXTURES = _collect_positive_fixtures()


@pytest.mark.parametrize("fixture_dir", POSITIVE_FIXTURES, ids=[p.name for p in POSITIVE_FIXTURES])
def test_positive_fixture_parses(fixture_dir: Path) -> None:
    cif_text = (fixture_dir / "structure.cif").read_text()
    structure = parse_minimal_cif(cif_text)
    # Sanity checks on the parsed dict shape.
    assert "lattice_vectors" in structure
    assert "species" in structure
    assert "fractional_coords" in structure
    assert len(structure["species"]) == len(structure["fractional_coords"])
    assert len(structure["species"]) >= 1
    assert len(structure["lattice_vectors"]) == 3


@pytest.mark.parametrize("fixture_dir", POSITIVE_FIXTURES, ids=[p.name for p in POSITIVE_FIXTURES])
def test_positive_fixture_hash_matches_manifest(fixture_dir: Path) -> None:
    cif_text = (fixture_dir / "structure.cif").read_text()
    manifest = json.loads((fixture_dir / "manifest.json").read_text())
    expected = manifest["structure_hash"]
    actual = cif_hash_from_text(cif_text)
    assert actual == expected, (
        f"structure_hash mismatch for {fixture_dir.name}: "
        f"manifest says {expected!r} but recomputation gave {actual!r}"
    )


@pytest.mark.parametrize("fixture_dir", POSITIVE_FIXTURES, ids=[p.name for p in POSITIVE_FIXTURES])
def test_positive_fixture_hash_is_deterministic(fixture_dir: Path) -> None:
    cif_text = (fixture_dir / "structure.cif").read_text()
    structure = parse_minimal_cif(cif_text)
    h1 = structure_hash(structure)
    h2 = structure_hash(structure)
    assert h1 == h2


def test_distinct_fixtures_have_distinct_hashes() -> None:
    """No two distinct positive fixtures collide on structure_hash."""
    hashes: dict[str, str] = {}
    for fixture_dir in POSITIVE_FIXTURES:
        cif_text = (fixture_dir / "structure.cif").read_text()
        h = cif_hash_from_text(cif_text)
        if h in hashes:
            pytest.fail(
                f"hash collision: {fixture_dir.name} and {hashes[h]} share {h}"
            )
        hashes[h] = fixture_dir.name


def test_positive_fixture_count() -> None:
    """We expect exactly 11 positive fixtures (PRD §A2 list).

    H2, LiH, Si, NaCl, LLZO/cubic, LLZO/tetragonal, Li6PS5Cl,
    Li-Mg-Zr-Cl-seed, Bi2Te3, PbTe, SnSe.
    """
    names = {p.name for p in POSITIVE_FIXTURES}
    expected = {
        "H2",
        "LiH",
        "Si",
        "NaCl",
        "cubic",  # LLZO/cubic
        "tetragonal",  # LLZO/tetragonal
        "Li6PS5Cl",
        "Li-Mg-Zr-Cl-seed",
        "Bi2Te3",
        "PbTe",
        "SnSe",
    }
    assert names == expected, f"unexpected positive fixture set: {names ^ expected}"
