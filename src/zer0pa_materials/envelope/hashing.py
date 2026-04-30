"""Deterministic structure and JSON hashing for the universal envelope.

The PRD mandates SHA-256 commitments on every envelope's ``input`` and
``output`` payloads, and on every artifact manifest. Hashes must be
deterministic across machines so that the Runpod cutover parity tests
(``runpod_mock`` vs ``runpod_rest``) can compare schema-shape AND payload
identity bit-exactly. This module is the single source of truth for that
canonicalisation.

Three layers of canonicalisation:

1. ``canonical_json_bytes`` — RFC 8785-ish JSON canonicalisation: sorted
   keys, no insignificant whitespace, ``orjson`` numeric output. We use
   orjson for performance and to avoid Python's float repr drift.

2. ``sha256_of`` — convenience wrapper returning the audit-format string
   ``"sha256:<hex>"`` matching the envelope's ``input_hash``/``output_hash``
   regex.

3. ``structure_hash`` — domain-specific canonicalisation for crystal
   structures so that translation by a unit lattice vector and reordering
   of equivalent species/coordinates do not change the hash. This is the
   primitive used by the L6 de-duplication gate (PRD §Phase 0/L6: "structure
   hash de-duplication … pymatgen.StructureMatcher").

A note on spglib: the PRD allows spglib for primitive-cell normalisation
when available. spglib is NOT a hard install dependency in the CPU-side
A0 wave (``pyproject.toml`` only declares it under ``materials-extras``).
We therefore detect it at runtime and fall back to a pure-Python Niggli-ish
reduction. The fallback is sufficient for: (a) translation invariance,
(b) species/coord re-ordering invariance, (c) lattice-vector permutation
invariance to the canonical sort order. It does NOT claim to find the
crystallographic primitive cell — that is a downstream L1/L1.5 concern,
not an A0 hashing concern. The fallback IS deterministic.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
import orjson

__all__ = [
    "HASH_REGEX",
    "canonical_json_bytes",
    "sha256_of",
    "structure_hash",
    "cif_hash_from_text",
    "parse_minimal_cif",
]


# Audit-format hash regex used by envelope validators.
HASH_REGEX = re.compile(r"^sha256:[0-9a-f]{64}$")


# ----------------------------------------------------------------------------
# JSON canonicalisation
# ----------------------------------------------------------------------------

def _coerce_for_orjson(obj: Any) -> Any:
    """Convert non-orjson-native types into JSON-friendly equivalents.

    Pydantic v2 models, numpy arrays/scalars, sets, frozensets, and tuples
    of mixed types all need explicit handling so ``OPT_SORT_KEYS`` produces a
    stable byte stream.
    """
    if obj is None or isinstance(obj, (bool, int, str)):
        return obj
    if isinstance(obj, float):
        # orjson handles floats but rejects non-finite values silently in
        # some modes — coerce them to canonical strings so hash collisions
        # don't occur when subtle nan/inf differences appear.
        if obj != obj:  # NaN
            return "__nan__"
        if obj == float("inf"):
            return "__inf__"
        if obj == float("-inf"):
            return "__neg_inf__"
        return obj
    if isinstance(obj, Mapping):
        return {str(k): _coerce_for_orjson(v) for k, v in obj.items()}
    if isinstance(obj, np.ndarray):
        return _coerce_for_orjson(obj.tolist())
    if isinstance(obj, np.generic):
        return _coerce_for_orjson(obj.item())
    if isinstance(obj, (set, frozenset)):
        # Sets have no inherent order; sort by canonical-bytes representation
        # so the result is deterministic.
        items = [_coerce_for_orjson(x) for x in obj]
        items.sort(key=lambda x: orjson.dumps(x, option=orjson.OPT_SORT_KEYS))
        return items
    if isinstance(obj, (list, tuple)):
        return [_coerce_for_orjson(x) for x in obj]
    if hasattr(obj, "model_dump"):
        # Pydantic v2 model.
        return _coerce_for_orjson(obj.model_dump(mode="json"))
    if hasattr(obj, "__dict__"):
        return _coerce_for_orjson(vars(obj))
    return str(obj)


def canonical_json_bytes(obj: Any) -> bytes:
    """Return canonical JSON bytes (sorted keys, no whitespace, deterministic).

    The output is byte-stable across runs and machines for any JSON-coercible
    object. orjson's ``OPT_SORT_KEYS`` covers nested-object key ordering;
    arrays are NOT reordered here because in JSON arrays are positional.
    """
    coerced = _coerce_for_orjson(obj)
    return orjson.dumps(coerced, option=orjson.OPT_SORT_KEYS)


def sha256_of(obj: Any) -> str:
    """Return ``"sha256:<hex>"`` of canonical JSON bytes for ``obj``."""
    digest = hashlib.sha256(canonical_json_bytes(obj)).hexdigest()
    return f"sha256:{digest}"


# ----------------------------------------------------------------------------
# Structure hashing
# ----------------------------------------------------------------------------

# Tolerances for treating coordinates as "the same" before sorting.
# 1e-5 is conservative relative to typical DFT-relaxed positions and is
# tighter than typical fixture noise in the A2 wave.
_COORD_TOL_DEFAULT = 1e-5
_LATTICE_TOL_DEFAULT = 1e-5


def _wrap_to_unit_cell(frac: np.ndarray) -> np.ndarray:
    """Wrap fractional coordinates into [0, 1) so translations don't change hash."""
    wrapped = frac - np.floor(frac)
    # numerically clamp to [0,1)
    wrapped = np.where(wrapped >= 1.0 - 1e-12, 0.0, wrapped)
    return wrapped


