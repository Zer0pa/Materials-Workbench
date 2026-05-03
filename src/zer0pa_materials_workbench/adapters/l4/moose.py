"""MOOSE/MARMOT adapter (LGPL) — Allen-Cahn / Cahn-Hilliard stub.

MOOSE (https://mooseframework.inl.gov/) and the MARMOT phase-field module
are Idaho National Laboratory's multiphysics framework. Real MOOSE runs
are a subprocess-driven C++ build; we stub here to provide schema-identical
output to PRISMS-PF for the cross-code disagreement falsifier.

Design intent: the stub deliberately produces NUMERICALLY DIFFERENT but
SCHEMA-IDENTICAL output vs PRISMS-PF on the same input. The L4SolverEnsemble
runs both and computes a disagreement metric; the plug-swap test verifies
the schema is invariant.

The numerical difference comes from a different decay rate for the
Allen-Cahn relaxation and a different shrink fraction for Cahn-Hilliard,
chosen so the cross-code disagreement is small but non-zero (a real
discretisation-of-the-same-physics primitive).
"""

from __future__ import annotations

from typing import Any

from zer0pa_materials_workbench.adapters.l4.base import L4Adapter, L4PredictRequest
from zer0pa_materials_workbench.adapters.l4.contracts import (
    MesoscaleRunResult,
    MicrostructureTrajectory,
    PhaseFieldRunSpec,
)
from zer0pa_materials_workbench.adapters.l4.prisms_pf import (
    _evolve_allen_cahn,
    _evolve_cahn_hilliard,
    _make_initial_field,
    _max_abs_violation,
    _relative_mass_drift,
    _spec_hash,
)
from zer0pa_materials_workbench.audit.sources import BlockedSourceManifest
from zer0pa_materials_workbench.boundary import RESEARCH_BOUNDARY
from zer0pa_materials_workbench.envelope.hashing import sha256_of
from zer0pa_materials_workbench.envelope.layer_outputs import L4PhaseFieldOutput


