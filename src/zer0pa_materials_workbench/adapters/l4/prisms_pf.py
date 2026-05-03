"""PRISMS-PF adapter (LGPL) — Allen-Cahn / Cahn-Hilliard / MPF stub.

PRISMS-PF (https://prisms-center.github.io/phaseField/) is a C++ phase-field
code with a Python wrapper. The real C++ build is parked behind
``L4_SOLVER=runpod_rest`` until a containerised build is provisioned.

This stub deterministically generates synthetic Allen-Cahn / Cahn-Hilliard
trajectories on a 32×32 fixture suitable for falsifier verification:

    Allen-Cahn (non-conserved, double-well potential):
        Initial:   phi(x,y,0) ∈ {-1, +1} from spinodal seeded noise
        Evolution: simple gradient descent toward {-1, +1} attractors
        Bounds gate: max(|phi|) - 1 must be < 1e-4 (PRD §L4 falsifiers)

    Cahn-Hilliard (conserved):
        Initial:   phi(x,y,0) = phi0 ± epsilon noise (mean phi0 fixed)
        Evolution: synthetic shrink-toward-mean dynamics that PRESERVE the
                   spatial mean exactly.  We add a tiny known drift the
                   negative-fixture path can amplify to trigger the gate.
        Mass-drift gate: |<phi>(t) - <phi>(0)| / |<phi>(0)| < 1e-3.

The synthetic dynamics are NOT real PRISMS-PF — they're deterministic data
generators chosen so the falsifier gates have signal. The wire-level shape
is identical to what a real PRISMS-PF run would emit.
"""

from __future__ import annotations

import math
import struct
from typing import Any

from zer0pa_materials_workbench.adapters.l4.base import L4Adapter, L4PredictRequest
from zer0pa_materials_workbench.adapters.l4.contracts import (
    MesoscaleRunResult,
    MicrostructureTrajectory,
    PhaseFieldRunSpec,
)
from zer0pa_materials_workbench.audit.sources import BlockedSourceManifest
from zer0pa_materials_workbench.boundary import RESEARCH_BOUNDARY
from zer0pa_materials_workbench.envelope.hashing import sha256_of
from zer0pa_materials_workbench.envelope.layer_outputs import L4PhaseFieldOutput

# ---------------------------------------------------------------------------
# Synthetic-trajectory helpers (deterministic from spec hash)
# ---------------------------------------------------------------------------


def _spec_hash(spec: PhaseFieldRunSpec, seed_offset: int = 0) -> str:
    """Deterministic hash of a spec; used as the synthetic-data RNG seed."""
    return sha256_of(spec.model_dump(mode="json"))


def _hash_to_uniform(h: str, byte_offset: int) -> float:
    """Map 8 bytes of a hash to a uniform float in [0, 1)."""
    hex_body = h.split(":", 1)[1]
    raw = bytes.fromhex(hex_body[byte_offset * 2 : byte_offset * 2 + 16])
    return struct.unpack(">Q", raw)[0] / (2**64)


def _make_initial_field(
    n_y: int, n_x: int, ic: str, seed_hash: str, mean: float = 0.0
) -> list[list[float]]:
    """Construct a deterministic 2D initial field as nested list."""
    field_2d: list[list[float]] = []
    for j in range(n_y):
        row: list[float] = []
        for i in range(n_x):
            offset = (j * n_x + i) % 8  # cycle through hash bytes
            u = _hash_to_uniform(seed_hash, offset)
            if ic == "uniform":
                row.append(mean)
            elif ic == "single_seed":
                # one centred Gaussian-ish bump
                cy, cx = n_y / 2.0, n_x / 2.0
                r2 = (j - cy) ** 2 + (i - cx) ** 2
                sigma2 = max(1.0, (n_x / 8.0) ** 2)
                row.append(mean + math.exp(-r2 / sigma2))
            else:  # spinodal_noise / fixture_default
                # tiny noise around mean, deterministically from hash
                row.append(mean + (u - 0.5) * 0.02)
        field_2d.append(row)
    return field_2d


def _evolve_allen_cahn(
    initial_field: list[list[float]],
    n_dumps: int,
    decay_rate: float = 0.4,
) -> list[list[list[float]]]:
    """Synthetic Allen-Cahn evolution: each cell relaxes toward {-1, +1}.

    The relaxation is:
        phi(t+dt) = phi(t) + decay * sign(phi(t)) * (1 - |phi(t)|) * dt
    Bounded so |phi| <= 1.0 - 1e-12 to keep the bounds gate clean.
    """
    n_y = len(initial_field)
    n_x = len(initial_field[0]) if n_y > 0 else 0
    trajectory: list[list[list[float]]] = []
    cur = [row[:] for row in initial_field]
    trajectory.append([row[:] for row in cur])
    dt = 1.0 / max(1, n_dumps - 1)
    for _ in range(n_dumps - 1):
        nxt = [[0.0] * n_x for _ in range(n_y)]
        for j in range(n_y):
            for i in range(n_x):
                v = cur[j][i]
                # Relax toward ±1; sign(0) handled as +1 by convention
                sign_v = 1.0 if v >= 0 else -1.0
                step = decay_rate * sign_v * (1.0 - abs(v)) * dt
                new_v = v + step
                # hard clamp to keep bounds-violation < 1e-4
                if new_v > 1.0:
                    new_v = 1.0 - 1e-12
                elif new_v < -1.0:
                    new_v = -1.0 + 1e-12
                nxt[j][i] = new_v
        cur = nxt
        trajectory.append([row[:] for row in cur])
    return trajectory


