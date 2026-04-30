"""Canonical L4 contracts: PhaseFieldRunSpec, KmcRunSpec, MesoscaleRunResult.

PRD §L4 (verbatim): "L4 is a solver-ensemble layer, not a single phase-field
tool... Required canonical interface: ``PhaseFieldRunSpec``, ``KmcRunSpec``,
``MesoscaleRunResult``, ``MicrostructureTrajectory``... PRISMS-PF, MOOSE,
MICROSIM, SPPARKS, and neural-operator surrogate must emit the same schema."

Every L4 backend MUST consume one of these spec types and emit a
``MesoscaleRunResult``. Plug-swap from PRISMS-PF to MOOSE (or any other
backend) changes the values inside the result, NOT the schema.

Design decisions
----------------

1. **One spec per modality, not one spec per backend.** ``PhaseFieldRunSpec``
   covers Allen-Cahn / Cahn-Hilliard / multi-phase-field (MPF). ``KmcRunSpec``
   covers SPPARKS-style lattice kMC. The neural-operator surrogate consumes
   ``PhaseFieldRunSpec`` (it predicts the same thing PRISMS-PF would).

2. **Trajectory is field-major.** A 32×32 grid × 11 dump times yields an
   11×32×32 array; for a multi-phase system we add a leading variable axis.
   The schema stores fields as nested lists (JSON-serialisable, no numpy
   round-trip required for the contract).

3. **Conserved quantities are first-class.** Cahn-Hilliard mass conservation
   and Allen-Cahn order-parameter bounds are the falsifier targets. We surface
   them as ``conserved_quantities: dict[str, float]`` instead of leaving the
   gate to mine the trajectory.

4. **Advisory flag for neural operators.** ``MesoscaleRunResult.advisory``
   is mandatory and defaults to ``False`` for classical solvers. Neural
   operator adapters MUST set ``advisory=True`` until they pass both the
   persistence-baseline AND <10% relative QoI gates.

5. **Run ID separate from candidate ID.** ``run_id`` is the URN of this
   specific compute job, ``candidate_id`` is the scientific candidate the
   run is studying. Multiple runs on the same candidate share candidate_id.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ---------------------------------------------------------------------------
# Equation-mode and solver-mode literals
# ---------------------------------------------------------------------------

PhaseFieldEquation = Literal[
    "allen_cahn",      # non-conserved order parameter; bounds gate
    "cahn_hilliard",   # conserved order parameter; mass-drift gate
    "mpf",             # multi-phase-field (KKS / KKS+CALPHAD coupling)
    "grand_potential", # MICROSIM-style grand-potential formulation
]

KmcLatticeType = Literal["square", "triangular", "cubic", "fcc", "bcc"]
KmcEnergyModel = Literal["potts", "ising", "binary_alloy", "custom"]


# ---------------------------------------------------------------------------
# Domain / mesh / materials sub-blocks
# ---------------------------------------------------------------------------


class PhaseFieldDomain(BaseModel):
    """Spatial domain of a phase-field run (rectangular box for now)."""

    model_config = ConfigDict(extra="forbid")

    dimension: Literal[2, 3] = Field(..., description="Spatial dimension.")
    extents: list[float] = Field(
        ..., min_length=2, max_length=3, description="Box size [Lx, Ly, Lz?] in length units."
    )
    units: Literal["m", "nm", "um", "Å"] = Field(default="nm")
    periodic: tuple[bool, bool, bool] = Field(
        default=(True, True, True),
        description="Per-axis periodicity. The third element is unused if dimension=2.",
    )


class PhaseFieldMesh(BaseModel):
    """Cartesian mesh on the domain. Tiny fixtures use 32x32 by default."""

    model_config = ConfigDict(extra="forbid")

    nodes: list[int] = Field(
        ..., min_length=2, max_length=3, description="Node count per axis."
    )
    refinement_level: int = Field(
        default=0, ge=0, description="AMR refinement level (0 = uniform mesh)."
    )

    @field_validator("nodes")
    @classmethod
    def _all_positive(cls, v: list[int]) -> list[int]:
        if any(n <= 0 for n in v):
            raise ValueError(f"all node counts must be positive; got {v}")
        return v


class PhaseFieldMaterial(BaseModel):
    """One phase / material entry in the run spec."""

    model_config = ConfigDict(extra="forbid")

    phase_name: str = Field(..., min_length=1)
    initial_fraction: float = Field(..., ge=0.0, le=1.0)
    interface_energy_J_per_m2: float | None = Field(
        default=None, ge=0.0, description="Interface energy in J/m²."
    )
    mobility: float | None = Field(
        default=None, ge=0.0, description="Order-parameter mobility (model-specific units)."
    )


# ---------------------------------------------------------------------------
# PhaseFieldRunSpec — the primary L4 spec
# ---------------------------------------------------------------------------


class PhaseFieldRunSpec(BaseModel):
    """Phase-field run specification consumed by every classical L4 adapter
    and the neural-operator surrogate.

    Every backend (PRISMS-PF, MOOSE, MICROSIM, neural operator) reads this
    same shape. Plug-swap one for another changes the backend, not the spec.
    """

    model_config = ConfigDict(extra="forbid")

    equation: PhaseFieldEquation = Field(..., description="Governing PDE.")
    domain: PhaseFieldDomain
    mesh: PhaseFieldMesh
    materials: list[PhaseFieldMaterial] = Field(
        ..., min_length=1, description="One entry per phase."
    )
    time_steps: int = Field(..., ge=1, description="Number of time steps to integrate.")
    dt: float = Field(..., gt=0.0, description="Time step size in time units.")
    time_units: Literal["s", "ms", "us", "ns", "ps", "fs"] = Field(default="s")
    n_dumps: int = Field(
        default=11,
        ge=2,
        description="Number of trajectory snapshots; first dump is the initial condition.",
    )
    initial_condition: Literal["uniform", "spinodal_noise", "single_seed", "fixture_default"] = (
        Field(default="fixture_default", description="How to initialise the field.")
    )
    initial_seed: int = Field(
        default=42, description="RNG seed for spinodal/random initial conditions."
    )
    temperature_K: float | None = Field(
        default=None, ge=0.0, description="Optional temperature (K) for CALPHAD-coupled runs."
    )
    extra: dict[str, Any] = Field(
        default_factory=dict,
        description="Adapter-specific opaque pass-through (e.g. PRISMS-PF flag overrides).",
    )


# ---------------------------------------------------------------------------
# KmcRunSpec — SPPARKS-style kinetic Monte Carlo
# ---------------------------------------------------------------------------


class KmcRunSpec(BaseModel):
    """Kinetic Monte Carlo run spec consumed by SpparksKmcAdapter."""

    model_config = ConfigDict(extra="forbid")

    lattice: KmcLatticeType = Field(default="square")
    grid_size: list[int] = Field(
        ...,
        min_length=2,
        max_length=3,
        description="Lattice site counts per axis.",
    )
    energy_model: KmcEnergyModel = Field(default="potts")
    n_states: int = Field(
        default=10,
        ge=2,
        description="Number of Potts states / spin labels (q in q-state Potts).",
    )
    n_steps: int = Field(..., ge=1, description="Number of kMC steps to run.")
    n_dumps: int = Field(default=11, ge=2)
    temperature_K: float = Field(
        ...,
        ge=0.0,
        description=(
            "Lattice temperature in Kelvin. T=0 is the Potts-energy-monotonic "
            "falsifier configuration (energy non-increasing across dumps)."
        ),
    )
    initial_seed: int = Field(default=42)
    extra: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Trajectory and result
# ---------------------------------------------------------------------------


class MicrostructureTrajectory(BaseModel):
    """Time-series of microstructure fields at dump times.

    The ``fields`` member is a per-variable dict whose values are nested
    lists [n_dumps, ...spatial...]. This keeps the contract JSON-friendly
    without a numpy hard dependency.

    For Allen-Cahn / Cahn-Hilliard there is one variable named ``phi``.
    For multi-phase-field there are ``phi_<phase_name>`` keys.
    For SPPARKS Potts the field is named ``spin``.
    """

    model_config = ConfigDict(extra="forbid")

    times: list[float] = Field(..., min_length=2, description="Dump times in run time units.")
    fields: dict[str, list[Any]] = Field(
        ..., description="Variable name -> [n_dumps, ny, nx[, nz]] nested list."
    )
    mesh: PhaseFieldMesh | None = Field(
        default=None, description="Mesh used. None for kMC (lattice-based)."
    )
    grid_size: list[int] | None = Field(
        default=None, description="Lattice grid for kMC; None for phase field."
    )


class MesoscaleRunResult(BaseModel):
    """Canonical L4 result. Every backend emits this shape.

    The ``advisory`` flag is mandatory: classical solvers default to False;
    neural-operator surrogate MUST set True until both gates pass.
    """

    model_config = ConfigDict(extra="forbid")

    spec: PhaseFieldRunSpec | KmcRunSpec
    trajectory: MicrostructureTrajectory
    conserved_quantities: dict[str, float] = Field(
        default_factory=dict,
        description=(
            "Quantities the gates check. "
            "For Cahn-Hilliard: 'mass_drift_relative'. "
            "For Allen-Cahn:    'bounds_violation_max'. "
            "For SPPARKS T=0:   'energy_monotonic_violations'. "
            "For neural op:     'qoi_relative_error', 'beats_persistence_baseline'."
        ),
    )
    run_id: str = Field(..., description="URN starting with 'run:'.")
    backend: Literal["stub", "local_cpu", "runpod_mock", "runpod_rest"]
    advisory: bool = Field(
        default=False,
        description=(
            "True iff this result must NOT be promoted directly. Neural "
            "operator results are advisory until they beat the persistence "
            "baseline AND have <10% relative QoI error."
        ),
    )
    adapter_name: str = Field(..., min_length=1)
    adapter_version: str = Field(..., min_length=1)
    notes: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Neural operator predict request (REST surface)
# ---------------------------------------------------------------------------


class NeuralOpPredictRequest(BaseModel):
    """REST-surface request to ``POST /v1/l4/neural-op/predict``.

    The neural operator predicts a microstructure trajectory given the same
    spec a classical solver consumes. The advisory state is reported in the
    envelope; this request does not toggle it.
    """

    model_config = ConfigDict(extra="forbid")

    run_id: str
    candidate_id: str
    campaign_id: str
    rights_claim_id: str
    spec: PhaseFieldRunSpec
    held_out_classical_qoi: float | None = Field(
        default=None,
        description=(
            "Optional held-out classical-trajectory QoI (e.g. final domain-wall "
            "length or final phase fraction) used to compute the relative-QoI "
            "gate. If omitted, the gate is BLOCKED (cannot pass)."
        ),
    )
    persistence_baseline_qoi: float | None = Field(
        default=None,
        description="Optional QoI from the persistence baseline.",
    )
