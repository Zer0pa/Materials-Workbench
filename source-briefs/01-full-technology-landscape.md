# In Silico Materials Science: Full Technology Landscape for Orchestrated AI Pipelines

**Zer0pa / Frontier AI Orchestration Lab — April 2026**
*Companion to: In Silico Drug Process Development: Full Technology Landscape for Orchestrated AI Pipelines*

***

## Executive Map

**Top 3 tools per pipeline layer with license class (April 2026)**

| Layer | Name | Top Tool 1 | Top Tool 2 | Top Tool 3 |
|-------|------|-----------|-----------|-----------|
| **L1: Electronic Structure** | Quantum / DFT | Quantum ESPRESSO 7.4 (B) | PySCF 2.8 (A) | CP2K 2025 (B) |
| **L2: Atomistic Simulation** | MLIP / MD | MACE-MPA-0 (A) | MatterSim-v1 (A) | Meta UMA (A†) |
| **L3: Thermodynamic Modelling** | CALPHAD | pycalphad 0.10 (A) | OpenCalphad 6.0 (B) | Thermo-Calc 2025a (D) |
| **L4: Mesoscale Microstructure** | Phase field / kMC | PRISMS-PF 2.4 (B) | MOOSE/MARMOT (B) | SPPARKS (B) |
| **L5: Continuum / Process** | FEM / CFD | FEniCSx 0.9 (B) | MOOSE Framework (B) | deal.II 9.7 (A) |
| **L6: Generative Discovery** | Inverse design | MatterGen 1.0 (A) | DiffCSP (A) | USPEX 10.5 (C) |
| **L7: Orchestration** | Workflow / Active learning | AiiDA 2.8 (A) | Atomate2 0.5 (A) | BoTorch + Ax (A) |

*†UMA from Meta FAIR is released under a commercially permissive license but carries geographic and acceptable-use restrictions — see Licensing Risk Flags section.*

***

## Section 1: The Multi-Scale Pipeline

### 1.1 How the Computational Materials Science Community Structures Multi-Scale Simulation

Computational materials science self-organises around a strict physical hierarchy defined by the spatial and temporal scales at which distinct physics operate. Unlike the pharmaceutical pipeline, which is largely a sequential workflow of distinct scientific tasks, the materials pipeline is a **nested scale hierarchy** where each layer generates parameters consumed by the layer above it. The grand challenge — bridging quantum mechanics to macroscale engineering properties — is known as multi-scale modelling and remains the most active research frontier in the field.[^1][^2]

The canonical scale hierarchy, as practised by the community, spans seven distinct layers. The boundaries between layers are defined not by arbitrary convention but by the mathematical regime change that occurs at each transition: from quantum to classical mechanics (Layer 1→2), from particle trajectories to statistical ensembles (Layer 2→3), from thermodynamic equilibrium to kinetic evolution (Layer 3→4), from discrete grain-scale physics to continuum field equations (Layer 4→5). Two additional layers — generative discovery and orchestration — operate orthogonally across the stack rather than at a single scale.[^2]

### 1.2 The Seven Layers: Definitions, Inputs, Outputs, and Data Tokens

#### Layer 1: Electronic Structure
**What happens here**: The quantum mechanical electronic structure of a material is calculated from first principles. This determines the chemical bonding, electronic band structure, magnetic properties, and the energy landscape that governs all higher-scale physics. Density Functional Theory (DFT) is the workhorse method; more accurate but expensive alternatives include GW approximation, time-dependent DFT (TDDFT), and quantum Monte Carlo (QMC).[^2]

**Scale**: 1–1,000 atoms; femtosecond–picosecond timescales.

**Primary input token**: CIF (Crystallographic Information File) or POSCAR (VASP structure file) — the universal crystal structure interchange format specifying space group, lattice parameters, and Wyckoff site positions.

**Primary output token**: Energy, forces, and stress tensor in extxyz format (extended XYZ) — the de facto standard for training MLIP datasets. Also outputs band structure (in formats readable by Wannier90), electron density (cube files), and phonon dispersions.

**Scale-bridging challenge (L1→L2)**: The output of electronic structure calculations must be assembled into a training dataset for machine learning interatomic potentials. This requires active learning — iterative cycles of short MD runs, detection of novel configurations, DFT recalculation, and model retraining. No single automated protocol has become universal, though AiiDA/Atomate2 workflows partially address this.[^3][^4]

#### Layer 2: Atomistic Simulation
**What happens here**: Using a potential energy surface — either a classical force field or an MLIP trained on Layer 1 data — millions to billions of atoms are simulated at finite temperature and pressure. This layer accesses the thermodynamic, kinetic, and mechanical properties of materials: diffusion coefficients, elastic moduli, melting points, and interface energies that are impractical to compute from electronic structure directly.[^5][^2]

**Scale**: 10³–10⁹ atoms; picoseconds–microseconds.

**Primary input token**: MLIP model weights + atomic configuration in extxyz or LAMMPS data format.

**Primary output token**: Trajectory files (HDF5 or LAMMPS dump format) containing time-evolving atomic positions and velocities; thermodynamic ensemble averages.

**Scale-bridging challenge (L2→L3)**: Extracting thermodynamic functions (free energies, chemical potentials, phase boundaries) from atomistic trajectories requires thermodynamic integration methods and is computationally expensive. CALPHAD provides empirical shortcut but requires fitting to experiment or DFT endpoint data. The coupling remains the most computationally expensive step in the hierarchy.

#### Layer 3: Thermodynamic Modelling (CALPHAD)
**What happens here**: The thermodynamics of multi-component alloy systems are parameterised using the CALPHAD (CALculation of PHAse Diagrams) method — fitting Gibbs energy functions to experimental and DFT data to produce thermodynamic databases that can rapidly predict phase stability, solidification paths, and transformation temperatures for any composition in the system.[^6]

**Scale**: Composition space (continuous); temperature/pressure range (0–3000K).

**Primary input token**: TDB (Thermo-Calc Database) file — the standard format for CALPHAD thermodynamic databases. Readable by Thermo-Calc, OpenCalphad, and pycalphad.

**Primary output token**: Phase diagrams, equilibrium phase fractions, solidification curves (Scheil-Gulliver), chemical potential–composition relationships.

**Scale-bridging challenge (L3→L4)**: Phase field simulations of microstructure evolution require local thermodynamic driving forces computed from CALPHAD databases evaluated at each grid point. The direct coupling of CALPHAD solvers to phase field codes is established but computationally intensive — pycalphad and OpenCalphad are the open-source options that support this coupling.[^7]

#### Layer 4: Mesoscale Microstructure Simulation
**What happens here**: The evolution of material microstructure — grain growth, solidification, spinodal decomposition, precipitate formation, dislocation networks — is simulated at the scale of micrometer features. Phase field methods are the dominant continuous approach; kinetic Monte Carlo handles discrete atomic/grain-level events; dislocation dynamics simulates the motion of crystallographic defects that determine plastic deformation.[^8][^9]

**Scale**: 1μm–10mm; microseconds–seconds.

**Primary input token**: CALPHAD TDB data + atomistic parameters (interface energies, mobilities) + initial microstructure (imported from experiment or generated procedurally).

**Primary output token**: Microstructure field variables at each grid point in VTK or HDF5 format; grain size distributions; precipitate morphologies.

**The phase field ↔ cellular automata isomorphism**: Phase field models solve Allen-Cahn and Cahn-Hilliard equations — reaction-diffusion PDEs that are the continuous generalisation of discrete cellular automata. The Allen-Cahn equation \( \partial_t \phi = -M \frac{\delta F}{\delta \phi} \) where \( F \) is the free energy functional is mathematically equivalent to a continuous Turing morphogenesis system. PINNs-MPF (2025) has recently demonstrated that physics-informed neural networks can solve multi-phase-field equations, directly bridging deep learning and microstructure simulation.[^10][^11][^12]

#### Layer 5: Continuum / Process Simulation
**What happens here**: At the scale of engineering components, microstructure-informed constitutive laws are fed into finite element analysis (FEA) codes to predict macroscale mechanical behaviour, thermal response, residual stresses, and forming/processing characteristics. This layer handles metal forming, additive manufacturing thermal gradients, structural analysis, and fatigue prediction.[^13]

**Scale**: 1mm–metres; seconds–hours.

**Primary input token**: Constitutive law parameters (yield strength, hardening coefficients, thermal conductivity) derived from Layer 4 + process boundary conditions (temperature, pressure, loading).

**Primary output token**: Stress-strain field data in Exodus or VTK format; property maps over engineered components.

**Scale-bridging challenge (L4→L5)**: Homogenisation — extracting single effective material properties from a heterogeneous microstructure — remains computationally intensive. Crystal plasticity finite element methods (CPFEM) partially address this but require significant setup. Hybrid ML-FEM approaches that learn constitutive laws from MD/phase-field data are an active frontier.[^13]

#### Layer 6: Generative Discovery (Cross-Scale)
**What happens here**: Rather than simulating a known material forward through the scale hierarchy, this layer runs the problem in reverse. Given a target property (high bulk modulus, specific band gap, optimal Seebeck coefficient), generative models propose candidate crystal structures and compositions for validation by Layers 1–5. This is the layer where most frontier AI development is concentrated in 2024–2026.[^14][^15]

**Input token**: Target property constraint + chemical system constraints (elements allowed, stoichiometry limits).

**Output token**: Candidate crystal structures in CIF format → passed to Layer 1 for DFT validation.

#### Layer 7: Orchestration and Active Learning (Meta-Layer)
**What happens here**: All seven layers are connected into automated, provenance-tracked workflows. Bayesian optimisation or reinforcement learning algorithms determine which experiments to run next, closing the loop between simulation and discovery. This is Zer0pa's natural entry point and competitive domain.[^16][^17]

**Input token**: Objective function definition + allowed budget (compute hours) + constraints on composition/processing space.

**Output token**: Converged optimal material/process specification with full computational provenance chain.

***

## Section 2: Commercial Value Map

### 2.1 Sub-Domain Rankings by Market Size and AI/Simulation Penetration

#### Battery Materials
**Market size**: The global sustainable battery materials market was valued at approximately USD 91.37 billion in 2024, projected to reach USD 49.88 billion by 2034 on a market restructuring trajectory (cost reduction dominates raw volume). The solid-state electrolyte sub-market alone was valued at USD 216.85 million in 2025, projected to reach USD 1,558.19 million by 2035 at a 21.91% CAGR.[^18][^19]

**AI/simulation penetration**: Exceptionally high. Ionic conductivity prediction, electrochemical stability window calculation, and interface stability modelling are all active ML/DFT targets. Autonomous AI agent workflows for solid electrolyte discovery were reviewed comprehensively in December 2025. The A-Lab at UC Berkeley demonstrated autonomous closed-loop inorganic synthesis in Nature in 2023. DFT-computed formation energies from the Materials Project are the standard pre-filter for battery materials candidates.[^20][^17]

**Unmet simulation need**: Solid-electrolyte interface (SEI) layer formation at nanosecond timescales — beyond typical MLIP timescales; requires bridging Layer 1 accuracy with Layer 2 sampling. LUMI-lab's closed-loop discovery of ionizable lipids (2026) represents a technology transfer proof-of-concept.[^21]

**Strategic accessibility**: Very high. All major materials databases contain dedicated battery materials subsets. GNoME's dataset includes ionic conductor candidates. The Open Catalyst datasets (OC20, OC22, OC25) cover electrocatalysis directly relevant to battery charging chemistry.

#### Semiconductor and Microelectronics Materials
**Market size**: The global semiconductor materials market exceeded USD 65 billion in 2025. 2D materials (graphene, TMDs, h-BN) command premium computational R&D investment from TSMC, Samsung, Intel.

**AI/simulation penetration**: High for established silicon technologies; rapidly growing for 2D materials. AI-guided 2D materials research was reviewed comprehensively in March 2026. Band gap engineering and defect level prediction are mature DFT applications. Topological materials prediction is frontier territory — computationally identifying topological insulators and Weyl semimetals from structure alone is now feasible with Z2Pack.[^22][^23][^24]

**Unmet simulation need**: Accurate modelling of dielectric interfaces at the nanoscale; dopant distribution in strained heterostructures; thermal transport at grain boundaries in advanced nodes.

**Strategic accessibility**: High for DFT-level property prediction. Commercial gate exists for actual process simulation (TCAD tools from Synopsys/Cadence are Class D with no open alternatives).

#### Heterogeneous and Electrocatalysis
**Market size**: Green hydrogen electrolysis market projected at USD 130B+ by 2030; CO₂ reduction catalysis is a multi-billion R&D market. The Open Catalyst Project (Meta/CMU) represents arguably the most significant single investment in AI for catalysis.

**AI/simulation penetration**: The highest of any sub-domain. The Open Catalyst 2020/2022/2025 (OC20/OC22/OC25) datasets have defined the benchmark for ML-accelerated catalysis. OC25, released September 2025, achieved energy/force/solvation energy errors as low as 0.1 eV / 0.015 eV/Å / 0.04 eV respectively. A comprehensive 2026 review declared AI "fundamentally reshaping the research paradigm of catalyst discovery".[^25][^26]

**Unmet simulation need**: Solid-liquid interface catalysis — the OC25 dataset was specifically designed to address this gap. Modelling of operando catalyst evolution (structural changes under reaction conditions) at DFT accuracy.[^27]

**Strategic accessibility**: Best-in-class open datasets (OC25, Apache 2.0). The fairchem library (Meta, Apache 2.0) wraps all models with Python APIs.

#### Structural Alloys: Aerospace and Additive Manufacturing
**Market size**: High-entropy alloy (HEA) market growing at ~12% CAGR; aerospace superalloy market at USD 6B+. Additive manufacturing of structural metals is a USD 20B+ market with printability prediction as a key unsolved simulation problem.

**AI/simulation penetration**: Growing rapidly. Machine learning for HEA property prediction — hardness, phase stability, corrosion resistance — has been extensively benchmarked. CALPHAD-MLIP coupling for HEA phase diagram prediction was demonstrated in November 2024. Additive manufacturing process simulation involves integrated MD→phase field→FEM chains for predicting residual stress and microstructure in laser powder bed fusion.[^28][^29][^30][^31]

