"""Neural operator phase field adapter — U-AFNO + DeepONet, ADVISORY-ONLY.

PRD §L4 (Brief #2 verbatim): "Neural operator starting point: U-AFNO first,
DeepONet as comparison. Neural operator is advisory only until it beats
persistence baseline AND has < 10% relative QoI error on held-out classical
trajectories."

The neural operator replaces the deprecated PINNs-MPF approach. The synthesis
brief Section B Issue 3 makes this explicit:

    "Build or contribute to a neural operator phase field solver with
    CALPHAD coupling. Target: FNO or DeepONet on phase field order
    parameters with CALPHAD-computed driving forces as operator inputs."

This adapter is the engine of the synthesis recommendation: real-time
microstructure prediction during synthesis (FNO + AlabOS sensor stream
→ BoTorch decision in milliseconds), but ONLY after the advisory gates
clear.

Advisory gate (BOTH must pass before ``advisory=False``):
    1. ``beats_persistence_baseline``: model better than "the field
       at t=t_final equals the field at t=0" (a no-op predictor).
    2. ``qoi_relative_error < 0.10``: relative error on a held-out
       classical-trajectory QoI is below 10%.

Until BOTH gates pass, ``advisory=True`` is enforced. The
``neural_operator_advisory_gate`` falsifier in
:mod:`zer0pa_materials.falsifiers.l4_falsifiers` is the dual of this
contract: it FAILS if an envelope claims ``advisory=False`` without
both gates clearing.

CPU-side stub
-------------

The actual U-AFNO is too heavy for CPU verification. We stub a tiny
"linear surrogate" that:
    - reads the spec hash to seed a deterministic small-magnitude
      multiplicative factor
    - applies that factor to the PRISMS-PF stub trajectory to get a
      "predicted" trajectory
    - is calibrated so the QoI error is sometimes < 10% (passes gate)
      and sometimes > 10% (fails gate), depending on the spec hash.
This gives the advisory gate REAL signal even though no neural network
training is done.

Two architectures are exposed:
    - "u_afno"   (default): U-Net + Adaptive Fourier Neural Operator
    - "deeponet" (comparison): DeepONet branch+trunk
Both produce the same wire schema. The architecture choice is recorded
in ``_l4_meta.architecture``.
"""

from __future__ import annotations

import struct
from typing import Any, Literal

from zer0pa_materials.adapters.l4.base import L4Adapter, L4PredictRequest
from zer0pa_materials.adapters.l4.contracts import (
    MesoscaleRunResult,
    MicrostructureTrajectory,
    PhaseFieldRunSpec,
)
from zer0pa_materials.adapters.l4.prisms_pf import (
    _evolve_allen_cahn,
    _evolve_cahn_hilliard,
    _hash_to_uniform,
    _make_initial_field,
    _max_abs_violation,
    _relative_mass_drift,
    _spec_hash,
)
from zer0pa_materials.audit.sources import BlockedSourceManifest
from zer0pa_materials.boundary import RESEARCH_BOUNDARY
from zer0pa_materials.envelope.hashing import sha256_of
from zer0pa_materials.envelope.layer_outputs import L4PhaseFieldOutput


NeuralOpArchitecture = Literal["u_afno", "deeponet"]


def _qoi_from_trajectory(traj: list[list[list[float]]]) -> float:
    """Compute a scalar QoI from a phase-field trajectory.

    We pick the final-time spatial mean as the QoI — robust to mesh
    permutations, easy to compare across solvers, and load-bearing for
    the Cahn-Hilliard mass invariant. For Allen-Cahn the QoI is the
    final-time mean absolute order parameter.
    """
    if not traj:
        return 0.0
    final = traj[-1]
    n_y = len(final)
    n_x = len(final[0]) if n_y > 0 else 0
    if n_x == 0 or n_y == 0:
        return 0.0
    return sum(sum(abs(v) for v in row) for row in final) / (n_y * n_x)


def _persistence_qoi(traj: list[list[list[float]]]) -> float:
    """Persistence baseline QoI: predict final = initial.

    For mass-conserved systems this is exactly the initial spatial mean,
    which is the SAME as the final spatial mean if the solver conserves
    mass. So persistence is a strong baseline for Cahn-Hilliard.
    """
    if not traj:
        return 0.0
    initial = traj[0]
    n_y = len(initial)
    n_x = len(initial[0]) if n_y > 0 else 0
    if n_x == 0 or n_y == 0:
        return 0.0
    return sum(sum(abs(v) for v in row) for row in initial) / (n_y * n_x)


