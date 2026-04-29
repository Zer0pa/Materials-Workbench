# Zer0pa Materials Overnight Execution PRD

## Boundary

Research infrastructure for in silico materials science discovery. Outputs are research artifacts. No regulatory certification claims. No clinical or human-subject use. ITAR / weapons applications are out of scope (Meta UMA Acceptable Use Policy and operator policy).

Every artifact produced by the overnight executor must carry the boundary block above verbatim.

## Operating Mandate

This PRD is written for a long-horizon overnight execution by an Opus Max-class lead agent with Sonnet-level subagents at minimum and Opus-level subagents where high-context scientific judgment, cross-layer architecture, falsification strategy, ontology/audit semantics, or hard engineering arbitration is required.

The lead agent is the chief engineer and chief scientific integrator. It is not a task narrator. It has an executive mandate to make reversible engineering decisions that move the system toward more performant, more dataful, more powerful, and more falsifiable outcomes. It should keep its own context free for cognitive intersectional scientific thinking, problem solving, and on-the-fly innovation while delegating bounded implementation to subagents.

Upon receipt of the startup prompt, the overnight executor proceeds immediately. It does not ask the user what to do next. It reads the repo, restores context, plans, spawns subagents, implements, tests, runs a falsification wave, commits, pushes, and reports only when the full CPU-side pipeline and falsification wave have run, or when a hard blocker prevents further progress.

Only work that actually requires GPU hardware, unavailable credentials, or unavailable physical lab hardware is parked. Parked work must still have schemas, adapters, stubs, fixtures, audit records, falsifiers, source manifests, and Runpod cutover gates. CPU-side architecture, contracts, tests, audit, KG, fixtures, orchestration, and stubs are not parkable.

The governing objective is the authority metric: an end-to-end, CPU-complete, audit-trailed, falsifiable materials discovery pipeline whose GPU layers can be swapped in on Runpod by config flag only. A narratable local win is not success if the authority metric regresses.

## Source Basis

The overnight executor must read the repository in the order specified in `HANDOFF-TO-OVERNIGHT-EXECUTOR.md`. The external folder on the originating machine, `/Users/Zer0pa/Materials Portfolio/Materials Pipeline Research`, contains the same two large research briefs committed under `source-briefs/`:

- `source-briefs/01-full-technology-landscape.md`
- `source-briefs/02-corrections-and-architecture.md`

The GitHub repository is canonical: `https://github.com/Zer0pa/Materials`.

## Scope

Build research infrastructure for in silico materials science discovery. The first commercial wedge is solid-state battery electrolytes / Li-ion conductors. The thermoelectric stack is a sidecar validation lane because its ZT calculation path is cleaner and fully open end to end.

The first deliverable is not a toy demo. It is a campaign-grade evidence packet and reproducibility package targeting a publishable paper:

> Audit-trailed multi-fidelity discovery of quaternary halide solid electrolytes with calibrated DFT/MLIP/CALPHAD disagreement.

The first seed evidence packet uses:

| Role | Material | Purpose |
|---|---|---|
| Known-good control | `Li7La3Zr2O12` / LLZO | Recover literature behavior while distinguishing cubic high-conductivity LLZO from tetragonal low-conductivity behavior. |
| Known-borderline control | `Li6PS5Cl` | Recover high-conductivity potential while flagging disorder, moisture sensitivity, interface, and Li-metal compatibility risk. |
| Novel challenge seed | `Li2.2Mg0.1Zr0.9Cl6` in the Li-Mg-Zr-Cl halide design family | Treat as a pre-registered generated challenge candidate, not as a novelty claim, until de-duplication passes. If exact novelty fails, keep the family and let L6/L7 reselect. |

If the first GPU campaign cannot produce a defensible battery novel candidate after de-duplication and validation, the first publishable paper may pivot to the thermoelectric sidecar. The commercial wedge remains batteries unless the user explicitly changes it.

## Architecture Invariant

The orchestrator-facing architecture remains seven physical layers plus Phase 0. The buyer-facing abstraction is three functional layers:

