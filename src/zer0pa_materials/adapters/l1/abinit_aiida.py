"""AbinitAiiDASolver — dry-run + parse-only ABINIT adapter (PRD §L1).

Real ABINIT runs are PARKED. This adapter:
1. Emits an ABINIT input file in dry-run mode.
2. Parses a hand-crafted / real ABINIT output to produce L1DftOutput.

BlockedSourceManifest: ABINIT is GPL-3+.
"""

from __future__ import annotations

import re
import textwrap

from zer0pa_materials.adapters.l1.base import L1DftAdapter, L1JobParams
from zer0pa_materials.audit.sources import BlockedSourceManifest
from zer0pa_materials.envelope import L1DftOutput

__all__ = ["AbinitAiiDASolver", "ABINIT_BLOCKED_MANIFEST"]

ABINIT_BLOCKED_MANIFEST = BlockedSourceManifest(
    source_manifest_id="src:blocked:abinit:gpl",
    attempted_locator="https://www.abinit.org/",
    blocker_reason="license_unverified",
    blocker_detail="ABINIT — GPL-3.0-or-later. Dry-run and parse-only mode active; real binary execution requires GPL redistribution review.",
    retry_strategy="Set MATERIALS_L1_BACKEND=abinit and deploy runpod_rest backend to enable real ABINIT. Confirm GPL-3.0 compliance before shipping binaries.",
)

_HA_TO_EV = 27.211386245988  # Hartree → eV


def _generate_abinit_input(structure_cif: str, params: L1JobParams) -> str:
    """Generate a minimal ABINIT input file. Does NOT run ABINIT."""
    cutoff = params.cutoff_Ry or 30.0  # ABINIT ecut in Hartree
    mesh = params.kpoint_mesh or [1, 1, 1]
    return textwrap.dedent(f"""\
        # ABINIT input — DRY-RUN — structure_hash={params.structure_hash}
        ndtset 1
        #
        # System
        natom 2
        ntypat 1
        typat 1 1
        znucl 1
        xcart  0.0  0.0  0.0
               0.0  0.0  1.3984  # 0.74 Ang in Bohr
        acell 18.897 18.897 18.897  # 10 Ang cubic box
        #
        # SCF
        ecut {cutoff}
        ngkpt {mesh[0]} {mesh[1]} {mesh[2]}
        nshiftk 1
        shiftk 0.0 0.0 0.0
        nstep {params.max_scf_cycles}
        toldfe {params.convergence_threshold}
        #
        # Functional
        ixc 11  # GGA-PBE
        #
        pspdir './psps'
        pseudos 'H.psp8'
    """)


class AbinitAiiDASolver(L1DftAdapter):
    """Dry-run + parse-only ABINIT adapter."""

    ADAPTER_NAME = "AbinitAiiDASolver"
    ADAPTER_VERSION = "0.1.0"
    BACKEND = "stub"
    ENGINE = "ABINIT"

    def parse_output(self, raw_text: str) -> L1DftOutput:
        """Parse ABINIT output. Looks for 'etotal' energy line."""
        energy_Ha = 0.0
        force_rmse = 0.0
        delta: float | None = None

        for line in raw_text.splitlines():
            # "  etotal    -1.1637291  Ha"  or "etotal   -1.1637E+00 Ha"
            m_e = re.search(r"^\s*etotal\s+([-\d.E+\-]+)", line, re.IGNORECASE)
            if m_e:
                energy_Ha = float(m_e.group(1))
            # "  fcart   X.XXX  X.XXX  X.XXX"  — ABINIT force array (take norm)
            m_f = re.search(r"^\s*fcart\s+([-\d.E+\-]+)\s+([-\d.E+\-]+)\s+([-\d.E+\-]+)", line)
            if m_f:
                import math
                fx, fy, fz = float(m_f.group(1)), float(m_f.group(2)), float(m_f.group(3))
                force_rmse = max(force_rmse, math.sqrt(fx**2 + fy**2 + fz**2))
            m_d = re.search(r"CONVERGENCE_DELTA:\s+([-\d.]+)", line)
            if m_d:
                delta = float(m_d.group(1))

        energy_eV = energy_Ha * _HA_TO_EV
        return L1DftOutput(
            code="ABINIT",
            functional="PBE",
            total_energy_eV=energy_eV,
            force_rmse_eV_per_Ang=force_rmse,
            kpoint_mesh=[1, 1, 1],
            convergence_delta_meV_per_atom=delta,
            publication_grade=False,
        )

    def _compute_output(self, structure_cif: str, params: L1JobParams) -> L1DftOutput:
        """Return synthetic ABINIT output; emit dry-run input file."""
        self._last_abinit_input = _generate_abinit_input(structure_cif, params)
        energy_eV = -31.58  # slightly different from QE/CP2K for disagreement tests
        return L1DftOutput(
            code="ABINIT",
            functional="PBE",
            total_energy_eV=energy_eV,
            force_rmse_eV_per_Ang=0.0018,
            kpoint_mesh=params.kpoint_mesh or [1, 1, 1],
            convergence_delta_meV_per_atom=None,
            publication_grade=False,
        )
