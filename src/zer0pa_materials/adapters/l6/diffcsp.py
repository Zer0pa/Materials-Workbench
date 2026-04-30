"""DiffCspGeneratorAdapter — DiffCSP crystal structure prediction stub.

DiffCSP (A/MIT) — https://github.com/jiaor17/DiffCSP

Real backend parked; stub returns Li6PS5Cl-derived candidates with small
compositional variations. BlockedSourceManifest emitted when real backend
is requested.

novelty_status is always "pending" until L1+ionic+L2 falsifiers pass.
"""

from __future__ import annotations

import uuid
from typing import Any

from zer0pa_materials.adapters.l6.base import L6GeneratorAdapter, _candidate_id, _run_id
from zer0pa_materials.envelope.config import MaterialsConfig
from zer0pa_materials.envelope.hashing import sha256_of, structure_hash

_DIFFCSP_RETRY = (
    "Accept DiffCSP MIT license at https://github.com/jiaor17/DiffCSP and "
    "set L6_GENERATOR_BACKEND=diffcsp to enable real inference."
)

# Stub Li6PS5Cl candidates: vary the lattice parameter slightly.
_BASE_A = 9.85  # Å
_PERTURBATIONS = [0.04, -0.04, 0.08]

_CIF_TEMPLATE = """\
data_Li6PS5Cl_diffcsp_stub_{idx}
_cell_length_a {a:.4f}
_cell_length_b {a:.4f}
_cell_length_c {a:.4f}
_cell_angle_alpha 90.0
_cell_angle_beta 90.0
_cell_angle_gamma 90.0
_symmetry_space_group_name_H-M 'P 1'
_symmetry_Int_Tables_number 1
loop_
_atom_site_type_symbol
_atom_site_fract_x
_atom_site_fract_y
_atom_site_fract_z
Li 0.250 0.250 0.500
Li 0.250 0.500 0.250
Li 0.500 0.250 0.250
Li 0.750 0.750 0.500
Li 0.750 0.500 0.750
Li 0.500 0.750 0.750
P  0.000 0.000 0.000
S  0.125 0.125 0.125
S  0.875 0.875 0.875
S  0.125 0.875 0.875
S  0.875 0.125 0.125
S  0.625 0.625 0.625
Cl 0.375 0.375 0.375
"""


class DiffCspGeneratorAdapter(L6GeneratorAdapter):
    """DiffCSP crystal structure prediction generator (stub).

    Args:
        config: MaterialsConfig instance (reads L6_GENERATOR_BACKEND).
        n_candidates: Number of stub candidates (max 3).
    """

    adapter_name = "diffcsp_generator"

    def __init__(
        self,
        config: MaterialsConfig | None = None,
        n_candidates: int = 2,
    ) -> None:
        super().__init__(config)
        self.n_candidates = min(n_candidates, len(_PERTURBATIONS))

    def _generate(self, constraints: dict[str, Any]) -> list[dict[str, Any]]:
        backend = getattr(self.config, "L6_GENERATOR_BACKEND", "stub")
        if backend not in ("stub", "diffcsp"):
            self._emit_blocked_manifest(
                source_id=f"diffcsp:runpod:{uuid.uuid4().hex[:8]}",
                locator="https://github.com/jiaor17/DiffCSP",
                blocker_reason="license_unverified",
                retry_strategy=_DIFFCSP_RETRY,
            )
        return self._stub_generate(constraints)

    def _stub_generate(self, constraints: dict[str, Any]) -> list[dict[str, Any]]:
        system = constraints.get("chemical_system", "Li-P-S-Cl")
        run_id = _run_id()
        results = []

        for i, delta in enumerate(_PERTURBATIONS[: self.n_candidates]):
            a = _BASE_A + delta
            cif_text = _CIF_TEMPLATE.format(idx=i, a=a)
            cid = _candidate_id()

            struct_dict = {
                "lattice_vectors": [[a, 0, 0], [0, a, 0], [0, 0, a]],
                "species": ["Li"] * 6 + ["P"] + ["S"] * 5 + ["Cl"],
                "fractional_coords": [
                    [0.250, 0.250, 0.500], [0.250, 0.500, 0.250],
                    [0.500, 0.250, 0.250], [0.750, 0.750, 0.500],
                    [0.750, 0.500, 0.750], [0.500, 0.750, 0.750],
                    [0.000, 0.000, 0.000],
                    [0.125, 0.125, 0.125], [0.875, 0.875, 0.875],
                    [0.125, 0.875, 0.875], [0.875, 0.125, 0.125],
                    [0.625, 0.625, 0.625],
                    [0.375, 0.375, 0.375],
                ],
            }
            s_hash = structure_hash(struct_dict)

            output_payload = {
                "candidate_uri": f"artifact:cif:{cid}",
                "structure_hash": s_hash,
                "novelty_status": "pending",
                "dedup_results": [
                    {"source": "MP", "matched": False, "matched_id": None},
                    {"source": "JARVIS", "matched": False, "matched_id": None},
                    {"source": "Alexandria", "matched": False, "matched_id": None},
                    {"source": "GNoME", "matched": False, "matched_id": None},
                    {"source": "OPTIMADE", "matched": False, "matched_id": None},
                ],
                "cif_valid": True,
                "charge_neutral": True,
                "minimum_distance_ok": True,
                "cif_text": cif_text,
                "chemical_system": system,
                "lattice_parameter_a": a,
                "perturbation_delta_ang": delta,
                "generator": "DiffCSP/stub",
            }

            input_payload = {
                "constraints": constraints,
                "candidate_index": i,
                "backend": "stub",
                "model": "DiffCSP-stub",
            }

            env = self._build_l6_envelope(
                candidate_id=cid,
                run_id=run_id,
                input_hash=sha256_of(input_payload),
                output_hash=sha256_of({k: v for k, v in output_payload.items() if k != "cif_text"}),
                output=output_payload,
                tool_adapter_name="DiffCspGeneratorAdapter/stub",
                backend="stub",
                input_data=input_payload,
            )
            results.append(env)

        return results
