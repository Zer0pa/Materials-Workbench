# Fresh-Eyes Synthesis on the Materials Briefs

Synthesis-agent output. Captures the operator-read on the two source briefs (`source-briefs/01-full-technology-landscape.md`, `source-briefs/02-corrections-and-architecture.md`) and the research-agent handover note (`source-briefs/00-research-agent-handover-note.md`) by Claude Opus 4.7 (1M context), 2026-04-29. Read by the materials orchestrator as the substrate for their own fresh-eyes augmentation.

## Boundary

Research infrastructure for in silico materials science discovery. Outputs are research artifacts. No regulatory certification claims. No clinical or human-subject use. ITAR / weapons applications excluded.

## Acknowledgement

The briefs and the handover note are strong. Issue 4 (CALPHAD sovereignty), Gap B (DPA-3 #1 LAMBench), Gap D (AlabOS production-grade), Gap H (battery MVP commercial spec), and the eight intersectional signals are decisive. The handover note already does substantial "what the agent missed" work and elevates LAMBench to corrections-level, the EMMO ontology gap, the OMol25 context gap, the PennyLane+PySCF integration gap, and the neural-operator phase-field starting-point gap. This synthesis does not repeat those.

## The architectural reframe — 7 layers collapse to 3 via variational unification

The eight intersectional signals are not "framing language for customer differentiation." They are the architecture, and the briefs treat them as commentary instead of as load-bearing structure. Read them together:

- L1 (DFT / VQE) — variational over electron density / quantum state.
- L1.5 (phonon BTE) — variational over information channel capacity.
- L2 (MLIP) — descriptor as sufficient statistic; equivariance is information-preserving compression.
- L3 (CALPHAD) — variational over Gibbs energy on a Fisher-information manifold.
- L4 (phase field) — variational over Ginzburg-Landau free energy functional.
- L6 (MatterGen) — variational over learned distribution.
- L7 (BoTorch + AlabOS) — variational over expected free energy (epistemic + instrumental).

**Every layer is a variational problem on a different functional space.** This is mathematically the same statement as "every layer is solving min F(θ) for some F and θ." Brief #2 names this in Gap G ("Unified Variational Architecture") but stops at the observation. The implication it does not draw out:

**The 7-layer pipeline collapses to 3 functional layers:**

1. **Knowledge / Hypothesis Layer** — literature mining + KG + LLM agent. Selects what variational problem to instantiate.
2. **Variational Solver Layer** — single abstract solver class, parameterised differently per physical layer. DFT / MLIP / CALPHAD / phase field / acquisition function are seven instantiations of the same `VariationalProblem(parametrisation, action, constraints).solve()` interface.
3. **Active Inference Loop Layer** — BoTorch + AlabOS as the same epistemic-free-energy-minimising agent in different substrates (in silico vs in lab).

This is the architectural core no competitor can replicate cleanly. Citrine has SaaS but no variational engine. Schrödinger has variational solvers but per-layer, closed-source, not unified. Materials Project has data but no orchestration. Orbital is a single MLIP. **Zer0pa's edge is open-source-with-math: every variational instance shares an interface, and they can be composed.**

Concretely: a single `solve()` call routes to PySCF for DFT, PennyLane for VQE (today classical-simulated, 2030+ quantum), DeePMD for MLIP, ESPEI for CALPHAD, PRISMS-PF for phase field, BoTorch for acquisition. Plug-replaceability becomes "swap any variational solver in <1 day" because they all conform to one interface. The PRD should consider specifying this interface as the architectural primitive.

## What this means for the quantum slot

Brief #2 places the PennyLane slot at L1 (electronic structure VQE). That is correct but underspecified. **At the variational-engine abstraction layer, quantum can plug into three slots, not one:**

- L1 VQE — quantum minimisation of molecular Hamiltonian.
- L4 phase field — QAOA optimisation of free-energy functional on discretised mesh.
- L7 BoTorch acquisition — quantum amplitude amplification of high-EI candidates.

When fault-tolerant hardware lands in 2030–2035, the same `VariationalProblem` interface routes to whichever slot has a quantum advantage first. Probability is ~0 that DFT VQE is the first quantum-advantaged materials problem — the hardware threshold is 100+ logical qubits for 50-electron systems, the hardest of the three. QAOA on phase field discretisation may land sooner. The quantum slot may belong at the abstract layer rather than at L1 specifically.

## The DPA-3 + MACE ensemble is a universal pattern

The handover correctly elevates this to a corrections-level finding. The deeper insight: cross-model energy disagreement is not just an L2 uncertainty signal. **It is the universal falsification primitive across the pipeline.**

Same pattern, different layers:

- L1: Quantum ESPRESSO PBE vs CP2K HSE on the same structure → exchange-correlation functional uncertainty.
- L2: DPA-3 vs MACE → MLIP epistemic uncertainty.
- L3: ESPEI MCMC posterior vs Thermo-Calc TDB → CALPHAD parameter uncertainty.
- L4: PRISMS-PF vs MOOSE on identical microstructure → phase field discretisation uncertainty.
- L6: MatterGen vs DiffCSP → generative model novelty disagreement.

The PRD should consider specifying "ensemble disagreement" as a first-class quantity that flows through the audit log alongside primary outputs. It is the materials-domain equivalent of cross-falsifier discipline. Cross-model disagreement at every layer turns the audit log into something a regulator (or a customer's CTO) can audit.

## Specific things the briefs and handover do not see

### 1. The first MVP should produce a publishable paper, not just a customer deliverable

Materials outputs face no regulatory ceiling. They can publish in *Nature Materials*, *npj Computational Materials*, *Chem*, *Joule*. **The first MVP cardiac-analogue should be: "First open-source, audit-trailed, variationally-unified closed-loop discovery of [chemistry] X with predicted properties Y and AlabOS-compatible synthesis recipe Z, validated at partner lab W."** That paper is the credibility signal customers need to see before paying $50K-$250K. Without it, the price point is hypothetical. The PRD should target a paper deliverable as part of the MVP, not a follow-on.

### 2. Property-targeted, not domain-targeted, is the productisation play

The handover says "battery materials" or "thermoelectrics." But the engine reasons over a property target ("σ > 10⁻³ S/cm at 300K", "ZT > 1.5 at 700K", "elastic modulus < 50 GPa"). **The product is property-targeted closed-loop discovery, parameterised per customer chemistry.** A single architecture serves: solid-state electrolytes → thermoelectrics → fuel-cell catalysts → CO2 capture sorbents → optoelectronics. The MVP picks one (battery), the year-2 expansion is "same engine, different parameterisation." Pricing should reflect: campaign ($50K-$250K) + access-to-engine subscription. The handover misses the recurring-revenue framing.

### 3. The data sovereignty schema is missing and will block the first sale

Customer brings their chemistry. The pipeline runs DFT + MLIP fine-tune + CALPHAD fit + ESPEI parameter posterior + AlabOS recipe. Each step generates a (structure, energy, force, parameter, posterior) tuple. **Who owns these?**

- If Zer0pa owns: customers won't sign, because their chemistry IP leaks into our private dataset.
- If customer owns: the self-bootstrapping reasoner moat dies — no domain-specific MLIP corpus across customers.
- If shared with rights split: defines per-data-class rights (raw DFT = customer; MLIP fine-tune weights = customer; anonymised property posteriors = shared; audit log structure = Zer0pa).

The PRD must specify the data-rights schema before the first sale. This is a contract structure, not just a technical schema, and it determines whether the moat compounds or evaporates.

### 4. The 7→3 layer collapse changes how customers think about the product

A customer reading "we have a 7-layer pipeline (L1 DFT, L1.5 phonons, L2 MLIP, L3 CALPHAD, L4 phase field, L5 FEM/CFD, L6 generative, L7 orchestration)" hears: "complicated tool chain." A customer reading "we have a knowledge layer, a variational solver, and an active-inference loop" hears: "three things I understand." The 7-layer abstraction is for orchestrators. The 3-layer abstraction is for buyers. The PRD should specify both.

### 5. Real-time microstructure during synthesis is a frontier no one has

FNO/DeepONet phase field running inline with AlabOS synthesis. Sensor reports T, time, composition → neural operator predicts microstructure formation in milliseconds → BoTorch decides next experimental condition before the current step finishes. Currently:

- FNO for phase field is research (Issue 3 redirects to it; no production starting point yet — handover note flags this gap).
- AlabOS deployment is rare (the only production instance is the A-Lab itself, with 41 syntheses on record).
- No public integration of the two exists.

Zer0pa can be first. The PRD may consider specifying this as a Phase-2 frontier deliverable.

### 6. Cross-domain transfer for MLIPs is buried in Gap F

The intersectional signal in Gap F notes: "the irreducible representations of SO(3) that e3nn uses are the same Wigner D-matrices that describe how physical tensor fields transform under rotations." Concrete consequence the brief does not name: **a MACE backbone trained on inorganic crystals can transfer to molecular property prediction with limited retraining of the readout head.** Same equivariant backbone, different readout. This means the L2 MLIP layer is not just "DPA-3 + MACE for inorganic"; it is a cross-chemistry foundation model. **One foundation, many readouts.**

### 7. Three named compounds for the MVP seed evidence packet

If solid-state Li-ion electrolyte is the MVP wedge, three named compounds for the seed evidence packet (analogous to dofetilide / verapamil / ranolazine in Health):

- **A known good** — Li₇La₃Zr₂O₁₂ (LLZO). Verifies the engine reaches the literature reading on a well-studied system.
- **A known borderline** — Li₆PS₅Cl argyrodite. Partially studied. The engine should show calibrated uncertainty, not over-confidence.
- **A novel candidate** — a quaternary outside MP-20 coverage. The engine should produce a stability + conductivity prediction that no off-the-shelf TDB can compute.

If the engine reaches the literature reading on LLZO, calibrated uncertainty on Li₆PS₅Cl, and a defensible novel prediction on the quaternary, the MVP is real. If any of those fails, the MVP is in trouble — a clean falsification gate. The orchestrator may improve on this triple; the principle (known-good / known-borderline / novel) should hold.

### 8. The price ceiling is $1M/campaign by year 3, not $250K

Year-1 campaigns yield: 1 chemistry-specific MLIP fine-tune + 1 sovereign quaternary TDB + 1 AlabOS recipe + raw DFT corpus. At $50K-$250K. Year-3 campaigns can yield: same outputs *plus* access to a maturing internal MLIP zoo (5-10 chemistry-specific fine-tunes that transfer-learn into novel chemistries), a sovereign multi-quaternary CALPHAD library, validated synthesis recipes across an AlabOS-compatible robot fleet, and the property posterior conditioned on years of internal campaign data. **That's CRO+platform pricing, $500K-$1M+/campaign.** The PRD's pricing section should specify the year-1 floor and the year-3 ceiling, plus the data-asset accumulation that justifies the trajectory.

## A cross-workstream substrate proposal — and the operator override

Pharma and Materials are one pipeline with two domain configurations, not two pipelines. The variational engine is identical. The orchestration trio is identical. The KG schema differs only at leaf-node ontology. The active-inference loop with BoTorch is identical. AlabOS for materials = Strateos for pharma — same epistemic-free-energy effector, different physical substrate.

If the orchestrator builds Materials independently of the prior Health PRD, Zer0pa duplicates the architectural core twice. The synthesis agent recommended a shared `Zer0pa/zer0pa-substrate` repo or namespace for the variational engine + audit trail + KG schema + active inference loop, with `Zer0pa/Health` and `Zer0pa/Materials-Workbench  as domain configurations on top.

**The operator has rejected this proposal.** The reasoning is captured in `MODUS-OPERANDI.md` § Parallel-exploration principle: parallel agents on the same engineering problem produce diversity of architecture; surplus coding capacity makes redundancy cheap; convergence happens after all parallel workstreams complete, not during. **The Materials orchestrator builds an independent end-to-end pipeline.** Cross-pollination at the fresh-eyes level (reading the Health repo as reference) is allowed; substrate dependency is not. This synthesis recommendation is captured here for traceability.

## How this maps onto the orchestrator's job

The Materials orchestrator's PRD should differ from the Health PRD in five concrete ways, beyond domain content:

1. **Variational engine considered as architectural primitive** — `VariationalProblem(parametrisation, action, constraints).solve()` with seven dispatch routes, ensemble-by-construction at the engine layer.
2. **Cross-model disagreement** as a first-class quantity flowing through the audit log alongside primary outputs.
3. **Publishable-paper deliverable** — explicit MVP target.
4. **Property-targeted productisation** — pricing + recurring-revenue framing built in; year-1 floor and year-3 ceiling.
5. **Data sovereignty schema** — contract structure specified, not just technical schema.

These are pressure-test points for the orchestrator, not pre-baked answers. The orchestrator may take them, refine them, or override them with reasoning. The full PRD shape is the orchestrator's call; the substrate is on the table.

## Provenance

- Synthesis agent: Claude Opus 4.7 (1M context).
- Source: `source-briefs/00-research-agent-handover-note.md`, `source-briefs/01-full-technology-landscape.md`, `source-briefs/02-corrections-and-architecture.md`, plus reference to the Zer0pa Health workstream at `https://github.com/Zer0pa/Health` (for sibling-pattern reading only).
- Date: 2026-04-29.
- Operator override on cross-workstream substrate sharing: 2026-04-30. Captured here and in `HANDOFF-TO-ORCHESTRATOR.md` § Operator override.
- Next role: materials orchestrator (writes `PRD.md`).