1. Knowledge / Hypothesis Layer: Phase 0 literature mining, databases, ontology, KG, and candidate priors.
2. Variational Solver Layer: DFT, quantum slot, ionic transport, phonons, MLIP, CALPHAD, phase field, FEM/CFD, and generative solvers exposed through stable contracts.
3. Active-Inference Loop Layer: BoTorch/Ax acquisition, LangGraph reasoning, Prefect campaign runs, Parsl fan-out, AiiDA/atomate2 provenance, and Phase 2 AlabOS closure.

Every layer is tool-agnostic and contract-first. Downstream components depend on versioned interfaces, not on Quantum ESPRESSO, PySCF, PennyLane, DPA-3, MACE, pycalphad, PRISMS-PF, MatterGen, LangGraph, or any other implementation detail.

The universal envelope is mandatory:

```json
{
  "contract_version": "zer0pa.materials.layer-envelope.v1",
  "research_boundary": "Research infrastructure for in silico materials science discovery. Outputs are research artifacts. No regulatory certification claims. No clinical or human-subject use. ITAR / weapons applications are out of scope (Meta UMA Acceptable Use Policy and operator policy).",
  "run_id": "run:...",
  "campaign_id": "campaign:...",
  "candidate_id": "candidate:...",
  "layer": "phase0|L1|L1.5|ionic|L2|L3|L4|L5|L6|L7",
  "tool_adapter": {
    "name": "adapter name",
    "version": "adapter version",
    "backend": "stub|local_cpu|runpod_mock|runpod_rest",
    "engine": "tool or model name"
  },
  "input_refs": [],
  "output": {},
  "confidence": {
    "score": 0.0,
    "band": "low|medium|high",
    "basis": []
  },
  "disagreement": {
    "metrics": []
  },
  "falsifier": {
    "status": "pass|fail|blocked|inconclusive",
    "items": []
  },
  "audit": {
    "audit_record_id": "audit:...",
    "input_hash": "sha256:...",
    "output_hash": "sha256:...",
    "source_manifest_refs": []
  },
  "rights": {
    "rights_claim_id": "rights:...",
    "reuse_scope": "tenant_only|shared_learning|open_science"
  },
  "back_edges": []
}
```

Plug-replaceability acceptance test:

1. Pick one layer adapter and a golden seed request.
2. Replace its implementation with a second adapter or `runpod_mock` behind the same contract.
3. Run the same request through downstream orchestration.
4. Pass only if downstream code is unchanged, schemas validate, audit provenance records the adapter difference, disagreement/falsifier state is preserved, and scientific changes appear as output/confidence/falsifier deltas rather than interface breakage.

The "<1 day swap" invariant is measured through these plug-swap tests. Documentation alone is not evidence.

## Layer Contracts

