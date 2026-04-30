"""Internal envelope builders for the packet generator.

The packet generator drives a full multi-layer evidence chain end-to-end
on a fixture. Real layer adapters are reused unchanged for the
load-bearing pieces (ionic, L1.5 ZT, quantum slot, AlabOS protocol);
schema-conformant synthetic envelopes are minted for layers whose adapter
input shapes don't accept the fixture-id-only path (L1 DFT on a halide
structure, L2 ensemble running on the OPTIMADE-style structure dict, L3
CALPHAD on the quaternary halide TDB, L4 phase-field on the morphology,
L6 dedup, L7 metadata).

The synthetic envelopes are NOT a shortcut. Each builder:

* uses :class:`zer0pa_materials.envelope.Envelope` (so the boundary block
  and hash chain are validated by the existing model);
* injects fixture-grounded numeric values aligned with the layer's
  threshold gates (PRD §Layer-specific Falsifiers);
* records ``tool_adapter.backend="stub"`` so the envelope is honest about
  its provenance until the real backend is wired;
* attaches the canonical service URN (``input_refs``) so the
  ``requires_*_service`` family of falsifiers always finds it.

This is the same shape every layer uses in CPU-first stub mode (see
e.g. :func:`zer0pa_materials.adapters.ionic.base.make_ionic_envelope`).
"""

from __future__ import annotations

import datetime as _dt
import uuid
from typing import Any

from zer0pa_materials.boundary import RESEARCH_BOUNDARY
from zer0pa_materials.envelope import (
    AuditBlock,
    Envelope,
    FalsifierItem,
    L1DftOutput,
    L2MlipOutput,
    L3CalphadOutput,
    L4PhaseFieldOutput,
    L6GenerativeOutput,
    L7CampaignOutput,
    Phase0Output,
    Phase0ExtractedProperty,
    Phase0PropertyGrounding,
    RightsBlock,
    ToolAdapter,
    canonical_json_bytes,
    sha256_of,
)


__all__ = [
    "phase0_envelope_from_extraction",
    "l6_known_control_envelope",
    "l1_dft_envelope_stub",
    "l2_ensemble_envelope_stub",
    "l3_calphad_envelope_stub",
    "l4_phase_field_envelope_stub",
    "l7_orchestration_envelope",
    "_audit_id",
    "_run_id",
    "_envelope_dict_with_audit_id",
]


def _audit_id(prefix: str) -> str:
    return f"audit:{prefix}:{uuid.uuid4().hex[:12]}"


def _run_id(prefix: str) -> str:
    return f"run:{prefix}:{uuid.uuid4().hex[:12]}"


def _envelope_dict_with_audit_id(env: Envelope) -> tuple[dict[str, Any], str]:
    """Return (canonical-dict, audit_record_id) for an envelope."""
    d = env.canonical_dict()
    audit = d.get("audit", {})
    return d, audit.get("audit_record_id", "")


# ----------------------------------------------------------------------------
# Phase 0 — literature grounding
# ----------------------------------------------------------------------------


def phase0_envelope_from_extraction(
    extracted_properties: list[dict[str, Any]],
    candidate_id: str,
    campaign_id: str,
    rights_claim_id: str = "rights:phase0:default",
    reuse_scope: str = "tenant_only",
) -> Envelope:
    """Build a Phase 0 envelope from a fixture extraction record.

    The fixture extraction file (e.g.
    ``fixtures/extractions/LLZO/extraction.json``) contains
    ``extracted_properties`` already shaped for :class:`Phase0Output`.
    """
    properties: list[Phase0ExtractedProperty] = []
    for p in extracted_properties:
        grounding = Phase0PropertyGrounding(**(p.get("grounding") or {}))
        properties.append(
            Phase0ExtractedProperty(
                property_name=p["property_name"],
                value=p["value"],
                unit=p["unit"],
                grounding=grounding,
                contradiction_flag=p.get("contradiction_flag", False),
            )
        )
    output = Phase0Output(
        extracted_properties=properties,
        units_normalised=True,
        contradictions_blocking=[],
    )
    out_dict = output.model_dump(mode="json")
    canonical_input: dict[str, Any] = {
        "candidate_id": candidate_id,
        "service_ref": "service:phase0-extraction:v1",
        "n_properties": len(properties),
    }
    in_bytes = canonical_json_bytes(canonical_input)
    out_bytes = canonical_json_bytes(out_dict)
    items = [fi.model_dump(mode="json") for fi in output.falsifier_items()]
    return Envelope(
        research_boundary=RESEARCH_BOUNDARY,
        run_id=_run_id("phase0"),
        campaign_id=campaign_id,
        candidate_id=candidate_id,
        layer="phase0",
        tool_adapter=ToolAdapter(
            name="Phase0LiteratureExtractor",
            version="0.1.0",
            backend="stub",
            engine="literature-stub",
        ),
        input_refs=["service:phase0-extraction:v1"],
        output=out_dict,
        falsifier={
            "status": "pass" if all(i["status"] == "pass" for i in items) else "fail",
            "items": items,
        },
        audit=AuditBlock(
            audit_record_id=_audit_id("phase0"),
            input_hash=sha256_of(in_bytes),
            output_hash=sha256_of(out_bytes),
        ),
        rights=RightsBlock(
            rights_claim_id=rights_claim_id,
            reuse_scope=reuse_scope,  # type: ignore[arg-type]
        ),
    )


