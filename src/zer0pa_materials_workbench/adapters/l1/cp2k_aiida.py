"""Cp2kAiiDASolver — dry-run + parse-only CP2K adapter (PRD §L1).

Real CP2K runs are PARKED. This adapter:
1. Emits a CP2K input file in dry-run mode.
2. Parses a hand-crafted / real CP2K output to produce L1DftOutput.

BlockedSourceManifest: CP2K is GPL-2+.
"""

from __future__ import annotations

import re
import textwrap

from zer0pa_materials_workbench.adapters.l1.base import L1DftAdapter, L1JobParams
from zer0pa_materials_workbench.audit.sources import BlockedSourceManifest
from zer0pa_materials_workbench.envelope import L1DftOutput

__all__ = ["CP2K_BLOCKED_MANIFEST", "Cp2kAiiDASolver"]

CP2K_BLOCKED_MANIFEST = BlockedSourceManifest(
    source_manifest_id="src:blocked:cp2k:gpl",
    attempted_locator="https://www.cp2k.org/",
    blocker_reason="license_unverified",
    blocker_detail="CP2K — GPL-2.0-or-later. Dry-run and parse-only mode active; real binary execution requires GPL redistribution review.",
    retry_strategy="Set MATERIALS_L1_BACKEND=cp2k and deploy runpod_rest backend to enable real CP2K. Confirm GPL compliance before shipping CP2K binaries.",
)

_AU_TO_EV = 27.211386245988  # Hartree → eV


def _generate_cp2k_input(structure_cif: str, params: L1JobParams) -> str:
    """Generate a CP2K input file. Does NOT run CP2K."""
    functional = params.functional or "PBE"
    cutoff = params.cutoff_Ry or 300  # CP2K uses Ry for plane-wave cutoff
    return textwrap.dedent(f"""\
        &GLOBAL
          PROJECT zer0pa_l1
          RUN_TYPE ENERGY_FORCE
          PRINT_LEVEL MEDIUM
        &END GLOBAL
        &FORCE_EVAL
          METHOD Quickstep
          &DFT
            BASIS_SET_FILE_NAME BASIS_MOLOPT
            POTENTIAL_FILE_NAME GTH_POTENTIALS
            &QS
              EPS_DEFAULT 1.0E-12
            &END QS
            &MGRID
              NGRIDS 4
              CUTOFF {cutoff}
              REL_CUTOFF 60
            &END MGRID
            &XC
              &XC_FUNCTIONAL {functional}
              &END XC_FUNCTIONAL
            &END XC
            &SCF
              MAX_SCF {params.max_scf_cycles}
              EPS_SCF {params.convergence_threshold}
              SCF_GUESS ATOMIC
            &END SCF
          &END DFT
          &SUBSYS
            &CELL
              ABC 10.0 10.0 10.0
            &END CELL
            &COORD
              H 0.0 0.0 0.0
              H 0.0 0.0 0.74
            &END COORD
            &KIND H
              BASIS_SET DZVP-MOLOPT-GTH
              POTENTIAL GTH-PBE-q1
            &END KIND
          &END SUBSYS
        &END FORCE_EVAL
        # DRY-RUN ONLY — structure_hash={params.structure_hash}
    """)


class Cp2kAiiDASolver(L1DftAdapter):
    """Dry-run + parse-only CP2K adapter."""

    ADAPTER_NAME = "Cp2kAiiDASolver"
    ADAPTER_VERSION = "0.1.0"
    BACKEND = "stub"
    ENGINE = "CP2K"

    def parse_output(self, raw_text: str) -> L1DftOutput:
        """Parse CP2K output. Looks for ENERGY| Total FORCE_EVAL line."""
        energy_Ha = 0.0
        force_rmse = 0.0
        delta: float | None = None

        for line in raw_text.splitlines():
            # "ENERGY| Total FORCE_EVAL ( QS ) energy [a.u.]:    -1.163729100"
            m_e = re.search(r"ENERGY\|\s+Total FORCE_EVAL.*?:\s+([-\d.]+)", line)
            if m_e:
                energy_Ha = float(m_e.group(1))
            # "MAX. GRADIENT =   X.XXX"
            m_f = re.search(r"MAX\. GRADIENT\s*=\s*([\d.E+\-]+)", line)
            if m_f:
                force_rmse = float(m_f.group(1))
            m_d = re.search(r"CONVERGENCE_DELTA:\s+([-\d.]+)", line)
            if m_d:
                delta = float(m_d.group(1))

        energy_eV = energy_Ha * _AU_TO_EV
        return L1DftOutput(
            code="CP2K",
            functional="PBE",
            total_energy_eV=energy_eV,
            force_rmse_eV_per_Ang=force_rmse,
            kpoint_mesh=[1, 1, 1],
            convergence_delta_meV_per_atom=delta,
            publication_grade=False,
        )

    def _compute_output(self, structure_cif: str, params: L1JobParams) -> L1DftOutput:
        """Return synthetic CP2K output; emit dry-run input file."""
        self._last_cp2k_input = _generate_cp2k_input(structure_cif, params)
        # Synthetic: slightly different from QE to enable cross-code disagreement tests
        energy_eV = -31.52  # ~-1.16 Ha × 27.21 eV/Ha (H2 proxy)
        return L1DftOutput(
            code="CP2K",
            functional="PBE",
            total_energy_eV=energy_eV,
            force_rmse_eV_per_Ang=0.0015,
            kpoint_mesh=params.kpoint_mesh or [1, 1, 1],
            convergence_delta_meV_per_atom=None,
            publication_grade=False,
        )