| Layer | Purpose | Primary adapters | CPU-first output | Parked until Runpod |
|---|---|---|---|---|
| Phase 0 | Literature, databases, hypothesis KG | `OptimadeFederatedQueryAdapter`, `LangGraphExtractionWorkflow`, `RobocrystallographerStructureNarrator`, gated `MaterialsBertNerAdapter` | EMMO-aligned records, source manifests, small fixtures | Bulk corpus extraction and paid API scale-out |
| L6 | Generative discovery | `MatterGenGeneratorAdapter`, `DiffCspGeneratorAdapter`, `CrystaLlmCifGeneratorAdapter`, `LeMatGenBenchEvaluatorAdapter` | Candidate schemas, CIF/extxyz stubs, novelty filters | GPU generation and large novelty benchmark batches |
| L1 | Electronic structure | `QuantumEspressoAiiDASolver`, `PyScfMolecularSolver`, `Cp2kAiiDASolver`, `AbinitAiiDASolver` | dry-run adapters, parsers, extxyz contracts, H2/LiH fixtures | real QE/CP2K/GPU4PySCF workloads |
| Quantum slot | Future variational solver | `PennyLaneVqeSolver`, optional `QiskitNatureVqeSolver` | PySCF-backed H2/LiH VQE falsifiers | hardware quantum execution |
| Ionic | Battery-specific ion transport | `NebMigrationBarrierAdapter`, `MlipMdDiffusionAdapter`, `AimdDiffusionAdapter`, `ElectrochemicalWindowAdapter`, `InterfaceStabilityAdapter` | schemas, NEB/MD stubs, MSD/Nernst-Einstein calculators, fixtures | real NEB/AIMD/MLIP-MD production runs |
| L1.5 | Phonons and electronic/thermal transport | `PhonopyHarmonicAdapter`, `Phono3pyAnharmonicBTEAdapter`, `HiPhiveForceConstantFitAdapter`, `BoltzTraP2RigidBandTransportAdapter`, `AmsetScatteringTransportAdapter` | mock force/band providers, ZT assembly, phonon tests | DFT/MLIP displacement force batches |
| L2 | MLIP/MD | `DeepmdDpaCalculatorAdapter`, `MaceMpCalculatorAdapter`, `UmaCalculatorAdapter`, `MaceMultiheadCommitteeRunner`, `DpaCommitteeRunner` | ASE surface, DPA/MACE stubs, disagreement routing, license gates | real weights, GPU inference, fine-tuning |
| L3 | CALPHAD | `PyCalphadEquilibriumAdapter`, `EspeiBayesianFitAdapter`, `PhaseForgePlusMlipPriorAdapter`, `ThermoCalcTdbReadOnlyAdapter` | open TDB fixtures, ESPEI dry-run, TDB quarantine | heavy quaternary fitting |
| L4 | Phase field and kMC | `PrismsPfAdapter`, `MoosePhaseFieldAdapter`, `MicrosimGrandPotentialAdapter`, `SpparksKmcAdapter`, `NeuralOperatorPhaseFieldAdapter` | native input emitters, parsers, toy invariant fixtures | production solver runs, neural-operator training |
| L5 | Continuum/process | `FEniCSxContinuumAdapter`, `DealIIStructuralAdapter`, `OpenFOAMProcessAdapter`, `ContinuumHandoffCodec` | homogenization, VTK/Exodus/FMI codecs, analytic fixtures | large meshes, production OpenFOAM/deal.II runs |
| L7 | Orchestration and active learning | `AiiDAProvenanceAdapter`, `Atomate2WorkflowAdapter`, `PrefectCampaignAdapter`, `ParslFanoutAdapter`, `LangGraphReasonerAdapter`, `BoTorchAcquisitionAdapter`, `AlabOSProtocolCompilerStub` | local campaign with stubs, BoTorch loop, audit/KG persistence | high-throughput queues and hardware lab closure |

## Layer-Specific Falsifiers And Gates

### Phase 0 / L6

- Reject numeric claims without DOI/page/table/figure grounding.
- Normalize units before promotion.
- Block unresolved contradictions unless conditions differ.
- Generated candidates must pass valid CIF parsing, charge-neutrality checks, minimum interatomic distance checks, structure hash de-duplication, `pymatgen.StructureMatcher`, and reference expansion against Materials Project, JARVIS, Alexandria, GNoME, and OPTIMADE.
- MatterGen/DiffCSP/CrystaLLM output is only a proposal queue. No "novel material" wording until de-duplication, L2 screening, and L1 validation pass.

### L1

- H2 PennyLane VQE must match PySCF FCI within `1e-3 Ha`.
- LiH active-space VQE must match PySCF reference within `5e-3 Ha`.
- Final promoted structures must log DFT code or functional/convergence deltas.
- Publication candidates require tightened convergence delta `<= 5 meV/atom`.
- Screening candidates flag above `50 meV/atom` cross-code or functional delta.

### Ionic Transport

Battery MVP claims require an explicit `IonicTransportService`; phonons do not substitute for Li-ion conductivity.

Required quantities:

- migration barrier in eV from NEB or equivalent path search
- mean squared displacement, diffusion coefficient, and Nernst-Einstein conductivity from MD/AIMD/MLIP-MD
- Arrhenius activation energy and uncertainty
- electrochemical stability window versus Li/Li+
- interface stability classification for Li metal and cathode-facing use
- defect/disorder assumptions and confidence

Battery promotion thresholds:

- room-temperature ionic conductivity credible interval includes or exceeds `1e-3 S/cm`
- activation barrier target `<= 0.35 eV`, stretch `<= 0.30 eV`
- oxidative stability target `>= 4.0 V vs Li/Li+`
- Li-metal reduction instability is allowed only if explicitly routed to coating/interlayer mode

### L1.5

