"""Ionic Transport layer adapters (PRD §Ionic Transport, §Layer Contracts).

Public surface
--------------

* :class:`IonicTransportAdapter` — abstract base for every ionic adapter.
* :class:`IonicJobParams` — canonical input struct.
* :class:`NebMigrationBarrierAdapter` — NEB / equivalent path-search migration
  barrier (eV) adapter.
* :class:`MlipMdDiffusionAdapter` — MLIP-MD trajectory → MSD → D
  (cm²/s) → Nernst-Einstein conductivity (S/cm).
* :class:`AimdDiffusionAdapter` — same shape, AIMD seed (deliberately offset
  from MLIP-MD to support cross-method disagreement falsifier).
* :class:`ArrheniusFitAdapter` — fit ln(σ·T) vs 1/T for activation
  energy (eV) and uncertainty.
* :class:`ElectrochemicalWindowAdapter` — oxidative / reductive stability
  window vs Li/Li+.
* :class:`InterfaceStabilityAdapter` — Li-metal / cathode interface
  classification (PRD §Ionic Transport).
* :func:`nernst_einstein_conductivity` — testable formula.
* BlockedSourceManifest entries — tools whose real backends are parked
  behind L1 source-manifest gates.
"""

from zer0pa_materials.adapters.ionic.aimd import (
    AIMD_BLOCKED_MANIFEST,
    AimdDiffusionAdapter,
)
from zer0pa_materials.adapters.ionic.arrhenius import (
    ArrheniusFitAdapter,
    ArrheniusFitParams,
    ArrheniusFitResult,
)
from zer0pa_materials.adapters.ionic.base import (
    IonicJobParams,
    IonicTransportAdapter,
)
from zer0pa_materials.adapters.ionic.electrochemical_window import (
    ELECTROCHEMICAL_WINDOW_BLOCKED_MANIFEST,
    ElectrochemicalWindowAdapter,
)
from zer0pa_materials.adapters.ionic.interface_stability import (
    INTERFACE_STABILITY_BLOCKED_MANIFEST,
    InterfaceStabilityAdapter,
)
from zer0pa_materials.adapters.ionic.mlip_md import (
    MLIP_MD_BLOCKED_MANIFEST,
    MlipMdDiffusionAdapter,
)
from zer0pa_materials.adapters.ionic.neb import (
    NEB_BLOCKED_MANIFEST,
    NebMigrationBarrierAdapter,
)
from zer0pa_materials.adapters.ionic.nernst_einstein import (
    BOLTZMANN_J_PER_K,
    ELEMENTARY_CHARGE_C,
    HavenRatio,
    nernst_einstein_conductivity,
)

__all__ = [
    # base
    "IonicTransportAdapter",
    "IonicJobParams",
    # adapters
    "NebMigrationBarrierAdapter",
    "MlipMdDiffusionAdapter",
    "AimdDiffusionAdapter",
    "ArrheniusFitAdapter",
    "ArrheniusFitParams",
    "ArrheniusFitResult",
    "ElectrochemicalWindowAdapter",
    "InterfaceStabilityAdapter",
    # nernst-einstein
    "nernst_einstein_conductivity",
    "ELEMENTARY_CHARGE_C",
    "BOLTZMANN_J_PER_K",
    "HavenRatio",
    # blocked manifests
    "NEB_BLOCKED_MANIFEST",
    "MLIP_MD_BLOCKED_MANIFEST",
    "AIMD_BLOCKED_MANIFEST",
    "ELECTROCHEMICAL_WINDOW_BLOCKED_MANIFEST",
    "INTERFACE_STABILITY_BLOCKED_MANIFEST",
]
