"""Quantum layer adapters (PRD §Quantum slot — VQE).

Public surface:

* :class:`PennyLaneVqeSolver` — PennyLane VQE backed by PySCF integrals (try-import or stub).
* :class:`QiskitNatureVqeSolver` — Qiskit Nature VQE (try-import or stub).
* :class:`QuantumProblemDispatcher` — slot router (L1-VQE / L4-QAOA / L7-QAA).
"""

from zer0pa_materials_workbench.adapters.quantum.dispatcher import QuantumProblemDispatcher
from zer0pa_materials_workbench.adapters.quantum.pennylane_vqe import PennyLaneVqeSolver
from zer0pa_materials_workbench.adapters.quantum.qiskit_nature_vqe import QiskitNatureVqeSolver

__all__ = [
    "PennyLaneVqeSolver",
    "QiskitNatureVqeSolver",
    "QuantumProblemDispatcher",
]