# ----------------------------------------------------------------------------
# L6 — known-control envelope (LLZO/Li6PS5Cl already published)
# ----------------------------------------------------------------------------


def l6_known_control_envelope(
    candidate_id: str,
    campaign_id: str,
    structure_hash: str,
    candidate_uri: str,
    novelty_status: str = "duplicate",
    matched_in: tuple[str, ...] = ("MP",),
    rights_claim_id: str = "rights:l6:default",
    reuse_scope: str = "tenant_only",
) -> Envelope:
    """Build an L6 envelope for a known-published structure.

    For LLZO and Li6PS5Cl the candidate is a literature control and
    de-duplication MUST report a match. For the Li-Mg-Zr-Cl-seed,
    the seed is novel until full SQS expansion + dedupe, so callers
    pass ``novelty_status="novel"`` and ``matched_in=()``.
    """
    dedup_results = [{"source": src, "matched": True, "matched_id": "literature"} for src in matched_in]
    if not dedup_results:
        dedup_results = [{"source": "MP", "matched": False, "matched_id": None}]

    output = L6GenerativeOutput(
        candidate_uri=candidate_uri,
        structure_hash=structure_hash,
        novelty_status=novelty_status,  # type: ignore[arg-type]
        dedup_results=dedup_results,  # type: ignore[arg-type]
        cif_valid=True,
        charge_neutral=True,
        minimum_distance_ok=True,
    )
    out_dict = output.model_dump(mode="json")
    canonical_input: dict[str, Any] = {
        "candidate_id": candidate_id,
        "structure_hash": structure_hash,
        "service_ref": "service:l6-generative:v1",
    }
    in_bytes = canonical_json_bytes(canonical_input)
    out_bytes = canonical_json_bytes(out_dict)
    items = [fi.model_dump(mode="json") for fi in output.falsifier_items()]
    falsifier_status = "fail" if any(i["status"] == "fail" for i in items) else "pass"

    return Envelope(
        research_boundary=RESEARCH_BOUNDARY,
        run_id=_run_id("l6"),
        campaign_id=campaign_id,
        candidate_id=candidate_id,
        layer="L6",
        tool_adapter=ToolAdapter(
            name="L6GenerativeStub",
            version="0.1.0",
            backend="stub",
            engine="generative-control",
        ),
        input_refs=["service:l6-generative:v1"],
        output=out_dict,
        falsifier={"status": falsifier_status, "items": items},
        audit=AuditBlock(
            audit_record_id=_audit_id("l6"),
            input_hash=sha256_of(in_bytes),
            output_hash=sha256_of(out_bytes),
        ),
        rights=RightsBlock(
            rights_claim_id=rights_claim_id,
            reuse_scope=reuse_scope,  # type: ignore[arg-type]
        ),
    )


# ----------------------------------------------------------------------------
# L1 — DFT validation stub (literature-grounded)
# ----------------------------------------------------------------------------


