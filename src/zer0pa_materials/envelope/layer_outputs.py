"""Per-layer output schemas referenced by ``Envelope.output``.

Architectural decision — registry vs discriminated union
--------------------------------------------------------

We use a **registry pattern** rather than a tagged Pydantic discriminated
union. The reasons:

1. The envelope already carries a top-level ``layer`` discriminator. The
   layer field is the ground truth. Adding a redundant discriminator inside
   ``output`` would create two sources of truth and a class of falsifier
   ("layer says L2 but output type is L3") that does not add scientific
   value at A0.

2. Phase 0/L6/L7 emit heterogeneous mixed-shape outputs in early waves
   (e.g., L7 may attach a campaign-level summary AND a per-candidate
   record). A registry lets us keep ``Envelope.output`` as a permissive
   ``dict[str, Any]`` and validate against the right schema by layer at
   the boundary, without forcing every wave to migrate to a closed union.

3. The plug-replaceability invariant (§Plug-replaceability acceptance test)
   demands schema parity across adapters. Validating "the dict passed for
   layer=L2 conforms to L2MlipOutput.model_validate" is exactly the right
   shape of contract test, and the registry exposes it directly.

Each model in this module declares the *minimum* fields the PRD's layer
gates require. Later waves may extend these via subclassing; A0 freezes
the wire-level keys.

Falsifier method
----------------

Every layer-output model implements ``.falsifier_items() -> list[FalsifierItem]``.
The method does not run external checks — it converts the recorded values
into a list of falsifier rows aligned with the per-layer gate thresholds
in PRD §Layer-Specific Falsifiers And Gates. The orchestration layer (L7)
collects these into ``Envelope.falsifier.items`` and routes the candidate
based on the aggregate status.

The thresholds are quoted from the PRD verbatim where possible. Any
divergence is documented in `phases/A0-contracts/NOTES.md`.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from zer0pa_materials.envelope.falsifier import FalsifierItem, FalsifierStatus

__all__ = [
    "LayerOutputBase",
    "Phase0Output",
    "L6GenerativeOutput",
    "L1DftOutput",
    "L1QuantumVqeOutput",
    "IonicTransportOutput",
    "L15PhononOutput",
    "L2MlipOutput",
    "L3CalphadOutput",
    "L4PhaseFieldOutput",
    "L5ContinuumOutput",
    "L7CampaignOutput",
    "LAYER_OUTPUT_REGISTRY",
    "validate_layer_output",
]


# ----------------------------------------------------------------------------
# Common helpers
# ----------------------------------------------------------------------------


def _status_for(actual: float | None, op: str, target: float) -> FalsifierStatus:
    """Return falsifier status from a numeric comparison.

    ``op`` is one of ``"<="``, ``"<"``, ``">="``, ``">"``, ``"=="``.
    ``None`` actual returns ``blocked`` so missing measurements never silently
    pass. Inconclusive is reserved for posterior bands and is not produced
    here.
    """
    if actual is None:
        return "blocked"
    if op == "<=":
        return "pass" if actual <= target else "fail"
    if op == "<":
        return "pass" if actual < target else "fail"
    if op == ">=":
        return "pass" if actual >= target else "fail"
    if op == ">":
        return "pass" if actual > target else "fail"
    if op == "==":
        return "pass" if actual == target else "fail"
    raise ValueError(f"unknown comparison operator: {op}")


class LayerOutputBase(BaseModel):
    """Base class for all layer-output schemas.

    Sealed via ``extra='forbid'`` so an adapter cannot smuggle untyped data
    past the schema. Subclasses MAY relax this if a specific layer needs
    forward-compatible keys (none do at A0).
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    def falsifier_items(self) -> list[FalsifierItem]:
        """Return the falsifier rows derived from this output.

        Default returns an empty list so subclasses can opt in. Subclasses
        SHOULD override; an adapter that returns no falsifier rows is itself
        a falsifier failure handled at the audit layer.
        """
        return []


# ----------------------------------------------------------------------------
# Phase 0 — literature / extraction
# ----------------------------------------------------------------------------