- Non-acoustic imaginary mode magnitude `> 0.25 THz` after acoustic sum rule and NAC review fails dynamical stability.
- MLIP vs DFT displacement force RMSE `> 0.05 eV/A` escalates to DFT.
- Phonopy vs HiPhive frequency RMSE `> 0.20 THz` or lattice thermal conductivity delta `> 20%` flags.
- Phono3py q-mesh convergence must be `< 10%` for a publishable transport candidate.
- Thermoelectric ZT candidate rank must be stable across transport assumptions.

### L2

Decision: DPA-3 + MACE ensemble by construction.

- Run DPA-3.1-3M and MACE-MPA-0 on every L2 candidate.
- DPA-3 may be the ranking model under compute constraint, but no candidate is promoted on DPA-3 alone.
- UMA is optional third-model evidence behind verified HF organization registration and AUP acceptance.

Routing thresholds:

- queue DFT if DPA/MACE energy disagreement `> 25 meV/atom`
- queue DFT if force RMSE `> 0.15 eV/A`
- queue DFT if relaxation endpoints differ by `> 0.08 A/atom`, `> 2%` volume, or different space group
- hard reject pending DFT if energy disagreement `> 75 meV/atom` or force RMSE `> 0.35 eV/A`

License correction: DPA-3.1-3M model metadata indicates CC-BY-4.0 weights; DeePMD-kit is LGPL-3.0. Do not copy inherited "MIT" labels without verification. MACE checkpoint licenses must be pinned by checkpoint. UMA library and weights licenses are separate.

### L3

Decision: sovereign pycalphad/ESPEI build by default.

- Commercial Thermo-Calc TDBs are allowed only as quarantined read-only inputs for customer projects with valid license coverage.
- Commercial TDB data must never be committed, copied into fixtures, redistributed, or used as general training data.
- For battery and novel quaternary systems, use DFT/MLIP data -> gated PhaseForgePlus prior -> ESPEI posterior -> pycalphad equilibrium.

Gates:

- produced TDB must parse in pycalphad
- known fixture phase-boundary drift `<= 25 K`
- phase set Jaccard distance `> 0.33` escalates
- phase fraction JS divergence `> 0.15` escalates
- ESPEI posterior diagnostics must be recorded

PhaseForgePlus/PhaseForge maturity and license must be verified before authority use.

### L4

L4 is a solver-ensemble layer, not a single phase-field tool.

- Required canonical interface: `PhaseFieldRunSpec`, `KmcRunSpec`, `MesoscaleRunResult`, `MicrostructureTrajectory`.
- PRISMS-PF, MOOSE, MICROSIM, SPPARKS, and neural-operator surrogate must emit the same schema.
- MICROSIM is treated as GPL-3 subprocess/container until license review says otherwise.
- Neural operator starting point: U-AFNO first, DeepONet as comparison. Neural operator is advisory only until it beats persistence baseline and has `< 10%` relative QoI error on held-out classical trajectories.

Gates:

- Cahn-Hilliard mass drift `< 1e-3` on tiny fixture
- Allen-Cahn bounds violated by `< 1e-4`
- T=0 SPPARKS Potts energy does not increase across dumps
- plug-swap from stub to another L4 backend changes backend, not schema

### L5

- Reject non-SPD stiffness or conductivity tensors.
- Analytic heat slab error `< 1e-6`.
- Elastic patch residual `< 1e-8`.
- FEniCSx vs deal.II strain energy disagreement `< 2%`.
- OpenFOAM Poiseuille profile error `< 5%`.
- CFD mass balance and heat balance errors `< 1e-4`.
- VTK/Exodus/FMI artifacts must include units sidecars and hashes.

### L7

- LangGraph is reasoning state, not scientific audit.
- Prefect owns campaign lifecycle, retries, cancellation, deployment metadata.
- Parsl owns fan-out.
- AiiDA/atomate2 own materials workflow provenance.
- BoTorch/Ax owns multi-fidelity acquisition.

Default acquisition:

- use `qMultiFidelityKnowledgeGradient` for expensive multi-fidelity choices
- use `qLogExpectedImprovement` for simpler exploitation
- do not use plain `qExpectedImprovement` as default

Candidate promotion fails if it lacks audit provenance, bypasses disagreement gates, duplicates a rejected candidate, or violates data reuse scope.

## AlabOS Integration

Decision: AlabOS hardware integration is Phase 2.

Phase 1 is in silico only:

- ranked candidates
- provenance and uncertainty
- `AlabOSProtocolCandidate` JSON artifacts
- synthesis-route confidence and assumptions
- no hardware-executable action

