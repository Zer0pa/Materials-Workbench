"""Falsification wave: synthesised L3 envelope claiming use of commercial
TDB while ``MaterialsConfig.L3_COMMERCIAL_TDB_PROVIDER == 'disabled'``
triggers EXACTLY ``commercial_tdb_provider_disabled_by_default``.

PRD §Core Config Flags + §L3 quarantine: the default config posture is
``L3_COMMERCIAL_TDB_PROVIDER=disabled``. An envelope that claims commercial
TDB use while the config says disabled is a falsifier failure.
"""

from __future__ import annotations

import pytest

from zer0pa_materials.envelope import RESEARCH_BOUNDARY
from zer0pa_materials.falsifiers.l3_falsifiers import (
    commercial_tdb_provider_disabled_by_default,
    espei_posterior_diagnostics,
    phase_boundary_drift,
    phaseforgeplus_license_gate,
    tdb_quarantine_breach,
)


def _commercial_claim_envelope() -> dict:
    """An envelope that claims to have used a commercial TDB provider."""
    return {
        "research_boundary": RESEARCH_BOUNDARY,
        "contract_version": "zer0pa.materials.layer-envelope.v1",
        "layer": "L3",
        "run_id": "run:falsification/cfg/001",
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
            "audit_record_id": "audit:falsification/cfg/001",
            "input_hash": "sha256:" + "0" * 64,
            "output_hash": "sha256:" + "0" * 64,
            "source_manifest_refs": [],
        },
        "rights": {"rights_claim_id": "rights:falsification/001", "reuse_scope": "tenant_only"},
        "back_edges": [],
        "_quarantine_meta": {
            "tdb_provider": "ThermoCalc",
            "license": "proprietary",
            "redistributable": False,
            "committed_to_repo": False,
            "included_in_training_corpus": False,
            "customer_id": None,
        },
    }


class TestCommercialTdbDisabledByDefault:
    def test_falsifier_fails_when_config_disabled_but_envelope_claims_commercial(self):
        envelope = _commercial_claim_envelope()
        result = commercial_tdb_provider_disabled_by_default(
            envelope, materials_config_provider_value="disabled"
        )
        assert result.status == "fail"

    def test_falsifier_passes_for_non_commercial_envelope(self):
        envelope = _commercial_claim_envelope()
        # Drop the quarantine metadata.
        envelope.pop("_quarantine_meta")
        envelope["tool_adapter"]["engine"] = "pycalphad-stub"
        envelope["tool_adapter"]["backend"] = "stub"
        result = commercial_tdb_provider_disabled_by_default(
            envelope, materials_config_provider_value="disabled"
        )
        assert result.status == "pass"

    def test_falsifier_passes_when_config_explicitly_quarantined_with_customer(self):
        envelope = _commercial_claim_envelope()
        envelope["_quarantine_meta"]["customer_id"] = "customer:acme:001"
        result = commercial_tdb_provider_disabled_by_default(
            envelope, materials_config_provider_value="thermo_calc_quarantined"
        )
        assert result.status == "pass"

    def test_falsifier_fails_when_config_quarantined_but_no_customer(self):
        envelope = _commercial_claim_envelope()
        # customer_id is None.
        result = commercial_tdb_provider_disabled_by_default(
            envelope, materials_config_provider_value="thermo_calc_quarantined"
        )
        assert result.status == "fail"

    def test_falsifier_blocked_for_unknown_config_value(self):
        envelope = _commercial_claim_envelope()
        result = commercial_tdb_provider_disabled_by_default(
            envelope, materials_config_provider_value="unknown_future_value"
        )
        assert result.status == "blocked"


class TestExclusivity:
    """The commercial-tdb gate should be the ONLY one that fires on this
    fixture (other than tdb_quarantine_breach which is not exclusive — both
    target the same policy)."""

    def test_phase_boundary_drift_blocked(self):
        envelope = _commercial_claim_envelope()
        result = phase_boundary_drift(envelope)
        assert result.status == "blocked"

    def test_espei_diagnostics_blocked(self):
        envelope = _commercial_claim_envelope()
        result = espei_posterior_diagnostics(envelope)
        assert result.status == "blocked"

    def test_phaseforgeplus_gate_passes(self):
        envelope = _commercial_claim_envelope()
        result = phaseforgeplus_license_gate(envelope)
        assert result.status == "pass"

    def test_quarantine_breach_passes(self):
        # The fixture's redistributable=False, committed_to_repo=False, etc.
        # are clean — only the config-vs-claim mismatch fails.
        envelope = _commercial_claim_envelope()
        result = tdb_quarantine_breach(envelope)
        assert result.status == "pass"

    def test_only_default_disabled_falsifier_fails(self):
        envelope = _commercial_claim_envelope()
        results = {
            "commercial_tdb_provider_disabled_by_default": commercial_tdb_provider_disabled_by_default(
                envelope, materials_config_provider_value="disabled"
            ),
            "tdb_quarantine_breach": tdb_quarantine_breach(envelope),
            "phase_boundary_drift": phase_boundary_drift(envelope),
            "espei_posterior_diagnostics": espei_posterior_diagnostics(envelope),
            "phaseforgeplus_license_gate": phaseforgeplus_license_gate(envelope),
        }
        failed = [name for name, r in results.items() if r.status == "fail"]
        assert failed == ["commercial_tdb_provider_disabled_by_default"], (
            f"Expected only 'commercial_tdb_provider_disabled_by_default' to fail; got: {failed}"
        )