class Phase0PropertyGrounding(BaseModel):
    """Source grounding for an extracted property (PRD §Phase 0 falsifier).

    The PRD requires ``DOI/page/table/figure`` grounding for any numeric
    claim. ``page`` and ``table`` and ``figure`` are individually optional
    so figure-only or table-only citations remain valid; ``doi`` is required.
    """

    model_config = ConfigDict(extra="forbid")

    doi: str = Field(..., min_length=1, description="DOI of the source publication.")
    page: int | None = Field(None, ge=1, description="Page number of the cited claim.")
    table: str | None = Field(None, description="Table identifier (e.g. 'Table 2').")
    figure: str | None = Field(None, description="Figure identifier (e.g. 'Figure 3').")


class Phase0ExtractedProperty(BaseModel):
    model_config = ConfigDict(extra="forbid")

    property_name: str = Field(..., min_length=1)
    value: float = Field(..., description="Numeric value in canonical unit (post-normalisation).")
    unit: str = Field(..., description="Canonical unit string (see envelope.units.CANONICAL_UNITS).")
    grounding: Phase0PropertyGrounding
    contradiction_flag: bool = Field(
        default=False,
        description="True if multiple sources disagree and conditions did not differ.",
    )


class Phase0Output(LayerOutputBase):
    """Output of a Phase 0 extraction adapter."""

    extracted_properties: list[Phase0ExtractedProperty] = Field(default_factory=list)
    units_normalised: bool = Field(
        default=True,
        description="True iff every property in extracted_properties carries a canonical unit.",
    )
    contradictions_blocking: list[str] = Field(
        default_factory=list,
        description="Names of properties whose contradictions are unresolved and BLOCK promotion.",
    )

    def falsifier_items(self) -> list[FalsifierItem]:
        items: list[FalsifierItem] = []
        # Gate: every extracted property must have grounding (already structurally
        # required by the schema). We still emit a falsifier row so the audit
        # layer records that the gate ran.
        ungrounded_count = 0
        for p in self.extracted_properties:
            if not p.grounding.doi:
                ungrounded_count += 1
        items.append(
            FalsifierItem(
                name="phase0.grounding_required",
                threshold="ungrounded_count == 0",
                actual=ungrounded_count,
                status="pass" if ungrounded_count == 0 else "fail",
            )
        )
        items.append(
            FalsifierItem(
                name="phase0.units_normalised",
                threshold="units_normalised == True",
                actual=self.units_normalised,
                status="pass" if self.units_normalised else "fail",
            )
        )
        items.append(
            FalsifierItem(
                name="phase0.contradictions_resolved",
                threshold="contradictions_blocking == []",
                actual=list(self.contradictions_blocking),
                status="pass" if not self.contradictions_blocking else "fail",
            )
        )
        return items


# ----------------------------------------------------------------------------
# L6 — generative discovery
# ----------------------------------------------------------------------------


L6NoveltyStatus = Literal["pending", "novel", "duplicate", "invalid"]
L6DedupSource = Literal["MP", "JARVIS", "Alexandria", "GNoME", "OPTIMADE"]


class L6DedupResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: L6DedupSource
    matched: bool
    matched_id: str | None = Field(
        default=None, description="ID in the source database if matched."
    )


