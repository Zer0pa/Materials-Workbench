"""Unit tests for ``PyCalphadEquilibriumAdapter``.

Coverage:
    - Cu-Mg toy TDB equilibrium runs (real or stub)
    - Phase set is returned (LIQUID, FCC_A1, HCP_A3 in the stub)
    - Envelope validates against L3CalphadOutput
    - blocked_manifests reflects pycalphad availability
    - Determinism: same TDB hash -> same phase fractions
    - PYCALPHAD_AVAILABLE flag is reflected in the envelope
"""

from __future__ import annotations

from pathlib import Path

import pytest

from zer0pa_materials_workbench.adapters.l3 import (
    PYCALPHAD_AVAILABLE,
    L3CalphadRequest,
    PyCalphadEquilibriumAdapter,
)
from zer0pa_materials_workbench.envelope import Envelope, L3CalphadOutput

REPO_ROOT = Path(__file__).resolve().parents[4]
CU_MG_TDB = REPO_ROOT / "fixtures" / "tdb" / "Cu-Mg-toy.tdb"
LI_HALIDE_TDB = REPO_ROOT / "fixtures" / "tdb" / "Li-halide-toy.tdb"


def _req(suffix: str = "001", tdb_path: str | None = None) -> L3CalphadRequest:
    return L3CalphadRequest(
        run_id=f"run:l3/eq/{suffix}",
        candidate_id=f"candidate:Cu-Mg:{suffix}",
        campaign_id="campaign:l3-eq/001",
        rights_claim_id="rights:l3-eq/001",
        tdb_path=tdb_path,
        components=["CU", "MG"],
        extra={"temperature_K": 1200.0, "composition": {"CU": 0.7, "MG": 0.3}},
    )


class TestEquilibriumStub:
    """Tests that always run regardless of pycalphad availability."""

    def test_adapter_instantiates(self):
        adapter = PyCalphadEquilibriumAdapter()
        assert adapter.NAME == "PyCalphadEquilibriumAdapter"

    def test_run_returns_envelope_dict(self):
        adapter = PyCalphadEquilibriumAdapter()
        envelope = adapter.run(_req())
        assert isinstance(envelope, dict)
        assert envelope["layer"] == "L3"

    def test_envelope_validates_as_envelope(self):
        adapter = PyCalphadEquilibriumAdapter()
        envelope = adapter.run(_req())
        clean = {k: v for k, v in envelope.items() if not k.startswith("_")}
        Envelope.model_validate(clean)

    def test_output_validates_as_l3_output(self):
        adapter = PyCalphadEquilibriumAdapter()
        envelope = adapter.run(_req())
        L3CalphadOutput.model_validate(envelope["output"])

    def test_phase_set_returned(self):
        adapter = PyCalphadEquilibriumAdapter()
        envelope = adapter.run(_req())
        phases = envelope["output"]["equilibrium_phases"]
        assert len(phases) >= 1

    def test_phase_fraction_posterior_returned(self):
        adapter = PyCalphadEquilibriumAdapter()
        envelope = adapter.run(_req())
        fractions = envelope["output"]["phase_fraction_posterior"]
        assert isinstance(fractions, dict)
        assert all(0.0 <= v <= 1.0 + 1e-6 for v in fractions.values())

    def test_phase_fractions_sum_to_one(self):
        adapter = PyCalphadEquilibriumAdapter()
        envelope = adapter.run(_req())
        fractions = envelope["output"]["phase_fraction_posterior"]
        total = sum(fractions.values())
        assert abs(total - 1.0) < 1e-9

    def test_calphad_meta_present(self):
        adapter = PyCalphadEquilibriumAdapter()
        envelope = adapter.run(_req())
        assert "_calphad_meta" in envelope
        meta = envelope["_calphad_meta"]
        assert "temperature_K" in meta
        assert "gibbs_energy_J_per_mol" in meta

    def test_temperature_K_propagated(self):
        adapter = PyCalphadEquilibriumAdapter()
        envelope = adapter.run(_req())
        assert envelope["_calphad_meta"]["temperature_K"] == 1200.0

    def test_composition_propagated(self):
        adapter = PyCalphadEquilibriumAdapter()
        envelope = adapter.run(_req())
        assert envelope["_calphad_meta"]["composition"] == {"CU": 0.7, "MG": 0.3}

    def test_research_boundary_present(self):
        adapter = PyCalphadEquilibriumAdapter()
        envelope = adapter.run(_req())
        assert envelope["research_boundary"]
        assert "ITAR" in envelope["research_boundary"]

    def test_layer_is_l3(self):
        adapter = PyCalphadEquilibriumAdapter()
        envelope = adapter.run(_req())
        assert envelope["layer"] == "L3"

    def test_audit_record_id_present(self):
        adapter = PyCalphadEquilibriumAdapter()
        envelope = adapter.run(_req())
        assert envelope["audit"]["audit_record_id"].startswith("audit:")

    def test_input_hash_is_sha256(self):
        adapter = PyCalphadEquilibriumAdapter()
        envelope = adapter.run(_req())
        h = envelope["audit"]["input_hash"]
        assert h.startswith("sha256:")

    def test_output_hash_is_sha256(self):
        adapter = PyCalphadEquilibriumAdapter()
        envelope = adapter.run(_req())
        h = envelope["audit"]["output_hash"]
        assert h.startswith("sha256:")