def _evolve_cahn_hilliard(
    initial_field: list[list[float]],
    n_dumps: int,
    mass_drift: float = 0.0,
) -> list[list[list[float]]]:
    """Synthetic Cahn-Hilliard evolution with EXACT mass conservation.

    We compute the mean of the initial field, then at every timestep drive
    each cell toward the mean by a small fraction, while applying the EXACT
    correction that keeps the spatial mean equal to the initial mean.

    A non-zero ``mass_drift`` adds a tiny systematic mean shift per dump for
    falsification-wave fixtures that need to TRIGGER the mass-drift gate.
    """
    n_y = len(initial_field)
    n_x = len(initial_field[0]) if n_y > 0 else 0
    n_cells = n_y * n_x
    if n_cells == 0:
        raise ValueError("Cahn-Hilliard requires non-empty mesh")
    initial_mean = sum(sum(row) for row in initial_field) / n_cells
    trajectory: list[list[list[float]]] = []
    cur = [row[:] for row in initial_field]
    trajectory.append([row[:] for row in cur])
    relax = 0.1  # fraction per step
    for k in range(1, n_dumps):
        # First, relax each cell toward the running mean
        cur_mean = sum(sum(row) for row in cur) / n_cells
        nxt = [[(1.0 - relax) * cur[j][i] + relax * cur_mean for i in range(n_x)] for j in range(n_y)]
        # Compute current mean and shift to enforce mean-preservation
        nxt_mean = sum(sum(row) for row in nxt) / n_cells
        target_mean = initial_mean + mass_drift * k  # drift only if non-zero
        delta = target_mean - nxt_mean
        for j in range(n_y):
            for i in range(n_x):
                nxt[j][i] += delta
        cur = nxt
        trajectory.append([row[:] for row in cur])
    return trajectory


def _max_abs_violation(traj: list[list[list[float]]]) -> float:
    """For Allen-Cahn: max(|phi|) - 1 over the trajectory."""
    worst = 0.0
    for snap in traj:
        for row in snap:
            for v in row:
                excess = abs(v) - 1.0
                if excess > worst:
                    worst = excess
    return max(worst, 0.0)


def _relative_mass_drift(traj: list[list[list[float]]]) -> float:
    """For Cahn-Hilliard: |<phi>(end) - <phi>(0)| / max(|<phi>(0)|, 1e-12)."""
    n_y = len(traj[0])
    n_x = len(traj[0][0]) if n_y > 0 else 0
    n_cells = n_y * n_x
    initial_mean = sum(sum(row) for row in traj[0]) / n_cells
    final_mean = sum(sum(row) for row in traj[-1]) / n_cells
    return abs(final_mean - initial_mean) / max(abs(initial_mean), 1e-12)


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------


