"""Falsification wave: synthesise a CH envelope with mass drift > 1e-3
and confirm cahn_hilliard_mass_drift falsifier triggers EXACTLY.

PRD §Falsification wave: "phase-field conservation violation".
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
from zer0pa_materials_workbench.adapters.l4.prisms_pf import PrismsPfAdapter
from zer0pa_materials_workbench.falsifiers.l4_falsifiers import (
    allen_cahn_bounds_violation,
    cahn_hilliard_mass_drift,
    microsim_subprocess_isolation,
    neural_operator_advisory_gate,
    spparks_potts_energy_monotonic,
)


def _ch_spec() -> PhaseFieldRunSpec:
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
def violating_envelope():
    """Run a clean CH simulation, then synthesise the mass-drift violation
    by mutating the output. This isolates the FALSIFIER's behaviour from
    the SOLVER's behaviour."""
    req = L4PredictRequest(
        run_id="run:falsification/l4/ch-violation",
        candidate_id="candidate:falsification/001",
        campaign_id="campaign:falsification/001",
        rights_claim_id="rights:falsification/001",
    )
    env = PrismsPfAdapter().run(_ch_spec(), req)
    # Synthesise a mass-drift violation: 5e-3 > 1e-3 threshold
    env["output"]["cahn_hilliard_mass_drift"] = 5e-3
    return env


class TestMassDriftViolationTriggersGate:
    def test_falsifier_fails(self, violating_envelope):
        result = cahn_hilliard_mass_drift(violating_envelope)
        assert result.status == "fail"

    def test_actual_value_recorded(self, violating_envelope):
        result = cahn_hilliard_mass_drift(violating_envelope)
        assert result.actual == pytest.approx(5e-3)


class TestExclusivity:
    """Only the cahn_hilliard_mass_drift gate should fire."""

    def test_only_mass_drift_falsifier_fails(self, violating_envelope):
        results = {
            "cahn_hilliard_mass_drift": cahn_hilliard_mass_drift(violating_envelope),
            "allen_cahn_bounds_violation": allen_cahn_bounds_violation(violating_envelope),
            "spparks_potts_energy_monotonic": spparks_potts_energy_monotonic(
                violating_envelope
            ),
            "microsim_subprocess_isolation": microsim_subprocess_isolation(
                violating_envelope
            ),
            "neural_operator_advisory_gate": neural_operator_advisory_gate(
                violating_envelope
            ),
        }
        failed = [name for name, r in results.items() if r.status == "fail"]
        assert failed == ["cahn_hilliard_mass_drift"], (
            f"Expected only mass-drift to fail; got: {failed}"
        )

    def test_other_gates_are_blocked_or_pass(self, violating_envelope):
        # AC bounds is None for a CH envelope -> blocked
        ac = allen_cahn_bounds_violation(violating_envelope)
        assert ac.status in {"blocked", "pass"}
        # SPPARKS gate is None -> blocked
        sp = spparks_potts_energy_monotonic(violating_envelope)
        assert sp.status == "blocked"
