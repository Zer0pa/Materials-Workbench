"""Plug-replaceability through the full campaign chain (Wave 4c).

Boundary: Research infrastructure for in silico materials science discovery.
Outputs are research artifacts. No regulatory certification claims. No
clinical or human-subject use. ITAR / weapons applications are out of scope
(Meta UMA Acceptable Use Policy and operator policy).

PRD §Architecture Invariant plug-replaceability acceptance test:
    For one layer at a time (cycle through all 11), swap local_stub →
    runpod_mock mid-campaign and verify:
      - Downstream code unchanged (schema invariant)
      - Schemas validate
      - Audit provenance records the adapter difference
      - Disagreement/falsifier state preserved
      - Scientific changes in output/confidence/falsifier deltas acceptable

This is the campaign-level plug-replaceability test (Wave 4c), distinct from
the per-layer plug-swap tests (Wave 5b).
"""

from __future__ import annotations

from pathlib import Path

from zer0pa_materials_workbench.adapters.ionic.base import IonicJobParams
from zer0pa_materials_workbench.adapters.ionic.mlip_md import MlipMdDiffusionAdapter
from zer0pa_materials_workbench.adapters.ionic.neb import NebMigrationBarrierAdapter
from zer0pa_materials_workbench.adapters.l1.base import L1JobParams
from zer0pa_materials_workbench.adapters.l1.pyscf import PyScfMolecularSolver
from zer0pa_materials_workbench.adapters.l1.qe_aiida import QuantumEspressoAiiDASolver
from zer0pa_materials_workbench.adapters.l1_5.base import L15JobParams
from zer0pa_materials_workbench.adapters.l1_5.phono3py_bte import Phono3pyAnharmonicBTEAdapter
from zer0pa_materials_workbench.adapters.l1_5.phonopy_harmonic import PhonopyHarmonicAdapter
from zer0pa_materials_workbench.adapters.l2.base import L2PredictRequest
from zer0pa_materials_workbench.adapters.l2.deepmd_dpa import DeepmdDpaCalculatorAdapter
from zer0pa_materials_workbench.adapters.l2.ensemble import L2EnsembleRunner
from zer0pa_materials_workbench.adapters.l2.mace_mp import MaceMpCalculatorAdapter
from zer0pa_materials_workbench.adapters.l7 import LangGraphReasonerAdapter, PrefectCampaignAdapter
from zer0pa_materials_workbench.adapters.l7.base import L7CampaignParams
from zer0pa_materials_workbench.audit.kg import MaterialsKG
from zer0pa_materials_workbench.audit.log import AuditLog
from zer0pa_materials_workbench.envelope.envelope import Envelope
from zer0pa_materials_workbench.orchestration import Campaign, CampaignSpec

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_BASE_STRUCTURE = {
    "lattice_vectors": [[3.84, 0.0, 0.0], [0.0, 3.84, 0.0], [0.0, 0.0, 3.84]],
    "species": ["Si", "Si"],
    "fractional_coords": [[0.0, 0.0, 0.0], [0.5, 0.5, 0.5]],
}

_BASE_HASH = "sha256:" + "a" * 64
_BASE_CIF = (
    "data_Si\n"
    "_cell_length_a 5.43\n"
    "_cell_length_b 5.43\n"
    "_cell_length_c 5.43\n"
    "_cell_angle_alpha 90\n"
    "_cell_angle_beta 90\n"
    "_cell_angle_gamma 90\n"
)


def _make_audit_kg(tmp_path: Path) -> tuple[AuditLog, MaterialsKG]:
    return AuditLog(tmp_path / "audit"), MaterialsKG(tmp_path / "kg.sqlite")


def _make_camp(audit: AuditLog, kg: MaterialsKG, campaign_id: str) -> Campaign:
    spec = CampaignSpec(
        campaign_id=campaign_id,
        tenant="swap-test",
        objective="Li-ion conductivity > 1e-3 S/cm",
    )
    return Campaign.create(spec, audit, kg)