**Unmet simulation need**: Powder characterisation and printability prediction; distortion compensation in large builds; multi-material interface behaviour.

**Strategic accessibility**: Moderate. Alloy composition databases (AFLOW, OQMD) are open. CALPHAD databases for complex alloy systems (TDB files) are often commercial (Thermo-Calc, PANDAT).

#### Functional Materials: Thermoelectrics, Piezoelectrics, Magnetics
**Market size**: Thermoelectric market at USD 600M growing at 9% CAGR; piezoelectric devices at USD 25B+ globally. Magnetic materials (permanent magnets for EV motors) are a strategic chokepoint market.

**AI/simulation penetration**: Strong for thermoelectrics — Seebeck coefficient, electrical conductivity, and lattice thermal conductivity prediction from crystal structure are established ML tasks. Tensor property prediction (dielectric, piezoelectric, elasticity tensors) using equivariant GNNs was demonstrated in 2024. JARVIS-DFT contains >40,000 thermoelectric material calculations.[^32][^33][^34][^35]

**Unmet simulation need**: Accurate prediction of phonon-phonon scattering rates (determining lattice thermal conductivity) at finite temperature — computationally expensive even with MLIPs.

**Strategic accessibility**: High. JARVIS-Leaderboard includes thermoelectric property benchmarks; all data NIST-hosted and publicly accessible.

#### Polymers and Soft Matter
*Limited inclusion*: AI/simulation approaches are producing commercially significant results in polymer property prediction (glass transition temperature, solubility, ionic conductivity) but the simulation stack (coarse-grained MD, MARTINI force field) is distinct from the crystalline inorganic stack that is Zer0pa's primary focus. Inclusion in a Phase 2 pipeline is recommended.

***

## Section 3: Tool Catalogue by Layer

### 3.1 Layer 1: Electronic Structure Tools

#### Quantum ESPRESSO 7.4
**What it does**: DFT plane-wave pseudopotential calculations for electronic structure, phonons, response properties, spectroscopy, and molecular dynamics. The most widely deployed open-source DFT code globally, with dedicated GPU acceleration available.[^36][^37]
**Maintained**: Actively maintained; GPU-accelerated beta release available.
**License**: GPL v2 — **Class B**. Outputs (energies, band structures, trained MLIPs) are fully commercialisable.
**Python API**: Via the Quantum ESPRESSO Python module; Atomate2 and AiiDA both have native QE plugins.
**GPU support**: Yes — CUDA/HIP GPU port available for the pw.x (plane-wave DFT) executable.[^37]
**Performance**: State of the art for periodic DFT. Not appropriate for hybrid functional calculations at scale (VASP is faster for those).
**Commercialisability of outputs**: Full.
**Integration**: CLI + Python wrapper via AiiDA plugin; Atomate2 QEProvider.

#### PySCF 2.8
**What it does**: Python-based quantum chemistry package that spans Hartree-Fock, MP2, CCSD(T), DFT, TDDFT, and GW/BSE. Unique position: the only major quantum chemistry code written natively in Python with a clean programmatic API.[^38]
**Maintained**: Actively maintained by a large academic community.
**License**: Apache 2.0 — **Class A**. Fully commercialisable.
**Python API**: Native Python — the entire codebase is a Python library.
**GPU support**: Yes, via PySCF-GPU extension (cuNumeric/cuPy backend).
**Performance**: Competitive for molecular systems; periodic DFT (solid-state) via PySCF-periodic module; slower than QE for large periodic systems.
**Commercialisability of outputs**: Full, unrestricted.
**Integration**: `pip install pyscf`; direct Python import with no binary dependencies.

#### CP2K 2025.1
**What it does**: Hybrid QM/MM and mixed Gaussian/plane-wave DFT. Specialised for large-scale DFT-MD (Born-Oppenheimer MD at DFT level) and linear-scaling DFT. Uniquely positioned for training MLIP datasets on condensed-phase systems at finite temperature.[^39]
**Maintained**: Active — 2025.1 release.
**License**: GPL v2 — **Class B**.
**Python API**: cp2k-input-tools Python library; AiiDA-CP2K plugin is the standard interface.
**GPU support**: Yes (CUDA and OpenCL).
**Performance**: Best open-source option for large-scale DFT-MD; less convenient than QE for quick property calculations.
**Commercialisability of outputs**: Full.

#### VASP 6.6.0
**What it does**: The industry-standard DFT code for solid-state materials — fastest plane-wave DFT implementation for hybrid functionals and GW calculations. Used in the majority of Materials Project, AFLOW, and NOMAD entries.[^40]
**Maintained**: Active — version 6.6.0 released.
**License**: Commercial — **Class D**. Academic licenses approximately EUR 5,000; commercial licenses separately priced. Outputs are yours to commercialise, but the tool itself requires a paid license.
**Python API**: Via pymatgen/vasprun.xml parsing; no official Python API from VASP Software GmbH. AiiDA-VASP plugin provides workflow automation.
**GPU support**: Yes (CUDA).
**Performance**: Gold standard for hybrid functional and GW calculations; fastest for those specific tasks.
**Commercialisability of outputs**: Full, but tool access requires a commercial license.
**Note**: VASP training data (MP database entries) was computed with VASP — accessing those results does not require a VASP license.

#### ABINIT 10.x
**What it does**: Full-featured DFT + TDDFT + GW + DFPT code. Strong in response function calculations (phonons, dielectric response, Raman spectra). Widely used for phonon and electron-phonon coupling calculations critical for thermoelectric and superconductor modelling.
**License**: GPL v3 — **Class B**.
**Python API**: AiiDA-ABINIT plugin; abipy Python library for analysis.
**GPU support**: Limited.
**Commercialisability of outputs**: Full.

#### FHI-aims
**What it does**: All-electron full-potential DFT code based on numeric atom-centred orbitals. Best-in-class accuracy for isolated molecules and surfaces; used as reference for benchmark datasets.
**License**: Free for academics under registration; commercial use requires negotiation — **Class C/E**. The license situation is ambiguous for commercial use.
**Python API**: Via FHI-vibes workflow package; AiiDA-FHI-aims.
**Commercialisability of outputs**: Requires license clarification.

#### PySCF (highlight for Zer0pa): The only major QM code that is a pure Python library, MIT/Apache-compatible in practice, and directly connectable to LLM tool-calling without subprocess invocation. For an orchestration-first lab, this is the native integration point for Layer 1.

***

### 3.2 Layer 2: Machine Learning Interatomic Potentials (MLIPs)

The MLIP landscape has undergone a step-change since 2023. The community has converged on **equivariant message-passing neural networks** — architectures that are mathematically invariant to rotation, reflection, and permutation of atoms — as the dominant architecture class. The 2024–2025 benchmark competition (MLIP Arena, Matbench Discovery, LAMBench) has established a clear performance hierarchy.[^41][^42][^43][^44][^45]

#### MACE-MPA-0 (Cambridge / ACEsuit)
**What it does**: Equivariant message-passing neural network trained on the MPtrj dataset (Materials Project DFT-MD trajectories) + OMat24 (Meta Open Materials 2024, 100M+ structures). Currently one of the top-performing universal MLIPs on Matbench Discovery leaderboard.[^46][^47][^48]
**Version**: MACE-MPA-0 (released late 2024); current Matbench Discovery ranking confirms state-of-art performance.[^49]
**License**: MIT — **Class A**. Fully commercialisable.
**Python API**: `pip install mace-torch`; direct integration with ASE, LAMMPS, OpenMM.
**GPU support**: Full CUDA via PyTorch backend.
**Performance**: Matbench Discovery F1 ~0.8; strong across diverse chemical space including oxides, halides, intermetallics. Benchmark shows "MACE-MPA-0 becomes the second most accurate FF" for classical force field comparisons; on MOF benchmarks requires fine-tuning for quantitative accuracy.[^50][^48]
**Commercialisability of outputs**: Full — MIT license.
**Fine-tuning**: Documented fine-tuning protocol; fine-tuning on task-specific datasets "enhances accuracy and, in some cases, outperforms models trained from scratch".[^51]

#### Meta UMA (Universal Model for Atoms)
**What it does**: The largest universal MLIP trained to date — on over 500 million unique 3D atomic structures spanning molecules, materials, and catalysts. Presented at NeurIPS 2025. Trained on OMat24 + OMol25 + OC25 + other Meta FAIR datasets.[^52][^53][^54]
**Version**: UMA (NeurIPS 2025); development version also available.
**License**: Commercially permissive — but carries geographic and acceptable-use restrictions. Not fully Class A. Class A† (requires review of specific restrictions before commercial deployment). **License Risk Flag: review UMA license terms before production deployment — geographic restrictions may apply from Sandton / ZA.**[^55]
**Python API**: Via `fairchem` library (Apache 2.0, facebookresearch/fairchem).[^56]
**GPU support**: Full.
**Performance**: Top of benchmarks including OC25; current best on several LAMBench tasks. "Meta FAIR presents UMA, designed to push the frontier of speed, accuracy, and generalization".[^52]
**Commercialisability of outputs**: Requires license review.

#### MatterSim-v1 (Microsoft Research)
**What it does**: Deep learning model for materials simulation across the full periodic table, 0–5000 K temperature range, and 0–1000 GPa pressure range. Based on M3GNet architecture. Released as open-source in July 2025 and available on Azure AI Catalog.[^57][^58][^59][^60][^61]
**Version**: MatterSim-v1.0.0-1M (fast) and MatterSim-v1.0.0-5M (accurate).
**License**: MIT — **Class A**. Fully commercialisable.
**Python API**: `pip install mattersim`; direct ASE integration.
**GPU support**: Full.
**Performance**: "Up to ten-fold enhancement in precision compared to the prior best-in-class" at time of arxiv submission (May 2024); achieves first-principles accuracy for lattice dynamics, mechanical, and thermodynamic properties.[^62]
**Commercialisability of outputs**: Full.
**MatterSim + MatterGen together**: Microsoft's integrated approach — MatterGen generates novel candidates; MatterSim validates their properties — is the most integrated commercial-grade discovery stack.[^63]

#### CHGNet
**What it does**: Crystal Hamiltonian Graph Neural Network — universal MLIP that also predicts magnetic moments, making it uniquely capable for magnetic materials simulation. Trained on Materials Project database. Benchmarked against ab initio data for TMDs (WS2, MoS2) with good agreement after fine-tuning.[^64]
**License**: MIT — **Class A**.
**Python API**: `pip install chgnet`; ASE calculator interface.
**GPU support**: Full.
**Performance**: Strong for magnetics; slightly below MACE-MPA-0 for general chemical space on Matbench Discovery.

#### SevenNet
**What it does**: Efficient equivariant MLIP optimised for low-cost inference. Strong performance-cost trade-off. Placed above MACE in initial Matbench Discovery ranking. Developed at KAIST.[^44][^48]
**License**: MIT — **Class A**.
**Python API**: Yes; ASE/LAMMPS compatible.
**Performance**: "Lighter model[s] such as Orb and SevenNet" show "wider scatter in predictions but are able to capture broader trends" — optimal for screening pipelines where DFT reranking follows.[^65]

#### ORB-v3 (Orbital Materials)
**What it does**: Universal MLIP with commercial backing (Orbital Materials). Designed specifically for industrial deployment with focus on inference speed. Ranked second behind EquiformerV2+DeNS in original Matbench Discovery leaderboard.[^44]
**License**: Apache 2.0 for the model weights, commercial company backing — **Class A** for the open model.
**Python API**: Yes; `pip install orb-models`.

#### MACE-OFF23/24 (Cambridge)
**What it does**: Molecular MLIP (organic molecules in solution, condensed phase). Distinct from MACE-MP-0 which targets inorganic materials. Essential for polymer, drug-excipient, and organic crystal simulations. "Excels at a variety of condensed-phase properties — including peptide dynamics and folding, organic liquid properties".[^66]
**License**: MIT — **Class A**.
**Application**: Layer 2 for organic/molecular systems; bridges to pharma pipeline.

#### The Current MLIP Pareto Front (April 2026)
Based on Matbench Discovery leaderboard, LAMBench, and MOFSimBench: **EquiformerV2 + DeNS > UMA > MACE-MPA-0 > ORB-v3 > SevenNet > MACE-MP-0 > CHGNet** for thermodynamic stability prediction. For compute efficiency at scale: SevenNet and ORB-v3 are preferred for pre-screening; MACE-MPA-0 for production; UMA for highest accuracy with license review.[^67][^68][^44]

***

### 3.3 Layer 3: Thermodynamic Modelling (CALPHAD)

#### pycalphad 0.10
**What it does**: Python library for designing thermodynamic models, calculating phase diagrams, and investigating phase equilibria using the CALPHAD method. Reads standard TDB files (Thermo-Calc Database format). MIT licensed — the only fully open Python CALPHAD engine.[^69][^70][^71]
**Version**: 0.10.x (October 2025 release).
**License**: MIT — **Class A**. Fully commercialisable.
**Python API**: Native Python — `from pycalphad import calculate, equilibrium`.
**GPU support**: No — CPU-based thermodynamic optimisation.
**Performance**: Comparable to commercial software for single/multi-component equilibrium; presented at CALPHAD 2025 as the Python reference implementation.[^72]
**Integration**: Direct coupling to phase field codes; CALPHAD 2025 conference featured pycalphad extensively.[^73]
**Limitation**: Requires TDB thermodynamic database files — open-source TDB files are available for some systems but many commercially important systems (Ni superalloys, Ti alloys) require commercial databases (Thermo-Calc TCNI, TCTI — Class D).

#### OpenCalphad 6.0
**What it does**: Free, open-source thermodynamic calculation software — the most mature open alternative to Thermo-Calc. Supports multicomponent equilibrium, phase diagram calculation, and thermodynamic optimisation. First thermodynamic software with full parallelisation.[^74][^75][^76]
**License**: LGPL — **Class B**. Outputs fully commercialisable.
**Python API**: Via OCASI (OpenCalphad API for Simulation Interface) — C library callable from Python via ctypes.
**Commercialisability of outputs**: Full.

