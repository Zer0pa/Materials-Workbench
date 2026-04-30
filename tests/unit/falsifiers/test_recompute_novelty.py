"""Adversarial tests: L6 novelty re-dedupe (Wave D hardened gate 3).

Boundary
--------
Research infrastructure for in silico materials science discovery. Outputs are
research artifacts. No regulatory certification claims. No clinical or
human-subject use. ITAR / weapons applications are out of scope (Meta UMA
Acceptable Use Policy and operator policy).

Discipline
----------
The OLD ``novelty_status_gate`` accepts ``output.novelty_status == "novel"``
as long as a single L1 back-edge exists; it trusts the field. A buggy
adapter can paint that label on a candidate that already lives in
Materials Project / JARVIS / Alexandria / GNoME / OPTIMADE.

The NEW ``novelty_status_gate_recomputed`` ignores the claim and re-runs
the dedupe pipeline:

1. Recompute structure_hash from the CIF text in ``output.cif_text``.
2. Match against the ``reference_set`` (per-test fixture).
3. Match against the per-batch sibling envelopes.
4. Confirm L1 + ionic + L2 back-edges are all present.
"""

from __future__ import annotations

from zer0pa_materials.envelope.hashing import structure_hash
from zer0pa_materials.falsifiers.l6_falsifiers import (
    novelty_status_gate_recomputed,
    recompute_novelty,
)
from zer0pa_materials.falsifiers.raw_evidence import llzo_cubic_reference_structure


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _llzo_envelope(claim: str = "novel") -> dict:
    """Envelope claiming novelty but actually containing the LLZO reference."""
    structure = llzo_cubic_reference_structure()
    # Recompute the hash so the claim and the reference set share a target.
    return {
        "candidate_id": "candidate:test/llzo-forged-novel",
        "layer": "L6",
        "output": {
            "structure": structure,
            "novelty_status": claim,
            # A buggy adapter could ALSO paint a fake structure_hash;
            # the recompute ignores it.
            "structure_hash": "sha256:" + "9" * 64,
        },
        "back_edges": [
            {"layer": "L1", "audit_record_id": "audit:run/X/L1"},
            {"layer": "ionic", "audit_record_id": "audit:run/X/ionic"},
            {"layer": "L2", "audit_record_id": "audit:run/X/L2"},
        ],
    }


def _novel_envelope(claim: str = "novel") -> dict:
    """A genuinely novel structure not in the reference set."""
    return {
        "candidate_id": "candidate:test/genuinely-novel",
        "layer": "L6",
        "output": {
            "structure": {
                "lattice_vectors": [[3.0, 0.0, 0.0], [0.0, 3.0, 0.0], [0.0, 0.0, 3.0]],
                "species": ["Li", "F"],
                "fractional_coords": [[0.0, 0.0, 0.0], [0.5, 0.5, 0.5]],
            },
            "novelty_status": claim,
        },
        "back_edges": [
            {"layer": "L1", "audit_record_id": "audit:run/Y/L1"},
            {"layer": "ionic", "audit_record_id": "audit:run/Y/ionic"},
            {"layer": "L2", "audit_record_id": "audit:run/Y/L2"},
        ],
    }


def _reference_set_with_llzo() -> set[str]:
    """Reference set containing the LLZO reference structure hash."""
    return {structure_hash(llzo_cubic_reference_structure())}


# ---------------------------------------------------------------------------
# Old shape — what the prior gate would accept
# ---------------------------------------------------------------------------


def _old_check_novelty(envelope: dict) -> bool:
    """Mimic the trust-the-field shape of the original gate.

    Returns True (passes) when:
      * ``output.novelty_status == "novel"``, AND
      * at least one L1 back-edge exists.

    This is roughly what the original ``novelty_status_gate`` does
    minus the dedupe pipeline.
    """
    output = envelope.get("output") or {}
    novelty = output.get("novelty_status")
    if novelty != "novel":
        return False
    back_edges = envelope.get("back_edges") or []
    return any(
        be.get("layer") == "L1"
        for be in back_edges
        if isinstance(be, dict)
    )


# ---------------------------------------------------------------------------
# Test 1: forged novelty — structure is in the reference set
# ---------------------------------------------------------------------------


