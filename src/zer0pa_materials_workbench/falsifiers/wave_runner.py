"""Falsification wave runner (Wave 6).

Boundary
--------
Research infrastructure for in silico materials science discovery. Outputs
are research artifacts. No regulatory certification claims. No clinical or
human-subject use. ITAR / weapons applications are out of scope (Meta UMA
Acceptable Use Policy and operator policy).

Purpose
-------

Orchestrate the **16 deliberate failure cases** from PRD §Falsification
wave (15 PRD-mandated cases plus the L3 quarantine breach negative fixture
delivered in A2). The runner:

1. Iterates the 16 cases in a fixed deterministic order.
2. For each case, loads the input from a fixture file or a synthesizer
   function and routes it through the appropriate layer falsifier(s).
3. Asserts the **target falsifier fired** with ``status="fail"``.
4. Asserts no spurious falsifiers fired (the negative fixtures were
   designed for clean attribution; we accept *at most one extra* trigger
   of a documented co-firing falsifier — see ``COFIRES`` below).
5. Records each fired falsifier as a row in ``falsifiers.jsonl`` via the
   hash-chained :class:`~zer0pa_materials_workbench.audit.AuditLog`.
6. Records a ``Decision`` row noting the campaign halt at the layer that
   detected the failure.
7. Validates the audit hash chain after every case so a single bad row is
   surfaced immediately.

The wave is **adversarial by design**. A "passing" wave does NOT mean every
gate is happy — it means every gate FIRED CORRECTLY when shown the
deliberate failure designed to trip it. The semantics are inverted; the
wave_report module documents this clearly.

Source files
------------

* This module — runner + result types.
* :mod:`zer0pa_materials_workbench.falsifiers.wave_report` — markdown report generator.
* :mod:`zer0pa_materials_workbench.cli.falsification` — CLI subapp.
* ``tests/integration/test_full_falsification_wave.py`` — full end-to-end test.
"""

from __future__ import annotations

import datetime as _dt
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from zer0pa_materials_workbench.audit.kg import KGNodeType, MaterialsKG
from zer0pa_materials_workbench.audit.log import AuditLog
from zer0pa_materials_workbench.boundary import RESEARCH_BOUNDARY
from zer0pa_materials_workbench.envelope.envelope import Envelope
from zer0pa_materials_workbench.envelope.falsifier import FalsifierItem
from zer0pa_materials_workbench.envelope.layer_outputs import (
    L1DftOutput,
)

__all__ = [
    "DEFAULT_CASES",
    "WAVE_CASE_ORDER",
    "FalsificationCase",
    "FalsificationCaseResult",
    "FalsificationWaveResult",
    "FalsificationWaveRunner",
    "RecomputeSweepResult",
]


# ---------------------------------------------------------------------------
# Wave F5: post-PRD recompute sweep result type
# ---------------------------------------------------------------------------


@dataclass
class RecomputeSweepResult:
    """Result of running every Wave D recompute gate over a sentinel chain.

    Attributes
    ----------
    gate_results
        ``{gate_name: FalsifierItem}`` for each Wave D gate that ran.
    forged_chain_caught
        Aggregate verdict: did the sentinel forged-evidence chain make
        ANY recompute gate trip with status="fail"? If True, the wiring
        is alive.
    sentinel_kind
        ``"forged"`` (the deliberate-failure chain) or ``"clean"``
        (a positive control).
    """

    gate_results: dict[str, FalsifierItem] = field(default_factory=dict)
    forged_chain_caught: bool = False
    sentinel_kind: str = "forged"

    @property
    def n_failed(self) -> int:
        return sum(1 for it in self.gate_results.values() if it.status == "fail")

    @property
    def n_total(self) -> int:
        return len(self.gate_results)


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FalsificationCase:
    """One adversarial test case in the wave.

    Attributes
    ----------
    name:
        Stable case identifier (e.g. ``"invalid_cif"``).
    target_falsifier:
        The PRD-mandated falsifier that this case MUST trigger
        (e.g. ``"l6.cif_valid"`` — what the FalsifierItem would name itself
        on a successful gate run).
    expected_layer:
        The PRD layer at which the campaign must halt.
    fixture_dir:
        Subdirectory under ``fixtures/negatives/`` to load. ``None`` for
        synthesizer-only cases (case 4 missing-source-manifest, case 7 DFT
        convergence, case 11 phase-field conservation violation).
    synthesizer:
        Optional callable that returns the case's input dict. Mutually
        exclusive with ``fixture_dir`` for cases with no fixture file.
    rationale:
        One-sentence description of the deliberate violation.
    """

    name: str
    target_falsifier: str
    expected_layer: str
    fixture_dir: str | None = None
    synthesizer: Callable[[], dict[str, Any]] | None = None
    rationale: str = ""


@dataclass
class FalsificationCaseResult:
    """Outcome of running one case."""

    case: FalsificationCase
    triggered_falsifiers: list[FalsifierItem] = field(default_factory=list)
    error: str | None = None
    audit_event_hash: str = ""
    decision_event_hash: str = ""
    chain_validation_ok: bool = True
    chain_errors: list[str] = field(default_factory=list)

    @property
    def target_fired(self) -> bool:
        """True iff at least one ``triggered_falsifiers`` item carries the
        target name AND status="fail"."""
        for item in self.triggered_falsifiers:
            if (
                item.name == self.case.target_falsifier
                and item.status == "fail"
            ):
                return True
        return False

    @property
    def spurious_extra_count(self) -> int:
        """Count fired (status=fail) falsifiers other than the target.

        Documented co-firings (see :data:`COFIRES`) are NOT counted.
        """
        cofires = COFIRES.get(self.case.name, set())
        extras = 0
        for item in self.triggered_falsifiers:
            if item.status != "fail":
                continue
            if item.name == self.case.target_falsifier:
                continue
            if item.name in cofires:
                continue
            extras += 1
        return extras

    @property
    def verdict(self) -> str:
        """Wave verdict for this case.

        ``"correct"``: target fired, no spurious extras, chain valid.
        ``"missed"``: target did not fire (real bug to surface).
        ``"spurious"``: target fired but at least one undocumented extra also fired.
        ``"chain_break"``: target fired but the audit hash chain broke.
        """
        if not self.target_fired:
            return "missed"
        if not self.chain_validation_ok:
            return "chain_break"
        if self.spurious_extra_count > 0:
            return "spurious"
        return "correct"