Phase 2 begins only when a lab owner provides hardware inventory, credentials, safety interlocks, and adaptation requirements. AlabOS is proven in A-Lab-like solid-state settings, not automatically portable to arbitrary customer hardware.

`ALABOS_MODE=recipe_only` is the default. Any attempt to emit hardware-executable instructions while this flag is active is a hard failure.

## Agent Topology For Overnight Execution

Lead:

- Opus Max-class chief engineer and scientific integrator.
- Owns objective, architecture, scientific coherence, subagent decomposition, hard decisions, integration, and final gate.
- Does not ask user for next steps after startup.

Minimum subagent levels:

- Sonnet-level minimum for implementation subagents.
- Opus-level for architecture, audit/KG, falsification, scientific acceptance, ontology/data rights, and any place where local coding is not enough.

Required subagents:

| Subagent | Minimum | Ownership |
|---|---|---|
| Contracts/audit | Opus preferred | envelope, schema package, unit registry, artifact manifest, audit hash chain |
| KG/ontology/data rights | Opus preferred | EMMO-aligned schema, PROV-O, source manifests, rights claims |
| Fixtures | Sonnet | tiny fixtures only, no bulk datasets |
| Phase 0/L6 | Sonnet, Opus if novelty policy changes | literature extraction stubs, OPTIMADE, generator stubs, novelty filters |
| L1/quantum | Sonnet | DFT/quantum contracts, parsers, H2/LiH VQE tests |
| Ionic transport | Opus preferred | battery conductivity contracts, NEB/MD schemas, falsifiers |
| L1.5 | Sonnet | phonon/transport contracts, ZT sidecar |
| L2 | Sonnet | DPA/MACE stubs, disagreement, license gates |
| L3 | Sonnet/Opus | pycalphad/ESPEI/TDB quarantine |
| L4 | Sonnet/Opus | phase-field/kMC/neural-operator contracts |
| L5 | Sonnet | FEM/CFD contracts and analytic fixtures |
| L7 | Opus preferred | campaign state, Prefect/Parsl/LangGraph/BoTorch wiring |
| MVP packet | Opus preferred | battery evidence packet and thermoelectric sidecar |
| Falsification | Opus preferred | negative fixtures and full falsification wave |
| Runpod cutover | Sonnet | remote stubs, config flags, parity tests |

## Deep Research Policy

When current evidence is needed, use Claude deep research capabilities and Claude subagents. Prefer primary sources, official docs, papers, model cards, software repositories, and license files. Every strategic lookup writes a `SourceManifest` with retrieval date, locator, license, summary, and decision impact.

Required research checks before real use:

- UMA model card, FAIR Chemistry License, HF organization registration, and AUP
- DPA-3.1-3M model card and DeePMD-kit license
- MACE checkpoint license
- PhaseForgePlus and PhaseForge license/maturity
- MICROSIM license
- MaterialsBERT license
- MatterGen, DiffCSP, CrystaLLM license and current generation CLI/API
- OPTIMADE current version and provider coverage
- AlabOS APIs before any non-stub integration

If a lookup cannot be completed, implement a gated stub and record a blocked source manifest. Do not silently assume.

## Audit Trail And KG

Adopt an EMMO-aligned Phase 0 schema with a Zer0pa proprietary extension namespace. Runtime APIs use JSON Schema/Pydantic. Each entity carries JSON-LD ontology bindings so the KG can export RDF/OWL-compatible views.

Use:

- EMMO for materials, properties, models, processes, metrology, and reasoning hooks
- OPTIMADE v1.3-first, v1.2-compatible structure/database interop
- MatML only as import/export adapter
- PROV-O under provenance
- RO-Crate for exportable campaign evidence packages
- SPDX license expressions for source/model/tool licenses

Append-only audit files under `audit/`:

| File | Purpose |
|---|---|
| `runs.jsonl` | run metadata, git commit, executor identity, environment |
| `events.jsonl` | append-only layer events and decisions |
| `artifacts.jsonl` | artifact URI, hash, size, schema, offload refs |
| `sources.jsonl` | source manifests for papers, APIs, docs, model cards |
| `models.jsonl` | tool/model/adapter versions and license gates |
| `parameters.jsonl` | explicit parameters and defaults |
| `disagreement.jsonl` | cross-model and cross-solver disagreement metrics |
| `falsifiers.jsonl` | falsifier definitions, triggers, statuses |
| `rights.jsonl` | tenant, ownership, reuse scope, export rights |
| `decisions.jsonl` | routing and architecture decisions |
| `reasoner_tuples.jsonl` | self-bootstrapping tuple queue |