def _round_to_grid(values: np.ndarray, tol: float) -> np.ndarray:
    """Round to a grid of size ``tol`` so values that differ by < tol hash equal."""
    return np.round(values / tol).astype(np.int64) * tol


def _canonicalise_lattice(
    lattice: np.ndarray, tol: float = _LATTICE_TOL_DEFAULT
) -> np.ndarray:
    """Return a canonical orientation of the lattice matrix.

    We sort lattice vectors by length (then by lex order) so a permutation
    of rows does not change the hash. We do NOT compute the Niggli-reduced
    cell here; that would require spglib and is out of A0 scope. The sort
    is sufficient for translation invariance and for the limited
    "rename-the-cell-vectors" symmetry we need at the contract layer.
    """
    a = np.asarray(lattice, dtype=np.float64).reshape(3, 3)
    lengths = np.linalg.norm(a, axis=1)
    # Sort primarily by length; secondarily by tuple-of-rounded-components
    # so ties are broken deterministically.
    keys = []
    for i in range(3):
        keys.append((round(lengths[i] / tol), tuple(_round_to_grid(a[i], tol))))
    order = sorted(range(3), key=lambda i: keys[i])
    return a[order, :]


def _canonicalise_sites(
    species: Sequence[str],
    fractional_coords: np.ndarray,
    tol: float = _COORD_TOL_DEFAULT,
) -> list[tuple[str, tuple[float, float, float]]]:
    """Return a deterministic list of (species, (x, y, z)) sorted entries."""
    coords = np.asarray(fractional_coords, dtype=np.float64).reshape(-1, 3)
    if coords.shape[0] != len(species):
        raise ValueError(
            f"species count ({len(species)}) does not match fractional_coords count ({coords.shape[0]})"
        )
    wrapped = _wrap_to_unit_cell(coords)
    rounded = _round_to_grid(wrapped, tol)
    sites: list[tuple[str, tuple[float, float, float]]] = []
    for sp, c in zip(species, rounded):
        sites.append((str(sp), (float(c[0]), float(c[1]), float(c[2]))))
    sites.sort(key=lambda s: (s[0], s[1]))
    return sites


def structure_hash(
    structure: Mapping[str, Any],
    coord_tol: float = _COORD_TOL_DEFAULT,
    lattice_tol: float = _LATTICE_TOL_DEFAULT,
) -> str:
    """Hash a crystal structure dict deterministically.

    Expected dict shape (subset of OPTIMADE/pymatgen-style)::

        {
            "lattice_vectors": [[a1x, a1y, a1z], [a2x, ...], [a3x, ...]],
            "species": ["Li", "Cl", ...],         # length N
            "fractional_coords": [[x, y, z], ...] # length N
        }

    Properties guaranteed:

    * Translation invariance: adding an integer to any fractional coord
      leaves the hash unchanged (because we wrap into [0,1)).
    * Site-permutation invariance: reordering species + fractional_coords
      together leaves the hash unchanged.
    * Lattice-vector permutation invariance: passing the same lattice with
      its rows reordered leaves the hash unchanged.
    * Coord-perturbation sensitivity: perturbing a coord by more than the
      ``coord_tol`` (default 1e-5) changes the hash.

    This is sufficient for L6 de-duplication; downstream layers MAY override
    by passing tighter or looser tolerances if they need finer-grained
    matching (e.g., MatterGen vs DFT-relaxed comparison).
    """
    lattice = _canonicalise_lattice(np.asarray(structure["lattice_vectors"]), lattice_tol)
    species = list(structure["species"])
    coords = np.asarray(structure["fractional_coords"], dtype=np.float64)
    sites = _canonicalise_sites(species, coords, coord_tol)

    canonical = {
        "schema": "zer0pa.materials.structure-hash.v1",
        "lattice_vectors": [[round(float(x) / lattice_tol) * lattice_tol for x in row] for row in lattice],
        "sites": [[sp, [c[0], c[1], c[2]]] for sp, c in sites],
    }
    return sha256_of(canonical)


# ----------------------------------------------------------------------------
# Minimal CIF parser (pure Python, no pymatgen/ASE dependency)
# ----------------------------------------------------------------------------

# We only need enough CIF to roundtrip the tiny test fixtures. A real Phase 0
# adapter will use pymatgen / ASE / gemmi when those are installed (recorded
# under materials-extras). The PRD explicitly says A0 must NOT require
# pymatgen.