def _assert_schema_invariant(env_a: Envelope, env_b: Envelope, layer: str) -> None:
    """Both envelopes must have identical top-level key sets."""
    keys_a = set(env_a.model_dump(mode="json").keys())
    keys_b = set(env_b.model_dump(mode="json").keys())
    assert keys_a == keys_b, (
        f"Layer {layer}: schema differs between adapters.\n"
        f"  Only in A: {keys_a - keys_b}\n"
        f"  Only in B: {keys_b - keys_a}"
    )


def _assert_layer_field_matches(env_a: Envelope, env_b: Envelope, layer: str) -> None:
    assert env_a.layer == env_b.layer, (
        f"Layer {layer}: layer field mismatch {env_a.layer!r} vs {env_b.layer!r}"
    )


def _assert_boundary_present(env: Envelope, layer: str) -> None:
    assert env.research_boundary, (
        f"Layer {layer}: research_boundary must be non-empty"
    )
    assert "Research infrastructure" in env.research_boundary, (
        f"Layer {layer}: research_boundary must contain canonical text"
    )


def _assert_audit_record_id_present(env: Envelope, layer: str) -> None:
    assert env.audit.audit_record_id, (
        f"Layer {layer}: audit_record_id must be non-empty"
    )


def _assert_adapter_names_differ(env_a: Envelope, env_b: Envelope, layer: str) -> None:
    """Adapter names must differ (otherwise we didn't actually swap)."""
    name_a = env_a.tool_adapter.name if env_a.tool_adapter else ""
    name_b = env_b.tool_adapter.name if env_b.tool_adapter else ""
    assert name_a != name_b, (
        f"Layer {layer}: adapter names must differ after swap; "
        f"both are {name_a!r}"
    )


# ---------------------------------------------------------------------------
# L1: PyScf ↔ QuantumEspresso swap
# ---------------------------------------------------------------------------


class TestL1PlugSwapThroughCampaign:
    """L1 DFT adapter: PyScf (local_stub) ↔ QuantumEspresso (different stub)."""

    def test_l1_swap_schema_invariant(self, tmp_path: Path) -> None:
        params_a = L1JobParams(
            structure_cif=_BASE_CIF,
            structure_hash=_BASE_HASH,
            candidate_id="candidate:swap-test/l1",
            campaign_id="campaign:swap-test/l1",
        )
        params_b = L1JobParams(
            structure_cif=_BASE_CIF,
            structure_hash=_BASE_HASH,
            candidate_id="candidate:swap-test/l1",
            campaign_id="campaign:swap-test/l1",
        )
        env_a = PyScfMolecularSolver().submit_job(params_a.structure_cif, params_a)
        env_b = QuantumEspressoAiiDASolver().submit_job(params_b.structure_cif, params_b)

        _assert_schema_invariant(env_a, env_b, "L1")
        _assert_layer_field_matches(env_a, env_b, "L1")

    def test_l1_swap_boundary_present(self, tmp_path: Path) -> None:
        params = L1JobParams(
            structure_cif=_BASE_CIF,
            structure_hash=_BASE_HASH,
            candidate_id="candidate:swap-test/l1",
            campaign_id="campaign:swap-test/l1",
        )
        for adapter_cls in (PyScfMolecularSolver, QuantumEspressoAiiDASolver):
            env = adapter_cls().submit_job(params.structure_cif, params)
            _assert_boundary_present(env, "L1")

    def test_l1_swap_audit_record_id_present(self, tmp_path: Path) -> None:
        params = L1JobParams(
            structure_cif=_BASE_CIF,
            structure_hash=_BASE_HASH,
            candidate_id="candidate:swap-test/l1",
            campaign_id="campaign:swap-test/l1",
        )
        for adapter_cls in (PyScfMolecularSolver, QuantumEspressoAiiDASolver):
            env = adapter_cls().submit_job(params.structure_cif, params)
            _assert_audit_record_id_present(env, "L1")

    def test_l1_swap_adapter_names_differ(self, tmp_path: Path) -> None:
        params = L1JobParams(
            structure_cif=_BASE_CIF,
            structure_hash=_BASE_HASH,
            candidate_id="candidate:swap-test/l1",
            campaign_id="campaign:swap-test/l1",
        )
        env_a = PyScfMolecularSolver().submit_job(params.structure_cif, params)
        env_b = QuantumEspressoAiiDASolver().submit_job(params.structure_cif, params)
        _assert_adapter_names_differ(env_a, env_b, "L1")

    def test_l1_swap_campaign_audit_chain_intact(self, tmp_path: Path) -> None:
        audit, kg = _make_audit_kg(tmp_path)
        camp = _make_camp(audit, kg, "campaign:swap-test/l1-chain")
        camp.transition_to("hypothesising")
        cid = "candidate:swap-test/l1"
        camp.register_candidate(cid, structure_hash=_BASE_HASH)

        # Attach both adapter envelopes.
        params = L1JobParams(
            structure_cif=_BASE_CIF,
            structure_hash=_BASE_HASH,
            candidate_id=cid,
            campaign_id=camp.campaign_id,
        )
        env_a = PyScfMolecularSolver().submit_job(params.structure_cif, params)
        env_b = QuantumEspressoAiiDASolver().submit_job(params.structure_cif, params)
        camp.attach_envelope(env_a)
        camp.attach_envelope(env_b)

        for cat in ("runs", "events", "decisions"):
            result = audit.validate_chain(cat)
            assert result.ok, (
                f"L1 swap: audit chain {cat!r} must be intact; "
                f"errors: {result.errors}"
            )


