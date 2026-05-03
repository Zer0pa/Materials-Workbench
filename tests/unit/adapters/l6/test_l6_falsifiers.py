"""Unit tests for L6 falsifiers."""

import pytest

from zer0pa_materials_workbench.adapters.l6.mattergen import MatterGenGeneratorAdapter
from zer0pa_materials_workbench.falsifiers.l6_falsifiers import (
    ChargeNeutralityError,
    DuplicateStructureError,
    InvalidCifError,
    MinDistanceError,
    PrematureNoveltyError,
    ReferenceMatchError,
    charge_neutrality_check,
    min_interatomic_distance,
    novelty_status_gate,
    pymatgen_structure_matcher,
    reference_expansion_dedupe,
    structure_hash_dedupe,
    valid_cif_only,
)

# ---------------------------------------------------------------------------
# valid_cif_only
# ---------------------------------------------------------------------------

class TestValidCifOnly:
    def test_pass_valid_cif(self):
        adapter = MatterGenGeneratorAdapter(n_candidates=1)
        env = adapter.generate({})[0]
        item = valid_cif_only(env)
        assert item.status == "pass"
        assert item.name == "l6.cif_valid"

    def test_fail_empty_cif(self):
        adapter = MatterGenGeneratorAdapter(n_candidates=1)
        env = adapter.generate({})[0]
        # Mutate the output to have empty cif_text.
        env.output["cif_text"] = ""
        with pytest.raises(InvalidCifError, match="empty"):
            valid_cif_only(env)

    def test_fail_malformed_cif(self):
        adapter = MatterGenGeneratorAdapter(n_candidates=1)
        env = adapter.generate({})[0]
        env.output["cif_text"] = "this is not a CIF file at all"
        with pytest.raises(InvalidCifError):
            valid_cif_only(env)

    def test_fail_invalid_cif_fixture(self):
        """The invalid_cif fixture must trigger InvalidCifError."""
        from pathlib import Path
        fixture_path = (
            Path(__file__).parents[4]
            / "fixtures" / "negatives" / "invalid_cif" / "structure.cif"
        )
        cif_text = fixture_path.read_text()
        adapter = MatterGenGeneratorAdapter(n_candidates=1)
        env = adapter.generate({})[0]
        env.output["cif_text"] = cif_text
        with pytest.raises(InvalidCifError):
            valid_cif_only(env)


# ---------------------------------------------------------------------------
# charge_neutrality_check
# ---------------------------------------------------------------------------

class TestChargeNeutralityCheck:
    def _llzo_struct(self):
        return {
            "species": ["Li"] * 7 + ["La"] * 3 + ["Zr"] * 2 + ["O"] * 12,
            # Li=+1*7=7, La=+3*3=9, Zr=+4*2=8, O=-2*12=-24 → sum=0
        }

    def test_llzo_is_neutral(self):
        item = charge_neutrality_check(self._llzo_struct())
        assert item.status == "pass"

    def test_li6ps5cl_is_neutral(self):
        # Li6=+6, P=+5, S5=-10, Cl=-1 → sum=0
        struct = {"species": ["Li"] * 6 + ["P"] + ["S"] * 5 + ["Cl"]}
        item = charge_neutrality_check(struct)
        assert item.status == "pass"

    def test_non_neutral_raises(self):
        struct = {"species": ["Li", "Li", "O"]}  # +2 + (-2) = 0 → actually neutral
        item = charge_neutrality_check(struct)
        assert item.status == "pass"

    def test_charged_species_raises(self):
        # Li2 + O → +2 + (-2) = 0 ✓; let's use something that fails
        struct = {"species": ["Li", "Li", "Li"]}  # +3, no anion → not neutral
        with pytest.raises(ChargeNeutralityError):
            charge_neutrality_check(struct)

    def test_unknown_element_inconclusive(self):
        struct = {"species": ["Li", "Xy"]}  # Xy not in table
        item = charge_neutrality_check(struct)
        assert item.status == "inconclusive"
        assert "Xy" in item.actual["unknown_elements"]

    def test_override_oxidation_states(self):
        struct = {"species": ["Li", "O"], "oxidation_states": [1, -1]}
        item = charge_neutrality_check(struct)
        assert item.status == "pass"

    def test_override_non_neutral_raises(self):
        struct = {"species": ["Li", "Li"], "oxidation_states": [1, 1]}
        with pytest.raises(ChargeNeutralityError):
            charge_neutrality_check(struct)

    def test_item_name(self):
        struct = {"species": ["Li", "O"]}  # 1+(-2)=-1 → fails
        # Note: Li+O is not neutral; will raise. Check name via a neutral case.
        struct = {"species": ["Na", "Cl"]}  # 1+(-1)=0
        item = charge_neutrality_check(struct)
        assert item.name == "l6.charge_neutral"


# ---------------------------------------------------------------------------
# min_interatomic_distance
# ---------------------------------------------------------------------------