#### Thermo-Calc 2025a
**What it does**: Industry gold standard for CALPHAD calculations. Version 2025a introduces improved microstructure modelling, Noble Metal Alloys Library, and four new databases.[^77][^78]
**License**: Commercial — **Class D**. Academic licenses available.
**Python API**: TC-Python SDK — full Python API for automation.
**Note**: Thermo-Calc thermodynamic databases (SSUB, TCFE, TCNI) are required for industrial alloy systems and are available only commercially. The TDB format is an open standard but high-quality databases carry commercial licenses.

#### PANDAT
**What it does**: Commercial CALPHAD software for multicomponent phase diagram calculation, with strong solidification modelling.
**License**: Commercial — **Class D**.
**Strategic note**: For an orchestration pipeline, pycalphad (MIT) provides the programmatic engine; TDB databases are the commercial bottleneck. Acquiring appropriate TDB files is the single most impactful commercial investment for Layer 3.

***

### 3.4 Layer 4: Mesoscale Microstructure Simulation

#### PRISMS-PF 2.4 (University of Michigan)
**What it does**: Open-source, massively parallel finite element phase field code. Implements Allen-Cahn, Cahn-Hilliard, and coupled PDE systems for grain growth, solidification, spinodal decomposition, and precipitate evolution. Benchmarked as 12x faster than finite difference implementations for equivalent problems.[^79][^80][^8]
**Version**: 2.4 (GitHub, active maintenance).
**License**: LGPL — **Class B**. Outputs fully commercialisable.
**Python API**: No native Python API — C++ with input scripts. Python post-processing via VTK reader libraries.
**GPU support**: Limited; primary acceleration via MPI parallelisation.
**Performance**: Best open-source option for quantitative phase field simulation; comparable to commercial (MICRESS) for solidification benchmarks.[^9]
**Integration**: CALPHAD coupling via pycalphad for thermodynamic driving forces.

#### MOOSE Framework + MARMOT (Idaho National Laboratory)
**What it does**: Multiphysics Object-Oriented Simulation Environment — a general-purpose finite element framework with specific phase field application modules. MARMOT is the nuclear fuels microstructure module; the phase field module is widely used for general materials applications.[^81]
**License**: LGPL — **Class B**.
**Python API**: Python bindings via MOOSE's hit input system; extensive Python scripting for parameter studies.
**GPU support**: Limited.
**Performance**: Extremely flexible — can couple phase field to mechanics, heat transfer, and species diffusion in a single simulation. Best choice when multi-physics coupling is required.

#### SPPARKS (Sandia National Laboratories)
**What it does**: Parallel kinetic Monte Carlo (kMC) simulator for grain growth, surface deposition, reaction kinetics, and recrystallisation. The standard open-source kMC engine for mesoscale materials simulation.[^82][^83][^84][^85]
**Version**: Active — maintained by Sandia; April 2026 confirmed active status.[^84]
**License**: GPL v2 — **Class B**. Outputs fully commercialisable.
**Python API**: Limited — primarily CLI + input scripts. Python post-processing via custom scripts.
**GPU support**: Limited.
**Integration**: Couples to LAMMPS (same Sandia ecosystem) for hybrid kMC-MD approaches.

#### ParaDiS (Lawrence Livermore National Laboratory)
**What it does**: Parallel Dislocation Simulator — the primary open-source code for dislocation dynamics simulation of plastic deformation in crystalline metals. Critical for predicting yield strength, work hardening, and creep in alloys.
**License**: BSD — **Class A**.
**Python API**: No native Python API.
**GPU support**: Limited.

#### PINNs-MPF (Research Tool, 2025)
**What it does**: Physics-Informed Neural Network framework for multi-phase-field problems. Solves phase field PDEs using neural networks rather than finite elements, potentially enabling mesh-free simulation and inverse problem solving.[^11][^12][^10]
**Status**: Research code — GitHub available (SFETNI/PINNs_MPF), MIT-ish license. Not production-grade.
**Strategic signal**: The exact cellular automata ↔ phase field ↔ PINN convergence that Zer0pa's philosophy predicts. A PINN that solves Allen-Cahn equations is simultaneously: a physics simulator, a differentiable ML model, and a continuous cellular automaton. This is the deepest cross-domain convergence in the materials stack. **Build or contribute to this.**

***

### 3.5 Layer 5: Continuum / Process Simulation

#### FEniCSx 0.9 (FEniCS Project)
**What it does**: Python-based finite element library for solving arbitrary PDE systems expressed in weak form (UFL — Unified Form Language). The most programmable open FEM toolkit — PDEs are written in near-mathematical notation.[^86][^87]
**Version**: 0.9.x (active development).
**License**: LGPL — **Class B**. Outputs fully commercialisable.
**Python API**: Native Python — `from dolfinx import fem, mesh`. The primary interface.
**GPU support**: Limited; primarily CPU-based with MPI parallelisation.
**Performance**: Best-in-class for custom PDE formulations; slower than commercial (Abaqus) for standard mechanical analysis.
**Integration**: Can be coupled to MOOSE workflows; VTK output for visualisation.[^88]

#### deal.II 9.7
**What it does**: C++ finite element library supporting adaptive mesh refinement, parallel computing, and a wide range of PDE types. Version 9.7 released 2025.[^88]
**License**: LGPL — **Class A** (LGPL with full commercial output rights).
**Python API**: Indirect via Python wrappers; primarily C++ library.
**GPU support**: Yes (CUDA/HIP via Trilinos backend).

#### OpenFOAM (CFD for Process Simulation)
**What it does**: Finite volume CFD solver for fluid dynamics — relevant for solidification (melt pool dynamics), spray drying, powder bed dynamics, and casting process simulation.
**License**: GPL — **Class B**.
**Python API**: Via PyFOAM or OpenFOAM Python bindings.
**Integration**: Coupling to phase field codes for solidification simulation.

***

### 3.6 Layer 6: Generative Discovery

#### MatterGen 1.0 (Microsoft Research)
**What it does**: Diffusion-based generative model for inorganic crystal structure generation across the periodic table. Published in Nature January 2025 — the first generative model with rigorous benchmarking of conditional generation under property constraints.[^89][^90][^91][^14]
**Architecture**: Equivariant diffusion model that jointly generates atom types, fractional coordinates, and unit cell lattice vectors. Uses periodic E(3)-equivariant denoising.
**Training data**: Materials Project (CC-BY-4.0) + experimental crystal databases.
**License**: MIT on GitHub (microsoft/mattergen) — **Class A**. Fully commercialisable.[^89]
**Python API**: `pip install mattergen`; Hugging Face model card available.[^90]
**GPU support**: Required for training; inference on GPU.
**Performance**: Generates stable, diverse materials across the periodic table; fine-tunable to specific property constraints (bulk modulus, magnetic density, chemical system). A critical April 2026 preprint notes that a significant fraction of MatterGen-generated novel structures correspond to training data compounds predicted in different representations — an important validation caveat. Novel generation capability confirmed but must be combined with DFT validation.[^92]
**Commercialisability of outputs**: Full — generated structures are outputs, not derivatives of the model code.

#### DiffCSP (Rui Jia et al., NeurIPS 2023)
**What it does**: Crystal Structure Prediction by joint equivariant diffusion — simultaneously generates lattice and atomic coordinates using periodic-E(3)-equivariant denoising. Trained on Materials Project structures.[^93]
**License**: MIT — **Class A**.[^94]
**Python API**: GitHub (jiaor17/DiffCSP); requires GPU.
**Performance**: Strong on MP-20 and MPTS-52 benchmarks; a 2026 evaluation on unexplored chemical space found limitations that motivate continued development.[^95]
**Commercialisability of outputs**: Full.

#### CrystaLLM (Nature Communications 2024)
**What it does**: Autoregressive LLM trained on millions of CIF files to generate plausible crystal structures. Treats CIF format as text — structure prediction as language modelling.[^96]
**License**: MIT — **Class A**.
**Python API**: GitHub; requires GPU for generation.
**Intersectional signal**: This model is literally treating crystal structure as a language modelling problem — composition-structure encoding as text compression. This is Zer0pa's information theory lens applied directly.

#### USPEX 10.5 (Oganov Lab)
**What it does**: Universal Structure Predictor: Evolutionary Xtallography — evolutionary algorithm for crystal structure prediction at arbitrary pressure/temperature conditions. Used by 10,600+ researchers worldwide.[^97]
**License**: Free for academic use; **Class C** for commercial applications. Commercial license required for industrial use.
**Python API**: Python scripting interface available.
**Performance**: Gold standard for ab initio crystal structure prediction; combines evolutionary search with DFT energy evaluation.
**Commercialisability of outputs**: Structures generated are yours; tool itself requires commercial license for commercial deployment.

#### CALYPSO
**What it does**: Crystal structure prediction via particle swarm optimisation. Alternative to USPEX with comparable performance.[^98][^99]
**License**: Free for academic use — **Class C**.

#### GNoME Data (Google DeepMind)
**What it does**: 2.2 million crystal structures (380,000 newly stable materials) discovered by DeepMind's GNNs, with DFT-calculated energies. The dataset is available via Matbench Discovery platform.[^100][^101][^102][^103]
**License**: The dataset is available; the GNoME model weights are proprietary — **Class D** for the model. The training data is downloadable but the discovery model itself is not open.[^103]
**Access**: Matbench Discovery data API; `matbench-discovery` Python package.
**Commercial note**: Using the GNoME dataset to train your own models (MACE, DiffCSP) is legitimate under the dataset license.

***

### 3.7 Layer 7: Orchestration and Active Learning

#### AiiDA 2.8 (EPFL / Psi-k Community)
**What it does**: Automated Interactive Infrastructure and Database for Computational Science. Python workflow manager with full provenance tracking, automated error handling, and native integration with DFT codes (QE, VASP, CP2K, ABINIT via plugins).[^104][^105][^106][^4]
**Version**: 2.8.0 (2025 release); v2.7.2 also actively supported.[^104]
**License**: MIT — **Class A**. Fully commercialisable.
**Python API**: Full Python — `from aiida.engine import run, submit`; RabbitMQ + PostgreSQL backend.
**GPU support**: N/A (orchestration layer; individual codes it submits have their own GPU support).
**Performance**: The standard workflow manager for the computational materials science community. OPTIMADE integration available. 150+ code plugins maintained by the community.[^107]
**Commercialisability of outputs**: Full — AiiDA manages provenance; outputs from DFT codes are yours.
**Note**: Interoperability between DFT workflow frameworks was reviewed in February 2026 — AiiDA identified as the dominant choice for provenance-critical workflows.[^4]

#### Atomate2 0.5 (Materials Project Team)
**What it does**: Next-generation workflow library built on top of Jobflow (an Apache-2.0 Python workflow tool). More modular and Pythonic than original atomate. Supports VASP, QE, CP2K, ABINIT, and MLIP substitution (can replace DFT calculators with MLIPs for faster runs).[^108][^109][^110][^3]
**Version**: 0.5.x (RSC paper published July 2025, citing current state).[^108]
**License**: Apache 2.0 — **Class A**.
**Python API**: Full — `from atomate2.vasp.flows import StaticMaker`.
**Unique capability**: "Substituting DFT-based calculators with MLIPs allows faster and cheaper runs, making atomate2 an ideal tool for easily reproducible high-throughput screening". This is the key Layer 1→2 coupling mechanism.[^108]
**Commercialisability of outputs**: Full.

#### pyiron (Max Planck Institute)
**What it does**: Integrated development environment for atomistic simulation workflows. BSD licensed, HPC-native, HDF5-based data storage. Originally materials-focused; now used as general-purpose HPC workflow manager.[^111][^112][^113][^114][^115]
**Version**: Active development; April 2026 PyPI confirmed active.[^114]
**License**: BSD — **Class A**.
**Python API**: Full — `from pyiron_atomistics import Project`.
**Unique capability**: Jupyter-notebook-native workflow design; tight integration with LAMMPS and VASP; HDF5 provenance storage without external database dependency.
**Commercialisability of outputs**: Full.

#### BoTorch + Ax (Meta FAIR)
**What it does**: BoTorch is a PyTorch-based Bayesian optimisation library; Ax is the higher-level platform for sequential experimentation. Together they form the primary open-source stack for active learning in materials discovery.[^116][^117]
**License**: MIT — **Class A**.
**Python API**: Full — `pip install botorch ax-platform`.
**Performance**: "State-of-the-art MC acquisition functions, GPU acceleration, auto-differentiation". Used by Argonne National Laboratory for materials screening.[^118][^116]
**Application**: Directly implements the self-driving lab loop: propose candidate → simulate → update surrogate model → propose next candidate.
**Commercialisability of outputs**: Full.

#### OpenAD (IBM Research, 2024)
**What it does**: Open Accelerated Discovery — open-source Python toolkit for molecular and materials discovery. Wraps RXN for Chemistry (reaction prediction), GT4SD (generative models), and multiple property prediction services with a unified CLI and Python API.[^119][^120][^121][^122]
**License**: Apache 2.0 — **Class A**.
**Python API**: Full.
**Integration**: Designed explicitly for agent-style use — provides a workspace (molecular working set), tool dispatch, and result management compatible with LLM tool-calling.[^123][^121]
**Note**: Bridges the pharma (drug discovery) and materials pipelines — wraps tools from both domains.

***

## Section 4: Dataset and Database Catalogue

### 4.1 Primary Structural and Property Databases

