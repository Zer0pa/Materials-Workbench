"""L4 phase field / kMC / neural operator adapters.

L4 is a SOLVER-ENSEMBLE LAYER, not a single phase-field tool (PRD §L4).
PRISMS-PF, MOOSE, MICROSIM, SPPARKS, and the neural-operator surrogate
all emit the same canonical schema declared in :mod:`contracts`.

Public surface:
    PhaseFieldRunSpec        — phase-field run specification
    KmcRunSpec               — kinetic Monte Carlo run specification
    MesoscaleRunResult       — adapter-emitted result envelope payload
    MicrostructureTrajectory — time-series field data structure
    L4Adapter                — abstract base for all L4 adapters
    PrismsPfAdapter          — PRISMS-PF stub adapter (Allen-Cahn / Cahn-Hilliard)
    MoosePhaseFieldAdapter   — MOOSE/MARMOT stub adapter (cross-code disagreement)
    MicrosimGrandPotentialAdapter — MICROSIM grand-potential, GPL-3 SUBPROCESS-ISOLATED
    SpparksKmcAdapter        — SPPARKS kMC Potts-model stub
    NeuralOperatorPhaseFieldAdapter — U-AFNO / DeepONet surrogate, ADVISORY-ONLY
    L4SolverEnsemble         — primary user-facing ensemble; runs PRISMS-PF + MOOSE,
                               computes plug-swap-equivalent disagreement metric

Architecture invariant: every adapter returns the SAME wire-level schema.
Plug-swap from one backend to another changes the backend label and the
numbers, NOT the schema.
"""

from zer0pa_materials_workbench.adapters.l4.base import (
    L4Adapter,
    L4PredictRequest,
)
from zer0pa_materials_workbench.adapters.l4.contracts import (
    KmcRunSpec,
    MesoscaleRunResult,
    MicrostructureTrajectory,
    NeuralOpPredictRequest,
    PhaseFieldEquation,
    PhaseFieldRunSpec,
)
from zer0pa_materials_workbench.adapters.l4.ensemble import L4SolverEnsemble
from zer0pa_materials_workbench.adapters.l4.microsim import MicrosimGrandPotentialAdapter
from zer0pa_materials_workbench.adapters.l4.moose import MoosePhaseFieldAdapter
from zer0pa_materials_workbench.adapters.l4.neural_operator import NeuralOperatorPhaseFieldAdapter
from zer0pa_materials_workbench.adapters.l4.prisms_pf import PrismsPfAdapter
from zer0pa_materials_workbench.adapters.l4.spparks import SpparksKmcAdapter

__all__ = [
    # Contracts
    "PhaseFieldRunSpec",
    "KmcRunSpec",
    "MesoscaleRunResult",
    "MicrostructureTrajectory",
    "NeuralOpPredictRequest",
    "PhaseFieldEquation",
    # Base
    "L4Adapter",
    "L4PredictRequest",
    # Adapters
    "PrismsPfAdapter",
    "MoosePhaseFieldAdapter",
    "MicrosimGrandPotentialAdapter",
    "SpparksKmcAdapter",
    "NeuralOperatorPhaseFieldAdapter",
    "L4SolverEnsemble",
]
