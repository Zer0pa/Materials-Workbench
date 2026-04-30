"""L1 DFT layer adapters.

Public surface:

* :class:`L1DftAdapter` — abstract base; ``submit_job``, ``parse_output``, ``validate_convergence``.
* :class:`PyScfMolecularSolver` — local-CPU RHF/MP2/FCI (pyscf try-import or deterministic stub).
* :class:`QuantumEspressoAiiDASolver` — dry-run + parse-only stub for QE.
* :class:`Cp2kAiiDASolver` — dry-run + parse-only stub for CP2K.
* :class:`AbinitAiiDASolver` — dry-run + parse-only stub for ABINIT.
* :func:`get_l1_adapter` — backend selector via ``MATERIALS_L1_BACKEND`` env-var.
"""

from zer0pa_materials.adapters.l1.base import L1DftAdapter, L1JobParams
from zer0pa_materials.adapters.l1.pyscf import PyScfMolecularSolver
from zer0pa_materials.adapters.l1.qe_aiida import QuantumEspressoAiiDASolver
from zer0pa_materials.adapters.l1.cp2k_aiida import Cp2kAiiDASolver
from zer0pa_materials.adapters.l1.abinit_aiida import AbinitAiiDASolver

__all__ = [
    "L1DftAdapter",
    "L1JobParams",
    "PyScfMolecularSolver",
    "QuantumEspressoAiiDASolver",
    "Cp2kAiiDASolver",
    "AbinitAiiDASolver",
    "get_l1_adapter",
]


def get_l1_adapter(backend: str | None = None) -> "L1DftAdapter":
    """Return the L1 adapter selected by *backend* or ``MATERIALS_L1_BACKEND``.

    Backend tokens:
        ``pyscf``  — :class:`PyScfMolecularSolver` (default; runs locally).
        ``qe``     — :class:`QuantumEspressoAiiDASolver` (dry-run / parse-only).
        ``cp2k``   — :class:`Cp2kAiiDASolver` (dry-run / parse-only).
        ``abinit`` — :class:`AbinitAiiDASolver` (dry-run / parse-only).
        ``runpod_rest`` — resolves to ``qe`` (real-run path parked).
    """
    import os

    chosen = (backend or os.environ.get("MATERIALS_L1_BACKEND", "pyscf")).lower()
    if chosen in ("pyscf", "local_cpu"):
        return PyScfMolecularSolver()
    if chosen in ("qe", "qe_aiida", "runpod_rest"):
        return QuantumEspressoAiiDASolver()
    if chosen in ("cp2k", "cp2k_aiida"):
        return Cp2kAiiDASolver()
    if chosen in ("abinit", "abinit_aiida"):
        return AbinitAiiDASolver()
    raise ValueError(
        f"Unknown MATERIALS_L1_BACKEND={chosen!r}. "
        "Valid choices: pyscf, qe, cp2k, abinit, runpod_rest."
    )
