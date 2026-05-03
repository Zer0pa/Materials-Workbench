"""Schema-validate every fixture manifest and budget the total committed footprint.

PRD §Constraints / §Hard Gates explicitly forbids bulk local datasets.
The fixture wave commits to a 1 MB upper bound on the entire
``fixtures/`` tree (:data:`tests.unit.fixtures.conftest.BUDGET_BYTES`).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.unit.fixtures.conftest import (
    BUDGET_BYTES,
    FIXTURES_ROOT,
    RESEARCH_BOUNDARY,
    iter_manifests,
    total_committed_bytes,
)

REQUIRED_KEYS = (
    "research_boundary",
    "fixture_id",
    "name",
    "kind",
    "purpose",
    "sources",
    "expected_use_layers",
    "structure_hash",
    "size_bytes",
    "novelty_status",
    "negative_falsifier_target",
    "verified",
    "notes",
)

ALLOWED_KINDS = {"structure", "extraction", "tdb", "negative"}
ALLOWED_NOVELTY = {"pending", "known", "synthetic_known", "deliberate_violation"}


def _all_manifest_paths() -> list[Path]:
    out: list[Path] = []
    for path, _ in iter_manifests():
        out.append(path)
    return out


ALL_MANIFESTS = _all_manifest_paths()


@pytest.mark.parametrize("manifest_path", ALL_MANIFESTS, ids=[str(p.relative_to(FIXTURES_ROOT)) for p in ALL_MANIFESTS])
def test_manifest_has_required_keys(manifest_path: Path) -> None:
    data = json.loads(manifest_path.read_text())
    missing = [k for k in REQUIRED_KEYS if k not in data]
    assert not missing, (
        f"{manifest_path.relative_to(FIXTURES_ROOT)}: missing keys {missing}"
    )


@pytest.mark.parametrize("manifest_path", ALL_MANIFESTS, ids=[str(p.relative_to(FIXTURES_ROOT)) for p in ALL_MANIFESTS])
def test_manifest_boundary_block_verbatim(manifest_path: Path) -> None:
    data = json.loads(manifest_path.read_text())
    assert data["research_boundary"] == RESEARCH_BOUNDARY, (
        f"{manifest_path.relative_to(FIXTURES_ROOT)}: research_boundary not verbatim"
    )


@pytest.mark.parametrize("manifest_path", ALL_MANIFESTS, ids=[str(p.relative_to(FIXTURES_ROOT)) for p in ALL_MANIFESTS])
def test_manifest_kind_is_allowed(manifest_path: Path) -> None:
    data = json.loads(manifest_path.read_text())
    assert data["kind"] in ALLOWED_KINDS, (
        f"{manifest_path.relative_to(FIXTURES_ROOT)}: unknown kind {data['kind']!r}"
    )


@pytest.mark.parametrize("manifest_path", ALL_MANIFESTS, ids=[str(p.relative_to(FIXTURES_ROOT)) for p in ALL_MANIFESTS])
def test_manifest_novelty_is_allowed(manifest_path: Path) -> None:
    data = json.loads(manifest_path.read_text())
    assert data["novelty_status"] in ALLOWED_NOVELTY, (
        f"{manifest_path.relative_to(FIXTURES_ROOT)}: unknown novelty_status {data['novelty_status']!r}"
    )


@pytest.mark.parametrize("manifest_path", ALL_MANIFESTS, ids=[str(p.relative_to(FIXTURES_ROOT)) for p in ALL_MANIFESTS])
def test_manifest_negative_target_consistent_with_kind(manifest_path: Path) -> None:
    data = json.loads(manifest_path.read_text())
    if data["kind"] == "negative":
        assert data["negative_falsifier_target"] is not None, (
            f"{manifest_path.relative_to(FIXTURES_ROOT)}: negative kind requires non-null negative_falsifier_target"
        )
        assert data["novelty_status"] == "deliberate_violation", (
            f"{manifest_path.relative_to(FIXTURES_ROOT)}: negative kind requires novelty_status='deliberate_violation'"
        )
    else:
        assert data["negative_falsifier_target"] is None, (
            f"{manifest_path.relative_to(FIXTURES_ROOT)}: non-negative kind must have null negative_falsifier_target"
        )


@pytest.mark.parametrize("manifest_path", ALL_MANIFESTS, ids=[str(p.relative_to(FIXTURES_ROOT)) for p in ALL_MANIFESTS])
def test_manifest_fixture_id_unique(manifest_path: Path) -> None:
    """Every fixture_id is unique across the manifest set."""
    seen: dict[str, str] = {}
    for path, data in iter_manifests():
        fid = data["fixture_id"]
        if fid in seen:
            pytest.fail(f"duplicate fixture_id {fid!r}: {seen[fid]} and {path.relative_to(FIXTURES_ROOT)}")
        seen[fid] = str(path.relative_to(FIXTURES_ROOT))


@pytest.mark.parametrize("manifest_path", ALL_MANIFESTS, ids=[str(p.relative_to(FIXTURES_ROOT)) for p in ALL_MANIFESTS])
def test_manifest_sources_present(manifest_path: Path) -> None:
    data = json.loads(manifest_path.read_text())
    sources = data["sources"]
    assert isinstance(sources, list), f"{manifest_path}: sources must be list"
    assert len(sources) >= 1, f"{manifest_path}: must have at least one source"
    for src in sources:
        assert "type" in src and "locator" in src and "license" in src, (
            f"{manifest_path}: each source must carry type/locator/license"
        )


def test_total_footprint_under_budget() -> None:
    """The whole fixtures/ tree fits in BUDGET_BYTES."""
    total = total_committed_bytes()
    assert total <= BUDGET_BYTES, (
        f"committed fixture footprint {total} bytes exceeds budget {BUDGET_BYTES}"
    )


def test_no_fixture_path_implies_bulk_data() -> None:
    """Refuse to ship anything that smells like a bulk dataset.

    This is a string-based hygiene check: nothing in fixtures/ should be
    named or located like a bulk artifact (e.g., ``*.tar.gz``, ``*.h5``,
    ``*.npz`` files larger than 100 KB, dataset-style top-level dirs).
    """
    suspicious_extensions = {".h5", ".hdf5", ".npz", ".tar.gz", ".tar", ".zip", ".parquet", ".feather"}
    for path in FIXTURES_ROOT.rglob("*"):
        if not path.is_file():
            continue
        if path.name == ".gitkeep":
            continue
        for ext in suspicious_extensions:
            if path.name.endswith(ext):
                pytest.fail(f"suspicious bulk-data file in fixtures: {path.relative_to(FIXTURES_ROOT)}")


def test_manifest_count_per_category() -> None:
    """Counts: 11 structures, 13 negatives, 3 extractions, 2 TDBs."""
    by_kind: dict[str, int] = {}
    for _, data in iter_manifests():
        by_kind[data["kind"]] = by_kind.get(data["kind"], 0) + 1
    assert by_kind == {
        "structure": 11,
        "negative": 13,
        "extraction": 3,
        "tdb": 2,
    }, f"unexpected per-kind manifest counts: {by_kind}"
