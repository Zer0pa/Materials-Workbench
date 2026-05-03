"""Adversarial tests: L3 sovereign block enforcement (Wave D hardened gate 7).

Boundary
--------
Research infrastructure for in silico materials science discovery. Outputs are
research artifacts. No regulatory certification claims. No clinical or
human-subject use. ITAR / weapons applications are out of scope (Meta UMA
Acceptable Use Policy and operator policy).

Discipline
----------
The OLD ``phaseforgeplus_license_gate`` and ``tdb_quarantine_breach``
inspect ``_phaseforgeplus_meta`` and ``_quarantine_meta`` fields on the
ENVELOPE itself. An adapter can write those fields without recording
the corresponding decision in ``decisions.jsonl``. The new
``verify_l3_sovereign_block_enforced`` requires a CONCRETE PRIOR
DECISION row for any envelope claiming a restricted backend.
"""

from __future__ import annotations

from zer0pa_materials_workbench.falsifiers.l3_falsifiers import (
    phaseforgeplus_license_gate,
    verify_l3_sovereign_block_enforced,
)

# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _phaseforgeplus_envelope() -> dict:
    """Envelope claiming PhaseForgePlus contribution.

    The envelope-side ``_phaseforgeplus_meta`` block is fully populated
    (the way the OLD gate prefers it). This is exactly the forgery
    posture: the adapter emits all the right fields locally without
    recording an enable decision in ``decisions.jsonl``.
    """
    return {
        "layer": "L3",
        "tool_adapter": {
            "name": "PhaseForgePlusAdapter",
            "version": "0.1.0",
            "backend": "research_aid",
            "engine": "phaseforge_plus",
        },
        "_phaseforgeplus_meta": {
            "enabled": True,
            "license_spdx": "GPL-3.0-only",
            "verified_at": "2026-04-30T00:00:00+00:00",
            "repo": "github.com/example/phaseforge_plus",
        },
        "input_refs": [],
        "output": {"equilibrium_phases": ["LIQUID", "GARNET"]},
    }


def _thermocalc_envelope() -> dict:
    """Envelope claiming Thermo-Calc contribution."""
    return {
        "layer": "L3",
        "tool_adapter": {
            "name": "ThermoCalcTdbReadOnlyAdapter",
            "version": "0.1.0",
            "backend": "thermo_calc_quarantined",
            "engine": "thermo-calc-quarantined",
        },
        "_quarantine_meta": {
            "tdb_provider": "ThermoCalc TCFE9",
            "license": "proprietary",
            "redistributable": False,
            "committed_to_repo": False,
            "included_in_training_corpus": False,
            "customer_id": "customer:zer0pa",
        },
        "input_refs": [],
        "output": {"equilibrium_phases": ["FCC_A1"]},
    }


def _decisions_log(*decisions: dict) -> list[dict]:
    """In-memory decisions.jsonl shape consumable by iter_audit_rows."""
    return list(decisions)


# ---------------------------------------------------------------------------
# Test 1: PhaseForgePlus envelope without a license decision
# ---------------------------------------------------------------------------


class TestForgedPhaseForgePlusNoDecision:
    def test_old_gate_passes_envelope_with_meta_only(self):
        env = _phaseforgeplus_envelope()
        # Old gate: presence of populated _phaseforgeplus_meta + enabled
        # flag → pass.
        item = phaseforgeplus_license_gate(env)
        assert item.status == "pass", (
            "old gate trusts _phaseforgeplus_meta even with no decision; "
            "this is the weakness Wave D fixes"
        )

    def test_new_gate_fails_without_decisions_jsonl_record(self):
        env = _phaseforgeplus_envelope()
        empty_log = _decisions_log()  # no enable record
        item = verify_l3_sovereign_block_enforced(env, empty_log)
        assert item.status == "fail"
        failures = item.actual["failures"]
        assert any(
            f["backend"] == "phaseforgeplus"
            and f["reason"] == "no_enable_decision_in_decisions_jsonl"
            for f in failures
        )

    def test_new_gate_passes_with_enable_decision(self):
        env = _phaseforgeplus_envelope()
        decisions = _decisions_log(
            {
                "decision_id": "decision:enable_with_verified_license/PhaseForgePlus",
                "made_by": "lead",
                "context": "PhaseForgePlus license verified for the operator.",
                "rationale": (
                    "enable_with_verified_license — operator has verified the "
                    "GPL-3.0 redistributability obligations and accepted them."
                ),
            }
        )
        item = verify_l3_sovereign_block_enforced(env, decisions)
        assert item.status == "pass"


# ---------------------------------------------------------------------------
# Test 2: Thermo-Calc envelope without a customer license decision
# ---------------------------------------------------------------------------


class TestForgedThermoCalcNoDecision:
    def test_new_gate_fails_without_customer_license_decision(self):
        env = _thermocalc_envelope()
        empty_log = _decisions_log()
        item = verify_l3_sovereign_block_enforced(env, empty_log)
        assert item.status == "fail"
        failures = item.actual["failures"]
        assert any(
            f["backend"] == "thermo_calc"
            and f["reason"] == "no_enable_decision_in_decisions_jsonl"
            for f in failures
        )

    def test_new_gate_passes_with_customer_license_decision(self):
        env = _thermocalc_envelope()
        decisions = _decisions_log(
            {
                "decision_id": "decision:enable_with_customer_license/thermo-calc-quarantined",
                "made_by": "lead",
                "context": "Customer-supplied Thermo-Calc TCFE9 license verified.",
                "rationale": "enable_with_customer_license: customer:zer0pa supplied valid TCFE9 lock.",
            }
        )
        item = verify_l3_sovereign_block_enforced(env, decisions)
        assert item.status == "pass"


# ---------------------------------------------------------------------------
# Test 3: non-restricted backend — gate is no-op
# ---------------------------------------------------------------------------


class TestNonRestrictedBackendNoOp:
    def test_open_pycalphad_backend_passes(self):
        env = {
            "layer": "L3",
            "tool_adapter": {
                "name": "PycalphadOpenTdbAdapter",
                "version": "0.1.0",
                "backend": "pycalphad",
                "engine": "pycalphad",
            },
            "input_refs": [],
            "output": {"equilibrium_phases": ["LIQUID"]},
        }
        empty_log = _decisions_log()
        item = verify_l3_sovereign_block_enforced(env, empty_log)
        assert item.status == "pass"
        assert "not applicable" in (item.rationale or "").lower()