class TestForgedNoveltyOnReferenceMatch:
    """Adapter claims novelty=novel for an LLZO-cubic structure already in
    the reference set."""

    def test_old_gate_accepts_forged_envelope(self):
        env = _llzo_envelope(claim="novel")
        # Old shape-only check: novelty=novel + L1 back-edge → "pass".
        assert _old_check_novelty(env), (
            "old gate accepts the forged label; this is the weakness "
            "Wave D fixes"
        )

    def test_recompute_returns_duplicate(self):
        env = _llzo_envelope(claim="novel")
        re = recompute_novelty(env, reference_set=_reference_set_with_llzo())
        assert re["status"] == "duplicate"
        assert re["duplicate_of"] == "reference_set"

    def test_new_gate_fails_forged_envelope(self):
        env = _llzo_envelope(claim="novel")
        item = novelty_status_gate_recomputed(
            env, reference_set=_reference_set_with_llzo()
        )
        assert item.status == "fail"
        assert item.actual["recomputed"] == "duplicate"
        assert item.actual["claim"] == "novel"


# ---------------------------------------------------------------------------
# Test 2: forged novelty — structure matches a batch sibling
# ---------------------------------------------------------------------------


class TestForgedNoveltyOnBatchSibling:
    """Two candidates in the same batch have identical structures.

    The "winner" claims novelty=novel; the recompute spots the batch
    duplicate.
    """

    def test_new_gate_fails_when_batch_sibling_matches(self):
        env_winner = _llzo_envelope(claim="novel")
        env_winner["candidate_id"] = "candidate:test/winner"
        env_loser = _llzo_envelope(claim="duplicate")
        env_loser["candidate_id"] = "candidate:test/loser"
        # The reference set is empty here — the duplicate is in the batch.
        item = novelty_status_gate_recomputed(
            env_winner, reference_set=set(), batch_envelopes=[env_loser]
        )
        assert item.status == "fail"
        assert item.actual["recomputed"] == "duplicate"


# ---------------------------------------------------------------------------
# Test 3: clean novel candidate passes both
# ---------------------------------------------------------------------------


class TestGenuineNoveltyPasses:
    def test_old_gate_accepts(self):
        env = _novel_envelope(claim="novel")
        assert _old_check_novelty(env)

    def test_new_gate_passes(self):
        env = _novel_envelope(claim="novel")
        item = novelty_status_gate_recomputed(
            env, reference_set=_reference_set_with_llzo()
        )
        assert item.status == "pass"
        assert item.actual["recomputed"] == "novel"


# ---------------------------------------------------------------------------
# Test 4: missing back-edges — even a structurally-novel candidate must
#         have all three back-edges before claiming novel
# ---------------------------------------------------------------------------


class TestMissingBackEdges:
    """Candidate is structurally novel but only has L1 back-edge.

    Old gate accepts (it only checks for L1). New gate requires L1 +
    ionic + L2.
    """

    def _envelope(self) -> dict:
        env = _novel_envelope(claim="novel")
        # Trim back-edges to just L1.
        env["back_edges"] = [
            {"layer": "L1", "audit_record_id": "audit:run/Z/L1"}
        ]
        return env

    def test_old_gate_accepts(self):
        assert _old_check_novelty(self._envelope())

    def test_new_gate_fails_with_missing_back_edges(self):
        item = novelty_status_gate_recomputed(
            self._envelope(), reference_set=set()
        )
        assert item.status == "fail"
        # The missing back-edges should mention ionic and L2.
        missing = item.actual.get("missing_back_edges", [])
        assert "ionic" in missing
        assert "L2" in missing


# ---------------------------------------------------------------------------
# Test 5: invalid CIF — recompute is "invalid"
# ---------------------------------------------------------------------------


class TestInvalidStructure:
    def test_invalid_structure_hash_recompute_fails(self):
        env = {
            "candidate_id": "candidate:test/invalid",
            "layer": "L6",
            "output": {
                # Empty structure dict — recompute returns None.
                "structure_hash": "sha256:" + "f" * 64,
                "novelty_status": "novel",
            },
            "back_edges": [],
        }
        item = novelty_status_gate_recomputed(env, reference_set=set())
        assert item.status == "fail"
        assert item.actual["recomputed"] == "invalid"