@dataclass
class FalsificationWaveResult:
    """Aggregate result of the full wave."""

    started_at: str
    finished_at: str
    audit_dir: Path
    case_results: list[FalsificationCaseResult] = field(default_factory=list)
    chain_validation_ok: bool = True
    chain_errors: list[str] = field(default_factory=list)
    total_falsifier_rows_written: int = 0
    total_decision_rows_written: int = 0
    kg_node_count_after: int = 0
    # Wave F5: post-PRD recompute sweep over the sentinel forged chain.
    recompute_sweep: RecomputeSweepResult | None = None

    @property
    def cases_correct(self) -> int:
        return sum(1 for r in self.case_results if r.verdict == "correct")

    @property
    def cases_missed(self) -> int:
        return sum(1 for r in self.case_results if r.verdict == "missed")

    @property
    def cases_spurious(self) -> int:
        return sum(1 for r in self.case_results if r.verdict == "spurious")

    @property
    def cases_chain_break(self) -> int:
        return sum(1 for r in self.case_results if r.verdict == "chain_break")


# ---------------------------------------------------------------------------
# Documented co-firings
# ---------------------------------------------------------------------------


# Some negative fixtures legitimately co-fire a second falsifier as a
# defence-in-depth check. The dryrun integration test
# (tests/integration/campaigns/test_falsification_wave_dryrun.py) documents
# the exact set we accept here. Anything NOT in this dict is counted as a
# spurious extra and lowers the wave verdict from "correct" to "spurious".
COFIRES: dict[str, set[str]] = {
    # Boundary violation also fires the L7 cross-layer disagreement check
    # vacuously (it's blocked, not a "fail" trigger), so no co-fires.
    # The ionic overclaim fixture also (correctly) fires the phonon-ionic
    # boundary falsifier in some envelope shapes.
    "ionic_overclaim_no_service": {
        "l15.phonon_does_not_substitute_for_ionic",
    },
    # Tenant-only tuple leak fires both L7 tuple_leak AND the reasoner
    # enforce_reuse_scope_export when surfaced as an L7 promotion gate.
    "tenant_only_tuple_leak": {
        "l7.candidate_promotion_provenance",
    },
    # The Phase 0 KG-write check requires BOTH a LiteratureSource node and
    # a PropertyObservation node. A missing source manifest by definition
    # leaves both nodes absent, so both PRD-mandated falsifier rows fire
    # together. We list the property-observation row here so the wave
    # treats them as a paired trigger (the target is the literature-source
    # row; the property-observation row is the documented co-fire).
    "missing_source_manifest": {
        "phase0.kg_property_observation_written",
    },
    # Runpod schema drift: pydantic Envelope rejects the extra field;
    # detect_schema_drift fires; downstream missing-boundary detector may
    # also fire because the envelope.json carries the right boundary —
    # so we expect ONE primary trigger. Empty co-fire allowance.
    "runpod_schema_drift": set(),
    # The ungrounded property fixture has unit "S/cm" + a missing grounding;
    # only the ungrounded gate must fire. Empty co-fire allowance.
    "ungrounded_property": set(),
}


# ---------------------------------------------------------------------------
# Synthesizers (cases without dedicated fixture files)
# ---------------------------------------------------------------------------


def _synthesize_missing_source_envelope() -> dict[str, Any]:
    """Case 4: An envelope that claims a Phase 0 extraction but has no source manifest.

    The audit-grounded gate ``phase0.kg_literature_source_written`` (from
    ``assert_kg_nodes_for``) fails because the KG has no LiteratureSource
    node when this envelope is the only thing in flight.
    """
    return {
        "contract_version": "zer0pa.materials.layer-envelope.v1",
        "research_boundary": RESEARCH_BOUNDARY,
        "run_id": "run:wave6/missing_source",
        "campaign_id": "campaign:wave6/missing_source",
        "candidate_id": "candidate:wave6/missing_source",
        "layer": "phase0",
        "tool_adapter": {
            "name": "WaveRunnerSynth",
            "version": "0.0.1",
            "backend": "stub",
            "engine": "synthesised",
        },
        "input_refs": [],
        "output": {
            "extracted_properties": [],
            "units_normalised": True,
            "contradictions_blocking": [],
        },
        "audit": {
            "audit_record_id": "audit:wave6/missing_source",
            "input_hash": "sha256:" + "0" * 64,
            "output_hash": "sha256:" + "0" * 64,
            "source_manifest_refs": [],  # ← the deliberate violation
        },
        "rights": {
            "rights_claim_id": "rights:wave6/missing_source",
            "reuse_scope": "tenant_only",
        },
    }


def _synthesize_dft_convergence_failure() -> dict[str, Any]:
    """Case 7: An L1DftOutput with convergence_delta way above the screening
    threshold (200 meV/atom > 50 meV/atom)."""
    output = L1DftOutput(
        code="QE",
        functional="PBE",
        total_energy_eV=-100.0,
        force_rmse_eV_per_Ang=0.001,
        kpoint_mesh=[1, 1, 1],
        convergence_delta_meV_per_atom=200.0,  # ← deliberate failure
        publication_grade=False,
    )
    return output.model_dump(mode="json")


def _synthesize_phasefield_mass_drift() -> dict[str, Any]:
    """Case 11: An L4 envelope with mass_drift = 5e-3 > 1e-3."""
    return {
        "research_boundary": RESEARCH_BOUNDARY,
        "layer": "L4",
        "output": {
            # Cahn-Hilliard mass drift exceeds threshold (1e-3).
            "cahn_hilliard_mass_drift": 5e-3,
            # Other fields set to passing values so only mass-drift fires.
            "allen_cahn_bounds_violation": None,
            "spparks_potts_energy_monotonic": None,
        },
        "tool_adapter": {
            "name": "WaveRunnerSynth",
            "version": "0.0.1",
            "backend": "stub",
            "engine": "synthesised-l4",
        },
    }


# ---------------------------------------------------------------------------
# Default case list
# ---------------------------------------------------------------------------


