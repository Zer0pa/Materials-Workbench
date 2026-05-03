"""Unit tests for L3 falsifiers (PRD §L3 + §Falsification wave).

Each falsifier is exercised with both a passing case and a failing case.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from zer0pa_materials_workbench.envelope import RESEARCH_BOUNDARY
from zer0pa_materials_workbench.falsifiers.l3_falsifiers import (
    commercial_tdb_provider_disabled_by_default,
    espei_posterior_diagnostics,
    phase_boundary_drift,
    phase_fraction_js_divergence,
    phase_set_jaccard_distance,
    phaseforgeplus_license_gate,
    tdb_parses_in_pycalphad,
    tdb_quarantine_breach,
)

REPO_ROOT = Path(__file__).resolve().parents[4]
CU_MG_TDB = REPO_ROOT / "fixtures" / "tdb" / "Cu-Mg-toy.tdb"
LI_HALIDE_TDB = REPO_ROOT / "fixtures" / "tdb" / "Li-halide-toy.tdb"
BROKEN_TDB = REPO_ROOT / "fixtures" / "negatives" / "unreadable_tdb" / "broken.tdb"


def _envelope_with_output(output: dict[str, Any], extras: dict[str, Any] | None = None) -> dict:
    """Build a minimal wire-level envelope shell with ``output`` set."""
    base: dict[str, Any] = {
        "research_boundary": RESEARCH_BOUNDARY,
        "contract_version": "zer0pa.materials.layer-envelope.v1",
        "layer": "L3",
        "run_id": "run:l3/falsifier-test/001",
        "candidate_id": "candidate:l3:001",
        "campaign_id": "campaign:l3:001",
        "tool_adapter": {
            "name": "tester",
            "version": "0.1.0",
            "backend": "stub",
            "engine": "test-engine",
        },
        "output": output,
        "confidence": {"score": 0.5, "band": "medium", "basis": []},
        "disagreement": {"metrics": []},
        "falsifier": {"status": "pass", "items": []},
        "audit": {
            "audit_record_id": "audit:l3:001",
            "input_hash": "sha256:" + "0" * 64,
            "output_hash": "sha256:" + "0" * 64,
            "source_manifest_refs": [],
        },
        "rights": {"rights_claim_id": "rights:l3:001", "reuse_scope": "tenant_only"},
        "back_edges": [],
    }
    if extras:
        base.update(extras)
    return base


# ---------------------------------------------------------------------------
# tdb_parses_in_pycalphad
# ---------------------------------------------------------------------------


class TestTdbParsesInPycalphad:
    def test_cu_mg_tdb_passes(self):
        result = tdb_parses_in_pycalphad(CU_MG_TDB)
        assert result.status == "pass"

    def test_li_halide_tdb_passes(self):
        result = tdb_parses_in_pycalphad(LI_HALIDE_TDB)
        assert result.status == "pass"

    def test_broken_tdb_fails(self):
        result = tdb_parses_in_pycalphad(BROKEN_TDB)
        assert result.status == "fail"

    def test_missing_file_fails(self):
        result = tdb_parses_in_pycalphad(REPO_ROOT / "no-such-file.tdb")
        assert result.status == "fail"

    def test_falsifier_name_correct(self):
        result = tdb_parses_in_pycalphad(CU_MG_TDB)
        assert result.name == "l3.tdb_parses_in_pycalphad"


# ---------------------------------------------------------------------------
# phase_boundary_drift
# ---------------------------------------------------------------------------


class TestPhaseBoundaryDrift:
    def test_below_25K_passes(self):
        env = _envelope_with_output(
            {
                "tdb_ref": "synthetic:test",
                "equilibrium_phases": [],
                "phase_fraction_posterior": {},
                "espei_diagnostics": {},
                "fixture_phase_boundary_drift_K": 12.0,
                "phase_set_jaccard_distance": None,
                "phase_fraction_js_divergence": None,
            }
        )
        result = phase_boundary_drift(env)
        assert result.status == "pass"

    def test_above_25K_fails(self):
        env = _envelope_with_output(
            {
                "tdb_ref": "synthetic:test",
                "equilibrium_phases": [],
                "phase_fraction_posterior": {},
                "espei_diagnostics": {},
                "fixture_phase_boundary_drift_K": 30.0,
                "phase_set_jaccard_distance": None,
                "phase_fraction_js_divergence": None,
            }
        )
        result = phase_boundary_drift(env)
        assert result.status == "fail"

    def test_none_drift_blocked(self):
        env = _envelope_with_output(
            {
                "tdb_ref": "synthetic:test",
                "equilibrium_phases": [],
                "phase_fraction_posterior": {},
                "espei_diagnostics": {},
                "fixture_phase_boundary_drift_K": None,
                "phase_set_jaccard_distance": None,
                "phase_fraction_js_divergence": None,
            }
        )
        result = phase_boundary_drift(env)
        assert result.status == "blocked"

    def test_at_threshold_passes(self):
        env = _envelope_with_output(
            {
                "tdb_ref": "synthetic:test",
                "equilibrium_phases": [],
                "phase_fraction_posterior": {},
                "espei_diagnostics": {},
                "fixture_phase_boundary_drift_K": 25.0,  # boundary
                "phase_set_jaccard_distance": None,
                "phase_fraction_js_divergence": None,
            }
        )
        result = phase_boundary_drift(env)
        assert result.status == "pass"


# ---------------------------------------------------------------------------
# phase_set_jaccard_distance
# ---------------------------------------------------------------------------


def _envelope_with_phases(phases: list[str], fractions: dict[str, float] | None = None) -> dict:
    return _envelope_with_output(
        {
            "tdb_ref": "synthetic:test",
            "equilibrium_phases": phases,
            "phase_fraction_posterior": fractions or {p: 1.0 / len(phases) for p in phases},
            "espei_diagnostics": {},
            "fixture_phase_boundary_drift_K": None,
            "phase_set_jaccard_distance": None,
            "phase_fraction_js_divergence": None,
        }
    )


class TestPhaseSetJaccard:
    def test_identical_phase_sets_pass(self):
        env_a = _envelope_with_phases(["LIQUID", "FCC_A1", "HCP_A3"])
        env_b = _envelope_with_phases(["LIQUID", "FCC_A1", "HCP_A3"])
        result = phase_set_jaccard_distance(env_a, env_b)
        assert result.status == "pass"
        assert result.actual == 0.0

    def test_overlapping_sets_pass(self):
        env_a = _envelope_with_phases(["LIQUID", "FCC_A1", "HCP_A3"])
        env_b = _envelope_with_phases(["LIQUID", "FCC_A1", "HCP_A3", "BCC_A2"])
        # Jaccard distance = 1 - 3/4 = 0.25 (below 0.33 threshold)
        result = phase_set_jaccard_distance(env_a, env_b)
        assert result.status == "pass"
        assert abs(result.actual - 0.25) < 1e-9

    def test_disjoint_sets_fail(self):
        env_a = _envelope_with_phases(["LIQUID", "FCC_A1"])
        env_b = _envelope_with_phases(["BCC_A2", "HCP_A3"])
        # Jaccard distance = 1 - 0/4 = 1.0
        result = phase_set_jaccard_distance(env_a, env_b)
        assert result.status == "fail"
        assert result.actual == 1.0


# ---------------------------------------------------------------------------
# phase_fraction_js_divergence
# ---------------------------------------------------------------------------


class TestPhaseFractionJSDivergence:
    def test_identical_distributions_pass(self):
        env_a = _envelope_with_phases(["A", "B"], {"A": 0.5, "B": 0.5})
        env_b = _envelope_with_phases(["A", "B"], {"A": 0.5, "B": 0.5})
        result = phase_fraction_js_divergence(env_a, env_b)
        assert result.status == "pass"
        assert result.actual < 1e-9

    def test_close_distributions_pass(self):
        env_a = _envelope_with_phases(["A", "B"], {"A": 0.55, "B": 0.45})
        env_b = _envelope_with_phases(["A", "B"], {"A": 0.50, "B": 0.50})
        result = phase_fraction_js_divergence(env_a, env_b)
        assert result.status == "pass"

    def test_far_distributions_fail(self):
        env_a = _envelope_with_phases(["A", "B"], {"A": 0.99, "B": 0.01})
        env_b = _envelope_with_phases(["A", "B"], {"A": 0.01, "B": 0.99})
        result = phase_fraction_js_divergence(env_a, env_b)
        assert result.status == "fail"


# ---------------------------------------------------------------------------
# espei_posterior_diagnostics
# ---------------------------------------------------------------------------


class TestEspeiDiagnostics:
    def test_clean_diagnostics_pass(self):
        env = _envelope_with_output(
            {
                "tdb_ref": "synthetic:test",
                "equilibrium_phases": ["LIQUID"],
                "phase_fraction_posterior": {"LIQUID": 1.0},
                "espei_diagnostics": {
                    "ran": True,
                    "R_hat": 1.05,
                    "effective_sample_size": 500.0,
                    "acceptance_rate": 0.35,
                },
                "fixture_phase_boundary_drift_K": None,
                "phase_set_jaccard_distance": None,
                "phase_fraction_js_divergence": None,
            }
        )
        result = espei_posterior_diagnostics(env)
        assert result.status == "pass"

    def test_high_R_hat_fails(self):
        env = _envelope_with_output(
            {
                "tdb_ref": "synthetic:test",
                "equilibrium_phases": [],
                "phase_fraction_posterior": {},
                "espei_diagnostics": {
                    "ran": True,
                    "R_hat": 1.5,
                    "effective_sample_size": 500.0,
                    "acceptance_rate": 0.35,
                },
                "fixture_phase_boundary_drift_K": None,
                "phase_set_jaccard_distance": None,
                "phase_fraction_js_divergence": None,
            }
        )
        result = espei_posterior_diagnostics(env)
        assert result.status == "fail"

    def test_low_ESS_fails(self):
        env = _envelope_with_output(
            {
                "tdb_ref": "synthetic:test",
                "equilibrium_phases": [],
                "phase_fraction_posterior": {},
                "espei_diagnostics": {
                    "ran": True,
                    "R_hat": 1.05,
                    "effective_sample_size": 50.0,
                    "acceptance_rate": 0.35,
                },
                "fixture_phase_boundary_drift_K": None,
                "phase_set_jaccard_distance": None,
                "phase_fraction_js_divergence": None,
            }
        )
        result = espei_posterior_diagnostics(env)
        assert result.status == "fail"

    def test_no_diagnostics_blocked(self):
        env = _envelope_with_output(
            {
                "tdb_ref": "synthetic:test",
                "equilibrium_phases": [],
                "phase_fraction_posterior": {},
                "espei_diagnostics": {"ran": False},
                "fixture_phase_boundary_drift_K": None,
                "phase_set_jaccard_distance": None,
                "phase_fraction_js_divergence": None,
            }
        )
        result = espei_posterior_diagnostics(env)
        assert result.status == "blocked"


# ---------------------------------------------------------------------------
# tdb_quarantine_breach
# ---------------------------------------------------------------------------


class TestTdbQuarantineBreach:
    def test_clean_quarantine_metadata_passes(self):
        env = _envelope_with_output(
            {
                "tdb_ref": "hash://sha256:abc",
                "equilibrium_phases": [],
                "phase_fraction_posterior": {},
                "espei_diagnostics": {},
                "fixture_phase_boundary_drift_K": None,
                "phase_set_jaccard_distance": None,
                "phase_fraction_js_divergence": None,
            },
            extras={
                "_quarantine_meta": {
                    "tdb_provider": "ThermoCalc",
                    "license": "proprietary",
                    "redistributable": False,
                    "committed_to_repo": False,
                    "included_in_training_corpus": False,
                    "customer_id": "customer:acme:001",
                }
            },
        )
        result = tdb_quarantine_breach(env)
        assert result.status == "pass"

    def test_redistributable_true_fails(self):
        env = _envelope_with_output(
            {
                "tdb_ref": "hash://sha256:abc",
                "equilibrium_phases": [],
                "phase_fraction_posterior": {},
                "espei_diagnostics": {},
                "fixture_phase_boundary_drift_K": None,
                "phase_set_jaccard_distance": None,
                "phase_fraction_js_divergence": None,
            },
            extras={
                "_quarantine_meta": {
                    "tdb_provider": "ThermoCalc",
                    "license": "proprietary",
                    "redistributable": True,  # BREACH
                    "committed_to_repo": False,
                    "included_in_training_corpus": False,
                }
            },
        )
        result = tdb_quarantine_breach(env)
        assert result.status == "fail"

    def test_committed_to_repo_true_fails(self):
        env = _envelope_with_output(
            {
                "tdb_ref": "hash://sha256:abc",
                "equilibrium_phases": [],
                "phase_fraction_posterior": {},
                "espei_diagnostics": {},
                "fixture_phase_boundary_drift_K": None,
                "phase_set_jaccard_distance": None,
                "phase_fraction_js_divergence": None,
            },
            extras={
                "_quarantine_meta": {
                    "tdb_provider": "ThermoCalc",
                    "license": "proprietary",
                    "redistributable": False,
                    "committed_to_repo": True,  # BREACH
                    "included_in_training_corpus": False,
                }
            },
        )
        result = tdb_quarantine_breach(env)
        assert result.status == "fail"

    def test_training_corpus_true_fails(self):
        env = _envelope_with_output(
            {
                "tdb_ref": "hash://sha256:abc",
                "equilibrium_phases": [],
                "phase_fraction_posterior": {},
                "espei_diagnostics": {},
                "fixture_phase_boundary_drift_K": None,
                "phase_set_jaccard_distance": None,
                "phase_fraction_js_divergence": None,
            },
            extras={
                "_quarantine_meta": {
                    "tdb_provider": "ThermoCalc",
                    "license": "proprietary",
                    "redistributable": False,
                    "committed_to_repo": False,
                    "included_in_training_corpus": True,  # BREACH
                }
            },
        )
        result = tdb_quarantine_breach(env)
        assert result.status == "fail"

    def test_inconsistent_license_fails(self):
        # Provider says ThermoCalc but license claims open license -> fail.
        env = _envelope_with_output(
            {
                "tdb_ref": "hash://sha256:abc",
                "equilibrium_phases": [],
                "phase_fraction_posterior": {},
                "espei_diagnostics": {},
                "fixture_phase_boundary_drift_K": None,
                "phase_set_jaccard_distance": None,
                "phase_fraction_js_divergence": None,
            },
            extras={
                "_quarantine_meta": {
                    "tdb_provider": "ThermoCalc-TCFE9",
                    "license": "MIT",  # WRONG
                    "redistributable": False,
                    "committed_to_repo": False,
                    "included_in_training_corpus": False,
                }
            },
        )
        result = tdb_quarantine_breach(env)
        assert result.status == "fail"


# ---------------------------------------------------------------------------
# phaseforgeplus_license_gate
# ---------------------------------------------------------------------------


class TestPhaseForgePlusLicenseGate:
    def test_non_phaseforgeplus_envelope_passes(self):
        env = _envelope_with_output(
            {
                "tdb_ref": "synthetic:test",
                "equilibrium_phases": [],
                "phase_fraction_posterior": {},
                "espei_diagnostics": {},
                "fixture_phase_boundary_drift_K": None,
                "phase_set_jaccard_distance": None,
                "phase_fraction_js_divergence": None,
            }
        )
        result = phaseforgeplus_license_gate(env)
        assert result.status == "pass"

    def test_pfp_default_blocked_returns_blocked(self):
        env = _envelope_with_output(
            {
                "tdb_ref": "synthetic:test",
                "equilibrium_phases": [],
                "phase_fraction_posterior": {},
                "espei_diagnostics": {},
                "fixture_phase_boundary_drift_K": None,
                "phase_set_jaccard_distance": None,
                "phase_fraction_js_divergence": None,
            },
            extras={
                "tool_adapter": {
                    "name": "PhaseForgePlusMlipPriorAdapter",
                    "version": "0.1.0",
                    "backend": "stub",
                    "engine": "phaseforgeplus-blocked-license-unverified",
                },
                "_phaseforgeplus_meta": {
                    "enabled": False,
                    "repo": "dogusariturk/PhaseForgePlus",
                    "license_spdx": None,
                    "verified_at": None,
                },
            },
        )
        result = phaseforgeplus_license_gate(env)
        assert result.status == "blocked"

    def test_pfp_enabled_passes(self):
        env = _envelope_with_output(
            {
                "tdb_ref": "synthetic:test",
                "equilibrium_phases": [],
                "phase_fraction_posterior": {},
                "espei_diagnostics": {},
                "fixture_phase_boundary_drift_K": None,
                "phase_set_jaccard_distance": None,
                "phase_fraction_js_divergence": None,
            },
            extras={
                "tool_adapter": {
                    "name": "PhaseForgePlusMlipPriorAdapter",
                    "version": "0.1.0",
                    "backend": "phaseforgeplus_local_pending",
                    "engine": "phaseforgeplus-license-verified-MIT",
                },
                "_phaseforgeplus_meta": {
                    "enabled": True,
                    "repo": "dogusariturk/PhaseForgePlus",
                    "license_spdx": "MIT",
                    "verified_at": "2026-04-30T12:00:00+00:00",
                },
            },
        )
        result = phaseforgeplus_license_gate(env)
        assert result.status == "pass"


# ---------------------------------------------------------------------------
# commercial_tdb_provider_disabled_by_default
# ---------------------------------------------------------------------------


class TestCommercialProviderDisabledByDefault:
    def test_default_disabled_clean_envelope_passes(self):
        env = _envelope_with_output(
            {
                "tdb_ref": "synthetic:test",
                "equilibrium_phases": [],
                "phase_fraction_posterior": {},
                "espei_diagnostics": {},
                "fixture_phase_boundary_drift_K": None,
                "phase_set_jaccard_distance": None,
                "phase_fraction_js_divergence": None,
            }
        )
        result = commercial_tdb_provider_disabled_by_default(env, materials_config_provider_value="disabled")
        assert result.status == "pass"

    def test_default_disabled_but_envelope_claims_commercial_fails(self):
        env = _envelope_with_output(
            {
                "tdb_ref": "synthetic:test",
                "equilibrium_phases": [],
                "phase_fraction_posterior": {},
                "espei_diagnostics": {},
                "fixture_phase_boundary_drift_K": None,
                "phase_set_jaccard_distance": None,
                "phase_fraction_js_divergence": None,
            },
            extras={
                "tool_adapter": {
                    "name": "ThermoCalcTdbReadOnlyAdapter",
                    "version": "0.1.0",
                    "backend": "local_cpu",
                    "engine": "thermo-calc-quarantined-read-only",
                },
                "_quarantine_meta": {
                    "tdb_provider": "ThermoCalc",
                    "license": "proprietary",
                    "redistributable": False,
                    "committed_to_repo": False,
                    "included_in_training_corpus": False,
                },
            },
        )
        result = commercial_tdb_provider_disabled_by_default(env, materials_config_provider_value="disabled")
        assert result.status == "fail"

    def test_quarantined_with_customer_id_passes(self):
        env = _envelope_with_output(
            {
                "tdb_ref": "hash://sha256:abc",
                "equilibrium_phases": [],
                "phase_fraction_posterior": {},
                "espei_diagnostics": {},
                "fixture_phase_boundary_drift_K": None,
                "phase_set_jaccard_distance": None,
                "phase_fraction_js_divergence": None,
            },
            extras={
                "tool_adapter": {
                    "name": "ThermoCalcTdbReadOnlyAdapter",
                    "version": "0.1.0",
                    "backend": "local_cpu",
                    "engine": "thermo-calc-quarantined-read-only",
                },
                "_quarantine_meta": {
                    "tdb_provider": "ThermoCalc",
                    "license": "proprietary",
                    "customer_id": "customer:acme:001",
                    "redistributable": False,
                    "committed_to_repo": False,
                    "included_in_training_corpus": False,
                },
            },
        )
        result = commercial_tdb_provider_disabled_by_default(
            env, materials_config_provider_value="thermo_calc_quarantined"
        )
        assert result.status == "pass"

    def test_quarantined_without_customer_id_fails(self):
        env = _envelope_with_output(
            {
                "tdb_ref": "hash://sha256:abc",
                "equilibrium_phases": [],
                "phase_fraction_posterior": {},
                "espei_diagnostics": {},
                "fixture_phase_boundary_drift_K": None,
                "phase_set_jaccard_distance": None,
                "phase_fraction_js_divergence": None,
            },
            extras={
                "tool_adapter": {
                    "name": "ThermoCalcTdbReadOnlyAdapter",
                    "version": "0.1.0",
                    "backend": "local_cpu",
                    "engine": "thermo-calc-quarantined-read-only",
                },
                "_quarantine_meta": {
                    "tdb_provider": "ThermoCalc",
                    "license": "proprietary",
                    "redistributable": False,
                    "committed_to_repo": False,
                    "included_in_training_corpus": False,
                    # customer_id MISSING
                },
            },
        )
        result = commercial_tdb_provider_disabled_by_default(
            env, materials_config_provider_value="thermo_calc_quarantined"
        )
        assert result.status == "fail"
