"""Unit tests for deterministic structure hashing and CIF parsing."""

from __future__ import annotations

import math

import numpy as np
import pytest

from zer0pa_materials_workbench.envelope import (
    HASH_REGEX,
    canonical_json_bytes,
    cif_hash_from_text,
    parse_minimal_cif,
    sha256_of,
    structure_hash,
)

# ----------------------------------------------------------------------------
# canonical_json_bytes
# ----------------------------------------------------------------------------


def test_canonical_json_bytes_sorted_keys():
    a = canonical_json_bytes({"b": 1, "a": 2})
    b = canonical_json_bytes({"a": 2, "b": 1})
    assert a == b


def test_canonical_json_bytes_handles_numpy():
    arr = np.array([1.0, 2.0, 3.0])
    a = canonical_json_bytes({"x": arr})
    b = canonical_json_bytes({"x": [1.0, 2.0, 3.0]})
    assert a == b


def test_canonical_json_bytes_handles_pydantic_model():
    from zer0pa_materials_workbench.envelope import FalsifierItem
    fi = FalsifierItem(name="t", threshold=">0", actual=1.0, status="pass")
    a = canonical_json_bytes(fi)
    b = canonical_json_bytes(fi.model_dump(mode="json"))
    assert a == b


# ----------------------------------------------------------------------------
# sha256_of
# ----------------------------------------------------------------------------


def test_sha256_of_format():
    s = sha256_of({"x": 1})
    assert HASH_REGEX.match(s)


def test_sha256_of_deterministic():
    assert sha256_of({"x": 1, "y": 2}) == sha256_of({"y": 2, "x": 1})


def test_sha256_of_varies_with_payload():
    assert sha256_of({"x": 1}) != sha256_of({"x": 2})


# ----------------------------------------------------------------------------
# Structure hash — the four invariants and the sensitivity guarantee
# ----------------------------------------------------------------------------


def _llzo_like_structure() -> dict:
    """A small, hand-crafted cubic-like structure for invariance testing.

    Not chemically correct LLZO (which has 192 atoms and complex Wyckoff
    occupancies); a 4-atom test cell is sufficient to exercise the hashing
    invariants the PRD requires at A0.
    """
    return {
        "lattice_vectors": [
            [4.0, 0.0, 0.0],
            [0.0, 4.0, 0.0],
            [0.0, 0.0, 4.0],
        ],
        "species": ["Li", "Li", "O", "O"],
        "fractional_coords": [
            [0.0, 0.0, 0.0],
            [0.5, 0.5, 0.5],
            [0.5, 0.0, 0.0],
            [0.0, 0.5, 0.5],
        ],
    }


def test_structure_hash_format():
    s = structure_hash(_llzo_like_structure())
    assert HASH_REGEX.match(s)


def test_structure_hash_invariant_under_unit_translation():
    """Translating every coord by an integer must NOT change the hash."""
    s0 = _llzo_like_structure()
    s1 = {
        **s0,
        "fractional_coords": [
            [c + 1.0 for c in coord] for coord in s0["fractional_coords"]
        ],
    }
    assert structure_hash(s0) == structure_hash(s1)


def test_structure_hash_invariant_under_fractional_translation_by_one():
    """Translating ONE coordinate component by 1.0 must NOT change the hash."""
    s0 = _llzo_like_structure()
    s1 = {
        **s0,
        "fractional_coords": [
            [coord[0] + 2.0, coord[1], coord[2]] for coord in s0["fractional_coords"]
        ],
    }
    assert structure_hash(s0) == structure_hash(s1)


def test_structure_hash_invariant_under_site_reorder():
    """Reordering species + coords together must NOT change the hash."""
    s0 = _llzo_like_structure()
    n = len(s0["species"])
    perm = list(reversed(range(n)))
    s1 = {
        **s0,
        "species": [s0["species"][i] for i in perm],
        "fractional_coords": [s0["fractional_coords"][i] for i in perm],
    }
    assert structure_hash(s0) == structure_hash(s1)


def test_structure_hash_invariant_under_lattice_row_permutation():
    """Reordering lattice vectors MUST be invariant."""
    s0 = _llzo_like_structure()
    s1 = {
        **s0,
        "lattice_vectors": [
            s0["lattice_vectors"][2],
            s0["lattice_vectors"][0],
            s0["lattice_vectors"][1],
        ],
    }
    assert structure_hash(s0) == structure_hash(s1)


def test_structure_hash_sensitive_to_perturbation():
    """Perturbing ONE coordinate by 1e-2 (well above tolerance) MUST change hash."""
    s0 = _llzo_like_structure()
    s1 = {
        **s0,
        "fractional_coords": [
            [c[0] + 0.01, c[1], c[2]] if i == 0 else c
            for i, c in enumerate(s0["fractional_coords"])
        ],
    }
    assert structure_hash(s0) != structure_hash(s1)