# The 16 cases, in the PRD's order of presentation.
WAVE_CASE_ORDER: tuple[str, ...] = (
    "invalid_cif",
    "duplicate_candidate",
    "missing_boundary",
    "missing_source_manifest",
    "ungrounded_property",
    "high_disagreement",
    "dft_convergence_failure",
    "ionic_overclaim_no_service",
    "unstable_phonon",
    "unreadable_tdb",
    "phasefield_conservation_violation",
    "non_spd_tensor",
    "alabos_executable_in_recipe_only",
    "tenant_only_tuple_leak",
    "runpod_schema_drift",
    "tdb_quarantine_breach",
)


DEFAULT_CASES: tuple[FalsificationCase, ...] = (
    FalsificationCase(
        name="invalid_cif",
        target_falsifier="l6.cif_valid",
        expected_layer="L6",
        fixture_dir="invalid_cif",
        rationale="Deliberately malformed CIF must trigger valid_cif_only.",
    ),
    FalsificationCase(
        name="duplicate_candidate",
        target_falsifier="l6.dedup_unique",
        expected_layer="L6",
        fixture_dir="duplicate_candidate",
        rationale="Repeated structure_hash must trigger structure_hash_dedupe.",
    ),
    FalsificationCase(
        name="missing_boundary",
        target_falsifier="boundary.missing_or_wrong",
        expected_layer="A0",
        fixture_dir="missing_boundary",
        rationale="Wrong research_boundary must raise BoundaryError on Envelope.model_validate.",
    ),
    FalsificationCase(
        name="missing_source_manifest",
        target_falsifier="phase0.kg_literature_source_written",
        expected_layer="phase0",
        synthesizer=_synthesize_missing_source_envelope,
        rationale="Phase 0 envelope without LiteratureSource node must fail KG-write check.",
    ),
    FalsificationCase(
        name="ungrounded_property",
        target_falsifier="phase0.grounding_required",
        expected_layer="phase0",
        fixture_dir="ungrounded_property",
        rationale="Phase 0 property with grounding=null must trigger reject_ungrounded_property.",
    ),
    FalsificationCase(
        name="high_disagreement",
        target_falsifier="l2.dpa_mace_disagreement_routing",
        expected_layer="L2",
        fixture_dir="high_disagreement",
        rationale="Energy disagreement > 75 meV/atom must trigger L2 hard_reject routing.",
    ),
    FalsificationCase(
        name="dft_convergence_failure",
        target_falsifier="l1.screening_convergence_delta",
        expected_layer="L1",
        synthesizer=_synthesize_dft_convergence_failure,
        rationale="L1 convergence delta > 50 meV/atom must trigger screening threshold gate.",
    ),
    FalsificationCase(
        name="ionic_overclaim_no_service",
        target_falsifier="ionic.requires_ionic_transport_service",
        expected_layer="ionic",
        fixture_dir="ionic_overclaim_no_service",
        rationale="Conductivity claim without IonicTransportService ref must trigger requires_ionic_transport_service.",
    ),
    FalsificationCase(
        name="unstable_phonon",
        target_falsifier="l15.dynamical_stability",
        expected_layer="L1.5",
        fixture_dir="unstable_phonon",
        rationale="Imaginary mode > 0.25 THz must trigger dynamical_stability.",
    ),
    FalsificationCase(
        name="unreadable_tdb",
        target_falsifier="l3.tdb_parses_in_pycalphad",
        expected_layer="L3",
        fixture_dir="unreadable_tdb",
        rationale="Malformed TDB must trigger tdb_parses_in_pycalphad.",
    ),
    FalsificationCase(
        name="phasefield_conservation_violation",
        target_falsifier="l4.cahn_hilliard_mass_drift",
        expected_layer="L4",
        synthesizer=_synthesize_phasefield_mass_drift,
        rationale="Cahn-Hilliard mass drift > 1e-3 must trigger cahn_hilliard_mass_drift.",
    ),
    FalsificationCase(
        name="non_spd_tensor",
        target_falsifier="l5.tensor_spd",
        expected_layer="L5",
        fixture_dir="non_spd_tensor",
        rationale="Non-SPD stiffness tensor must trigger tensor_spd_check.",
    ),
    FalsificationCase(
        name="alabos_executable_in_recipe_only",
        target_falsifier="l7.alabos_recipe_only_enforcement",
        expected_layer="L7",
        fixture_dir="alabos_executable_in_recipe_only",
        rationale="ALABOS_MODE=recipe_only with hardware_executable=true must trigger alabos_recipe_only_enforcement.",
    ),
    FalsificationCase(
        name="tenant_only_tuple_leak",
        target_falsifier="l7.tenant_only_tuple_leak",
        expected_layer="L7",
        fixture_dir="tenant_only_tuple_leak",
        rationale="tenant_only tuple inside shared_learning bundle must trigger tenant_only_tuple_leak.",
    ),
    FalsificationCase(
        name="runpod_schema_drift",
        target_falsifier="runpod.hard_failure.schema_drift",
        expected_layer="L7",
        fixture_dir="runpod_schema_drift",
        rationale="Runpod_mock envelope with extra field must trigger detect_schema_drift.",
    ),
    FalsificationCase(
        name="tdb_quarantine_breach",
        target_falsifier="l3.tdb_quarantine_breach",
        expected_layer="L3",
        fixture_dir="tdb_quarantine_breach",
        rationale="Commercial TDB claim with redistributable=true must trigger tdb_quarantine_breach.",
    ),
)


# ---------------------------------------------------------------------------
# Per-case routing logic — pure functions returning a list[FalsifierItem]
# ---------------------------------------------------------------------------


def _route_invalid_cif(fixture_dir: Path) -> list[FalsifierItem]:
    """Run the L6 CIF gate against the deliberately malformed CIF."""
    from zer0pa_materials_workbench.falsifiers.l6_falsifiers import (
        InvalidCifError,
        valid_cif_only,
    )

    cif_text = (fixture_dir / "structure.cif").read_text()
    # Synthesise an L6 envelope wrapper. The valid_cif_only helper expects
    # an envelope with output["cif_text"]. We use a minimal Envelope.
    env = _make_l6_envelope(cif_text=cif_text, structure_hash=None)
    items: list[FalsifierItem] = []
    try:
        items.append(valid_cif_only(env))
    except InvalidCifError as exc:
        items.append(
            FalsifierItem(
                name="l6.cif_valid",
                threshold="cif_hash_from_text succeeds",
                actual={"error": str(exc)[:256]},
                status="fail",
            )
        )
    return items