class L6GenerativeOutput(LayerOutputBase):
    """Output of an L6 generative adapter (MatterGen, DiffCSP, CrystaLLM)."""

    candidate_uri: str = Field(..., description="URI to the CIF or extxyz artifact.")
    structure_hash: str = Field(
        ..., pattern=r"^sha256:[0-9a-f]{64}$", description="Deterministic structure hash."
    )
    novelty_status: L6NoveltyStatus = Field(
        ..., description="Outcome of de-duplication and validity gate."
    )
    dedup_results: list[L6DedupResult] = Field(
        default_factory=list,
        description="Per-source de-duplication outcomes (MP, JARVIS, Alexandria, GNoME, OPTIMADE).",
    )
    cif_valid: bool = Field(default=True, description="CIF parsed and basic checks passed.")
    charge_neutral: bool = Field(default=True)
    minimum_distance_ok: bool = Field(default=True)

    def falsifier_items(self) -> list[FalsifierItem]:
        items: list[FalsifierItem] = []
        items.append(
            FalsifierItem(
                name="l6.cif_valid",
                threshold="cif_valid == True",
                actual=self.cif_valid,
                status="pass" if self.cif_valid else "fail",
            )
        )
        items.append(
            FalsifierItem(
                name="l6.charge_neutral",
                threshold="charge_neutral == True",
                actual=self.charge_neutral,
                status="pass" if self.charge_neutral else "fail",
            )
        )
        items.append(
            FalsifierItem(
                name="l6.minimum_distance_ok",
                threshold="minimum_distance_ok == True",
                actual=self.minimum_distance_ok,
                status="pass" if self.minimum_distance_ok else "fail",
            )
        )
        # Duplicate against any source is a fail.
        any_dup = any(r.matched for r in self.dedup_results)
        items.append(
            FalsifierItem(
                name="l6.dedup_unique",
                threshold="no source returned matched=True",
                actual={"matched_in": [r.source for r in self.dedup_results if r.matched]},
                status="fail" if any_dup else "pass",
            )
        )
        # Novelty status must not be 'pending' when promoted.
        items.append(
            FalsifierItem(
                name="l6.novelty_resolved",
                threshold="novelty_status != 'pending'",
                actual=self.novelty_status,
                status="pass" if self.novelty_status != "pending" else "blocked",
            )
        )
        return items


# ----------------------------------------------------------------------------
# L1 — DFT
# ----------------------------------------------------------------------------

L1DftCode = Literal["QE", "CP2K", "ABINIT", "PySCF", "GPU4PySCF"]


class L1DftOutput(LayerOutputBase):
    """Output of an L1 DFT adapter (PRD §L1 gates)."""

    code: L1DftCode
    functional: str = Field(
        ..., description="Functional / theory level, e.g. 'PBE', 'HSE06', 'r2SCAN'."
    )
    total_energy_eV: float = Field(..., description="Total energy in eV.")
    force_rmse_eV_per_Ang: float = Field(
        ..., ge=0.0, description="Force RMSE on the converged geometry."
    )
    kpoint_mesh: list[int] = Field(
        ..., description="K-point mesh, e.g. [4,4,4]; length 3.", min_length=3, max_length=3
    )
    convergence_delta_meV_per_atom: float | None = Field(
        default=None,
        description="Cross-code or cross-functional delta vs reference (meV/atom).",
    )
    publication_grade: bool = Field(
        default=False,
        description="True iff convergence_delta_meV_per_atom <= 5; PRD §L1.",
    )

    def falsifier_items(self) -> list[FalsifierItem]:
        items: list[FalsifierItem] = []
        # Publication candidates require <= 5 meV/atom convergence delta.
        delta = self.convergence_delta_meV_per_atom
        if self.publication_grade:
            items.append(
                FalsifierItem(
                    name="l1.publication_convergence_delta",
                    threshold="<= 5 meV/atom",
                    actual=delta,
                    status=_status_for(delta, "<=", 5.0),
                )
            )
        # Screening: above 50 meV/atom flags.
        if delta is not None:
            items.append(
                FalsifierItem(
                    name="l1.screening_convergence_delta",
                    threshold="< 50 meV/atom",
                    actual=delta,
                    status=_status_for(delta, "<", 50.0),
                )
            )
        return items


# ----------------------------------------------------------------------------
# L1 quantum slot — VQE
# ----------------------------------------------------------------------------


L1VqeOptimizer = Literal["SPSA", "COBYLA", "Adam", "L-BFGS-B", "GradientDescent"]