KG nodes:

`Campaign`, `CustomerTenant`, `Objective`, `AcceptanceGate`, `Hypothesis`, `CandidateMaterial`, `Composition`, `Structure`, `Phase`, `PropertyObservation`, `SimulationJob`, `SimulationResult`, `ModelCheckpoint`, `Dataset`, `LiteratureSource`, `OPTIMADEResource`, `SynthesisRecipe`, `Artifact`, `SourceManifest`, `Falsifier`, `DisagreementMetric`, `Decision`, `Actor`, `Tool`, `ComputeEnvironment`, `License`, `RightsClaim`, `OntologyTerm`.

KG edges:

`DERIVED_FROM`, `USED`, `GENERATED`, `ATTRIBUTED_TO`, `HAS_STRUCTURE`, `HAS_COMPOSITION`, `HAS_PROPERTY`, `PREDICTED_BY`, `MEASURED_BY`, `HAS_UNCERTAINTY`, `AGREES_WITH`, `CONTRADICTS`, `PASSES_GATE`, `FAILS_GATE`, `ROUTED_TO`, `CITES`, `MAPS_TO_ONTOLOGY`, `LICENSED_UNDER`, `OWNED_BY`, `PERMITTED_FOR`, `REDACTED_AS`, `SUPERSEDES`, `CALIBRATED_ON`, `FINETUNED_FROM`, `MEMBER_OF_ENSEMBLE`.

No claim may be promoted unless it has evidence, source manifest, audit record, falsifier, and rights scope.

## Data Sovereignty

Default contract posture: customer-private campaign data, Zer0pa-owned infrastructure, opt-in shared learning.

| Data class | Default ownership | Zer0pa retained rights |
|---|---|---|
| Customer input chemistry, specs, constraints | Customer | processing only during campaign |
| Raw DFT/phonon/MLIP/CALPHAD outputs from customer chemistry | Customer | hash commitments, QA metrics, internal campaign use |
| MLIP fine-tune checkpoints trained on customer data | Customer | adapter code and training pipeline remain Zer0pa |
| CALPHAD TDBs/posteriors fitted from customer data | Customer | generic priors/templates remain Zer0pa |
| Audit log schema and software | Zer0pa | full reuse |
| Audit event content for customer campaign | Customer confidential | redacted hash-chain proof and aggregate reliability metrics |
| Public literature/database KG | Zer0pa subject to source licenses | reuse with attribution |
| Cross-customer training corpus | no use by default | explicit opt-in only |

Offer three contract modes:

- `strict_sovereign`: no cross-customer learning
- `shared_advantage`: anonymized/posterior learning rights for discount
- `open_science`: agreed public artifacts for publishable campaigns

## Self-Bootstrapping Reasoner

Every campaign emits tuples:

```text
(input, proposed_action, simulation_or_experiment, output, falsifier, ground_truth, decision, audit_ref)
```

Fields:

- `input`: structure, composition, target property, prior literature/KG context
- `proposed_action`: run L2, run DFT, run NEB/MD, fit CALPHAD, compile protocol, reject
- `simulation_or_experiment`: layer and adapter
- `output`: property prediction, posterior, disagreement, artifacts
- `falsifier`: threshold checks and disagreement
- `ground_truth`: DFT now, lab characterization later
- `decision`: promote, queue higher fidelity, reject, hold
- `audit_ref`: immutable event chain

If rights are unresolved, tuple `reuse_scope` is `tenant_only`.

## CPU-First Build Sequence

The overnight executor follows this order:

