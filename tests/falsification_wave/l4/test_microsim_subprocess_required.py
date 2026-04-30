"""Falsification wave: synthetic in-process MICROSIM run triggers the
microsim_subprocess_isolation falsifier EXACTLY.

This protects PRD §L4: "MICROSIM is treated as GPL-3 subprocess/container
until license review says otherwise." If a future code path tries to
co-import MICROSIM modules, the GPL-3 quarantine collapses and Zer0pa code
becomes derivative under GPL-3.

We synthesise the violation by mutating ``_l4_meta.isolation_mode`` from
'subprocess' to 'in_process' on a real MICROSIM envelope.
"""

from __future__ import annotations

import pytest

from zer0pa_materials.adapters.l4.base import L4PredictRequest
from zer0pa_materials.adapters.l4.contracts import (
    PhaseFieldDomain,
    PhaseFieldMaterial,
    PhaseFieldMesh,
    PhaseFieldRunSpec,
)
from zer0pa_materials.adapters.l4.microsim import MicrosimGrandPotentialAdapter
from zer0pa_materials.falsifiers.l4_falsifiers import (
    allen_cahn_bounds_violation,
    cahn_hilliard_mass_drift,
    microsim_subprocess_isolation,
    neural_operator_advisory_gate,
    spparks_potts_energy_monotonic,
)


def _spec() -> PhaseFieldRunSpec:
    return PhaseFieldRunSpec(
        equation="grand_potential",
        domain=PhaseFieldDomain(dimension=2, extents=[10.0, 10.0], units="nm"),
        mesh=PhaseFieldMesh(nodes=[10, 10]),
        materials=[PhaseFieldMaterial(phase_name="alpha", initial_fraction=0.5)],
        time_steps=5,
        dt=0.01,
        n_dumps=4,
    )


@pytest.fixture
def in_process_envelope():
    """Run MICROSIM correctly (subprocess), then synthesise the GPL-3
    quarantine violation by switching isolation_mode."""
    req = L4PredictRequest(
        run_id="run:falsification/l4/microsim-in-process",
        candidate_id="candidate:falsification/001",
        campaign_id="campaign:falsification/001",
        rights_claim_id="rights:falsification/001",
    )
    env = MicrosimGrandPotentialAdapter().run(_spec(), req)
    env["_l4_meta"]["isolation_mode"] = "in_process"
    return env


@pytest.fixture
def proper_microsim_envelope():
    req = L4PredictRequest(
        run_id="run:falsification/l4/microsim-correct",
        candidate_id="candidate:falsification/001",
        campaign_id="campaign:falsification/001",
        rights_claim_id="rights:falsification/001",
    )
    return MicrosimGrandPotentialAdapter().run(_spec(), req)


class TestInProcessTriggersGate:
    def test_falsifier_fails(self, in_process_envelope):
        result = microsim_subprocess_isolation(in_process_envelope)
        assert result.status == "fail"

    def test_actual_records_in_process(self, in_process_envelope):
        result = microsim_subprocess_isolation(in_process_envelope)
        assert result.actual["isolation_mode"] == "in_process"


class TestExclusivity:
    def test_only_isolation_gate_fails(self, in_process_envelope):
        results = {
            "cahn_hilliard_mass_drift": cahn_hilliard_mass_drift(in_process_envelope),
            "allen_cahn_bounds_violation": allen_cahn_bounds_violation(
                in_process_envelope
            ),
            "spparks_potts_energy_monotonic": spparks_potts_energy_monotonic(
                in_process_envelope
            ),
            "microsim_subprocess_isolation": microsim_subprocess_isolation(
                in_process_envelope
            ),
            "neural_operator_advisory_gate": neural_operator_advisory_gate(
                in_process_envelope
            ),
        }
        failed = [name for name, r in results.items() if r.status == "fail"]
        assert failed == ["microsim_subprocess_isolation"], (
            f"Expected only isolation to fail; got: {failed}"
        )


class TestProperEnvelopePasses:
    def test_proper_subprocess_passes_gate(self, proper_microsim_envelope):
        result = microsim_subprocess_isolation(proper_microsim_envelope)
        assert result.status == "pass"

    def test_isolation_mode_recorded_subprocess(self, proper_microsim_envelope):
        assert proper_microsim_envelope["_l4_meta"]["isolation_mode"] == "subprocess"


class TestMissingIsolationFieldFails:
    def test_missing_field_triggers_gate(self, proper_microsim_envelope):
        del proper_microsim_envelope["_l4_meta"]["isolation_mode"]
        result = microsim_subprocess_isolation(proper_microsim_envelope)
        assert result.status == "fail"
