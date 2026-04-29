# In Silico Materials Science: Corrections, Augmentations, and Extended Architecture — Brief #2

**Companion to Brief #1 | Zer0pa / Frontier AI Orchestration Lab | April 2026**

***

## How to Use Brief #2

Brief #1 produced a broad, high-quality first-pass survey of the seven-layer multi-scale materials simulation pipeline. This document corrects four specific claims that required verification, fills eight technical gaps absent from Brief #1, and supersedes the Brief #1 Executive Map with a combined master tool selection table. Read Brief #1 for pipeline context and layer architecture; use this document to patch it. Specific cross-references to Brief #1 sections are given wherever a correction or addition directly modifies prior content. The intersectional signal sections are written for Zer0pa's orchestration-native, physics-first perspective and are intended to surface the precise mathematical connections that give the lab competitive framing over domain-native players.

***

## Section 1: Corrections and Verifications

### Issue 1 — Meta UMA Geographic License Restrictions

**Brief #1 claim:** Meta UMA carries geographic and acceptable-use restrictions that may apply from Sandton, South Africa. Flagged as Class A† with a license review warning.

**Verdict: Flag is overstated. South Africa is not a restricted territory. UMA is usable with standard compliance. Recommended license re-classification: Class E (custom FAIR Chemistry License v1 — commercially usable with Acceptable Use Policy constraints).**

The actual license governing UMA model weights is the **FAIR Chemistry License v1** (last updated May 14, 2025). This is emphatically not the same as the MIT license covering the `fairchem` library code; Brief #1's implied conflation of the two is the source of the ambiguity. The weights are explicitly governed by a separate custom license, accessed at the HuggingFace model card for `facebook/UMA`.[^1][^2]

The geographic restriction is stated precisely in the model card: **"UMA is available via HuggingFace globally, except in comprehensively sanctioned jurisdictions, and in China, Russia, and Belarus."** South Africa does not appear on any restricted territory list. The restriction applies only to OFAC-comprehensively-sanctioned countries (North Korea, Iran, Cuba, Syria, Crimea/occupied territories) and the three explicitly named jurisdictions. Accessing UMA from Sandton, South Africa requires only standard HuggingFace account registration and acceptance of the FAIR Chemistry License v1 terms.[^1]

The license grants "a non-exclusive, worldwide, non-transferable, and royalty-free limited license... to use, reproduce, distribute, copy, create derivative works of, and make modifications to the Materials." Critically for Zer0pa's commercial output model, the license states: "as between you and Meta, you are and will be the owner of such derivative works and modifications" — confirming that computational outputs (simulation results, predicted properties, discovered materials) are fully owned by the operator, not Meta. The Acceptable Use Policy prohibits military/warfare, ITAR-controlled applications, and weapons development. For energy materials and battery discovery applications this restriction is immaterial.[^1]

**Correction to apply to Brief #1 Executive Map:** Replace the Class A† classification and geographic warning with: *Class E (FAIR Chemistry License v1, custom). Commercial output rights confirmed. Geographic restriction applies only to China, Russia, Belarus, and comprehensively sanctioned jurisdictions. South Africa (ZA) is unrestricted. Acceptable Use Policy bars ITAR/weapons applications. Re-assess only if pipeline is applied to nuclear or defense-adjacent materials.*

***

### Issue 2 — MatterGen Novelty Validation Caveat

**Brief #1 claim:** An April 2026 preprint notes that a significant fraction of MatterGen "novel" structures correspond to training data compounds predicted in different representations.

**Verdict: Partially Correct. The LeMat-GenBench evaluation framework (December 2025, NeurIPS 2025) documents the stability-novelty tradeoff in principled quantitative terms. The precise April 2026 preprint described in Brief #1 most closely matches the ScienceDirect paper "Are diffusion models ready for materials discovery in unexplored spaces?" (April 2026), which compares MatterGen and DiffCSP novelty metrics against a broader chemical space definition. The core caveat is confirmed but the framing is more nuanced than Brief #1 implies.**

**LeMat-GenBench** (December 2025, open-source benchmark suite on HuggingFace with NeurIPS 2025 workshop presentation) is the most rigorous independent evaluation of crystal generative models and the primary source for this correction. It introduces a unified S.U.N. (Stability, Uniqueness, Novelty) metric framework and benchmarks 12 recent generative models. Its central finding is directly relevant: *"an increase in stability leads to a decrease in novelty and diversity on average, with no model excelling across all dimensions."* This is the quantitative basis for the novelty caveat in Brief #1.[^3][^4]

Novelty in LeMat-GenBench is defined using structural fingerprinting against reference databases; a structure is "novel" only if its fingerprint does not match any structure in the training distribution. The April 2026 ScienceDirect paper "Are diffusion models ready for materials discovery in unexplored spaces?" extends this critique: when evaluation is conducted against a broader chemical space definition than the MP-20 benchmark (the standard evaluation set), the effective novelty of pretrained MatterGen outputs is substantially lower than the headline SUN score suggests. This is not about identical duplicates — it is about structural representation equivalence at the fingerprint level, which is precisely the caveat Brief #1 describes.[^5][^6]

Quantitatively, the limitation is best described as: the headline MatterGen SUN rate (which exceeds prior generative models by 2x+ on the MP-20 benchmark) does not transfer uniformly to unexplored chemical spaces. Novelty relative to training data is a function of how broadly the reference space is defined. For Zer0pa's use case — discovering solid-state electrolyte compositions outside the dense MP-20 coverage zone — this means the pipeline should always include DFT stability verification at L1 after L6 generation, which Brief #1 already recommends. The caveat does not invalidate MatterGen as an L6 tool; it confirms the necessity of the DFT validation step that Brief #1 already specifies as mandatory.[^7][^8]

No public patch or model update from Microsoft Research addressing this limitation was found as of April 2026. DiffCSP shows similar stability-novelty tradeoffs in independent evaluation.[^9][^10]

**Correction to apply to Brief #1:** Add to the MatterGen tool description: *"Novelty ratings are benchmark-dependent. On MP-20, SUN scores exceed prior models by 2x. On broader chemical space definitions, effective novelty is lower. DFT validation at L1 is non-optional and handles this. The LeMat-GenBench leaderboard (HuggingFace, open) is the current standard for tracking generative model novelty."* No change to tool selection recommendation.

***

### Issue 3 — PINNs-MPF Production Status

**Brief #1 claim:** PINNs-MPF (SFETNI/PINNs_MPF, GitHub) is a research code, not production-grade. Flagged as a strategic build/contribute target.

**Verdict: Confirmed — still research-only. Additionally: the broader community is moving toward neural operator architectures (FNO, DeepONet) rather than PINNs for phase field problems. The "build or contribute" recommendation should be updated to reflect this architectural shift.**

The SFETNI/PINNs_MPF repository remains an early-stage research codebase. No production-grade successor implementing Allen-Cahn or Cahn-Hilliard equations via PINNs as a deployable Python library was found in the 2024–2026 literature search. The MICROSIM solver (2024) provides an open-source phase field stack with CALPHAD coupling for real alloys, but is based on classical numerical methods rather than PINNs.[^11]

Critically, the field appears to be converging on a different architectural approach. The 2025–2026 literature demonstrates that **neural operator** methods — Fourier Neural Operators (FNO) and DeepONet — are better positioned than PINNs for solving phase field PDEs at scale. Neural operators learn the operator mapping between function spaces directly, rather than embedding PDE residuals as loss terms; this is both computationally faster and more generalizable to new initial/boundary conditions. The PDEBENCH benchmark demonstrates this gap. NeuralPDE.jl (Julia) supports both PINNs and neural operators with a unified interface, and is actively maintained, but is not yet a production-grade drop-in for materials phase field simulation.[^12]

**Updated recommendation:** Reframe the Brief #1 "build PINNs-MPF successor" directive as *"build or contribute to a neural operator phase field solver with CALPHAD coupling."* The target architecture is FNO or DeepONet operating on phase field order parameters, with CALPHAD-computed driving forces as operator inputs. This is the open gap in the 2026 toolchain.

***

### Issue 4 — The CALPHAD TDB Database Bottleneck: Is ML-CALPHAD a Bypass?

**Brief #1 claim:** Acquiring commercial TDB databases (Thermo-Calc TCNI, TCTI, Class D) is "the single most impactful commercial investment for Layer 3."

**Verdict: Partially Correct. The bottleneck is real and the commercial TDB investment remains justified for immediate production use on well-studied alloy systems. However, two developments since Brief #1 significantly reduce the strategic urgency of that investment: (1) the maturation of ESPEI for 3–5 component systems, and (2) PhaseForgePlus (2025), an open-source MLIP-to-CALPHAD pipeline that bypasses experimental TDB data for some systems.**

ESPEI (MIT, NIST) uses Bayesian MCMC to fit CALPHAD Gibbs energy parameters to thermochemical and phase boundary data from DFT and experiment. It is production-ready for binary and ternary systems, demonstrated end-to-end on systems including the Cu-Mg binary and molten salt fluoride systems (LiF-NaF-KF) for nuclear applications. The Cu-Mg workflow (DFT → ESPEI → pycalphad-readable TDB → phase diagram) is fully documented in ESPEI's official tutorial. For 4–5 component systems (battery cathode-relevant), ESPEI is functional but requires substantially more DFT supercell calculations and experimental calibration data; the computational cost scales steeply with component count.[^13][^14][^15]