# ---------------------------------------------------------------------------
# L2: DPA ↔ MACE swap
# ---------------------------------------------------------------------------


class TestL2PlugSwapThroughCampaign:
    """L2 MLIP adapter: DeepMD-DPA ↔ MACE-MP swap."""

    def test_l2_swap_schema_invariant(self) -> None:
        req_a = L2PredictRequest(
            run_id="run:l2/swap-dpa",
            candidate_id="candidate:swap-test/l2",
            campaign_id="campaign:swap-test/l2",
            rights_claim_id="rights:swap-test",
        )
        req_b = L2PredictRequest(
            run_id="run:l2/swap-mace",
            candidate_id="candidate:swap-test/l2",
            campaign_id="campaign:swap-test/l2",
            rights_claim_id="rights:swap-test",
        )
        env_dict_a = DeepmdDpaCalculatorAdapter().predict(_BASE_STRUCTURE, req_a)
        env_dict_b = MaceMpCalculatorAdapter().predict(_BASE_STRUCTURE, req_b)
        env_a = Envelope.model_validate({k: v for k, v in env_dict_a.items() if not k.startswith("_")})
        env_b = Envelope.model_validate({k: v for k, v in env_dict_b.items() if not k.startswith("_")})

        _assert_schema_invariant(env_a, env_b, "L2")
        _assert_layer_field_matches(env_a, env_b, "L2")

    def test_l2_swap_boundary_present(self) -> None:
        req = L2PredictRequest(
            run_id="run:l2/swap",
            candidate_id="candidate:swap-test/l2",
            campaign_id="campaign:swap-test/l2",
            rights_claim_id="rights:swap-test",
        )
        for cls in (DeepmdDpaCalculatorAdapter, MaceMpCalculatorAdapter):
            env_dict = cls().predict(_BASE_STRUCTURE, req)
            env = Envelope.model_validate({k: v for k, v in env_dict.items() if not k.startswith("_")})
            _assert_boundary_present(env, "L2")

    def test_l2_ensemble_uses_both_adapters(self) -> None:
        """The ensemble runner uses both DPA and MACE by construction."""
        runner = L2EnsembleRunner()
        req = L2PredictRequest(
            run_id="run:l2/ensemble",
            candidate_id="candidate:swap-test/l2-ens",
            campaign_id="campaign:swap-test/l2-ens",
            rights_claim_id="rights:swap-test",
        )
        env_dict = runner.run(_BASE_STRUCTURE, req)
        env = Envelope.model_validate({k: v for k, v in env_dict.items() if not k.startswith("_")})
        assert env.layer == "L2"
        # Ensemble must have predictions from both adapters.
        preds = env.output.get("predictions", [])
        assert len(preds) >= 2, (
            f"L2 ensemble must produce at least 2 predictions; got {len(preds)}"
        )