class L1QuantumVqeOutput(LayerOutputBase):
    """Output of a PennyLane VQE adapter (PRD §L1 quantum gates).

    Falsifier thresholds (PRD §L1):
        H2 vs PySCF FCI within 1e-3 Ha.
        LiH active-space within 5e-3 Ha.
    """

    system: Literal["H2", "LiH", "other"]
    ansatz: str = Field(..., description="Variational ansatz, e.g. 'UCCSD', 'HEA(p=2)'.")
    qubits: int = Field(..., gt=0)
    optimizer: L1VqeOptimizer
    ground_state_energy_Ha: float
    classical_reference_Ha: float = Field(
        ..., description="PySCF FCI (H2) or active-space CASCI (LiH) reference."
    )

    @property
    def absolute_delta_Ha(self) -> float:
        return abs(self.ground_state_energy_Ha - self.classical_reference_Ha)

    def falsifier_items(self) -> list[FalsifierItem]:
        items: list[FalsifierItem] = []
        delta = self.absolute_delta_Ha
        if self.system == "H2":
            items.append(
                FalsifierItem(
                    name="l1.h2_vqe_vs_fci",
                    threshold="<= 1e-3 Ha",
                    actual=delta,
                    status=_status_for(delta, "<=", 1e-3),
                )
            )
        elif self.system == "LiH":
            items.append(
                FalsifierItem(
                    name="l1.lih_vqe_vs_fci",
                    threshold="<= 5e-3 Ha",
                    actual=delta,
                    status=_status_for(delta, "<=", 5e-3),
                )
            )
        return items


# ----------------------------------------------------------------------------
# Ionic transport (battery MVP)
# ----------------------------------------------------------------------------


IonicInterfaceClass = Literal[
    "li_metal_stable",
    "li_metal_unstable_coating_required",
    "cathode_facing_stable",
    "cathode_facing_unstable",
    "unknown",
]


class IonicArrhenius(BaseModel):
    model_config = ConfigDict(extra="forbid")

    activation_energy_eV: float = Field(..., gt=0.0)
    activation_energy_uncertainty_eV: float = Field(..., ge=0.0)


class IonicTransportOutput(LayerOutputBase):
    """Output of the IonicTransportService (PRD §Ionic Transport gates)."""

    migration_barrier_eV: float | None = Field(
        default=None, description="NEB or path-search migration barrier."
    )
    msd_A2: float | None = Field(default=None, description="Mean-square displacement (Å²).")
    diffusion_coefficient_cm2_per_s: float | None = Field(
        default=None, description="MD/AIMD/MLIP-MD diffusion coefficient (cm²/s)."
    )
    nernst_einstein_conductivity_S_per_cm: float | None = Field(
        default=None,
        description="Room-temperature ionic conductivity from Nernst-Einstein (S/cm).",
    )
    arrhenius: IonicArrhenius | None = Field(
        default=None, description="Activation energy with uncertainty."
    )
    electrochemical_window_V_vs_LiLi: tuple[float, float] | None = Field(
        default=None, description="(reduction, oxidation) potentials vs Li/Li+."
    )
    interface_stability: IonicInterfaceClass = Field(default="unknown")
    defect_disorder_assumptions: list[str] = Field(default_factory=list)
    confidence: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Self-reported confidence in [0, 1]."
    )

    def falsifier_items(self) -> list[FalsifierItem]:
        items: list[FalsifierItem] = []
        # Migration barrier: target <= 0.35 eV; stretch <= 0.30 eV.
        items.append(
            FalsifierItem(
                name="ionic.activation_barrier_target",
                threshold="<= 0.35 eV",
                actual=self.migration_barrier_eV,
                status=_status_for(self.migration_barrier_eV, "<=", 0.35),
            )
        )
        items.append(
            FalsifierItem(
                name="ionic.activation_barrier_stretch",
                threshold="<= 0.30 eV",
                actual=self.migration_barrier_eV,
                status=_status_for(self.migration_barrier_eV, "<=", 0.30),
            )
        )
        # RT conductivity credible interval includes or exceeds 1e-3 S/cm.
        items.append(
            FalsifierItem(
                name="ionic.rt_conductivity_target",
                threshold=">= 1e-3 S/cm",
                actual=self.nernst_einstein_conductivity_S_per_cm,
                status=_status_for(self.nernst_einstein_conductivity_S_per_cm, ">=", 1e-3),
            )
        )
        # Oxidative stability >= 4.0 V vs Li/Li+.
        ox_actual: float | None = (
            self.electrochemical_window_V_vs_LiLi[1] if self.electrochemical_window_V_vs_LiLi else None
        )
        items.append(
            FalsifierItem(
                name="ionic.oxidative_stability",
                threshold=">= 4.0 V vs Li/Li+",
                actual=ox_actual,
                status=_status_for(ox_actual, ">=", 4.0),
            )
        )
        return items