1. `A0-contracts`: boundary enforcement, runtime layout, schema package, artifact manifest, stable structure hashing, unit registry, config registry, universal envelope.
2. `A1-audit-kg-ontology`: audit hash chain, EMMO-aligned KG, source manifests, rights claims, decision log, episodic memory.
3. `A2-fixtures`: H2, LiH, Si, NaCl, LLZO metadata/reduced fixture, Li6PS5Cl metadata fixture, Li-Mg-Zr-Cl seed manifest, Bi2Te3/PbTe/SnSe sidecar, synthetic unstable structure, invalid CIF, duplicate candidate.
4. Phase 0/L6 contracts and stubs.
5. L1 and quantum contracts and stubs.
6. Ionic transport contracts and stubs.
7. L2 contracts and stubs.
8. L3 contracts and stubs.
9. L1.5 contracts and stubs.
10. L4 contracts and stubs.
11. L5 contracts and stubs.
12. L7 orchestration, state machine, BoTorch loop, backedges, and handoff packet.
13. MVP evidence packet generator for battery primary and thermoelectric sidecar.
14. Plug-swap tests for every backend flag.
15. Full falsification wave.
16. Commit, push, report.

Documentation and handover artifacts are not declared final until the engineering, scientific, and brain-functionality gates pass.

## Core Config Flags

```env
MATERIALS_MODE=local_cpu
ARTIFACT_BACKEND=local_manifest
KG_BACKEND=sqlite_stub
PHASE0_SCHEMA=emmo_aligned
PHASE0_LLM_PROVIDER=stub

PHASE0_EXTRACTION_BACKEND=local_stub
PHASE0_DATABASE_BACKEND=optimade_mock
L6_GENERATOR_BACKEND=stub
MATERIALS_L1_BACKEND=local_cpu
IONIC_TRANSPORT_BACKEND=stub
L15_FORCE_BACKEND=mock
L15_BAND_BACKEND=mock
L15_TRANSPORT_BACKEND=local_cpu
L2_BACKEND=local_stub
L2_REQUIRE_DUAL_MODEL=true
L3_CALPHAD_PROVIDER=pycalphad_cpu
L3_TDB_FIT_PROVIDER=espei_cpu
L3_MLIP_PRIOR_PROVIDER=phaseforgeplus_stub
L3_COMMERCIAL_TDB_PROVIDER=disabled
L4_SOLVER=stub
L4_COMPUTE_URL=http://localhost:8044
L5_EXECUTION_MODE=local_stub
L5_BACKEND=fenicsx
L7_ORCHESTRATOR_BACKEND=local_prefect
ALABOS_MODE=recipe_only
```

## REST Stub Surface

```text
GET  /v1/capabilities
POST /v1/audit/events
POST /v1/artifacts/manifests
POST /v1/phase0/extract
POST /v1/phase0/optimade/query
POST /v1/l6/generate
POST /v1/l1/dft/jobs
POST /v1/l1/quantum/vqe/jobs
POST /v1/ionic/neb
POST /v1/ionic/md-diffusion
POST /v1/ionic/electrochemical-window
POST /v1/l15/force-batches
POST /v1/l15/bands/uniform
POST /v1/l2/predict
POST /v1/l2/relax
POST /v1/l2/finetune
POST /v1/l3/equilibrium
POST /v1/l3/fit-tdb
POST /v1/l4/runs
POST /v1/l5/continuum-runs
POST /v1/l7/campaigns
POST /v1/l7/campaigns/{id}/dispatch
POST /v1/l7/campaigns/{id}/acquire
GET  /v1/jobs/{job_id}
GET  /v1/jobs/{job_id}/artifacts
POST /v1/jobs/{job_id}/cancel
```

## Runpod Migration

Runpod migration may begin only when `local_stub`, `local_cpu`, and `runpod_mock` pass the same contract tests.

Cutover procedure:

1. Provision Runpod machine and clone `https://github.com/Zer0pa/Materials`.
2. Install GPU/Docker dependencies only on the Runpod machine.
3. Set backend URLs and config flags.
4. Run sentinel campaign with LLZO, Li6PS5Cl, Li-Mg-Zr-Cl seed, and thermoelectric sidecar.
5. Compare schema shape, artifact manifests, hashes, audit events, disagreement records, and candidate IDs against `runpod_mock`.
6. Confirm no downstream code changed.
7. Promote backend from mock to real only after parity passes.

Hard cutover failures:

- schema drift
- missing artifact hashes
- missing boundary block
- no resource metrics
- caller changes
- lost audit provenance
- model response without disagreement metrics
- UMA access without verified HF organization and AUP gate
- bulk datasets written locally
- promoted candidate bypassing DFT/ensemble/ionic falsifiers

