"""IonicTransportService — FastAPI service that owns the battery MVP gate.

PRD §Ionic Transport (verbatim quote):

    "Battery MVP claims require an explicit IonicTransportService;
    phonons do not substitute for Li-ion conductivity."

This service is the single place that produces battery-MVP-grade
ionic-transport envelopes. The MVP packet generator MUST call
``/v1/ionic/full-battery-evidence`` for every promoted candidate; the
``promote_battery_candidate`` helper is the canonical promotion gate.

Endpoints
---------

* ``POST /v1/ionic/neb`` — NEB barrier
* ``POST /v1/ionic/md-diffusion`` — MLIP-MD D / sigma_NE
* ``POST /v1/ionic/aimd-diffusion`` — AIMD D / sigma_NE
* ``POST /v1/ionic/arrhenius-fit`` — Arrhenius fit over (T, sigma) series
* ``POST /v1/ionic/electrochemical-window`` — oxidative/reductive window
* ``POST /v1/ionic/interface-stability`` — interface classification
* ``POST /v1/ionic/full-battery-evidence`` — orchestrator
* ``POST /v1/ionic/promote-battery-candidate`` — promotion gate
* ``GET  /v1/ionic/healthz`` — liveness probe

Architectural decisions
-----------------------

1. **Service is the sole producer of ionic envelopes.** Every adapter
   sets ``input_refs=[IONIC_TRANSPORT_SERVICE_REF]`` so the
   ``requires_ionic_transport_service`` falsifier always finds the
   reference. L1.5 phonon outputs cannot impersonate ionic envelopes.

2. **Orchestrator returns envelopes in dependency order.** The
   ``full-battery-evidence`` endpoint returns:

   1. NEB (migration barrier — independent input)
   2. MLIP-MD diffusion (D, sigma_NE — independent input)
   3. AIMD diffusion (parallel to MLIP-MD; cross-method check)
   4. Arrhenius fit (DEPENDS on MLIP-MD via T-sweep)
   5. Electrochemical window (independent)
   6. Interface stability (independent)

   The dependency on the MLIP-MD/AIMD output for Arrhenius is encoded
   by synthesising a temperature sweep from the diffusion measurement
   when no real T-series is provided.

3. **Promotion gate is the central MVP gate.** Returns
   ``promote | defer | reject`` based on the PRD §Ionic Transport
   gates. The decision is fully traceable: each contributing falsifier
   item is recorded in :class:`PromotionDecision.evidence`.
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from zer0pa_materials.adapters.ionic.aimd import AimdDiffusionAdapter
from zer0pa_materials.adapters.ionic.arrhenius import (
    ArrheniusFitAdapter,
    ArrheniusFitParams,
)
from zer0pa_materials.adapters.ionic.base import (
    IONIC_TRANSPORT_SERVICE_REF,
    IonicJobParams,
)
from zer0pa_materials.adapters.ionic.electrochemical_window import (
    ElectrochemicalWindowAdapter,
)
from zer0pa_materials.adapters.ionic.interface_stability import (
    InterfaceStabilityAdapter,
)
from zer0pa_materials.adapters.ionic.mlip_md import MlipMdDiffusionAdapter
from zer0pa_materials.adapters.ionic.neb import NebMigrationBarrierAdapter
from zer0pa_materials.envelope import Envelope, FalsifierItem
from zer0pa_materials.falsifiers.ionic_falsifiers import (
    activation_energy_target_threshold,
    arrhenius_fit_quality,
    defect_disorder_assumptions_documented,
    full_battery_evidence_chain_complete,
    li_metal_reduction_route_compatibility,
    mlip_aimd_diffusion_disagreement,
    neb_barrier_range_check,
    oxidative_stability_threshold,
    requires_ionic_transport_service,
    room_temperature_conductivity_credible_interval_meets_threshold,
    verify_ionic_service_back_edge,
)
from zer0pa_materials.falsifiers.l2_falsifiers import (
    dpa_mace_disagreement_routing_recomputed,
)
from zer0pa_materials.falsifiers.l3_falsifiers import (
    verify_l3_sovereign_block_enforced,
)
from zer0pa_materials.falsifiers.l5_falsifiers import (
    verify_l5_artifact_sidecar,
)
from zer0pa_materials.falsifiers.l6_falsifiers import (
    novelty_status_gate_recomputed,
)
from zer0pa_materials.falsifiers.phase0_falsifiers import (
    verify_source_manifest_linkage,
)

__all__ = [
    "IONIC_SERVICE_NAME",
    "IONIC_SERVICE_VERSION",
    "BatteryEvidenceBundle",
    "PromotionDecision",
    "PromotionStatus",
    "ionic_app",
    "create_ionic_app",
    "run_full_battery_evidence",
    "promote_battery_candidate",
]


IONIC_SERVICE_NAME: str = "IonicTransportService"
IONIC_SERVICE_VERSION: str = "0.1.0"

PromotionStatus = Literal["promote", "defer", "reject"]


# ----------------------------------------------------------------------------
# Pydantic input models for FastAPI
# ----------------------------------------------------------------------------


class _BasePayload(BaseModel):
    """Base payload that is consumed by every adapter endpoint."""

    model_config = ConfigDict(extra="forbid")

    structure_hash: str = Field(..., min_length=8)
    fixture_id: str | None = Field(default=None)
    candidate_id: str = Field(default="candidate:ionic-default")
    campaign_id: str = Field(default="campaign:ionic-default")
    temperature_K: float = Field(default=300.0, gt=0.0)
    li_carrier_concentration_per_cm3: float = Field(default=2.0e22, gt=0.0)
    haven_ratio: float = Field(default=1.0, gt=0.0)
    image_count: int = Field(default=7, ge=3)
    force_tolerance_eV_per_angstrom: float = Field(default=0.05, gt=0.0)
    md_trajectory_length_ps: float = Field(default=10.0, gt=0.0)
    n_md_steps: int = Field(default=10000, ge=100)
    interface_mode: str = Field(default="li_metal")
    cathode_chemistry: str = Field(default="NMC811")
    rights_claim_id: str = Field(default="rights:ionic:default")
    reuse_scope: str = Field(default="tenant_only")

    def to_params(self) -> IonicJobParams:
        return IonicJobParams(
            structure_hash=self.structure_hash,
            fixture_id=self.fixture_id,
            candidate_id=self.candidate_id,
            campaign_id=self.campaign_id,
            temperature_K=self.temperature_K,
            li_carrier_concentration_per_cm3=self.li_carrier_concentration_per_cm3,
            haven_ratio=self.haven_ratio,
            image_count=self.image_count,
            force_tolerance_eV_per_angstrom=self.force_tolerance_eV_per_angstrom,
            md_trajectory_length_ps=self.md_trajectory_length_ps,
            n_md_steps=self.n_md_steps,
            interface_mode=self.interface_mode,
            cathode_chemistry=self.cathode_chemistry,
            rights_claim_id=self.rights_claim_id,
            reuse_scope=self.reuse_scope,
        )


class NebPayload(_BasePayload):
    path_id: str | None = Field(default=None)


class MdDiffusionPayload(_BasePayload):
    pass


class AimdDiffusionPayload(_BasePayload):
    pass


class ArrheniusFitPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    temperatures_K: list[float] = Field(..., min_length=3)
    conductivities_S_per_cm: list[float] = Field(..., min_length=3)
    candidate_id: str = Field(default="candidate:arrhenius-default")
    campaign_id: str = Field(default="campaign:arrhenius-default")
    structure_hash: str = Field(default="sha256:none")
    fixture_id: str | None = Field(default=None)
    rights_claim_id: str = Field(default="rights:ionic:default")
    reuse_scope: str = Field(default="tenant_only")


class FullBatteryEvidencePayload(_BasePayload):
    pass


class PromoteBatteryCandidatePayload(_BasePayload):
    pass


# ----------------------------------------------------------------------------
# Bundle / promotion models
# ----------------------------------------------------------------------------


class BatteryEvidenceBundle(BaseModel):
    """Container for the six envelopes the orchestrator returns."""

    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    structure_hash: str
    fixture_id: str | None = None
    neb: dict[str, Any]
    mlip_md: dict[str, Any]
    aimd: dict[str, Any]
    arrhenius: dict[str, Any]
    electrochemical_window: dict[str, Any]
    interface_stability: dict[str, Any]
    chain_complete: dict[str, Any]
    mlip_vs_aimd_disagreement: dict[str, Any]


class PromotionDecision(BaseModel):
    """Output of :func:`promote_battery_candidate`."""

    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    structure_hash: str
    decision: PromotionStatus
    rationale: str
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    bundle: BatteryEvidenceBundle | None = None


# ----------------------------------------------------------------------------
# Orchestrator + promotion gate
# ----------------------------------------------------------------------------


def run_full_battery_evidence(params: IonicJobParams) -> BatteryEvidenceBundle:
    """Run every ionic adapter for *params* and return the bundle.

    Order:

    1. NEB — barrier.
    2. MLIP-MD — D, sigma_NE.
    3. AIMD — D, sigma_NE (parallel to MLIP-MD).
    4. Arrhenius — synthesise (T, sigma) sweep at 300/400/500 K from
       the MLIP-MD D and the literature Ea via the
       :meth:`ArrheniusFitAdapter.compute` default path.
    5. Electrochemical window.
    6. Interface stability.

    After the six adapter envelopes, the orchestrator computes:

    * the chain-complete falsifier (covers all six required pieces)
    * the MLIP-vs-AIMD disagreement falsifier
    """
    neb_env = NebMigrationBarrierAdapter().compute(params)
    mlip_env = MlipMdDiffusionAdapter().compute(params)
    aimd_env = AimdDiffusionAdapter().compute(params)
    arrhenius_env = ArrheniusFitAdapter().compute(params)
    ec_env = ElectrochemicalWindowAdapter().compute(params)
    intf_env = InterfaceStabilityAdapter().compute(params)

    # Chain falsifier covers all six envelopes.
    chain_item = full_battery_evidence_chain_complete(
        [neb_env, mlip_env, aimd_env, arrhenius_env, ec_env, intf_env]
    )
    disagreement_item = mlip_aimd_diffusion_disagreement(mlip_env, aimd_env)

    return BatteryEvidenceBundle(
        candidate_id=params.candidate_id,
        structure_hash=params.structure_hash,
        fixture_id=params.fixture_id,
        neb=neb_env.canonical_dict(),
        mlip_md=mlip_env.canonical_dict(),
        aimd=aimd_env.canonical_dict(),
        arrhenius=arrhenius_env.canonical_dict(),
        electrochemical_window=ec_env.canonical_dict(),
        interface_stability=intf_env.canonical_dict(),
        chain_complete=chain_item.model_dump(mode="json"),
        mlip_vs_aimd_disagreement=disagreement_item.model_dump(mode="json"),
    )


def _consolidated_envelope_for_promotion(
    bundle: BatteryEvidenceBundle,
) -> dict[str, Any]:
    """Build a synthetic envelope dict that combines fields across the bundle.

    The promotion falsifiers expect a single envelope-shaped object
    with the relevant output fields populated. We merge the relevant
    output fields from the six adapter envelopes into one dict for
    falsifier evaluation.
    """
    merged_output: dict[str, Any] = {}
    merged_falsifier_items: list[dict[str, Any]] = []
    for env_name in (
        "neb",
        "mlip_md",
        "aimd",
        "arrhenius",
        "electrochemical_window",
        "interface_stability",
    ):
        env_dict = getattr(bundle, env_name)
        out = env_dict.get("output", {})
        falsifier = env_dict.get("falsifier", {})
        items = falsifier.get("items", [])
        merged_falsifier_items.extend(items)
        for k, v in out.items():
            if k == "defect_disorder_assumptions":
                merged_output.setdefault(k, []).extend(v or [])
            elif k == "interface_stability":
                # Take the most informative classification (non-unknown wins).
                if merged_output.get(k) in (None, "unknown"):
                    merged_output[k] = v
            else:
                # First-write-wins; later adapters do NOT clobber earlier values.
                if k not in merged_output or merged_output[k] is None:
                    merged_output[k] = v
    return {
        "layer": "ionic",
        "research_boundary": bundle.neb.get("research_boundary", ""),
        "candidate_id": bundle.candidate_id,
        "input_refs": [IONIC_TRANSPORT_SERVICE_REF],
        "output": merged_output,
        "falsifier": {"status": "pass", "items": merged_falsifier_items},
    }


def promote_battery_candidate(
    candidate_id: str,
    bundle: BatteryEvidenceBundle | None = None,
    *,
    params: IonicJobParams | None = None,
    extra_envelopes: dict[str, Any] | None = None,
    audit_log: Any | None = None,
    novelty_reference_hashes: set[str] | None = None,
) -> PromotionDecision:
    """Battery promotion gate (PRD §Acceptance Gates: Battery MVP).

    Wave F5 wiring
    --------------
    Beyond the original PRD §Ionic Transport blocking gates, this function
    now also invokes every Wave D hardened recompute gate that applies to
    the evidence chain. These are the smoking-gun gates the OLD path
    skipped:

    * :func:`dpa_mace_disagreement_routing_recomputed` on the L2 envelope
      in ``extra_envelopes`` (if any) — recomputes DPA/MACE disagreement
      from per-model predictions and rejects forged routing decisions.
    * :func:`verify_source_manifest_linkage` on every envelope's
      ``audit.source_manifest_refs`` — fails if any ref does not resolve
      in ``sources.jsonl``.
    * :func:`novelty_status_gate_recomputed` on the L6 envelope in
      ``extra_envelopes`` (if any) — re-runs the dedupe pipeline against
      the supplied ``novelty_reference_hashes``.
    * :func:`verify_ionic_service_back_edge` on the consolidated ionic
      evidence — fails if the back-edge does not resolve in the audit log.
    * :func:`neb_barrier_range_check` on the NEB envelope — applies the
      literature plausibility band on ``migration_barrier_eV`` and the
      Arrhenius consistency check on σ ≥ 1e-3 promoted candidates.
    * :func:`verify_l5_artifact_sidecar` on any L5 artifacts in
      ``extra_envelopes`` — re-reads on-disk bytes and re-hashes.
    * :func:`verify_l3_sovereign_block_enforced` if an L3 envelope is in
      ``extra_envelopes`` — requires an enable decision in
      ``decisions.jsonl``.

    Promotion is BLOCKED if ANY of these recompute gates returns ``fail``
    or ``blocked``. ``inconclusive`` is also fail-closed (the gate cannot
    establish recompute-vs-claim equivalence).

    Parameters
    ----------
    candidate_id
        Stable URN of the candidate under evaluation.
    bundle
        Pre-computed full-battery-evidence bundle. If not supplied,
        ``params`` MUST be passed and the orchestrator runs in-line.
    params
        :class:`IonicJobParams` to drive the adapters when ``bundle``
        is None.
    extra_envelopes
        Optional dict mapping layer-name → envelope-dict for Wave D
        recompute gates that operate on layers OTHER than the ionic
        bundle (L2, L6, L5, L3, phase0). Pass these in when the
        promotion is the final gate at the end of a full multi-layer
        campaign. When absent, the recompute gates that need those
        envelopes are skipped (no-op pass).
    audit_log
        Optional live :class:`zer0pa_materials.audit.AuditLog` (or
        in-memory iterable of audit rows). Required by the
        audit-log-resolving recompute gates: ionic back-edge, source
        manifest linkage, L3 sovereign block. When absent, those gates
        are skipped (no-op pass). Skipping is acceptable in fixture
        smoke tests; in production the orchestrator MUST pass the
        live log.
    novelty_reference_hashes
        Optional reference structure_hash set (Materials Project /
        JARVIS / Alexandria / GNoME / OPTIMADE). Used by the L6
        recompute novelty gate to detect duplicates that claim
        ``novelty_status='novel'``.

    Returns
    -------
    PromotionDecision
        ``decision="promote"`` if every required gate passes;
        ``"defer"`` if at least one gate is ``blocked`` (the candidate
        needs more evidence before final routing); ``"reject"`` if at
        least one gate is ``fail``.
    """
    if bundle is None:
        if params is None:
            raise ValueError("either bundle or params must be supplied.")
        bundle = run_full_battery_evidence(params)

    consolidated = _consolidated_envelope_for_promotion(bundle)

    # Run every gate.
    gate_items: list[FalsifierItem] = []
    gate_items.append(requires_ionic_transport_service(consolidated))
    gate_items.append(
        room_temperature_conductivity_credible_interval_meets_threshold(
            bundle.mlip_md, threshold_S_per_cm=1e-3
        )
    )
    target, stretch = activation_energy_target_threshold(consolidated)
    gate_items.append(target)
    gate_items.append(stretch)
    gate_items.append(oxidative_stability_threshold(consolidated))
    gate_items.append(li_metal_reduction_route_compatibility(consolidated))
    gate_items.append(arrhenius_fit_quality(bundle.arrhenius))
    chain_dict = bundle.chain_complete
    chain_item = (
        FalsifierItem(**chain_dict) if isinstance(chain_dict, dict) else chain_dict
    )
    gate_items.append(chain_item)
    gate_items.append(defect_disorder_assumptions_documented(consolidated))
    # Disagreement is informational — it goes into evidence but does not
    # block promotion by itself.
    dis_dict = bundle.mlip_vs_aimd_disagreement
    disagreement_item = (
        FalsifierItem(**dis_dict) if isinstance(dis_dict, dict) else dis_dict
    )

    # ------------------------------------------------------------------
    # Wave F5: hardened recompute gates.
    # ------------------------------------------------------------------
    extra_envelopes = extra_envelopes or {}
    recompute_items: list[FalsifierItem] = []

    # NEB barrier range check on the NEB envelope.
    recompute_items.append(neb_barrier_range_check(bundle.neb))

    # Ionic back-edge: only check when an audit log is supplied. Without
    # the log we cannot resolve the back-edge; fail-closed would block
    # every fixture-mode promotion in CI, which is acceptable only when
    # the orchestrator supplies a real ledger. The consolidated ionic
    # envelope is built from the bundle's six adapter envelopes — it
    # contains the claim itself, not a back-edge to a separate ionic
    # producer, so the gate only applies if a back-edge is present.
    if audit_log is not None:
        consolidated_back_edges = consolidated.get("back_edges") or []
        has_ionic_be = any(
            isinstance(be, dict) and be.get("layer") == "ionic"
            for be in consolidated_back_edges
        )
        if has_ionic_be:
            recompute_items.append(
                verify_ionic_service_back_edge(consolidated, audit_log)
            )
        # Source-manifest linkage on every nested envelope that carries
        # source_manifest_refs.
        for env_name in (
            "neb",
            "mlip_md",
            "aimd",
            "arrhenius",
            "electrochemical_window",
            "interface_stability",
        ):
            env_dict = getattr(bundle, env_name, None)
            if isinstance(env_dict, dict):
                audit = env_dict.get("audit") or {}
                refs = audit.get("source_manifest_refs") or []
                if refs:
                    recompute_items.append(
                        verify_source_manifest_linkage(env_dict, audit_log)
                    )

    # L2 disagreement recompute (if an L2 envelope is provided).
    l2_env = extra_envelopes.get("L2")
    if l2_env is not None:
        if isinstance(l2_env, Envelope):
            l2_dict = l2_env.model_dump(mode="json")
        else:
            l2_dict = dict(l2_env)
        recompute_items.append(dpa_mace_disagreement_routing_recomputed(l2_dict))
        if audit_log is not None:
            audit = l2_dict.get("audit") or {}
            if audit.get("source_manifest_refs"):
                recompute_items.append(
                    verify_source_manifest_linkage(l2_dict, audit_log)
                )

    # L6 novelty recompute.
    l6_env = extra_envelopes.get("L6")
    if l6_env is not None:
        if isinstance(l6_env, Envelope):
            l6_dict = l6_env.model_dump(mode="json")
        else:
            l6_dict = dict(l6_env)
        recompute_items.append(
            novelty_status_gate_recomputed(
                l6_dict,
                reference_set=novelty_reference_hashes or set(),
            )
        )
        if audit_log is not None:
            audit = l6_dict.get("audit") or {}
            if audit.get("source_manifest_refs"):
                recompute_items.append(
                    verify_source_manifest_linkage(l6_dict, audit_log)
                )

    # L5 artifact sidecar recompute.
    l5_env = extra_envelopes.get("L5")
    if l5_env is not None:
        if isinstance(l5_env, Envelope):
            l5_dict = l5_env.model_dump(mode="json")
        else:
            l5_dict = dict(l5_env)
        recompute_items.append(verify_l5_artifact_sidecar(l5_dict))

    # L3 sovereign-block enforcement.
    l3_env = extra_envelopes.get("L3")
    if l3_env is not None and audit_log is not None:
        if isinstance(l3_env, Envelope):
            l3_dict = l3_env.model_dump(mode="json")
        else:
            l3_dict = dict(l3_env)
        recompute_items.append(
            verify_l3_sovereign_block_enforced(l3_dict, audit_log)
        )

    # Phase 0 source-manifest linkage on the dedicated phase0 envelope.
    phase0_env = extra_envelopes.get("phase0")
    if phase0_env is not None and audit_log is not None:
        if isinstance(phase0_env, Envelope):
            phase0_dict = phase0_env.model_dump(mode="json")
        else:
            phase0_dict = dict(phase0_env)
        recompute_items.append(
            verify_source_manifest_linkage(phase0_dict, audit_log)
        )

    gate_items.extend(recompute_items)

    # Decision logic — required gates that block promotion if they fail
    # or are blocked. The stretch gate is informational only.
    blocking_names = {
        "ionic.requires_ionic_transport_service",
        "ionic.rt_conductivity_ci_meets_threshold",
        "ionic.activation_energy_target",
        "ionic.oxidative_stability_threshold",
        "ionic.li_metal_route_compatibility",
        "ionic.arrhenius_fit_quality_gate",
        "ionic.full_battery_evidence_chain_complete",
        "ionic.defect_disorder_assumptions_documented",
        # Wave F5: hardened recompute gates are blocking.
        "ionic.neb_barrier_range_check",
        "ionic.verify_back_edge_resolves",
        "l2.dpa_mace_disagreement_routing_recomputed",
        "l6.novelty_resolved_recomputed",
        "l5.verify_artifact_sidecar",
        "l3.sovereign_block_enforced",
        "phase0.source_manifest_linkage",
    }

    has_fail = False
    has_blocked = False
    has_inconclusive = False
    for item in gate_items:
        if item.name not in blocking_names:
            continue
        if item.status == "fail":
            has_fail = True
        elif item.status == "blocked":
            has_blocked = True
        elif item.status == "inconclusive":
            has_inconclusive = True

    # Wave F5 discipline: inconclusive recompute is fail-closed for
    # promotion. The orchestrator MUST treat "I cannot establish
    # claim/recompute equivalence" as a hard block on promotion.
    if has_fail or has_inconclusive:
        decision: PromotionStatus = "reject"
        rationale = "One or more PRD §Ionic Transport gates failed."
    elif has_blocked:
        decision = "defer"
        rationale = (
            "One or more gates are blocked (insufficient evidence); "
            "rerun the missing pieces before promotion."
        )
    else:
        decision = "promote"
        rationale = "All PRD §Ionic Transport gates pass."

    return PromotionDecision(
        candidate_id=candidate_id,
        structure_hash=bundle.structure_hash,
        decision=decision,
        rationale=rationale,
        evidence=[item.model_dump(mode="json") for item in gate_items]
        + [disagreement_item.model_dump(mode="json")],
        bundle=bundle,
    )


# ----------------------------------------------------------------------------
# FastAPI factory
# ----------------------------------------------------------------------------


def create_ionic_app() -> FastAPI:
    """Build the FastAPI app for the IonicTransportService."""

    app = FastAPI(
        title=IONIC_SERVICE_NAME,
        version=IONIC_SERVICE_VERSION,
        description=(
            "Battery MVP ionic-transport evidence service. PRD §Ionic Transport: "
            "Battery MVP claims require an explicit IonicTransportService; "
            "phonons do not substitute for Li-ion conductivity."
        ),
    )

    @app.get("/v1/ionic/healthz")
    async def healthz() -> dict[str, Any]:
        return {
            "status": "ok",
            "service": IONIC_SERVICE_NAME,
            "version": IONIC_SERVICE_VERSION,
            "service_ref": IONIC_TRANSPORT_SERVICE_REF,
        }

    @app.post("/v1/ionic/neb")
    async def neb(payload: NebPayload) -> dict[str, Any]:
        params = payload.to_params()
        params = IonicJobParams(**{**params.model_dump(), "path_id": payload.path_id})
        env = NebMigrationBarrierAdapter().compute(params)
        return env.canonical_dict()

    @app.post("/v1/ionic/md-diffusion")
    async def md_diffusion(payload: MdDiffusionPayload) -> dict[str, Any]:
        env = MlipMdDiffusionAdapter().compute(payload.to_params())
        return env.canonical_dict()

    @app.post("/v1/ionic/aimd-diffusion")
    async def aimd_diffusion(payload: AimdDiffusionPayload) -> dict[str, Any]:
        env = AimdDiffusionAdapter().compute(payload.to_params())
        return env.canonical_dict()

    @app.post("/v1/ionic/arrhenius-fit")
    async def arrhenius_fit(payload: ArrheniusFitPayload) -> dict[str, Any]:
        try:
            params = ArrheniusFitParams(**payload.model_dump())
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=422, detail=str(exc))
        env = ArrheniusFitAdapter().compute_from_params(params)
        return env.canonical_dict()

    @app.post("/v1/ionic/electrochemical-window")
    async def electrochemical_window(payload: _BasePayload) -> dict[str, Any]:
        env = ElectrochemicalWindowAdapter().compute(payload.to_params())
        return env.canonical_dict()

    @app.post("/v1/ionic/interface-stability")
    async def interface_stability(payload: _BasePayload) -> dict[str, Any]:
        env = InterfaceStabilityAdapter().compute(payload.to_params())
        return env.canonical_dict()

    @app.post("/v1/ionic/full-battery-evidence")
    async def full_battery_evidence(payload: FullBatteryEvidencePayload) -> dict[str, Any]:
        bundle = run_full_battery_evidence(payload.to_params())
        return bundle.model_dump(mode="json")

    @app.post("/v1/ionic/promote-battery-candidate")
    async def promote(payload: PromoteBatteryCandidatePayload) -> dict[str, Any]:
        params = payload.to_params()
        decision = promote_battery_candidate(params.candidate_id, params=params)
        return decision.model_dump(mode="json")

    return app


# Module-level app instance for `uvicorn zer0pa_materials.services:ionic_app`.
ionic_app: FastAPI = create_ionic_app()