# ----------------------------------------------------------------------------
# L1.5 — phonons / transport
# ----------------------------------------------------------------------------


class L15PhononOutput(LayerOutputBase):
    """Output of an L1.5 phonon adapter (Phonopy/Phono3py/HiPhive + ZT sidecar)."""

    imaginary_mode_max_THz: float = Field(
        ..., ge=0.0, description="Largest non-acoustic imaginary mode magnitude (THz)."
    )
    mlip_vs_dft_force_rmse_eV_per_Ang: float | None = Field(
        default=None, ge=0.0, description="MLIP vs DFT force RMSE (eV/Å)."
    )
    qmesh_convergence_pct: float | None = Field(
        default=None,
        ge=0.0,
        description="Phono3py q-mesh convergence as percentage; <10% required for publishable.",
    )
    seebeck_uV_per_K: float | None = Field(
        default=None, description="Seebeck coefficient (μV/K) — TE sidecar."
    )
    electrical_conductivity_S_per_cm: float | None = Field(default=None)
    thermal_conductivity_W_per_mK: float | None = Field(default=None, ge=0.0)
    zt: float | None = Field(default=None, ge=0.0, description="Thermoelectric figure of merit.")

    def falsifier_items(self) -> list[FalsifierItem]:
        items: list[FalsifierItem] = []
        # Non-acoustic imaginary mode > 0.25 THz fails dynamical stability.
        items.append(
            FalsifierItem(
                name="l15.imaginary_mode_threshold",
                threshold="<= 0.25 THz (after acoustic sum rule + NAC review)",
                actual=self.imaginary_mode_max_THz,
                status=_status_for(self.imaginary_mode_max_THz, "<=", 0.25),
            )
        )
        # MLIP vs DFT force RMSE escalates if > 0.05 eV/Å.
        items.append(
            FalsifierItem(
                name="l15.mlip_vs_dft_force_rmse",
                threshold="<= 0.05 eV/Å",
                actual=self.mlip_vs_dft_force_rmse_eV_per_Ang,
                status=_status_for(self.mlip_vs_dft_force_rmse_eV_per_Ang, "<=", 0.05),
            )
        )
        # Phono3py q-mesh convergence < 10%.
        items.append(
            FalsifierItem(
                name="l15.phono3py_qmesh_convergence",
                threshold="< 10%",
                actual=self.qmesh_convergence_pct,
                status=_status_for(self.qmesh_convergence_pct, "<", 10.0),
            )
        )
        return items


# ----------------------------------------------------------------------------
# L2 — MLIP
# ----------------------------------------------------------------------------

L2RoutingDecision = Literal["promote", "queue_dft", "hard_reject"]


class L2ModelPrediction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model: str = Field(..., description="Model identifier, e.g. 'DPA-3.1-3M', 'MACE-MPA-0'.")
    energy_eV_per_atom: float
    force_rmse_eV_per_Ang: float = Field(..., ge=0.0)