| Database | Size | Access | License | ML-Ready | Key Property Coverage |
|----------|------|--------|---------|----------|----------------------|
| **Materials Project** | 154,000+ compounds, 530,000+ calculations | REST API (next-gen.materialsproject.org/api) + OPTIMADE[^124][^125] | CC-BY-4.0 | Yes — pymatgen integration, MPContribs | Band gap, formation energy, elasticity, piezo, dielectric, magnetic |
| **AFLOW** | 3.5M+ compounds | REST API + AFLOWLIB | Customised free access | Partial — AFLOW-ML library | Crystal structure, electronic, thermodynamic, mechanical |
| **OQMD** | 1.2M+ DFT calculations | REST API (oqmd.org/download) | CC-BY-4.0 | Yes — qmpy Python library | Formation energy, stability, band structure |
| **NOMAD** | 15M+ calculations, largest materials DFT archive | REST API (nomad-lab.eu) + OPTIMADE[^126] | CC-BY-4.0 | AI Toolkit with Jupyter notebooks | All properties from DFT code output |
| **JARVIS-DFT** | 80,000+ 3D + 1,000 2D structures | API + bulk download + OPTIMADE[^127][^128][^129] | Public domain (NIST) | Yes — jarvis-tools Python library, MatBench integration | 40+ properties including topological, thermoelectric, magnetic |
| **Alexandria** | 4.5M+ structures (PBE + HSE) | Bulk download (alexandria.icams.rub.de) + OPTIMADE[^130][^131] | CC-BY-4.0 | Partial | Formation energy at multiple DFT levels; OMat24 based on Alexandria |
| **COD (Crystallography Open Database)** | 500,000+ experimental crystal structures | REST API + bulk download | CC0 (public domain) | Requires preprocessing (CIF → ML features) | Experimental structures only |
| **ICSD** | 300,000+ experimental structures | Commercial subscription | **Class D** | Requires pymatgen preprocessing | Experimental crystal structures, most complete experimental database |
| **GNoME** | 2.2M structures (380k stable) | Via Matbench Discovery[^100] | Custom (data public) | Yes — matbench-discovery package | DFT energies/forces; new stable materials |
| **OMat24** | 110M+ DFT calculations | Download via fairchem[^132][^133] | CC-BY-4.0 | Yes — fairchem/OMat24 loader | Energies, forces, stresses for diverse inorganic materials |
| **OMol25** | 100M+ molecular DFT calculations | Download via LBNL/fairchem[^54][^134] | CC-BY-4.0 | Yes — UMA pre-trained on it | Molecular chemistry, electrolytes, biomolecules |
| **OC25** | Large-scale solid-liquid catalysis | Open Catalyst Project[^26][^27][^135] | CC-BY-4.0 | Yes — fairchem loaders | Solid-liquid interface catalysis, adsorption energies |
| **Matbench** | 13 property prediction tasks | Python (pip install matbench) | MIT | Yes — standardised splits and metrics | Band gap, formation energy, refractive index, Tc, etc. |
| **Matbench Discovery** | Crystal stability prediction leaderboard | Python (pip install matbench-discovery) | MIT | Yes — structured evaluation framework | Thermodynamic stability for new structure prediction |
| **JARVIS-Leaderboard** | Multi-task ML benchmark | jarvis.nist.gov/benchmarks | Public domain | Yes — includes thermoelectric, topological, QMC tasks[^136] | 40+ property prediction benchmarks |

### 4.2 OPTIMADE: The Universal Materials Database API
OPTIMADE v1.2 is the REST API specification that unifies access across all major databases. A single OPTIMADE-compliant query can simultaneously query Materials Project, AFLOW, JARVIS, NOMAD, Alexandria, COD, OQMD, and others via a federated protocol. The `optimade-python-tools` package implements the full v1.2 spec with pymatgen adapter for structure conversion. This is the universal data transport layer for Layer 7 orchestration.[^137][^138][^139][^140][^141][^142]

```python
from optimade.client import OptimadeClient
client = OptimadeClient("https://optimade.materialsproject.org")
structures = client.get("/structures?filter=elements HAS ALL 'Li','Fe'")
```

**For Zer0pa**: OPTIMADE is the materials-science equivalent of the ChEMBL API in pharma. Every database query in the pipeline should route through OPTIMADE for maximum portability and future-proofing.

***

## Section 5: Frontier Watch (2024–2026)

*Sorted by strategic significance to an orchestration-first entrant. Emphasis on 2025–2026 developments.*

### 5.1 UMA: A Family of Universal Models for Atoms (Meta FAIR, NeurIPS 2025)
**What broke**: Prior universal MLIPs were trained on ~1–10M structures. UMA was trained on over 500 million unique 3D atomic structures — spanning molecules, materials, and catalysts — making it the first MLIP foundation model trained at language-model scale. Empirical scaling laws were developed for MLIP training analogous to Chinchilla laws for LLMs.[^53][^143][^52]
**Result**: Top performance on OC25 (catalysis), OMol25 (molecular), and Matbench Discovery (materials) simultaneously — a single model competitive across all chemistry domains.
**Access**: Via fairchem Python library. License: commercially permissive with geographic/use restrictions.[^55]
**Strategic implication for Zer0pa**: The MLIP has crossed the same threshold as LLMs in 2020 — a single foundation model that generalises to most chemistry without domain-specific training. The fine-tuning paradigm (pretrain on 500M structures, fine-tune on 1,000 system-specific structures) is now standard.

### 5.2 MatterGen + MatterSim: Microsoft's Integrated Generative-Simulation Stack (Nature 2025, arXiv 2024)
**What broke**: Prior generative models for crystal structures had no property-conditional generation capability. MatterGen introduced property-constrained diffusion — generate a material with bulk modulus > 200 GPa in the Li-Fe-O system.[^14][^63]
**Result**: MatterGen generated novel structures; MatterSim validated properties at near-DFT accuracy. Together they represent a closed-loop generative–validation pipeline from Microsoft Research, both MIT licensed.
**Access**: `pip install mattergen`, `pip install mattersim`. MIT license.
**Caveats**: April 2026 preprint showed that some "novel" MatterGen structures are artefacts of training data representation — true novelty rate requires careful DFT validation.[^92]
**Strategic implication**: The MatterGen → DFT validation → property ranking pipeline is the clearest template for a materials discovery agent.

### 5.3 CLOUD Foundation Model for Crystals (Nature Communications, March 2026)
**What broke**: All prior crystal property prediction models required 3D coordinate information and equivariant architectures. CLOUD uses a **symmetry-consistent string representation** (SCOPE — encoding space group, Wyckoff positions, and elemental compositions as text) enabling Transformer-based language modelling of crystal properties without 3D coordinates.[^144][^145][^146][^147][^148]
**Result**: Pre-trained on millions of crystals via masked language modelling; fine-tuned on 8 MatBench datasets, achieving near-SOTA with a text-only representation. Demonstrates robust scaling with model and data size.
**Access**: GitHub available; Nature Communications paper March 2026.
**Intersectional signal**: CLOUD treats crystal structure as a **language** — the space group + Wyckoff positions are a compact information encoding of the crystal's symmetry class. This is an explicit information-theoretic treatment of structure encoding. For Zer0pa, this model is directly connectable to an LLM reasoning layer without any 3D geometry processing.

### 5.4 OMat24 + OMol25 (Meta FAIR, October 2024 + May 2025)
**What broke**: The training data bottleneck for universal MLIPs. OMat24 contains 110 million DFT calculations on diverse inorganic materials; OMol25 contains 100 million molecular DFT calculations — together the largest open computational chemistry datasets by orders of magnitude.[^132][^54][^134]
**Access**: CC-BY-4.0, downloadable via fairchem.
**Strategic implication**: Both datasets are freely available for training custom MLIPs. The combination OMat24 + OMol25 enables training a universal MLIP covering both crystalline solids and molecular chemistry — the same chemical space relevant to battery electrolytes, drug-material interfaces, and heterogeneous catalysis.

### 5.5 Autonomous Materials Discovery — The A-Lab and LUMI-Lab (2023–2026)
**What broke**: Self-driving labs moved from proof-of-concept to peer-reviewed demonstrations. The A-Lab (UC Berkeley, Nature 2023) demonstrated autonomous solid-state synthesis of 41 predicted compounds, confirming 19 as successfully synthesised in a closed-loop system using GNoME predictions → MLIP screening → robotic synthesis → XRD characterisation. LUMI-lab (Cell 2026) extended this to lipid nanoparticle delivery, autonomously discovering brominated lipids as mRNA delivery enhancers from a 1,700-compound synthesis campaign.[^149][^17][^21]
**The AI stack used**: LUMI-lab used a pretrained foundation model + active learning (Bayesian optimisation) + robotic synthesis. The simulation stack was not DFT-based for LUMI-lab (molecular), but the A-Lab used GNoME DFT data as the prior.
**Strategic implication for Zer0pa**: This is Zer0pa's endgame architecture. The orchestration layer (AiiDA/Atomate2 + BoTorch) feeding generative proposals (MatterGen) to DFT screening (QE/PySCF) to experimental synthesis is now a demonstrated template, not a speculation.

### 5.6 PINNs-MPF: Physics-Informed Neural Networks for Phase Field (2025)
**What broke**: Phase field simulations require mesh generation, time-stepping, and significant numerical engineering. PINNs-MPF demonstrated that physics-informed neural networks can solve the multi-phase-field equations without mesh discretisation, enabling mesh-free microstructure simulation and differentiable forward models suitable for inverse design.[^12][^10][^11]
**A second PINN paper (April 2026)** demonstrated PINN-based phase-field modelling of intergranular fracture.[^150]
**Strategic implication**: A differentiable phase field simulator is a Layer 4 component that can be differentiated end-to-end, enabling gradient-based optimisation of microstructure evolution parameters — directly feeding into a Zer0pa-style generative loop.

### 5.7 MatSciBench and AlchemyBench: LLM Benchmarks for Materials Science (2025)
**What broke**: No rigorous benchmark existed for evaluating LLM reasoning in materials science. MatSciBench introduced 1,340 expert-curated college-level materials science problems across 31 sub-fields. AlchemyBench provided 17K synthesis recipes with LLM-as-judge evaluation for materials synthesis prediction.[^151][^152][^119]
**Results**: Gemini-2.5-Pro achieved under 80% on MatSciBench, "highlighting the complexity of the benchmark". Even frontier models struggle with materials science reasoning.[^119]
**Strategic implication**: There is no GPT-Rosalind equivalent for materials science. The reasoning gap is an open space. A fine-tuned model on MatSciBench + JARVIS + Materials Project knowledge would outperform any current general-purpose model on materials-specific reasoning tasks.

### 5.8 MLIP Arena: Rigorous Benchmark Platform (April 2026)
**What broke**: Prior MLIP benchmarks suffered from data leakage, limited transferability, and over-reliance on static test sets. MLIP Arena, presented at ICLR 2026 (April 22, 2026), evaluates force field performance based on **physics awareness, chemical reactivity, and stability under extreme conditions** — dynamic evaluation rather than static dataset F1 scores.[^41]
**Strategic implication**: Zer0pa's pipeline should include dynamic MLIP evaluation as a quality gate, not just static benchmark ranking.

***

## Section 6: Intersectional Signals

*Each signal maps a Zer0pa existing domain to a specific convergence point in the materials stack.*

### Signal 1: SE(3)/O(3)-Equivariant Architectures — The Crystal ↔ Protein Isomorphism

The same E(3)-equivariant message-passing architectures used in AlphaFold2 (Evoformer) and ESMFold (protein folding) are the dominant architecture class for crystal property prediction. MACE, NequIP, Allegro, and EquiformerV2 all implement SE(3) or O(3) equivariance — not by coincidence but because both crystal graphs and protein structures are geometric objects in 3D Euclidean space where physical properties must transform correctly under rotation.[^43][^153][^32]

**Benchmark confirmed**: E(3)-equivariant capsule networks for crystal property prediction (CGN-e3) explicitly demonstrate that "E(3)-equivariance preserves geometric symmetries" achieving state-of-art on multiple MatBench tasks. The GoeCTP framework generalises O(3)-equivariance to tensor material properties (dielectric, piezoelectric, elasticity tensors).[^154][^43][^32]

**For Zer0pa**: The equivariant neural network architecture expertise developed for pharma (protein structure prediction) translates directly to materials (crystal property prediction). The same SE(3)-transformer code, potentially the same trained model weights (via transfer learning), applies at both layers. MACE is the practical implementation: MIT licensed, `pip install mace-torch`, direct ASE/LAMMPS integration.

### Signal 2: Topological Data Analysis and Persistent Homology for Crystal Materials

Persistent homology — the TDA tool for detecting multi-scale topological features in data — has been applied to crystal structure representation with documented benchmark performance. Atom-Specific Persistent Homology (ASPH) achieves "highly accurate predictions of DFT-calculated formation energy".[^155][^156][^157]

**November 2025 preprint**: ASPH-based ML models were developed for crystal formation energy prediction, explicitly using topological descriptors at the atom level.[^155]

**September 2025 review**: "TDA-based descriptors have been proposed to serve as powerful tools for high-throughput screening of materials with specific topological features... enabling identification of materials with desired properties".[^156]

**The separate topological materials domain**: Z2Pack 2.2.1[^22][^158][^23] computes topological invariants (Z₂, Chern numbers, mirror Chern numbers) from DFT band structures, classifying materials as topological insulators, Weyl semimetals, or trivial. This uses manifold topology applied to quantum mechanical Hamiltonians — the Berry curvature \( \Omega_n(\mathbf{k}) = -2 \text{Im} \langle \partial_{k_x} u_n | \partial_{k_y} u_n \rangle \) is the materials manifestation of the same differential geometric structures Zer0pa works with.

**Toolchain**: QE/VASP → Wannier90 (Wannierisation) → Z2Pack (topological invariant calculation) → property classification. Fully open-source for the Z2Pack leg (GPL).

**For Zer0pa**: Persistent homology descriptors are directly applicable to materials property prediction as a drop-in feature engineering step in Matminer workflows. Z2Pack + JARVIS-DFT topological dataset provides the full stack for topological materials classification — a direct application of geometric computation.

### Signal 3: Information Theory and Crystal Structure as a Channel Problem

The composition-structure-property map in materials science is formally an information channel: composition (input alphabet) → crystal structure (encoding) → material property (output signal). Three recent developments make this explicit:

1. **CLOUD (March 2026)**: Uses a symmetry-aware string representation (SCOPE) that encodes crystal structure as a compact text token — treating the space group + Wyckoff positions as a compressed information representation. The architecture is a masked language model, trained to reconstruct missing tokens in the structural description.[^145][^146][^144]

2. **CrystaLLM (Nature Comms, 2024)**: Explicitly treats CIF files as a language — generating crystal structures by sampling from a trained LM over CIF tokens. The model learns the "grammar" of crystal structures from millions of training examples.[^96]

3. **xtal2png**: Encodes crystal structures as PNG images — mapping atomic coordinates to pixel values in a compact 2D representation readable by image models.[^159]

