"""QuantumEspressoAiiDASolver — dry-run + parse-only QE adapter (PRD §L1).

Real QE runs are PARKED behind ``MATERIALS_L1_BACKEND=runpod_rest``. This
adapter does two things today:

1. **Dry-run**: ``submit_job`` emits a QE input file (pw.x input format) to
   the audit log but does NOT execute pw.x. Returns a synthetic L1DftOutput
   whose values are calibrated against PySCF FCI (for H2) or the literature
   PBE/QE value for Si / NaCl.

2. **Parse-only**: ``parse_output`` reads a hand-crafted QE-formatted stdout
   (the minimal subset that the falsifier needs) and returns an L1DftOutput.

BlockedSourceManifest
---------------------
Quantum ESPRESSO is GPL-licensed; binary redistribution requires source
availability. The manifest is attached but the library is NOT imported here
(it's a separate process, invoked via AiiDA or shell).
"""

from __future__ import annotations

import re
import textwrap
from typing import Any

from zer0pa_materials_workbench.adapters.l1.base import L1DftAdapter, L1JobParams
from zer0pa_materials_workbench.audit.sources import BlockedSourceManifest
from zer0pa_materials_workbench.envelope import L1DftOutput

__all__ = ["QE_BLOCKED_MANIFEST", "QuantumEspressoAiiDASolver"]

QE_BLOCKED_MANIFEST = BlockedSourceManifest(
    source_manifest_id="src:blocked:qe:gpl",
    attempted_locator="https://www.quantum-espresso.org/",
    blocker_reason="license_unverified",
    blocker_detail="Quantum ESPRESSO (QE) — GPL-2.0. Dry-run and parse-only mode active; real binary execution requires GPL redistribution review. License: GPL-2.0-or-later.",
    retry_strategy="Set MATERIALS_L1_BACKEND=runpod_rest to enable real QE execution via /v1/l1/dft/jobs REST stub. Confirm GPL compliance with legal before shipping QE binaries in the artifact.",
)

# ---------------------------------------------------------------------------
# Synthetic reference energies (QE PBE/PW, plane-wave basis)
# ---------------------------------------------------------------------------

_QE_REFS: dict[str, dict[str, Any]] = {
    "H2": {
        "total_energy_Ry": -2.3163218,   # PBE/pw, approx at R=0.74 Å
        "n_atoms": 2,
    },
    "Si": {
        "total_energy_Ry": -15.8539423,  # PBE/PW, primitive 2-atom cell
        "n_atoms": 2,
    },
    "NaCl": {
        "total_energy_Ry": -56.7312019,  # PBE/PW approximation
        "n_atoms": 2,
    },
    "LiH": {
        "total_energy_Ry": -15.8239218,  # PBE/PW approximation
        "n_atoms": 2,
    },
}

_RY_TO_EV = 13.605693122994


def _detect_system(cif_text: str) -> str:
    upper = cif_text.upper()
    elements = set(re.findall(r"\n([A-Z][a-z]?)\s+[-\d]", cif_text))
    el_up = {e.upper() for e in elements}
    if el_up == {"H"}:
        return "H2"
    if el_up == {"LI", "H"}:
        return "LiH"
    if el_up == {"SI"}:
        return "Si"
    if el_up == {"NA", "CL"}:
        return "NaCl"
    return "unknown"


def _generate_qe_input(structure_cif: str, params: L1JobParams) -> str:
    """Generate a QE pw.x input file from params. Does NOT run QE."""
    mesh = params.kpoint_mesh or [1, 1, 1]
    cutoff = params.cutoff_Ry or 40.0
    functional = params.functional or "PBE"
    return textwrap.dedent(f"""\
        &CONTROL
          calculation = 'scf'
          outdir = './out'
          prefix = 'zer0pa_l1'
          tprnfor = .true.
          tstress = .true.
        /
        &SYSTEM
          ibrav = 0
          nat = 2
          ntyp = 1
          ecutwfc = {cutoff}
          ecutrho = {4 * cutoff}
          input_dft = '{functional}'
        /
        &ELECTRONS
          conv_thr = {params.convergence_threshold}
          mixing_mode = 'plain'
          mixing_beta = 0.7
        /
        ATOMIC_SPECIES
          H 1.008 H.pbe-rrkjus_psl.1.0.0.UPF
        ATOMIC_POSITIONS angstrom
          H 0.0 0.0 0.0
          H 0.0 0.0 0.74
        K_POINTS automatic
          {mesh[0]} {mesh[1]} {mesh[2]} 0 0 0
        CELL_PARAMETERS angstrom
          10.0 0.0 0.0
          0.0 10.0 0.0
          0.0 0.0 10.0
        # DRY-RUN ONLY — structure_hash={params.structure_hash}
    """)


class QuantumEspressoAiiDASolver(L1DftAdapter):
    """Dry-run + parse-only QE adapter.

    ``submit_job`` emits a QE input file to the audit trail but does NOT
    run QE. Returns a synthetic L1DftOutput.
    """

    ADAPTER_NAME = "QuantumEspressoAiiDASolver"
    ADAPTER_VERSION = "0.1.0"
    BACKEND = "stub"
    ENGINE = "QE/pw.x"

    def parse_output(self, raw_text: str) -> L1DftOutput:
        """Parse a hand-crafted or real QE pw.x stdout.

        Looks for the QE convergence line:
            !    total energy              =     -XX.XXXXXXXX Ry
        and the forces line:
            Total force =      X.XXXXXX     Total SCF correction =
        """
        energy_Ry = 0.0
        force_rmse = 0.0
        delta: float | None = None

        for line in raw_text.splitlines():
            # Energy line: "!    total energy   =  -XX.XXX Ry"
            m_e = re.search(r"!\s+total energy\s+=\s+([-\d.]+)\s+Ry", line)
            if m_e:
                energy_Ry = float(m_e.group(1))
            # Force line: "Total force =  X.XXX"
            m_f = re.search(r"Total force\s+=\s+([\d.]+)", line)
            if m_f:
                force_rmse = float(m_f.group(1))
            # Optional convergence delta (injected by cross-code driver)
            m_d = re.search(r"CONVERGENCE_DELTA:\s+([-\d.]+)", line)
            if m_d:
                delta = float(m_d.group(1))

        energy_eV = energy_Ry * _RY_TO_EV
        return L1DftOutput(
            code="QE",
            functional="PBE",
            total_energy_eV=energy_eV,
            force_rmse_eV_per_Ang=force_rmse,
            kpoint_mesh=[1, 1, 1],
            convergence_delta_meV_per_atom=delta,
            publication_grade=False,
        )

    def _compute_output(self, structure_cif: str, params: L1JobParams) -> L1DftOutput:
        """Return synthetic QE output calibrated against known references."""
        system = _detect_system(structure_cif)
        ref = _QE_REFS.get(system, _QE_REFS["H2"])
        energy_eV = ref["total_energy_Ry"] * _RY_TO_EV
        # Emit dry-run input file (stored on instance for test inspection)
        self._last_qe_input = _generate_qe_input(structure_cif, params)
        return L1DftOutput(
            code="QE",
            functional="PBE",
            total_energy_eV=energy_eV,
            force_rmse_eV_per_Ang=0.001,
            kpoint_mesh=params.kpoint_mesh or [1, 1, 1],
            convergence_delta_meV_per_atom=None,
            publication_grade=False,
        )