class L2MlipOutput(LayerOutputBase):
    """Output of the L2 ensemble (DPA-3 + MACE; PRD §L2 thresholds)."""

    predictions: list[L2ModelPrediction] = Field(..., min_length=1)
    energy_disagreement_meV_per_atom: float = Field(..., ge=0.0)
    force_rmse_disagreement_eV_per_Ang: float = Field(..., ge=0.0)
    routing_decision: L2RoutingDecision

    @field_validator("predictions")
    @classmethod
    def _ensure_dual_model(cls, v: list[L2ModelPrediction]) -> list[L2ModelPrediction]:
        # PRD §L2 mandates DPA-3 + MACE ensemble. We do not enforce specific
        # model names here (a stub may register placeholders) — only that the
        # ensemble has at least 2 distinct entries when there are 2+ models.
        names = {p.model for p in v}
        if len(v) >= 2 and len(names) < 2:
            raise ValueError(
                "L2 ensemble requires distinct model identifiers when >=2 predictions present."
            )
        return v

    def falsifier_items(self) -> list[FalsifierItem]:
        items: list[FalsifierItem] = []
        # queue DFT if energy disagreement > 25 meV/atom.
        items.append(
            FalsifierItem(
                name="l2.energy_disagreement_promote",
                threshold="<= 25 meV/atom",
                actual=self.energy_disagreement_meV_per_atom,
                status=_status_for(self.energy_disagreement_meV_per_atom, "<=", 25.0),
            )
        )
        # queue DFT if force RMSE > 0.15 eV/Å.
        items.append(
            FalsifierItem(
                name="l2.force_rmse_promote",
                threshold="<= 0.15 eV/Å",
                actual=self.force_rmse_disagreement_eV_per_Ang,
                status=_status_for(self.force_rmse_disagreement_eV_per_Ang, "<=", 0.15),
            )
        )
        # hard reject if energy disagreement > 75 meV/atom.
        items.append(
            FalsifierItem(
                name="l2.energy_disagreement_hard_reject",
                threshold="<= 75 meV/atom",
                actual=self.energy_disagreement_meV_per_atom,
                status=_status_for(self.energy_disagreement_meV_per_atom, "<=", 75.0),
            )
        )
        # hard reject if force RMSE > 0.35 eV/Å.
        items.append(
            FalsifierItem(
                name="l2.force_rmse_hard_reject",
                threshold="<= 0.35 eV/Å",
                actual=self.force_rmse_disagreement_eV_per_Ang,
                status=_status_for(self.force_rmse_disagreement_eV_per_Ang, "<=", 0.35),
            )
        )
        return items


# ----------------------------------------------------------------------------
# L3 — CALPHAD
# ----------------------------------------------------------------------------


class L3CalphadOutput(LayerOutputBase):
    """Output of an L3 CALPHAD adapter (PRD §L3 gates)."""

    tdb_ref: str = Field(..., description="URI/URN of the TDB used (read-only if commercial).")
    equilibrium_phases: list[str] = Field(default_factory=list)
    phase_fraction_posterior: dict[str, float] = Field(
        default_factory=dict, description="Phase -> mean fraction in [0, 1]."
    )
    espei_diagnostics: dict[str, Any] = Field(
        default_factory=dict,
        description="MCMC diagnostics: r_hat, ess, n_chains, n_samples, accept_rate, ...",
    )
    fixture_phase_boundary_drift_K: float | None = Field(
        default=None, description="Drift vs fixture (K)."
    )
    phase_set_jaccard_distance: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Jaccard distance to reference phase set."
    )
    phase_fraction_js_divergence: float | None = Field(
        default=None, ge=0.0, description="JS divergence vs reference distribution."
    )

    def falsifier_items(self) -> list[FalsifierItem]:
        items: list[FalsifierItem] = []
        items.append(
            FalsifierItem(
                name="l3.fixture_boundary_drift",
                threshold="<= 25 K",
                actual=self.fixture_phase_boundary_drift_K,
                status=_status_for(self.fixture_phase_boundary_drift_K, "<=", 25.0),
            )
        )
        items.append(
            FalsifierItem(
                name="l3.phase_set_jaccard",
                threshold="<= 0.33",
                actual=self.phase_set_jaccard_distance,
                status=_status_for(self.phase_set_jaccard_distance, "<=", 0.33),
            )
        )
        items.append(
            FalsifierItem(
                name="l3.phase_fraction_js_divergence",
                threshold="<= 0.15",
                actual=self.phase_fraction_js_divergence,
                status=_status_for(self.phase_fraction_js_divergence, "<=", 0.15),
            )
        )
        # ESPEI posterior diagnostics must be recorded.
        items.append(
            FalsifierItem(
                name="l3.espei_diagnostics_recorded",
                threshold="non-empty",
                actual={"keys": sorted(self.espei_diagnostics.keys())},
                status="pass" if self.espei_diagnostics else "blocked",
            )
        )
        return items


# ----------------------------------------------------------------------------
# L4 — phase field / kMC
# ----------------------------------------------------------------------------


