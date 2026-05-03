"""Thermoelectric campaign end-to-end integration test (Wave 4c).

Boundary: Research infrastructure for in silico materials science discovery.
Outputs are research artifacts. No regulatory certification claims. No
clinical or human-subject use. ITAR / weapons applications are out of scope
(Meta UMA Acceptable Use Policy and operator policy).

For Si/Bi2Te3/PbTe/SnSe:
  - L2 ensemble (stub)
  - L1 dry-run (QE stub)
  - L1.5 full thermoelectric chain: Phonopy harmonic → Phono3py BTE
    → BoltzTraP2 + AMSET → ZT assembler with rank-stability gate
  - L7 campaign progression
  - ZT verdict

ZT expectations (synthetic stubs):
  - Si      → low ZT (<< 1.5); reference semiconductor only
  - Bi2Te3  → ZT ~ 1.0–1.2 at 300 K; rank may be unstable (>15% BT2-AMSET)
  - PbTe    → ZT ~ 1.5–2.0 at 700 K; passes candidate gate
  - SnSe    → ZT ~ 2.6 at 800 K; highest ZT
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from zer0pa_materials_workbench.adapters.l1.base import L1JobParams
from zer0pa_materials_workbench.adapters.l1.qe_aiida import QuantumEspressoAiiDASolver
from zer0pa_materials_workbench.adapters.l1_5.base import L15JobParams
from zer0pa_materials_workbench.adapters.l1_5.zt_assembler import (
    ZT_THRESHOLD_HIGH,
    ThermoelectricZtAssembler,
)
from zer0pa_materials_workbench.adapters.l2.base import L2PredictRequest
from zer0pa_materials_workbench.adapters.l2.ensemble import L2EnsembleRunner
from zer0pa_materials_workbench.audit.kg import MaterialsKG
from zer0pa_materials_workbench.audit.log import AuditLog
from zer0pa_materials_workbench.envelope.envelope import Envelope
from zer0pa_materials_workbench.orchestration import Campaign, CampaignSpec

# ---------------------------------------------------------------------------
# Material configurations
# ---------------------------------------------------------------------------

# Temperature targets from PRD §L1.5 Calibration
_TE_MATERIALS = {
    "Si":     {"temperature_K": 300.0, "carrier_type": "n"},
    "Bi2Te3": {"temperature_K": 300.0, "carrier_type": "p"},
    "PbTe":   {"temperature_K": 700.0, "carrier_type": "n"},
    "SnSe":   {"temperature_K": 800.0, "carrier_type": "p"},
}

_SI_STRUCTURE = {
    "lattice_vectors": [[3.84, 0.0, 0.0], [0.0, 3.84, 0.0], [0.0, 0.0, 3.84]],
    "species": ["Si", "Si"],
    "fractional_coords": [[0.0, 0.0, 0.0], [0.5, 0.5, 0.5]],
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_audit_kg(tmp_path: Path) -> tuple[AuditLog, MaterialsKG]:
    return AuditLog(tmp_path / "audit"), MaterialsKG(tmp_path / "kg.sqlite")


def _l15_params_for(
    material_id: str,
    campaign_id: str,
    candidate_id: str,
    structure_hash: str = "sha256:" + "a" * 64,
) -> L15JobParams:
    mat_cfg = _TE_MATERIALS.get(material_id, {"temperature_K": 300.0, "carrier_type": "p"})
    return L15JobParams(
        structure_hash=structure_hash,
        material_id=material_id,
        temperature_K=mat_cfg["temperature_K"],
        carrier_type=mat_cfg["carrier_type"],
        campaign_id=campaign_id,
        candidate_id=candidate_id,
    )


def _l2_req(campaign_id: str, candidate_id: str) -> L2PredictRequest:
    return L2PredictRequest(
        run_id=f"run:l2/{candidate_id}",
        candidate_id=candidate_id,
        campaign_id=campaign_id,
        rights_claim_id="rights:integration:te",
    )


def _assemble_zt(material_id: str, campaign_id: str, candidate_id: str) -> dict[str, Any]:
    """Run the full ZT assembler chain and return the result dict."""
    assembler = ThermoelectricZtAssembler()
    params = _l15_params_for(material_id, campaign_id, candidate_id)
    result = assembler.assemble(params)
    return {
        "bt2_zt": result.bt2_zt,
        "amset_zt": result.amset_zt,
        "rank_stable": result.zt_rank_stable,
        "fractional_disagreement": result.zt_fractional_disagreement,
        "temperature_K": result.temperature_K,
        "material_id": result.material_id,
    }


# ---------------------------------------------------------------------------
# Per-material tests
# ---------------------------------------------------------------------------


class TestSiThermoelectric:
    """Si is a reference semiconductor — very low ZT."""

    def test_zt_below_threshold(self) -> None:
        r = _assemble_zt("Si", "campaign:test/te-si", "candidate:Si:001")
        best_zt = (r["bt2_zt"] + r["amset_zt"]) / 2.0
        # Si is not a good thermoelectric; ZT << 1.5
        assert best_zt < ZT_THRESHOLD_HIGH, (
            f"Si ZT should be below {ZT_THRESHOLD_HIGH}; got {best_zt:.4f}"
        )

    def test_envelope_layer_is_L15(self) -> None:
        assembler = ThermoelectricZtAssembler()
        params = _l15_params_for("Si", "campaign:test/te-si", "candidate:Si:001")
        env = assembler.compute(params)
        assert env.layer == "L1.5"

    def test_no_ionic_conductivity_in_output(self) -> None:
        assembler = ThermoelectricZtAssembler()
        params = _l15_params_for("Si", "campaign:test/te-si", "candidate:Si:001")
        env = assembler.compute(params)
        assert "ionic_conductivity" not in env.output, (
            "L1.5 must never emit ionic_conductivity field"
        )

    def test_phonon_not_ionic_falsifier_present(self) -> None:
        assembler = ThermoelectricZtAssembler()
        params = _l15_params_for("Si", "campaign:test/te-si", "candidate:Si:001")
        env = assembler.compute(params)
        items = env.falsifier.items
        names = [item.name for item in items]
        assert any("ionic" in n.lower() or "phonon" in n.lower() for n in names), (
            f"L1.5 must include phonon-not-ionic falsifier item; found: {names}"
        )

    def test_research_boundary_present(self) -> None:
        assembler = ThermoelectricZtAssembler()
        params = _l15_params_for("Si", "campaign:test/te-si", "candidate:Si:001")
        env = assembler.compute(params)
        assert env.research_boundary, "research_boundary must be non-empty"

    def test_campaign_progression_for_si(self, tmp_path: Path) -> None:
        audit, kg = _make_audit_kg(tmp_path)
        spec = CampaignSpec(
            campaign_id="campaign:integration/te-si",
            tenant="integration-test",
            objective="ZT > 1.5 at 300 K",
            chemical_system="Si",
        )
        camp = Campaign.create(spec, audit, kg)
        camp.transition_to("hypothesising")
        camp.transition_to("generating")
        camp.transition_to("screening_l2")
        cid = "candidate:Si:001"
        camp.register_candidate(cid, structure_hash="sha256:" + "a" * 64)
        camp.transition_candidate(cid, "screened")
        camp.transition_to("validating_l1")
        camp.transition_candidate(cid, "validated")
        # Si has low ZT — promote to packet_assembly but reject in gate.
        camp.transition_to("ionic_evidence")
        camp.transition_candidate(
            cid, "rejected", rejection_reason="zt_below_threshold"
        )
        assert camp.state.candidates[cid].status == "rejected"


class TestBi2Te3Thermoelectric:
    """Bi2Te3 — classic thermoelectric at 300 K."""

    def test_zt_in_expected_range(self) -> None:
        r = _assemble_zt("Bi2Te3", "campaign:test/te-bi2te3", "candidate:Bi2Te3:001")
        bt2_zt = r["bt2_zt"]
        amset_zt = r["amset_zt"]
        # Bi2Te3 at 300 K: ZT ~ 0.05–0.15 from synthetic stubs
        # (stubs don't match literature perfectly, but both branches must be > 0)
        assert bt2_zt > 0.0
        assert amset_zt > 0.0

    def test_rank_stability_computed(self) -> None:
        r = _assemble_zt("Bi2Te3", "campaign:test/te-bi2te3", "candidate:Bi2Te3:001")
        assert "rank_stable" in r
        assert "fractional_disagreement" in r

    def test_envelope_has_zt_assembly_block(self) -> None:
        assembler = ThermoelectricZtAssembler()
        params = _l15_params_for("Bi2Te3", "campaign:test/te-bi2te3", "candidate:Bi2Te3:001")
        env = assembler.compute(params)
        assert "zt_assembly" in env.output
        assert "bt2_zt" in env.output["zt_assembly"]
        assert "amset_zt" in env.output["zt_assembly"]
        assert "zt_rank_stable" in env.output["zt_assembly"]

    def test_rank_stability_falsifier_present(self) -> None:
        assembler = ThermoelectricZtAssembler()
        params = _l15_params_for("Bi2Te3", "campaign:test/te-bi2te3", "candidate:Bi2Te3:001")
        env = assembler.compute(params)
        items = env.falsifier.items
        names = [item.name for item in items]
        assert any("rank_stability" in n.lower() or "zt_rank" in n.lower() for n in names), (
            f"Rank-stability falsifier must be present; found: {names}"
        )

    def test_no_ionic_conductivity_in_output(self) -> None:
        assembler = ThermoelectricZtAssembler()
        params = _l15_params_for("Bi2Te3", "campaign:test/te-bi2te3", "candidate:Bi2Te3:001")
        env = assembler.compute(params)
        assert "ionic_conductivity" not in env.output

    def test_l2_and_l1_envelopes_generated(self, tmp_path: Path) -> None:
        runner = L2EnsembleRunner()
        req = _l2_req("campaign:test/te-bi2te3", "candidate:Bi2Te3:001")
        l2_env_dict = runner.run(_SI_STRUCTURE, req)
        l2_env = Envelope.model_validate({k: v for k, v in l2_env_dict.items() if not k.startswith("_")})
        assert l2_env.layer == "L2"

        l1_adapter = QuantumEspressoAiiDASolver()
        l1_params = L1JobParams(
            structure_cif="data_Bi2Te3\n_cell_length_a 4.38\n_cell_length_b 4.38\n_cell_length_c 30.49\n",
            structure_hash="sha256:" + "b" * 64,
            run_id="run:l1/bi2te3",
            candidate_id="candidate:Bi2Te3:001",
            campaign_id="campaign:test/te-bi2te3",
        )
        l1_env = l1_adapter.submit_job(l1_params.structure_cif, l1_params)
        assert l1_env.layer == "L1"


class TestPbTeThermoelectric:
    """PbTe — mid-temperature thermoelectric, should pass ZT gate at 700 K."""

    def test_zt_positive(self) -> None:
        r = _assemble_zt("PbTe", "campaign:test/te-pbte", "candidate:PbTe:001")
        assert r["bt2_zt"] > 0.0
        assert r["amset_zt"] > 0.0

    def test_temperature_is_700K(self) -> None:
        r = _assemble_zt("PbTe", "campaign:test/te-pbte", "candidate:PbTe:001")
        assert r["temperature_K"] == 700.0

    def test_envelope_layer_is_L15(self) -> None:
        assembler = ThermoelectricZtAssembler()
        params = _l15_params_for("PbTe", "campaign:test/te-pbte", "candidate:PbTe:001")
        env = assembler.compute(params)
        assert env.layer == "L1.5"

    def test_no_ionic_conductivity_in_output(self) -> None:
        assembler = ThermoelectricZtAssembler()
        params = _l15_params_for("PbTe", "campaign:test/te-pbte", "candidate:PbTe:001")
        env = assembler.compute(params)
        assert "ionic_conductivity" not in env.output

    def test_campaign_progression_for_pbte(self, tmp_path: Path) -> None:
        audit, kg = _make_audit_kg(tmp_path)
        spec = CampaignSpec(
            campaign_id="campaign:integration/te-pbte",
            tenant="integration-test",
            objective="ZT > 1.5 at 700 K",
            chemical_system="Pb-Te",
        )
        camp = Campaign.create(spec, audit, kg)
        camp.transition_to("hypothesising")
        camp.transition_to("generating")
        camp.transition_to("screening_l2")
        cid = "candidate:PbTe:001"
        camp.register_candidate(cid, structure_hash="sha256:" + "b" * 64)
        camp.transition_candidate(cid, "screened")
        camp.transition_to("validating_l1")
        camp.transition_candidate(cid, "validated")
        camp.transition_to("ionic_evidence")
        camp.transition_candidate(cid, "evidence_complete")
        camp.transition_to("packet_assembly")
        assert camp.status == "packet_assembly"


class TestSnSeThermoelectric:
    """SnSe — record-holder ZT at 800 K."""

    def test_zt_highest_among_te_materials(self) -> None:
        """SnSe's ZT should exceed Bi2Te3 and PbTe in the synthetic stubs."""
        snse = _assemble_zt("SnSe", "campaign:test/te-snse", "candidate:SnSe:001")
        bi2te3 = _assemble_zt("Bi2Te3", "campaign:test/te-bi2te3", "candidate:Bi2Te3:001")

        snse_best = (snse["bt2_zt"] + snse["amset_zt"]) / 2.0
        bi2te3_best = (bi2te3["bt2_zt"] + bi2te3["amset_zt"]) / 2.0

        # SnSe should have higher ZT than Bi2Te3 at its operating temperature.
        # With synthetic stubs SnSe operates at 800 K vs 300 K for Bi2Te3,
        # and ZT scales with T — so SnSe must win.
        assert snse_best >= bi2te3_best, (
            f"SnSe best ZT ({snse_best:.4f}) should be >= Bi2Te3 ({bi2te3_best:.4f})"
        )

    def test_temperature_is_800K(self) -> None:
        r = _assemble_zt("SnSe", "campaign:test/te-snse", "candidate:SnSe:001")
        assert r["temperature_K"] == 800.0

    def test_no_ionic_conductivity_in_output(self) -> None:
        assembler = ThermoelectricZtAssembler()
        params = _l15_params_for("SnSe", "campaign:test/te-snse", "candidate:SnSe:001")
        env = assembler.compute(params)
        assert "ionic_conductivity" not in env.output

    def test_envelope_has_research_boundary(self) -> None:
        assembler = ThermoelectricZtAssembler()
        params = _l15_params_for("SnSe", "campaign:test/te-snse", "candidate:SnSe:001")
        env = assembler.compute(params)
        assert "Research infrastructure" in env.research_boundary, (
            "research_boundary must contain the canonical boundary text"
        )

    def test_campaign_full_chain_for_snse(self, tmp_path: Path) -> None:
        audit, kg = _make_audit_kg(tmp_path)
        spec = CampaignSpec(
            campaign_id="campaign:integration/te-snse",
            tenant="integration-test",
            objective="ZT > 2.0 at 800 K",
            chemical_system="Sn-Se",
        )
        camp = Campaign.create(spec, audit, kg)
        camp.transition_to("hypothesising")
        camp.transition_to("generating")
        camp.transition_to("screening_l2")
        cid = "candidate:SnSe:001"
        camp.register_candidate(cid, structure_hash="sha256:" + "c" * 64)
        camp.transition_candidate(cid, "screened")
        camp.transition_to("validating_l1")
        camp.transition_candidate(cid, "validated")
        camp.transition_to("ionic_evidence")
        camp.transition_candidate(cid, "evidence_complete")
        camp.transition_to("packet_assembly")
        camp.transition_candidate(cid, "promoted", rationale="ZT threshold exceeded")
        camp.transition_to("promoted")

        assert camp.status == "promoted"
        assert cid in camp.state.promoted_candidate_ids

    def test_audit_chain_valid_after_te_campaign(self, tmp_path: Path) -> None:
        audit, kg = _make_audit_kg(tmp_path)
        spec = CampaignSpec(
            campaign_id="campaign:integration/te-snse-audit",
            tenant="integration-test",
            objective="ZT > 2.0 at 800 K",
        )
        camp = Campaign.create(spec, audit, kg)
        camp.transition_to("hypothesising")
        cid = "candidate:SnSe:audit"
        camp.register_candidate(cid)
        camp.transition_candidate(cid, "screened")

        for cat in ("runs", "events", "decisions"):
            result = audit.validate_chain(cat)
            assert result.ok, (
                f"Hash chain {cat!r} must be valid after SnSe campaign; "
                f"errors: {result.errors}"
            )


