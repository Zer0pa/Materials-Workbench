"""Verify every negative fixture triggers EXACTLY its named falsifier target.

The PRD §Falsification wave enumerates the negative cases. Each negative
fixture under ``fixtures/negatives/<name>/`` carries
``manifest.negative_falsifier_target == <name>``. The test invokes the
stub `detect_falsifier` (in conftest) on each fixture and asserts that
the returned list contains EXACTLY ``[target]``. This pins the
falsifier-attribution contract: a negative fixture that triggers more
than one falsifier is "leaky" and would confuse the falsification wave.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.unit.fixtures.conftest import FIXTURES_ROOT, detect_falsifier


def _collect_negative_fixtures() -> list[Path]:
    out: list[Path] = []
    root = FIXTURES_ROOT / "negatives"
    if not root.exists():
        return out
    for sub in sorted(p for p in root.iterdir() if p.is_dir()):
        if (sub / "manifest.json").exists():
            out.append(sub)
    return out


NEGATIVE_FIXTURES = _collect_negative_fixtures()


@pytest.mark.parametrize(
    "fixture_dir", NEGATIVE_FIXTURES, ids=[p.name for p in NEGATIVE_FIXTURES]
)
def test_negative_fixture_triggers_named_target(fixture_dir: Path) -> None:
    manifest = json.loads((fixture_dir / "manifest.json").read_text())
    expected = manifest["negative_falsifier_target"]
    assert expected is not None, (
        f"negative fixture {fixture_dir.name} has null negative_falsifier_target"
    )
    fired = detect_falsifier(fixture_dir)
    assert fired == [expected], (
        f"fixture {fixture_dir.name}: expected exactly [{expected!r}], "
        f"got {fired!r}"
    )


@pytest.mark.parametrize(
    "fixture_dir", NEGATIVE_FIXTURES, ids=[p.name for p in NEGATIVE_FIXTURES]
)
def test_negative_target_matches_directory_name(fixture_dir: Path) -> None:
    """The directory name and the manifest target must be the same.

    This is a sanity gate: the directory layout encodes the target so
    later code (audit scripts, falsification wave) can scan by name.
    """
    manifest = json.loads((fixture_dir / "manifest.json").read_text())
    assert manifest["negative_falsifier_target"] == fixture_dir.name


def test_negative_fixture_count() -> None:
    """We expect exactly 13 negative fixtures (PRD §A2 list)."""
    names = {p.name for p in NEGATIVE_FIXTURES}
    expected = {
        "invalid_cif",
        "duplicate_candidate",
        "missing_boundary",
        "ungrounded_property",
        "unstable_phonon",
        "unreadable_tdb",
        "high_disagreement",
        "non_spd_tensor",
        "tdb_quarantine_breach",
        "alabos_executable_in_recipe_only",
        "runpod_schema_drift",
        "tenant_only_tuple_leak",
        "ionic_overclaim_no_service",
    }
    assert names == expected, f"unexpected negative fixture set: {names ^ expected}"


def test_no_negative_target_collisions() -> None:
    """Each negative_falsifier_target appears at most once across negatives."""
    seen: dict[str, str] = {}
    for fixture_dir in NEGATIVE_FIXTURES:
        manifest = json.loads((fixture_dir / "manifest.json").read_text())
        target = manifest["negative_falsifier_target"]
        if target in seen:
            pytest.fail(
                f"two negatives share target {target!r}: {seen[target]} and {fixture_dir.name}"
            )
        seen[target] = fixture_dir.name