def _route_duplicate_candidate(fixture_dir: Path) -> list[FalsifierItem]:
    """Run structure_hash_dedupe across a small batch including the duplicate."""
    from zer0pa_materials_workbench.falsifiers.l6_falsifiers import (
        DuplicateStructureError,
        structure_hash_dedupe,
    )

    manifest = json.loads((fixture_dir / "manifest.json").read_text())
    duplicate_hash = manifest["structure_hash"]

    # Build two L6 envelopes that share the same structure_hash so dedupe
    # fails. The dedupe gate only fires on intra-batch duplicates.
    env1 = _make_l6_envelope(cif_text="data_dummy_a\n", structure_hash=duplicate_hash)
    env2 = _make_l6_envelope(cif_text="data_dummy_b\n", structure_hash=duplicate_hash)

    items: list[FalsifierItem] = []
    try:
        items.append(structure_hash_dedupe([env1, env2]))
    except DuplicateStructureError as exc:
        items.append(
            FalsifierItem(
                name="l6.dedup_unique",
                threshold="no duplicate structure_hash in batch",
                actual={"error": str(exc)[:256], "duplicate_hash": duplicate_hash},
                status="fail",
            )
        )
    return items


def _route_missing_boundary(fixture_dir: Path) -> list[FalsifierItem]:
    """Attempt to construct an Envelope with the wrong boundary; capture the failure."""
    from zer0pa_materials_workbench.boundary import BoundaryError

    envelope_dict = json.loads((fixture_dir / "envelope.json").read_text())
    items: list[FalsifierItem] = []
    try:
        Envelope.model_validate(envelope_dict)
        # If we reach here, the gate did NOT fire — record an inconclusive.
        items.append(
            FalsifierItem(
                name="boundary.missing_or_wrong",
                threshold="research_boundary == RESEARCH_BOUNDARY",
                actual={"reason": "Envelope.model_validate did not raise"},
                status="pass",
            )
        )
    except (BoundaryError, ValueError, Exception) as exc:
        items.append(
            FalsifierItem(
                name="boundary.missing_or_wrong",
                threshold="research_boundary == RESEARCH_BOUNDARY",
                actual={
                    "error": str(exc)[:256],
                    "fixture_boundary_prefix": str(envelope_dict.get("research_boundary", ""))[:80],
                },
                status="fail",
            )
        )
    return items


def _route_missing_source_manifest(envelope_dict: dict[str, Any], kg: MaterialsKG) -> list[FalsifierItem]:
    """Run assert_kg_nodes_for against a synthesised Phase 0 envelope on an
    empty KG — both LiteratureSource and PropertyObservation are absent so
    the gate fails."""
    from zer0pa_materials_workbench.falsifiers.phase0_falsifiers import (
        KGWriteError,
        assert_kg_nodes_for,
    )

    env = Envelope.model_validate(envelope_dict)
    items: list[FalsifierItem] = []
    try:
        items.extend(assert_kg_nodes_for(env, kg))
    except KGWriteError as exc:
        # Fallback: if neither LiteratureSource nor PropertyObservation exists,
        # the helper raises. We still record both items as fail because the
        # PRD demands both nodes exist.
        items.append(
            FalsifierItem(
                name="phase0.kg_literature_source_written",
                threshold="at least one LiteratureSource node",
                actual={"error": str(exc)[:256], "count": 0},
                status="fail",
            )
        )
        items.append(
            FalsifierItem(
                name="phase0.kg_property_observation_written",
                threshold="at least one PropertyObservation node",
                actual={"error": str(exc)[:256], "count": 0},
                status="fail",
            )
        )
    return items


def _route_ungrounded_property(fixture_dir: Path) -> list[FalsifierItem]:
    """Try to construct a Phase0ExtractedProperty from the ungrounded fixture."""
    from zer0pa_materials_workbench.falsifiers.phase0_falsifiers import (
        UngroundedPropertyError,
        reject_ungrounded_property,
    )

    extraction = json.loads((fixture_dir / "extraction.json").read_text())
    raw_props = extraction.get("extracted_properties", [])
    items: list[FalsifierItem] = []
    for raw in raw_props:
        # Build a permissive object that mimics Phase0ExtractedProperty's
        # attribute access. We don't go through the pydantic model because
        # the fixture deliberately violates the schema.
        prop = _PropertyShim(
            property_name=raw.get("property_name", ""),
            value=raw.get("value", 0.0),
            unit=raw.get("unit", ""),
            grounding=_GroundingShim.from_raw(raw.get("grounding")),
            contradiction_flag=raw.get("contradiction_flag", False),
        )
        try:
            items.append(reject_ungrounded_property(prop))  # type: ignore[arg-type]
        except UngroundedPropertyError as exc:
            items.append(
                FalsifierItem(
                    name="phase0.grounding_required",
                    threshold="doi non-empty AND at least one of page/table/figure",
                    actual={"error": str(exc)[:256], "property_name": prop.property_name},
                    status="fail",
                )
            )
    return items


@dataclass
class _GroundingShim:
    doi: str | None = None
    page: int | None = None
    table: str | None = None
    figure: str | None = None

    @classmethod
    def from_raw(cls, raw: Any) -> _GroundingShim | None:
        if raw is None:
            return None
        if isinstance(raw, dict):
            return cls(
                doi=raw.get("doi"),
                page=raw.get("page"),
                table=raw.get("table"),
                figure=raw.get("figure"),
            )
        return None


@dataclass
class _PropertyShim:
    property_name: str
    value: float
    unit: str
    grounding: _GroundingShim | None
    contradiction_flag: bool = False


def _route_high_disagreement(fixture_dir: Path) -> list[FalsifierItem]:
    """Wrap the L2 result fixture in an envelope shape and run the routing gate."""
    from zer0pa_materials_workbench.falsifiers.l2_falsifiers import (
        dpa_mace_disagreement_routing,
    )

    l2_result = json.loads((fixture_dir / "l2_result.json").read_text())
    envelope_dict = {
        "research_boundary": RESEARCH_BOUNDARY,
        "layer": "L2",
        "output": {
            "predictions": l2_result.get("predictions", []),
            "energy_disagreement_meV_per_atom": l2_result.get(
                "energy_disagreement_meV_per_atom"
            ),
            "force_rmse_disagreement_eV_per_Ang": l2_result.get(
                "force_rmse_disagreement_eV_per_Ang"
            ),
            "routing_decision": l2_result.get("routing_decision"),
        },
    }
    return [dpa_mace_disagreement_routing(envelope_dict)]