**Information-theoretic interpretation**: The maximum information about a crystal's properties that can be extracted from its composition is bounded by the mutual information \( I(\text{composition}; \text{properties}) \). Crystal structure is an intermediate encoding that increases this mutual information — the "channel capacity" from composition to properties is increased by knowing the structure. CLOUD and CrystaLLM are both learning this channel mapping implicitly.

**For Zer0pa**: The information-theoretic framing of structure prediction is directly usable. Building on CLOUD's SCOPE representation — treating crystal space groups as a 230-symbol alphabet, Wyckoff positions as word tokens — connects directly to information-theoretic analysis of crystal symmetry. A materials-specific LLM fine-tuned on SCOPE-encoded structures would simultaneously be a crystal structure modeller and a channel-capacity analyser.

### Signal 4: Renormalisation Group Methods at the Machine Learning ↔ Phase Transition Boundary

The renormalisation group (RG) — developed by Wilson to describe how physical descriptions change across scales — has an exact information-theoretic interpretation: RG transformations are coarse-graining operations that maximise preserved mutual information. This connection between RG and machine learning was recognised as early as 2015 and is now confirmed at multiple levels:

**January 2026**: Machine-Learned Renormalization-Group-Improved Gauge Actions — using ML to learn improved RG actions in lattice field theory. A direct application of ML to the scale-bridging problem in quantum field theory.[^160]

**October 2025**: "Renormalization group for deep neural networks: Universality of learning and scaling laws" — demonstrating that RG scaling intervals emerge in neural network learning curves, with quantitative departures from standard RG theory revealed by spectrum discreteness.[^161]

**For materials science**: Phase transitions in materials (ferromagnetic to paramagnetic, liquid to solid, normal to superconducting) are governed by fixed points of the RG flow. Machine learning models that predict phase diagrams are implicitly learning RG-invariant features. Tools for phase transition classification in materials (temperature-composition phase diagrams from CALPHAD; order parameter evolution from phase field) can be interpreted as learning the RG fixed point structure.

**For Zer0pa**: The Landau theory of phase transitions (order parameters, symmetry breaking, free energy functionals) is formally equivalent to information field theory — the free energy is the negative log partition function of the distribution over microstates. Phase diagram prediction from composition and temperature is a classification problem whose decision boundaries are determined by the renormalisation group flow. This is the deepest mathematical connection between statistical mechanics and materials informatics.

### Signal 5: Phase Field as Continuous Cellular Automata — The Turing Morphogenesis Link