**PhaseForgePlus** (2025, fully open-source, MIT equivalent) integrates MLIPs (via the ATAT framework) directly into CALPHAD parameter generation for alloy systems. Demonstrated on the Pt-W binary system, PhaseForgePlus shows that ML potential-computed thermodynamic data can replace most experimental input, with only minor gradient-informed adjustments needed for phase diagram accuracy. The companion PhaseForge workflow (June 2025) extends this to multi-component alloy phase diagram mapping.[^16][^17][^18]

**Open TDB availability (April 2026 survey):**
- *Li-Mn-Ni-Co-O battery cathode systems:* No comprehensive open TDB covering all relevant phases exists. Partial open thermodynamic data is available in the literature and Materials Project, but not assembled into a CALPHAD-compatible TDB.
- *Al alloys (Al-Cu-Mg-Zn-Si):* Partial open TDB data exists in ESPEI's example datasets and NIST publications; not production-quality for all six-component system.
- *Fe-Ni-Cr stainless steel:* Partial coverage in OpenCalphad demonstration databases; insufficient for precision alloy design.
- *High-entropy alloys (five-component equimolar):* Essentially no open TDB for commercially relevant HEA systems.

The absence of a curated open TDB repository analogous to Materials Project for crystal structures is confirmed. The CALPHAD community's proprietary database model remains deeply entrenched.[^19][^20][^21]

**Revised verdict:** The Brief #1 assessment holds for immediate commercial deployment on standard alloy systems. For the Zer0pa battery materials MVP, the revised strategy is: use PhaseForgePlus + ESPEI for novel compositions where no TDB exists; acquire commercial TCNI/TCTI TDB for existing Ni/Ti alloy systems only if those sub-domains are explicitly targeted. For Li-ion battery cathode systems (Li-Mn-Ni-Co-O), neither open nor commercial CALPHAD databases are adequate without custom ESPEI fitting from DFT data — a conclusion that actually favors the Zer0pa orchestration approach over competitors who rely on off-the-shelf TDB files.

***

## Section 2: New Technical Additions — Gaps A through H

***

### Gap A: The Phonon Simulation Stack (L1.5 — Thermal and Transport Properties)

**Current State:** A complete, fully open-source chain for predicting thermoelectric figure of merit (ZT) from crystal structure exists, spanning DFT → Phonopy → Phono3py → BoltzTraP2 → ZT calculation. The chain is documented, functional, and increasingly accelerated by MLIPs. The weakest link in 2026 is not the tooling but the accuracy of force constant calculations for strongly anharmonic materials (SnSe, Bi₂Te₃), where MLIP shortcuts are fastest but DFT remains more accurate. The most promising 2026 development is the EquiformerV2-OAM model outperforming all other universal potentials on phonon property benchmarks for inorganic materials.

| Tool | Version | License Class | Python API | GPU Support | Commercial Output Rights | Key Limitation |
|------|---------|---------------|------------|-------------|--------------------------|----------------|
| Phonopy | v2.26+ | A (BSD) | Yes (phonopy.load) | Via MLIP backend | Yes | Harmonic only; requires DFT/MLIP displacements |
| Phono3py | v2.7+ | A (BSD) | Yes (phono3py.load) | Via MLIP backend | Yes | Supercell count scales as N³; expensive for large unit cells |
| HiPhive | v1.4+ | A (MIT) | Yes (pip install hiphive) | Via MLIP backend | Yes | Accuracy depends on training data coverage |
| BoltzTraP2 | v22.12+ | B (GPL) | Yes (Python CLI) | CPU only | Yes (outputs) | Requires accurate DFT band structure; no ML shortcut |
| AMSET | v0.4+ | A (MIT) | Yes | CPU | Yes | Better than BoltzTraP2 for defect scattering but slower |

**Phonopy** integrates with Quantum ESPRESSO, CP2K, VASP, LAMMPS (via phonoLAMMPS), and all major MLIPs via ASE calculator interface. It computes harmonic force constants from finite displacement supercell calculations and produces phonon dispersion curves, thermodynamic functions, and PDOS. Output formats include FORCE_CONSTANTS files that Phono3py, HiPhive, and ShengBTE can consume.[^22][^23]

**Phono3py** computes anharmonic third-order force constants, phonon-phonon scattering rates, and lattice thermal conductivity. For a 10-atom unit cell, typical DFT supercell calculations number in the hundreds; MLIP-accelerated displacement forces reduce this by an order of magnitude. For canonical thermoelectrics, Phono3py-predicted thermal conductivities are within 20–30% of experiment for well-studied systems (Si, GaAs, SiC). For complex thermoelectrics with strong anharmonicity (SnSe), the error can reach 50–100%.[^24][^25]

**MLIP-accelerated phonons:** The September 2025 benchmark by Peng et al. evaluates six universal MLIPs (EquiformerV2, MatterSim, MACE, CHGNet) on 2,429 crystalline materials for phonon properties. **EquiformerV2 pre-trained on OMat24 shows the strongest performance in atomic force prediction for displaced supercells; its fine-tuned counterpart consistently outperforms all models for second-order IFC, lattice thermal conductivity, and phonon properties generally.** MACE-MP-0 zero-shot achieves thermal conductivities compatible within a factor of two of DFT-PBE values for 69% of materials in the phononDB-PBE database. The HiPhive-accelerated approach (replacing DFT displacements with MLIP forces) reduces compute cost by an order of magnitude, from ~480,000 CPU-hours to ~12,000 CPU-hours for a 220-material ternary benchmark, preserving accuracy within 10%.[^26][^27][^25]

**BoltzTraP2** computes electronic transport coefficients (Seebeck coefficient, electrical conductivity) from DFT band structures via Boltzmann transport theory. It connects to Phonopy output for combined thermal + electronic transport analysis. The full ZT prediction chain (DFT → Phonopy → Phono3py → κ_L → BoltzTraP2 → σ, S → ZT) is documented in several high-throughput thermoelectric screening papers.[^28][^29]

**Direct ML prediction of ZT (2025–2026):** XGBoost and GNN-based models now predict ZT, Seebeck coefficient, and thermal conductivity directly from structural descriptors for specific material classes (skutterudites, chalcogenides). For skutterudites, XGBoost achieves accurate temperature-dependent ZT prediction with substantially lower compute cost than the full DFT chain. GPT-4.1-based LLM extraction pipelines have curated 27,822 thermoelectric property records from ~10,000 papers (F1 ≈ 0.91 for ZT extraction), providing training data for these direct prediction models.[^30][^31][^29]

**Weakest link in the ZT chain (2026):** Three bottlenecks limit accuracy: (1) anharmonic force constants for materials with complex phonon-phonon scattering (SnSe, PbSe); (2) the BoltzTraP2 band structure rigid-band approximation breaks down for heavily doped systems; (3) grain boundary and defect contributions to thermal resistivity are absent from all first-principles models. The last point is particularly significant: real ZT values in polycrystalline materials often differ by 30–50% from single-crystal predictions.

**Intersectional Signal — Phonon Cellular Automata:** Phonon dispersion is the normal mode decomposition of a coupled harmonic oscillator lattice — which is formally a linear cellular automaton in the thermodynamic limit. The phonon Brillouin zone is the dual space of the real-space lattice automaton, and the phonon group velocity is the information propagation speed of the corresponding rule space. More precisely: the lattice thermal conductivity predicted by the phonon Boltzmann Transport Equation (BTE) is a statement about information flow in a noisy discrete network — each phonon mode is a channel with a finite mean free path (information decay length). The BTE is mathematically equivalent to a master equation for a discrete-time information-theoretic channel with scattering as a noise operator. Zer0pa's information theory and cellular automata competencies translate directly: Shannon channel capacity maximisation over phonon mode space is a formally valid reformulation of the problem of maximising thermal conductivity. The dual problem — minimising thermal conductivity for thermoelectric applications — is channel capacity suppression via structured noise injection (defect engineering, alloying). This is not a metaphor; it is a direct mathematical correspondence between the phonon BTE and the discrete information flow equations the lab already works with.

**Strategic Recommendation:** Implement the Phonopy → Phono3py chain as a standard L1.5 subpipeline for thermal property prediction. Use MACE-MP-0 or EquiformerV2 forces for initial high-throughput screening (factor-of-magnitude speed gain), then DFT-recalculate force constants only for top-ranked candidates. BoltzTraP2 is Class B (GPL outputs commercialisable); AMSET (MIT) is the preferred alternative for doped thermoelectrics. Include a BoltzTraP2 → ZT calculation node as a standard L1.5 output.

***

### Gap B: DeePMD-kit and the Deep Potential Ecosystem

**Current State:** DeePMD-kit v3 (released November 2024, paper published May 2025) is a mature, MIT-licensed MLIP framework with multi-backend support (TensorFlow, PyTorch, JAX, PaddlePaddle). The DPA-3 model (DPA-3.1-3M) ranks #1 overall on the LAMBench leaderboard (August 2025, the most comprehensive multi-domain MLIP benchmark), outperforming MACE-MPA-0 across all three evaluated domains — Inorganic Materials, Molecules, and Catalysis. This is the most significant finding for the Brief #1 MLIP selection rationale: the exclusive focus on MACE-class models should be broadened to include the DPA architecture.[^32][^33][^34][^35]

| Tool | Version | License Class | Python API | GPU Support | Commercial Output Rights | Key Limitation |
|------|---------|---------------|------------|-------------|--------------------------|----------------|
| DeePMD-kit | v3.1+ | A (MIT) | Yes (pip install deepmd-kit) | Yes (CUDA) | Yes | More complex setup than MACE; older descriptor-based architecture less expressive than equivariant |
| DPA-2.4-7M | Universal | A (MIT weights) | Via DeePMD-kit | Yes | Yes | Catalysis domain lags DPA-3 |
| DPA-3.1-3M | Universal | A (MIT weights) | Via DeePMD-kit | Yes | Yes | DPA-3 in active development; stability slightly lower than MACE |
| DP-GEN | v0.11+ | A (LGPL) | Yes | Via MLIP | Yes (outputs) | Tightly coupled to DeePMD; partial support for other MLIPs |