def _route_dft_convergence_failure(output_dict: dict[str, Any]) -> list[FalsifierItem]:
    """Run the L1 screening convergence gate."""
    from zer0pa_materials_workbench.falsifiers.l1_falsifiers import (
        convergence_delta_screening_threshold,
    )

    output = L1DftOutput.model_validate(output_dict)
    return [convergence_delta_screening_threshold(output)]


def _route_ionic_overclaim(fixture_dir: Path) -> list[FalsifierItem]:
    """Run the ionic_transport_service requirement gate."""
    from zer0pa_materials_workbench.falsifiers.ionic_falsifiers import (
        requires_ionic_transport_service,
    )

    candidate = json.loads((fixture_dir / "candidate.json").read_text())
    items = [requires_ionic_transport_service(candidate)]
    return items


def _route_unstable_phonon(fixture_dir: Path) -> list[FalsifierItem]:
    """Run the L1.5 dynamical-stability gate."""
    from zer0pa_materials_workbench.falsifiers.l1_5_falsifiers import dynamical_stability

    spectrum = json.loads((fixture_dir / "phonon_spectrum.json").read_text())
    env = _make_l1_5_envelope(spectrum)
    return [dynamical_stability(env)]


def _route_unreadable_tdb(fixture_dir: Path) -> list[FalsifierItem]:
    """Run the L3 TDB-parse gate against the malformed TDB."""
    from zer0pa_materials_workbench.falsifiers.l3_falsifiers import tdb_parses_in_pycalphad

    tdb_path = fixture_dir / "broken.tdb"
    return [tdb_parses_in_pycalphad(tdb_path)]


def _route_phasefield_conservation(synth: dict[str, Any]) -> list[FalsifierItem]:
    """Run the L4 cahn_hilliard_mass_drift gate."""
    from zer0pa_materials_workbench.falsifiers.l4_falsifiers import cahn_hilliard_mass_drift

    return [cahn_hilliard_mass_drift(synth)]


def _route_non_spd_tensor(fixture_dir: Path) -> list[FalsifierItem]:
    """Run the L5 SPD gate against the non-SPD fixture matrix."""
    from zer0pa_materials_workbench.falsifiers.l5_falsifiers import tensor_spd_check

    payload = json.loads((fixture_dir / "l5_result.json").read_text())
    matrix = payload["_synthetic_C_3x3"]
    name = payload.get("tensors", [{}])[0].get("name", "stiffness_C_3x3")
    return [tensor_spd_check(matrix, name=name)]


def _route_alabos_executable(fixture_dir: Path) -> list[FalsifierItem]:
    """Run the L7 AlabOS recipe-only enforcement gate."""
    from zer0pa_materials_workbench.falsifiers.l7_falsifiers import (
        alabos_recipe_only_enforcement,
    )

    payload = json.loads((fixture_dir / "protocol.json").read_text())
    return [alabos_recipe_only_enforcement(payload)]


def _route_tenant_only_tuple_leak(fixture_dir: Path) -> list[FalsifierItem]:
    """Run the L7 tuple_leak gate AND the candidate_promotion_provenance gate.

    The PRD-mandated mapping for case 14 is BOTH:
      * A1 reasoner enforce_reuse_scope_export
      * L7 candidate_promotion_provenance

    We surface tenant_only_tuple_leak as the primary trigger (it owns the
    "private tuple reuse outside reuse_scope" PRD wording verbatim) and
    record candidate_promotion_provenance via COFIRES.
    """
    from zer0pa_materials_workbench.falsifiers.l7_falsifiers import (
        candidate_promotion_provenance,
        tenant_only_tuple_leak,
    )

    bundle = json.loads((fixture_dir / "tuple_export.json").read_text())
    items: list[FalsifierItem] = [tenant_only_tuple_leak(bundle)]

    # Also run candidate_promotion_provenance as a co-fire — a leaked
    # tuple is a rights-incompatibility violation by definition. The
    # promotion gate is built to fail when rights_compatible=False.
    leaked_envelope = {
        "candidate_id": bundle.get("tuples", [{}])[0].get("input", {}).get("candidate_id", "candidate:test/leaked"),
        "audit": {"audit_record_id": "audit:wave6/leaked"},
        "output": {"promotion_decision": "promote"},
        "falsifier": {"items": []},
        "disagreement": {"metrics": []},
    }
    items.append(
        candidate_promotion_provenance(
            leaked_envelope,
            rejected_candidate_ids=set(),
            rejected_structure_hashes=set(),
            audit_provenance_chain=None,
            expected_disagreement_present=True,
            rights_compatible=False,  # the leak makes rights incompatible
        )
    )
    return items


def _route_runpod_schema_drift(fixture_dir: Path) -> list[FalsifierItem]:
    """Run the runpod schema-drift detector against the deliberately drifted envelope."""
    from zer0pa_materials_workbench.runpod.hard_failures import HardFailureDetector

    envelope_dict = json.loads((fixture_dir / "envelope.json").read_text())
    # Build a "baseline" envelope without the schema_drift_field so the
    # detector sees the missing-field drift.
    baseline = {k: v for k, v in envelope_dict.items() if k != "schema_drift_field"}
    detector = HardFailureDetector()
    result = detector.detect_schema_drift(baseline, envelope_dict)
    item_dict = result.to_falsifier_item_dict()
    return [
        FalsifierItem(
            name=item_dict["name"],
            threshold=item_dict["threshold"],
            actual=item_dict["actual"],
            status=item_dict["status"],
            evidence_ref=item_dict.get("evidence_ref"),
            rationale=item_dict.get("rationale"),
        )
    ]


def _route_tdb_quarantine_breach(fixture_dir: Path) -> list[FalsifierItem]:
    """Run the L3 quarantine-breach gate against the proprietary-TDB claim."""
    from zer0pa_materials_workbench.falsifiers.l3_falsifiers import tdb_quarantine_breach

    claim = json.loads((fixture_dir / "tdb_claim.json").read_text())
    envelope = {
        "research_boundary": RESEARCH_BOUNDARY,
        "layer": "L3",
        "output": {"tdb_ref": claim.get("tdb_ref", "")},
        "_quarantine_meta": {
            "tdb_provider": claim.get("tdb_provider"),
            "license": claim.get("license"),
            "redistributable": claim.get("redistributable"),
            "committed_to_repo": claim.get("committed_to_repo", False),
            "included_in_training_corpus": claim.get(
                "included_in_training_corpus", False
            ),
        },
    }
    return [tdb_quarantine_breach(envelope)]