def _surrogate_predict(
    classical_traj: list[list[list[float]]],
    spec_hash: str,
    architecture: NeuralOpArchitecture,
) -> list[list[list[float]]]:
    """Synthetic neural-operator prediction: classical trajectory * (1 + epsilon).

    The epsilon is deterministic from the spec hash (so this is reproducible)
    and ranges in [-0.15, 0.15]. Combined with a small (sub-cell) phase
    shift, the QoI relative error sometimes exceeds 10% and sometimes does
    not. The U-AFNO and DeepONet variants use different byte offsets so
    they do NOT produce identical predictions.
    """
    byte_offset = 0 if architecture == "u_afno" else 8
    eps = (_hash_to_uniform(spec_hash, byte_offset) - 0.5) * 0.30  # [-0.15, 0.15]
    n_dumps = len(classical_traj)
    n_y = len(classical_traj[0])
    n_x = len(classical_traj[0][0]) if n_y > 0 else 0
    pred: list[list[list[float]]] = []
    for k in range(n_dumps):
        snap = [
            [classical_traj[k][j][i] * (1.0 + eps) for i in range(n_x)]
            for j in range(n_y)
        ]
        pred.append(snap)
    return pred


def _classical_reference_trajectory(
    spec: PhaseFieldRunSpec,
) -> list[list[list[float]]]:
    """Generate the same classical trajectory PRISMS-PF would for this spec.

    Used as the held-out reference for the < 10% QoI gate.
    """
    n_x = spec.mesh.nodes[0]
    n_y = spec.mesh.nodes[1] if len(spec.mesh.nodes) > 1 else n_x
    h = _spec_hash(spec)
    if spec.equation == "allen_cahn":
        ic = "spinodal_noise" if spec.initial_condition == "fixture_default" else spec.initial_condition
        initial = _make_initial_field(n_y, n_x, ic, h, mean=0.0)
        return _evolve_allen_cahn(initial, spec.n_dumps)
    elif spec.equation == "cahn_hilliard":
        ic = "uniform" if spec.initial_condition == "fixture_default" else spec.initial_condition
        initial = _make_initial_field(n_y, n_x, ic, h, mean=0.5)
        return _evolve_cahn_hilliard(initial, spec.n_dumps, mass_drift=0.0)
    elif spec.equation == "mpf":
        initial_ac = _make_initial_field(n_y, n_x, "spinodal_noise", h, mean=0.0)
        traj_ac = _evolve_allen_cahn(initial_ac, spec.n_dumps)
        initial_ch = _make_initial_field(n_y, n_x, "uniform", h, mean=0.5)
        traj_ch = _evolve_cahn_hilliard(initial_ch, spec.n_dumps, mass_drift=0.0)
        return [
            [
                [(traj_ac[k][j][i] + traj_ch[k][j][i]) / 2.0 for i in range(n_x)]
                for j in range(n_y)
            ]
            for k in range(spec.n_dumps)
        ]
    else:  # grand_potential
        # Use cahn_hilliard as a fallback reference
        ic = "uniform" if spec.initial_condition == "fixture_default" else spec.initial_condition
        initial = _make_initial_field(n_y, n_x, ic, h, mean=0.5)
        return _evolve_cahn_hilliard(initial, spec.n_dumps, mass_drift=0.0)