The Allen-Cahn equation \( \tau \partial_t \phi = \epsilon^2 \nabla^2 \phi - f'(\phi) \) governing phase field evolution is a reaction-diffusion PDE of exactly the form studied by Turing (1952) for biological pattern formation. The connection is not metaphorical:

- Spinodal decomposition (Cahn-Hilliard equation) produces labyrinthine patterns identical to Turing stripe/spot patterns
- Grain growth simulation in PRISMS-PF produces coarsening dynamics governed by the same universality class as cellular automaton coarsening
- PINNs-MPF (2025) makes this connection explicit — using neural networks to solve phase field equations removes the discretisation that distinguishes continuous PDEs from cellular automata

**SPPARKS** implements kinetic Monte Carlo on lattices that are literal discrete cellular automata — local transition rules producing emergent grain microstructure. The grain growth models in SPPARKS are formally equivalent to Potts model cellular automata studied in computational intelligence.[^82][^84]

**For Zer0pa**: The cellular automata simulation expertise is directly applicable to SPPARKS-style grain growth simulation. More importantly, the PINNs-MPF architecture — a neural network trained to reproduce phase field dynamics — can be trained on SPPARKS data to produce a continuous, differentiable cellular automaton simulator. This is the most direct path from existing Zer0pa capability to materials process simulation.

### Signal 6: Foundation Models for Atomistic Simulation — The Chemistry ↔ Language Scaling Law

A March 2025 perspective paper titled "Foundation Models for Atomistic Simulation of Chemistry and Materials" explicitly asked: "Is a foundational model based on data and parameter scaling laws and pre-training strategies possible for learned simulations of chemistry and materials?" The answer, demonstrated by UMA and MACE-MPA-0, is yes — with the same scaling laws as LLMs.[^162][^163][^164]

**MACE-MP-0's companion paper** (AIP JCP, November 2025) explicitly describes it as "a foundation model for atomistic materials chemistry" — the same framing used for LLMs and protein models. Training on diverse, large datasets enables transfer to new chemical systems with minimal fine-tuning.[^165][^166][^164]

**The analogy to LLMs is precise**: Pre-training on diverse chemical space (OMat24: 110M calculations) → base model learns "chemical grammar" → fine-tune on specific system (100–1000 DFT calculations) → system-specific accuracy. This is GPT-3→GPT-4 fine-tuning applied to atomistic simulation.

**For Zer0pa**: The lab's orchestration infrastructure — designed for managing and routing between foundation models — maps directly to MLIP foundation model management. The workflow is: (1) dispatch to MACE-MPA-0/UMA for zero-shot screening; (2) identify systems where zero-shot error exceeds threshold; (3) dispatch DFT calculations via AiiDA; (4) fine-tune MLIP on new data; (5) re-screen. This is a standard LLM fine-tuning workflow applied to physics simulation.

### Signal 7: Active Learning as Self-Referential Simulation — The Cognitive Theory Connection

Bayesian active learning in materials discovery is formally equivalent to a cognitive agent learning from its environment: the surrogate model (Gaussian Process or MLIP) is the agent's world model, the acquisition function is its reward signal, and the experimental result is the environmental feedback that updates beliefs.

**BoTorch (Meta FAIR)**: Implements this formally — "sequential experimentation" with "sample average approximation optimisation, auto-differentiation, and variance reduction". The knowledge gradient acquisition function is provably optimal for maximising information gain per experiment.[^116]

**The A-Lab closed loop**: DFT screening → experimental synthesis → XRD characterisation → Bayesian update → new candidate generation is precisely a reinforcement learning agent operating in chemical space, using simulations as its model-based environment predictor.[^17]

**For Zer0pa**: The cognitive theory framework (Hebbian learning, predictive coding, belief updating) maps precisely to active learning for materials discovery. The acquisition function in BoTorch is formally equivalent to a reward-modulated learning rule. The lab's cognitive theory background is directly applicable to designing the acquisition strategy for materials discovery campaigns.

***

## Section 7: Integration Architecture

### 7.1 Minimum Viable Orchestrated Materials Pipeline

The following is a fully open-source, commercially deployable minimum viable pipeline for materials discovery, requiring no commercial licenses at the tool level (commercial databases are the bottleneck for specific alloy systems):

```
[Target property specification]
         ↓
[Layer 6: MatterGen (MIT) — conditional crystal generation]
         ↓ CIF files
[Layer 1: PySCF (Apache 2.0) or QE (GPL) — DFT validation]
         ↓ extxyz training data
[Layer 2: MACE-MPA-0 (MIT) — MLIP screening at scale]
         ↓ thermodynamic properties
[Layer 3: pycalphad (MIT) — phase diagram construction]
         ↓ TDB + driving forces
[Layer 4: PRISMS-PF (LGPL) — microstructure simulation]
         ↓ VTK microstructure fields
[Layer 5: FEniCSx (LGPL) — continuum property calculation]
         ↓ macroscale properties
[Layer 7: AiiDA (MIT) + BoTorch (MIT) — orchestration + Bayesian update]
         ↑_______________ active learning loop __________________|
```

**Data handoffs**:
- L6 → L1: CIF format (universal crystal structure)
- L1 → L2: extxyz (energy/force/stress training data)
- L2 → L3: Thermodynamic functions → pycalphad Python API
- L3 → L4: TDB file + interface energies → PRISMS-PF input
- L4 → L5: VTK microstructure → FEniCSx material model
- All ↔ L7: AiiDA provenance graph; BoTorch acquisition function

### 7.2 Best-of-Breed Stack

| Layer | Primary | Alternative | Rationale |
|-------|---------|-------------|-----------|
| Electronic structure | PySCF (Apache 2.0) | Quantum ESPRESSO (GPL) | PySCF for Python-native; QE for large-scale periodic |
| MLIP | MACE-MPA-0 (MIT) | MatterSim-v1 (MIT) | MACE for accuracy; MatterSim for temperature/pressure range |
| CALPHAD | pycalphad (MIT) | OpenCalphad (LGPL) | pycalphad for Python integration; OC for CLI batch |
| Phase field | PRISMS-PF (LGPL) | MOOSE (LGPL) | PRISMS-PF for performance; MOOSE for multi-physics |
| kMC | SPPARKS (GPL) | — | No strong alternative |
| FEM | FEniCSx (LGPL) | deal.II (LGPL) | FEniCSx for Python-native PDE; deal.II for performance |
| Generative | MatterGen (MIT) | DiffCSP (MIT) | MatterGen for property-conditional; DiffCSP for unconditional |
| Workflow | AiiDA (MIT) | Atomate2 (Apache 2.0) | AiiDA for provenance; Atomate2 for ML/DFT mixing |
| Bayesian opt | BoTorch + Ax (MIT) | GPyOpt (BSD) | BoTorch for production; GPyOpt for lightweight |
| Data access | OPTIMADE (open standard) | pymatgen (MIT) | OPTIMADE for federation; pymatgen for local processing |
| Topology | Z2Pack (GPL) | Wannier90 (GPL) | Z2Pack for invariants; Wannier90 for Wannierisation |
| Materials informatics | Matminer (Modified BSD) | Crystal Toolkit (MIT) | Matminer for ML features; Crystal Toolkit for analysis |
| Agent framework | OpenAD (Apache 2.0) | pyiron (BSD) | OpenAD for molecular/materials agents; pyiron for HPC |

### 7.3 Open vs. Commercial Gaps

**Layer 1 (Electronic Structure)**: VASP 6.6.0 (Class D) is faster than all open alternatives for hybrid functional calculations. This matters for high-accuracy benchmarking but not for MLIP training data generation (QE is sufficient). The open-source stack covers 90%+ of use cases.

**Layer 3 (CALPHAD databases)**: The bottleneck is not the software (pycalphad is MIT) but the thermodynamic database files. Open TDB files exist for simple systems (binary Cu-Ag, Al-Cu); industrial alloy TDB files (TCNI9 for Ni superalloys, TCFE11 for steels) are commercial (Thermo-Calc, ~USD 15,000/year). **This is the single unavoidable commercial cost for industrial alloy simulation.**

**Layer 6 (Crystal Structure Prediction)**: USPEX and CALYPSO are Class C (academic only) for commercial use. MatterGen (MIT) is the production-grade open alternative for unconditional generation; DiffCSP (MIT) for structure-from-composition.

**AI Reasoning Layer**: No open-weight model currently matches GPT-4-class reasoning on materials science tasks (MatSciBench top score under 80% even for Gemini-2.5-Pro). Fine-tuning a base model (Llama 3.3 or equivalent) on JARVIS + Materials Project knowledge + MatSciBench is the path to a materials-specific reasoning engine. CLOUD's SCOPE representation could serve as the input tokenisation for such a model.[^119]

### 7.4 Compute Cost Estimates

Based on published benchmark data and literature:

| Task | Tool | GPU-hours per run |
|------|------|-------------------|
| Single DFT calculation (100-atom unit cell) | QE | ~0.1–1 GPU-hour |
| MLIP screening (10,000 structures) | MACE-MPA-0 | ~0.5 GPU-hours total |
| MLIP fine-tuning (1,000 training structures) | MACE fine-tuning | ~2–5 GPU-hours |
| Crystal generation (1,000 candidates) | MatterGen | ~0.5 GPU-hours |
| Phase field simulation (3D, 10^6 voxels, 1μs) | PRISMS-PF | ~10–50 CPU-hours |
| Full pipeline (one target property campaign, 100 candidates) | Combined stack | ~50–100 GPU-hours |

***

## Section 8: Master Tool Selection Table

**Single authoritative reference — all layers, top 3 tools, license class, outputs commercialisable**

| Layer | Function | Tool | Version (Apr 2026) | License | Outputs Commercialisable | Python API | GPU | Integration |
|-------|----------|------|--------------------|---------|-------------------------|------------|-----|-------------|
| **L1** | DFT (periodic) | Quantum ESPRESSO | 7.4 | B (GPL) | ✓ | Via AiiDA/Atomate2 | ✓ | AiiDA, Atomate2, pymatgen |
| **L1** | DFT (Python-native) | PySCF | 2.8 | A (Apache 2.0) | ✓ | Native Python | ✓ | Direct import |
| **L1** | DFT-MD / QM/MM | CP2K | 2025.1 | B (GPL) | ✓ | AiiDA plugin | ✓ | AiiDA-CP2K |
| **L1** | DFT (commercial, hybrid) | VASP | 6.6.0 | D | ✓ | pymatgen/AiiDA-VASP | ✓ | pymatgen parser |
| **L1** | Topological invariants | Z2Pack | 2.2.1 | B (GPL) | ✓ | Full Python | ✗ | Wannier90 |
| **L2** | Universal MLIP (accuracy) | MACE-MPA-0 | 2024 | A (MIT) | ✓ | mace-torch | ✓ | ASE, LAMMPS |
| **L2** | Universal MLIP (temp/P range) | MatterSim-v1 | 1.0.0 | A (MIT) | ✓ | mattersim | ✓ | ASE |
| **L2** | Universal MLIP (catalysis) | Meta UMA / fairchem | NeurIPS 2025 | A† (permissive+restrictions) | Requires review | fairchem | ✓ | ASE, LAMMPS |
| **L2** | Universal MLIP (magnetics) | CHGNet | 0.3.x | A (MIT) | ✓ | chgnet | ✓ | ASE |
| **L2** | Universal MLIP (fast screening) | SevenNet | Current | A (MIT) | ✓ | sevennet | ✓ | ASE |
| **L2** | MD engine (classical/MLIP) | LAMMPS | 2024.x | B (GPL) | ✓ | lammps Python | ✓ | MACE, SevenNet, CHGNet |
| **L3** | CALPHAD (Python) | pycalphad | 0.10 | A (MIT) | ✓ | Native | ✗ | Direct import |
| **L3** | CALPHAD (CLI) | OpenCalphad | 6.0 | B (LGPL) | ✓ | OCASI → ctypes | ✗ | Python via C bindings |
| **L3** | CALPHAD (commercial) | Thermo-Calc | 2025a | D | ✓ | TC-Python SDK | ✗ | TC-Python |
| **L4** | Phase field (parallel) | PRISMS-PF | 2.4 | B (LGPL) | ✓ | C++ only | Partial | VTK output |
| **L4** | Phase field (multi-physics) | MOOSE | 2025 | B (LGPL) | ✓ | Python scripting | Limited | AiiDA-MOOSE |
| **L4** | Kinetic Monte Carlo | SPPARKS | 2025 | B (GPL) | ✓ | Limited | Limited | LAMMPS |
| **L4** | Dislocation dynamics | ParaDiS | Current | A (BSD) | ✓ | None | Limited | — |
| **L4** | Phase field PINN | PINNs-MPF | 2025 | E (GitHub, unclear) | Review needed | Python/TF | ✓ | DeepXDE |
| **L5** | FEM (Python-native) | FEniCSx | 0.9 | B (LGPL) | ✓ | Native (dolfinx) | Limited | VTK |
| **L5** | FEM (performance) | deal.II | 9.7 | A (LGPL) | ✓ | Python wrappers | ✓ (CUDA) | — |
| **L5** | CFD | OpenFOAM | 2024 | B (GPL) | ✓ | PyFOAM | Limited | — |
| **L6** | Generative (conditional) | MatterGen | 1.0 | A (MIT) | ✓ | Full | ✓ | Hugging Face |
| **L6** | Generative (diffusion CSP) | DiffCSP | NeurIPS 2023 | A (MIT) | ✓ | Full | ✓ | GitHub |
| **L6** | Generative (LLM for CIF) | CrystaLLM | 2024 | A (MIT) | ✓ | Full | ✓ | GitHub |
| **L6** | Traditional CSP | USPEX | 10.5 | C (academic) | ✓ (structures) | Python scripting | ✗ | VASP/QE |
| **L6** | Foundation (crystal text) | CLOUD | Mar 2026 | E (preprint) | Review needed | GitHub | ✓ | Transformer |
| **L7** | Workflow + provenance | AiiDA | 2.8 | A (MIT) | ✓ | Full | N/A | 150+ plugins |
| **L7** | Workflow + MLIP mixing | Atomate2 | 0.5 | A (Apache 2.0) | ✓ | Full | N/A | VASP, QE, MLIPs |
| **L7** | HPC-native workflow | pyiron | Current | A (BSD) | ✓ | Full | N/A | LAMMPS, VASP |
| **L7** | Bayesian optimisation | BoTorch + Ax | Current | A (MIT) | ✓ | Full | ✓ | GPyTorch |
| **L7** | Chemistry/materials agent | OpenAD | 2024 | A (Apache 2.0) | ✓ | Full | N/A | RXN, GT4SD |
| **L7** | Database federation | OPTIMADE (pyopt-tools) | v1.2 | A (MIT) | N/A | Full | N/A | 15+ databases |
| **L7** | ML features | Matminer | Current | A (Modified BSD) | ✓ | Full | N/A | pymatgen |
| **L7** | Structure analysis | pymatgen | 2026.3 | A (MIT) | ✓ | Full | N/A | All databases |

***

## Licensing Risk Flags

1. **Meta UMA**: NeurIPS 2025 poster states "model weights are available with a commercially permissive license (with some geographic and acceptable use restrictions)". The specific geographic restrictions and acceptable use clauses must be reviewed before deploying UMA in a commercial pipeline from South Africa. Use MACE-MPA-0 (MIT, unrestricted) as the default until UMA license is confirmed.[^55]

2. **VASP 6.6.0**: Purchased academic license does not extend to commercial use. A separate commercial license is required. Pricing is not publicly listed; contact VASP Software GmbH.[^167][^40]

3. **FHI-aims**: Free for academic registration but commercial use terms are unclear — **Class C/E**. Avoid in commercial pipeline without explicit license confirmation.[^168]

4. **USPEX/CALYPSO**: Both are free for academic research but explicitly require a commercial license for commercial applications. MatterGen (MIT) is the recommended replacement for commercial workflows.[^97][^98]

5. **GNoME model**: Google DeepMind released the dataset (publicly available) but the GNoME model weights are proprietary and not publicly available. Using the GNoME dataset for training your own model is legitimate; using the GNoME inference API (if offered) would require terms review.[^102]

6. **Thermo-Calc TDB databases**: The pycalphad software (MIT) can read any TDB file, but the TDB files themselves for industrial alloy systems (TCNI, TCFE, TCAL) are commercial property of Thermo-Calc Software. Acquiring a pycalphad + commercial TDB license is the recommended approach for industrial alloy simulation.

7. **PINNs-MPF**: GitHub repository exists (SFETNI/PINNs_MPF) but no explicit license file is present in the repository — **Class E**. Contact authors before commercial deployment.[^12]

8. **CLOUD foundation model**: March 2026 Nature Communications paper; GitHub code status and license not confirmed at time of research — **Class E**. Monitor repository for license update.

9. **SPPARKS GPL v2**: The GPL copyleft license means that if SPPARKS code is modified and distributed as part of a software product, the modified code must be open-sourced. However, running SPPARKS as a computation tool and commercialising the simulation outputs (microstructure predictions) does not trigger GPL requirements — **Class B** interpretation holds.[^83][^82]

---

## References

1. [Materials Informatics Across the Length Scales - arXiv](https://arxiv.org/html/2604.18086v1) - In this Review, we examine how materials informatics is being applied across different length scales...

2. [Principles of Inorganic Materials Design](https://cashmere.io/v/f26HGH) - by John N. Lalena, David A. Cleary, Olivier B.M. Hardouin Duparc  Introduction to Computational Mate...

3. [Atomate2: modular workflows for materials science - RSC Publishing](https://pubs.rsc.org/en/content/articlelanding/2025/dd/d5dd00019j) - This manuscript introduces atomate2, a comprehensive evolution of our original atomate framework, de...

4. [The Interoperability Challenge in DFT Workflows Across ... - Wiley](https://advanced.onlinelibrary.wiley.com/doi/pdf/10.1002/aidi.202500232) - AiiDA (automated interactive infrastructure and database for computational science) is a Python-base...

5. [Principles of Inorganic Materials Design](https://cashmere.io/v/3qcbmp) - by John N. Lalena, David A. Cleary, Olivier B.M. Hardouin Duparc  Crystalline solids began to be stu...

6. [THE CALPHAD METHOD AND ITS ROLE IN MATERIAL AND PROCESS DEVELOPMENT.](http://tecnologiammm.com.br/files/v13n1/v13n1a01.pdf) - ... and manufacturing processes requires the availability of reliable materials data. Commercial all...

7. [A Sublattice Phase-Field Model for Direct CALPHAD Database Coupling](https://arxiv.org/pdf/2103.16603.pdf) - The phase-field method has been established as a de facto standard for
simulating the microstructura...

8. [PRISMS-PF: A general framework for phase-field modeling ... - Nature](https://www.nature.com/articles/s41524-020-0298-5) - A new phase-field modeling framework with an emphasis on performance, flexibility, and ease of use i...

9. [Benchmarking of massively parallel phase-field codes for directional ...](https://www.sciencedirect.com/science/article/pii/S0927025626002399) - We present a detailed benchmark comparing two state-of-the-art phase-field implementations for simul...

10. [PINNs-MPF: A Physics-Informed Neural Network framework for Multi ...](https://www.sciencedirect.com/science/article/pii/S0955799725000888) - We present PINNs-MPF framework, an application of Physics-Informed Neural Networks (PINNs) to handle...

11. [[PDF] PINNs-MPF - OPUS](https://opus4.kobv.de/opus4-bam/files/62974/PINNs_MPF_2025.pdf) - Multi-phase-field (MPF) methods for microstructure modeling have proven to be powerful tools for cap...

12. [SFETNI/PINNs_MPF--a-Physics-Informed-Neural-Network ... - GitHub](https://github.com/SFETNI/PINNs_MPF--a-Physics-Informed-Neural-Network-for-Multi-Phase-Field-problems) - We present an application of Physics-Informed Neural Networks (PINNs) to handle multi-phase-field (M...

13. [Enhancing phase change thermal energy storage material ...](https://www.frontiersin.org/journals/materials/articles/10.3389/fmats.2025.1616233/full) - This paper proposes a hybrid multiscale modeling framework that integrates molecular dynamics (MD) s...

14. [A generative model for inorganic materials design - Nature](https://www.nature.com/articles/s41586-025-08628-5) - In this study, we present MatterGen, a diffusion-based generative model that generates stable, diver...

15. [AI-Accelerated Materials Discovery: How Generative Models, Graph ...](https://www.cypris.ai/insights/ai-accelerated-materials-discovery-in-2025-how-generative-models-graph-neural-networks-and-autonomous-labs-are-transforming-r-d) - Self-driving laboratories (SDLs) or autonomous laboratories combine robotic synthesis, in situ chara...

16. [AI-powered open-source infrastructure for accelerating materials ...](https://www.nature.com/articles/s43246-026-01105-0) - Self-driving laboratories (SDLs) are revolutionizing scientific research by integrating automation, ...

17. [An autonomous laboratory for the accelerated synthesis of novel materials](https://pmc.ncbi.nlm.nih.gov/articles/PMC10700133/) - Nature. 2023 Nov 29;624(7990):86–91. doi: 10.1038/s41586-023-06734-w

# An autonomous laboratory for...

18. [Solid-State Electrolyte Market Set to Reach USD 1,558.19 Million by ...](https://finance.yahoo.com/news/solid-state-electrolyte-market-set-040000863.html) - The U.S. solid-state electrolyte market size is USD 47.36 million in 2025 ... battery materials are ...

19. [Sustainable Battery Materials Market Size and Forecast 2025 to 2034](https://www.precedenceresearch.com/sustainable-battery-materials-market) - The global sustainable battery materials market size is estimated to hit around USD 49.88 billion by...

20. [AI agents for solid electrolytes: opportunities, challenges, and future ...](https://www.oaepublish.com/articles/aiagent.2025.10) - This review summarizes recent progress in integrating machine learning, molecular dynamics, and dens...

21. [AI-powered platform accelerates discovery of new mRNA delivery ...](https://www.eurekalert.org/news-releases/1117549) - Self-driving LUMI-lab system combines AI and robotics to advance design and evaluation of lipid nano...

22. [Overview — Z2Pack 2.2.1 documentation](https://z2pack.greschd.ch) - A tool for calculating topological invariants. The method is based on tracking the evolution of hybr...

23. [Z2Pack: Numerical implementation of hybrid Wannier centers for ...](https://link.aps.org/doi/10.1103/PhysRevB.95.075146) - We apply the method to compute and identify Chern, , and crystalline topological insulators, as well...

24. [[PDF] AI-Guided Two-Dimensional Materials: From Discovery and Property ...](https://papers.ssrn.com/sol3/Delivery.cfm/6314398.pdf?abstractid=6314398&mirid=1) - This review presents a comprehensive overview of the potential of AI-guided 2D materials research, c...

25. [Accelerating Catalyst Materials Discovery With Large Artificial ...](https://onlinelibrary.wiley.com/doi/full/10.1002/anie.202526150) - The integration of artificial intelligence (AI) into catalysis is fundamentally reshaping the resear...

26. [[PDF] The Open Catalyst 2025 (OC25) Dataset and Models for Solid ...](https://arxiv.org/pdf/2509.17862.pdf) - State-of-the-art models trained on the OC25 dataset exhibit energy, force, and solvation energy erro...

27. [Open Catalyst 2025 (OC25) Dataset - Emergent Mind](https://www.emergentmind.com/topics/open-catalyst-2025-oc25-dataset) - The Open Catalyst 2025 (OC25) dataset is a large-scale, open-access resource designed to accelerate ...

28. [Accelerating CALPHAD-based Phase Diagram Predictions in Complex Alloys
  Using Universal Machine Learning Potentials: Opportunities and Challenges](http://arxiv.org/pdf/2411.15351.pdf) - Accurate phase diagram prediction is crucial for understanding alloy
thermodynamics and advancing ma...

29. [Machine-learning-assisted design of high-hardness high-entropy ...](https://www.sciencedirect.com/science/article/pii/S0264127526003059) - This paper collects a dataset of multi-component alloys and hardness data composed of seven elements...

30. [Machine Learning-Based Computational Design Methods for High ...](https://scholars.cityu.edu.hk/en/publications/machine-learning-based-computational-design-methods-for-high-entr/) - High-entropy alloys (HEAs) have attracted much attention due to their excellent properties and wide ...

31. [Integrated simulation framework for metal additive manufacturing](https://www.sciencedirect.com/science/article/abs/pii/S2352492825017180) - Laser Powder Bed Fusion is an advanced additive manufacturing technique characterized by its complex...

32. [Equivariant Graph Neural Networks for Prediction of Tensor Material ...](https://arxiv.org/abs/2406.03563) - Modern E(3)-Equivariant networks may be used to predict rotationally equivariant properties, includi...

33. [Machine learning for predictive design and optimization of high ...](https://www.oaepublish.com/articles/jmi.2025.18) - The Seebeck coefficient ( S ), a critical parameter governing thermoelectric energy conversion effic...

34. [Machine learning for next-generation thermoelectrics - ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S2468606924002120) - This review investigates the transformative role of machine learning in accelerating material discov...

35. [Interpretable machine learning for thermoelectric materials design ...](https://www.nature.com/articles/s41598-026-44723-x) - AI-driven ensemble learning for accurate Seebeck coefficient prediction in half-Heusler compounds ba...

36. [Quantum Espresso - Advancing quantum simulations of materials for ...](https://www.quantum-espresso.org) - Quantum ESPRESSO is an integrated suite of Open-Source computer codes for electronic-structure calcu...

37. [Quantum ESPRESSO for GPU](https://www.quantum-espresso.org/quantum-espresso-for-gpu/) - The first GPU-enabled beta release of Quantum ESPRESSO is available for download. Further informatio...

38. [Open-Source Machine Learning in Computational Chemistry](https://pmc.ncbi.nlm.nih.gov/articles/PMC10430767/) - ...approaches. For each project, we provide a short description, the link to the code, the accompany...

39. [Principles of Inorganic Materials Design](https://cashmere.io/v/VlWyz3) - by John N. Lalena, David A. Cleary, Olivier B.M. Hardouin Duparc  a few hundreds of atoms during hun...

40. [VASP - Vienna Ab initio Simulation Package](https://www.vasp.at) - 6.6.0 ... A new version of VASP is available now! Have a look at the list of new features and improv...

41. [MLIP Arena: Advancing Fairness and Transparency in Machine ...](https://openreview.net/forum?id=SAT0KPA5UO) - We introduce MLIP Arena, a benchmark platform that evaluates force field performance based on physic...

42. [LAMBench: a benchmark for large atomistic models - Nature](https://www.nature.com/articles/s41524-025-01929-3) - Utilizing LAMBench, we assessed the performance of ten leading LAMs released before August 1, 2025, ...

43. [Capsule graph networks for accurate and interpretable crystalline ...](https://pmc.ncbi.nlm.nih.gov/articles/PMC12865943/) - The key contributions of this work are threefold: First, We design an E(3)-Equivariant message passi...

44. [Matbench Discovery -- A framework to evaluate machine learning crystal stability predictions](https://www.semanticscholar.org/paper/65ee42147f1cdd7eb04160d6a9f9552f981901b3) - The rapid adoption of machine learning (ML) in domain sciences necessitates best practices and stand...

45. [PDEBENCH: An Extensive Benchmark for Scientific Machine Learning](https://arxiv.org/pdf/2210.07182.pdf) - ...with popular machine learning models (FNO,
U-Net, PINN, Gradient-Based Inverse Method). PDEBench ...

46. [models/mace-mpa-0 - Matbench Discovery](https://matbench-discovery.materialsproject.org/models/mace-mpa-0) - MACE is a higher-order equivariant message-passing neural network for fast and accurate force fields...

47. [MACE foundation models (MP, OMAT, mh-1) - GitHub](https://github.com/ACEsuit/mace-foundations) - This repository contains the MACE pre-trained foundation models for materials chemistry, parameteris...

48. [Comparing Classical and Machine Learning Force Fields for ...](https://pubs.acs.org/doi/10.1021/acs.jpcc.5c04020) - While the MAEs decrease, the ranking of the MLFFs remains similar, except for MACE-MPA-0, which beco...

49. [A new reference model for machine-learning–driven materials ...](https://nccr-marvel.ch/highlights/COSMO-Matbench-Discovery) - The Matbench Discovery leaderboard has long been dominated by models developed at Meta, which can de...

50. [MOFSimBench: evaluating universal machine learning interatomic ...](https://www.nature.com/articles/s41524-025-01872-3) - This brings the main comparison set to nine universal models and MACE-MP-MOF0. Results for all 20 mo...

51. [A Study on the Fine-Tuning Performance of Universal Machine ...](https://arxiv.org/html/2506.07401v1) - In this work, we evaluate the fine-tuning performance of two MACE-based foundation models, MACE-MP-0...

52. [[2506.23971] UMA: A Family of Universal Models for Atoms - arXiv](https://arxiv.org/abs/2506.23971) - Meta FAIR presents a family of Universal Models for Atoms (UMA), designed to push the frontier of sp...

53. [UMA: A Family of Universal Models for Atoms | Research - AI at Meta](https://ai.meta.com/research/publications/uma-a-family-of-universal-models-for-atoms/) - Meta FAIR presents a family of Universal Models for Atoms UMA, designed to push the frontier of spee...

54. [Exploring Meta's Open Molecules 2025 (OMol25) & Universal ...](https://www.rowansci.com/blog/exploring-open-molecules-2025) - Meta's Fundamental AI Research (FAIR) team released Open Molecules 2025 (OMol25), a massive dataset ...

55. [NeurIPS Poster UMA: A Family of Universal Models for Atoms](https://neurips.cc/virtual/2025/poster/117891) - UMA model weights are available with a commercially permissive license (with some geographic and acc...

56. [facebookresearch/fairchem: FAIR Chemistry's library of ... - GitHub](https://github.com/facebookresearch/fairchem) - UMA models and legacy inorganic bulk models trained using OMat24 are trained with DFT and DFT+U tota...

57. [MatterSim: A Deep Learning Atomistic Model Across Elements, Temperatures
  and Pressures](https://arxiv.org/html/2405.04967v1) - Accurate and fast prediction of materials properties is central to the
digital transformation of mat...

58. [MatterSim: A deep-learning model for materials under real-world ...](https://www.microsoft.com/en-us/research/blog/mattersim-a-deep-learning-model-for-materials-under-real-world-conditions/) - A deep-learning model for accurate and efficient materials simulation and property prediction over a...

59. [Welcome to the MatterSim Documentation!](https://microsoft.github.io/mattersim/) - MatterSim is an advanced deep learning model designed to simulate the properties of materials across...

60. [MatterSim | Early-Stage AI Experiments & Prototypes](https://labs.ai.azure.com/projects/mattersim/) - MatterSim is a deep learning model for accurate and efficient materials simulation and property pred...

61. [MatterSim - AI Model Catalog | Microsoft Foundry Models](https://ai.azure.com/catalog/models/MatterSim) - The MatterSim model is intended for property predictions of materials. Direct Use. The model is used...

62. [[2405.04967] MatterSim: A Deep Learning Atomistic Model Across ...](https://arxiv.org/abs/2405.04967) - We present MatterSim, a deep learning model actively learned from large-scale first-principles compu...

63. [Artificial Intelligence-Driven Materials Design for Next-Generation ...](https://pubs.acs.org/doi/10.1021/acssuschemeng.6c01084) - MatterGen generates novel material candidates, while MatterSim simulates their properties, significa...

64. [Benchmarking CHGNet Universal Machine Learning Interatomic ...](https://arxiv.org/abs/2509.08498) - In this study, we use the CHGNet uMLIP to model thermal disorder in isostructural layered 2Hc-WS2 an...

65. [Challenges and Opportunities of Pretrained Machine Learning ...](https://pubs.acs.org/doi/10.1021/acscatal.5c08945) - While lighter models, such as Orb and SevenNet, exhibit a wider scatter in their predictions, they a...

66. [Long-Range Forces and Neural Network Potentials - Corin Wagen](https://cwagen.substack.com/p/long-range-forces-and-neural-network) - The MACE-OFF23 and MACE-OFF24 models excel at a variety of condensed-phase properties—including pept...

67. [Matbench Discovery A framework to evaluate machine learning ...](https://arxiv.org/html/2308.14920v3) - Our initial results rank models by test set F1 scores for thermodynamic stability prediction: Equifo...

68. [[PDF] A framework to evaluate machine learning crystal stability predictions](https://perssongroup.lbl.gov/papers/Riebesell_et_al-2025-Nature_Machine_Intelligence.pdf) - The top models are UIPs which we establish to be the best meth- odology for ML-guided materials disc...

69. [pycalphad - PyPI](https://pypi.org/project/pycalphad/0.1.1/) - pycalphad is a free and open-source Python library for designing thermodynamic models, calculating p...

70. [pycalphad, a library for the CALculation of PHAse Diagrams - GitHub](https://github.com/pycalphad/pycalphad) - pycalphad is a free and open-source Python library for designing thermodynamic models, calculating p...

71. [PyCalphad](http://pycalphad.org/docs) - pycalphad is a Python library for computational thermodynamics using the CALPHAD method. The latest ...

72. [PyCalphad - CALPHAD 2025](https://calphad2025.org/?page_id=383) - PyCalphad is a free and open-source Python library for calculating phase diagrams, designing thermod...

73. [Open Source Software - calphad.com](https://calphad.com/open_source_software/) - A Python-based open-source package that offers a programmable interface for CALPHAD calculations. It...

74. [The OpenCalphad thermodynamic software interface.](https://pmc.ncbi.nlm.nih.gov/articles/PMC5329768/) - ...assumed for creating the lookup table. Speed and accuracy requires that thermodynamic software is...

75. [OpenCalphad](https://www.opencalphad.com) - OpenCalphad is an informal international collaboration of scientists and researchers interested in t...

76. [[PDF] OpenCalphad - a free thermodynamic software - CORE](https://files01.core.ac.uk/download/pdf/302363752.pdf) - Licenses for commer- cial thermodynamic software are expensive and may not be available for the requ...

77. [CALPHAD Software and Databases](https://thermocalc.com/products/) - Thermo-Calc Software's CALPHAD software and databases allow you to make thermodynamic calculations t...

78. [Thermo-Calc 2025a Available Now](https://thermocalc.com/news/thermo-calc-2025a-release-overview/) - Thermo-Calc 2025a introduces an improved ability to model microstructure, a Noble Metal Alloys Libra...

79. [PRISMS-PF: An Open-Source Phase-Field Modeling ... - GitHub](https://github.com/prisms-center/phaseField) - PRISMS-PF is a powerful, massively parallel finite element code for conducting phase field and other...

80. [PRISMS-PF - GitHub Pages](https://prisms-center.github.io/phaseField/) - PRISMS-PF is a powerful, massively parallel finite element code for conducting phase field and other...

81. [Problem Set-Up — Phase Field Method Recommended Practices](https://pages.nist.gov/pf-recommended-practices/bp-guide-gh/ch5-problem-setup.html) - The purpose of this page is to give guidance on some of the important considerations when setting up...

82. [Stochastic Parallel PARticle Kinetic Simulator (Software) | OSTI.GOV](https://www.osti.gov/biblio/code-44868) - Short Name / Acronym: SPPARKS ; Site Accession Number: SCR# 1139.0 ; Software Type: Scientific ; Lic...

83. [SPPARKS Kinetic Monte Carlo Simulator](https://spparks.github.io) - SPPARKS is distributed as an open source code under the terms of the GPL, or sometimes by request un...

84. [SPPARKS: Mesoscale Model for Simulating Microstructural ...](https://www.energy.gov/cmei/h2awsm/spparks-mesoscale-model-simulating-microstructural-evolution-materials) - Open source code available under a GPL license. Benefit. Investigating and modeling mesoscale behavi...

85. [SPPARKS – Center for Computing Research (CCR)](https://www.sandia.gov/ccr/software/spparks/) - SPPARKS is a parallel Monte Carlo code for on-lattice and off-lattice models that includes algorithm...

86. [[PDF] Expressing general constitutive models in FEniCSx using external ...](https://jtcam.episciences.org/16616/pdf) - The software framework and fully documented examples are available as supplementary material under t...

87. [FEniCS | FEniCS Project](https://fenicsproject.org) - FEniCS is a popular open-source computing platform for solving partial differential equations (PDEs)...

88. [[PDF] The deal.II Library, Version 9.7, 2025 - OSTI](https://www.osti.gov/servlets/purl/3006478) - deal.II is an object-oriented finite element library used around the world in the development of fin...

89. [Official implementation of MatterGen -- a generative model ... - GitHub](https://github.com/microsoft/mattergen) - MatterGen is a generative model for inorganic materials design across the periodic table that can be...

90. [README.md · microsoft/mattergen at main - Hugging Face](https://huggingface.co/microsoft/mattergen/blob/main/README.md) - MatterGen is a generative model for inorganic materials design. It is a diffusion model which jointl...

91. [MatterGen: a generative model for inorganic materials design - arXiv](https://arxiv.org/abs/2312.03687) - Here, we present MatterGen, a model that generates stable, diverse inorganic materials across the pe...

92. [MatterGen predicts compounds from the training dataset](https://pubs.rsc.org/en/content/articlehtml/2026/mh/d6mh00268d) - In January 2025, Zeni et al. revealed MatterGen, a diffusion-based generative model trained on both ...

93. [Crystal Structure Prediction by Joint Equivariant Diffusion](https://arxiv.org/abs/2309.04475) - ...symmetries, this paper proposes DiffCSP, a novel diffusion model to learn the
structure distribut...

94. [jiaor17/DiffCSP: [NeurIPS 2023] The implementation for the ... - GitHub](https://github.com/jiaor17/DiffCSP) - Implementation codes for Crystal Structure Prediction by Joint Equivariant Diffusion (DiffCSP). Lice...

95. [Are diffusion models ready for materials discovery in unexplored ...](https://www.sciencedirect.com/science/article/pii/S2666389926000462) - For DiffCSP, we use a pretrained model trained on the MPTS-52 database, which contains selected crys...

96. [Crystal structure generation with autoregressive large language ...](https://pmc.ncbi.nlm.nih.gov/articles/PMC11624194/) - We introduce CrystaLLM, a methodology for the versatile generation of crystal structures, based on t...

97. [Universal Structure Predictor: Evolutionary Xtallography - USPEX](https://uspex-team.org/en/uspex/overview) - USPEX code solves this problem and allows to predict crystal structure with arbitrary PT conditions ...

98. [[CALYPSO - An Efficient Structure Prediction Method and Computer ...](https://www.calypso.cn/home/) - CALYPSO (Crystal structure AnaLYsis by Particle Swarm Optimization) is an efficient structure predic...

99. [Towards quantitative evaluation of crystal structure prediction ...](https://www.sciencedirect.com/science/article/abs/pii/S0927025624000235) - The global search-based CSP algorithms such as USPEX and CALYPSO combine search algorithms with DFT ...

100. [data/gnome - Matbench Discovery](https://matbench-discovery.materialsproject.org/data/gnome) - Google DeepMind's Graph Networks for Materials Exploration dataset containing millions of crystal st...

101. [Millions of new materials discovered with deep learning](https://deepmind.google/blog/millions-of-new-materials-discovered-with-deep-learning/) - AI tool GNoME finds 2.2 million new crystals, including 380,000 stable materials that could power fu...

102. [google-deepmind/materials_discovery - GNoME - GitHub](https://github.com/google-deepmind/materials_discovery) - GNoME were the predominant model behind new materials discovery. This simple message passing archite...

103. [Scaling deep learning for materials discovery - Nature](https://www.nature.com/articles/s41586-023-06735-9) - GNoME models have already found 2.2 million stable crystals with respect to previous work and enable...

104. [AiiDA](https://www.aiida.net) - We are happy to announce the release of AiiDA v2.8.0! This minor release brings important improvemen...

105. [Posted in 2025 — AiiDA documentation](https://www.aiida.net/news/index/2025.html) - We just released a new version of AiiDA, v2.7.2. This patch release comes with a number of important...

106. [aiida-core - PyPI](https://pypi.org/project/aiida-core/) - AiiDA is a workflow manager for computational science with a strong focus on provenance, performance...

107. [JARVIS-OPTIMADE](https://jarvis.nist.gov/optimade/jarvisdft) - JARVIS-OPTIMADE is designed to provide JARVIS data in REST-API format following OPTIMADE protocols. ...

108. [Atomate2: modular workflows for materials science - RSC Publishing](https://pubs.rsc.org/en/content/articlehtml/2025/dd/d5dd00019j) - Substituting DFT-based Calculators with MLIPs allows faster and cheaper runs, and makes atomate2 an ...

109. [Atomate2: Modular workflows for materials science - ChemRxiv](https://chemrxiv.org/doi/10.26434/chemrxiv-2025-tcr5h) - Key features include the support for multiple electronic structure packages and interoperability bet...

110. [Atomate2: modular workflows for materials science - eScholarship.org](https://escholarship.org/uc/item/9d78f7qc) - This manuscript introduces atomate2, a comprehensive evolution of our original atomate framework, de...

111. [Introduction to pyiron workflows — PMD-workflow-workshop](https://materialdigital.github.io/PMD-workflow-workshop/1_1_intro_pyiron_building_blocks/1_1_intro.html) - In this notebook, you will learn about different pyiron objects which acts as blocks of a building t...

112. [Hands-on Tutorial: Automated Workflows and Machine Learning for ...](http://workshop.pyiron.org/DPG-tutorial-2025/) - The tutorial gives a general introduction to the use of Pyiron with a focus on atomistic simulation ...

113. [pyiron/pyiron_workflow_atomistics: Atomistic workflows for ... - GitHub](https://github.com/pyiron/pyiron_workflow_atomistics) - This repository contains a pyiron module for atomistic simulation workflows, providing tools and uti...

114. [pyiron - Workflows Community Initiative](https://workflows.community/systems/pyiron_base/) - Originally developed for atomistic simulation in computational materials science, pyiron is more rec...

115. [pyiron_atomistics — pyiron_atomistics](https://pyiron-atomistics.readthedocs.io) - pyiron_atomistics - an integrated development environment (IDE) for atomistic simulation in computat...

116. [BOTORCH: A Framework for Efficient Monte-Carlo Bayesian ...](https://research.facebook.com/publications/botorch-a-framework-for-efficient-monte-carlo-bayesian-optimization/) - We introduce BOTORCH, a modern programming framework for Bayesian optimization that combines Monte-C...

117. [Using BoTorch with Ax](https://botorch.org/docs/botorch_and_ax/) - Ax is a platform for sequential experimentation. It relies on BoTorch for implementing Bayesian Opti...

118. [Active Learning via Bayesian Optimization for Materials Discovery](https://www.youtube.com/watch?v=yqspdqa0H-s) - 2021.06.16 Hieu Doan, Garvit Agarwal, Argonne National Laboratory Part of Hands-on Data Science and ...

119. [MatSciBench: Benchmarking the Reasoning Ability of Large ... - arXiv](https://arxiv.org/abs/2510.12171) - MatSciBench provides detailed reference solutions enabling precise error analysis and incorporates m...

120. [acceleratedscience/openad-toolkit: Open Accelerated ... - GitHub](https://github.com/acceleratedscience/open-ad-toolkit) - OpenAD is an intuitive toolkit that simplifies access to a variety of AI models and services for sci...

121. [OpenAD Docs - GitHub Pages](https://acceleratedscience.github.io/openad-docs/) - Open Accelerated Discovery (aka OpenAD) is an open-source framework for molecular and materials disc...

122. [Advancing Open-Source AI in Chemistry and Materials—From ...](https://research.ibm.com/publications/advancing-open-source-ai-in-chemistry-and-materialsfrom-foundation-models-to-integrated-frameworks-to-solve-global-challenges) - This presentation highlights AI advancements in chemistry and material science, emphasizing open-sou...

123. [2024 - OpenAD - Accelerated Discovery](https://openad.accelerate.science/blog/archive/2024/) - OpenAD is a technical framework for molecular discovery. A new approach for providing easy access to...

124. [Materials Project - API](https://next-gen.materialsproject.org/api) - The Materials Project API allows anyone to have direct access to current, up-to-date information fro...

125. [Materials Project - OPTIMADE](https://optimade.materialsproject.org) - This is an OPTIMADE base URL which can be queried with an OPTIMADE client. OPTIMADE version: 1.1.0. ...

126. [The NOMAD Artificial-Intelligence Toolkit: Turning materials-science
  data into knowledge and understanding](http://arxiv.org/pdf/2205.15686.pdf) - ...operates on the FAIR data stored in the
central server of the NOMAD Archive, the largest database...

127. [The JARVIS Infrastructure is All You Need for Materials Design](https://arxiv.org/pdf/2503.04133.pdf) - Joint Automated Repository for Various Integrated Simulations (JARVIS) is a
comprehensive infrastruc...

128. [The JARVIS Infrastructure is All You Need for Materials Design - arXiv](https://arxiv.org/html/2503.04133v2) - JARVIS is a unified platform for multiscale, multimodal, forward, and inverse materials design. It i...

129. [[PDF] The JARVIS Infrastructure is All You Need for Materials Design](https://tsapps.nist.gov/publication/get_pdf.cfm?pub_id=959617) - This schematic highlights key elements of JARVIS, including databases for structural, electronic, me...

130. [Alexandria Materials Database](https://alexandria.icams.rub.de) - Databases. If you would like to have immediate access to still unreleased data, please contact us di...

131. [Links to Large Computational Materials Databases](https://www.royce.ac.uk/programmes/digital-materials-foundry/computational-materials-databases/) - The Alexandria Materials Database is an open-access resource containing extensive computational data...

132. [Open Materials 2024 (OMat24) Inorganic Materials Dataset and Models](https://arxiv.org/html/2410.12771) - ...space
compared to other computational methods or by trial-and-error. While
substantial progress h...

133. [data/omat24 - Matbench Discovery](https://matbench-discovery.materialsproject.org/data/omat24) - Open Materials 2024 dataset from Meta's FAIRchem containing over 100M structures derived from applyi...

134. [Computational Chemistry Unlocked: A Record-Breaking Dataset to ...](https://newscenter.lbl.gov/2025/05/14/computational-chemistry-unlocked-a-record-breaking-dataset-to-train-ai-models-has-launched/) - Open Molecules 2025, or OMol25, is a collection of more than 100 million 3D molecular snapshots whos...

135. [Open Catalyst Project](https://opencatalystproject.org) - The aim is to use AI to model and discover new catalysts for use in renewable energy storage to help...

136. [ML - JARVIS-DB](https://jarvis-materials-design.github.io/dbdocs/jarvisml/) - Several high-accuracy classifications and regression ML models were developed, with applications to ...

137. [OPTIMADE | Open Databases Integration for Materials Design](https://optimade.org) - The Open Databases Integration for Materials Design (OPTIMADE) consortium aims to make materials dat...

138. [Developments and applications of the OPTIMADE API for materials
  discovery, design, and data exchange](https://arxiv.org/pdf/2402.00572.pdf) - The Open Databases Integration for Materials Design (OPTIMADE) application
programming interface (AP...

139. [Developments and applications of the OPTIMADE API for materials discovery, design, and data exchange](https://pubs.rsc.org/en/content/articlepdf/2024/dd/d4dd00039k) - The Open Databases Integration for Materials Design (OPTIMADE) application programming interface (AP...

140. [Developments and applications of the OPTIMADE API for materials discovery, design, and data exchange](https://pmc.ncbi.nlm.nih.gov/articles/PMC11305395/) - The Open Databases Integration for Materials Design (OPTIMADE) application programming interface (AP...

141. [pymatgen - OPTIMADE Python tools](https://www.optimade.org/optimade-python-tools/0.20.2/api_reference/adapters/structures/pymatgen/) - Convert an OPTIMADE structure, in the format of StructureResource to a pymatgen Molecule or Structur...

142. [Materials Consortia's OPTIMADE list of providers](https://www.optimade.org/providers-dashboard/) - A collection of databases from the group of Prof Miguel A. L. Marques at Ruhr University Bochum. Ava...

143. [Introducing OMol25 and UMA for molecular chemistry | AI at Meta ...](https://www.linkedin.com/posts/aiatmeta_weve-released-open-molecules-2025-omol25-activity-7330269368737587202-f_wA) - Universal Model for Atoms, a new standard for modeling the interaction of atoms in both molecules an...

144. [A Scalable and Physics-Informed Foundation Model for Crystal ...](https://www.nature.com/articles/s41467-026-70467-3) - Predicting crystal properties is essential for understanding structure-property relationships and ac...

145. [CLOUD: A Scientific Foundation Model for Crystal Property Prediction](https://changwenxu98.github.io/talks/2024-06-19-Cloud) - CLOUD utilizes a novel symmetry-aware string representation that efficiently encodes symmetry, equiv...

146. [CLOUD: A Scalable and Physics-Informed Foundation Model ... - arXiv](https://arxiv.org/html/2506.17345v1) - A scalable and physics-informed foundation model for crystalline materials, unifying symmetry-consis...

147. [A Scalable and Physics-Informed Foundation Model for Crystal ...](https://www.nature.com/articles/s41467-026-70467-3_reference.pdf) - CLOUD leverages a symmetry-consistent string representation, SCOPE, to encode space group symmetries...

148. [A Scalable and Physics-Informed Foundation Model for Crystal ...](https://www.semanticscholar.org/paper/CLOUD:-A-Scalable-and-Physics-Informed-Foundation-Xu-Zhu/bd45cfe824bb90de613534a645b3942760302d55) - CLOUD (Crystal Language mOdel for Unified and Differentiable materials modeling), a transformer-base...

149. [LUMI-lab: A foundation model-driven autonomous platform enabling ...](https://www.sciencedirect.com/science/article/abs/pii/S0092867426000991) - Pretrained LUMI model drives autonomous closed-loop molecular discovery · Self-driving lab synthesiz...

150. [Physics-informed Neural Network Framework for Phase-field ...](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6570359) - This work develops a PINN-based phase-field formulation to model intergranular fracture. Introducing...

151. [Towards Fully-Automated Materials Discovery via Large-Scale Synthesis
  Dataset and Expert-Level LLM-as-a-Judge](https://arxiv.org/html/2502.16457v4) - ...guided by expert intuition. Our work aims
to support the materials science community by providing...

152. [Benchmarking the Reasoning Ability of LLM in Materials Science](https://openreview.net/forum?id=qxsSiIIGfj) - This paper presents MatSciBench, a benchmark of 1,340 expert-curated, college-level materials scienc...

153. [Efficient equivariant model for machine learning interatomic potentials](https://www.nature.com/articles/s41524-025-01535-3) - We introduce an efficient equivariant graph neural network (E 2 GNN) that can enable accurate and ef...

154. [[PDF] FAST CRYSTAL TENSOR PROPERTY PREDICTION - OpenReview](https://openreview.net/pdf?id=0k7pbSxNOG) - CGCNN is a pioneering GNN model specifically designed for handling crystal ... Equivariant graph neu...

155. [[PDF] Topological representations of crystalline compounds for the ...](https://www.pkusam.com/uploads/upload/files/20251127/b676140ff3f123b3ee42d907f6b8c6d9.pdf) - In this work, we propose atom- specific persistent homology (ASPH) and apply it to material science ...

156. [A review of topological data analysis and topological deep learning ...](https://arxiv.org/html/2509.16877v1) - Their approach showed strong correlation coefficients between persistent homology predictions and re...

157. [Feature engineering methods for machine learning in ...](https://pubs.rsc.org/en/content/articlehtml/2026/cp/d5cp04352b) - More recently, topological data analysis (TDA) has provided mathematical tools such as persistent ho...

158. [Z2PackDev/Z2Pack: A tool for calculating topological invariants.](https://github.com/Z2PackDev/Z2Pack) - Z2Pack automates the calculation of topological numbers of band-structures. It works with first-prin...

159. [xtal2png: A Python package for representing crystal structure as PNG files](https://joss.theoj.org/papers/10.21105/joss.04528) - The latest advances in machine learning are often in natural language processing such as with long s...

160. [Machine-Learned Renormalization-Group-Improved Gauge Actions ...](https://link.aps.org/doi/10.1103/k41k-2pnc) - Renormalization-group (RG)-improved lattice actions can preserve continuum properties, but are in ge...

161. [[2510.25553] Renormalization group for deep neural networks - arXiv](https://arxiv.org/abs/2510.25553) - Abstract page for arXiv paper 2510.25553: Renormalization group for deep neural networks: Universali...

162. [Foundation Models for Atomistic Simulation of Chemistry and Materials](https://arxiv.org/abs/2503.10538) - A foundational model based on data and parameter scaling laws and pre-training strategies is possibl...

163. [Foundation models for atomistic simulation of chemistry and materials](https://pubmed.ncbi.nlm.nih.gov/41673335/) - Conventional computational methods for modeling chemical and materials systems are limited by system...

164. [A foundation model for atomistic materials chemistry](https://collaborate.princeton.edu/en/publications/a-foundation-model-for-atomistic-materials-chemistry/) - We demonstrate the power of the MACE-MP-0 model—and its qualitative and at times quantitative accura...

165. [Powder metallurgy in additive manufacturing: Trends, challenges ...](https://www.sciencedirect.com/science/article/abs/pii/S0032591026003098) - Powder metallurgy based additive manufacturing (PM-AM) is a remarkable technology for the production...

166. [A foundation model for atomistic materials chemistry - AIP Publishing](https://pubs.aip.org/aip/jcp/article/163/18/184110/3372267/A-foundation-model-for-atomistic-materials) - Although the multitude of applications demonstrates that MACE-MP-0 is a robust model, it is also cle...

167. [How can I purchase a VASP license?](https://www.vasp.at/info/faq/purchase_vasp/) - VASP licenses are available for both academic and commercial use: Academic, Governmental, and Non-Pr...

168. [Software codes | Psi-k](https://psi-k.net/software/) - ABINIT is a package whose main program allows one to find the total energy, charge density, and elec...