**LAMBench Rankings (Table 2, benchmark against 10 models, released January 2026):**[^33]
- DPA-3.1-3M: FF generalizability 0.175 (**rank 1**), property generalizability 0.322 (**rank 1**)
- DPA-2.4-7M: FF 0.241 (**rank 3**), property 0.342 (**rank 2**)
- MACE-MPA-0: FF 0.308 (**rank 8**), property 0.425 (**rank 7**)
- MACE-MP-0: FF 0.351 (**rank 10**), property 0.472 (**rank 9**)

DPA-3.1-3M's dominance is attributed to multi-task training across 31 datasets spanning all three domains. In the Inorganic Materials domain specifically, the ordering follows the Matbench Discovery leaderboard: SevenNet-MF-ompa < GRACE-2L-OAM < DPA-3.1-3M, while for Molecules and Catalysis (cross-domain), DPA-3.1-3M outperforms all competitors. The UMA models were **excluded from LAMBench evaluation due to licensing restrictions** — the FAIR Chemistry License v1 is cited as a barrier to benchmark inclusion.[^35][^33]

**DPA-2 architecture** (introduced 2024) uses a multi-task pretraining strategy with a transformer-based attention descriptor, moving the DeePMD family from purely descriptor-based invariant representations toward a partially attention-based architecture. DPA-3 extends this further. Both are trained on the OpenLAM dataset (curated by the DeepModeling community, MIT license).[^36][^37]

**Descriptor-based vs. equivariant architectures:** MACE's explicit E(3) equivariant message-passing achieves higher accuracy per parameter for inorganic materials but requires more compute per forward pass. DPA/DeePMD's attention-based descriptor is faster at inference but captures symmetry more implicitly. The LAMBench results suggest this distinction is collapsing at scale: DPA-3's multi-domain generalizability now exceeds equivariant MACE at the universal model level, while MACE-OFF23 retains superiority for organic molecules specifically. The principled answer for Zer0pa: **run both in ensemble for uncertainty quantification on high-value candidates.** The disagreement between DPA-3 and MACE-MPA-0 predictions is a direct signal of epistemic uncertainty about that candidate's energy landscape.[^33]

**DP-GEN** (active learning for iterative MLIP training) is tightly coupled to DeePMD-kit but supports basic LAMMPS and CP2K interfacing; it is not architecture-agnostic. MACE's built-in multi-head committee uncertainty quantification (December 2025) is a more modern alternative for MACE-based active learning.[^38][^33]

**Integration:** DeePMD-kit v3 integrates with GROMACS for MD (February 2026, enabling AB initio quality MD at molecular dynamics scale). Both DeePMD and MACE can be used as ASE calculators, enabling drop-in substitution in AiiDA workflows.[^39][^40]

**Intersectional Signal — Descriptor as Sufficient Statistics:** The descriptor-based approach compresses local atomic environments into invariant feature vectors before energy prediction. This is formally the problem of finding sufficient statistics for the energy given the local configuration — precisely the information-theoretic concept of sufficient statistics for an exponential family model. A descriptor is sufficient if it preserves all the mutual information between local structure and energy that is relevant for prediction. The equivariant architecture (MACE) achieves sufficiency by a different route: rather than computing an invariant compression, it propagates the full tensor field and lets the network learn the invariant subspace. The information-theoretic argument for why equivariant architectures should theoretically outperform descriptor-based ones is: they do not discard any symmetry-related information during the compression step — they process the full irreducible representation decomposition of the local geometry before projecting to a scalar energy. In practice, at sufficient model capacity and training data, this theoretical advantage narrows. The LAMBench results confirm this empirically: DPA-3's attention mechanism achieves comparable generalizability to MACE-MPA-0 at the universal model level by compensating with broader training data diversity.

**Strategic Recommendation:** Add DPA-3.1-3M alongside MACE-MPA-0 as co-equal L2 options in the pipeline. Run both on every candidate above the L6 generation threshold; use their energy disagreement as the primary uncertainty quantification signal for prioritising L1 DFT recalculation. DeePMD-kit v3's multi-backend support (JAX, PyTorch) aligns well with the lab's stack.

***

### Gap C: ESPEI and the Path to CALPHAD Database Sovereignty

**Current State:** A fully open-source path from DFT data to production CALPHAD TDB now exists and is partially demonstrated. ESPEI (MIT) is production-ready for binary and ternary systems. PhaseForgePlus (2025, MIT-equivalent) bridges the gap between MLIPs and CALPHAD parameter fitting. For 4–6 component battery systems, the open-source path is viable but requires significant DFT compute investment; there is no shortcut for first-of-kind quaternary systems.

| Tool | Version | License Class | Python API | GPU Support | Commercial Output Rights | Key Limitation |
|------|---------|---------------|------------|-------------|--------------------------|----------------|
| ESPEI | v0.8+ | A (MIT) | Yes (pip install espei) | No | Yes | Data-hungry for >3 components; accuracy below commercial TCNI for Ni superalloys |
| pycalphad | v0.10+ | A (MIT) | Yes | No | Yes | Reads TDB files; depends on quality of thermodynamic data |
| DFTTK | v0.4+ | A (MIT) | Yes | No | Yes | Low maintenance activity in 2025–2026; VASP-centric |
| PhaseForgePlus | v0.1 (2025) | A (MIT) | Yes | Via MLIP backend | Yes | Demonstrated only on binary Pt-W; multi-component validation limited |
| PhaseForge | 2025 | A (MIT) | Yes | Via MLIP backend | Yes | Extends PhaseForgePlus to multi-component |

**ESPEI** uses Bayesian MCMC with pycalphad as the thermodynamic backend. The Cu-Mg end-to-end workflow (DFT first-principles → ESPEI parameter fitting → pycalphad TDB) is the canonical published demonstration. For the Cu-Mg binary, ~50–100 DFT configurations provide adequate training data. For a ternary system, the dataset requirement scales to ~200–500 configurations. For a quaternary (Li-Mn-Ni-Co) with multiple competing phases, the requirement is estimated at 1,000–5,000 DFT calculations — substantial but feasible via MLIP-accelerated pre-screening. ESPEI's Bayesian uncertainty quantification propagates DFT input uncertainty into output CALPHAD parameter distributions, which is directly useful for the lab's BoTorch active learning layer.[^41][^15][^13]

**PhaseForgePlus** (2025, GitHub: `dogusariturk/PhaseForgePlus`) integrates MLIPs into the ATAT (Alloy Theoretic Automated Toolkit) framework for Gibbs energy calculation, then feeds these into CALPHAD parameter fitting using a Jansson derivative gradient method. Demonstrated on Pt-W, it shows that MLIP-computed thermodynamic data (replacing most DFT) can produce physically-grounded Gibbs energy descriptions requiring only minimal experimental calibration. The PhaseForge wrapper extends this to multi-component alloy phase diagram mapping (June 2025).[^17][^18][^16]

**Open TDB availability (April 2026):** The survey confirms the absence of a curated open TDB repository comparable to Materials Project. The MSTDB-TC (Molten Salt Thermodynamic Database, open-access, NIST/ANL) covers nuclear molten salt systems (LiF-NaF-KF and related fluorides) and is used with ESPEI for MSR applications. For the battery cathode space (Li-Mn-Ni-Co-O), the Materials Project contains formation energy data covering individual binary and ternary sub-systems, and these can be used as ESPEI input — but no pre-assembled quaternary TDB file exists in open repositories.[^14]

**ML-CALPHAD (2025–2026):** The Construction and Tuning paper (Springer, 2025) demonstrates that MLIPs can reduce the DFT calculation burden for CALPHAD parameter fitting by ~10x for binary/ternary systems. No published demonstration achieves accuracy comparable to commercial Thermo-Calc databases for 5+ component industrially critical systems. For novel compositions outside the commercial database coverage zone, ML-CALPHAD is the only available path.[^16]

**Intersectional Signal — Information Geometry and CALPHAD:** The CALPHAD optimisation problem — fitting Gibbs energy functional parameters to reproduce observed phase boundaries — is formally an instance of fitting an exponential family statistical model. The Gibbs energy of a CALPHAD phase is an expression of the form \( G = \sum_i x_i \mu_i + RT\sum_i x_i \ln x_i + G^{xs} \), where the excess term \(G^{xs}\) is parameterised by Redlich-Kister polynomials. This is precisely the structure of a natural exponential family, with the composition variables \(x_i\) as natural parameters and the Gibbs energy as the log-partition function. The ESPEI Bayesian MCMC fitting procedure is therefore navigating the **information geometry of the thermodynamic state space** — following geodesics in the curved manifold of the exponential family. This is not a metaphor: the Fisher information metric on the CALPHAD parameter space determines the efficiency of ESPEI's MCMC sampling. Zer0pa's prior work in information theory maps directly onto optimising the ESPEI sampling algorithm — natural gradient MCMC on the thermodynamic manifold could substantially improve convergence for multi-component systems relative to ESPEI's current flat-space sampler.[^42]

**Strategic Recommendation:** Build the DFT → ESPEI → pycalphad pipeline as the standard L3 implementation. Use PhaseForgePlus as the MLIP bridge for initial parameter estimation. Acquire commercial TCNI/TCTI only if Zer0pa takes on a Ni/Ti superalloy project with immediate delivery timelines. For battery cathode systems, the open-source path is the only viable one regardless of budget — a strategic advantage since competitors using off-the-shelf TDB files cannot model novel quaternary compositions.

