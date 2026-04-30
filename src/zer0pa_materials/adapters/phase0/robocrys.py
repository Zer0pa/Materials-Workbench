"""RobocrystallographerStructureNarrator — structure-to-text description.

Robocrystallographer (A/MIT) converts a CIF structure into a natural-language
description suitable for LLM context in the LangGraph extraction workflow.

Backend: always "local_stub" — returns templated descriptions of positive
fixtures. Real Robocrystallographer integration parked pending
``robocrystallographer`` pip install in materials-extras.

SourceManifest is emitted on every call.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from zer0pa_materials.adapters.phase0.base import Phase0Adapter, _now_iso, _run_id
from zer0pa_materials.audit.sources import SourceManifest
from zer0pa_materials.envelope.config import MaterialsConfig
from zer0pa_materials.envelope.hashing import sha256_of

_FIXTURES_STRUCTURES = Path(__file__).parents[4] / "fixtures" / "structures"

# Canned descriptions for positive fixtures.
_STUB_DESCRIPTIONS: dict[str, str] = {
    "LLZO_cubic": (
        "Li7La3Zr2O12 (LLZO) adopts the cubic garnet structure (Ia-3d) with "
        "lattice parameter a = 12.971 Å. The structure features Li ions "
        "distributed across tetrahedral 24d and octahedral 48g/96h Wyckoff "
        "sites, La on 24c sites coordinated by eight oxygen atoms, and Zr on "
        "16a sites in oxygen octahedra. The 3D Li sublattice provides fast "
        "lithium-ion diffusion pathways."
    ),
    "LLZO_tetragonal": (
        "Tetragonal Li7La3Zr2O12 adopts space group I41/acd (I-4(1)/acd) "
        "with ordered Li sublattice (a ≈ 13.13 Å, c ≈ 12.66 Å). "
        "Li ordering on the 8a/16f/32g Wyckoff sites reduces ionic "
        "conductivity relative to the cubic phase."
    ),
    "Li6PS5Cl": (
        "Li6PS5Cl (argyrodite) adopts F-43m cubic symmetry (a ≈ 9.85 Å). "
        "The structure features PS4 tetrahedra with S/Cl anion disorder on "
        "4c/4a sites. The Li sublattice is highly disordered, providing "
        "exceptionally fast Li-ion diffusion."
    ),
    "Li-Mg-Zr-Cl-seed": (
        "Novel Li2MgZrCl6 seed composition (P1 cell, 10 atoms). "
        "Halide electrolyte candidate with edge-sharing MCl6 octahedra. "
        "Pre-registered novel challenge seed — no literature characterisation."
    ),
    "Si": (
        "Silicon adopts the diamond cubic structure (Fd-3m, a = 5.431 Å) "
        "with two equivalent Si atoms per unit cell."
    ),
    "NaCl": (
        "Sodium chloride adopts the rock-salt structure (Fm-3m, a = 5.64 Å) "
        "with face-centred cubic packing of Na⁺ and Cl⁻ ions."
    ),
}


class RobocrystallographerStructureNarrator(Phase0Adapter):
    """Structure-to-text adapter (Robocrystallographer stub).

    Args:
        config: MaterialsConfig instance.
    """

    adapter_name = "robocrystallographer_structure_narrator"

    def __init__(self, config: MaterialsConfig | None = None) -> None:
        super().__init__(config)
        self._last_manifest: SourceManifest | None = None

    def _execute(self, input: dict[str, Any]) -> dict[str, Any]:
        # Only stub backend implemented.
        return self._query_stub(input)

    def _query_stub(self, input: dict[str, Any]) -> dict[str, Any]:
        """Return a templated structure description from the fixture set."""
        structure_key = input.get("structure_key", input.get("material", "LLZO_cubic"))
        cif_text = input.get("cif_text", "")
        run_id = _run_id()
        query_id = uuid.uuid4().hex[:12]

        description = _STUB_DESCRIPTIONS.get(
            str(structure_key),
            f"Stub description for structure_key={structure_key!r}. "
            "Real Robocrystallographer integration parked pending materials-extras install.",
        )

        input_payload = {
            "structure_key": structure_key,
            "cif_text_len": len(cif_text),
            "backend": "local_stub",
        }
        # Phase0Output must have extracted_properties, units_normalised,
        # contradictions_blocking — narrator produces no numeric extractions;
        # the description is carried in an extra field that the schema allows
        # via the output dict (raw, not validated to Phase0Output at this layer).
        output_payload = {
            "extracted_properties": [],
            "units_normalised": True,
            "contradictions_blocking": [],
            "structure_description": description,
            "structure_key": structure_key,
        }

        input_hash = sha256_of(input_payload)
        output_hash = sha256_of(output_payload)

        self._last_manifest = self._make_source_manifest(
            source_id=f"robocrys:stub:{query_id}",
            source_type="repo",
            locator="robocrystallographer>=0.4 (MIT)",
            license_spdx="MIT",
            summary=f"Robocrystallographer stub description for {structure_key}",
            content_hash=output_hash,
            query_params=input_payload,
        )

        return self._build_envelope(
            run_id=run_id,
            input_hash=input_hash,
            output_hash=output_hash,
            output=output_payload,
            tool_adapter_name="RobocrystallographerStructureNarrator/stub",
            backend="stub",
            input_data=input_payload,
        )

    def get_last_manifest(self) -> SourceManifest | None:
        return self._last_manifest
