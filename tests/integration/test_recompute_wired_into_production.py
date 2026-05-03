"""Wave F5 adversarial integration test.

Boundary
--------
Research infrastructure for in silico materials science discovery. Outputs are
research artifacts. No regulatory certification claims. No clinical or
human-subject use. ITAR / weapons applications are out of scope (Meta UMA
Acceptable Use Policy and operator policy).

Discipline
----------
The Wave F5 audit caught the smoking gun: the orchestration layer
(``AcceptanceGate``, ``promote_battery_candidate``, ``wave_runner``,
``validate_evidence_packet``) called the OLD shape-only gates while Wave D
had hardened gates sitting unwired in ``zer0pa_materials_workbench.falsifiers``.

This test builds a synthetic battery campaign on LLZO cubic with FORGED
envelopes — each envelope carries a claim that PASSES the OLD shape-only
gate but FAILS the recompute gate. We then route the chain through every
production promotion path and assert that each path now blocks
promotion. If any path still passes, the wiring regressed.

Forged envelopes
----------------
- L2 envelope: per-model predictions imply 100 meV/atom disagreement;
  claim = 5 meV/atom (forged routing).
- Phase 0 envelope: ``source_manifest_refs = ["src:fabricated:fake"]``
  with no matching row in the audit log.
- L6 envelope: ``novelty_status="novel"`` claimed but the structure
  matches LLZO cubic in the reference set.
- Ionic envelope: claims ``ionic_conductivity_S_per_cm > 1e-3`` with
  back-edge to ``audit:fake-id`` that does not resolve.
- NEB envelope: barrier=5.0 eV (outside the literature band).
- L5 envelope: VTK artifact URI but no sidecar on disk.
- L3 envelope: claims PhaseForgePlus contribution, no enable decision in
  decisions.jsonl.

Each forged piece is the SAME shape that a buggy/malicious adapter could
produce. The test confirms every production path now catches them.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from zer0pa_materials_workbench.audit.rights import RightsClaim
from zer0pa_materials_workbench.boundary import RESEARCH_BOUNDARY
from zer0pa_materials_workbench.envelope import (
    AuditBlock,
    Envelope,
    FalsifierBlock,
    RightsBlock,
    ToolAdapter,
    sha256_of,
)
from zer0pa_materials_workbench.envelope.hashing import structure_hash
from zer0pa_materials_workbench.falsifiers.raw_evidence import (
    llzo_cubic_reference_structure,
)
from zer0pa_materials_workbench.orchestration.acceptance_gates import (
    AcceptanceGate,
    GateContext,
)

# ---------------------------------------------------------------------------
# Forged envelope builders
# ---------------------------------------------------------------------------


def _envelope(
    layer: str,
    output_dict: dict[str, Any],
    audit_id: str,
    back_edges: list[dict[str, str]] | None = None,
    source_manifest_refs: list[str] | None = None,
    rights_scope: str = "tenant_only",
) -> Envelope:
    """Build a minimal valid Envelope wrapping the supplied output_dict."""
    return Envelope(
        research_boundary=RESEARCH_BOUNDARY,
        run_id="run:wave_f5/forged-chain",
        campaign_id="campaign:wave_f5/forged-chain",
        candidate_id="candidate:wave_f5/forged-llzo",
        layer=layer,  # type: ignore[arg-type]
        tool_adapter=ToolAdapter(
            name=f"{layer}-forged-adapter",
            version="0.0.1",
            backend="stub",
            engine=f"{layer}-forged",
        ),
        input_refs=[],
        output=output_dict,
        falsifier=FalsifierBlock(status="pass", items=[]),
        audit=AuditBlock(
            audit_record_id=audit_id,
            input_hash=sha256_of({"layer": layer, "in": "forged"}),
            output_hash=sha256_of(output_dict),
            source_manifest_refs=source_manifest_refs or [],
        ),
        rights=RightsBlock(
            rights_claim_id="rights:wave_f5/forged",
            reuse_scope=rights_scope,  # type: ignore[arg-type]
        ),
        back_edges=back_edges or [],  # type: ignore[arg-type]
    )


def _forged_l2_envelope() -> Envelope:
    """E_DPA = -5.0 eV, E_MACE = +5.0 eV → 10000 meV/atom recompute; claim = 5 meV."""
    output = {
        "predictions": [
            {
                "model": "DPA-3.1-3M",
                "energy_eV_per_atom": -5.0,
                "force_rmse_eV_per_Ang": 0.05,
            },
            {
                "model": "MACE-MPA-0",
                "energy_eV_per_atom": +5.0,  # 100 meV/atom diff = 10000 meV
                "force_rmse_eV_per_Ang": 0.06,
            },
        ],
        "energy_disagreement_meV_per_atom": 5.0,  # FORGED — true is 10000
        "force_rmse_disagreement_eV_per_Ang": 0.01,
        "routing_decision": "promote",  # FORGED
    }
    return _envelope(
        "L2",
        output,
        audit_id="audit:wave_f5/forged-L2",
        source_manifest_refs=["src:wave_f5:l2-fabricated"],
    )


def _forged_phase0_envelope() -> Envelope:
    """Phase 0 envelope claiming a fabricated source manifest ref."""
    output = {
        "extracted_properties": [],
        "units_normalised": True,
        "contradictions_blocking": [],
    }
    return _envelope(
        "phase0",
        output,
        audit_id="audit:wave_f5/forged-phase0",
        source_manifest_refs=["src:fabricated:fake"],
    )


def _forged_l6_envelope() -> Envelope:
    """L6 envelope claims novel but the structure is LLZO cubic (in reference set)."""
    llzo_struct = llzo_cubic_reference_structure()
    output = {
        "candidate_uri": "artifact:wave_f5/forged-llzo.cif",
        # Buggy adapter could paint a wrong hash; the recompute ignores it.
        "structure_hash": "sha256:" + "9" * 64,
        "structure": llzo_struct,
        "novelty_status": "novel",  # FORGED — recompute will detect it's a duplicate
        "dedup_results": [{"source": "MP", "matched": False, "matched_id": None}],
        "cif_valid": True,
        "charge_neutral": True,
        "minimum_distance_ok": True,
    }
    return _envelope(
        "L6",
        output,
        audit_id="audit:wave_f5/forged-L6",
        back_edges=[
            {"layer": "L1", "audit_record_id": "audit:wave_f5/forged-L1"},
            {"layer": "ionic", "audit_record_id": "audit:wave_f5/forged-ionic"},
            {"layer": "L2", "audit_record_id": "audit:wave_f5/forged-L2"},
        ],
        source_manifest_refs=["src:wave_f5:l6-fabricated"],
    )


def _forged_ionic_envelope() -> Envelope:
    """Ionic envelope claims σ > 1e-3 with a non-resolving back-edge."""
    output = {
        "migration_barrier_eV": 0.30,
        "msd_A2": 10.0,
        "diffusion_coefficient_cm2_per_s": 1e-7,
        "nernst_einstein_conductivity_S_per_cm": 5e-3,
        "arrhenius": {"activation_energy_eV": 0.30},
        "electrochemical_window_V_vs_LiLi": [0.0, 4.5],
        "interface_stability": "li_metal_stable",
        "defect_disorder_assumptions": ["forged"],
    }
    return _envelope(
        "ionic",
        output,
        audit_id="audit:wave_f5/forged-ionic",
        back_edges=[
            {
                "layer": "ionic",
                "audit_record_id": "audit:fake-id",  # FORGED — does not resolve
            }
        ],
    )


def _forged_neb_envelope() -> Envelope:
    """NEB envelope claims a barrier of 5.0 eV (outside literature band)."""
    output = {
        "migration_barrier_eV": 5.0,  # FORGED — > 3.0 eV upper bound
        "nernst_einstein_conductivity_S_per_cm": 1e-3,
    }
    return _envelope(
        "ionic",
        output,
        audit_id="audit:wave_f5/forged-neb",
    )


def _forged_l5_envelope() -> Envelope:
    """L5 envelope claims a VTK artifact whose file does not exist."""
    output = {
        # The recompute scans top-level _artifact_sidecars; the envelope
        # contract puts unknown keys in output but the recompute helper
        # accepts both shapes via a dict view.
        "_artifact_sidecars": [
            {
                "format": "vtk",
                "uri": "file:///tmp/wave_f5/does_not_exist.vtk",
                "sha256": "sha256:" + "0" * 64,
                "units": {"x": "m"},
            }
        ],
    }
    env = _envelope(
        "L5",
        output,
        audit_id="audit:wave_f5/forged-L5",
    )
    return env


def _forged_l3_envelope() -> Envelope:
    """L3 envelope claims PhaseForgePlus contribution with no enable decision.

    The Envelope schema forbids the original ``_phaseforgeplus_meta``
    extra block, so we encode the adversarial signal via the adapter
    name (``PhaseForgePlusAdapter``). The L3 sovereign-block recompute
    helper recognises this path too — see
    :func:`zer0pa_materials_workbench.falsifiers.l3_falsifiers._envelope_used_phaseforgeplus`.
    """
    output = {
        "phase_set": ["alpha", "beta"],
    }
    return Envelope(
        research_boundary=RESEARCH_BOUNDARY,
        run_id="run:wave_f5/forged-chain",
        campaign_id="campaign:wave_f5/forged-chain",
        candidate_id="candidate:wave_f5/forged-llzo",
        layer="L3",
        tool_adapter=ToolAdapter(
            name="PhaseForgePlusAdapter",  # signal to the L3 recompute gate
            version="0.0.1",
            backend="stub",
            engine="phaseforge_plus",
        ),
        input_refs=["phaseforge_plus/forged-fixture"],
        output=output,
        falsifier=FalsifierBlock(status="pass", items=[]),
        audit=AuditBlock(
            audit_record_id="audit:wave_f5/forged-L3",
            input_hash=sha256_of({"layer": "L3", "in": "forged"}),
            output_hash=sha256_of(output),
        ),
        rights=RightsBlock(
            rights_claim_id="rights:wave_f5/forged",
            reuse_scope="tenant_only",
        ),
        back_edges=[],
    )


# ---------------------------------------------------------------------------
# Forged chain assembly
# ---------------------------------------------------------------------------


@pytest.fixture
def forged_envelope_chain() -> dict[str, Envelope]:
    """Return the dict of forged envelopes keyed by canonical layer name."""
    return {
        "phase0": _forged_phase0_envelope(),
        "L6": _forged_l6_envelope(),
        "L2": _forged_l2_envelope(),
        "L5": _forged_l5_envelope(),
        "L3": _forged_l3_envelope(),
        "ionic": _forged_ionic_envelope(),
    }


@pytest.fixture
def empty_audit_log() -> list[dict[str, Any]]:
    """An audit log that does not contain any of the forged refs.

    The audit-log-resolving recompute gates will treat every back-edge
    or source-manifest ref as unresolved, which is the correct response
    to fabricated refs.
    """
    return []


@pytest.fixture
def llzo_reference_set() -> set[str]:
    """The reference set against which the forged L6 envelope is duplicate."""
    return {structure_hash(llzo_cubic_reference_structure())}


@pytest.fixture
def rights_claim() -> RightsClaim:
    return RightsClaim(
        rights_claim_id="rights:wave_f5/forged",
        tenant="wave_f5",
        data_class="raw_simulation_output",
        ownership="customer",
        reuse_scope="tenant_only",
        contract_mode="strict_sovereign",
        rationale="Wave F5 adversarial test fixture",
    )


# ---------------------------------------------------------------------------
# 1. AcceptanceGate.evaluate() must return overall=fail
# ---------------------------------------------------------------------------


class TestAcceptanceGateBlocksForgedChain:
    """The unified acceptance gate must reject the forged chain.

    Before Wave F5 wiring: the gate composition included audit
    provenance, disagreement, rights, duplicate, layer falsifiers,
    ionic, boundary — but NOT the recompute gates. So a forged chain
    where every per-layer envelope's claim painted a "passing" shape
    would slip through.

    After Wave F5 wiring: the new ``recompute_consistency`` sub-gate
    runs every Wave D recompute helper and fails on any mismatch.
    """

    def test_evaluate_overall_fail(
        self,
        forged_envelope_chain: dict[str, Envelope],
        empty_audit_log: list[dict[str, Any]],
        llzo_reference_set: set[str],
        rights_claim: RightsClaim,
    ) -> None:
        ctx = GateContext(
            candidate_id="candidate:wave_f5/forged-llzo",
            campaign_id="campaign:wave_f5/forged-chain",
            layer_envelopes=forged_envelope_chain,
            rights_claim=rights_claim,
            aggregate_disagreement_score=0.1,  # passes other gates
            audit_log=empty_audit_log,
            novelty_reference_hashes=llzo_reference_set,
            expected_layers=("L6", "L2", "L1"),
        )
        # Note: L1 envelope is intentionally absent; the missing-layer gate
        # would block, but we want to verify the recompute_consistency
        # gate ALSO fires on the forged chain. Add a placeholder L1 to
        # rule out the missing-layer signal as the only source of failure.
        ctx.layer_envelopes["L1"] = _envelope(
            "L1",
            {
                "code": "QE",
                "functional": "PBE",
                "total_energy_eV": -100.0,
                "force_rmse_eV_per_Ang": 0.01,
                "kpoint_mesh": [4, 4, 4],
                "convergence_delta_meV_per_atom": 2.0,
                "publication_grade": True,
            },
            audit_id="audit:wave_f5/forged-L1",
        )
        verdict = AcceptanceGate(include_ionic_battery_evidence=True).evaluate(ctx)
        assert verdict.overall == "fail", verdict.rationale
        # The recompute-consistency sub-gate MUST be the load-bearing
        # signal (could co-fire with other gates that also catch the
        # forgery, but the recompute one must be present).
        assert verdict.gate_outcomes["recompute_consistency"] in ("fail", "blocked"), (
            f"recompute_consistency gate did not catch the forged chain; "
            f"outcomes={verdict.gate_outcomes}"
        )
        assert "claim_recompute_mismatch" in verdict.failure_reasons, (
            f"recompute mismatch reason not surfaced; "
            f"reasons={verdict.failure_reasons}"
        )

    def test_specific_recompute_gates_fired(
        self,
        forged_envelope_chain: dict[str, Envelope],
        empty_audit_log: list[dict[str, Any]],
        llzo_reference_set: set[str],
        rights_claim: RightsClaim,
    ) -> None:
        """Identify every Wave D recompute gate that fired on the forged chain.

        The chain forged seven distinct attack vectors. We expect at
        least four to trip — the rest may be skipped because they need
        an audit log we don't hand them. The test names the tripped
        gates so any regression is immediately diagnosable.
        """
        ctx = GateContext(
            candidate_id="candidate:wave_f5/forged-llzo",
            campaign_id="campaign:wave_f5/forged-chain",
            layer_envelopes=dict(forged_envelope_chain),
            rights_claim=rights_claim,
            aggregate_disagreement_score=0.1,
            audit_log=empty_audit_log,
            novelty_reference_hashes=llzo_reference_set,
            expected_layers=("L2", "L6"),
        )
        verdict = AcceptanceGate(include_ionic_battery_evidence=False).evaluate(ctx)
        recompute_failures = sorted(
            {
                fi.name
                for fi in verdict.falsifier_items
                if fi.status == "fail"
                and (
                    "recomputed" in fi.name
                    or "verify" in fi.name
                    or "neb_barrier" in fi.name
                    or "sovereign_block" in fi.name
                    or "novelty_resolved" in fi.name
                    or "source_manifest" in fi.name
                )
            }
        )
        # Expect: L2 disagreement, L6 novelty, L5 sidecar, ionic back-edge,
        # NEB barrier, source-manifest linkage, L3 sovereign block. Any
        # subset of these reaching ``fail`` confirms the wiring is alive.
        assert len(recompute_failures) >= 4, (
            f"expected >=4 Wave D recompute gates to trip; got "
            f"{recompute_failures}"
        )


# ---------------------------------------------------------------------------
# 2. promote_battery_candidate() must return reject
# ---------------------------------------------------------------------------


class TestPromoteBatteryCandidateBlocksForgedChain:
    """The battery promotion gate must reject when the forged ionic+NEB
    bundle is wired with the Wave D recompute gates.

    We construct a synthetic ``BatteryEvidenceBundle`` whose NEB envelope
    has a 5.0 eV barrier (outside the literature band) and pass it to
    ``promote_battery_candidate`` with ``extra_envelopes`` carrying the
    forged L2/L6/L5/L3/phase0 envelopes. Without the Wave F5 wiring,
    the OLD path could have promoted; with the wiring, the recompute
    gates catch each forgery and the decision is "reject".
    """

    def test_promote_returns_reject(
        self,
        forged_envelope_chain: dict[str, Envelope],
        empty_audit_log: list[dict[str, Any]],
        llzo_reference_set: set[str],
    ) -> None:
        from zer0pa_materials_workbench.adapters.ionic.base import IonicJobParams
        from zer0pa_materials_workbench.services.ionic_transport_service import (
            promote_battery_candidate,
            run_full_battery_evidence,
        )

        # Use the canonical LLZO params to build a real bundle, then
        # corrupt the NEB envelope's migration_barrier_eV to 5.0 eV
        # (forged: outside the literature plausibility band).
        params = IonicJobParams(
            structure_hash="sha256:d45cb2bfe5e76b86b365e1402e118ed32280049a62345c903558c6cfac04ef19",
            fixture_id="fixture:LLZO_cubic:d45cb2bf",
            candidate_id="candidate:wave_f5/forged-llzo",
        )
        bundle = run_full_battery_evidence(params)
        bundle.neb["output"]["migration_barrier_eV"] = 5.0  # FORGED

        # Pass the forged extra envelopes. The L2/L6 are the load-bearing
        # adversarial pieces; the L5/L3/phase0 corroborate via their
        # specific recompute gates.
        extra = {
            layer: env
            for layer, env in forged_envelope_chain.items()
            if layer in ("L2", "L6", "L5", "L3", "phase0")
        }
        decision = promote_battery_candidate(
            "candidate:wave_f5/forged-llzo",
            bundle=bundle,
            extra_envelopes=extra,
            audit_log=empty_audit_log,
            novelty_reference_hashes=llzo_reference_set,
        )
        assert decision.decision == "reject", (
            f"forged chain should be rejected; got decision={decision.decision} "
            f"with rationale={decision.rationale}"
        )
        # Identify the load-bearing recompute gate failures in the evidence.
        recompute_failures = sorted(
            {
                ev["name"]
                for ev in decision.evidence
                if ev.get("status") == "fail"
                and (
                    "recomputed" in ev["name"]
                    or "verify" in ev["name"]
                    or "neb_barrier_range" in ev["name"]
                    or "sovereign_block" in ev["name"]
                    or "novelty_resolved" in ev["name"]
                    or "source_manifest" in ev["name"]
                )
            }
        )
        assert len(recompute_failures) >= 2, (
            f"expected >=2 Wave D recompute gates to fail in promotion; "
            f"got {recompute_failures}"
        )

    def test_promote_returns_reject_when_only_neb_forged(
        self,
    ) -> None:
        """Even without the extra L2/L6/etc envelopes, the NEB barrier
        recompute alone is enough to reject the forged chain via the
        ionic-bundle path."""
        from zer0pa_materials_workbench.adapters.ionic.base import IonicJobParams
        from zer0pa_materials_workbench.services.ionic_transport_service import (
            promote_battery_candidate,
            run_full_battery_evidence,
        )

        params = IonicJobParams(
            structure_hash="sha256:d45cb2bfe5e76b86b365e1402e118ed32280049a62345c903558c6cfac04ef19",
            fixture_id="fixture:LLZO_cubic:d45cb2bf",
            candidate_id="candidate:wave_f5/forged-only-neb",
        )
        bundle = run_full_battery_evidence(params)
        # Force the NEB barrier into the literature-implausible region.
        bundle.neb["output"]["migration_barrier_eV"] = 5.0

        decision = promote_battery_candidate(
            "candidate:wave_f5/forged-only-neb", bundle=bundle
        )
        assert decision.decision == "reject"
        # Ensure the NEB recompute gate is the load-bearing signal.
        neb_fails = [
            ev for ev in decision.evidence
            if ev.get("name") == "ionic.neb_barrier_range_check"
            and ev.get("status") == "fail"
        ]
        assert neb_fails, (
            f"NEB barrier-range recompute did not fire on the forged bundle; "
            f"evidence={[ev['name'] for ev in decision.evidence]}"
        )


# ---------------------------------------------------------------------------
# 3. validate_evidence_packet() must return failures
# ---------------------------------------------------------------------------


class TestValidatePacketBlocksForgedChain:
    """The packet validator must surface the forged chain's recompute
    failures. Customers receive packets through this validator; without
    the Wave F5 wiring they would receive the unhardened version.
    """

    def test_validator_overall_fail_on_forged_packet(
        self,
        forged_envelope_chain: dict[str, Envelope],
    ) -> None:
        """Construct a minimal packet shape that the validator can run
        recompute gates against. We build a synthetic
        :class:`EvidencePacket` whose nested envelopes are the forged
        ones; the validator's per-envelope recompute walker MUST surface
        at least one ``fail`` per smoking-gun gate.
        """
        from zer0pa_materials_workbench.packets.evidence_packet import (
            EvidencePacket,
            PacketBundle,
            PacketPublishableTarget,
            PacketSection,
        )
        from zer0pa_materials_workbench.packets.validators import validate_evidence_packet

        # Wrap each forged envelope as a section.
        sections: dict[str, PacketSection] = {}
        for layer, env in forged_envelope_chain.items():
            section_name = f"forged_{layer.lower().replace('.', '_')}_section"
            sections[section_name] = PacketSection(
                section_name=section_name,
                envelopes=[env.model_dump(mode="json")],
                raw_payload={},
            )
        # The validator also requires a few side sections; provide them
        # in their minimum-pass shape so the recompute gates are the
        # only failing signal.
        sections["audit_trail_head"] = PacketSection(
            section_name="audit_trail_head",
            envelopes=[],
            raw_payload={
                "audit_record_ids": [
                    env.audit.audit_record_id
                    for env in forged_envelope_chain.values()
                ],
                "rows": [],
            },
        )

        bundle = PacketBundle(sections=sections)
        packet = EvidencePacket(
            packet_id="packet:wave_f5/forged-chain",
            research_boundary=RESEARCH_BOUNDARY,
            objective="battery_solid_electrolyte",
            campaign_id="campaign:wave_f5/forged-chain",
            candidate_id="candidate:wave_f5/forged-llzo",
            structure_hash="sha256:" + "f" * 64,
            promotion_decision="promote",  # the forge claims promote
            promotion_rationale="forged",
            bundle=bundle,
            publishable_paper_target=PacketPublishableTarget(
                primary_journal="J. Wave F5 Tests",
                alternative_journal="Adversarial Materials Today",
            ),
        )

        report = validate_evidence_packet(packet)
        assert report.overall_status == "fail"
        # Identify the load-bearing recompute failures in the report.
        recompute_failures = sorted(
            {
                fi.name
                for fi in report.falsifier_items
                if fi.status == "fail"
                and (
                    "recomputed" in fi.name
                    or "verify" in fi.name
                    or "neb_barrier_range" in fi.name
                    or "sovereign_block" in fi.name
                    or "novelty_resolved" in fi.name
                    or "source_manifest" in fi.name
                )
            }
        )
        assert len(recompute_failures) >= 2, (
            f"expected >=2 Wave D recompute gates to fail in packet "
            f"validator; got {recompute_failures}. All failures: "
            f"{[fi.name for fi in report.falsifier_items if fi.status == 'fail']}"
        )


# ---------------------------------------------------------------------------
# 4. The wave runner must surface recompute violations
# ---------------------------------------------------------------------------


class TestWaveRunnerSurfacesRecomputeViolations:
    """The falsification wave runner now ends with a post-PRD recompute
    sweep that runs every Wave D gate against a forged sentinel chain.
    The aggregate ``recompute_sweep.forged_chain_caught`` must be True;
    each gate's status must be recorded in ``falsifiers.jsonl``.
    """

    def test_recompute_sweep_catches_forged_chain(self, tmp_path: Path) -> None:
        from zer0pa_materials_workbench.audit.kg import MaterialsKG
        from zer0pa_materials_workbench.audit.log import AuditLog
        from zer0pa_materials_workbench.falsifiers.wave_runner import (
            FalsificationWaveRunner,
        )

        audit_log = AuditLog(tmp_path / "audit")
        # ``MaterialsKG(":memory:")`` creates an on-disk file because the
        # constructor calls ``Path.resolve``. Use the tmp_path so the
        # test does not leave artifacts in the repo root.
        kg = MaterialsKG(tmp_path / "kg.sqlite")
        runner = FalsificationWaveRunner(audit_log=audit_log, kg=kg)
        result = runner.run_all(Path("fixtures/negatives"))
        assert result.recompute_sweep is not None
        assert result.recompute_sweep.forged_chain_caught, (
            f"recompute sweep did not catch the forged sentinel chain; "
            f"results={result.recompute_sweep.gate_results}"
        )
        # At least 4 of the 7 gates must trip with status="fail".
        assert result.recompute_sweep.n_failed >= 4, (
            f"expected >=4 sweep gates to fail; got {result.recompute_sweep.n_failed}"
        )


# ---------------------------------------------------------------------------
# 5. Regression-safety pin: the OLD shape gates would have passed the
#    forged chain. This test documents the smoking gun.
# ---------------------------------------------------------------------------


class TestOldShapeGatesWouldHaveAccepted:
    """Document what the OLD shape-only gates would have done with the
    forged chain. This is a regression-safety pin: if anyone re-introduces
    the old gates without the recompute, this test will pin the gap.
    """

    def test_old_l2_disagreement_shape_gate_accepts_forged_l2(self) -> None:
        """The old ``dpa_mace_disagreement_routing`` reads the claim field
        directly. The forged L2 envelope claims 5 meV/atom (under the 25
        threshold) and routing_decision='promote', so the old gate
        accepts it as ``status="pass"``."""
        from zer0pa_materials_workbench.falsifiers.l2_falsifiers import (
            dpa_mace_disagreement_routing,
        )

        forged_l2 = _forged_l2_envelope().model_dump(mode="json")
        item = dpa_mace_disagreement_routing(forged_l2)
        # The old gate trusts the claim. It returns "pass" because the
        # claimed disagreement is 5 meV/atom (below the 25 threshold).
        assert item.status == "pass", (
            f"old shape-only gate is supposed to accept the forged L2 "
            f"claim; got status={item.status}"
        )

    def test_new_l2_recompute_gate_rejects_forged_l2(self) -> None:
        """The new ``dpa_mace_disagreement_routing_recomputed`` recomputes
        from the per-model predictions and catches the forgery."""
        from zer0pa_materials_workbench.falsifiers.l2_falsifiers import (
            dpa_mace_disagreement_routing_recomputed,
        )

        forged_l2 = _forged_l2_envelope().model_dump(mode="json")
        item = dpa_mace_disagreement_routing_recomputed(forged_l2)
        assert item.status == "fail", (
            f"new recompute gate must catch the forged L2 disagreement; "
            f"got status={item.status} with actual={item.actual}"
        )