class NeuralOperatorPhaseFieldAdapter(L4Adapter):
    """U-AFNO / DeepONet neural-operator surrogate. ADVISORY-ONLY until both
    gates clear (PRD §L4 Brief #2 reframe).

    Parameters
    ----------
    architecture:
        "u_afno" (default; PRD-mandated starting point) or "deeponet"
        (comparison). The two architectures use different deterministic
        seeds so their predictions differ; both produce the same wire
        schema.
    qoi_relative_error_threshold:
        Threshold for the < 10% QoI gate (default 0.10). Values <= this
        threshold are considered to pass the gate. Configurable for
        future tightening.
    advisory_override:
        For test fixtures that need to assert the advisory gate, this
        forces the advisory flag regardless of measured gate states.
        Production code SHOULD NOT pass this argument.
    """

    NAME = "NeuralOperatorPhaseFieldAdapter"
    VERSION = "0.1.0"
    LIBRARY_LICENSE = "MIT"
    QOI_THRESHOLD = 0.10

    def __init__(
        self,
        architecture: NeuralOpArchitecture = "u_afno",
        qoi_relative_error_threshold: float = 0.10,
        advisory_override: bool | None = None,
    ) -> None:
        self.architecture: NeuralOpArchitecture = architecture
        self.qoi_threshold = qoi_relative_error_threshold
        self._advisory_override = advisory_override
        self.name = self.NAME
        self.version = self.VERSION
        self.backend = "stub"
        self.engine = (
            "U-AFNO-stub" if architecture == "u_afno" else "DeepONet-stub"
        )
        self.description = (
            f"Neural operator surrogate ({architecture}); ADVISORY-ONLY until "
            f"persistence-baseline AND <{qoi_relative_error_threshold * 100:.0f}% "
            f"QoI gates clear."
        )

    # -------------------------------------------------------------------- run

    def run(
        self,
        spec: PhaseFieldRunSpec,
        request: L4PredictRequest,
    ) -> dict[str, Any]:
        if not isinstance(spec, PhaseFieldRunSpec):
            raise TypeError(
                f"{self.NAME} consumes PhaseFieldRunSpec; got {type(spec).__name__}"
            )

        # Compute classical reference (PRISMS-PF-shaped) and the surrogate prediction
        h = _spec_hash(spec)
        classical = _classical_reference_trajectory(spec)
        prediction = _surrogate_predict(classical, h, self.architecture)

        # QoI gates
        qoi_classical = _qoi_from_trajectory(classical)
        qoi_surrogate = _qoi_from_trajectory(prediction)
        qoi_persistence = _persistence_qoi(classical)

        # Relative QoI error on held-out classical trajectory
        if abs(qoi_classical) > 1e-12:
            qoi_relative_error = abs(qoi_surrogate - qoi_classical) / abs(qoi_classical)
        else:
            qoi_relative_error = abs(qoi_surrogate - qoi_classical)
        # Persistence baseline error (vs classical)
        if abs(qoi_classical) > 1e-12:
            persistence_relative_error = abs(qoi_persistence - qoi_classical) / abs(qoi_classical)
        else:
            persistence_relative_error = abs(qoi_persistence - qoi_classical)

        beats_persistence = qoi_relative_error < persistence_relative_error
        qoi_gate_passes = qoi_relative_error < self.qoi_threshold

        # Advisory state: True (advisory) UNLESS both gates pass
        if self._advisory_override is not None:
            advisory = self._advisory_override
        else:
            advisory = not (beats_persistence and qoi_gate_passes)

        # Conserved quantities (for compat with the gates):
        # the canonical phase-field gates are still computed even though
        # they shouldn't gate-promote a surrogate result.
        conserved: dict[str, float] = {
            "qoi_relative_error": qoi_relative_error,
            "persistence_qoi_relative_error": persistence_relative_error,
            "beats_persistence_baseline": float(1.0 if beats_persistence else 0.0),
            "qoi_classical": qoi_classical,
            "qoi_surrogate": qoi_surrogate,
            "qoi_persistence": qoi_persistence,
        }
        if spec.equation == "allen_cahn":
            conserved["bounds_violation_max"] = _max_abs_violation(prediction)
        elif spec.equation == "cahn_hilliard":
            conserved["mass_drift_relative"] = _relative_mass_drift(prediction)
        elif spec.equation == "mpf":
            conserved["bounds_violation_max"] = _max_abs_violation(prediction)
            conserved["mass_drift_relative"] = _relative_mass_drift(prediction)

        times = [k * spec.dt for k in range(spec.n_dumps)]
        traj = MicrostructureTrajectory(
            times=times,
            fields={"phi": prediction},
            mesh=spec.mesh,
        )
        result = MesoscaleRunResult(
            spec=spec,
            trajectory=traj,
            conserved_quantities=conserved,
            run_id=request.run_id,
            backend=self.backend,
            advisory=advisory,
            adapter_name=self.NAME,
            adapter_version=self.VERSION,
            notes=[
                f"Neural operator ({self.architecture}); advisory={advisory}",
                f"qoi_rel_err={qoi_relative_error:.4f}; "
                f"persistence_rel_err={persistence_relative_error:.4f}; "
                f"beats_persistence={beats_persistence}",
            ],
        )

        return self._build_envelope(
            spec, request, result, conserved, advisory, beats_persistence, qoi_gate_passes
        )

    def _build_envelope(
        self,
        spec: PhaseFieldRunSpec,
        request: L4PredictRequest,
        result: MesoscaleRunResult,
        conserved: dict[str, float],
        advisory: bool,
        beats_persistence: bool,
        qoi_gate_passes: bool,
    ) -> dict[str, Any]:
        l4_output: dict[str, Any] = {
            "cahn_hilliard_mass_drift": conserved.get("mass_drift_relative"),
            "allen_cahn_bounds_violation": conserved.get("bounds_violation_max"),
            "spparks_potts_energy_monotonic": None,
            "microstructure_trajectory_uri": f"artifact:{request.run_id}/neural-op-trajectory",
        }
        l4_obj = L4PhaseFieldOutput.model_validate(l4_output)
        falsifier_items = [it.model_dump(mode="json") for it in l4_obj.falsifier_items()]
        active_items = [it for it in falsifier_items if it["actual"] is not None]
        falsifier_status = (
            "fail" if any(it["status"] == "fail" for it in active_items)
            else "pass"
        )

        input_hash = sha256_of(spec.model_dump(mode="json"))
        out_hash = sha256_of(l4_output)

        envelope = {
            "research_boundary": RESEARCH_BOUNDARY,
            "contract_version": "zer0pa.materials.layer-envelope.v1",
            "layer": "L4",
            "run_id": request.run_id,
            "candidate_id": request.candidate_id,
            "campaign_id": request.campaign_id,
            "tool_adapter": {
                "name": self.NAME,
                "version": self.VERSION,
                "backend": self.backend,
                "engine": self.engine,
            },
            "output": l4_output,
            "confidence": {
                # Advisory results have low confidence by definition.
                "score": 0.2 if advisory else 0.7,
                "band": "low" if advisory else "medium",
                "basis": [
                    f"adapter={self.NAME}",
                    f"architecture={self.architecture}",
                    f"advisory={advisory}",
                    f"qoi_rel_err={conserved.get('qoi_relative_error', 0.0):.4f}",
                    f"beats_persistence={beats_persistence}",
                ],
            },
            "disagreement": {"metrics": []},
            "falsifier": {"status": falsifier_status, "items": falsifier_items},
            "audit": {
                "audit_record_id": f"audit:{request.run_id}/neural-op",
                "input_hash": input_hash,
                "output_hash": out_hash,
                "source_manifest_refs": ["src:neural-op:weights"],
            },
            "rights": {
                "rights_claim_id": request.rights_claim_id,
                "reuse_scope": "tenant_only",
            },
            "back_edges": [],
            "_l4_meta": {
                "equation": spec.equation,
                "mesh_nodes": spec.mesh.nodes,
                "n_dumps": spec.n_dumps,
                "conserved_quantities": conserved,
                "result_payload": result.model_dump(mode="json"),
                "advisory": advisory,
                "adapter_name": self.NAME,
                "architecture": self.architecture,
                "neural_op_gates": {
                    "beats_persistence_baseline": beats_persistence,
                    "qoi_relative_error": conserved["qoi_relative_error"],
                    "qoi_threshold": self.qoi_threshold,
                    "qoi_gate_passes": qoi_gate_passes,
                    "persistence_relative_error": conserved["persistence_qoi_relative_error"],
                },
            },
        }
        return envelope

    def blocked_manifests(self) -> list[dict[str, Any]]:
        return [
            BlockedSourceManifest(
                source_manifest_id="src:neural-op:weights",
                attempted_locator="zer0pa-internal://l4/neural-op",
                blocker_reason="unavailable_credentials",
                blocker_detail=(
                    "U-AFNO / DeepONet phase-field surrogate weights are "
                    "Zer0pa-trained; production weights live on Runpod. "
                    "The CPU-side stub uses a deterministic linear surrogate "
                    "calibrated so the <10% QoI gate has signal (sometimes "
                    "passes, sometimes fails depending on input). The "
                    "advisory flag is enforced until the persistence-baseline "
                    "AND <10% relative QoI error gates clear."
                ),
                retry_strategy=(
                    "Train the U-AFNO on PRISMS-PF reference trajectories; "
                    "verify on held-out classical trajectories; only then "
                    "may the advisory flag be False on production envelopes."
                ),
            ).model_dump(mode="json"),
        ]