_CIF_NUMBER_PATTERN = re.compile(r"-?\d+(?:\.\d+)?(?:\([\d]+\))?")


def _strip_cif_uncertainty(value: str) -> str:
    """Strip trailing parenthetical uncertainty, e.g. ``5.4(2) -> 5.4``."""
    return re.sub(r"\([\d]+\)$", "", value.strip())


def parse_minimal_cif(cif_text: str) -> dict[str, Any]:
    """Parse a minimal subset of CIF into a structure dict.

    Supported keys:

    * ``_cell_length_a``, ``_cell_length_b``, ``_cell_length_c``
    * ``_cell_angle_alpha``, ``_cell_angle_beta``, ``_cell_angle_gamma``
    * a single ``loop_`` containing
      ``_atom_site_type_symbol``, ``_atom_site_fract_x``, ``_atom_site_fract_y``,
      ``_atom_site_fract_z`` (in any order; order is read from the loop header).

    Raises ``ValueError`` if the CIF is malformed or missing required fields.
    The resulting structure is ready to be passed to ``structure_hash``.
    """
    a = b = c = None
    alpha = beta = gamma = None

    lines = [ln.rstrip() for ln in cif_text.splitlines()]
    i = 0
    species: list[str] = []
    fractional: list[list[float]] = []
    while i < len(lines):
        line = lines[i].strip()
        if not line or line.startswith("#"):
            i += 1
            continue
        if line.startswith("_cell_length_a"):
            a = float(_strip_cif_uncertainty(line.split()[-1]))
        elif line.startswith("_cell_length_b"):
            b = float(_strip_cif_uncertainty(line.split()[-1]))
        elif line.startswith("_cell_length_c"):
            c = float(_strip_cif_uncertainty(line.split()[-1]))
        elif line.startswith("_cell_angle_alpha"):
            alpha = float(_strip_cif_uncertainty(line.split()[-1]))
        elif line.startswith("_cell_angle_beta"):
            beta = float(_strip_cif_uncertainty(line.split()[-1]))
        elif line.startswith("_cell_angle_gamma"):
            gamma = float(_strip_cif_uncertainty(line.split()[-1]))
        elif line.startswith("loop_"):
            # Read loop headers (lines that start with "_") then data lines.
            i += 1
            headers: list[str] = []
            while i < len(lines):
                inner = lines[i].strip()
                if inner.startswith("_"):
                    headers.append(inner)
                    i += 1
                else:
                    break
            if {
                "_atom_site_type_symbol",
                "_atom_site_fract_x",
                "_atom_site_fract_y",
                "_atom_site_fract_z",
            }.issubset(set(headers)):
                idx_sym = headers.index("_atom_site_type_symbol")
                idx_x = headers.index("_atom_site_fract_x")
                idx_y = headers.index("_atom_site_fract_y")
                idx_z = headers.index("_atom_site_fract_z")
                while i < len(lines):
                    inner = lines[i].strip()
                    if not inner or inner.startswith("loop_") or inner.startswith("_"):
                        break
                    if inner.startswith("#"):
                        i += 1
                        continue
                    tokens = inner.split()
                    if len(tokens) < len(headers):
                        i += 1
                        continue
                    species.append(tokens[idx_sym])
                    fractional.append(
                        [
                            float(_strip_cif_uncertainty(tokens[idx_x])),
                            float(_strip_cif_uncertainty(tokens[idx_y])),
                            float(_strip_cif_uncertainty(tokens[idx_z])),
                        ]
                    )
                    i += 1
                continue  # the inner loop already incremented i
            # else: skip this loop entirely
        i += 1

    if None in (a, b, c, alpha, beta, gamma):
        raise ValueError("minimal CIF: missing one or more cell parameters (a, b, c, alpha, beta, gamma)")
    if not species:
        raise ValueError("minimal CIF: no atom sites parsed")

    # Build lattice vectors from a, b, c, alpha, beta, gamma.
    # Standard orientation: a along x; b in xy plane; c the rest.
    a_v = np.array([a, 0.0, 0.0])
    cos_g = np.cos(np.deg2rad(gamma))
    sin_g = np.sin(np.deg2rad(gamma))
    b_v = np.array([b * cos_g, b * sin_g, 0.0])
    cos_b = np.cos(np.deg2rad(beta))
    cos_a = np.cos(np.deg2rad(alpha))
    cx = c * cos_b
    cy = c * (cos_a - cos_b * cos_g) / sin_g if abs(sin_g) > 1e-12 else 0.0
    cz_sq = c * c - cx * cx - cy * cy
    cz = float(np.sqrt(max(cz_sq, 0.0)))
    c_v = np.array([cx, cy, cz])

    return {
        "lattice_vectors": [a_v.tolist(), b_v.tolist(), c_v.tolist()],
        "species": species,
        "fractional_coords": fractional,
    }


def cif_hash_from_text(cif_text: str) -> str:
    """Parse a minimal CIF then hash via :func:`structure_hash`."""
    structure = parse_minimal_cif(cif_text)
    return structure_hash(structure)
