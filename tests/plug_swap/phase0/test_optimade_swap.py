"""Plug-swap tests: OPTIMADE stub vs mock backend schema parity.

Verifies that the envelope schema shape is identical across all backends
for the OPTIMADE adapter. The real backend is parked; we test stub vs
a second stub call to confirm the adapter contract is stable.
"""

import pytest

from zer0pa_materials_workbench.adapters.phase0.optimade import OptimadeFederatedQueryAdapter
from zer0pa_materials_workbench.envelope.envelope import Envelope


@pytest.fixture
def adapter_a() -> OptimadeFederatedQueryAdapter:
    return OptimadeFederatedQueryAdapter()


@pytest.fixture
def adapter_b() -> OptimadeFederatedQueryAdapter:
    return OptimadeFederatedQueryAdapter(base_url="https://optimade.aflow.org")


class TestOptimadeSwapSchemaParity:
    """PRD §Plug-replaceability: schema must match across backends."""

    def test_top_level_keys_identical(self, adapter_a, adapter_b):
        env_a = adapter_a.query({"elements": ["Li"]}).model_dump(mode="json")
        env_b = adapter_b.query({"elements": ["Li"]}).model_dump(mode="json")
        assert set(env_a.keys()) == set(env_b.keys())

    def test_output_keys_identical(self, adapter_a, adapter_b):
        env_a = adapter_a.query({"elements": ["Li"]}).model_dump(mode="json")
        env_b = adapter_b.query({"elements": ["Li"]}).model_dump(mode="json")
        assert set(env_a["output"].keys()) == set(env_b["output"].keys())

    def test_layer_always_phase0(self, adapter_a, adapter_b):
        for adapter in (adapter_a, adapter_b):
            assert adapter.query({"elements": ["Li"]}).layer == "phase0"

    def test_optimade_version_consistent(self, adapter_a, adapter_b):
        v_a = adapter_a.query({}).output["optimade_version"]
        v_b = adapter_b.query({}).output["optimade_version"]
        assert v_a == v_b == "1.3"

    def test_envelope_round_trips_both(self, adapter_a, adapter_b):
        for adapter in (adapter_a, adapter_b):
            env = adapter.query({"elements": ["La"]})
            env2 = Envelope.model_validate(env.model_dump(mode="json"))
            assert env2.layer == "phase0"

    def test_hit_structure_schema_identical(self, adapter_a, adapter_b):
        hits_a = adapter_a.query({"elements": ["Li"]}).output["optimade_hits"]
        hits_b = adapter_b.query({"elements": ["Li"]}).output["optimade_hits"]
        if hits_a and hits_b:
            assert set(hits_a[0].keys()) == set(hits_b[0].keys())

    def test_schema_json_schema_stable(self):
        """The JSON Schema for phase0 output must not drift between backends."""
        from zer0pa_materials_workbench.envelope.layer_outputs import Phase0Output
        schema = Phase0Output.model_json_schema()
        assert "extracted_properties" in str(schema)
        assert "units_normalised" in str(schema)
        assert "contradictions_blocking" in str(schema)
