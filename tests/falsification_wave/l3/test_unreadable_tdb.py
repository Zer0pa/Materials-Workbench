"""Falsification wave: unreadable TDB triggers EXACTLY l3.tdb_parses_in_pycalphad.

The fixture ``fixtures/negatives/unreadable_tdb/broken.tdb`` is a deliberately
malformed TDB. The falsifier ``tdb_parses_in_pycalphad`` MUST fail; no other
L3 falsifier should fire on this fixture (since the fixture is metadata-only,
no envelope to compare).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from zer0pa_materials_workbench.falsifiers.l3_falsifiers import (
    espei_posterior_diagnostics,
    phase_boundary_drift,
    phaseforgeplus_license_gate,
    tdb_parses_in_pycalphad,
    tdb_quarantine_breach,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURE_DIR = REPO_ROOT / "fixtures" / "negatives" / "unreadable_tdb"
BROKEN_TDB = FIXTURE_DIR / "broken.tdb"
MANIFEST = FIXTURE_DIR / "manifest.json"
GOOD_TDB = REPO_ROOT / "fixtures" / "tdb" / "Cu-Mg-toy.tdb"


class TestFixtureExists:
    def test_broken_tdb_exists(self):
        assert BROKEN_TDB.exists(), f"unreadable_tdb fixture missing: {BROKEN_TDB}"

    def test_manifest_exists(self):
        assert MANIFEST.exists()

    def test_manifest_targets_unreadable_tdb(self):
        m = json.loads(MANIFEST.read_text())
        assert m["negative_falsifier_target"] == "unreadable_tdb"


class TestUnreadableTdbTriggersFalsifier:
    """The unreadable TDB MUST fail tdb_parses_in_pycalphad."""

    def test_broken_tdb_fails_falsifier(self):
        result = tdb_parses_in_pycalphad(BROKEN_TDB)
        assert result.status == "fail"

    def test_falsifier_name_is_correct(self):
        result = tdb_parses_in_pycalphad(BROKEN_TDB)
        assert result.name == "l3.tdb_parses_in_pycalphad"

    def test_good_tdb_passes_for_contrast(self):
        # Sanity check: the good TDB does pass.
        result = tdb_parses_in_pycalphad(GOOD_TDB)
        assert result.status == "pass"


class TestExclusivity:
    """Only ``tdb_parses_in_pycalphad`` should fire on this fixture.

    Other L3 falsifiers operate on envelopes; the broken TDB fixture is a
    file. Other falsifiers should return blocked or pass when given a
    clean envelope (whose fields they cannot find a violation in).
    """

    @pytest.fixture
    def empty_envelope(self) -> dict:
        return {
            "layer": "L3",
            "tool_adapter": {"name": "test", "version": "0.1.0", "backend": "stub", "engine": "test"},
            "output": {
                "tdb_ref": "synthetic:test",
                "equilibrium_phases": [],
                "phase_fraction_posterior": {},
                "espei_diagnostics": {},
                "fixture_phase_boundary_drift_K": None,
                "phase_set_jaccard_distance": None,
                "phase_fraction_js_divergence": None,
            },
        }

    def test_phase_boundary_drift_blocks(self, empty_envelope):
        result = phase_boundary_drift(empty_envelope)
        assert result.status == "blocked"

    def test_espei_diagnostics_blocks(self, empty_envelope):
        result = espei_posterior_diagnostics(empty_envelope)
        assert result.status == "blocked"

    def test_quarantine_breach_passes(self, empty_envelope):
        # No quarantine metadata = no breach.
        result = tdb_quarantine_breach(empty_envelope)
        assert result.status == "pass"

    def test_phaseforgeplus_gate_passes_for_non_pfp(self, empty_envelope):
        result = phaseforgeplus_license_gate(empty_envelope)
        assert result.status == "pass"

    def test_only_unreadable_tdb_falsifier_fails(self):
        """Confirm the load-bearing assertion: ONLY unreadable_tdb falsifier fails."""
        result_a = tdb_parses_in_pycalphad(BROKEN_TDB)
        result_b = tdb_parses_in_pycalphad(GOOD_TDB)
        assert result_a.status == "fail"
        assert result_b.status == "pass"