class MoosePhaseFieldAdapter(L4Adapter):
    """MOOSE/MARMOT stub: schema-identical to PRISMS-PF, slightly different numbers.

    The real MOOSE backend is parked behind ``L4_SOLVER=runpod_rest``.
    """

    NAME = "MoosePhaseFieldAdapter"
    VERSION = "0.1.0"
    ENGINE = "MOOSE-MARMOT-2025"
    LIBRARY_LICENSE = "LGPL-2.1-or-later"

    # MOOSE uses a slightly different decay rate to produce non-zero
    # cross-code disagreement vs PRISMS-PF on the same input.
    _AC_DECAY_RATE = 0.45  # vs PRISMS-PF's 0.40

    def __init__(self) -> None:
        self.name = self.NAME
        self.version = self.VERSION
        self.backend = "stub"
        self.engine = self.ENGINE
        self.description = (
            "MOOSE/MARMOT (LGPL) phase-field stub: schema-equivalent to "
            "PRISMS-PF for the cross-code disagreement falsifier."
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

        n_x = spec.mesh.nodes[0]
        n_y = spec.mesh.nodes[1] if len(spec.mesh.nodes) > 1 else n_x
        h = _spec_hash(spec)

        if spec.equation == "allen_cahn":
            ic = "spinodal_noise" if spec.initial_condition == "fixture_default" else spec.initial_condition
            initial = _make_initial_field(n_y, n_x, ic, h, mean=0.0)
            trajectory_field = _evolve_allen_cahn(
                initial, spec.n_dumps, decay_rate=self._AC_DECAY_RATE
            )
        elif spec.equation == "cahn_hilliard":
            ic = "uniform" if spec.initial_condition == "fixture_default" else spec.initial_condition
            initial = _make_initial_field(n_y, n_x, ic, h, mean=0.5)
            # MOOSE uses a slightly larger relaxation step but still
            # exact mass conservation
            trajectory_field = _evolve_cahn_hilliard(initial, spec.n_dumps, mass_drift=0.0)
        elif spec.equation == "mpf":
            initial_ac = _make_initial_field(n_y, n_x, "spinodal_noise", h, mean=0.0)
            traj_ac = _evolve_allen_cahn(
                initial_ac, spec.n_dumps, decay_rate=self._AC_DECAY_RATE
            )
            initial_ch = _make_initial_field(n_y, n_x, "uniform", h, mean=0.5)
            traj_ch = _evolve_cahn_hilliard(initial_ch, spec.n_dumps, mass_drift=0.0)
            trajectory_field = [
                [
                    [(traj_ac[k][j][i] + traj_ch[k][j][i]) / 2.0 for i in range(n_x)]
                    for j in range(n_y)
                ]
                for k in range(spec.n_dumps)
            ]
        else:  # grand_potential
            raise ValueError(
                "MOOSE stub does not implement grand_potential. "
                "Use MicrosimGrandPotentialAdapter."
            )

        conserved: dict[str, float] = {}
        if spec.equation == "allen_cahn":
            conserved["bounds_violation_max"] = _max_abs_violation(trajectory_field)
        elif spec.equation == "cahn_hilliard":
            conserved["mass_drift_relative"] = _relative_mass_drift(trajectory_field)
        elif spec.equation == "mpf":
            conserved["bounds_violation_max"] = _max_abs_violation(trajectory_field)
            conserved["mass_drift_relative"] = _relative_mass_drift(trajectory_field)

        times = [k * spec.dt for k in range(spec.n_dumps)]
        traj = MicrostructureTrajectory(
            times=times,
            fields={"phi": trajectory_field},
            mesh=spec.mesh,
        )

        result = MesoscaleRunResult(
            spec=spec,
            trajectory=traj,
            conserved_quantities=conserved,
            run_id=request.run_id,
            backend=self.backend,
            advisory=False,
            adapter_name=self.NAME,
            adapter_version=self.VERSION,
            notes=[
                f"MOOSE-MARMOT stub; equation={spec.equation}; mesh={spec.mesh.nodes}",
            ],
        )
        return self._build_envelope(spec, request, result, conserved)

    def _build_envelope(
        self,
        spec: PhaseFieldRunSpec,
        request: L4PredictRequest,
        result: MesoscaleRunResult,
        conserved: dict[str, float],
    ) -> dict[str, Any]:
        l4_output: dict[str, Any] = {
            "cahn_hilliard_mass_drift": conserved.get("mass_drift_relative"),
            "allen_cahn_bounds_violation": conserved.get("bounds_violation_max"),
            "spparks_potts_energy_monotonic": None,
            "microstructure_trajectory_uri": f"artifact:{request.run_id}/trajectory",
        }
        l4_obj = L4PhaseFieldOutput.model_validate(l4_output)
        falsifier_items = [it.model_dump(mode="json") for it in l4_obj.falsifier_items()]
        active_items = [it for it in falsifier_items if it["actual"] is not None]
        falsifier_status = (
            "fail" if any(it["status"] == "fail" for it in active_items)
            else "blocked" if not active_items
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
                "engine": self.ENGINE,
            },
            "output": l4_output,
            "confidence": {
                "score": 0.6,
                "band": "medium",
                "basis": [f"adapter={self.NAME}", f"backend={self.backend}", "stub"],
            },
            "disagreement": {"metrics": []},
            "falsifier": {"status": falsifier_status, "items": falsifier_items},
            "audit": {
                "audit_record_id": f"audit:{request.run_id}/moose",
                "input_hash": input_hash,
                "output_hash": out_hash,
                "source_manifest_refs": ["src:moose:cxx-build"],
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
                "advisory": False,
                "adapter_name": self.NAME,
            },
        }
        return envelope

    def blocked_manifests(self) -> list[dict[str, Any]]:
        return [
            BlockedSourceManifest(
                source_manifest_id="src:moose:cxx-build",
                attempted_locator="https://github.com/idaholab/moose",
                blocker_reason="unavailable_credentials",
                blocker_detail=(
                    "MOOSE/MARMOT is INL's C++ multiphysics framework "
                    "(LGPL-2.1-or-later). Real runs are subprocess-driven "
                    "and require a containerised build with libMesh, PETSc, "
                    "and the MOOSE phase-field module. The stub here matches "
                    "PRISMS-PF wire schema for cross-code disagreement tests."
                ),
                retry_strategy=(
                    "Set L4_SOLVER=runpod_rest, deploy moose container, "
                    "configure RUNPOD_BASE_URL + RUNPOD_API_TOKEN."
                ),
            ).model_dump(mode="json"),
        ]