# ---------------------------------------------------------------------------
# Ionic: NEB ↔ MLIP-MD swap
# ---------------------------------------------------------------------------


class TestIonicPlugSwapThroughCampaign:
    """Ionic adapter: NEB ↔ MLIP-MD swap."""

    def test_ionic_neb_vs_mlip_md_schema_invariant(self) -> None:
        params = IonicJobParams(
            structure_hash=_BASE_HASH,
            candidate_id="candidate:swap-test/ionic",
            campaign_id="campaign:swap-test/ionic",
        )
        env_a = NebMigrationBarrierAdapter().compute(params)
        env_b = MlipMdDiffusionAdapter().compute(params)

        # Both are ionic layer envelopes.
        assert env_a.layer == "ionic"
        assert env_b.layer == "ionic"

        # Schema invariant: same top-level keys.
        keys_a = set(env_a.model_dump(mode="json").keys())
        keys_b = set(env_b.model_dump(mode="json").keys())
        assert keys_a == keys_b, (
            f"Ionic swap: schema differs.\n"
            f"  Only in NEB: {keys_a - keys_b}\n"
            f"  Only in MLIP-MD: {keys_b - keys_a}"
        )

    def test_ionic_swap_boundary_present(self) -> None:
        params = IonicJobParams(
            structure_hash=_BASE_HASH,
            candidate_id="candidate:swap-test/ionic-bnd",
            campaign_id="campaign:swap-test/ionic-bnd",
        )
        for adapter_cls in (NebMigrationBarrierAdapter, MlipMdDiffusionAdapter):
            env = adapter_cls().compute(params)
            _assert_boundary_present(env, "ionic")

    def test_ionic_swap_audit_record_id_present(self) -> None:
        params = IonicJobParams(
            structure_hash=_BASE_HASH,
            candidate_id="candidate:swap-test/ionic-audit",
            campaign_id="campaign:swap-test/ionic-audit",
        )
        for adapter_cls in (NebMigrationBarrierAdapter, MlipMdDiffusionAdapter):
            env = adapter_cls().compute(params)
            _assert_audit_record_id_present(env, "ionic")

    def test_ionic_swap_adapter_names_differ(self) -> None:
        params = IonicJobParams(
            structure_hash=_BASE_HASH,
            candidate_id="candidate:swap-test/ionic-names",
            campaign_id="campaign:swap-test/ionic-names",
        )
        env_a = NebMigrationBarrierAdapter().compute(params)
        env_b = MlipMdDiffusionAdapter().compute(params)
        _assert_adapter_names_differ(env_a, env_b, "ionic")


# ---------------------------------------------------------------------------
# L1.5: Phonopy ↔ Phono3py swap
# ---------------------------------------------------------------------------


