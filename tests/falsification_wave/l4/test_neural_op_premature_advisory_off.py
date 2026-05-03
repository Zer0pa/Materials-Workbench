"""Falsification wave: a neural-operator envelope claims advisory=False
without passing both subgates. The neural_operator_advisory_gate falsifier
must trigger EXACTLY.

This is a positive control on the PRD §L4 (Brief #2 reframe) directive:
"Neural operator is advisory only until it beats persistence baseline AND
has < 10% relative QoI error on held-out classical trajectories."
"""

from __future__ import annotations

import pytest

from zer0pa_materials_workbench.adapters.l4.base import L4PredictRequest
from zer0pa_materials_workbench.adapters.l4.contracts import (
    PhaseFieldDomain,
    PhaseFieldMaterial,
    PhaseFieldMesh,
    PhaseFieldRunSpec,
)
from zer0pa_materials_workbench.adapters.l4.neural_operator import NeuralOperatorPhaseFieldAdapter
from zer0pa_materials_workbench.falsifiers.l4_falsifiers import (
    allen_cahn_bounds_violation,
    cahn_hilliard_mass_drift,
    microsim_subprocess_isolation,
    neural_operator_advisory_gate,
    spparks_potts_energy_monotonic,
)


def _spec() -> PhaseFieldRunSpec:
    return PhaseFieldRunSpec(
        equation="cahn_hilliard",
        domain=PhaseFieldDomain(dimension=2, extents=[10.0, 10.0], units="nm"),
        mesh=PhaseFieldMesh(nodes=[16, 16]),
        materials=[PhaseFieldMaterial(phase_name="alpha", initial_fraction=0.5)],
        time_steps=10,
        dt=0.01,
        n_dumps=6,
    )


@pytest.fixture
def premature_advisory_off_envelope():
    """Force advisory=False, then synthesise gate failures."""
    req = L4PredictRequest(
        run_id="run:falsification/l4/neural-op-premature",
        candidate_id="candidate:falsification/001",
        campaign_id="campaign:falsification/001",
        rights_claim_id="rights:falsification/001",
    )
    env = NeuralOperatorPhaseFieldAdapter(advisory_override=False).run(_spec(), req)
    # Synthesise gate failures: high QoI error AND not beating persistence
    env["_l4_meta"]["neural_op_gates"]["qoi_relative_error"] = 0.5
    env["_l4_meta"]["neural_op_gates"]["qoi_gate_passes"] = False
    env["_l4_meta"]["neural_op_gates"]["beats_persistence_baseline"] = False
    return env


class TestPrematureAdvisoryOffTriggersGate:
    def test_falsifier_fails(self, premature_advisory_off_envelope):
        result = neural_operator_advisory_gate(premature_advisory_off_envelope)
        assert result.status == "fail"

    def test_actual_records_offending_state(self, premature_advisory_off_envelope):
        result = neural_operator_advisory_gate(premature_advisory_off_envelope)
        actual = result.actual
        assert actual["advisory"] is False
        assert actual["qoi_relative_error"] == pytest.approx(0.5)
        assert actual["beats_persistence"] is False


class TestExclusivity:
    """Only the neural_operator_advisory_gate should fire on this envelope."""

    def test_only_advisory_gate_fails(self, premature_advisory_off_envelope):
        results = {
            "cahn_hilliard_mass_drift": cahn_hilliard_mass_drift(
                premature_advisory_off_envelope
            ),
            "allen_cahn_bounds_violation": allen_cahn_bounds_violation(
                premature_advisory_off_envelope
            ),
            "spparks_potts_energy_monotonic": spparks_potts_energy_monotonic(
                premature_advisory_off_envelope
            ),
            "microsim_subprocess_isolation": microsim_subprocess_isolation(
                premature_advisory_off_envelope
            ),
            "neural_operator_advisory_gate": neural_operator_advisory_gate(
                premature_advisory_off_envelope
            ),
        }
        failed = [name for name, r in results.items() if r.status == "fail"]
        assert failed == ["neural_operator_advisory_gate"], (
            f"Expected only advisory-gate to fail; got: {failed}"
        )


class TestProperlyAdvisoryEnvelopePasses:
    """Sanity check: advisory=True (default) on the same surrogate must pass."""

    def test_default_advisory_true_passes_gate(self):
        req = L4PredictRequest(
            run_id="run:falsification/l4/neural-op-correct",
            candidate_id="candidate:falsification/001",
            campaign_id="campaign:falsification/001",
            rights_claim_id="rights:falsification/001",
        )
        # Force advisory=True so we know the gate handles correct case
        env = NeuralOperatorPhaseFieldAdapter(advisory_override=True).run(_spec(), req)
        result = neural_operator_advisory_gate(env)
        assert result.status == "pass"
