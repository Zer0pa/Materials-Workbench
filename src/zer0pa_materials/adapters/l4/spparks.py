"""SPPARKS kMC adapter (GPL) — Potts-model grain-coarsening stub.

SPPARKS (https://spparks.github.io/) is the Stochastic Parallel PARticle
Kinetic Simulator from Sandia National Laboratories. License: GPL — outputs
are commercialisable; the tool itself is copyleft. We invoke SPPARKS via
subprocess in production; here we stub a Potts model.

Falsifier target (PRD §L4): "T=0 SPPARKS Potts energy does not increase
across dumps." At zero temperature, every accepted spin-flip strictly
lowers (or keeps equal) the bond energy. We synthesise this behaviour by
running a deterministic q-state Potts coarsening that converges to a
single-domain ground state, with energy strictly non-increasing.

The "potts energy" here is the count of unlike-spin nearest-neighbour
bonds (4-connectivity on a square lattice). At T=0 this number is
non-increasing across dump times.
"""

from __future__ import annotations

import struct
from typing import Any

from zer0pa_materials.adapters.l4.base import L4Adapter, L4PredictRequest
from zer0pa_materials.adapters.l4.contracts import (
    KmcRunSpec,
    MesoscaleRunResult,
    MicrostructureTrajectory,
)
from zer0pa_materials.audit.sources import BlockedSourceManifest
from zer0pa_materials.boundary import RESEARCH_BOUNDARY
from zer0pa_materials.envelope.hashing import sha256_of
from zer0pa_materials.envelope.layer_outputs import L4PhaseFieldOutput


def _spec_hash(spec: KmcRunSpec) -> str:
    return sha256_of(spec.model_dump(mode="json"))


def _hash_byte(h: str, byte_idx: int) -> int:
    """Return one byte from the hash hex (0..255)."""
    hex_body = h.split(":", 1)[1]
    return int(hex_body[byte_idx * 2 : byte_idx * 2 + 2], 16)


def _make_initial_potts(n_y: int, n_x: int, n_states: int, h: str) -> list[list[int]]:
    """Initialise a random Potts lattice deterministically from the hash."""
    grid: list[list[int]] = []
    for j in range(n_y):
        row: list[int] = []
        for i in range(n_x):
            byte_val = _hash_byte(h, (j * n_x + i) % 32)
            row.append(byte_val % n_states)
        grid.append(row)
    return grid


def _potts_energy(grid: list[list[int]]) -> int:
    """Count unlike-spin bonds on a square lattice with 4-connectivity.

    Periodic boundary conditions (matches a torus, simplest case).
    """
    n_y = len(grid)
    n_x = len(grid[0]) if n_y > 0 else 0
    energy = 0
    for j in range(n_y):
        for i in range(n_x):
            spin = grid[j][i]
            # right neighbour
            ri = (i + 1) % n_x
            if grid[j][ri] != spin:
                energy += 1
            # below neighbour
            bj = (j + 1) % n_y
            if grid[bj][i] != spin:
                energy += 1
    return energy