class TestL15PlugSwapThroughCampaign:
    """L1.5 phonon adapter: Phonopy ↔ Phono3py swap."""

    def test_l1_5_swap_schema_invariant(self) -> None:
        params = L15JobParams(
            structure_hash=_BASE_HASH,
            candidate_id="candidate:swap-test/l1-5",
            campaign_id="campaign:swap-test/l1-5",
            material_id="Si",
        )
        env_a = PhonopyHarmonicAdapter().compute(params)
        env_b = Phono3pyAnharmonicBTEAdapter().compute(params)
        _assert_schema_invariant(env_a, env_b, "L1.5")

    def test_l1_5_both_layer_L15(self) -> None:
        params = L15JobParams(
            structure_hash=_BASE_HASH,
            candidate_id="candidate:swap-test/l1-5-layer",
            campaign_id="campaign:swap-test/l1-5-layer",
            material_id="Si",
        )
        for cls in (PhonopyHarmonicAdapter, Phono3pyAnharmonicBTEAdapter):
            env = cls().compute(params)
            assert env.layer == "L1.5"

    def test_l1_5_no_ionic_conductivity_after_swap(self) -> None:
        params = L15JobParams(
            structure_hash=_BASE_HASH,
            candidate_id="candidate:swap-test/l1-5-ionic",
            campaign_id="campaign:swap-test/l1-5-ionic",
            material_id="Si",
        )
        for cls in (PhonopyHarmonicAdapter, Phono3pyAnharmonicBTEAdapter):
            env = cls().compute(params)
            assert "ionic_conductivity" not in env.output, (
                f"L1.5 {cls.__name__}: must not emit ionic_conductivity after swap"
            )

    def test_l1_5_swap_boundary_present(self) -> None:
        params = L15JobParams(
            structure_hash=_BASE_HASH,
            candidate_id="candidate:swap-test/l1-5-bnd",
            campaign_id="campaign:swap-test/l1-5-bnd",
            material_id="Si",
        )
        for cls in (PhonopyHarmonicAdapter, Phono3pyAnharmonicBTEAdapter):
            env = cls().compute(params)
            _assert_boundary_present(env, "L1.5")


# ---------------------------------------------------------------------------
# L7: Prefect ↔ LangGraph swap
# ---------------------------------------------------------------------------


class TestL7PlugSwapThroughCampaign:
    """L7 adapter: Prefect (lifecycle) ↔ LangGraph (reasoner) swap."""

    def test_l7_swap_schema_invariant(self, tmp_path: Path) -> None:
        params = L7CampaignParams(
            campaign_id="campaign:swap-test/l7",
            candidate_id="candidate:swap-test/l7",
        )
        env_a = PrefectCampaignAdapter().execute(params)
        env_b = LangGraphReasonerAdapter().execute(params)
        _assert_schema_invariant(env_a, env_b, "L7")
        _assert_layer_field_matches(env_a, env_b, "L7")

    def test_l7_swap_boundary_present(self) -> None:
        params = L7CampaignParams(
            campaign_id="campaign:swap-test/l7-bnd",
            candidate_id="candidate:swap-test/l7-bnd",
        )
        for cls in (PrefectCampaignAdapter, LangGraphReasonerAdapter):
            env = cls().execute(params)
            _assert_boundary_present(env, "L7")

    def test_l7_swap_audit_record_id_present(self) -> None:
        params = L7CampaignParams(
            campaign_id="campaign:swap-test/l7-audit",
            candidate_id="candidate:swap-test/l7-audit",
        )
        for cls in (PrefectCampaignAdapter, LangGraphReasonerAdapter):
            env = cls().execute(params)
            _assert_audit_record_id_present(env, "L7")

    def test_l7_swap_campaign_can_attach_both_envelopes(self, tmp_path: Path) -> None:
        """Swapping L7 adapter mid-campaign does not break the campaign."""
        audit, kg = _make_audit_kg(tmp_path)
        camp = _make_camp(audit, kg, "campaign:swap-test/l7-attach")
        cid = "candidate:swap-test/l7-attach"
        camp.register_candidate(cid)

        params = L7CampaignParams(
            campaign_id=camp.campaign_id,
            candidate_id=cid,
        )
        env_a = PrefectCampaignAdapter().execute(params)
        env_b = LangGraphReasonerAdapter().execute(params)

        camp.attach_envelope(env_a)
        camp.attach_envelope(env_b)

        # Audit chain must still be intact.
        for cat in ("runs", "events", "decisions"):
            result = audit.validate_chain(cat)
            assert result.ok, (
                f"L7 swap mid-campaign: audit chain {cat!r} broken; "
                f"errors: {result.errors}"
            )


# ---------------------------------------------------------------------------
# Cross-layer: most-fragile layer identification
# ---------------------------------------------------------------------------


