"""Falsification wave: tdb_quarantine_breach fixture triggers EXACTLY tdb_quarantine_breach.

The fixture ``fixtures/negatives/tdb_quarantine_breach/tdb_claim.json`` is a
synthetic CLAIM/manifest naming a Thermo-Calc commercial TDB with
``redistributable=true`` — a contradiction the L3 falsifier must detect.

PRD §L3 verbatim:
    Commercial TDB data must never be committed, copied into fixtures,
    redistributed, or used as general training data.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from zer0pa_materials_workbench.envelope import RESEARCH_BOUNDARY
from zer0pa_materials_workbench.falsifiers.l3_falsifiers import (
    espei_posterior_diagnostics,
    phase_boundary_drift,
    phaseforgeplus_license_gate,
    tdb_quarantine_breach,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURE_DIR = REPO_ROOT / "fixtures" / "negatives" / "tdb_quarantine_breach"
TDB_CLAIM = FIXTURE_DIR / "tdb_claim.json"
MANIFEST = FIXTURE_DIR / "manifest.json"


def _envelope_from_claim(claim_path: Path) -> dict:
    """Wrap the fixture JSON into an L3 envelope shape so the falsifier can consume it."""
    claim = json.loads(claim_path.read_text())
    return {
        "research_boundary": RESEARCH_BOUNDARY,
        "contract_version": "zer0pa.materials.layer-envelope.v1",
        "layer": "L3",
        "run_id": "run:falsification/tdb-quarantine/001",
        "candidate_id": "candidate:test:001",
        "campaign_id": "campaign:falsification/001",
        "tool_adapter": {
            "name": "ThermoCalcTdbReadOnlyAdapter",
            "version": "0.1.0",
            "backend": "local_cpu",
            "engine": "thermo-calc-quarantined-read-only",
        },
        "output": {
            "tdb_ref": f"hash://sha256:{'0' * 64}",
            "equilibrium_phases": [],
            "phase_fraction_posterior": {},
            "espei_diagnostics": {},
            "fixture_phase_boundary_drift_K": None,
            "phase_set_jaccard_distance": None,
            "phase_fraction_js_divergence": None,
        },
        "confidence": {"score": 0.5, "band": "medium", "basis": []},
        "disagreement": {"metrics": []},
        "falsifier": {"status": "pass", "items": []},
        "audit": {
            "audit_record_id": "audit:falsification/tdb-quarantine/001",
            "input_hash": "sha256:" + "0" * 64,
            "output_hash": "sha256:" + "0" * 64,
            "source_manifest_refs": [],
        },
        "rights": {"rights_claim_id": "rights:falsification/001", "reuse_scope": "tenant_only"},
        "back_edges": [],
        # Carry the claim's fields into _quarantine_meta so the falsifier
        # has the same shape as the production code emits.
        "_quarantine_meta": {
            "tdb_provider": claim["tdb_provider"],
            "license": claim["license"],
            "redistributable": claim["redistributable"],
            "committed_to_repo": False,  # not present in the fixture; default
            "included_in_training_corpus": False,
            "customer_id": None,
        },
    }


class TestFixtureExists:
    def test_tdb_claim_exists(self):
        assert TDB_CLAIM.exists()

    def test_manifest_exists(self):
        assert MANIFEST.exists()

    def test_manifest_targets_quarantine_breach(self):
        m = json.loads(MANIFEST.read_text())
        assert m["negative_falsifier_target"] == "tdb_quarantine_breach"

    def test_claim_contains_redistributable_true(self):
        claim = json.loads(TDB_CLAIM.read_text())
        assert claim["redistributable"] is True

    def test_claim_provider_is_thermocalc(self):
        claim = json.loads(TDB_CLAIM.read_text())
        assert "ThermoCalc" in claim["tdb_provider"]


class TestQuarantineBreachTriggers:
    @pytest.fixture
    def envelope(self) -> dict:
        return _envelope_from_claim(TDB_CLAIM)

    def test_falsifier_fails(self, envelope):
        result = tdb_quarantine_breach(envelope)
        assert result.status == "fail"

    def test_falsifier_actual_contains_breach_flag(self, envelope):
        result = tdb_quarantine_breach(envelope)
        flags = result.actual["breach_flags"]
        assert "redistributable=True" in flags

    def test_falsifier_name(self, envelope):
        result = tdb_quarantine_breach(envelope)
        assert result.name == "l3.tdb_quarantine_breach"


class TestExclusivity:
    """Only tdb_quarantine_breach should fire on this fixture's envelope."""

    @pytest.fixture
    def envelope(self) -> dict:
        return _envelope_from_claim(TDB_CLAIM)

    def test_quarantine_breach_fails(self, envelope):
        result = tdb_quarantine_breach(envelope)
        assert result.status == "fail"

    def test_phase_boundary_drift_blocked(self, envelope):
        result = phase_boundary_drift(envelope)
        assert result.status == "blocked"

    def test_espei_diagnostics_blocked(self, envelope):
        result = espei_posterior_diagnostics(envelope)
        assert result.status == "blocked"

    def test_phaseforgeplus_gate_passes(self, envelope):
        # Not a PhaseForgePlus envelope.
        result = phaseforgeplus_license_gate(envelope)
        assert result.status == "pass"

    def test_only_quarantine_breach_fails(self, envelope):
        """Aggregate exclusivity: enumerate every L3 falsifier."""
        results = {
            "tdb_quarantine_breach": tdb_quarantine_breach(envelope),
            "phase_boundary_drift": phase_boundary_drift(envelope),
            "espei_posterior_diagnostics": espei_posterior_diagnostics(envelope),
            "phaseforgeplus_license_gate": phaseforgeplus_license_gate(envelope),
        }
        failed = [name for name, r in results.items() if r.status == "fail"]
        assert failed == ["tdb_quarantine_breach"], (
            f"Expected only 'tdb_quarantine_breach' to fail; got: {failed}"
        )