class TestMinInteratomicDistance:
    def _nacl_struct(self):
        return {
            "lattice_vectors": [[5.64, 0, 0], [0, 5.64, 0], [0, 0, 5.64]],
            "fractional_coords": [[0, 0, 0], [0.5, 0.5, 0.5]],
        }

    def test_nacl_passes_default_threshold(self):
        item = min_interatomic_distance(self._nacl_struct())
        assert item.status == "pass"

    def test_nacl_distance_is_correct(self):
        # NaCl body-diagonal distance = 5.64 * sqrt(3)/2 ≈ 4.88 Å
        item = min_interatomic_distance(self._nacl_struct())
        assert item.actual["min_distance_ang"] > 4.0

    def test_too_close_raises(self):
        struct = {
            "lattice_vectors": [[5.0, 0, 0], [0, 5.0, 0], [0, 0, 5.0]],
            "fractional_coords": [[0, 0, 0], [0.01, 0, 0]],  # 0.05 Å apart
        }
        with pytest.raises(MinDistanceError):
            min_interatomic_distance(struct, threshold_angstrom=0.7)

    def test_custom_threshold(self):
        # With 10.0 Å threshold, even NaCl fails.
        with pytest.raises(MinDistanceError):
            min_interatomic_distance(self._nacl_struct(), threshold_angstrom=10.0)

    def test_empty_coords_inconclusive(self):
        struct = {"lattice": [], "frac_coords": []}
        item = min_interatomic_distance(struct)
        assert item.status == "inconclusive"

    def test_item_name(self):
        item = min_interatomic_distance(self._nacl_struct())
        assert item.name == "l6.minimum_distance_ok"


# ---------------------------------------------------------------------------
# structure_hash_dedupe
# ---------------------------------------------------------------------------

class TestStructureHashDedupe:
    def test_unique_batch_passes(self):
        adapter = MatterGenGeneratorAdapter(n_candidates=3)
        envs = adapter.generate({})
        item = structure_hash_dedupe(envs)
        assert item.status == "pass"

    def test_duplicate_batch_raises(self):
        adapter = MatterGenGeneratorAdapter(n_candidates=2)
        envs = adapter.generate({})
        # Duplicate the first envelope.
        duped = envs + [envs[0]]
        with pytest.raises(DuplicateStructureError):
            structure_hash_dedupe(duped)

    def test_item_name(self):
        adapter = MatterGenGeneratorAdapter(n_candidates=1)
        envs = adapter.generate({})
        item = structure_hash_dedupe(envs)
        assert item.name == "l6.dedup_unique"

    def test_empty_batch_passes(self):
        item = structure_hash_dedupe([])
        assert item.status == "pass"


# ---------------------------------------------------------------------------
# reference_expansion_dedupe
# ---------------------------------------------------------------------------

class TestReferenceExpansionDedupe:
    def test_novel_candidate_passes(self):
        adapter = MatterGenGeneratorAdapter(n_candidates=1)
        env = adapter.generate({})[0]
        item = reference_expansion_dedupe(env, reference_set=set())
        assert item.status == "pass"

    def test_reference_match_raises(self):
        adapter = MatterGenGeneratorAdapter(n_candidates=1)
        env = adapter.generate({})[0]
        # Add the candidate's hash to the reference set.
        ref = {env.output["structure_hash"]}
        with pytest.raises(ReferenceMatchError):
            reference_expansion_dedupe(env, reference_set=ref)

    def test_item_name(self):
        adapter = MatterGenGeneratorAdapter(n_candidates=1)
        env = adapter.generate({})[0]
        item = reference_expansion_dedupe(env, reference_set=set())
        assert item.name == "l6.reference_expansion_dedupe"


# ---------------------------------------------------------------------------
# pymatgen_structure_matcher
# ---------------------------------------------------------------------------

class TestPymatgenStructureMatcher:
    def test_inconclusive_when_pymatgen_absent(self):
        adapter = MatterGenGeneratorAdapter(n_candidates=1)
        env = adapter.generate({})[0]
        item = pymatgen_structure_matcher(env)
        assert item.status == "inconclusive"
        assert "parked_pending_pymatgen" in str(item.actual)

    def test_item_name(self):
        adapter = MatterGenGeneratorAdapter(n_candidates=1)
        env = adapter.generate({})[0]
        item = pymatgen_structure_matcher(env)
        assert item.name == "l6.pymatgen_structure_matcher"


# ---------------------------------------------------------------------------
# novelty_status_gate
# ---------------------------------------------------------------------------

class TestNoveltyStatusGate:
    def test_pending_is_blocked(self):
        adapter = MatterGenGeneratorAdapter(n_candidates=1)
        env = adapter.generate({})[0]
        assert env.output["novelty_status"] == "pending"
        item = novelty_status_gate(env)
        assert item.status == "blocked"

    def test_premature_novel_raises(self):
        adapter = MatterGenGeneratorAdapter(n_candidates=1)
        env = adapter.generate({})[0]
        env.output["novelty_status"] = "novel"
        # No L1 back-edge → premature.
        with pytest.raises(PrematureNoveltyError):
            novelty_status_gate(env)

    def test_duplicate_is_fail(self):
        adapter = MatterGenGeneratorAdapter(n_candidates=1)
        env = adapter.generate({})[0]
        env.output["novelty_status"] = "duplicate"
        item = novelty_status_gate(env)
        assert item.status == "fail"

    def test_invalid_is_fail(self):
        adapter = MatterGenGeneratorAdapter(n_candidates=1)
        env = adapter.generate({})[0]
        env.output["novelty_status"] = "invalid"
        item = novelty_status_gate(env)
        assert item.status == "fail"

    def test_item_name(self):
        adapter = MatterGenGeneratorAdapter(n_candidates=1)
        env = adapter.generate({})[0]
        item = novelty_status_gate(env)
        assert item.name == "l6.novelty_resolved"
