"""Falsification-wave test: duplicate_candidate fixture triggers structure_hash_dedupe.

The fixture at fixtures/negatives/duplicate_candidate/ has the same
structure_hash as the LLZO cubic positive fixture. This test verifies:
    1. structure_hash_dedupe raises DuplicateStructureError when a batch
       contains the LLZO cubic hash more than once.
    2. reference_expansion_dedupe raises ReferenceMatchError when the
       candidate matches the LLZO cubic reference hash.
    3. Other L6 falsifiers do NOT trigger.
"""

import json
from pathlib import Path

import pytest

from zer0pa_materials.adapters.l6.mattergen import MatterGenGeneratorAdapter
from zer0pa_materials.falsifiers.l6_falsifiers import (
    DuplicateStructureError,
    InvalidCifError,
    ReferenceMatchError,
    reference_expansion_dedupe,
    structure_hash_dedupe,
    valid_cif_only,
)

_LLZO_CUBIC_HASH = "sha256:d45cb2bfe5e76b86b365e1402e118ed32280049a62345c903558c6cfac04ef19"
_FIXTURE_MANIFEST = (
    Path(__file__).parents[3]
    / "fixtures" / "negatives" / "duplicate_candidate" / "manifest.json"
)
_FIXTURE_CIF = _FIXTURE_MANIFEST.parent / "structure.cif"


@pytest.fixture
def llzo_duplicate_envelope():
    """Envelope whose structure_hash equals the LLZO cubic hash."""
    adapter = MatterGenGeneratorAdapter(n_candidates=1)
    env = adapter.generate({})[0]
    # Directly set to the LLZO cubic hash.
    env.output["structure_hash"] = _LLZO_CUBIC_HASH
    env.output["cif_text"] = _FIXTURE_CIF.read_text()
    return env


@pytest.fixture
def novel_envelope():
    """A genuinely unique envelope (non-zero perturbation)."""
    adapter = MatterGenGeneratorAdapter(n_candidates=2)
    envs = adapter.generate({})
    return envs[1]  # Second candidate has different hash.


class TestDuplicateCandidateFixture:
    def test_structure_hash_dedupe_raises_in_batch(self, llzo_duplicate_envelope, novel_envelope):
        """A batch containing two envelopes with the same hash must raise."""
        # Ensure both have the same hash to trigger.
        novel_envelope.output["structure_hash"] = _LLZO_CUBIC_HASH
        with pytest.raises(DuplicateStructureError):
            structure_hash_dedupe([llzo_duplicate_envelope, novel_envelope])

    def test_reference_expansion_dedupe_raises(self, llzo_duplicate_envelope):
        """The candidate hash matches the LLZO cubic reference → ReferenceMatchError."""
        ref = {_LLZO_CUBIC_HASH}
        with pytest.raises(ReferenceMatchError):
            reference_expansion_dedupe(llzo_duplicate_envelope, reference_set=ref)

    def test_valid_cif_only_does_not_raise(self, llzo_duplicate_envelope):
        """The duplicate fixture CIF is structurally valid."""
        item = valid_cif_only(llzo_duplicate_envelope)
        assert item.status == "pass"

    def test_manifest_negative_falsifier_target(self):
        manifest = json.loads(_FIXTURE_MANIFEST.read_text())
        assert manifest["negative_falsifier_target"] == "duplicate_candidate"

    def test_manifest_hash_equals_llzo_cubic(self):
        manifest = json.loads(_FIXTURE_MANIFEST.read_text())
        assert manifest["structure_hash"] == _LLZO_CUBIC_HASH

    def test_duplicate_in_batch_single_target(self, llzo_duplicate_envelope, novel_envelope):
        """Only structure_hash_dedupe triggers; valid_cif_only must pass."""
        novel_envelope.output["structure_hash"] = _LLZO_CUBIC_HASH
        triggered = []

        try:
            valid_cif_only(llzo_duplicate_envelope)
        except InvalidCifError:
            triggered.append("valid_cif_only")

        try:
            structure_hash_dedupe([llzo_duplicate_envelope, novel_envelope])
        except DuplicateStructureError:
            triggered.append("structure_hash_dedupe")

        assert "structure_hash_dedupe" in triggered
        assert "valid_cif_only" not in triggered


class TestNoveltyStatusGateWithDuplicate:
    """When the candidate is a known duplicate, novelty_status must be 'duplicate' not 'novel'."""

    def test_duplicate_status_is_fail_in_gate(self, llzo_duplicate_envelope):
        from zer0pa_materials.falsifiers.l6_falsifiers import novelty_status_gate
        llzo_duplicate_envelope.output["novelty_status"] = "duplicate"
        item = novelty_status_gate(llzo_duplicate_envelope)
        assert item.status == "fail"

    def test_pending_status_in_gate_before_check(self, llzo_duplicate_envelope):
        from zer0pa_materials.falsifiers.l6_falsifiers import novelty_status_gate
        # Default from generator is "pending".
        llzo_duplicate_envelope.output["novelty_status"] = "pending"
        item = novelty_status_gate(llzo_duplicate_envelope)
        assert item.status == "blocked"