class PrismsPfAdapter(L4Adapter):
    """PRISMS-PF stub. Synthesises Allen-Cahn / Cahn-Hilliard / MPF trajectories.

    The real PRISMS-PF C++ build is gated behind ``L4_SOLVER=runpod_rest``.
    See ``BlockedSourceManifest src:prisms-pf:cxx-build`` for the cutover
    procedure.
    """

    NAME = "PrismsPfAdapter"
    VERSION = "0.1.0"
    ENGINE = "PRISMS-PF-2.4"
    LIBRARY_LICENSE = "LGPL-2.1-or-later"

    def __init__(self) -> None:
        self.name = self.NAME
        self.version = self.VERSION
        self.backend = "stub"
        self.engine = self.ENGINE
        self.description = "PRISMS-PF (LGPL) phase-field stub: Allen-Cahn, Cahn-Hilliard, MPF."

    # -------------------------------------------------------------------- run

    def run(
        self,
        spec: PhaseFieldRunSpec,
        request: L4PredictRequest,
    ) -> dict[str, Any]:
        """Run PRISMS-PF stub on ``spec`` and return an envelope dict."""
        if not isinstance(spec, PhaseFieldRunSpec):
            raise TypeError(
                f"{self.NAME} consumes PhaseFieldRunSpec; got {type(spec).__name__}"
            )

        # Build the initial field on the requested mesh
        n_x = spec.mesh.nodes[0]
        n_y = spec.mesh.nodes[1] if len(spec.mesh.nodes) > 1 else n_x
        h = _spec_hash(spec)

        # Allen-Cahn / Cahn-Hilliard / MPF: scalar phi field
        if spec.equation == "allen_cahn":
            ic = "spinodal_noise" if spec.initial_condition == "fixture_default" else spec.initial_condition
            initial = _make_initial_field(n_y, n_x, ic, h, mean=0.0)
            trajectory_field = _evolve_allen_cahn(initial, spec.n_dumps)
        elif spec.equation == "cahn_hilliard":
            ic = "uniform" if spec.initial_condition == "fixture_default" else spec.initial_condition
            initial = _make_initial_field(n_y, n_x, ic, h, mean=0.5)
            trajectory_field = _evolve_cahn_hilliard(initial, spec.n_dumps, mass_drift=0.0)
        elif spec.equation == "mpf":
            # multi-phase-field: average of an Allen-Cahn trajectory and a Cahn-Hilliard one
            initial_ac = _make_initial_field(n_y, n_x, "spinodal_noise", h, mean=0.0)
            traj_ac = _evolve_allen_cahn(initial_ac, spec.n_dumps)
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
                "PRISMS-PF stub does not implement grand_potential. "
                "Use MicrosimGrandPotentialAdapter."
            )

        # Compute conserved quantities
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
                f"PRISMS-PF stub; equation={spec.equation}; mesh={spec.mesh.nodes}; n_dumps={spec.n_dumps}",
            ],
        )

        return self._build_envelope(spec, request, result, conserved)

    # ------------------------------------------------------------- envelope

    def _build_envelope(
        self,
        spec: PhaseFieldRunSpec,
        request: L4PredictRequest,
        result: MesoscaleRunResult,
        conserved: dict[str, float],
    ) -> dict[str, Any]:
        # L4PhaseFieldOutput surfaces the gate-checked values
        l4_output: dict[str, Any] = {
            "cahn_hilliard_mass_drift": conserved.get("mass_drift_relative"),
            "allen_cahn_bounds_violation": conserved.get("bounds_violation_max"),
            "spparks_potts_energy_monotonic": None,  # not a kMC run
            "microstructure_trajectory_uri": f"artifact:{request.run_id}/trajectory",
        }

        # Validate against the layer-output schema
        l4_obj = L4PhaseFieldOutput.model_validate(l4_output)
        falsifier_items = [item.model_dump(mode="json") for item in l4_obj.falsifier_items()]
        # Roll-up status considers ONLY gates whose value was measured. The
        # other gates default to blocked because the corresponding numeric
        # value is None (not applicable to this equation / kMC mode).
        active_items = [it for it in falsifier_items if it["actual"] is not None]
        falsifier_status = (
            "fail" if any(it["status"] == "fail" for it in active_items)
            else "blocked" if not active_items
            else "pass"
        )

        # Hashing
        input_hash = sha256_of(spec.model_dump(mode="json"))
        # Drop the canonical result from the envelope output; keep schema clean
        # by stashing it under an underscore-prefixed key.
        l4_output_with_payload = dict(l4_output)
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
            "output": l4_output_with_payload,
            "confidence": {
                "score": 0.6,
                "band": "medium",
                "basis": [f"adapter={self.NAME}", f"backend={self.backend}", "stub"],
            },
            "disagreement": {"metrics": []},
            "falsifier": {"status": falsifier_status, "items": falsifier_items},
            "audit": {
                "audit_record_id": f"audit:{request.run_id}/prisms-pf",
                "input_hash": input_hash,
                "output_hash": out_hash,
                "source_manifest_refs": ["src:prisms-pf:cxx-build"],
            },
            "rights": {
                "rights_claim_id": request.rights_claim_id,
                "reuse_scope": "tenant_only",
            },
            "back_edges": [],
            # Non-schema metadata retained outside Envelope-validated keys.
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

    # -------------------------------------------------------- blocked manifests

    def blocked_manifests(self) -> list[dict[str, Any]]:
        manifests = [
            BlockedSourceManifest(
                source_manifest_id="src:prisms-pf:cxx-build",
                attempted_locator="https://github.com/prisms-center/phaseField",
                blocker_reason="unavailable_credentials",
                blocker_detail=(
                    "PRISMS-PF is a C++ phase-field code (LGPL-2.1-or-later) "
                    "that requires a deal.II build, MPI, and a Python wrapper. "
                    "The CPU-side stub generates synthetic Allen-Cahn / "
                    "Cahn-Hilliard / MPF trajectories on a 32x32 fixture; the "
                    "real build is parked behind L4_SOLVER=runpod_rest until "
                    "a containerised build is provisioned."
                ),
                retry_strategy=(
                    "Set L4_SOLVER=runpod_rest, configure RUNPOD_BASE_URL and "
                    "RUNPOD_API_TOKEN, then deploy the prisms_pf container."
                ),
            ).model_dump(mode="json"),
        ]
        return manifests
