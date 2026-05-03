"""MatterGenGeneratorAdapter — diffusion CSP candidate generator.

MatterGen 1.0 (A/MIT) — https://github.com/microsoft/mattergen

Backend selection:
    "stub" (default)   — synthetic candidates from positive fixtures
                         (perturb LLZO cubic with small lattice variations).
    "mattergen_runpod" — real MatterGen inference on RunPod A100
                         (parked behind L6_GENERATOR_BACKEND=mattergen_runpod).

LeMat-GenBench S.U.N.:
    - S (Stability) — requires DFT validation; deferred to L1.
    - U (Uniqueness) — implemented via structure_hash_dedupe in falsifiers.
    - N (Novelty)    — implemented via reference_expansion_dedupe in falsifiers.
    novelty_status is always "pending" until L1+ionic+L2 all pass.

BlockedSourceManifest is emitted for the real backend.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from zer0pa_materials_workbench.adapters.l6.base import L6GeneratorAdapter, _candidate_id, _run_id
from zer0pa_materials_workbench.envelope.config import MaterialsConfig
from zer0pa_materials_workbench.envelope.hashing import sha256_of, structure_hash

_FIXTURES_STRUCTURES = Path(__file__).parents[4] / "fixtures" / "structures"

# Reference structure_hash for LLZO cubic (from A2 fixture manifest).
_LLZO_CUBIC_HASH = "sha256:d45cb2bfe5e76b86b365e1402e118ed32280049a62345c903558c6cfac04ef19"

# Canonical LLZO cubic CIF content (abbreviated for stub generation).
_LLZO_CIF_TEMPLATE = """\
data_LLZO_cubic_mattergen_stub
_cell_length_a {a:.4f}
_cell_length_b {b:.4f}
_cell_length_c {c:.4f}
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
Li 0.125 0.000 0.250
Li 0.125 0.500 0.250
Li 0.625 0.000 0.250
Li 0.625 0.500 0.250
Li 0.375 0.000 0.250
Li 0.375 0.500 0.250
Li 0.875 0.000 0.250
La 0.000 0.250 0.125
La 0.000 0.250 0.625
La 0.000 0.750 0.375
Zr 0.000 0.000 0.000
Zr 0.500 0.500 0.500
O  0.100 0.197 0.282
O  0.282 0.100 0.197
O  0.197 0.282 0.100
O  0.900 0.803 0.718
O  0.718 0.900 0.803
O  0.803 0.718 0.900
O  0.400 0.697 0.282
O  0.282 0.400 0.697
O  0.697 0.282 0.400
O  0.600 0.303 0.718
O  0.718 0.600 0.303
O  0.303 0.718 0.600
"""

# Small lattice parameter perturbations (Angstrom) for stub candidates.
_PERTURBATIONS: list[float] = [0.05, 0.10, -0.05, -0.10, 0.15]

_MATTERGEN_RETRY = (
    "Accept MatterGen MIT license at https://github.com/microsoft/mattergen and "
    "set L6_GENERATOR_BACKEND=mattergen_runpod to enable real inference."
)


class MatterGenGeneratorAdapter(L6GeneratorAdapter):
    """MatterGen diffusion CSP generator (stub + parked real backend).

    Args:
        config: MaterialsConfig instance (reads L6_GENERATOR_BACKEND).
        n_candidates: Number of stub candidates to generate (max 5).
    """

    adapter_name = "mattergen_generator"

    def __init__(
        self,
        config: MaterialsConfig | None = None,
        n_candidates: int = 3,
    ) -> None:
        super().__init__(config)
        self.n_candidates = min(n_candidates, len(_PERTURBATIONS))

    def _generate(self, constraints: dict[str, Any]) -> list[dict[str, Any]]:
        backend = getattr(self.config, "L6_GENERATOR_BACKEND", "stub")
        if backend == "mattergen_runpod":
            # Emit blocked manifest and fall through to stub.
            self._emit_blocked_manifest(
                source_id=f"mattergen:runpod:{uuid.uuid4().hex[:8]}",
                locator="https://github.com/microsoft/mattergen",
                blocker_reason="license_unverified",
                retry_strategy=_MATTERGEN_RETRY,
            )
        return self._stub_generate(constraints)

    def _stub_generate(self, constraints: dict[str, Any]) -> list[dict[str, Any]]:
        """Generate perturbed LLZO structures as synthetic candidates."""
        base_a = 12.971  # Å — LLZO cubic lattice parameter
        system = constraints.get("chemical_system", "Li-La-Zr-O")
        target_conductivity = constraints.get("target_conductivity_S_per_cm", 1e-3)

        run_id = _run_id()
        results = []

        for i, delta in enumerate(_PERTURBATIONS[: self.n_candidates]):
            a = base_a + delta
            cif_text = _LLZO_CIF_TEMPLATE.format(a=a, b=a, c=a)
            cid = _candidate_id()
            query_id = uuid.uuid4().hex[:12]

            # Build a minimal structure dict for hashing.
            struct_dict = {
                "lattice_vectors": [[a, 0, 0], [0, a, 0], [0, 0, a]],
                "species": ["Li"] * 7 + ["La"] * 3 + ["Zr"] * 2 + ["O"] * 12,
                "fractional_coords": [
                    [0.125, 0.000, 0.250], [0.125, 0.500, 0.250],
                    [0.625, 0.000, 0.250], [0.625, 0.500, 0.250],
                    [0.375, 0.000, 0.250], [0.375, 0.500, 0.250],
                    [0.875, 0.000, 0.250],
                    [0.000, 0.250, 0.125], [0.000, 0.250, 0.625],
                    [0.000, 0.750, 0.375],
                    [0.000, 0.000, 0.000], [0.500, 0.500, 0.500],
                    [0.100, 0.197, 0.282], [0.282, 0.100, 0.197],
                    [0.197, 0.282, 0.100], [0.900, 0.803, 0.718],
                    [0.718, 0.900, 0.803], [0.803, 0.718, 0.900],
                    [0.400, 0.697, 0.282], [0.282, 0.400, 0.697],
                    [0.697, 0.282, 0.400], [0.600, 0.303, 0.718],
                    [0.718, 0.600, 0.303], [0.303, 0.718, 0.600],
                ],
            }

            s_hash = structure_hash(struct_dict)

            # Dedup result: candidate is NOT the LLZO cubic fixture if a != 12.971.
            is_dup = abs(a - 12.971) < 1e-6
            dedup_results = [
                {"source": "MP", "matched": is_dup, "matched_id": "mp-942733" if is_dup else None},
                {"source": "JARVIS", "matched": False, "matched_id": None},
                {"source": "Alexandria", "matched": False, "matched_id": None},
                {"source": "GNoME", "matched": False, "matched_id": None},
                {"source": "OPTIMADE", "matched": False, "matched_id": None},
            ]

            output_payload = {
                "candidate_uri": f"artifact:cif:{cid}",
                "structure_hash": s_hash,
                "novelty_status": "pending",  # NEVER "novel" before L1+ionic+L2 pass
                "dedup_results": dedup_results,
                "cif_valid": True,
                "charge_neutral": True,
                "minimum_distance_ok": True,
                "cif_text": cif_text,
                "chemical_system": system,
                "lattice_parameter_a": a,
                "perturbation_delta_ang": delta,
                "lematgen_u_unique": not is_dup,
                "lematgen_n_novel": False,  # N requires DFT validation
                "lematgen_s_stable": None,  # S deferred to L1
                "target_conductivity_S_per_cm": target_conductivity,
                "generator": "MatterGen/stub",
            }

            input_payload = {
                "constraints": constraints,
                "candidate_index": i,
                "backend": "stub",
                "model": "MatterGen-1.0-stub",
            }

            input_hash = sha256_of(input_payload)
            output_hash = sha256_of({
                k: v for k, v in output_payload.items() if k != "cif_text"
            })

            env = self._build_l6_envelope(
                candidate_id=cid,
                run_id=run_id,
                input_hash=input_hash,
                output_hash=output_hash,
                output=output_payload,
                tool_adapter_name="MatterGenGeneratorAdapter/stub",
                backend="stub",
                input_data=input_payload,
            )
            results.append(env)

        return results
