"""Adversarial tests: L2 disagreement recompute (Wave D hardened gate 1).

Boundary
--------
Research infrastructure for in silico materials science discovery. Outputs are
research artifacts. No regulatory certification claims. No clinical or
human-subject use. ITAR / weapons applications are out of scope (Meta UMA
Acceptable Use Policy and operator policy).

Discipline
----------
The OLD gate ``dpa_mace_disagreement_routing`` reads
``output.energy_disagreement_meV_per_atom`` and ``output.routing_decision``
directly. A buggy / malicious adapter can write E_DPA = 100 meV/atom and
E_MACE = 102 meV/atom — true disagreement 2 meV/atom, well under the 25
threshold — but lie in the field by writing
``energy_disagreement_meV_per_atom = 5`` and ``routing_decision = "promote"``.
The OLD gate, given those fields, returns ``status="pass"``. The NEW
``dpa_mace_disagreement_routing_recomputed`` gate ignores the claim and
recomputes the scalar from the per-model energies; it then catches the
mismatch.

Conversely, when E_DPA = -5.0 and E_MACE = +95.0 (disagreement 100 meV/atom
≫ the hard-reject threshold), an adapter could lie and write
``energy_disagreement_meV_per_atom = 5`` with ``routing_decision = "promote"``.
The OLD gate would pass the envelope; the NEW gate routes to ``hard_reject``.
"""

from __future__ import annotations

from zer0pa_materials_workbench.falsifiers.l2_falsifiers import (
    dpa_mace_disagreement_routing,
    dpa_mace_disagreement_routing_recomputed,
)
from zer0pa_materials_workbench.falsifiers.raw_evidence import recompute_l2_disagreement

# ---------------------------------------------------------------------------
# Forged envelope helpers
# ---------------------------------------------------------------------------


def _envelope_with_predictions(
    e_dpa: float,
    e_mace: float,
    f_dpa: float = 0.05,
    f_mace: float = 0.05,
    *,
    claimed_energy_meV: float | None,
    claimed_force_eV_A: float | None = None,
    claimed_routing: str = "promote",
) -> dict:
    """Construct an envelope where the per-model predictions and the claim disagree."""
    return {
        "output": {
            "predictions": [
                {
                    "model": "DPA-3.1-3M",
                    "energy_eV_per_atom": e_dpa,
                    "force_rmse_eV_per_Ang": f_dpa,
                },
                {
                    "model": "MACE-MPA-0",
                    "energy_eV_per_atom": e_mace,
                    "force_rmse_eV_per_Ang": f_mace,
                },
            ],
            "energy_disagreement_meV_per_atom": claimed_energy_meV,
            "force_rmse_disagreement_eV_per_Ang": (
                claimed_force_eV_A
                if claimed_force_eV_A is not None
                else abs(f_dpa - f_mace)
            ),
            "routing_decision": claimed_routing,
        }
    }


# ---------------------------------------------------------------------------
# Test 1: forged-claim — true disagreement small (2 meV) but claim says 5
# ---------------------------------------------------------------------------


class TestForgedSmallDisagreement:
    """E_DPA - E_MACE = 2 meV (recompute) but the envelope claims 5 meV.

    Both values route to "promote" under the 25 meV threshold, so the
    OLD gate passes. The NEW gate also routes to "promote" but flags
    the claim/recompute mismatch.
    """

    def _envelope(self) -> dict:
        # E_DPA = -5.000 eV, E_MACE = -5.002 eV → disagreement = 2 meV/atom
        return _envelope_with_predictions(
            e_dpa=-5.000,
            e_mace=-5.002,
            claimed_energy_meV=5.0,  # forged: claimed 5 instead of 2
            claimed_routing="promote",
        )

    def test_old_gate_passes_forged_envelope(self):
        env = self._envelope()
        item = dpa_mace_disagreement_routing(env)
        # OLD gate trusts the claim — both 2 and 5 meV are below 25, both
        # route to "promote". Status="pass" demonstrates the
        # "shape-match as identity-match" weakness.
        assert item.status == "pass", (
            "old gate must trust the claim and pass; this is the "
            "weakness Wave D fixes"
        )

    def test_recompute_returns_two_meV(self):
        env = self._envelope()
        e_re, f_re = recompute_l2_disagreement(env)
        assert e_re is not None
        assert abs(e_re - 2.0) < 1e-6, (
            f"true disagreement should be ~2 meV/atom; got {e_re}"
        )

    def test_new_gate_fails_forged_envelope(self):
        env = self._envelope()
        item = dpa_mace_disagreement_routing_recomputed(env)
        # Hardened gate: claim/recompute mismatch → status="fail" with
        # the load-bearing rationale.
        assert item.status == "fail"
        assert "claimed_disagreement_inconsistent_with_per_model_predictions" in (
            item.rationale or ""
        )