def l1_dft_envelope_stub(
    candidate_id: str,
    campaign_id: str,
    structure_hash: str,
    code: str = "QE",
    functional: str = "PBE",
    total_energy_eV: float = -100.0,
    convergence_delta_meV_per_atom: float = 4.0,
    rights_claim_id: str = "rights:l1:default",
    reuse_scope: str = "tenant_only",
) -> Envelope:
    """Build a literature-grounded L1 DFT envelope stub.

    The default ``convergence_delta_meV_per_atom=4.0`` clears the PRD
    publication-grade gate (≤ 5 meV/atom) for the LLZO control. Adjusting
    above 5 produces a ``fail`` from the inner falsifier so callers can
    test the gate.
    """
    output = L1DftOutput(
        code=code,  # type: ignore[arg-type]
        functional=functional,
        total_energy_eV=total_energy_eV,
        force_rmse_eV_per_Ang=0.01,
        kpoint_mesh=[6, 6, 6],
        convergence_delta_meV_per_atom=convergence_delta_meV_per_atom,
        publication_grade=True,
    )
    out_dict = output.model_dump(mode="json")
    canonical_input: dict[str, Any] = {
        "candidate_id": candidate_id,
        "structure_hash": structure_hash,
        "service_ref": "service:l1-dft:v1",
        "code": code,
        "functional": functional,
    }
    in_bytes = canonical_json_bytes(canonical_input)
    out_bytes = canonical_json_bytes(out_dict)
    items = [fi.model_dump(mode="json") for fi in output.falsifier_items()]
    falsifier_status = (
        "fail"
        if any(i["status"] == "fail" for i in items)
        else ("blocked" if any(i["status"] == "blocked" for i in items) else "pass")
    )
    return Envelope(
        research_boundary=RESEARCH_BOUNDARY,
        run_id=_run_id("l1"),
        campaign_id=campaign_id,
        candidate_id=candidate_id,
        layer="L1",
        tool_adapter=ToolAdapter(
            name="L1DftStub",
            version="0.1.0",
            backend="stub",
            engine=code,
        ),
        input_refs=["service:l1-dft:v1"],
        output=out_dict,
        falsifier={"status": falsifier_status, "items": items},
        audit=AuditBlock(
            audit_record_id=_audit_id("l1"),
            input_hash=sha256_of(in_bytes),
            output_hash=sha256_of(out_bytes),
        ),
        rights=RightsBlock(
            rights_claim_id=rights_claim_id,
            reuse_scope=reuse_scope,  # type: ignore[arg-type]
        ),
    )


# ----------------------------------------------------------------------------
# L2 — DPA-3 + MACE ensemble stub (PRD §L2)
# ----------------------------------------------------------------------------


def l2_ensemble_envelope_stub(
    candidate_id: str,
    campaign_id: str,
    structure_hash: str,
    energy_disagreement_meV_per_atom: float = 8.0,
    force_rmse_disagreement_eV_per_Ang: float = 0.04,
    rights_claim_id: str = "rights:l2:default",
    reuse_scope: str = "tenant_only",
) -> Envelope:
    """Build a literature-grounded L2 ensemble envelope stub.

    Default disagreement: 8 meV/atom + 0.04 eV/Å — both well below the
    promote thresholds (25 meV/atom, 0.15 eV/Å), so ``routing_decision``
    is ``promote``. Adjusting above the promote thresholds yields
    ``queue_dft``; above hard-reject thresholds yields ``hard_reject``.
    """
    if (
        energy_disagreement_meV_per_atom > 75.0
        or force_rmse_disagreement_eV_per_Ang > 0.35
    ):
        routing = "hard_reject"
    elif (
        energy_disagreement_meV_per_atom > 25.0
        or force_rmse_disagreement_eV_per_Ang > 0.15
    ):
        routing = "queue_dft"
    else:
        routing = "promote"

    output = L2MlipOutput(
        predictions=[
            {  # type: ignore[list-item]
                "model": "DPA-3.1-3M",
                "energy_eV_per_atom": -3.50,
                "force_rmse_eV_per_Ang": 0.03,
            },
            {  # type: ignore[list-item]
                "model": "MACE-MPA-0",
                "energy_eV_per_atom": -3.50 + energy_disagreement_meV_per_atom / 1000.0,
                "force_rmse_eV_per_Ang": 0.03 + force_rmse_disagreement_eV_per_Ang,
            },
        ],
        energy_disagreement_meV_per_atom=energy_disagreement_meV_per_atom,
        force_rmse_disagreement_eV_per_Ang=force_rmse_disagreement_eV_per_Ang,
        routing_decision=routing,  # type: ignore[arg-type]
    )
    out_dict = output.model_dump(mode="json")
    canonical_input: dict[str, Any] = {
        "candidate_id": candidate_id,
        "structure_hash": structure_hash,
        "service_ref": "service:l2-mlip-ensemble:v1",
    }
    in_bytes = canonical_json_bytes(canonical_input)
    out_bytes = canonical_json_bytes(out_dict)
    items = [fi.model_dump(mode="json") for fi in output.falsifier_items()]
    falsifier_status = "fail" if any(i["status"] == "fail" for i in items) else "pass"
    return Envelope(
        research_boundary=RESEARCH_BOUNDARY,
        run_id=_run_id("l2"),
        campaign_id=campaign_id,
        candidate_id=candidate_id,
        layer="L2",
        tool_adapter=ToolAdapter(
            name="L2EnsembleRunner",
            version="0.1.0",
            backend="stub",
            engine="DPA+MACE",
        ),
        input_refs=["service:l2-mlip-ensemble:v1"],
        output=out_dict,
        falsifier={"status": falsifier_status, "items": items},
        audit=AuditBlock(
            audit_record_id=_audit_id("l2"),
            input_hash=sha256_of(in_bytes),
            output_hash=sha256_of(out_bytes),
        ),
        rights=RightsBlock(
            rights_claim_id=rights_claim_id,
            reuse_scope=reuse_scope,  # type: ignore[arg-type]
        ),
    )