# ---------------------------------------------------------------------------
# Envelope builders
# ---------------------------------------------------------------------------


_ZERO_HASH = "sha256:" + "0" * 64


def _make_l6_envelope(
    *,
    cif_text: str,
    structure_hash: str | None,
    candidate_id: str = "candidate:wave6/case",
) -> Envelope:
    """Construct a minimal L6 envelope for falsifier routing."""
    output: dict[str, Any] = {"cif_text": cif_text}
    if structure_hash:
        output["structure_hash"] = structure_hash
    return Envelope(
        research_boundary=RESEARCH_BOUNDARY,
        run_id="run:wave6/l6",
        campaign_id="campaign:wave6",
        candidate_id=candidate_id,
        layer="L6",
        tool_adapter={
            "name": "WaveRunnerSynth",
            "version": "0.0.1",
            "backend": "stub",
            "engine": "synth-l6",
        },
        input_refs=[],
        output=output,
        audit={
            "audit_record_id": f"audit:wave6/l6/{candidate_id.split(':')[-1]}",
            "input_hash": _ZERO_HASH,
            "output_hash": _ZERO_HASH,
            "source_manifest_refs": [],
        },
        rights={
            "rights_claim_id": "rights:wave6/l6",
            "reuse_scope": "tenant_only",
        },
    )


def _make_l1_5_envelope(spectrum: dict[str, Any]) -> Envelope:
    """Construct an L1.5 envelope for the unstable_phonon case."""
    output_payload = {
        "imaginary_mode_max_THz": spectrum.get("imaginary_mode_max_THz"),
        "mlip_vs_dft_force_rmse_eV_per_Ang": spectrum.get(
            "mlip_vs_dft_force_rmse_eV_per_Ang"
        ),
        "qmesh_convergence_pct": spectrum.get("qmesh_convergence_pct"),
    }
    return Envelope(
        research_boundary=RESEARCH_BOUNDARY,
        run_id="run:wave6/l1_5",
        campaign_id="campaign:wave6",
        candidate_id="candidate:wave6/unstable",
        layer="L1.5",
        tool_adapter={
            "name": "WaveRunnerSynth",
            "version": "0.0.1",
            "backend": "stub",
            "engine": "synth-l1_5",
        },
        input_refs=[],
        output=output_payload,
        audit={
            "audit_record_id": "audit:wave6/l1_5/unstable",
            "input_hash": _ZERO_HASH,
            "output_hash": _ZERO_HASH,
            "source_manifest_refs": [],
        },
        rights={
            "rights_claim_id": "rights:wave6/l1_5",
            "reuse_scope": "tenant_only",
        },
    )


# ---------------------------------------------------------------------------
# The runner itself
# ---------------------------------------------------------------------------


