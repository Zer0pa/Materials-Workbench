"""Unit tests for LeMatGenBenchEvaluatorAdapter."""

import pytest

from zer0pa_materials_workbench.adapters.l6.diffcsp import DiffCspGeneratorAdapter
from zer0pa_materials_workbench.adapters.l6.lematgen_eval import (
    LeMatGenBenchEvaluatorAdapter,
)
from zer0pa_materials_workbench.adapters.l6.mattergen import MatterGenGeneratorAdapter


@pytest.fixture
def evaluator() -> LeMatGenBenchEvaluatorAdapter:
    return LeMatGenBenchEvaluatorAdapter(reference_hashes=set())


@pytest.fixture
def mg_envelopes():
    adapter = MatterGenGeneratorAdapter(n_candidates=3)
    return adapter.generate({"chemical_system": "Li-La-Zr-O"})


@pytest.fixture
def dc_envelopes():
    adapter = DiffCspGeneratorAdapter(n_candidates=2)
    return adapter.generate({"chemical_system": "Li-P-S-Cl"})


class TestLeMatGenBenchResult:
    def test_empty_batch(self, evaluator):
        result = evaluator.evaluate([])
        assert result.n_total == 0
        assert result.u_score == 0.0
        assert result.n_score == 0.0

    def test_s_always_none(self, evaluator, mg_envelopes):
        result = evaluator.evaluate(mg_envelopes)
        assert result.n_stable is None, "S (stability) must be None — deferred to L1."

    def test_all_unique_when_no_dupes(self, evaluator, mg_envelopes):
        result = evaluator.evaluate(mg_envelopes)
        # MatterGen stub produces unique hashes.
        assert result.n_unique == result.n_total

    def test_u_score_is_fraction(self, evaluator, mg_envelopes):
        result = evaluator.evaluate(mg_envelopes)
        assert 0.0 <= result.u_score <= 1.0

    def test_n_score_is_fraction(self, evaluator, mg_envelopes):
        result = evaluator.evaluate(mg_envelopes)
        assert 0.0 <= result.n_score <= 1.0

    def test_all_novel_vs_empty_reference(self, evaluator, mg_envelopes):
        result = evaluator.evaluate(mg_envelopes)
        assert result.n_novel == result.n_unique

    def test_reference_match_reduces_novelty(self, mg_envelopes):
        # Add the first candidate's hash to the reference set.
        first_hash = mg_envelopes[0].output["structure_hash"]
        evaluator = LeMatGenBenchEvaluatorAdapter(reference_hashes={first_hash})
        result = evaluator.evaluate(mg_envelopes)
        assert result.n_novel == result.n_unique - 1

    def test_duplicate_within_batch_reduces_unique(self, evaluator, mg_envelopes):
        # Add a duplicate by appending the first envelope twice.
        duped = mg_envelopes + [mg_envelopes[0]]
        result = evaluator.evaluate(duped)
        # Total is n+1 but unique is still n.
        assert result.n_unique == len(mg_envelopes)
        assert result.n_total == len(mg_envelopes) + 1

    def test_details_length_matches_input(self, evaluator, mg_envelopes):
        result = evaluator.evaluate(mg_envelopes)
        assert len(result.details) == len(mg_envelopes)

    def test_details_have_required_keys(self, evaluator, mg_envelopes):
        result = evaluator.evaluate(mg_envelopes)
        for d in result.details:
            assert "candidate_id" in d
            assert "structure_hash" in d
            assert "unique_in_batch" in d
            assert "novel_vs_reference" in d
            assert "stable" in d
            assert d["stable"] is None

    def test_cross_adapter_batch(self, evaluator, mg_envelopes, dc_envelopes):
        combined = mg_envelopes + dc_envelopes
        result = evaluator.evaluate(combined)
        assert result.n_total == len(combined)
        assert result.n_unique <= result.n_total

    def test_repr_contains_sun_labels(self, evaluator, mg_envelopes):
        result = evaluator.evaluate(mg_envelopes)
        r = repr(result)
        assert "U=" in r
        assert "N=" in r
        assert "S=None" in r


class TestLeMatGenBenchFixtureHashes:
    """Verify the fixture hash loader works."""

    def test_load_fixture_hashes_returns_set(self):
        from zer0pa_materials_workbench.adapters.l6.lematgen_eval import _load_fixture_hashes
        hashes = _load_fixture_hashes()
        assert isinstance(hashes, set)
        assert len(hashes) >= 5, "Should load at least 5 positive fixture hashes."

    def test_llzo_cubic_hash_in_fixture_set(self):
        from zer0pa_materials_workbench.adapters.l6.lematgen_eval import _load_fixture_hashes
        hashes = _load_fixture_hashes()
        llzo_hash = "sha256:d45cb2bfe5e76b86b365e1402e118ed32280049a62345c903558c6cfac04ef19"
        assert llzo_hash in hashes, "LLZO cubic hash must be in reference set."