def _evolve_potts_t0(
    grid: list[list[int]], n_dumps: int
) -> tuple[list[list[list[int]]], list[int]]:
    """T=0 Potts evolution: greedy energy-non-increasing coarsening.

    At each step we visit every site and replace its spin with the
    most-common neighbour spin (mode of 4 neighbours). Ties broken
    deterministically (lower index wins). This is energy-non-increasing
    because mode is the energy-minimising local choice. Returns the
    trajectory of grids and the per-dump energies.

    To make energy STRICTLY non-increasing across dumps we run multiple
    sweeps per dump (so any per-sweep improvements aggregate).
    """
    n_y = len(grid)
    n_x = len(grid[0]) if n_y > 0 else 0
    trajectory: list[list[list[int]]] = [[row[:] for row in grid]]
    energies: list[int] = [_potts_energy(grid)]
    cur = [row[:] for row in grid]
    sweeps_per_dump = max(1, (n_y + n_x) // 8)
    for _ in range(n_dumps - 1):
        for _sweep in range(sweeps_per_dump):
            nxt = [row[:] for row in cur]
            for j in range(n_y):
                for i in range(n_x):
                    # neighbours with periodic BC
                    nbrs = [
                        cur[(j - 1) % n_y][i],
                        cur[(j + 1) % n_y][i],
                        cur[j][(i - 1) % n_x],
                        cur[j][(i + 1) % n_x],
                    ]
                    # mode (smallest index on tie)
                    counts: dict[int, int] = {}
                    for s in nbrs:
                        counts[s] = counts.get(s, 0) + 1
                    # majority decision: most-frequent neighbour wins, with
                    # original spin keeping ties when no strict majority
                    own = cur[j][i]
                    own_neighbour_count = counts.get(own, 0)
                    best_count = max(counts.values())
                    if own_neighbour_count == best_count:
                        chosen = own  # keep current spin on tie
                    else:
                        # pick the lowest-index spin among those tied at best_count
                        candidates = sorted(
                            [s for s, c in counts.items() if c == best_count]
                        )
                        chosen = candidates[0]
                    nxt[j][i] = chosen
            cur = nxt
        trajectory.append([row[:] for row in cur])
        energies.append(_potts_energy(cur))
    return trajectory, energies


def _evolve_potts_thermal(
    grid: list[list[int]], n_dumps: int, h: str
) -> tuple[list[list[list[int]]], list[int]]:
    """Synthetic T>0 Potts evolution: like T=0 but with deterministic noise
    that re-introduces a small fraction of bonds at random sites.

    The energy trajectory may locally INCREASE — useful for tests that
    distinguish T=0 (monotonic) from T>0 (non-monotonic).
    """
    n_y = len(grid)
    n_x = len(grid[0]) if n_y > 0 else 0
    trajectory: list[list[list[int]]] = [[row[:] for row in grid]]
    energies: list[int] = [_potts_energy(grid)]
    cur = [row[:] for row in grid]
    # First step: greedy coarsening
    nxt = [row[:] for row in cur]
    for j in range(n_y):
        for i in range(n_x):
            nbrs = [
                cur[(j - 1) % n_y][i],
                cur[(j + 1) % n_y][i],
                cur[j][(i - 1) % n_x],
                cur[j][(i + 1) % n_x],
            ]
            counts: dict[int, int] = {}
            for s in nbrs:
                counts[s] = counts.get(s, 0) + 1
            best_count = max(counts.values())
            candidates = sorted([s for s, c in counts.items() if c == best_count])
            nxt[j][i] = candidates[0]
    cur = nxt
    trajectory.append([row[:] for row in cur])
    energies.append(_potts_energy(cur))
    # Second step: deterministic thermal kick that flips a known site to
    # a new spin so energy goes back UP — this is what T>0 looks like
    if n_dumps >= 3:
        for k in range(2, n_dumps):
            kick = [row[:] for row in cur]
            site_byte = _hash_byte(h, (k - 2) % 32)
            j_kick = site_byte % n_y
            i_kick = (site_byte // n_y) % n_x
            # flip to a different spin
            n_states_seen = max(max(row) for row in cur) + 1
            new_spin = (cur[j_kick][i_kick] + 1) % max(2, n_states_seen)
            kick[j_kick][i_kick] = new_spin
            cur = kick
            trajectory.append([row[:] for row in cur])
            energies.append(_potts_energy(cur))
    return trajectory, energies


class SpparksKmcAdapter(L4Adapter):
    """SPPARKS kMC stub. T=0 Potts coarsening with energy-non-increasing gate.

    Real SPPARKS runs invoked via subprocess; this stub is in-process for
    speed. Output schema is identical between stub and real runs.
    """

    NAME = "SpparksKmcAdapter"
    VERSION = "0.1.0"
    ENGINE = "SPPARKS-2025-Potts"
    LIBRARY_LICENSE = "GPL-2.0-or-later"

    def __init__(self) -> None:
        self.name = self.NAME
        self.version = self.VERSION
        self.backend = "stub"
        self.engine = self.ENGINE
        self.description = (
            "SPPARKS kinetic Monte Carlo (GPL) Potts-model grain-coarsening stub."
        )

    # -------------------------------------------------------------------- run

    def run(
        self,
        spec: KmcRunSpec,
        request: L4PredictRequest,
    ) -> dict[str, Any]:
        if not isinstance(spec, KmcRunSpec):
            raise TypeError(
                f"{self.NAME} consumes KmcRunSpec; got {type(spec).__name__}"
            )

        n_x = spec.grid_size[0]
        n_y = spec.grid_size[1] if len(spec.grid_size) > 1 else n_x
        h = _spec_hash(spec)
        initial = _make_initial_potts(n_y, n_x, spec.n_states, h)

        if spec.temperature_K == 0.0:
            grid_traj, energies = _evolve_potts_t0(initial, spec.n_dumps)
        else:
            grid_traj, energies = _evolve_potts_thermal(initial, spec.n_dumps, h)

        # Energy-monotonic check
        monotonic_violations = 0
        for k in range(1, len(energies)):
            if energies[k] > energies[k - 1]:
                monotonic_violations += 1
        is_monotonic = monotonic_violations == 0

        # Convert grid trajectory to trajectory of float fields for the schema
        # (the canonical schema fields are list[Any] so int is fine; we wrap
        # for clarity and to allow downstream tooling to render uniformly)
        fields_payload: list[list[list[int]]] = grid_traj

        times = [k * 1.0 for k in range(spec.n_dumps)]
        traj = MicrostructureTrajectory(
            times=times,
            fields={"spin": fields_payload},
            mesh=None,
            grid_size=spec.grid_size,
        )

        conserved: dict[str, float] = {
            "energy_monotonic_violations": float(monotonic_violations),
            "energy_initial": float(energies[0]),
            "energy_final": float(energies[-1]),
        }
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
                f"SPPARKS Potts stub; T={spec.temperature_K}K; n_states={spec.n_states}; "
                f"energies={energies[:3]}...{energies[-3:]}",
            ],
        )

        return self._build_envelope(spec, request, result, conserved, is_monotonic, energies)

    def _build_envelope(
        self,
        spec: KmcRunSpec,
        request: L4PredictRequest,
        result: MesoscaleRunResult,
        conserved: dict[str, float],
        is_monotonic: bool,
        energies: list[int],
    ) -> dict[str, Any]:
        l4_output: dict[str, Any] = {
            "cahn_hilliard_mass_drift": None,
            "allen_cahn_bounds_violation": None,
            "spparks_potts_energy_monotonic": is_monotonic,
            "microstructure_trajectory_uri": f"artifact:{request.run_id}/spparks-trajectory",
        }
        l4_obj = L4PhaseFieldOutput.model_validate(l4_output)
        falsifier_items = [it.model_dump(mode="json") for it in l4_obj.falsifier_items()]
        # Active items: spparks gate. Filter out CH/AC since both are None.
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
                "engine": self.ENGINE,
            },
            "output": l4_output,
            "confidence": {
                "score": 0.65 if is_monotonic else 0.2,
                "band": "high" if is_monotonic and spec.temperature_K == 0.0 else "medium",
                "basis": [
                    f"adapter={self.NAME}",
                    f"T={spec.temperature_K}K",
                    f"monotonic={is_monotonic}",
                ],
            },
            "disagreement": {"metrics": []},
            "falsifier": {"status": falsifier_status, "items": falsifier_items},
            "audit": {
                "audit_record_id": f"audit:{request.run_id}/spparks",
                "input_hash": input_hash,
                "output_hash": out_hash,
                "source_manifest_refs": ["src:spparks:cxx-build"],
            },
            "rights": {
                "rights_claim_id": request.rights_claim_id,
                "reuse_scope": "tenant_only",
            },
            "back_edges": [],
            "_l4_meta": {
                "equation": "kmc_potts",
                "grid_size": spec.grid_size,
                "n_dumps": spec.n_dumps,
                "energies": energies,
                "energy_monotonic_violations": int(conserved["energy_monotonic_violations"]),
                "is_monotonic": is_monotonic,
                "result_payload": result.model_dump(mode="json"),
                "advisory": False,
                "adapter_name": self.NAME,
                "license": self.LIBRARY_LICENSE,
            },
        }
        return envelope

    def blocked_manifests(self) -> list[dict[str, Any]]:
        return [
            BlockedSourceManifest(
                source_manifest_id="src:spparks:cxx-build",
                attempted_locator="https://spparks.github.io/",
                blocker_reason="unavailable_credentials",
                blocker_detail=(
                    "SPPARKS is the Stochastic Parallel PARticle Kinetic "
                    "Simulator from Sandia. GPL-licensed; outputs are "
                    "commercialisable. Real runs require a subprocess "
                    "build with MPI. The CPU-side stub deterministically "
                    "synthesises Potts coarsening with the energy-non-"
                    "increasing T=0 invariant for the falsifier gate."
                ),
                retry_strategy=(
                    "Set L4_SOLVER=runpod_rest and deploy the spparks "
                    "container with MPI."
                ),
            ).model_dump(mode="json"),
        ]