class L4PhaseFieldOutput(LayerOutputBase):
    """Output of an L4 phase-field/kMC adapter (PRD §L4 gates)."""

    cahn_hilliard_mass_drift: float | None = Field(default=None, ge=0.0)
    allen_cahn_bounds_violation: float | None = Field(default=None, ge=0.0)
    spparks_potts_energy_monotonic: bool | None = Field(
        default=None, description="True iff energy non-increasing across dumps at T=0."
    )
    microstructure_trajectory_uri: str | None = Field(
        default=None, description="Artifact URI for the microstructure trajectory."
    )

    def falsifier_items(self) -> list[FalsifierItem]:
        items: list[FalsifierItem] = []
        items.append(
            FalsifierItem(
                name="l4.cahn_hilliard_mass_drift",
                threshold="< 1e-3",
                actual=self.cahn_hilliard_mass_drift,
                status=_status_for(self.cahn_hilliard_mass_drift, "<", 1e-3),
            )
        )
        items.append(
            FalsifierItem(
                name="l4.allen_cahn_bounds_violation",
                threshold="< 1e-4",
                actual=self.allen_cahn_bounds_violation,
                status=_status_for(self.allen_cahn_bounds_violation, "<", 1e-4),
            )
        )
        items.append(
            FalsifierItem(
                name="l4.spparks_potts_energy_monotonic",
                threshold="energy_non_increasing == True",
                actual=self.spparks_potts_energy_monotonic,
                status="pass" if self.spparks_potts_energy_monotonic else (
                    "blocked" if self.spparks_potts_energy_monotonic is None else "fail"
                ),
            )
        )
        return items


# ----------------------------------------------------------------------------
# L5 — continuum
# ----------------------------------------------------------------------------


class L5TensorRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., description="Tensor identifier (e.g. 'stiffness', 'conductivity').")
    spd: bool = Field(..., description="True iff the tensor is symmetric positive-definite.")
    eigvals_min: float | None = Field(default=None, description="Minimum eigenvalue.")


class L5ContinuumOutput(LayerOutputBase):
    """Output of an L5 continuum adapter (PRD §L5 gates)."""

    tensors: list[L5TensorRecord] = Field(default_factory=list)
    analytic_heat_slab_error: float | None = Field(default=None, ge=0.0)
    elastic_patch_residual: float | None = Field(default=None, ge=0.0)
    fenicsx_vs_dealii_strain_energy_disagreement_pct: float | None = Field(
        default=None, ge=0.0
    )
    openfoam_poiseuille_error_pct: float | None = Field(default=None, ge=0.0)
    cfd_mass_balance_error: float | None = Field(default=None, ge=0.0)
    cfd_heat_balance_error: float | None = Field(default=None, ge=0.0)
    artifact_uris: list[str] = Field(
        default_factory=list,
        description="VTK/Exodus/FMI artifacts (must include unit sidecars + hashes elsewhere).",
    )

    def falsifier_items(self) -> list[FalsifierItem]:
        items: list[FalsifierItem] = []
        # SPD tensors — fail if any tensor is not SPD.
        non_spd = [t.name for t in self.tensors if not t.spd]
        items.append(
            FalsifierItem(
                name="l5.tensors_spd",
                threshold="all tensors SPD",
                actual={"non_spd": non_spd},
                status="pass" if not non_spd else "fail",
            )
        )
        items.append(
            FalsifierItem(
                name="l5.analytic_heat_slab_error",
                threshold="< 1e-6",
                actual=self.analytic_heat_slab_error,
                status=_status_for(self.analytic_heat_slab_error, "<", 1e-6),
            )
        )
        items.append(
            FalsifierItem(
                name="l5.elastic_patch_residual",
                threshold="< 1e-8",
                actual=self.elastic_patch_residual,
                status=_status_for(self.elastic_patch_residual, "<", 1e-8),
            )
        )
        items.append(
            FalsifierItem(
                name="l5.fenicsx_vs_dealii",
                threshold="< 2%",
                actual=self.fenicsx_vs_dealii_strain_energy_disagreement_pct,
                status=_status_for(
                    self.fenicsx_vs_dealii_strain_energy_disagreement_pct, "<", 2.0
                ),
            )
        )
        items.append(
            FalsifierItem(
                name="l5.openfoam_poiseuille_error",
                threshold="< 5%",
                actual=self.openfoam_poiseuille_error_pct,
                status=_status_for(self.openfoam_poiseuille_error_pct, "<", 5.0),
            )
        )
        items.append(
            FalsifierItem(
                name="l5.cfd_mass_balance",
                threshold="< 1e-4",
                actual=self.cfd_mass_balance_error,
                status=_status_for(self.cfd_mass_balance_error, "<", 1e-4),
            )
        )
        items.append(
            FalsifierItem(
                name="l5.cfd_heat_balance",
                threshold="< 1e-4",
                actual=self.cfd_heat_balance_error,
                status=_status_for(self.cfd_heat_balance_error, "<", 1e-4),
            )
        )
        return items