***

### Gap D: Autonomous Laboratory Hardware-Software Interface

**Current State:** The software infrastructure for closed-loop materials discovery labs is more mature than Brief #1 implies. AlabOS (UC Berkeley, MIT license, open-sourced 2024) is the leading production-grade framework for autonomous solid-state synthesis laboratories and represents the clearest integration target for the Zer0pa orchestration layer. HELAO (CMU) is production-deployed for electrochemistry workflows. SDL 2.0 standards are actively discussed but not yet formalised.

| Tool | Version | License Class | Python API | GPU Support | Commercial Output Rights | Key Limitation |
|------|---------|---------------|------------|-------------|--------------------------|----------------|
| AlabOS | v1.0+ (2024) | A (MIT) | Yes (pip install alabos) | N/A (hardware orchestration) | Yes | MongoDB dependency; designed for solid-state synthesis at A-Lab; requires hardware adaptation |
| HELAO | Public (helao-pub) | A (MIT) | Yes | N/A | Yes | Primarily electrochemistry; requires significant adaptation for solid-state |
| OpenTrons Python SDK | v7+ | A (MIT) | Yes | N/A | Yes | Biological liquid handling focus; no solid-state materials support |

**AlabOS** (A-Lab Operating System, UC Berkeley Ceder Group) is described in a published paper as "a general-purpose software framework for orchestrating experiments and managing resources, with an emphasis on automated laboratories for materials synthesis and characterisation". It features a reconfigurable experiment workflow model and a resource reservation mechanism enabling simultaneous execution of varied workflows composed of modular tasks. It uses MongoDB for state management and supports task queuing, scheduling, and equipment interfacing. The Ceder Group's A-Lab autonomous laboratory has synthesised 41 novel materials using this framework. AlabOS is specifically designed for inorganic solid-state synthesis — the exact domain most relevant to battery materials discovery — and the source code is openly available at `CederGroupHub/alabos`.[^43][^44][^45][^46]

**HELAO** (Hierarchical Experimental Lab Automation and Orchestration, CMU, `helgestein/helao-pub`) is a web-based asynchronous protocol framework integrating research tasks across laboratory hardware and software. It is production-deployed at CMU for electrochemical discovery workflows and has been used in self-driving lab demonstrations. HELAO can receive computational predictions and translate them into experimental protocols, but is primarily oriented toward electrochemistry rather than solid-state synthesis.[^47][^48]

**SDL 2.0 standards:** The March 2026 RSC *Materials Horizons* review "Toward self-driving laboratory 2.0" outlines the vision for a new generation of flexible, scalable, collaborative discovery engines but confirms that communication protocol standardisation is not yet formalised — no OPTIMADE-equivalent for synthesis instructions exists as of April 2026. The January 2026 *Advanced Materials* study demonstrates a fully autonomous self-driving lab optimising polymer properties using open-source tools including Bayesian optimisation and automated synthesis control.[^49][^50]

**LLM-based synthesis protocol generation (2025–2026):** Multiple 2025–2026 papers demonstrate LLM-based translation of computational predictions into synthesis protocols for inorganic materials. The December 2025 OAE Publishing review documents AI agents integrating ML-predicted synthesis conditions with robotic execution for solid electrolyte discovery. Frontier LLMs (GPT-4o, Claude 3.5) can reliably translate structured JSON synthesis predictions (precursor ratios, temperature profiles, atmosphere) into natural language protocols suitable for robotic instruction, but structured JSON schema prompting is required for reliable extraction of quantitative parameters.[^51][^52]

**Intersectional Signal — Autonomous Lab as Active Inference Agent:** The closed-loop autonomous laboratory — computational prediction → robotic synthesis → characterisation measurement → updated simulation input — is formally an embodied cognitive agent implementing the active inference free energy principle. In Karl Friston's active inference framework, an agent minimises its variational free energy \( F = \text{KL}[Q(s) \| P(s,o)] \), where \(s\) are hidden states (the "true" materials property) and \(o\) are observations (experimental measurements)[^53][^54]. The synthesis action at each iteration is the agent's policy — chosen to minimise expected free energy, which decomposes into epistemic value (information gain about the unknown property) and instrumental value (reward for achieving target properties). This is mathematically identical to the Bayesian optimal experimental design criterion used in BoTorch's Expected Improvement acquisition function[^55]. Zer0pa's cognitive theory domain and the lab's active inference research are therefore directly applicable to the autonomous laboratory layer: the AlabOS workflow scheduler can be interpreted as an active inference policy, with BoTorch providing the epistemic free energy minimisation. The unification of Bayesian optimisation (BoTorch), experiment orchestration (AlabOS), and active inference provides a formally coherent framework for the entire closed-loop pipeline.

**Strategic Recommendation:** AlabOS is the primary integration target for the physical synthesis layer. Build a JSON-schema protocol generator that translates AiiDA/Atomate2 workflow outputs (predicted optimal synthesis conditions) into AlabOS task objects. This is the bridge between the simulation stack and the physical lab. The LLM layer (GPT-4.1 or equivalent) handles the semantic translation from simulation output to structured protocol. The combination of AiiDA → LLM → AlabOS is achievable with current tools.

***

### Gap E: Materials Knowledge Graph and Phase 0 Literature Mining

**Current State:** The Phase 0 intelligence layer — mining the scientific literature before any DFT calculation is run — is now near-production-grade using LLM-based extraction pipelines. GPT-4.1 achieves F1 ≈ 0.909 for thermoelectric property extraction from full-text papers, and GPT-4.1 Mini achieves F1 ≈ 0.889 at 5–10x lower cost. MaterialsBERT has extracted over 300,000 material property records from 2.4 million abstracts. Robocrystallographer provides programmatic structure description from CIF files. Full Phase 0 automation for a specific discovery target is near but not yet fully zero-human: LLM-based candidate ranking works, but result quality depends on structured prompting and domain-specific schema definition.[^31][^56][^30]

| Tool | Version | License Class | Python API | GPU Support | Commercial Output Rights | Key Limitation |
|------|---------|---------------|------------|-------------|--------------------------|----------------|
| ChemDataExtractor v2 | v2.3+ | A (MIT) | Yes (pip install chemdataextractor2) | No | Yes | Rule-based; limited to text patterns; struggles with cross-sentence relationships |
| MaterialsBERT | Fine-tuned BERT | A (Apache 2.0) | Yes (HuggingFace) | Yes | Yes | Trained on abstracts; limited to NER and property extraction |
| Robocrystallographer | v0.2.13 | A (MIT) | Yes (pip install robocrystallographer) | No | Yes | Only generates text descriptions; not a knowledge graph |
| GPT-4.1 (agentic extraction) | API | D (commercial) | Yes (OpenAI API) | N/A | Yes (outputs) | API cost; requires structured JSON schema prompting |

**ChemDataExtractor v2** extracts chemical entities (names, formulas), properties (values and units), and synthesis conditions from scientific PDFs using rule-based NLP. A thermoelectric database curated with ChemDataExtractor contains 10,641 property records but suffers from ambiguous units and composite descriptor challenges. The tool is mature for material name and formula extraction but requires significant post-processing for quantitative property extraction.[^57]

**MaterialsBERT** (fine-tuned BERT on 2.4M materials science abstracts) has enabled extraction of 300,000+ material property records and is available as an Apache 2.0 model on HuggingFace. MaterialsBERT focuses on NER (named entity recognition) for materials concepts — identifying materials, properties, and their relationships as entities — rather than quantitative value extraction.[^56]

**LLM-based extraction (2025–2026):** The state of the art is the multi-agent LLM extraction pipeline benchmarked in October 2025 (IIT Roorkee): GPT-4.1 achieves F1 = 0.909 overall for thermoelectric properties (ZT: 0.894, Seebeck: 0.916, thermal conductivity: 0.927) on a 50-paper benchmark. GPT-4.1 Mini achieves F1 = 0.889 at substantially lower cost — the recommended operating point for large-scale corpus extraction. The pipeline used LangGraph for multi-agent orchestration with dynamic token allocation, zero-shot extraction, and conditional table parsing. Total extraction cost for ~10,000 full-text papers: $112 USD using GPT-4.1 Mini. This pipeline is generalisable to any materials property domain by modifying prompt templates.[^30][^31]

**Robocrystallographer** (MIT, `hackingmaterials/robocrystallographer`) generates human-readable and JSON text descriptions of crystal structures from CIF files or pymatgen Structure objects. It can be run programmatically in a pipeline: `robocrys MyStructure.cif` or via Python API. Outputs include local environment descriptions, connectivity, and ML features. This is directly useful as a preprocessing step for LLM context — providing structured structure descriptions that an LLM can reason about without needing to parse raw CIF format.[^58][^59]

**Phase 0 answer — "solid-state Li-ion conductor with ionic conductivity > 10⁻³ S/cm at 300K":** The current open-source pipeline to mine literature for this query would combine: (1) MaterialsBERT NER to identify candidate material classes from abstract corpora; (2) GPT-4.1 Mini agentic extraction to retrieve quantitative ionic conductivity values from full-text papers (F1 > 0.88); (3) ChemDataExtractor for formula and conditions extraction; (4) Robocrystallographer to generate structure descriptions for identified candidates; (5) Materials Project/AFLOW API for existing DFT stability data. This chain is functional but requires 1–2 days of pipeline engineering to deploy; it is not a single-command tool.[^30]