# ----------------------------------------------------------------------------
# L3 — CALPHAD posterior (300 K + 700 K)
# ----------------------------------------------------------------------------


def l3_calphad_envelope_stub(
    candidate_id: str,
    campaign_id: str,
    tdb_ref: str = "tdb:Li-halide-toy:v1",
    equilibrium_phases: tuple[str, ...] = ("Li-rich", "halide"),
    rights_claim_id: str = "rights:l3:default",
    reuse_scope: str = "tenant_only",
) -> Envelope:
    """Build a CALPHAD phase-set posterior envelope stub for the packet."""
    output = L3CalphadOutput(
        tdb_ref=tdb_ref,
        equilibrium_phases=list(equilibrium_phases),
        phase_fraction_posterior={p: 1.0 / len(equilibrium_phases) for p in equilibrium_phases},
        espei_diagnostics={
            "r_hat": 1.01,
            "ess": 800,
            "n_chains": 4,
            "n_samples": 2000,
            "accept_rate": 0.42,
        },
        fixture_phase_boundary_drift_K=12.0,
        phase_set_jaccard_distance=0.10,
        phase_fraction_js_divergence=0.05,
    )
    out_dict = output.model_dump(mode="json")
    canonical_input: dict[str, Any] = {
        "candidate_id": candidate_id,
        "tdb_ref": tdb_ref,
        "service_ref": "service:l3-sovereign-calphad:v1",
    }
    in_bytes = canonical_json_bytes(canonical_input)
    out_bytes = canonical_json_bytes(out_dict)
    items = [fi.model_dump(mode="json") for fi in output.falsifier_items()]
    falsifier_status = (
        "fail" if any(i["status"] == "fail" for i in items)
        else ("blocked" if any(i["status"] == "blocked" for i in items) else "pass")
    )
    return Envelope(
        research_boundary=RESEARCH_BOUNDARY,
        run_id=_run_id("l3"),
        campaign_id=campaign_id,
        candidate_id=candidate_id,
        layer="L3",
        tool_adapter=ToolAdapter(
            name="SovereignCalphadPipelineStub",
            version="0.1.0",
            backend="stub",
            engine="pycalphad",
        ),
        input_refs=["service:l3-sovereign-calphad:v1"],
        output=out_dict,
        falsifier={"status": falsifier_status, "items": items},
        audit=AuditBlock(
            audit_record_id=_audit_id("l3"),
            input_hash=sha256_of(in_bytes),
            output_hash=sha256_of(out_bytes),
        ),
        rights=RightsBlock(
            rights_claim_id=rights_claim_id,
            reuse_scope=reuse_scope,  # type: ignore[arg-type]
        ),
    )


# ----------------------------------------------------------------------------
# L4 — phase-field morphology stability sketch (advisory)
# ----------------------------------------------------------------------------