# ---------------------------------------------------------------------------
# Test 2: forged-claim — true disagreement is hard-reject but claim says
#         promote
# ---------------------------------------------------------------------------


class TestForgedHardRejectDisagreement:
    """True disagreement = 100 meV/atom (hard-reject) but claim = 5 (promote).

    The OLD gate reads ``routing_decision="promote"`` and trusts it,
    returning ``status="pass"``. The NEW gate recomputes 100 meV/atom,
    routes to ``hard_reject``, and fails the envelope.
    """

    def _envelope(self) -> dict:
        # E_DPA = -5.0, E_MACE = -5.1 → disagreement 100 meV/atom
        return _envelope_with_predictions(
            e_dpa=-5.0,
            e_mace=-5.1,
            claimed_energy_meV=5.0,
            claimed_routing="promote",
        )

    def test_old_gate_passes_forged_envelope(self):
        env = self._envelope()
        item = dpa_mace_disagreement_routing(env)
        assert item.status == "pass", (
            "old gate trusts routing_decision='promote' even though "
            "the per-model energies imply hard_reject"
        )

    def test_new_gate_routes_to_hard_reject(self):
        env = self._envelope()
        item = dpa_mace_disagreement_routing_recomputed(env)
        assert item.status == "fail"
        assert item.actual["routing_recomputed"] == "hard_reject"
        # Recomputed value is in the hard-reject band.
        assert item.actual["energy_recomputed_meV"] > 75.0


# ---------------------------------------------------------------------------
# Test 3: forged-claim — true force RMSE disagreement large (> 0.35 eV/Å)
#         while claim is small
# ---------------------------------------------------------------------------


class TestForgedForceDisagreement:
    """Force-RMSE disagreement = 0.50 eV/Å (hard-reject) but claim = 0.05.

    Force-RMSE crosses the hard-reject threshold (0.35 eV/Å). The OLD
    gate reads only routing_decision; the NEW gate recomputes from the
    per-model force_rmse fields.
    """

    def _envelope(self) -> dict:
        # F_DPA = 0.05, F_MACE = 0.55 → disagreement 0.50 eV/Å
        return _envelope_with_predictions(
            e_dpa=-5.0,
            e_mace=-5.0,  # zero energy disagreement
            f_dpa=0.05,
            f_mace=0.55,
            claimed_energy_meV=0.0,
            claimed_force_eV_A=0.05,  # forged
            claimed_routing="promote",
        )

    def test_old_gate_passes_forged_envelope(self):
        env = self._envelope()
        item = dpa_mace_disagreement_routing(env)
        # routing="promote" gets a pass.
        assert item.status == "pass"

    def test_new_gate_routes_to_hard_reject(self):
        env = self._envelope()
        item = dpa_mace_disagreement_routing_recomputed(env)
        assert item.status == "fail"
        assert item.actual["routing_recomputed"] == "hard_reject"
        assert item.actual["force_recomputed_eV_per_A"] > 0.35


# ---------------------------------------------------------------------------
# Test 4: clean envelope — claim and recompute agree, both pass
# ---------------------------------------------------------------------------


class TestCleanEnvelopeStillPasses:
    """A clean adapter with consistent fields must still pass the new gate."""

    def _envelope(self) -> dict:
        return _envelope_with_predictions(
            e_dpa=-5.000,
            e_mace=-5.002,
            claimed_energy_meV=2.0,  # consistent with recompute
            claimed_routing="promote",
        )

    def test_recompute_matches_claim(self):
        env = self._envelope()
        e_re, _ = recompute_l2_disagreement(env)
        assert abs(e_re - 2.0) < 1e-6

    def test_new_gate_passes(self):
        env = self._envelope()
        item = dpa_mace_disagreement_routing_recomputed(env)
        assert item.status == "pass"
        assert item.actual["routing_recomputed"] == "promote"


# ---------------------------------------------------------------------------
# Test 5: missing predictions — gate is blocked
# ---------------------------------------------------------------------------


class TestMissingPredictionsBlocks:
    def test_only_one_model_blocks(self):
        env = {
            "output": {
                "predictions": [
                    {"model": "DPA-3.1-3M", "energy_eV_per_atom": -5.0, "force_rmse_eV_per_Ang": 0.05}
                ],
                "energy_disagreement_meV_per_atom": 0.0,
                "force_rmse_disagreement_eV_per_Ang": 0.0,
                "routing_decision": "promote",
            }
        }
        item = dpa_mace_disagreement_routing_recomputed(env)
        assert item.status == "blocked"
        assert "missing_per_model_predictions" in str(item.actual.get("reason", ""))

    def test_no_predictions_blocks(self):
        env = {"output": {"routing_decision": "promote"}}
        item = dpa_mace_disagreement_routing_recomputed(env)
        assert item.status == "blocked"