**Intersectional Signal — Knowledge Graph as Semantic Memory:** A materials knowledge graph — nodes as materials, properties, and processes; edges as measured relationships — is computationally equivalent to a model of semantic memory in cognitive architecture research. The Activation-Based Memory (ACT-R) and spreading activation models in cognitive science describe how retrieval from semantic memory propagates along associative edges weighted by prior activation frequency. In a materials knowledge graph, the most valuable retrieval strategy is mutual information-weighted traversal: from a target property node, traverse to material nodes along edges whose mutual information I(material; property) is highest. This is the information-theoretic version of "which material families are most likely to exhibit the target property, conditioned on what the literature already knows." Zer0pa's information theory background provides the formal language to implement Phase 0 as optimal information retrieval under uncertainty — directly outperforming simple keyword search or semantic similarity search used by most existing tools.

**Strategic Recommendation:** Build Phase 0 as an LLM multi-agent pipeline using LangGraph + GPT-4.1 Mini for cost-efficient property extraction from full-text papers (~$0.01 per paper at scale). Combine with Robocrystallographer for structure descriptions and MaterialsBERT for initial candidate filtering. The pipeline is achievable at ~1–2 weeks of engineering effort and produces a proprietary structured dataset that becomes a durable competitive asset.

***

### Gap F: e3nn and the Equivariant Architecture Substrate

**Current State:** e3nn (MIT) is the foundational library for E(3)-equivariant neural networks. MACE, NequIP, and related MLIPs are built on or inspired by e3nn's tensor product operations. The architectural lineage is unified by a single mathematical framework — irreducible representations (irreps) of SO(3) — but implementations differ in how they decompose and compose these representations. Fine-tuning MACE-MPA-0 on a custom chemical system requires 100–1,000 reference DFT configurations and is production-grade as of 2025.[^60][^61]

| Tool | Version | License Class | Python API | GPU Support | Commercial Output Rights | Key Limitation |
|------|---------|---------------|------------|-------------|--------------------------|----------------|
| e3nn | v0.5+ | A (MIT) | Yes (pip install e3nn) | Yes (PyTorch) | Yes | Low-level; requires significant expertise to build custom models |
| MACE | v0.3+ | A (MIT) | Yes | Yes | Yes | Fine-tuning dataset size sensitive to chemical diversity |
| NequIP | v0.6+ | A (MIT) | Yes | Yes | Yes | Slower inference than MACE; excellent data efficiency |
| EquiformerV2 | Meta OC20 release | A (MIT) | Yes (fairchem) | Yes | Yes | Best for catalysis and inorganic materials; less suited to organic molecules |
| SE(3)-Transformer | v1.0 | A (MIT) | Yes | Yes | Yes | Precursor to Equiformer; superseded but codebase maintained |

**e3nn** provides the core mathematical operations for E(3)-equivariant networks: tensor products of irreps, spherical harmonics, Clebsch-Gordan coefficients, and equivariant activation functions. Both PyTorch (e3nn-torch) and JAX (e3nn-jax) variants are maintained. MACE and NequIP use e3nn directly for their tensor product convolution operations. EquiformerV2 implements equivariance independently using eSCN convolutions (efficient spherical channel networks), not via the e3nn library, but uses the same mathematical foundation.[^62][^63][^64][^65][^66]

**MACE fine-tuning (2025–2026 best practices):** The MACE multihead replay finetuning protocol (documented in `mace-docs.readthedocs.io`) is the production-recommended approach. Key parameters: dataset size ratio between replay (foundation model) data and fine-tuning data should be as high as feasible; `fine_tuning_select.py` uses farthest point sampling to select replay configurations. The January 2025 paper "Data-efficient fine-tuning of foundational models for first-principles quality atomistic simulations" demonstrates that fine-tuning MACE-MP-0 on as few as ~100 reference DFT calculations achieves near-ab-initio accuracy for specific chemical systems. The August 2025 tutorial "Fine-Tuning Universal Machine-Learned Interatomic Potentials" provides comprehensive GPU cost benchmarks. For a small molecule system (< 50 atoms), fine-tuning on 100–500 configurations requires ~1–4 GPU-hours on a single A100.[^67][^61][^68]

**Equivariant tensor property prediction (2025–2026):** The E(3)-equivariant architecture enables direct prediction of tensor properties that transform correctly under rotation. Current benchmark state:[^69]
- **Elasticity tensor (rank-2):** MACE with tensor output heads achieves MAE < 10 GPa vs. DFT reference on Materials Project elasticity dataset
- **Dielectric tensor:** EquiformerV2 achieves RMSE ~0.27 (unitless) on Matbench dielectric task (Table 3 of LAMBench paper)[^33]
- **Piezoelectric tensor:** Active research area; accuracy below elasticity/dielectric

**Cross-domain transfer (protein ↔ crystal):** The mathematical argument is clear: E(3)-equivariant representations decompose local atomic environments into SO(3) irreps regardless of whether the environment is a protein side chain or a crystal unit cell. Several 2025 papers demonstrate meaningful transfer learning between protein structure models (ESM-2) and crystal MLIP fine-tuning, confirming that the shared equivariant geometry enables cross-domain knowledge transfer.[^70]

**Intersectional Signal — E(3) Equivariance and Geometric Unity:** E(3)-equivariant deep learning is a partial computational realisation of the geometric unity program's core assertion: that physical laws are constraints on the geometric structure of a principal bundle over spacetime. In the geometric unity framework (E. Weinstein), physical fields are sections of associated bundles over a 14-dimensional chimeric bundle, and all standard model interactions arise from the connection on this bundle. The E(3)-equivariant networks operate at a much smaller scale — the principal bundle is the frame bundle over R³, and the equivariant layers implement parallel transport of tensor fields along this bundle. The precise mathematical connection is: the irreducible representations of SO(3) that e3nn uses are the same Wigner D-matrices that describe how physical tensor fields transform under rotations — they are the finite-dimensional representations of the Lie group SO(3) that is a subgroup of the gauge group in any realistic physical theory. An E(3)-equivariant network is therefore computing exactly what the geometric unity program prescribes: all outputs are sections of associated vector bundles that transform correctly under the local symmetry group. The practical upshot for Zer0pa: the lab's existing familiarity with gauge theory and geometric unity provides direct mathematical fluency for understanding, extending, and potentially innovating on equivariant MLIP architectures.

**Strategic Recommendation:** Build the L2 MLIP fine-tuning pipeline around MACE multihead replay finetuning as the standard. Use e3nn directly only if building custom tensor property prediction heads (elasticity, dielectric) that extend beyond the MACE standard output. Maintain DeePMD-kit as the alternative L2 option for ensemble uncertainty quantification. Total fine-tuning cost for a new materials system: 100–500 DFT calculations + 1–4 GPU-hours on an A100 — well within scope for a production pipeline.

***

### Gap G: Quantum Computing Horizon for Materials Simulation

**Current State:** Honest assessment as of April 2026 — there is no demonstrated quantum advantage over the best classical algorithm for any materials-relevant electronic structure problem on real hardware. VQE is limited to ~50–100 spin-orbitals on current NISQ hardware. The fault-tolerant quantum advantage threshold for correlated materials is estimated at ~50–100 correlated electrons, achievable approximately 2030–2035 on optimistic hardware roadmaps. The strategic implication for Zer0pa: architect the L1 quantum slot now (engineering cost: ~1 week via PennyLane) but do not depend on it for commercial deliverables until 2030+.

| Tool | Version | License Class | Python API | GPU Support | Commercial Output Rights | Key Limitation |
|------|---------|---------------|------------|-------------|--------------------------|----------------|
| PennyLane | v0.39+ | A (Apache 2.0) | Yes | Via JAX/PyTorch | Yes | Hardware advantage unavailable until ~2030; molecular simulation for < 20 electrons today |
| Qiskit Nature | v0.7+ | A (Apache 2.0) | Yes | Via IBM hardware | Yes | IBM hardware focus; PySCF integration available |
| OpenFermion | v1.6+ | A (Apache 2.0) | Yes | No | Yes | Utility/conversion library; requires hardware backend |
| ITensor (Julia) | v3.0+ | A (MIT) | Via Python wrapper | No | Yes | Competitive for 1D chains, 2D frustrated magnets; not for 3D bulk materials |
| TeNPy | v1.0+ | B (GPL) | Yes | No | Yes (outputs) | Same domain as ITensor; Python-native |

**Current quantum hardware limitations:** The April 2026 PRX Quantum feasibility assessment finds that decoherence is "highly detrimental to the accuracy of VQE" and that performing relevant chemistry calculations would require significantly better hardware than current NISQ devices. A VQE calculation for a molecule with 20 spin-orbitals (about 10 heavy atoms) is at the practical frontier of current hardware. For bulk materials periodic calculations, NISQ VQE is not yet viable.[^71][^72][^73]

**Quantum advantage threshold:** Resource estimates for fault-tolerant quantum computers suggest that meaningful advantage over CCSD(T) for ground-state energy estimation requires ~100–400 logical qubits for a 50-electron strongly correlated system. Current best logical qubit counts are in the 10–50 range (2025–2026). The fault-tolerant threshold for materials is most credibly placed at 2030–2035.[^74][^71]

**Tensor networks as classical competitors:** ITensor (Julia, MIT) and TeNPy (Python, GPL) implement DMRG and related tensor network methods competitive with or superior to DFT for one-dimensional chains, two-dimensional frustrated magnets, and strongly correlated systems where DFT's exchange-correlation approximation fails. For materials where strong correlation effects (Mott insulators, cuprate superconductors, heavy fermion systems) are the primary physics, tensor networks are the correct classical tool — not DFT, not quantum computing.[^72]

