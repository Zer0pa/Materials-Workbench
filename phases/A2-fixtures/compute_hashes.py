"""Helper: compute and print structure hashes for every positive fixture.

Run from repo root:

    .venv/bin/python phases/A2-fixtures/compute_hashes.py
    (or: zer0pa-materials-workbench ...)

The hashes are then baked into the corresponding manifest.json files. The
test_structure_hashes test recomputes the hash and asserts equality with
the value committed in the manifest, so any future drift in canonicalisation
or in a CIF coordinate is immediately caught.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from zer0pa_materials_workbench.envelope.hashing import (  # noqa: E402
    parse_minimal_cif,
    structure_hash,
)

FIXTURE_PATHS = [
    "fixtures/structures/H2/structure.cif",
    "fixtures/structures/LiH/structure.cif",
    "fixtures/structures/Si/structure.cif",
    "fixtures/structures/NaCl/structure.cif",
    "fixtures/structures/LLZO/cubic/structure.cif",
    "fixtures/structures/LLZO/tetragonal/structure.cif",
    "fixtures/structures/Li6PS5Cl/structure.cif",
    "fixtures/structures/Li-Mg-Zr-Cl-seed/structure.cif",
    "fixtures/structures/Bi2Te3/structure.cif",
    "fixtures/structures/PbTe/structure.cif",
    "fixtures/structures/SnSe/structure.cif",
]


def main() -> int:
    print("structure_hashes:")
    for rel in FIXTURE_PATHS:
        cif_path = ROOT / rel
        text = cif_path.read_text()
        try:
            structure = parse_minimal_cif(text)
            h = structure_hash(structure)
        except Exception as exc:
            print(f"  {rel}: ERROR ({type(exc).__name__}: {exc})")
            continue
        n_atoms = len(structure["species"])
        print(f"  {rel}: n_atoms={n_atoms} hash={h}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
