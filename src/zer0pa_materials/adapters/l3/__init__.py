"""L3 CALPHAD adapters — sovereign pycalphad/ESPEI build (PRD §L3).

Public surface:

* :class:`L3CalphadAdapter` — abstract base for every L3 adapter.
* :class:`L3CalphadRequest` — caller-supplied run context.
* :class:`PyCalphadEquilibriumAdapter` — open-path pycalphad equilibrium calc
  (sovereign default; tries real pycalphad, falls back to deterministic stub).
* :class:`EspeiBayesianFitAdapter` — ESPEI Bayesian MCMC TDB-fit (sovereign
  default; tries real ESPEI, falls back to a calibrated synthetic posterior).
* :class:`PhaseForgePlusMlipPriorAdapter` — MLIP→CALPHAD prior bridge stub;
  default-blocked behind a license-verification gate.
* :class:`ThermoCalcTdbReadOnlyAdapter` — QUARANTINE adapter for commercial
  Thermo-Calc TDBs; default-blocked, returns hash + metadata only.
* :class:`SovereignCalphadPipeline` — primary user-facing adapter for novel
  quaternary systems: DFT/MLIP → PhaseForgePlus → ESPEI → pycalphad.
* :exc:`CommercialTdbQuarantineError` — raised when quarantine policy is
  violated.

License positions (PRD §L3, Brief #2 Gap C):
    pycalphad         MIT (open path A — sovereign default)
    ESPEI             MIT (open path A — sovereign default)
    PhaseForgePlus    MIT (open path A — Brief #2 declares; license must be
                      verified before authority use)
    Thermo-Calc TDBs  Proprietary; commercial; per-customer license required;
                      NEVER committed, copied to fixtures, or used as training
                      corpus.
"""

from zer0pa_materials.adapters.l3.base import (
    L3CalphadAdapter,
    L3CalphadRequest,
    CommercialTdbQuarantineError,
)
from zer0pa_materials.adapters.l3.pycalphad_equilibrium import (
    PyCalphadEquilibriumAdapter,
    PYCALPHAD_AVAILABLE,
)
from zer0pa_materials.adapters.l3.espei_fit import (
    EspeiBayesianFitAdapter,
    ESPEI_AVAILABLE,
)
from zer0pa_materials.adapters.l3.phaseforgeplus_prior import (
    PhaseForgePlusMlipPriorAdapter,
)
from zer0pa_materials.adapters.l3.thermocalc_quarantine import (
    ThermoCalcTdbReadOnlyAdapter,
)
from zer0pa_materials.adapters.l3.sovereign_pipeline import (
    SovereignCalphadPipeline,
)

__all__ = [
    "L3CalphadAdapter",
    "L3CalphadRequest",
    "CommercialTdbQuarantineError",
    "PyCalphadEquilibriumAdapter",
    "PYCALPHAD_AVAILABLE",
    "EspeiBayesianFitAdapter",
    "ESPEI_AVAILABLE",
    "PhaseForgePlusMlipPriorAdapter",
    "ThermoCalcTdbReadOnlyAdapter",
    "SovereignCalphadPipeline",
]