# ----------------------------------------------------------------------------
# L7 — campaigns / orchestration
# ----------------------------------------------------------------------------


L7Acquisition = Literal[
    "qMultiFidelityKnowledgeGradient",
    "qLogExpectedImprovement",
    "other",
]
L7PromotionDecision = Literal["promote", "queue_higher_fidelity", "reject", "hold"]


class L7CampaignOutput(LayerOutputBase):
    """Output of an L7 campaign step (PRD §L7 gates)."""

    candidate_id: str = Field(..., pattern=r"^candidate:.+$")
    acquisition: L7Acquisition
    promotion_decision: L7PromotionDecision
    audit_provenance_ref: str = Field(..., description="URN of audit event chain entry.")
    gate_verdict: Literal["pass", "fail", "blocked", "inconclusive"]

    def falsifier_items(self) -> list[FalsifierItem]:
        items: list[FalsifierItem] = []
        # Acquisition cannot be plain qExpectedImprovement (PRD: do not use as default).
        items.append(
            FalsifierItem(
                name="l7.acquisition_default",
                threshold="acquisition in {qMultiFidelityKnowledgeGradient, qLogExpectedImprovement, other}",
                actual=self.acquisition,
                status="pass",  # already restricted by Literal; recorded for audit.
            )
        )
        items.append(
            FalsifierItem(
                name="l7.audit_provenance_attached",
                threshold="audit_provenance_ref non-empty",
                actual=bool(self.audit_provenance_ref),
                status="pass" if self.audit_provenance_ref else "fail",
            )
        )
        items.append(
            FalsifierItem(
                name="l7.gate_verdict",
                threshold="recorded",
                actual=self.gate_verdict,
                status=self.gate_verdict if self.gate_verdict in {"pass", "fail", "blocked", "inconclusive"} else "blocked",
            )
        )
        return items


# ----------------------------------------------------------------------------
# Registry
# ----------------------------------------------------------------------------


# Layer names match the Envelope.layer literal exactly. The "quantum" slot is
# the future variational-solver lane defined in PRD §Architecture Invariant
# (the envelope literal lists ``L1.5`` and ``ionic`` but not ``quantum``
# directly — quantum outputs ride under ``layer="L1"`` with this output
# schema parameterising the body. We expose both ``L1`` and ``quantum`` keys
# in the registry so adapters that emit specifically VQE results can
# self-describe; the orchestrator MUST set ``layer="L1"`` on the envelope.).
LAYER_OUTPUT_REGISTRY: dict[str, type[LayerOutputBase]] = {
    "phase0": Phase0Output,
    "L1": L1DftOutput,
    "L1.5": L15PhononOutput,
    "ionic": IonicTransportOutput,
    "quantum": L1QuantumVqeOutput,
    "L2": L2MlipOutput,
    "L3": L3CalphadOutput,
    "L4": L4PhaseFieldOutput,
    "L5": L5ContinuumOutput,
    "L6": L6GenerativeOutput,
    "L7": L7CampaignOutput,
}


def validate_layer_output(layer: str, output: dict[str, Any]) -> LayerOutputBase:
    """Validate ``output`` against the schema registered for ``layer``.

    The orchestration layer calls this at the moment an envelope is built;
    a validation failure means the adapter emitted a payload that does not
    conform to the layer contract and the candidate is rejected before
    promotion.
    """
    if layer not in LAYER_OUTPUT_REGISTRY:
        raise KeyError(f"unknown layer: {layer!r}; valid: {sorted(LAYER_OUTPUT_REGISTRY)}")
    schema = LAYER_OUTPUT_REGISTRY[layer]
    return schema.model_validate(output)