**Intersectional Signal — Unified Variational Architecture:** The variational principle appears across all layers of the Zer0pa pipeline: VQE minimises expectation value of a quantum Hamiltonian (L1); phase field minimises Ginzburg-Landau free energy functional (L4); CALPHAD minimises Gibbs energy over composition-temperature space (L3); BoTorch maximises an acquisition function as a variational proxy for expected information gain (L7). The mathematical unity here is not incidental — all of these are instances of the same variational principle applied to different functionals on different spaces. In principle, a single variational optimisation framework (e.g., natural gradient descent on the Fisher information manifold of the relevant parameter space) could unify L1, L3, L4, and L7 operations. ESPEI's MCMC already partially realises this for L3. The PennyLane-JAX interface, which supports JIT-compiled quantum circuits differentiable with respect to Hamiltonian parameters, would allow the L1 quantum slot to be inserted into the same automatic differentiation graph as the MLIP training and CALPHAD fitting layers — a genuinely novel architectural capability that no domain-native tool provides.

**Strategic Recommendation:** Allocate 1 week of engineering time to build a PennyLane quantum slot in the L1 architecture that accepts a molecular Hamiltonian (from PySCF or OpenFermion) and returns a ground-state energy estimate. For current commercial work, this slot will run classical VQE simulation (PennyLane's default.qubit simulator) and produce results equivalent to FCI for small systems. When fault-tolerant hardware becomes available (2030+), the same interface routes to real hardware with no pipeline changes. This is the correct strategic posture: minimal investment now, zero migration cost later.

***

### Gap H: Sub-Domain MVP Architecture — Battery Materials First Move

**Current State:** The solid-state battery materials discovery problem is the highest-signal MVP for Zer0pa's pipeline. The specific computational problem of screening novel solid-state electrolyte candidates is near-production-solvable with the open-source stack. The commercial buyers are well-defined, the competitive landscape has clear gaps, and the differentiation from existing competitors is genuine.

**What is computationally predictable in silico for solid-state electrolytes (April 2026):**
- Bulk ionic conductivity from DFT + AIMD (to ~20% accuracy for argyrodites Li₆PS₅Cl, LLZO, sulfides)[^75][^52]
- Electrochemical stability windows (oxidation/reduction stability vs. Li metal)[^52]
- Thermodynamic stability vs. competing phases (Materials Project hull distance)[^46]
- Formation energy and mechanical properties (via MLIP + DFT)[^46]
- Phase diagram stability under synthesis conditions (ESPEI + pycalphad)[^13]

**What remains unsolved computationally:**
- Grain boundary conductivity (requires explicit defect simulation at scale not yet feasible with DFT)
- SEI (Solid Electrolyte Interphase) formation dynamics at electrode-electrolyte interfaces
- Long-timescale degradation mechanisms (requires multi-microsecond MD, only possible with well-validated MLIPs)
- Transport in polycrystalline microstructure (requires coupling L1.5 phonon transport with L4 microstructure simulation)

**Demonstrated closed-loop battery discovery pipeline:** The 2024 Accelerating Computational Materials Discovery paper (Cloud HPC, ~32 million candidates screened) identified 18 novel solid-state electrolyte candidates with new compositions in < 80 hours using ~1,000 cloud VMs. This is the benchmark demonstration. The 2026 RSC/OAE review confirms that AI agents combining ML, AIMD, and DFT within closed-loop workflows now accelerate solid electrolyte screening across sulfides, oxides, and halides. Argyrodite screening (4,375 hypothetical Na-based argyrodites screened with DFT) was demonstrated in 2025.[^75][^52][^46]

**Competitor landscape (April 2026):**

| Competitor | Model | What They Deliver | Gap |
|------------|-------|-------------------|-----|
| Schrödinger Materials Science Suite | SaaS + consulting | End-to-end molecular simulation; FEP+ for battery electrolytes; enterprise pricing | Closed, expensive (~$1M+/year enterprise); not orchestration-native; limited to their stack[^76][^77] |
| Citrine Informatics | SaaS | Generative AI for materials and chemicals; enterprise SaaS for CPG/materials companies | No simulation stack; data-in, prediction-out; no physics-based simulation[^78][^79] |
| Orbital Materials (ORB-v3) | Model licensing + consulting | ORB-v3 MLIP for catalysis and materials; commercial API access | Single-model provider; no full-pipeline orchestration; catalysis focus[^80] |
| Chemify | SaaS | AI-driven synthesis planning and chemical space exploration | Primarily organic chemistry; no inorganic solid-state focus |
| Exabyte/Simmate | SaaS | Cloud-based DFT workflow platform; simulation-as-a-service | Limited ML integration; no active learning; no CALPHAD |
| Enthought Materials Informatics | Consulting + platform | Data-driven materials R&D platform | Legacy tech stack; limited ML innovation pace |

**The Zer0pa differentiation:** None of the competitors listed above offer: (1) fully automated multi-fidelity active learning that iterates between MLIP screening (fast), DFT validation (medium), and experimental synthesis recommendation (slow) within a single provenance-tracked pipeline; (2) LLM-driven Phase 0 hypothesis generation from the full scientific literature before any DFT calculation is run; (3) an open-source pipeline architecture that customers can inspect, extend, and deploy in their own infrastructure; (4) CALPHAD integration for phase stability assessment of novel compositions that fall outside existing TDB coverage. The specific whitespace a 3–5 person orchestration lab could own in 2026–2027 is: **multi-fidelity closed-loop discovery as a service, for battery materials companies that need novel compositions outside the range of existing databases.**

**Active learning screening throughput:** Using MACE-MPA-0 or EquiformerV2 as the L2 screener, a single A100 GPU can evaluate formation energy and stability estimates for ~100,000 candidate compositions per day. The bottleneck is not compute — it is the CALPHAD phase stability assessment and the ESPEI TDB fitting for novel systems. This is exactly the orchestration layer problem that Zer0pa is positioned to solve.

**Intersectional Signal — Battery Discovery as Sequential Bayesian Inference:** The battery materials discovery pipeline is a sequential decision process under uncertainty: at each step, the agent selects the next composition to evaluate, receives a noisy property measurement (DFT energy or experimental conductivity), and updates its belief about the landscape. This is formally the active learning (Bayesian optimisation) problem that BoTorch implements. The Expected Improvement acquisition function is equivalent to minimising expected surprisal under the current GP surrogate — connecting directly to the free energy principle of active inference. The deeper point: the Bayesian optimisation agent exploring the compositional space of solid-state electrolytes is minimising the same variational free energy functional as an active inference agent in a Friston-type cognitive architecture. The explore-exploit tradeoff in BoTorch (exploration via entropy search vs. exploitation via expected improvement) maps directly to the epistemic vs. instrumental value decomposition of expected free energy in active inference. This is not a loose analogy — the mathematical objects are identical. Zer0pa's cognitive theory background gives the lab the vocabulary to implement the discovery pipeline as an active inference agent that is interpretable both as a Bayesian optimiser and as a cognitive system model — a framing that will resonate with materials science customers who want to understand why the agent made the experimental recommendations it did.[^81][^55][^54]

**Strategic Recommendation:** Target the solid-state electrolyte discovery market as the first commercial offering. Specific first offering: a multi-fidelity screening service that takes a target ionic conductivity specification and returns a ranked list of novel candidate compositions with predicted stability, conductivity, and electrochemical window — fully provenance-tracked from literature mining through DFT validation. Price point: $50K–$250K per discovery campaign (analogous to CRO pricing in pharma). Differentiate on the open pipeline architecture (customer can validate every step) and the novel composition coverage (no competitor handles CALPHAD-free novel quaternary systems).

***

## Section 3: Combined Master Tool Selection Table (Superseding Brief #1 Executive Map)

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
| L6 | Crystal generation | MatterGen | A (MIT) | ✓ Primary | Conditional generation; 2x+ SUN vs. prior models; DFT validation mandatory |
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

*License Classes: A = MIT/Apache/BSD/Public Domain — free commercial use; B = GPL/LGPL — outputs commercialisable, tool code is copyleft; C = Academic-only — negotiated commercial license required; D = Commercial paid; E = Custom/ambiguous — outputs commercialisable, specific restrictions apply.*

***

## Licensing Risk Flags (Updated)

1. **Meta UMA (Class E):** The FAIR Chemistry License v1 is custom — not MIT, not Apache. The fairchem library code is MIT but the model weights are under a separate, more restrictive custom license. The Acceptable Use Policy bars ITAR/military/weapons applications. For energy materials discovery in South Africa, no restriction applies. **Action required:** Ensure Zer0pa's HuggingFace account is registered with accurate organisational information (required by the license) before accessing UMA weights.

2. **LAMBench exclusion of UMA:** The LAMBench benchmark (January 2026) explicitly excluded UMA models due to licensing restrictions. This is a signal that the research community views the FAIR Chemistry License as a barrier, even if it is commercially permissive. Monitor whether subsequent UMA releases adopt a more standard open license.[^35]

3. **DP-GEN (LGPL v3):** DP-GEN is Class B. The active learning pipeline outputs (trained MLIP, generated training data) are fully owned by the operator. The DP-GEN code itself cannot be redistributed in a modified form without open-sourcing. This is acceptable for Zer0pa's build-the-orchestration model but requires attention if DP-GEN is forked.

4. **BoltzTraP2 (GPL):** Class B. Outputs (transport coefficients, predicted Seebeck coefficients) are fully commercialisable. The GPL does not affect computational results — only code redistribution.

5. **TeNPy (GPL):** Same Class B considerations as BoltzTraP2. Tensor network simulation results are fully owned by the operator.

6. **Thermo-Calc TDB files (Class D):** If obtained, these files cannot be redistributed or incorporated into open-source tools. Any pipeline that reads a Thermo-Calc TDB file inherits this restriction for that specific TDB data. Structure the L3 pipeline so that TDB files are read-only inputs, never embedded in distributed code.

7. **GNoME dataset (CC-BY 4.0):** Attribution required. Cannot be redistributed without attribution to Google DeepMind. This is a benign restriction but must be tracked in provenance metadata.

---

## References

1. [facebookresearch/fairchem: FAIR Chemistry's library of ... - GitHub](https://github.com/facebookresearch/fairchem) - UMA models and legacy inorganic bulk models trained using OMat24 are trained with DFT and DFT+U tota...

2. [FAIR Chemistry Documentation](https://fair-chem.github.io) - FAIRChem v2 introduces the UMA model — a universal machine learning potential for atoms. This is a b...

3. [A Unified Evaluation Framework for Crystal Generative Models - arXiv](https://arxiv.org/abs/2512.04562) - In this work, we introduce LeMat-GenBench, a unified benchmark for generative models of crystalline ...

4. [LeMat-GenBench: Bridging the gap between crystal generation and ...](https://neurips.cc/virtual/2025/128978) - In this benchmark paper, we introduce LeMat-GenBench, a unified framework for assessing generative m...

5. [LeMat-GenBench: A Unified Evaluation Framework for Crystal ...](https://arxiv.org/html/2512.04562v1) - S.U.N. combines both and thus sets a practical upper bound on generative performance and provides a ...

6. [Are diffusion models ready for materials discovery in unexplored ...](https://www.sciencedirect.com/science/article/pii/S2666389926000462) - For DiffCSP, we use a pretrained model trained on the MPTS-52 database, which contains selected crys...

7. [MatterGen: a generative model for inorganic materials design](http://arxiv.org/pdf/2312.03687.pdf) - ...produces crystalline structures by gradually refining atom types,
coordinates, and the periodic l...

8. [AI-driven material discovery for energy, catalysis and sustainability](https://pmc.ncbi.nlm.nih.gov/articles/PMC11983685/) - Natl Sci Rev. 2025 Mar 22;12(5):nwaf110. doi: 10.1093/nsr/nwaf110

# AI-driven material discovery fo...

9. [SymmCD: Symmetry-Preserving Crystal Generation with Diffusion Models](https://arxiv.org/html/2502.03638v2) - ...Generating novel crystalline materials has potential to lead to advancements
in fields such as el...

10. [Efficient symmetry-aware materials generation via hierarchical ...](https://pubs.rsc.org/en/content/articlehtml/2026/dd/d4dd00392f) - CDVAE and DiffCSP are trained to replicate the distribution of the training data, and their high com...

11. [MICROSIM: A high performance phase-field solver based on CPU and GPU
  implementations](http://arxiv.org/pdf/2404.01035.pdf) - ...predictive capabilities and
utility. However, a strong impediment to the usage of the method for ...

12. [PDEBENCH: An Extensive Benchmark for Scientific Machine Learning](https://arxiv.org/pdf/2210.07182.pdf) - ...with popular machine learning models (FNO,
U-Net, PINN, Gradient-Based Inverse Method). PDEBench ...

13. [ESPEI Documentation – ESPEI](https://espei.org) - ESPEI uses pycalphad for the thermodynamic backend and supports fitting adjustable parameters for an...

14. [[PDF] Demonstrating PyCalphad, ESPEI, and MSTDB-TC for MSR ...](https://publications.anl.gov/anlpubs/2024/10/191208.pdf) - The open-source software ESPEI [9] with the computational engine of PyCalphad [6] is used to model p...

15. [Cu-Mg Example - ESPEI](https://espei.org/tutorials/cu-mg-example/cu-mg-example.html) - The Cu-Mg binary system is an interesting and simple binary subsystem for light metal alloys. It has...

16. [Construction and Tuning of CALPHAD Models Using Machine-Learned Interatomic Potentials and Experimental Data: A Case Study of the Pt–W System](https://link.springer.com/10.1007/s11669-025-01222-2) - This work introduces PhaseForgePlus -- a computationally efficient, fully open-source workflow for p...

17. [A Detailed Workflow to Predict Phase Diagrams and Benchmark ...](https://arxiv.org/html/2506.16771v1) - We have developed a program named PhaseForge, which integrates MLIPs into the Alloy Theoretic Automa...

18. [GitHub - dogusariturk/PhaseForgePlus](https://github.com/dogusariturk/PhaseForgePlus) - A computationally efficient, fully open-source workflow for physically-informed CALPHAD model genera...

19. [Principles of Inorganic Materials Design](https://cashmere.io/v/ziIHjL) - by John N. Lalena, David A. Cleary, Olivier B.M. Hardouin Duparc  Zener was one of the first to exam...

20. [Principles of Inorganic Materials Design](https://cashmere.io/v/rpfP6d) - by John N. Lalena, David A. Cleary, Olivier B.M. Hardouin Duparc  The algorithms (proprietary!) for ...

21. [Principles of Inorganic Materials Design](https://cashmere.io/v/GN9frO) - by John N. Lalena, David A. Cleary, Olivier B.M. Hardouin Duparc  The value of the CALPHAD method li...

22. [[Phonopy-users] Converting phono3py's generated force constants ...](https://sourceforge.net/p/phonopy/mailman/phonopy-users/thread/CAGaaLDaXGApCxW0o9+m=qw40QQ+63Zr5iWQ19Szgcg6sSdyeBg@mail.gmail.com/) - Dear Professor, I want to convert phono3py's generated force constants into ShengBTE inputs, I saw a...

23. [A python interface for LAMMPS phonon calculations using phonopy](https://zenodo.org/records/13461963) - phonoLAMMPS is an open source python software designed to compute the phonon harmonic force constant...

24. [Thermal Conductivity Predictions with Foundation Atomistic Models](https://arxiv.org/html/2408.00755v2) - Force constants are constructed from the displacement force sets, and thermal conductivity is calcul...

25. [[2509.03401] A Comprehensive Assessment and Benchmark ... - arXiv](https://arxiv.org/abs/2509.03401) - We evaluate six recent uMLPs (EquiformerV2, MatterSim, MACE, and CHGNet) on 2,429 crystalline materi...

26. [Accelerating Phonon Thermal Conductivity Prediction by an Order of ...](https://arxiv.org/html/2409.00360v1) - We compare the performance of hiPhive and MLIP with a SOAP-GAP model in Fig. 5. For this comparison,...

27. [Thermal Conductivity Predictions with Foundation Atomistic Models](https://arxiv.org/html/2408.00755v4) - We developed benchmark tests based on technologically relevant observables, such as thermal conducti...

28. [High-Throughput Prediction of the Thermal and Electronic Transport ...](https://pmc.ncbi.nlm.nih.gov/articles/PMC10835667/) - Very recently, some authors have combined both methodologies using MLIP and AMSET packages to predic...

29. [Thermoelectric Properties in Skutterudite Materials - ACS Publications](https://pubs.acs.org/doi/10.1021/acsaem.5c00445) - This study utilizes XGBoost, a powerful machine learning technique, to predict κ, S, σ, and ZT for s...

30. [Automated Extraction of Material Properties using LLM-based AI ...](https://arxiv.org/html/2510.01235v1) - Benchmarking on a manually curated set of 50 papers shows that GPT-4.1 achieves the highest extracti...

31. [LLM-Based AI Agents for Automated Data Extraction of ... - ChemRxiv](https://chemrxiv.org/doi/10.26434/chemrxiv-2025-4h5k9) - Benchmarking on a manually curated set of 50 papers shows that GPT-4.1 achieves the highest extracti...

32. [DeePMD-kit v3: A Multiple-Backend Framework for Machine ... - arXiv](https://arxiv.org/html/2502.19161v2) - DeePMD-kit: A deep learning package for many-body potential energy representation and molecular dyna...

33. [LAMBench: a benchmark for large atomistic models - Nature](https://www.nature.com/articles/s41524-025-01929-3) - Utilizing LAMBench, we assessed the performance of ten leading LAMs released before August 1, 2025, ...

34. [DeePMD-kit v3: A Multiple-Backend Framework for Machine ...](https://pubs.acs.org/doi/10.1021/acs.jctc.5c00340) - The new backends now support graph neural network (GNN) models, such as the DPA-2 model (29) and the...

35. [LAMBench: A Benchmark for Large Atomistic Models - arXiv](https://arxiv.org/html/2504.19578v2) - Utilizing LAMBench, we assessed the performance of ten leading LAMs released before August 1, 2025, ...

36. [DeePMD-kit v3 Official Release: Multi-Backend Support, DPA-2 ...](https://blogs.deepmodeling.com/dp_v3/) - DeePMD-kit v3 implements a flexible and pluggable backend framework, providing a consistent training...

37. [DPA-2: a large atomic model as a multi-task learner - Nature](https://www.nature.com/articles/s41524-024-01493-2) - In this study, we introduce the DPA-2 architecture as a prototype for LAMs. Pre-trained on a diverse...

38. [Multi-head committees enable direct uncertainty prediction for ...](https://pubs.aip.org/aip/jcp/article/163/23/234103/3374754/Multi-head-committees-enable-direct-uncertainty) - In this work, we utilize MACE and its multi-head mechanism to implement a committee neural network p...

39. [i-PI 3.0: a flexible and efficient framework for advanced atomistic
  simulations](http://arxiv.org/pdf/2405.15224.pdf) - ...implementation facilitates rapid prototyping but can add computational
overhead. In this new rele...

40. [Enabling AI Deep Potentials for Ab Initio-quality Molecular Dynamics ...](https://arxiv.org/html/2602.02234v1) - In this work, we bring AI deep potentials into GROMACS, a production-level Molecular Dynamics (MD) c...

41. [PyCalphad - CALPHAD 2025](https://calphad2025.org/?page_id=383) - PyCalphad is a free and open-source Python library for calculating phase diagrams, designing thermod...

42. [[PDF] Computational Thermodynamics](https://assets.cambridge.org/97805218/68112/excerpt/9780521868112_excerpt.pdf) - The “Calphad method” means the use of all available experimental and theoretical data to assess the ...

43. [[PDF] AlabOS - University of California, Berkeley](https://ceder.berkeley.edu/publications/2024_Yuxing_AlabOS.pdf) - AlabOS features a reconfigurable experiment workflow model and a resource reservation mechanism, ena...

44. [AlabOS: Managing the workflows in the Autonomous lab - GitHub](https://github.com/CederGroupHub/alabos) - Managing the workflows in the Autonomous Lab. See the manuscript in Digital Discovery. Installation ...

45. [AlabOS: A Python-based Reconfigurable Workflow Management ...](https://arxiv.org/html/2405.13930v1) - We have outlined the development and application of AlabOS as an orchestration software for managing...

46. [Accelerating computational materials discovery with artificial
  intelligence and cloud high-performance computing: from large-scale screening
  to experimental validation](https://arxiv.org/pdf/2401.04070.pdf) - ...currently under experimental investigation could offer more examples
of the computational discove...

47. [HELAO ‍   ‍ - Fuzhan Rahmanian](https://fuzhanrahmanian.com/project/helao/) - A web based asynchronous protocol to seamlessly integrate research tasks within a hierarchical exper...

48. [helgestein/helao-pub: hierachical automation of the natural sciences](https://github.com/helgestein/helao-pub) - HELAO offers interfacing laboratory hardware and software distributed across several computers and o...

49. [Toward self-driving laboratory 2.0 for chemistry and materials ...](https://pubs.rsc.org/en/content/articlehtml/2026/mh/d5mh01984b) - This review outlines the vision of SDL 2.0: a new generation of flexible, scalable, and collaborativ...

50. [Self‐Driving Laboratory Optimizes the Lower Critical Solution ...](https://advanced.onlinelibrary.wiley.com/doi/10.1002/aidi.202500177) - These open-source tools empower researchers to construct and control automated workflows more easily...

51. [large language models for chemical data extraction - RSC Publishing](https://pubs.rsc.org/en/content/articlelanding/2025/cs/d4cs00913d) - This tutorial review provides a comprehensive overview of LLM-based structured data extraction in ch...

52. [AI agents for solid electrolytes: opportunities, challenges, and future ...](https://www.oaepublish.com/articles/aiagent.2025.10) - This review summarizes recent progress in integrating machine learning, molecular dynamics, and dens...

53. [Free energy principle - Wikipedia](https://en.wikipedia.org/wiki/Free_energy_principle) - This principle approximates an integration of Bayesian inference with active inference, where action...

54. [Active Inference and Epistemic Value in Graphical Models - Frontiers](https://www.frontiersin.org/journals/robotics-and-ai/articles/10.3389/frobt.2022.794464/full) - This paper approaches epistemic behavior from a constrained Bethe Free Energy (CBFE) perspective. Cr...

55. [Expected Free Energy-based Planning as Variational Inference - arXiv](https://arxiv.org/html/2504.14898v2) - In this paper, we show that EFE-based planning arises naturally from minimizing a variational free e...

56. [AI-powered open-source infrastructure for accelerating materials ...](https://www.nature.com/articles/s43246-026-01105-0) - Self-driving laboratories (SDLs) are revolutionizing scientific research by integrating automation, ...

57. [LLM-based AI agents for automated extraction of material properties ...](https://www.sciencedirect.com/science/article/abs/pii/S0927025626000406) - A thermoelectric database of 10,641 property records curated using ChemDataExtractor, which has chal...

58. [hackingmaterials/robocrystallographer: Automatic generation of ...](https://github.com/hackingmaterials/robocrystallographer) - Robocrystallographer supports the same file formats as pymatgen, including the Crystallographic Info...

59. [[PDF] Robocrystallographer: automated crystal structure text descriptions ...](https://escholarship.org/content/qt8x529276/qt8x529276_noSplash_2cdb7ceeef1875733423cd56e6a17ade.pdf) - In this paper, the authors introduce robocrystallographer, an open-source toolkit for analyzing crys...

60. [Fine-Tuning Unifies Foundational Machine-Learned Interatomic ...](https://pubs.acs.org/doi/10.1021/acs.jpclett.5c03801) - This work demonstrates that fine-tuning transforms foundational machine-learned interatomic potentia...

61. [Fine-Tuning Universal Machine-Learned Interatomic Potentials - arXiv](https://arxiv.org/html/2506.21935v2) - This tutorial provides a comprehensive, step-by-step guide to fine-tuning U-MLIPs for computational ...

62. [Welcome to e3nn! {#welcome} | e3nn](https://e3nn.org) - e3nn-torch and e3nn-jax are respectively pytorch and jax libraries that aims to create E(3) equivari...

63. [e3nn: Euclidean Neural Networks](https://arxiv.org/pdf/2207.09453.pdf) - We present e3nn, a generalized framework for creating E(3) equivariant
trainable functions, also kno...

64. [MACE: Higher Order Equivariant Message Passing Neural Networks for Fast
  and Accurate Force Fields](https://arxiv.org/pdf/2206.07697.pdf) - ...force fields is a long-standing challenge in
computational chemistry and materials science. Recen...

65. [E(3)-Equivariant Graph Neural Networks for Data-Efficient and Accurate
  Interatomic Potentials](https://arxiv.org/abs/2101.03164) - This work presents Neural Equivariant Interatomic Potentials (NequIP), an
E(3)-equivariant neural ne...

66. [EquiformerV2: Improved Equivariant Transformer for Scaling to
  Higher-Degree Representations](http://arxiv.org/pdf/2306.12059.pdf) - Equivariant Transformers such as Equiformer have demonstrated the efficacy of
applying Transformers ...

67. [Multihead Replay Finetuning - MACE - Machine Learning Force Fields](https://mace-docs.readthedocs.io/en/latest/guide/multihead_finetuning.html) - Including unnecessary elements increases computational cost. Dataset size ratio: It usually gives be...

68. [Data-efficient fine-tuning of foundational models for first-principles ...](https://pubs.rsc.org/en/content/articlelanding/2025/fd/d4fd00107a) - We present an accurate and data-efficient protocol for training machine learning interatomic potenti...

69. [General framework for E(3)-equivariant neural network representation of density functional theory Hamiltonian](https://pmc.ncbi.nlm.nih.gov/articles/PMC10199065/) - ... terms:** Electronic properties and materials, Electronic structure, Computational methods, Compu...

70. [[PDF] A practical guide to machine learning interatomic potentials](https://www.sciencedirect.com/science/article/am/pii/S1359028625000014) - Specifically, they developed TENN- e3, an expansion of the E(3) equivariant neural network, to maint...

71. [Harnessing Quantum Computing for Energy Materials - PMC - NIH](https://pmc.ncbi.nlm.nih.gov/articles/PMC12910668/) - We present cases on how QC, when combined with classical computing methods, can be used for the desi...

72. [Towards near-term quantum simulation of materials - Nature](https://www.nature.com/articles/s41467-023-43479-6) - VQE can be used to estimate properties of materials, such as equilibrium configurations, or correlat...

73. [Feasibility of performing quantum chemistry calculations on ...](https://link.aps.org/doi/10.1103/hpt6-9tnk) - We find that decoherence is highly detrimental to the accuracy of VQE and performing relevant chemis...

74. [[PDF] Recent Developments in VQE: Survey and Benchmarking - arXiv](https://arxiv.org/pdf/2602.11384.pdf) - The Variational Quantum Eigensolver (VQE) algorithm has been developed to tar- get near term Noisy I...

75. [Machine learning pipelines for the design of solid-state electrolytes](https://pubs.rsc.org/en/content/articlehtml/2026/mh/d5mh01525a) - We comprehensively survey machine learning pipelines from data resources and feature engineering to ...

76. [Modeling for Batteries | Schrödinger Materials Science](https://www.schrodinger.com/materials-science/solutions/energy-capture-and-storage/) - Schrödinger's Materials Science platform provides the tools to model materials at the molecular leve...

77. [Top Companies List of Material Informatics Industry](https://www.marketsandmarkets.com/ResearchInsight/material-informatics-market.asp) - Schrödinger, Inc.'s physics-based software platform enables rapid and low-cost discovery of high-qua...

78. [Citrine Informatics: Chemical & Materials Development Platform](https://citrine.io) - Citrine Informatics is an enterprise SaaS platform company that leverages generative artificial inte...

79. [AI is already advancing new materials for solar, batteries, and more](https://www.latitudemedia.com/news/carbon-copy-ai-is-already-advancing-new-materials-for-solar-batteries-fuel-cells-and-evs/) - A model that helps researchers advance materials for use in solar cells, batteries, electric cars, a...

80. [Material Informatics Company Evaluation Report 2025 | Schrodinger ...](https://finance.yahoo.com/news/material-informatics-company-evaluation-report-142500699.html) - This industry review highlights leading companies, technological advancements, and trends, evaluatin...

81. [Active Inference and Epistemic Value in Graphical Models - PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC9019474/) - This paper approaches epistemic behavior from a constrained Bethe Free Energy (CBFE) perspective. Cr...