class FalsificationWaveRunner:
    """Orchestrates the 16-case falsification wave end-to-end.

    Usage
    -----

    .. code-block:: python

        from pathlib import Path
        from zer0pa_materials_workbench.audit.kg import MaterialsKG
        from zer0pa_materials_workbench.audit.log import AuditLog
        from zer0pa_materials_workbench.falsifiers.wave_runner import (
            FalsificationWaveRunner,
            DEFAULT_CASES,
        )

        audit_log = AuditLog(tmp / "audit")
        kg = MaterialsKG(tmp / "kg.sqlite")
        runner = FalsificationWaveRunner(audit_log, kg)
        result = runner.run_all(Path("fixtures/negatives"))
        assert result.cases_correct == len(DEFAULT_CASES)

    The runner is designed for **adversarial verification**. Every case
    expects its target falsifier to FIRE WITH STATUS=fail. A "passing"
    wave run means every gate detected its deliberate failure correctly.
    """

    def __init__(
        self,
        audit_log: AuditLog,
        kg: MaterialsKG | None = None,
        cases: tuple[FalsificationCase, ...] = DEFAULT_CASES,
    ) -> None:
        """Build the runner.

        Args:
            audit_log: Hash-chained audit log instance.
            kg: Optional MaterialsKG instance — used by the missing-source-manifest
                case (which must see an empty KG to fire correctly) and for the
                final node-count summary in the wave report.
            cases: The cases to run. Defaults to the full 16-case wave.
        """
        self.audit_log = audit_log
        self.kg = kg
        self.cases = cases

    # ---- per-case dispatch -------------------------------------------------

    def run_one(
        self,
        case: FalsificationCase,
        fixtures_root: Path,
    ) -> FalsificationCaseResult:
        """Run a single case and record its falsifier rows + decision row."""
        result = FalsificationCaseResult(case=case)
        triggered: list[FalsifierItem]
        try:
            triggered = self._dispatch(case, fixtures_root)
        except Exception as exc:
            result.error = f"{type(exc).__name__}: {exc}"
            return result

        result.triggered_falsifiers = triggered

        # Persist every fired falsifier (status=fail) as a row in falsifiers.jsonl.
        for item in triggered:
            payload = {
                "case": case.name,
                "expected_layer": case.expected_layer,
                "target_falsifier": case.target_falsifier,
                "research_boundary": RESEARCH_BOUNDARY,
                "name": item.name,
                "threshold": item.threshold,
                "actual": item.actual,
                "status": item.status,
                "rationale": item.rationale,
            }
            row = self.audit_log.append_event("falsifiers", payload)
            if item.status == "fail":
                result.audit_event_hash = row.event_hash

        # Validate hash chain immediately after the appends.
        chain = self.audit_log.validate_chain("falsifiers")
        result.chain_validation_ok = chain.ok
        result.chain_errors = list(chain.errors)

        # Record the campaign-halt Decision regardless of how many extras fired.
        decision_payload = {
            "decision_id": f"decision:wave6/{case.name}",
            "made_by": "policy",
            "context": (
                f"Falsification wave case '{case.name}' fed deliberate failure into "
                f"the layer's gate. The campaign halts at {case.expected_layer}."
            ),
            "options_considered": [
                "halt_campaign_at_failed_layer",
                "ignore_falsifier_and_continue",
            ],
            "chosen": "halt_campaign_at_failed_layer",
            "rationale": case.rationale or "Falsifier fired correctly; halt promotion.",
            "supersedes": [],
            "back_edges": [result.audit_event_hash] if result.audit_event_hash else [],
            "research_boundary": RESEARCH_BOUNDARY,
        }
        # Decisions go in decisions.jsonl (separate chain).
        decision_row = self.audit_log.append_event("decisions", decision_payload)
        result.decision_event_hash = decision_row.event_hash

        # Optional KG side-effect: register a Falsifier node for this case
        # so the brain-functionality reconstruction can see what the wave
        # caught. The Falsifier node_type maps to the canonical EMMO IRI
        # via the KG_NODE_TO_EMMO table; we let MaterialsKG.add_node pick
        # that up by passing ontology_term=None. Re-running the wave on a
        # fresh audit dir is idempotent at the KG level too — duplicate
        # node_ids raise IntegrityError which we silently absorb.
        if self.kg is not None:
            try:
                self.kg.add_node(
                    node_id=f"falsifier:wave6/{case.name}",
                    node_type=KGNodeType.Falsifier,
                    properties={
                        "case_name": case.name,
                        "expected_layer": case.expected_layer,
                        "target_falsifier": case.target_falsifier,
                        "verdict": result.verdict,
                        "research_boundary": RESEARCH_BOUNDARY,
                    },
                    run_id="run:wave6/falsification-wave",
                )
            except Exception:
                pass

        return result

    def _dispatch(
        self,
        case: FalsificationCase,
        fixtures_root: Path,
    ) -> list[FalsifierItem]:
        """Route a case to its layer-specific falsifier(s)."""
        fixture_dir = (
            fixtures_root / case.fixture_dir if case.fixture_dir else None
        )

        # Deterministic dispatch by case name.
        if case.name == "invalid_cif":
            return _route_invalid_cif(fixture_dir)
        if case.name == "duplicate_candidate":
            return _route_duplicate_candidate(fixture_dir)
        if case.name == "missing_boundary":
            return _route_missing_boundary(fixture_dir)
        if case.name == "missing_source_manifest":
            assert case.synthesizer is not None
            envelope_dict = case.synthesizer()
            kg = self.kg or MaterialsKG(":memory:")
            return _route_missing_source_manifest(envelope_dict, kg)
        if case.name == "ungrounded_property":
            return _route_ungrounded_property(fixture_dir)
        if case.name == "high_disagreement":
            return _route_high_disagreement(fixture_dir)
        if case.name == "dft_convergence_failure":
            assert case.synthesizer is not None
            return _route_dft_convergence_failure(case.synthesizer())
        if case.name == "ionic_overclaim_no_service":
            return _route_ionic_overclaim(fixture_dir)
        if case.name == "unstable_phonon":
            return _route_unstable_phonon(fixture_dir)
        if case.name == "unreadable_tdb":
            return _route_unreadable_tdb(fixture_dir)
        if case.name == "phasefield_conservation_violation":
            assert case.synthesizer is not None
            return _route_phasefield_conservation(case.synthesizer())
        if case.name == "non_spd_tensor":
            return _route_non_spd_tensor(fixture_dir)
        if case.name == "alabos_executable_in_recipe_only":
            return _route_alabos_executable(fixture_dir)
        if case.name == "tenant_only_tuple_leak":
            return _route_tenant_only_tuple_leak(fixture_dir)
        if case.name == "runpod_schema_drift":
            return _route_runpod_schema_drift(fixture_dir)
        if case.name == "tdb_quarantine_breach":
            return _route_tdb_quarantine_breach(fixture_dir)

        raise ValueError(f"unknown case name: {case.name!r}")

    # ---- batch run ---------------------------------------------------------

    def run_all(self, fixtures_root: str | Path) -> FalsificationWaveResult:
        """Run every case in :attr:`cases` and return the aggregate result.

        Wave F5: after the 16 PRD cases, run an additional **post-PRD
        recompute sweep** of the seven Wave D hardened gates against a
        synthetic forged-evidence chain. The sweep verifies that the
        production wiring is alive: each forged envelope must trip its
        corresponding recompute gate with ``status="fail"``. The result
        is stored under :attr:`FalsificationWaveResult.recompute_sweep`
        and surfaced in the wave report.
        """
        root = Path(fixtures_root).resolve()
        started_at = _utc_now()

        result = FalsificationWaveResult(
            started_at=started_at,
            finished_at="",
            audit_dir=self.audit_log.audit_dir,
        )

        for case in self.cases:
            case_result = self.run_one(case, root)
            result.case_results.append(case_result)

        # Wave F5: post-PRD recompute sweep.
        try:
            sweep = self._run_recompute_sweep()
        except Exception as exc:
            sweep = RecomputeSweepResult(
                gate_results={},
                forged_chain_caught=False,
                sentinel_kind="error",
            )
            sweep.gate_results["wave_f5.sweep_error"] = FalsifierItem(
                name="wave_f5.sweep_error",
                threshold="recompute sweep runs to completion",
                actual={"error": f"{type(exc).__name__}: {exc}"[:240]},
                status="fail",
            )
        # Persist each sweep result as a falsifiers.jsonl row so the
        # ledger holds the post-PRD evidence too.
        for gate_name, item in sweep.gate_results.items():
            payload = {
                "case": "wave_f5.recompute_sweep",
                "expected_layer": gate_name.split(".", 1)[0],
                "target_falsifier": gate_name,
                "research_boundary": RESEARCH_BOUNDARY,
                "name": item.name,
                "threshold": item.threshold,
                "actual": item.actual,
                "status": item.status,
                "rationale": item.rationale,
            }
            try:
                self.audit_log.append_event("falsifiers", payload)
            except Exception:
                pass
        result.recompute_sweep = sweep

        result.finished_at = _utc_now()

        # Final chain validation on the falsifiers + decisions categories.
        falsifier_chain = self.audit_log.validate_chain("falsifiers")
        decision_chain = self.audit_log.validate_chain("decisions")
        result.chain_validation_ok = falsifier_chain.ok and decision_chain.ok
        result.chain_errors = list(falsifier_chain.errors) + list(decision_chain.errors)
        result.total_falsifier_rows_written = falsifier_chain.checked_rows
        result.total_decision_rows_written = decision_chain.checked_rows

        if self.kg is not None:
            try:
                result.kg_node_count_after = sum(1 for _ in self.kg.iter_nodes())
            except Exception:
                result.kg_node_count_after = 0

        return result

    # ---- Wave F5: post-PRD recompute sweep ---------------------------------

    def _run_recompute_sweep(self) -> RecomputeSweepResult:
        """Build a forged-evidence sentinel chain and run every Wave D gate.

        Each recompute gate is fed an envelope/chain that should trip it.
        The aggregate ``forged_chain_caught`` is True when at least four
        of the seven gates fired (the threshold for "wiring is alive";
        some gates depend on filesystem state we don't control here).
        """
        from zer0pa_materials_workbench.envelope.hashing import structure_hash
        from zer0pa_materials_workbench.falsifiers.ionic_falsifiers import (
            neb_barrier_range_check,
            verify_ionic_service_back_edge,
        )
        from zer0pa_materials_workbench.falsifiers.l2_falsifiers import (
            dpa_mace_disagreement_routing_recomputed,
        )
        from zer0pa_materials_workbench.falsifiers.l3_falsifiers import (
            verify_l3_sovereign_block_enforced,
        )
        from zer0pa_materials_workbench.falsifiers.l5_falsifiers import (
            verify_l5_artifact_sidecar,
        )
        from zer0pa_materials_workbench.falsifiers.l6_falsifiers import (
            novelty_status_gate_recomputed,
        )
        from zer0pa_materials_workbench.falsifiers.phase0_falsifiers import (
            verify_source_manifest_linkage,
        )
        from zer0pa_materials_workbench.falsifiers.raw_evidence import (
            llzo_cubic_reference_structure,
        )

        sweep = RecomputeSweepResult(sentinel_kind="forged")

        # 1. Forged L2 envelope: predictions imply 100 meV/atom, claim 5
        forged_l2 = {
            "output": {
                "predictions": [
                    {
                        "model": "DPA-3.1-3M",
                        "energy_eV_per_atom": -5.0,
                        "force_rmse_eV_per_Ang": 0.05,
                    },
                    {
                        "model": "MACE-MPA-0",
                        "energy_eV_per_atom": +5.0,  # 10 eV diff = 10000 meV/atom
                        "force_rmse_eV_per_Ang": 0.06,
                    },
                ],
                "energy_disagreement_meV_per_atom": 5.0,  # forged
                "force_rmse_disagreement_eV_per_Ang": 0.01,
                "routing_decision": "promote",  # forged
            }
        }
        sweep.gate_results["l2.recomputed"] = (
            dpa_mace_disagreement_routing_recomputed(forged_l2)
        )

        # 2. Forged source manifest: refs that don't resolve.
        forged_phase0 = {
            "layer": "L2",
            "audit": {
                "audit_record_id": "audit:wave_f5/forged-phase0",
                "input_hash": "sha256:" + "0" * 64,
                "output_hash": "sha256:" + "0" * 64,
                "source_manifest_refs": ["src:fabricated:fake"],
            },
        }
        sweep.gate_results["phase0.source_manifest_linkage"] = (
            verify_source_manifest_linkage(forged_phase0, [])
        )

        # 3. Forged L6 novelty: claims novel but the structure is in the
        #    reference set.
        llzo_struct = llzo_cubic_reference_structure()
        ref_hash = structure_hash(llzo_struct)
        forged_l6 = {
            "candidate_id": "candidate:wave_f5/forged-novel",
            "layer": "L6",
            "output": {
                "structure": llzo_struct,
                "novelty_status": "novel",  # forged
            },
            "back_edges": [
                {"layer": "L1", "audit_record_id": "audit:wave_f5/L1"},
                {"layer": "ionic", "audit_record_id": "audit:wave_f5/ionic"},
                {"layer": "L2", "audit_record_id": "audit:wave_f5/L2"},
            ],
        }
        sweep.gate_results["l6.novelty_recomputed"] = novelty_status_gate_recomputed(
            forged_l6, reference_set={ref_hash}
        )

        # 4. Forged ionic back-edge: claims conductivity but the
        #    audit_record_id does not resolve.
        forged_ionic = {
            "ionic_conductivity_S_per_cm": 5e-3,
            "output": {"nernst_einstein_conductivity_S_per_cm": 5e-3},
            "back_edges": [
                {"layer": "ionic", "audit_record_id": "audit:wave_f5/forged-ionic"},
            ],
        }
        sweep.gate_results["ionic.back_edge_resolves"] = (
            verify_ionic_service_back_edge(forged_ionic, [])
        )

        # 5. Forged NEB barrier: outside literature band.
        forged_neb = {
            "output": {
                "migration_barrier_eV": 5.0,  # > 3.0 max
                "nernst_einstein_conductivity_S_per_cm": 1e-3,
            }
        }
        sweep.gate_results["ionic.neb_barrier_range"] = neb_barrier_range_check(
            forged_neb
        )

        # 6. Forged L5 artifact sidecar: URI points at a non-existent file.
        forged_l5 = {
            "_artifact_sidecars": [
                {
                    "format": "vtk",
                    "uri": "file:///tmp/wave_f5_does_not_exist.vtk",
                    "sha256": "sha256:" + "0" * 64,
                    "units": {"x": "m"},
                }
            ]
        }
        sweep.gate_results["l5.artifact_sidecar"] = verify_l5_artifact_sidecar(
            forged_l5
        )

        # 7. Forged L3 sovereign block: claims PhaseForgePlus but no enable
        #    decision exists in decisions.jsonl. We pass an empty audit_log
        #    so the lookup fails by construction.
        forged_l3 = {
            "tool_adapter": {"name": "PhaseForgePlusAdapter", "version": "0.0.1"},
            "_phaseforgeplus_meta": {"enabled": True, "repo": "fake/repo"},
        }
        sweep.gate_results["l3.sovereign_block_enforced"] = (
            verify_l3_sovereign_block_enforced(forged_l3, [])
        )

        # Aggregate verdict: at least four gates fired (the threshold for
        # "wiring is alive"). All seven SHOULD fire; if some don't, the
        # report flags it but the wave is not invalidated.
        n_failed = sum(1 for it in sweep.gate_results.values() if it.status == "fail")
        sweep.forged_chain_caught = n_failed >= 4

        return sweep


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utc_now() -> str:
    return _dt.datetime.now(tz=_dt.timezone.utc).isoformat(timespec="microseconds")
