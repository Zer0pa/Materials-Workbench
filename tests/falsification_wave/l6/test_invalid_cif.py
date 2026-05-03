"""Falsification-wave test: invalid_cif fixture triggers EXACTLY valid_cif_only.

The fixture at fixtures/negatives/invalid_cif/structure.cif is deliberately
malformed. This test verifies:
    1. valid_cif_only raises InvalidCifError on the fixture.
    2. Other L6 falsifiers do NOT trigger on the same envelope.
"""

import json
from pathlib import Path

import pytest

from zer0pa_materials_workbench.adapters.l6.mattergen import MatterGenGeneratorAdapter
from zer0pa_materials_workbench.falsifiers.l6_falsifiers import (
    DuplicateStructureError,
    InvalidCifError,
    charge_neutrality_check,
    structure_hash_dedupe,
    valid_cif_only,
)

_FIXTURE_CIF = (
    Path(__file__).parents[3]
    / "fixtures" / "negatives" / "invalid_cif" / "structure.cif"
)
_FIXTURE_MANIFEST = _FIXTURE_CIF.parent / "manifest.json"


@pytest.fixture
def invalid_cif_envelope():
    """Return an L6 envelope whose cif_text is the invalid_cif fixture."""
    adapter = MatterGenGeneratorAdapter(n_candidates=1)
    env = adapter.generate({})[0]
    env.output["cif_text"] = _FIXTURE_CIF.read_text()
    return env


class TestInvalidCifFixture:
    def test_valid_cif_only_raises(self, invalid_cif_envelope):
        """The fixture must trigger EXACTLY InvalidCifError."""
        with pytest.raises(InvalidCifError):
            valid_cif_only(invalid_cif_envelope)

    def test_charge_neutrality_does_not_raise(self):
        """Charge neutrality checks the structure dict, not the CIF text."""
        struct = {"species": ["Na", "Cl"]}
        item = charge_neutrality_check(struct)
        assert item.status == "pass"

    def test_dedup_does_not_raise_on_single_envelope(self, invalid_cif_envelope):
        """A single envelope never has a duplicate hash."""
        item = structure_hash_dedupe([invalid_cif_envelope])
        assert item.status == "pass"

    def test_single_target_exactly(self, invalid_cif_envelope):
        """Only valid_cif_only must trigger; others must not."""
        triggered = []

        try:
            valid_cif_only(invalid_cif_envelope)
        except InvalidCifError:
            triggered.append("valid_cif_only")

        # structure_hash_dedupe on a single-element list never triggers.
        try:
            structure_hash_dedupe([invalid_cif_envelope])
        except DuplicateStructureError:
            triggered.append("structure_hash_dedupe")

        assert triggered == ["valid_cif_only"], (
            f"Expected exactly ['valid_cif_only'] to trigger, got {triggered}"
        )

    def test_manifest_negative_falsifier_target(self):
        manifest = json.loads(_FIXTURE_MANIFEST.read_text())
        assert manifest["negative_falsifier_target"] == "invalid_cif"

    def test_cif_fixture_has_known_flaws(self):
        """Verify the fixture has the documented deliberate flaws."""
        cif_text = _FIXTURE_CIF.read_text()
        # _cell_length_b must not appear as a CIF key (non-comment line).
        non_comment_lines = [ln for ln in cif_text.splitlines() if not ln.strip().startswith("#")]
        assert not any("_cell_length_b" in ln for ln in non_comment_lines), (
            "_cell_length_b must not appear as a CIF key in the invalid fixture"
        )
        # Data rows have fewer tokens than declared columns.
        assert "Na 0.000" in cif_text