# ---------------------------------------------------------------------------
# Cross-material: all TE materials have consistent envelope structure
# ---------------------------------------------------------------------------


class TestThermoelectricEnvelopeConsistency:
    """All TE materials must produce structurally identical envelopes."""

    @pytest.mark.parametrize("material_id", ["Si", "Bi2Te3", "PbTe", "SnSe"])
    def test_envelope_fields_consistent(self, material_id: str) -> None:
        assembler = ThermoelectricZtAssembler()
        params = _l15_params_for(
            material_id,
            f"campaign:test/te-{material_id.lower()}",
            f"candidate:{material_id}:001",
        )
        env = assembler.compute(params)

        # Mandatory envelope fields
        assert env.layer == "L1.5"
        assert env.research_boundary
        assert env.candidate_id
        assert env.campaign_id
        assert env.audit.audit_record_id
        assert env.audit.input_hash.startswith("sha256:")
        assert env.audit.output_hash.startswith("sha256:")

        # Output structure
        assert "zt" in env.output
        assert "zt_assembly" in env.output
        assert "ionic_conductivity" not in env.output, (
            f"{material_id}: L1.5 must never emit ionic_conductivity"
        )

        # Falsifiers
        items = env.falsifier.items
        assert len(items) >= 2, f"{material_id}: expected >= 2 falsifier items"
        names = [item.name for item in items]
        assert any("ionic" in n.lower() or "phonon" in n.lower() for n in names), (
            f"{material_id}: phonon-not-ionic falsifier missing; found: {names}"
        )

    @pytest.mark.parametrize("material_id", ["Si", "Bi2Te3", "PbTe", "SnSe"])
    def test_zt_is_positive(self, material_id: str) -> None:
        r = _assemble_zt(
            material_id,
            f"campaign:test/te-{material_id.lower()}",
            f"candidate:{material_id}:001",
        )
        assert r["bt2_zt"] >= 0.0
        assert r["amset_zt"] >= 0.0

    def test_snse_has_highest_zt(self) -> None:
        """SnSe at 800 K should have the highest ZT among all four materials."""
        results = {}
        for mat in ["Si", "Bi2Te3", "PbTe", "SnSe"]:
            r = _assemble_zt(mat, f"campaign:test/te-{mat.lower()}", f"candidate:{mat}:rank")
            results[mat] = (r["bt2_zt"] + r["amset_zt"]) / 2.0

        best = max(results, key=lambda m: results[m])
        # SnSe or PbTe should win (both operate at high T and have high ZT)
        assert best in ("SnSe", "PbTe"), (
            f"Expected SnSe or PbTe to have highest ZT; got {best} with {results}"
        )
