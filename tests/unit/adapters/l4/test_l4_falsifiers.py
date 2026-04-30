"""Unit tests for L4 falsifiers — every gate must trigger correctly.

PRD §L4 falsifiers tested here:
    - cahn_hilliard_mass_drift          < 1e-3 on tiny fixture
    - allen_cahn_bounds_violation       < 1e-4
    - spparks_potts_energy_monotonic    T=0 energy non-increasing
    - neural_operator_advisory_gate     advisory=False requires both subgates
    - plug_swap_schema_invariance       L4 backends emit identical schema
    - microsim_subprocess_isolation     MICROSIM must run subprocess
"""

from __future__ import annotations

import pytest

from zer0pa_materials.adapters.l4.base import L4PredictRequest
from zer0pa_materials.adapters.l4.contracts import (
    KmcRunSpec,
    PhaseFieldDomain,
    PhaseFieldMaterial,
    PhaseFieldMesh,
    PhaseFieldRunSpec,
)
from zer0pa_materials.adapters.l4.microsim import MicrosimGrandPotentialAdapter
from zer0pa_materials.adapters.l4.moose import MoosePhaseFieldAdapter
from zer0pa_materials.adapters.l4.neural_operator import NeuralOperatorPhaseFieldAdapter
from zer0pa_materials.adapters.l4.prisms_pf import PrismsPfAdapter
from zer0pa_materials.adapters.l4.spparks import SpparksKmcAdapter
from zer0pa_materials.falsifiers.l4_falsifiers import (
    allen_cahn_bounds_violation,
    cahn_hilliard_mass_drift,
    microsim_subprocess_isolation,
    neural_operator_advisory_gate,
    plug_swap_schema_invariance,
    spparks_potts_energy_monotonic,
)


