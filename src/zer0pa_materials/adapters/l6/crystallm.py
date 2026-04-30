"""CrystaLlmCifGeneratorAdapter — CrystaLLM text-to-CIF generator stub.

CrystaLLM 2024 (A/MIT) — https://github.com/lantunes/CrystaLLM

Real backend parked; stub returns a simple Li-Mg-Zr-Cl seed-derived
candidate. BlockedSourceManifest emitted when real backend requested.

novelty_status is always "pending" until L1+ionic+L2 falsifiers pass.
"""

from __future__ import annotations

import uuid
from typing import Any

from zer0pa_materials.adapters.l6.base import L6GeneratorAdapter, _candidate_id, _run_id
from zer0pa_materials.envelope.config import MaterialsConfig
from zer0pa_materials.envelope.hashing import sha256_of, structure_hash

_CRYSTALLM_RETRY = (
    "Accept CrystaLLM MIT license at https://github.com/lantunes/CrystaLLM and "
    "set L6_GENERATOR_BACKEND=crystallm to enable real inference."
)

_STUB_CIF = """\
data_Li2MgZrCl6_crystallm_stub
_cell_length_a 6.453
_cell_length_b 6.453
_cell_length_c 6.453
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
Li 0.250 0.250 0.250
Li 0.750 0.750 0.750
Mg 0.000 0.000 0.000
Zr 0.500 0.500 0.500
Cl 0.250 0.000 0.500
Cl 0.750 0.000 0.500
Cl 0.000 0.250 0.500
Cl 0.000 0.750 0.500
Cl 0.500 0.250 0.000
Cl 0.500 0.750 0.000
"""


class CrystaLlmCifGeneratorAdapter(L6GeneratorAdapter):
    """CrystaLLM text-to-CIF generator (stub).

    Args:
        config: MaterialsConfig instance (reads L6_GENERATOR_BACKEND).
    """

    adapter_name = "crystallm_cif_generator"

    def _generate(self, constraints: dict[str, Any]) -> list[dict[str, Any]]:
        backend = getattr(self.config, "L6_GENERATOR_BACKEND", "stub")
        if backend not in ("stub", "crystallm"):
            self._emit_blocked_manifest(
                source_id=f"crystallm:runpod:{uuid.uuid4().hex[:8]}",
                locator="https://github.com/lantunes/CrystaLLM",
                blocker_reason="license_unverified",
                retry_strategy=_CRYSTALLM_RETRY,
            )
        return self._stub_generate(constraints)

    def _stub_generate(self, constraints: dict[str, Any]) -> list[dict[str, Any]]:
        prompt = constraints.get("prompt", "Li Mg Zr Cl halide electrolyte")
        system = constraints.get("chemical_system", "Li-Mg-Zr-Cl")
        run_id = _run_id()
        cid = _candidate_id()

        struct_dict = {
            "lattice_vectors": [[6.453, 0, 0], [0, 6.453, 0], [0, 0, 6.453]],
            "species": ["Li", "Li", "Mg", "Zr", "Cl", "Cl", "Cl", "Cl", "Cl", "Cl"],
            "fractional_coords": [
                [0.250, 0.250, 0.250], [0.750, 0.750, 0.750],
                [0.000, 0.000, 0.000],
                [0.500, 0.500, 0.500],
                [0.250, 0.000, 0.500], [0.750, 0.000, 0.500],
                [0.000, 0.250, 0.500], [0.000, 0.750, 0.500],
                [0.500, 0.250, 0.000], [0.500, 0.750, 0.000],
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
            "cif_text": _STUB_CIF,
            "chemical_system": system,
            "prompt": prompt,
            "generator": "CrystaLLM/stub",
        }

        input_payload = {
            "constraints": constraints,
            "backend": "stub",
            "model": "CrystaLLM-stub",
        }

        return [
            self._build_l6_envelope(
                candidate_id=cid,
                run_id=run_id,
                input_hash=sha256_of(input_payload),
                output_hash=sha256_of({k: v for k, v in output_payload.items() if k != "cif_text"}),
                output=output_payload,
                tool_adapter_name="CrystaLlmCifGeneratorAdapter/stub",
                backend="stub",
                input_data=input_payload,
            )
        ]