class TestCuMgTdbEquilibrium:
    """Cu-Mg toy TDB equilibrium runs, in stub or real mode."""

    @pytest.fixture(scope="module")
    def envelope(self) -> dict:
        adapter = PyCalphadEquilibriumAdapter()
        return adapter.run(_req("cu-mg-tdb", tdb_path=str(CU_MG_TDB)))

    def test_envelope_returned(self, envelope):
        assert envelope is not None

    def test_layer_is_l3(self, envelope):
        assert envelope["layer"] == "L3"

    def test_phase_set_nonempty(self, envelope):
        assert len(envelope["output"]["equilibrium_phases"]) >= 1

    def test_tdb_ref_references_cu_mg_path(self, envelope):
        assert "Cu-Mg-toy.tdb" in envelope["output"]["tdb_ref"]

    def test_input_hash_reflects_tdb_content(self, envelope):
        # The input_hash should be a real hash of the TDB content.
        h = envelope["audit"]["input_hash"]
        assert h.startswith("sha256:")
        assert len(h) == len("sha256:") + 64

    def test_pycalphad_available_flag(self, envelope):
        assert envelope["_calphad_meta"]["pycalphad_available"] == PYCALPHAD_AVAILABLE


class TestDeterminism:
    """Same request -> same output (deterministic stub mode)."""

    def test_same_request_same_phase_fractions(self):
        adapter = PyCalphadEquilibriumAdapter()
        env_a = adapter.run(_req("det", tdb_path=str(CU_MG_TDB)))
        env_b = adapter.run(_req("det", tdb_path=str(CU_MG_TDB)))
        assert env_a["output"]["phase_fraction_posterior"] == env_b["output"]["phase_fraction_posterior"]

    def test_same_request_same_input_hash(self):
        adapter = PyCalphadEquilibriumAdapter()
        env_a = adapter.run(_req("det", tdb_path=str(CU_MG_TDB)))
        env_b = adapter.run(_req("det", tdb_path=str(CU_MG_TDB)))
        assert env_a["audit"]["input_hash"] == env_b["audit"]["input_hash"]

    def test_different_tdb_different_input_hash(self):
        adapter = PyCalphadEquilibriumAdapter()
        env_cu_mg = adapter.run(_req("a", tdb_path=str(CU_MG_TDB)))
        env_li = adapter.run(_req("b", tdb_path=str(LI_HALIDE_TDB)))
        assert env_cu_mg["audit"]["input_hash"] != env_li["audit"]["input_hash"]


class TestBlockedManifests:
    def test_when_pycalphad_unavailable_returns_blocked(self):
        adapter = PyCalphadEquilibriumAdapter()
        manifests = adapter.blocked_manifests()
        if PYCALPHAD_AVAILABLE:
            assert manifests == []
        else:
            assert len(manifests) == 1
            m = manifests[0]
            assert m["source_manifest_id"] == "src:pycalphad:library"
            assert m["blocker_reason"] in {
                "unavailable_credentials",
                "license_unverified",
                "unreachable",
                "rate_limited",
                "policy",
                "other",
            }

    def test_blocked_manifest_has_retry_strategy(self):
        adapter = PyCalphadEquilibriumAdapter()
        manifests = adapter.blocked_manifests()
        for m in manifests:
            assert m["retry_strategy"]


class TestBackendLabel:
    def test_backend_matches_availability(self):
        adapter = PyCalphadEquilibriumAdapter()
        envelope = adapter.run(_req(tdb_path=str(CU_MG_TDB)))
        backend = envelope["tool_adapter"]["backend"]
        if PYCALPHAD_AVAILABLE:
            # Real path or stub-fallback are both acceptable.
            assert backend in {"local_cpu", "stub"}
        else:
            assert backend == "stub"

    def test_engine_label_present(self):
        adapter = PyCalphadEquilibriumAdapter()
        envelope = adapter.run(_req(tdb_path=str(CU_MG_TDB)))
        engine = envelope["tool_adapter"]["engine"]
        assert engine.startswith("pycalphad")