REQ = L4PredictRequest(
    run_id="run:test/falsifiers/001",
    candidate_id="candidate:test/001",
    campaign_id="campaign:test/001",
    rights_claim_id="rights:test/001",
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


def _ac_spec() -> PhaseFieldRunSpec:
    return PhaseFieldRunSpec(
        equation="allen_cahn",
        domain=PhaseFieldDomain(dimension=2, extents=[10.0, 10.0], units="nm"),
        mesh=PhaseFieldMesh(nodes=[16, 16]),
        materials=[PhaseFieldMaterial(phase_name="alpha", initial_fraction=0.5)],
        time_steps=10,
        dt=0.01,
        n_dumps=6,
    )


# ---------------------------------------------------------------------------
# cahn_hilliard_mass_drift
# ---------------------------------------------------------------------------


class TestCahnHilliardMassDriftFalsifier:
    def test_passes_on_clean_envelope(self):
        env = PrismsPfAdapter().run(_ch_spec(), REQ)
        result = cahn_hilliard_mass_drift(env)
        assert result.status == "pass"

    def test_fails_on_synthetic_drift(self):
        env = PrismsPfAdapter().run(_ch_spec(), REQ)
        env["output"]["cahn_hilliard_mass_drift"] = 5e-3  # > 1e-3 threshold
        result = cahn_hilliard_mass_drift(env)
        assert result.status == "fail"
        assert result.actual == 5e-3

    def test_blocked_on_missing_value(self):
        env = PrismsPfAdapter().run(_ch_spec(), REQ)
        env["output"]["cahn_hilliard_mass_drift"] = None
        result = cahn_hilliard_mass_drift(env)
        assert result.status == "blocked"

    def test_blocked_on_missing_output(self):
        env = {"layer": "L4"}
        result = cahn_hilliard_mass_drift(env)
        assert result.status == "blocked"

    def test_threshold_configurable(self):
        env = PrismsPfAdapter().run(_ch_spec(), REQ)
        env["output"]["cahn_hilliard_mass_drift"] = 1e-2
        # default 1e-3 → fail
        assert cahn_hilliard_mass_drift(env).status == "fail"
        # relaxed 1.0 → pass
        assert cahn_hilliard_mass_drift(env, threshold=1.0).status == "pass"


# ---------------------------------------------------------------------------
# allen_cahn_bounds_violation
# ---------------------------------------------------------------------------


class TestAllenCahnBoundsFalsifier:
    def test_passes_on_clean_envelope(self):
        env = PrismsPfAdapter().run(_ac_spec(), REQ)
        result = allen_cahn_bounds_violation(env)
        assert result.status == "pass"

    def test_fails_on_synthetic_violation(self):
        env = PrismsPfAdapter().run(_ac_spec(), REQ)
        env["output"]["allen_cahn_bounds_violation"] = 5e-4  # > 1e-4 threshold
        result = allen_cahn_bounds_violation(env)
        assert result.status == "fail"

    def test_blocked_on_missing_value(self):
        env = PrismsPfAdapter().run(_ac_spec(), REQ)
        env["output"]["allen_cahn_bounds_violation"] = None
        result = allen_cahn_bounds_violation(env)
        assert result.status == "blocked"


# ---------------------------------------------------------------------------
# spparks_potts_energy_monotonic
# ---------------------------------------------------------------------------


class TestSpparksMonotonicFalsifier:
    def test_passes_at_t0(self):
        spec = KmcRunSpec(
            grid_size=[10, 10], n_states=4, n_steps=10, n_dumps=4, temperature_K=0.0
        )
        env = SpparksKmcAdapter().run(spec, REQ)
        result = spparks_potts_energy_monotonic(env)
        assert result.status == "pass"

    def test_fails_at_thermal(self):
        spec = KmcRunSpec(
            grid_size=[10, 10], n_states=4, n_steps=10, n_dumps=5, temperature_K=500.0
        )
        env = SpparksKmcAdapter().run(spec, REQ)
        result = spparks_potts_energy_monotonic(env)
        assert result.status == "fail"

    def test_blocked_when_no_monotonic_field(self):
        env = PrismsPfAdapter().run(_ch_spec(), REQ)
        # PRISMS-PF sets monotonic to None
        result = spparks_potts_energy_monotonic(env)
        assert result.status == "blocked"


# ---------------------------------------------------------------------------
# neural_operator_advisory_gate
# ---------------------------------------------------------------------------


class TestNeuralOperatorAdvisoryGate:
    def test_passes_when_advisory_true(self):
        # advisory_override forces advisory=True regardless of subgates
        env = NeuralOperatorPhaseFieldAdapter(advisory_override=True).run(
            _ch_spec(), REQ
        )
        result = neural_operator_advisory_gate(env)
        assert result.status == "pass"

    def test_fails_when_advisory_false_and_qoi_above_threshold(self):
        # Force advisory=False, then mutate the QoI to be above threshold
        env = NeuralOperatorPhaseFieldAdapter(advisory_override=False).run(
            _ch_spec(), REQ
        )
        env["_l4_meta"]["neural_op_gates"]["qoi_relative_error"] = 0.5
        env["_l4_meta"]["neural_op_gates"]["qoi_gate_passes"] = False
        env["_l4_meta"]["neural_op_gates"]["beats_persistence_baseline"] = False
        result = neural_operator_advisory_gate(env)
        assert result.status == "fail"

    def test_passes_when_advisory_false_and_both_gates_pass(self):
        env = NeuralOperatorPhaseFieldAdapter(advisory_override=False).run(
            _ch_spec(), REQ
        )
        env["_l4_meta"]["neural_op_gates"]["qoi_relative_error"] = 0.05
        env["_l4_meta"]["neural_op_gates"]["qoi_gate_passes"] = True
        env["_l4_meta"]["neural_op_gates"]["beats_persistence_baseline"] = True
        result = neural_operator_advisory_gate(env)
        assert result.status == "pass"

    def test_fails_when_advisory_false_and_only_persistence_passes(self):
        env = NeuralOperatorPhaseFieldAdapter(advisory_override=False).run(
            _ch_spec(), REQ
        )
        env["_l4_meta"]["neural_op_gates"]["qoi_relative_error"] = 0.5
        env["_l4_meta"]["neural_op_gates"]["qoi_gate_passes"] = False
        env["_l4_meta"]["neural_op_gates"]["beats_persistence_baseline"] = True
        result = neural_operator_advisory_gate(env)
        assert result.status == "fail"

    def test_passes_for_non_neural_op_envelope(self):
        env = PrismsPfAdapter().run(_ch_spec(), REQ)
        result = neural_operator_advisory_gate(env)
        assert result.status == "pass"


# ---------------------------------------------------------------------------
# plug_swap_schema_invariance
# ---------------------------------------------------------------------------


class TestPlugSwapSchemaInvariance:
    def test_prisms_vs_moose_pass(self):
        spec = _ch_spec()
        prisms = PrismsPfAdapter().run(spec, REQ)
        moose = MoosePhaseFieldAdapter().run(spec, REQ)
        result = plug_swap_schema_invariance(prisms, moose)
        assert result.status == "pass"

    def test_synthetic_layer_drift_fails(self):
        spec = _ch_spec()
        prisms = PrismsPfAdapter().run(spec, REQ)
        bad = dict(prisms)
        bad["layer"] = "L5"  # synthetic schema break
        result = plug_swap_schema_invariance(prisms, bad)
        assert result.status == "fail"

    def test_synthetic_output_key_drift_fails(self):
        spec = _ch_spec()
        prisms = PrismsPfAdapter().run(spec, REQ)
        bad = dict(prisms)
        bad["output"] = dict(prisms["output"])
        bad["output"]["new_key_not_in_schema"] = 0.0
        result = plug_swap_schema_invariance(prisms, bad)
        assert result.status == "fail"


# ---------------------------------------------------------------------------
# microsim_subprocess_isolation
# ---------------------------------------------------------------------------


class TestMicrosimSubprocessIsolation:
    def test_passes_for_microsim_envelope_with_subprocess_mode(self):
        spec = PhaseFieldRunSpec(
            equation="grand_potential",
            domain=PhaseFieldDomain(dimension=2, extents=[10.0, 10.0], units="nm"),
            mesh=PhaseFieldMesh(nodes=[10, 10]),
            materials=[PhaseFieldMaterial(phase_name="alpha", initial_fraction=0.5)],
            time_steps=5,
            dt=0.01,
            n_dumps=4,
        )
        env = MicrosimGrandPotentialAdapter().run(spec, REQ)
        result = microsim_subprocess_isolation(env)
        assert result.status == "pass"

    def test_fails_when_isolation_mode_is_in_process(self):
        spec = PhaseFieldRunSpec(
            equation="grand_potential",
            domain=PhaseFieldDomain(dimension=2, extents=[10.0, 10.0], units="nm"),
            mesh=PhaseFieldMesh(nodes=[10, 10]),
            materials=[PhaseFieldMaterial(phase_name="alpha", initial_fraction=0.5)],
            time_steps=5,
            dt=0.01,
            n_dumps=4,
        )
        env = MicrosimGrandPotentialAdapter().run(spec, REQ)
        # Synthetically break the contract by switching isolation_mode
        env["_l4_meta"]["isolation_mode"] = "in_process"
        result = microsim_subprocess_isolation(env)
        assert result.status == "fail"

    def test_passes_for_non_microsim_envelope(self):
        env = PrismsPfAdapter().run(_ch_spec(), REQ)
        result = microsim_subprocess_isolation(env)
        assert result.status == "pass"

    def test_fails_when_microsim_missing_isolation_field(self):
        spec = PhaseFieldRunSpec(
            equation="grand_potential",
            domain=PhaseFieldDomain(dimension=2, extents=[10.0, 10.0], units="nm"),
            mesh=PhaseFieldMesh(nodes=[10, 10]),
            materials=[PhaseFieldMaterial(phase_name="alpha", initial_fraction=0.5)],
            time_steps=5,
            dt=0.01,
            n_dumps=4,
        )
        env = MicrosimGrandPotentialAdapter().run(spec, REQ)
        del env["_l4_meta"]["isolation_mode"]
        result = microsim_subprocess_isolation(env)
        assert result.status == "fail"