class TestCrossLayerPlugSwapFragility:
    """Identify the most fragile layer in terms of schema stability.

    Per the Wave 4c brief: "Plug-replaceability through full chain: which
    layer is most fragile?" This test runs all pairwise swaps and flags any
    layer whose adapters produce schema differences.
    """

    def test_all_layers_schema_invariant(self, tmp_path: Path) -> None:
        """Run all pairwise swaps and assert none fail schema invariance."""
        fragile: list[str] = []

        # L1
        params_l1 = L1JobParams(
            structure_cif=_BASE_CIF,
            structure_hash=_BASE_HASH,
            candidate_id="candidate:fragility/l1",
            campaign_id="campaign:fragility/l1",
        )
        try:
            env_a = PyScfMolecularSolver().submit_job(params_l1.structure_cif, params_l1)
            env_b = QuantumEspressoAiiDASolver().submit_job(params_l1.structure_cif, params_l1)
            if set(env_a.model_dump(mode="json").keys()) != set(env_b.model_dump(mode="json").keys()):
                fragile.append("L1")
        except Exception:
            fragile.append("L1")

        # L2
        req = L2PredictRequest(
            run_id="run:fragility/l2",
            candidate_id="candidate:fragility/l2",
            campaign_id="campaign:fragility/l2",
            rights_claim_id="rights:fragility",
        )
        try:
            d_a = DeepmdDpaCalculatorAdapter().predict(_BASE_STRUCTURE, req)
            d_b = MaceMpCalculatorAdapter().predict(_BASE_STRUCTURE, req)
            e_a = Envelope.model_validate(d_a)
            e_b = Envelope.model_validate(d_b)
            if set(e_a.model_dump(mode="json").keys()) != set(e_b.model_dump(mode="json").keys()):
                fragile.append("L2")
        except Exception:
            fragile.append("L2")

        # Ionic
        iparams = IonicJobParams(
            structure_hash=_BASE_HASH,
            candidate_id="candidate:fragility/ionic",
            campaign_id="campaign:fragility/ionic",
        )
        try:
            i_a = NebMigrationBarrierAdapter().compute(iparams)
            i_b = MlipMdDiffusionAdapter().compute(iparams)
            if set(i_a.model_dump(mode="json").keys()) != set(i_b.model_dump(mode="json").keys()):
                fragile.append("ionic")
        except Exception:
            fragile.append("ionic")

        # L1.5
        l15params = L15JobParams(
            structure_hash=_BASE_HASH,
            candidate_id="candidate:fragility/l1-5",
            campaign_id="campaign:fragility/l1-5",
            material_id="Si",
        )
        try:
            l15_a = PhonopyHarmonicAdapter().compute(l15params)
            l15_b = Phono3pyAnharmonicBTEAdapter().compute(l15params)
            if set(l15_a.model_dump(mode="json").keys()) != set(l15_b.model_dump(mode="json").keys()):
                fragile.append("L1.5")
        except Exception:
            fragile.append("L1.5")

        # L7
        l7params = L7CampaignParams(
            campaign_id="campaign:fragility/l7",
            candidate_id="candidate:fragility/l7",
        )
        try:
            l7_a = PrefectCampaignAdapter().execute(l7params)
            l7_b = LangGraphReasonerAdapter().execute(l7params)
            if set(l7_a.model_dump(mode="json").keys()) != set(l7_b.model_dump(mode="json").keys()):
                fragile.append("L7")
        except Exception:
            fragile.append("L7")

        # Report fragile layers (do not assert failure — this is an informational gate).
        # The brief asks "which layer is most fragile?" not "all must pass".
        if fragile:
            import warnings
            warnings.warn(
                f"Wave 4c plug-swap fragility report: layers with schema drift: {fragile}",
                stacklevel=2,
            )
        # Hard assertion: at minimum, none of the five tested layers fail schema invariance.
        assert len(fragile) == 0, (
            f"Fragile layers detected (schema invariance failed): {fragile}\n"
            "All tested layers must produce schema-invariant envelopes."
        )
