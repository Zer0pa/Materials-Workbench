"""L2 MLIP ensemble adapters — DPA-3 + MACE + UMA (gated) + committees.

Public surface:

* :class:`DeepmdDpaCalculatorAdapter` — DPA-3.1-3M stub (LAMBench #1).
* :class:`MaceMpCalculatorAdapter` — MACE-MPA-0 stub (LAMBench #8).
* :class:`UmaCalculatorAdapter` — Meta UMA; default-BLOCKED until license verified.
* :class:`MaceMultiheadCommitteeRunner` — MACE multi-head committee for uncertainty.
* :class:`DpaCommitteeRunner` — DPA committee equivalent.
* :class:`SevenNetCalculatorAdapter` — third-tier optional MLIP stub.
* :class:`L2EnsembleRunner` — primary user-facing adapter (DPA+MACE mandatory).
* :exc:`LicenseGateError` — raised when UMA called without enabling.
"""

from zer0pa_materials.adapters.l2.base import L2MlipAdapter, L2PredictRequest
from zer0pa_materials.adapters.l2.deepmd_dpa import DeepmdDpaCalculatorAdapter
from zer0pa_materials.adapters.l2.dpa_committee import DpaCommitteeRunner
from zer0pa_materials.adapters.l2.ensemble import L2EnsembleRunner
from zer0pa_materials.adapters.l2.mace_committee import MaceMultiheadCommitteeRunner
from zer0pa_materials.adapters.l2.mace_mp import MaceMpCalculatorAdapter
from zer0pa_materials.adapters.l2.sevennet import SevenNetCalculatorAdapter
from zer0pa_materials.adapters.l2.uma import LicenseGateError, UmaCalculatorAdapter

__all__ = [
    "L2MlipAdapter",
    "L2PredictRequest",
    "DeepmdDpaCalculatorAdapter",
    "MaceMpCalculatorAdapter",
    "UmaCalculatorAdapter",
    "LicenseGateError",
    "MaceMultiheadCommitteeRunner",
    "DpaCommitteeRunner",
    "L2EnsembleRunner",
    "SevenNetCalculatorAdapter",
]