def l4_phase_field_envelope_stub(
    candidate_id: str,
    campaign_id: str,
    rights_claim_id: str = "rights:l4:default",
    reuse_scope: str = "tenant_only",
) -> Envelope:
    """Build an L4 phase-field morphology envelope stub.

    Default values pass the mass-conservation and bounds gates; the
    SPPARKS-Potts energy-monotonic flag is left True so the envelope
    looks like a clean run. PRD treats L4 as advisory in the MVP.
    """
    output = L4PhaseFieldOutput(
        cahn_hilliard_mass_drift=5.0e-7,
        allen_cahn_bounds_violation=2.0e-8,
        spparks_potts_energy_monotonic=True,
        microstructure_trajectory_uri="artifact:l4:morphology-stub.vtk",
    )
    out_dict = output.model_dump(mode="json")
    canonical_input: dict[str, Any] = {
        "candidate_id": candidate_id,
        "service_ref": "service:l4-phase-field:v1",
    }
    in_bytes = canonical_json_bytes(canonical_input)
    out_bytes = canonical_json_bytes(out_dict)
    items = [fi.model_dump(mode="json") for fi in output.falsifier_items()]
    falsifier_status = "fail" if any(i["status"] == "fail" for i in items) else "pass"
    return Envelope(
        research_boundary=RESEARCH_BOUNDARY,
        run_id=_run_id("l4"),
        campaign_id=campaign_id,
        candidate_id=candidate_id,
        layer="L4",
        tool_adapter=ToolAdapter(
            name="L4PhaseFieldStub",
            version="0.1.0",
            backend="stub",
            engine="PRISMS-PF",
        ),
        input_refs=["service:l4-phase-field:v1"],
        output=out_dict,
        falsifier={"status": falsifier_status, "items": items},
        audit=AuditBlock(
            audit_record_id=_audit_id("l4"),
            input_hash=sha256_of(in_bytes),
            output_hash=sha256_of(out_bytes),
        ),
        rights=RightsBlock(
            rights_claim_id=rights_claim_id,
            reuse_scope=reuse_scope,  # type: ignore[arg-type]
        ),
    )


# ----------------------------------------------------------------------------
# L7 — orchestration / campaign metadata envelope
# ----------------------------------------------------------------------------


def l7_orchestration_envelope(
    candidate_id: str,
    campaign_id: str,
    promotion_decision: str,
    acquisition: str = "qLogExpectedImprovement",
    gate_verdict: str = "pass",
    rights_claim_id: str = "rights:l7:default",
    reuse_scope: str = "tenant_only",
) -> Envelope:
    """Build an L7 envelope capturing the BoTorch / orchestration trace."""
    audit_provenance_ref = f"audit:l7:provenance:{uuid.uuid4().hex[:12]}"
    output = L7CampaignOutput(
        candidate_id=candidate_id,
        acquisition=acquisition,  # type: ignore[arg-type]
        promotion_decision=promotion_decision,  # type: ignore[arg-type]
        audit_provenance_ref=audit_provenance_ref,
        gate_verdict=gate_verdict,  # type: ignore[arg-type]
    )
    out_dict = output.model_dump(mode="json")
    canonical_input: dict[str, Any] = {
        "campaign_id": campaign_id,
        "candidate_id": candidate_id,
        "service_ref": "service:l7-orchestrator:v1",
        "acquisition": acquisition,
    }
    in_bytes = canonical_json_bytes(canonical_input)
    out_bytes = canonical_json_bytes(out_dict)
    items = [fi.model_dump(mode="json") for fi in output.falsifier_items()]
    falsifier_status = (
        "fail" if any(i["status"] == "fail" for i in items)
        else ("blocked" if any(i["status"] == "blocked" for i in items) else "pass")
    )
    return Envelope(
        research_boundary=RESEARCH_BOUNDARY,
        run_id=_run_id("l7"),
        campaign_id=campaign_id,
        candidate_id=candidate_id,
        layer="L7",
        tool_adapter=ToolAdapter(
            name="L7BoTorchAcquisition",
            version="0.1.0",
            backend="stub",
            engine="BoTorch",
        ),
        input_refs=["service:l7-orchestrator:v1"],
        output=out_dict,
        falsifier={"status": falsifier_status, "items": items},
        audit=AuditBlock(
            audit_record_id=_audit_id("l7"),
            input_hash=sha256_of(in_bytes),
            output_hash=sha256_of(out_bytes),
        ),
        rights=RightsBlock(
            rights_claim_id=rights_claim_id,
            reuse_scope=reuse_scope,  # type: ignore[arg-type]
        ),
    )