## Acceptance Gates

Scientific:

- Battery MVP has explicit ionic-transport evidence path.
- LLZO and Li6PS5Cl controls are recovered with calibrated uncertainty.
- Novel challenge seed is not called novel until de-duplication and validation pass.
- Every layer has falsifiers and disagreement metrics.
- No certification, clinical, human-subject, ITAR, weapons, or regulatory claims.

Engineering:

- CPU-side pipeline runs end to end with stubs.
- Every GPU layer has a schema-identical REST stub.
- Every backend has at least one plug-swap test.
- Audit hash chain validates.
- KG state is reconstructible.
- No bulk local datasets are downloaded.
- Blocked dependencies return structured blocked results, not crashes.

Brain-functionality:

- A fresh agent can reconstruct the project from repo artifacts without chat history.
- Failed falsifiers and contradictions remain visible.
- Decisions have rationale and supersession path.
- Next actions are explicit and gate-linked.

Falsification wave:

- deliberate invalid CIF
- duplicate generated candidate
- missing boundary block
- missing source manifest
- ungrounded extracted property
- DPA/MACE high disagreement
- DFT convergence failure
- ionic conductivity overclaim without `IonicTransportService`
- unstable phonon structure
- unreadable TDB
- phase-field conservation violation
- non-SPD L5 tensor
- AlabOS executable output while `recipe_only`
- private tuple reuse outside `reuse_scope`
- Runpod mock schema drift

The final report must say which gates pass, fail, or are blocked. Mixed evidence is not a pass narrative.

## Productisation And Pricing

Year 1:

- evidence packet: USD 50K to 75K
- full discovery campaign: USD 150K to 250K
- private deployment or high-IP customer environment: USD 300K to 500K

Year 3 ceiling:

- USD 500K to 1M+ per campaign once reusable MLIP fine-tunes, sovereign CALPHAD posteriors, prior campaign audit data, and validated protocol libraries compound.
- subscription: USD 10K to 40K/month for private campaign portal, audit ledger, KG memory, and model update cadence.

Cross-domain transfer story:

- same evidence engine, different property target
- batteries: ionic conductivity, stability, electrochemical window
- thermoelectrics: ZT, Seebeck, conductivity, thermal conductivity
- catalysts: adsorption energies and surface stability
- optoelectronics: band gap, dielectric/tensor properties
- structural materials: phase stability, microstructure, process properties

The product is property-targeted closed-loop discovery, not a single chemistry demo.

## Open Questions For User

1. Should Zer0pa seek co-IP or revenue share on discovered compositions, or default to customer ownership for lower first-sale friction?
2. Is anonymized posterior reuse explicit opt-in only, or acceptable in a discounted shared-learning mode?
3. Should the first KG backend be property graph with RDF export, or RDF-native with SHACL validation?
4. Should battery Phase 0 adopt BattINFO immediately, or after the MVP schema stabilizes?
5. Should `Li2.2Mg0.1Zr0.9Cl6` remain the pre-registered novel challenge seed, or should L6 choose the exact quaternary after de-duplication?

## Open Questions For Overnight Executor

1. Verify live licenses before enabling real adapters: DPA-3.1-3M, DeePMD-kit, MACE checkpoint, UMA, PhaseForgePlus, MICROSIM, MaterialsBERT.
2. Decide first KG implementation after dependency inspection: SQLite/property graph with RDF export is acceptable if RDF-native would slow the CPU gate.
3. Decide whether `IonicTransportService` starts with NEB-only stubs or includes MD diffusion stubs in the first pass. The PRD requires both contracts; implementation order is executive discretion.
4. Decide exact package layout based on the codebase created during execution. The architecture is contract-first; do not overfit to a preselected framework if it slows the authority metric.

## Final Output Required From Overnight Executor

Commit and push:

1. CPU-side implementation.
2. Schemas and validators.
3. Layer stubs and local services.
4. Audit/KG seed and validators.
5. MVP evidence packet generator.
6. Thermoelectric sidecar.
7. Runpod config and parity tests.
8. Full falsification wave report.
9. Final execution report with commit hash, links, tests, gates, parked items, and blockers.

Do not report a partial win as success. If the authority metric fails, keep the failure visible and continue the fix loop until blocked.
