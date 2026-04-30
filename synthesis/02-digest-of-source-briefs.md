# Digest of Source Briefs — Materials Workstream

Working reference. Consolidates `source-briefs/01-full-technology-landscape.md` (Brief #1, ~117K), `source-briefs/02-corrections-and-architecture.md` (Brief #2, ~88K), `source-briefs/00-research-agent-handover-note.md`. **Brief #2 supersedes Brief #1** where they disagree. Boundary: in-silico materials discovery research only — no clinical, regulatory, ITAR scope.

***

## Section A — The 7 layers (compact)

### L1 — Electronic Structure (DFT / VQE)
- **Stack:** Quantum ESPRESSO 7.4 (A/GPL, primary periodic), PySCF 2.8 (A/Apache 2.0, primary Python-native), CP2K 2025.1 (A/GPL, AIMD), ABINIT 10.x (A/GPL, optional DFPT), VASP 6.6.0 (C/commercial — **Brief #2 marks "✗ Avoid"**, supersedes Brief #1 which had it as D-acceptable). PennyLane v0.39+ (A/Apache 2.0) as quantum slot — entirely new in Brief #2.
- **Interface:** CIF / POSCAR in; extxyz (E/F/stress) out; cube files; Wannier90 bands.
- **GPU:** QE CUDA/HIP beta; PySCF cuNumeric/cuPy; CP2K CUDA+OpenCL; ABINIT limited. CPU or GPU buildable.
- **License:** A/B fully commercialisable; VASP separate commercial license (~EUR 5K academic per Brief #1).
- **Falsifier:** Functional disagreement (PBE vs HSE); cross-code reproduction.
- **Datasets:** Materials Project (154K compounds, 530K calcs, CC-BY-4.0); OQMD (1.2M); NOMAD (15M); JARVIS-DFT (80K 3D + 1K 2D, NIST); AFLOW (3.5M); Alexandria (4.5M).

### L1.5 — Phonon Stack (Brief #2 Gap A — absent from Brief #1's seven-layer table)
- **Stack:** Phonopy v2.26+ (A/BSD, harmonic), Phono3py v2.7+ (A/BSD, anharmonic), HiPhive v1.4+ (A/MIT, MLIP-accelerated), BoltzTraP2 v22.12+ (B/GPL, electronic transport), AMSET v0.4+ (A/MIT, doped systems alt).
- **Interface:** Phonopy reads QE/CP2K/VASP/LAMMPS via ASE; FORCE_CONSTANTS files consumed by Phono3py / HiPhive / ShengBTE.
- **GPU:** Inherited via MLIP backend; BoltzTraP2 / AMSET CPU only.
- **License:** All A/B — commercialisable.
- **Falsifier:** "MACE-MP-0 zero-shot achieves thermal conductivities compatible within a factor of two of DFT-PBE values for 69% of materials in the phononDB-PBE database." HiPhive ~10x speedup ("from ~480,000 CPU-hours to ~12,000 CPU-hours" for 220-material ternary benchmark).
- **Datasets:** phononDB-PBE; LLM-curated thermoelectric set (27,822 records via GPT-4.1 Mini, F1=0.909).
- **Best MLIP for phonons:** "EquiformerV2 pre-trained on OMat24… consistently outperforms all models for second-order IFC, lattice thermal conductivity" (Sept 2025 benchmark, 2,429 materials).

### L2 — Atomistic Simulation (MLIP)
- **Stack:** MACE-MPA-0 (A/MIT, primary), **DPA-3.1-3M (A/MIT, mandatory ensemble — overturns Brief #1)**, Meta UMA (E/FAIR Chem License v1, include — see corrections), MatterSim-v1 (A/MIT, optional), CHGNet (A/MIT, magnetics), SevenNet (A/MIT, fast screening), ORB-v3 (A/Apache 2.0). e3nn v0.5+ (A/MIT) as substrate.
- **Disagreement:** Brief #1 ranked **EquiformerV2+DeNS > UMA > MACE-MPA-0 > ORB > SevenNet > MACE-MP-0 > CHGNet** (Matbench Discovery). Brief #2 LAMBench (Jan 2026) overturns: **DPA-3.1-3M rank 1 (FF 0.175, prop 0.322); DPA-2.4-7M rank 3/2; MACE-MPA-0 rank 8/7; MACE-MP-0 rank 10/9.** UMA excluded from LAMBench due to FAIR Chem License barrier.
- **Interface:** extxyz / LAMMPS data in; HDF5 / LAMMPS dump out; ASE calculator universal.
- **GPU:** Full CUDA/PyTorch across all. LAMMPS for MD (B/GPL).
- **License:** A except UMA (E — custom commercially-usable).
- **Falsifier:** Energy disagreement DPA-3 vs MACE-MPA-0 — "primary uncertainty quantification signal for prioritising L1 DFT recalculation." MACE multi-head committee (Dec 2025).
- **Datasets:** OMat24 (110M+ DFT calcs, CC-BY-4.0); OMol25 (100M+ molecular calcs, CC-BY-4.0); OC25 (CC-BY-4.0, solid-liquid catalysis); OpenLAM (DeepModeling, MIT).
- **Fine-tuning economics:** "100–500 configurations + 1–4 GPU-hours on A100" — per-system onboarding cost.

### L3 — Thermodynamic Modelling (CALPHAD)
- **Stack:** pycalphad v0.10+ (A/MIT), **ESPEI v0.8+ (A/MIT — Brief #2 elevates)**, **PhaseForgePlus v0.1 (A/MIT, MLIP-to-CALPHAD bridge — entirely new in Brief #2; repo: `dogusariturk/PhaseForgePlus`)**, OpenCalphad 6.0 (B/LGPL), DFTTK v0.4+ (A/MIT, low maint.), Thermo-Calc 2025a TCNI/TCTI (D, conditional — ~$15K/year per Brief #1).
- **Disagreement:** Brief #1 called Thermo-Calc TDB "the single most impactful commercial investment." Brief #2 reframes as conditional; ESPEI + PhaseForgePlus is sovereign open path.
- **Interface:** TDB file in/out; pycalphad Python API.
- **GPU:** All CPU. PhaseForgePlus uses GPU only via MLIP backend.
- **License:** Open path A. TDB files D, non-redistributable.
- **Falsifier:** ESPEI Bayesian MCMC posterior vs experimental phase boundaries.
- **Datasets:** MSTDB-TC (NIST/ANL, open, molten salts); ESPEI Cu-Mg tutorial; Materials Project formation energies as ESPEI input.
- **Critical (Brief #2 Issue 4):** "for Li-Mn-Ni-Co-O battery cathode systems… neither open nor commercial TDB databases cover novel quaternary compositions adequately" — competitive advantage.
- **Scaling:** Cu-Mg binary ~50–100 DFT configs; ternary ~200–500; quaternary (Li-Mn-Ni-Co) ~1,000–5,000.

### L4 — Mesoscale (Phase Field / kMC)
- **Stack:** PRISMS-PF 2.4 (A/LGPL, primary), MOOSE/MARMOT 2025 (A/LGPL, multiphysics), MICROSIM 2024 (A/MIT, CALPHAD-coupled — new in Brief #2), SPPARKS 2025 (B/GPL, kMC), ParaDiS (A/BSD, dislocation). PINNs-MPF (E, research only). **FNO/DeepONet (A/MIT, build target — Brief #2 reframes from PINN)**.
- **Disagreement:** Brief #1 said "Build or contribute to PINNs-MPF." Brief #2 Issue 3: "build a neural operator phase field solver with CALPHAD coupling" via FNO or DeepONet. PINN no longer the target.
- **Interface:** TDB + interface energies + initial microstructure in; VTK / HDF5 fields out.
- **GPU:** PRISMS-PF partial; mostly MPI-parallel CPU regime today.
- **License:** A/B; SPPARKS GPL applies only to code redistribution, not outputs.
- **Falsifier:** Cross-code (PRISMS-PF vs MOOSE on identical microstructure).
- **Datasets:** Solver-driven; not a data-trained domain.
- **Build gap:** No production-grade neural operator phase field repo for materials — "the open gap in the 2026 toolchain."

### L5 — Continuum / Process (FEM / CFD)
- **Stack:** FEniCSx 0.9 (A/LGPL, primary), deal.II 9.7 (A/LGPL, alt), OpenFOAM 2024 (B/GPL, CFD).
- **Interface:** Constitutive law parameters + boundary conditions in; Exodus / VTK fields out.
- **GPU:** FEniCSx limited; deal.II CUDA/HIP via Trilinos; OpenFOAM limited. Mostly CPU + MPI.
- **License:** A/B fully commercialisable.
- **Falsifier:** CPFEM cross-validation; Abaqus benchmark (commercial).
- **Datasets:** Solver-driven on user geometries.

### L6 — Generative Discovery
- **Stack:** MatterGen 1.0 (A/MIT, primary), DiffCSP (A/MIT, alt), CrystaLLM 2024 (A/MIT, LLM-for-CIF), GNoME dataset (A/CC-BY, dataset only — model proprietary), USPEX 10.5 (C — **Brief #2 marks "✗ Avoid" commercial**), CALYPSO (C). CLOUD foundation model (E, license unconfirmed).
- **Phase 0 (Brief #2 Gap E):** GPT-4.1 Mini + LangGraph (D/API), Robocrystallographer (A/MIT), MaterialsBERT (A/Apache 2.0), ChemDataExtractor v2 (A/MIT).
- **Disagreement:** Brief #2 demotes USPEX commercially; adds Phase 0 LLM extraction layer as first-class.
- **Interface:** Property + chemical-system constraint in; CIF candidates out → mandatory L1 DFT validation.
- **GPU:** Required for training/inference on MatterGen/DiffCSP/CrystaLLM. Phase 0 LLMs API-based.
- **License:** A for open generative; D for GPT-4.1 Mini ($0.01/paper).
- **Falsifier:** **LeMat-GenBench (NeurIPS 2025, S.U.N. = Stability/Uniqueness/Novelty)** — canonical. "An increase in stability leads to a decrease in novelty and diversity on average, with no model excelling across all dimensions." Mandatory DFT validation closes loop.
- **Datasets:** Materials Project; GNoME (2.2M, 380K stable); LLM-curated TE (27,822 records).
- **Phase 0 economics:** GPT-4.1 F1=0.909 (ZT 0.894, Seebeck 0.916, κ 0.927); Mini F1=0.889 at $0.01/paper; "$112 USD for 10,000 papers."

### L7 — Orchestration / Lab
- **Stack:** AiiDA 2.8 (A/MIT, primary), Atomate2 0.5 (Brief #1: Apache 2.0; Brief #2: MIT — Section K item 1), pyiron (A/BSD, alt), BoTorch + Ax (A/MIT, Bayesian opt), OpenAD (A/Apache 2.0, agents), OPTIMADE v1.2 (A/spec). **AlabOS v1.0+ (A/MIT — entirely new in Brief #2; repo: `CederGroupHub/alabos`)** for production lab automation. HELAO (A/MIT, electrochemistry alt). Tensor networks: ITensor (A/MIT) / TeNPy (B/GPL) for strongly correlated systems where DFT fails.
- **Disagreement:** Brief #1 had no AlabOS in Executive Map; Brief #2 elevates to primary L7 ("41 novel materials synthesised at A-Lab").
- **Interface:** AiiDA provenance graph; JSON synthesis spec → LLM translation → AlabOS task objects → robotic execution; OPTIMADE federated REST.
- **GPU:** Orchestration N/A; BoTorch GPU yes.
- **License:** All A — outputs commercialisable.
- **Falsifier:** Provenance audit chain; cross-database OPTIMADE consistency.
- **Datasets/repos:** Materials Project API (`next-gen.materialsproject.org/api`); OPTIMADE 15+ DB federation (MP, AFLOW, JARVIS, NOMAD, Alexandria, COD, OQMD); AlabOS at `CederGroupHub/alabos`.

***

## Section B — The 4 corrections from Brief #2

### 1. UMA License Reclassification
**Brief #1:** UMA may be restricted from Sandton; Class A† with review warning.
**Brief #2 verdict:** "Flag is overstated. South Africa is not a restricted territory… Recommended re-classification: Class E (custom FAIR Chemistry License v1 — commercially usable with Acceptable Use Policy constraints)."
**Verbatim license text:** "UMA is available via HuggingFace globally, except in comprehensively sanctioned jurisdictions, and in China, Russia, and Belarus." Output ownership: "as between you and Meta, you are and will be the owner of such derivative works and modifications."
**AUP exclusions:** "military/warfare, ITAR-controlled applications, and weapons development. For energy materials and battery discovery applications this restriction is immaterial."
**Action:** Register Zer0pa HuggingFace account with accurate organisational info before accessing UMA weights.
**Critical:** fairchem library is MIT; weights are separate custom license. Brief #1 conflated.

### 2. MatterGen Novelty
**Brief #1:** "Significant fraction of MatterGen 'novel' structures correspond to training data compounds in different representations."
**Brief #2 verdict:** "Partially Correct." LeMat-GenBench (NeurIPS 2025) is canonical evaluation. Verbatim finding: "an increase in stability leads to a decrease in novelty and diversity on average, with no model excelling across all dimensions." MatterGen SUN exceeds prior models by 2x+ on MP-20 but does not transfer uniformly to unexplored chemical spaces.
**Action:** No tool change. DFT validation at L1 (already mandatory) handles this. Track LeMat-GenBench leaderboard (HuggingFace, open).

### 3. PINNs-MPF → Neural Operator Pivot
**Brief #1:** "Build or contribute to PINNs-MPF."
**Brief #2 verdict:** "Confirmed — still research-only. Additionally: the broader community is moving toward neural operator architectures (FNO, DeepONet)." "Neural operators learn the operator mapping between function spaces directly… both faster and more generalizable."
**Updated directive:** "Build or contribute to a neural operator phase field solver with CALPHAD coupling." Target: FNO or DeepONet on phase field order parameters with CALPHAD-computed driving forces as operator inputs.
**References:** PDEBENCH (general scientific ML, not materials phase field); NeuralPDE.jl (Julia, both). **No specific repo demonstrates FNO/DeepONet solving Allen-Cahn or Cahn-Hilliard for materials microstructure** — handover-flagged starting-point gap.

### 4. CALPHAD TDB Sovereignty
**Brief #1:** Commercial Thermo-Calc TDB is "the single most impactful commercial investment for Layer 3."
**Brief #2 verdict:** "Partially Correct… Two developments since Brief #1 significantly reduce the strategic urgency: (1) ESPEI for 3–5 component systems, and (2) PhaseForgePlus (2025), an open-source MLIP-to-CALPHAD pipeline."
**Open TDB survey (verbatim April 2026):** "Li-Mn-Ni-Co-O: No comprehensive open TDB. Al-Cu-Mg-Zn-Si: Partial. Fe-Ni-Cr stainless: Partial. HEAs (5-component equimolar): Essentially none."
**Strategic implication:** "for Li-ion battery cathode systems, neither open nor commercial CALPHAD databases are adequate without custom ESPEI fitting from DFT data — a conclusion that actually favors the Zer0pa orchestration approach over competitors who rely on off-the-shelf TDB files."
**Action:** DFT → ESPEI → pycalphad as standard L3. Acquire commercial TCNI/TCTI only for Ni/Ti superalloy projects.

***

## Section C — The 8 gaps (A through H)

**A — Phonon Stack:** Add L1.5 between L1 and L2. Phonopy → Phono3py chain. MACE-MP-0 / EquiformerV2 forces for screening (~10x speedup); DFT-recalculate force constants only for top candidates. BoltzTraP2 → ZT as standard output. AMSET preferred for doped thermoelectrics. Bottlenecks: anharmonic force constants (SnSe, PbSe); BoltzTraP2 rigid-band breaks for heavy doping; grain boundary thermal resistivity absent from all first-principles models.

**B — DPA-3 / DeePMD:** Add DPA-3.1-3M alongside MACE-MPA-0 as **co-equal** L2. Run both on every L6 candidate. Energy disagreement = primary uncertainty signal. LAMBench (Jan 2026): DPA-3.1-3M rank 1; DPA-2.4-7M rank 3/2; MACE-MPA-0 rank 8/7; MACE-MP-0 rank 10/9. UMA excluded due to FAIR Chem License — research-community signal. DeePMD-kit v3.1+ integrates with GROMACS (Feb 2026); both work as ASE calculators — drop-in in AiiDA. DP-GEN v0.11+ for active learning.

**C — ESPEI / CALPHAD Sovereignty:** Build DFT → ESPEI → pycalphad as standard L3. PhaseForgePlus as MLIP bridge. Cu-Mg end-to-end is canonical demo. ESPEI's Bayesian uncertainty "propagates DFT input uncertainty into output CALPHAD parameter distributions, which is directly useful for the lab's BoTorch active learning layer." Information-geometry insight: ESPEI MCMC navigates "the Fisher information manifold of the thermodynamic state space" — concrete improvement target is "natural gradient MCMC on the thermodynamic manifold."

**D — AlabOS:** "AlabOS is the primary integration target for the physical synthesis layer. Build a JSON-schema protocol generator that translates AiiDA/Atomate2 workflow outputs into AlabOS task objects." Architecture: AiiDA → JSON → LLM translation (GPT-4.1) → AlabOS task objects → robotic execution. "Achievable with current tools." Repo: `CederGroupHub/alabos` (MIT). MongoDB state. Production at A-Lab. Inorganic solid-state synthesis. SDL 2.0: "no OPTIMADE-equivalent for synthesis instructions exists as of April 2026."

**E — Phase 0 Literature Mining:** "LangGraph + GPT-4.1 Mini for cost-efficient property extraction from full-text papers (~$0.01 per paper at scale). Combine with Robocrystallographer for structure descriptions and MaterialsBERT for initial candidate filtering." GPT-4.1 F1=0.909 (50-paper benchmark); Mini F1=0.889 at $0.01/paper; $112 USD for 10,000 papers. Effort: 1–2 weeks. Output: "a proprietary structured dataset that becomes a durable competitive asset."

**F — e3nn / Equivariant Substrate:** Build L2 fine-tuning around MACE multihead replay finetuning. Use e3nn directly only for custom tensor property heads. "100–500 configurations + 1–4 GPU-hours on A100." Tensor benchmarks: elasticity MACE MAE < 10 GPa; dielectric EquiformerV2 RMSE ~0.27 on Matbench. Cross-domain: "Several 2025 papers demonstrate meaningful transfer learning between protein structure models (ESM-2) and crystal MLIP fine-tuning."

**G — Quantum Horizon:** "Allocate 1 week of engineering time to build a PennyLane quantum slot in the L1 architecture that accepts a molecular Hamiltonian (from PySCF or OpenFermion) and returns a ground-state energy estimate." Classical VQE today; routes to fault-tolerant hardware 2030+ with no pipeline changes. "No demonstrated quantum advantage… VQE limited to ~50–100 spin-orbitals on NISQ. Fault-tolerant threshold: ~50–100 correlated electrons, achievable approximately 2030–2035." Tools: PennyLane v0.39+, Qiskit Nature v0.7+, OpenFermion v1.6+ (all A/Apache 2.0). ITensor / TeNPy for strongly correlated systems.

**H — Battery Materials MVP:** Solid-state electrolyte discovery as first commercial offering. "Multi-fidelity screening service that takes a target ionic conductivity specification and returns a ranked list of novel candidate compositions… fully provenance-tracked from literature mining through DFT validation. Price point: $50K–$250K per discovery campaign (analogous to CRO pricing in pharma)." Computationally predictable: bulk ionic conductivity (~20% accuracy for argyrodites Li₆PS₅Cl, LLZO, sulfides), electrochemical stability, hull distance, formation energy, phase diagram stability. Unsolved: grain boundary conductivity, SEI dynamics, long-timescale degradation, polycrystalline transport. Throughput: "single A100 GPU can evaluate formation energy and stability estimates for ~100,000 candidate compositions per day." Differentiation: "Multi-fidelity closed-loop discovery as a service, for battery materials companies that need novel compositions outside the range of existing databases." Competitor table: Schrödinger (~$1M+/year enterprise), Citrine, Orbital Materials, Chemify, Exabyte/Simmate, Enthought.

***

## Section D — The 8 intersectional signals

Framing Zer0pa uses that domain-native competitors cannot.

1. **Phonon BTE = information channel** (Gap A). Phonon mean free path = information decay length; thermal conductivity minimisation = channel noise maximisation.
2. **Descriptor = sufficient statistics** (Gap B). Mutual information between local structure and energy; equivariance is information-preserving compression.
3. **CALPHAD = information geometry** (Gap C). Gibbs energy is log-partition function of exponential family; ESPEI MCMC follows Fisher metric geodesics.
4. **Autonomous lab = active inference agent** (Gap D). AlabOS policy implements Friston free energy minimisation; BoTorch EI = epistemic value decomposition.
5. **Knowledge graph = semantic memory** (Gap E). Mutual information-weighted graph traversal = optimal retrieval under uncertainty.
6. **E(3) equivariance = geometric unity** (Gap F). Wigner D-matrices as shared mathematical object; equivariant networks compute parallel transport on the frame bundle.
7. **Variational principle unification** (Gap G). VQE, phase field, CALPHAD, BoTorch are instances of the same variational principle on different functional spaces.
8. **BoTorch = active inference agent** (Gap H). EI = epistemic free energy minimisation; explore-exploit = epistemic vs instrumental value decomposition. "Not a loose analogy — the mathematical objects are identical."

***

## Section E — The 5 pending decisions

**1. L2 Architecture (DPA-3 alone vs DPA-3 + MACE ensemble).** For ensemble: LAMBench DPA-3 #1, MACE-MPA-0 #8 — but MACE-MPA-0 leads inorganic-only (Matbench Discovery). Brief #2 recommends co-equal ensemble; energy disagreement = uncertainty signal. Against: compute and fine-tuning costs double per system (~1–4 GPU-hours/A100/model). Asymmetric variant (DPA-3 primary + MACE validator) cheaper but cost-benefit threshold not stated in briefs.

**2. L3 Build vs Buy.** For build (sovereign): battery cathode quaternaries (Li-Mn-Ni-Co-O) have no adequate TDB; ESPEI + PhaseForgePlus is only viable route. For buy: Thermo-Calc faster for Ni/Ti superalloy projects with immediate timelines (~$15K/year). Scaling: binary 50–100 DFT configs → ternary 200–500 → quaternary 1,000–5,000. **Decision is sub-domain-specific, not pipeline-wide.**

**3. AlabOS Integration Timeline (Phase 1 in silico vs Phase 2 with hardware).** For Phase 1: AlabOS requires hardware adaptation for non-A-Lab systems; MVP simulation outputs alone produce sufficient deliverables. For Phase 2: AlabOS production-grade, A-Lab has 41 demonstrated syntheses; AiiDA → LLM → AlabOS bridge "achievable with current tools." Active inference framing matters even Phase-1-only — "the most theoretically coherent insight in the document." Hardware-adaptation effort estimate not in briefs.

**4. Phase 0 Schema (EMMO-aligned vs proprietary).** For EMMO: ecosystem interoperability; future OPTIMADE coupling. For proprietary: "durable competitive asset" (Brief #2 Gap E). EMMO / MatML / OWL not addressed in briefs.

**5. Thermoelectrics vs Solid-State Batteries as MVP Wedge.** Batteries: largest immediate buyer universe (solid-state electrolyte $216.85M 2025 → $1,558.19M 2035 at 21.91% CAGR); CALPHAD sovereignty advantage uniquely visible; Brief #2 Gap H explicit on batteries with full competitor map. Thermoelectrics: "more complete computational chain (ZT fully predictable end-to-end) and a smaller, easier-to-serve research community as initial beachhead" (handover note); $600M market at 9% CAGR; phonon BTE intersectional signal strongest; LLM-extracted dataset (27,822 records, F1=0.909) already exists.

***

## Section F — Datasets and APIs catalogue

| Resource | Endpoint | Auth | Scale | Purpose | License |
|---|---|---|---|---|---|
| **Materials Project** | `next-gen.materialsproject.org/api` + OPTIMADE | API key (free) | 154K compounds, 530K calcs | Primary structural / property; pymatgen | CC-BY-4.0 |
| **OPTIMADE** | `optimade.materialsproject.org` + 15 providers | None | Federated query | v1.2 REST spec; `optimade-python-tools` | A (open standard) |
| **OQMD** | `oqmd.org/download` REST | None | 1.2M+ DFT calcs | Formation energy, stability | CC-BY-4.0 |
| **NOMAD** | `nomad-lab.eu` REST + OPTIMADE | None (reg. for AI Toolkit) | 15M+ calcs | All DFT properties; AI Toolkit Jupyter | CC-BY-4.0 |
| **AFLOW** | REST + AFLOWLIB | None | 3.5M+ compounds | Crystal/electronic/thermodynamic; AFLOW-ML | "Customised free access" |
| **JARVIS-DFT** | API + OPTIMADE; `jarvis.nist.gov` | None | 80K 3D + 1K 2D | 40+ properties incl. topological, thermoelectric; jarvis-tools | NIST public domain |
| **Alexandria** | `alexandria.icams.rub.de` + OPTIMADE | None | 4.5M+ structures | PBE + HSE; OMat24 derives from this | CC-BY-4.0 |
| **COD** | REST + bulk | None | 500K+ experimental | Experimental crystal structures | CC0 |
| **ICSD** | Commercial subscription | Paid | 300K+ experimental | Most complete experimental DB | D |
| **GNoME** | Via `matbench-discovery` | None | 2.2M structures (380K stable) | Generative reference | CC-BY (data); model proprietary |
| **OMat24** | `fairchem` | HuggingFace | 110M+ DFT calcs | MLIP training (primary inorganic) | CC-BY-4.0 |
| **OMol25** | `fairchem` / LBNL | HuggingFace | 100M+ molecular calcs | Electrolytes, biomolecules; UMA training | CC-BY-4.0 |
| **OC25** | Open Catalyst Project | None | Solid-liquid catalysis | Surface adsorption | CC-BY-4.0 |
| **AlabOS** | `github.com/CederGroupHub/alabos` | None (clone + MongoDB) | Production framework | Lab automation; 41 syntheses | A (MIT) |
| **MSTDB-TC** | NIST/ANL open | None | Molten salt fluorides | CALPHAD reference for MSR | Open |
| **LeMat-GenBench** | HuggingFace | None | 12-model evaluation | S.U.N. metric | Open |
| **LLM-curated TE** | GPT-4.1 Mini pipeline output | N/A | 27,822 records | ZT/Seebeck/κ training | Open |

***

## Section G — Stuck-point lookups flagged as missed

**1. LAMBench Corrections-Level Positioning.** Brief #2 Gap B presents rankings: DPA-3.1-3M #1, MACE-MPA-0 #8, MACE-MP-0 #10. UMA excluded due to license. Master tool table treats DPA-3 as ensemble partner only, not primary; cost-benefit threshold for DPA-3-only mode not specified. Starting points: LAMBench paper (Nature `s41524-025-01929-3`); DeePMD-kit v3 paper (arXiv 2502.19161); DPA-2 paper (Nature `s41524-024-01493-2`); Matbench Discovery inorganic-only segment.

**2. PennyLane + PySCF Integration Verification.** Brief #2 says build a PennyLane slot accepting a Hamiltonian "from PySCF or OpenFermion." 1-week estimate. Handover note: "References PennyLane + Qiskit Nature + PySCF integration as available but does not deliver a specific tutorial or workflow reference. For the 1-week estimate to be reliable, this needs verification before engineering starts." Starting points: PennyLane docs `pennylane.ai`; OpenFermion-PySCF bridge package; Qiskit Nature PySCF driver.

**3. Neural Operator Phase Field Starting Point.** Brief #2 says build FNO or DeepONet on phase field order parameters with CALPHAD-computed driving forces. PDEBENCH and NeuralPDE.jl cited. Handover note: "Identifies no specific repository or paper demonstrating a neural operator solving Allen-Cahn or Cahn-Hilliard equations for materials microstructure. PDEBENCH is a general scientific ML benchmark, not a materials phase field demonstration." Starting points: PDEBENCH (arXiv 2210.07182); NeuralPDE.jl docs; FNO original (Li et al., ICLR 2021); MICROSIM as classical comparison (arXiv 2404.01035).

***

## Section H — Pricing / productisation signals

- **MVP campaign:** "$50K–$250K per discovery campaign (analogous to CRO pricing in pharma)" (Brief #2 Gap H).
- **Competitor reference:** "Schrödinger Materials Science Suite — Closed, expensive (~$1M+/year enterprise)" (Brief #2).
- **Phase 0 unit cost:** "$0.01 per paper" via GPT-4.1 Mini; "$112 USD for 10,000 papers."
- **MLIP fine-tuning unit cost:** "100–500 configurations + 1–4 GPU-hours on A100" per system.
- **Throughput:** "~100,000 candidate compositions per day per A100" for formation energy/stability.
- **Full pipeline campaign:** "Full pipeline (one target property campaign, 100 candidates) — ~50–100 GPU-hours" (Brief #1).
- **Year-1 floor / year-3 ceiling:** **Not stated in briefs.** Recurring-subscription model not pinned down.
- **Commercial TDB:** "Thermo-Calc, ~USD 15,000/year" (Brief #1).
- **VASP:** "Academic licenses approximately EUR 5,000; commercial licenses separately priced" (Brief #1).

***

## Section I — Boundary and policy citations

- **UMA AUP exclusions (verbatim):** "military/warfare, ITAR-controlled applications, and weapons development. For energy materials and battery discovery applications this restriction is immaterial."
- **UMA geographic (verbatim):** "available via HuggingFace globally, except in comprehensively sanctioned jurisdictions, and in China, Russia, and Belarus." OFAC-comprehensively-sanctioned: North Korea, Iran, Cuba, Syria, Crimea/occupied territories. South Africa unrestricted.
- **UMA output ownership (verbatim):** "as between you and Meta, you are and will be the owner of such derivative works and modifications" — outputs fully owned by operator.
- **GNoME dataset:** Attribution required to Google DeepMind; not redistributable without attribution. Track in provenance metadata.
- **Thermo-Calc TDB:** "If obtained, these files cannot be redistributed or incorporated into open-source tools… Structure the L3 pipeline so that TDB files are read-only inputs, never embedded in distributed code."
- **DP-GEN LGPL v3:** "Active learning pipeline outputs (trained MLIP, generated training data) are fully owned by the operator. The DP-GEN code itself cannot be redistributed in a modified form without open-sourcing."
- **GPL outputs vs code (SPPARKS, BoltzTraP2, TeNPy):** Running these as computation tools and commercialising simulation outputs does not trigger GPL.
- **Provenance / data sovereignty:** **Not addressed in briefs.** Customer-data-rights schema not specified.

***

## Section J — Verbatim Combined Master Tool Selection Table

Brief #2 Section 3, reproduced verbatim. Supersedes Brief #1's Executive Map.

| Layer | Role | Tool | License Class | Zer0pa-Recommended? | Notes |
|-------|------|------|---------------|---------------------|-------|
| L1 | DFT (periodic) | Quantum ESPRESSO | A (GPL) | ✓ Primary | Best open-source periodic DFT; Python interface via AiiDA |
| L1 | DFT (molecular) | PySCF | A (Apache 2.0) | ✓ Primary | Best Python-native quantum chem; GPU support |
| L1 | DFT (high accuracy) | CP2K | A (GPL) | ✓ Alt | Gaussian/plane-wave; large-scale AIMD |
| L1 | DFT (academic) | VASP | C (commercial) | ✗ Avoid | Commercial; no outputs restriction but license cost; use QE instead |
| L1 | DFT (alt) | ABINIT | A (GPL) | Optional | DFPT phonons natively; useful for specific properties |
| L1 (QM) | Quantum computing | PennyLane | A (Apache 2.0) | ✓ Include slot | Build quantum slot now; activate on fault-tolerant hardware ~2030 |
| L1.5 | Phonon dispersion | Phonopy | A (BSD) | ✓ Primary | Harmonic force constants; integrates with QE, CP2K, MACE |
| L1.5 | Anharmonic phonon | Phono3py | A (BSD) | ✓ Primary | Lattice thermal conductivity; integrates with Phonopy |
| L1.5 | MLIP force constants | HiPhive | A (MIT) | ✓ Accelerator | 10-40x speedup for force constant calculation |
| L1.5 | Electronic transport | BoltzTraP2 | B (GPL) | ✓ Primary | Seebeck, σ from DFT band structure; outputs commercialisable |
| L1.5 | Electronic transport (alt) | AMSET | A (MIT) | ✓ Alt | Better for doped systems; defect scattering |
| L2 | Universal MLIP (primary) | MACE-MPA-0 | A (MIT) | ✓ Primary | Best inorganic materials generalizability; stable MD |
| L2 | Universal MLIP (ensemble) | DPA-3.1-3M | A (MIT) | ✓ Ensemble | #1 LAMBench overall; essential for cross-domain and uncertainty quantification |
| L2 | Universal MLIP (catalysis) | Meta UMA | E (FAIR Chem Lic v1) | ✓ Include | Not restricted for ZA; best for catalysis/molecules; needs Acceptable Use compliance |
| L2 | MLIP (molecules) | MatterSim-v1 | A (MIT) | Optional | Strong across domains; slower than MACE |
| L2 | Active learning | MACE committee / DP-GEN | A (MIT) | ✓ Primary | MACE multi-head committees for MLIP uncertainty; DP-GEN for DeePMD workflows |
| L2 | Fine-tuning substrate | e3nn | A (MIT) | ✓ Substrate | Mathematical foundation for all equivariant MLIP work |
| L3 | CALPHAD computation | pycalphad | A (MIT) | ✓ Primary | Python CALPHAD engine; reads TDB files |
| L3 | TDB fitting | ESPEI | A (MIT) | ✓ Primary | Bayesian TDB parameter fitting; production-ready for ≤5 components |
| L3 | MLIP-to-CALPHAD | PhaseForgePlus | A (MIT) | ✓ Bridge | Bridges MLIP thermodynamics to CALPHAD; new 2025 tool |
| L3 | TDB (commercial) | Thermo-Calc TCNI/TCTI | D | Conditional | Acquire only for Ni/Ti superalloy projects with defined delivery timeline |
| L4 | Phase field (classical) | PRISMS-PF | A (LGPL) | ✓ Primary | Production-grade; GPU support; Allen-Cahn / Cahn-Hilliard |
| L4 | Phase field (multi-physics) | MOOSE/MARMOT | A (LGPL) | ✓ Primary | Multiphysics coupling; nuclear/structural validated |
| L4 | Phase field + CALPHAD | MICROSIM | A (MIT) | ✓ Alt | Open-source; CALPHAD-coupled; GPU/CPU; 2024 |
| L4 | Neural operator (future) | FNO/DeepONet (custom) | A (MIT) | ✓ Build target | Replace PINN-MPF; neural operator phase field is the 2026 gap |
| L5 | FEM (general) | FEniCSx | A (LGPL) | ✓ Primary | Modern successor to FEniCS; Python-native; GPU support |
| L5 | FEM (structured) | deal.II | A (LGPL) | ✓ Alt | Adaptive refinement; excellent for structural mechanics |
| L5 | CFD | OpenFOAM | B (GPL) | ✓ Primary | Industry-standard CFD; outputs commercialisable |
| L6 | Crystal generation | MatterGen | A (MIT) | ✓ Primary | Conditional generation; 2x+ SUN vs prior models; DFT validation mandatory |
| L6 | Crystal generation (alt) | DiffCSP | A (MIT) | ✓ Alt | Complementary novelty profile; use alongside MatterGen |
| L6 | Crystal generation (LLM) | CrystaLLM | A (MIT) | Optional | Text-to-structure; useful for literature-informed generation |
| L6 | Hypothesis generation | GNoME dataset | A (CC-BY) | ✓ Dataset | 380K stable structures for screening reference |
| L6 | Phase 0 (literature mining) | GPT-4.1 Mini + LangGraph | D (API) | N/A | F1=0.889 for property extraction; $0.01/paper at scale |
| L6 | Phase 0 (structure desc.) | Robocrystallographer | A (MIT) | ✓ Include | CIF → text description for LLM context |
| L6 | Phase 0 (NER) | MaterialsBERT | A (Apache 2.0) | ✓ Include | 300K+ property records; abstract-level NER |
| L7 | Workflow orchestration | AiiDA | A (MIT) | ✓ Primary | Provenance-tracked scientific workflow engine |
| L7 | High-throughput workflows | Atomate2 | A (MIT) | ✓ Primary | Pre-built materials workflows; plugs into AiiDA |
| L7 | Bayesian optimisation | BoTorch + Ax | A (MIT) | ✓ Primary | State-of-art Bayesian optimisation; multi-fidelity support |
| L7 | Database interop | OPTIMADE | A (spec) | ✓ Primary | Query unified API across Materials Project, AFLOW, JARVIS |
| L7 | Lab automation | AlabOS | A (MIT) | ✓ Include | UC Berkeley A-Lab OS; solid-state synthesis; production-grade |
| L7 | Tensor networks | ITensor / TeNPy | A/B (MIT/GPL) | ✓ Include | For strongly correlated systems where DFT fails |
| Data | Primary structural | Materials Project (API) | A (CC-BY) | ✓ Primary | 153K+ structures; formation energies; stability data |
| Data | High-throughput DFT | OMat24 | A (CC-BY 4.0) | ✓ Primary | 110M+ DFT calculations; MLIP training data |
| Data | Molecular | OMol25 | A (CC-BY) | ✓ Include | 100M+ molecular DFT calculations; organic/drug-like |
| Data | Catalysis | OC25 | A (CC-BY) | ✓ Include | Surface adsorption; heterogeneous catalysis |
| Data | Generative reference | GNoME (DeepMind) | A (CC-BY) | ✓ Include | 2.2M stable structures for generative model evaluation |
| Data | Thermoelectrics | LLM-curated TE dataset | A (open) | ✓ Include | 27,822 records from GPT-4.1 Mini pipeline |

*License Classes (Brief #2 verbatim): A = MIT/Apache/BSD/Public Domain — free commercial use; B = GPL/LGPL — outputs commercialisable, tool code is copyleft; C = Academic-only — negotiated commercial license required; D = Commercial paid; E = Custom/ambiguous — outputs commercialisable, specific restrictions apply.*

***

## Section K — What I noticed but the briefs did NOT explicitly cover

1. **Atomate2 license mismatch.** Brief #1 lists Apache 2.0; Brief #2 master table marks MIT (A). Neither flags this. Lead agent should verify against the GitHub repo.

2. **No structured-knowledge-layer (EMMO / MatML / OWL) coverage.** Handover note flags this; the briefs themselves do not name a recommendation. Phase 0's LLM extraction → unstructured property records does not address: formal ontology choice, OPTIMADE coupling pathway, or whether the materials knowledge graph is EMMO-aligned. Decision-4-shaped hole.

3. **The 7→3 layer collapse is not in the briefs.** Brief #2 names variational unification (Gap G intersectional signal) but stops at observation. The architectural reframe — that all seven layers reduce to (Knowledge / Variational Solver / Active Inference Loop), a marketing-grade primitive — is fresh-eyes territory, not load-bearing in the briefs.

4. **Customer data-rights / IP / sovereignty schema absent.** Neither brief specifies who owns: customer chemistry inputs, DFT outputs computed on customer chemistry, MLIP fine-tune weights for customer-specific systems, ESPEI parameter posteriors, or audit logs. This determines whether the moat compounds or evaporates. Missing entirely.

5. **Polymer / soft-matter Phase-1 / Phase-2 boundary.** Brief #1 notes polymers as "Phase 2" with no specific gating. Whether MACE-OFF24 (Brief #1, MIT, molecular MLIP) is Phase 1 or Phase 2 is unstated.

6. **Cross-domain MLIP transfer (crystal ↔ protein) is gestured at only.** Brief #2 Gap F notes 2025 papers on ESM-2 → crystal MLIP transfer but does not name a specific protocol for re-using L2 foundation across materials and pharma workstreams. "One foundation, many readouts" not operationalised.

7. **OMol25-vs-OMat24 selection rule for materials pipeline is undefined.** Handover note: OMol25 "appears in the master table's Data section but was not covered in any of the eight gaps." When an L2 pipeline should pull from OMol25 vs OMat24 — particularly for battery electrolyte work where the molecular-organic boundary matters — is not specified.

8. **MatSciBench reasoning-gap moat (Brief #1 §5.7) not picked up by Brief #2.** Brief #1: "no GPT-Rosalind equivalent for materials science… A fine-tuned model on MatSciBench + JARVIS + Materials Project knowledge would outperform any current general-purpose model." Whether Zer0pa builds a materials-specific reasoning model is unstated in Brief #2.

9. **No falsifier discipline at L4 / L5.** Cross-model disagreement is named at L1 (functionals), L2 (DPA-3 vs MACE), L3 (ESPEI MCMC), L6 (LeMat-GenBench). At L4 (PRISMS-PF vs MOOSE) and L5 (FEniCSx vs deal.II) the briefs do not specify a cross-validation primitive even though it is structurally analogous.

10. **The Phase 0 → L6 hand-off schema.** Phase 0 produces structured property records; L6 generative models accept property + chemical-system constraints. The briefs do not specify how Phase 0 outputs become L6 inputs (JSON? OPTIMADE? proprietary?), how LLM-extracted property posteriors propagate uncertainty into MatterGen's conditioning, or whether the literature prior seeds the generative model or only post-filters.