def test_structure_hash_invariant_under_subtolerance_perturbation():
    """Perturbing by less than coord_tol (1e-5) MUST NOT change hash."""
    s0 = _llzo_like_structure()
    s1 = {
        **s0,
        "fractional_coords": [
            [c[0] + 1e-7, c[1], c[2]] for c in s0["fractional_coords"]
        ],
    }
    assert structure_hash(s0) == structure_hash(s1)


def test_structure_hash_sensitive_to_species_change():
    s0 = _llzo_like_structure()
    s1 = {**s0, "species": ["Li", "Li", "F", "F"]}  # O -> F
    assert structure_hash(s0) != structure_hash(s1)


def test_structure_hash_rejects_mismatched_species_coords():
    bad = {
        "lattice_vectors": [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
        "species": ["Li"],
        "fractional_coords": [[0, 0, 0], [0.5, 0.5, 0.5]],
    }
    with pytest.raises(ValueError):
        structure_hash(bad)


# ----------------------------------------------------------------------------
# Minimal CIF round trip
# ----------------------------------------------------------------------------


# A hand-typed cubic NaCl primitive cell with 8 atoms (rocksalt FCC), good
# enough to exercise the parser.
NACL_CIF = """data_NaCl
_cell_length_a    5.6402
_cell_length_b    5.6402
_cell_length_c    5.6402
_cell_angle_alpha 90.0
_cell_angle_beta  90.0
_cell_angle_gamma 90.0
loop_
_atom_site_type_symbol
_atom_site_fract_x
_atom_site_fract_y
_atom_site_fract_z
Na 0.0  0.0  0.0
Na 0.5  0.5  0.0
Na 0.5  0.0  0.5
Na 0.0  0.5  0.5
Cl 0.5  0.5  0.5
Cl 0.0  0.0  0.5
Cl 0.0  0.5  0.0
Cl 0.5  0.0  0.0
"""


def test_parse_minimal_cif_nacl():
    s = parse_minimal_cif(NACL_CIF)
    assert len(s["species"]) == 8
    assert len(s["fractional_coords"]) == 8
    assert math.isclose(s["lattice_vectors"][0][0], 5.6402, rel_tol=1e-6)
    assert math.isclose(s["lattice_vectors"][1][1], 5.6402, rel_tol=1e-6)


def test_cif_hash_from_text_round_trip_invariant():
    """Adding a unit translation to every coord in the CIF must NOT change hash."""
    s_a = parse_minimal_cif(NACL_CIF)
    h_a = structure_hash(s_a)

    # Manually translate every coord by +1.0 and re-hash via structure_hash.
    s_b = {
        **s_a,
        "fractional_coords": [
            [c + 1.0 for c in coord] for coord in s_a["fractional_coords"]
        ],
    }
    h_b = structure_hash(s_b)
    assert h_a == h_b


def test_cif_hash_from_text_matches_explicit_structure_hash():
    s_a = parse_minimal_cif(NACL_CIF)
    h_explicit = structure_hash(s_a)
    h_via_cif = cif_hash_from_text(NACL_CIF)
    assert h_explicit == h_via_cif


def test_parse_minimal_cif_rejects_no_cell_params():
    with pytest.raises(ValueError):
        parse_minimal_cif("data_x\nloop_\n_atom_site_type_symbol\n_atom_site_fract_x\n")


def test_parse_minimal_cif_rejects_no_atoms():
    bad = """data_x
_cell_length_a 1.0
_cell_length_b 1.0
_cell_length_c 1.0
_cell_angle_alpha 90.0
_cell_angle_beta  90.0
_cell_angle_gamma 90.0
"""
    with pytest.raises(ValueError):
        parse_minimal_cif(bad)


def test_parse_minimal_cif_handles_uncertainty_in_value():
    """CIFs sometimes write ``5.4(2)`` where 2 is the uncertainty digit."""
    cif_with_uncert = """data_x
_cell_length_a 5.4(2)
_cell_length_b 5.4(2)
_cell_length_c 5.4(2)
_cell_angle_alpha 90.0
_cell_angle_beta  90.0
_cell_angle_gamma 90.0
loop_
_atom_site_type_symbol
_atom_site_fract_x
_atom_site_fract_y
_atom_site_fract_z
Na 0.0 0.0 0.0
"""
    s = parse_minimal_cif(cif_with_uncert)
    assert math.isclose(s["lattice_vectors"][0][0], 5.4, rel_tol=1e-6)
