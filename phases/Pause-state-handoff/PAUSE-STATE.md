# Pause-State Handoff — Zer0pa Materials Overnight Executor

## Boundary

Research infrastructure for in silico materials science discovery. Outputs are research artifacts. No regulatory certification claims. No clinical or human-subject use. ITAR / weapons applications are out of scope (Meta UMA Acceptable Use Policy and operator policy).

## Status at pause

- **Pause time:** 2026-04-30 (approximate)
- **Last commit:** `371bf01` — Wave 3B complete, pushed to `Zer0pa/Materials` main
- **Test state:** 2329 passed, 2 skipped (pycalphad), 0 failed
- **LOC:** ~28,421 src + ~21,465 tests
- **Pause reason:** Claude usage allocation near limit; resume after refresh (operator request)

## What is complete (CPU-side)

| Wave | Scope | Tests | Commit |
|---|---|---|---|
| A0-contracts | Universal envelope, 11 layer-output schemas, units, hashing, config, artifact manifest, CLI base | 157 | 220d348 |
| A1-audit-kg-ontology | Append-only JSONL audit (11 categories) + sha256 hash chain (4-mode tampering detection), 28-node + 25-edge KG, EMMO bindings, RDF/PROV-O export, RO-Crate manifest writer, decisions, reasoner tuples, episodic memory | 149 | 220d348 |
| A2-fixtures | 11 positive structures (LLZO cubic+tetragonal, Li6PS5Cl, Li-Mg-Zr-Cl seed, Bi2Te3, PbTe, SnSe, H2, LiH, Si, NaCl), 13 negative falsifier fixtures, 3 Phase 0 extractions, 2 toy TDBs (~73 KB total) | 286 | 220d348 |
| 3A.1 Phase 0 + L6 | OPTIMADE federated query, LangGraph extraction, Robocrystallographer, MaterialsBERT NER (gated), MatterGen, DiffCSP, CrystaLLM, LeMat-GenBench eval; novelty_status_gate | (cumulative) | ac1b88c |
| 3A.2 L1 + Quantum | QE/CP2K/ABINIT/PySCF DFT adapters, PennyLane VQE + Qiskit Nature + 3-slot dispatcher, cross-code disagreement; H2/LiH VQE-vs-FCI gates pass | 218 | ac1b88c |
| 3A.3 L2 MLIP | DeepMD-DPA, MACE-MP, UMA (default-blocked, license-gated), Mace/DPA committee, SevenNet, L2EnsembleRunner with DPA+MACE-by-construction, routing decisions (promote/queue_dft/hard_reject) | 200 | ac1b88c |
| 3A.4 Ionic transport | NEB barrier, MLIP-MD diffusion, AIMD diffusion, Nernst-Einstein converter (separate testable function), Arrhenius fit, electrochemical window, interface stability, full-battery-evidence orchestrator with adversarial promotion gate; LLZO promotes, Li6PS5Cl correctly rejects on oxidation gate, Li-Mg-Zr-Cl seed promotes only with `coating_interlayer` mode | 203 | ac1b88c |
| 3B.1 L1.5 phonon | Phonopy harmonic, Phono3py BTE, HiPhive FC fit, BoltzTraP2, AMSET, ZT assembler with BoltzTraP2-vs-AMSET rank-stability disagreement gate; thermoelectric sidecar for Bi2Te3/PbTe/SnSe | 207 | 371bf01 |
| 3B.2 L3 CALPHAD | pycalphad equilibrium, ESPEI Bayesian fit (with information-geometry framing exposed in `_information_geometry_note`), PhaseForgePlus prior (default-blocked), Thermo-Calc TDB read-only quarantine (per-customer license gate, hash-only output), SovereignCalphadPipeline (DFT/MLIP → prior → ESPEI → pycalphad@grid) | 258 | 371bf01 |
| 3B.3 L4 phase field | PRISMS-PF, MOOSE, MICROSIM (GPL-3 subprocess isolation enforced at runtime), SPPARKS, Neural-operator (U-AFNO + DeepONet, advisory=True until beats persistence baseline AND <10% relative QoI), L4SolverEnsemble, plug_swap_schema_invariance falsifier | 172 | 371bf01 |
| 3B.4 L5 FEM/CFD | FEniCSx, deal.II (subprocess), OpenFOAM, ContinuumHandoffCodec (VTK/Exodus/FMI with units sidecars + hashes), HomogenisationOperator (L4 → L5 effective tensors), SPD enforcement | 248 | 371bf01 |

## What remains before Runpod becomes a config-flag swap

The PRD §CPU-First Build Sequence requires steps 12–16 still:

1. **Wave 4a — L7 orchestration** (Opus subagent next)
   - LangGraph reasoner adapter (reasoning state, NOT scientific audit)
   - Prefect campaign adapter (lifecycle, retries, cancellation, deployment metadata)
   - Parsl fan-out adapter
   - AiiDA + atomate2 provenance adapter
   - BoTorch acquisition adapter — defaults: `qMultiFidelityKnowledgeGradient` for expensive multi-fidelity, `qLogExpectedImprovement` for simple exploitation. Plain `qExpectedImprovement` is forbidden as default.
   - AlabOS protocol compiler stub (`ALABOS_MODE=recipe_only` enforced; hardware-executable output is a hard failure)
   - Campaign state machine + handoff packet
   - L7 falsifiers: candidate promotion fails if no audit provenance, bypasses disagreement gates, duplicates rejected candidate, or violates data reuse scope

2. **Wave 4b — CLI integration** (lead agent does this)
   - Wire `cli/{phase0,l6,l1,quantum,l2,ionic,l1_5,l3,l4,l5,l7}.py` typer subapps into `cli/main.py`

3. **Wave 4c — Cross-layer integration tests**
   - Full campaign end-to-end on the three battery seeds (LLZO/Li6PS5Cl/Li-Mg-Zr-Cl)
   - Full thermoelectric campaign on Bi2Te3/PbTe/SnSe
   - Audit-chain verification across all 11 layers
   - KG state reconstructible from repo (PRD brain-functionality gate)

4. **Wave 5a — MVP evidence packet generator** (Opus subagent)
   - Battery primary packet: ranked candidates, full ionic-transport evidence chain, calibrated uncertainty, AlabOS protocol candidate JSON, RO-Crate 1.1 export
   - Thermoelectric sidecar packet
   - Publishable-paper deliverable target (per PRD §Scope)
   - Acceptance: every claim has source manifest + audit record + falsifier + rights scope

5. **Wave 5b — Plug-swap framework**
   - First-class plug-swap test framework (not just per-layer ad-hoc tests)
   - Per-backend swap test for every layer; "<1 day swap" invariant timed via test fixture
   - Schema-invariance assertions surfaced as a falsifier across the stack

6. **Wave 5c — Runpod migration scaffold + parity tests**
   - `runpod_mock` backend per GPU-bound layer with schema-identical REST shape
   - Parity tests: `local_stub` ↔ `local_cpu` ↔ `runpod_mock` produce same envelope schema, hashes, audit events for the same input
   - Cutover procedure document (`docs/RUNPOD-CUTOVER.md`)
   - Hard-failure detectors: schema drift, missing artifact hashes, missing boundary block, no resource metrics, lost audit provenance, model response without disagreement metrics, UMA access without verified HF org + AUP, bulk datasets locally, candidate bypassing DFT/ensemble/ionic falsifiers

7. **Wave 6 — Full falsification wave end-to-end**
   - Run all 14 deliberate-failure tests from PRD §Falsification wave in one sweep
   - Audit log proof of each (each falsifier item recorded in `falsifiers.jsonl` with status=fail and the input that triggered it)

8. **Final hard-gate verification + EXECUTION-REPORT.md**
   - Scientific gate, engineering gate, brain-functionality gate per PRD §Acceptance Gates
   - EXECUTION-REPORT.md with commit hashes, links, tests, gates, parked items, blockers
   - Final commit + push

## What is parked for Runpod (each has stub + schema + fixture + BlockedSourceManifest + falsifier already)

- Real QE / CP2K / ABINIT / GPU4PySCF DFT runs
- Real MLIP weights: DPA-3.1-3M, MACE-MPA-0, UMA (FAIR Chemistry License v1, AUP)
- Real DPA / MACE committee evaluations at scale
- Real MD / AIMD / MLIP-MD trajectories
- Real MatterGen / DiffCSP / CrystaLLM generation batches
- Real PRISMS-PF / MOOSE / MICROSIM (GPL-3 subprocess) / SPPARKS at production mesh
- Real neural-operator (U-AFNO / DeepONet) training on classical-trajectory corpus
- Real FEniCSx / deal.II / OpenFOAM at production mesh
- Real ESPEI heavy quaternary MCMC fits
- Real BoltzTraP2 / AMSET on DFT band structures
- Real OPTIMADE federated query at scale (currently mocked with fixture hits)
- Real LangGraph + GPT-4.1 Mini Phase 0 extraction (currently mocked)
- Real Phase 2 AlabOS hardware closure (recipe_only mode in Phase 1)

## Resume protocol for the next agent (or me on wake-up)

1. Read this file and `PRD.md` §CPU-First Build Sequence step 12 onward.
2. Verify `git status` clean and on `main` at `371bf01` (or later).
3. Run `.venv/bin/python -m pytest tests -q | tail -5` — should be 2329 passed, 2 skipped.
4. Spawn Wave 4a (L7 orchestration) with model=opus.
5. Continue per the "What remains" list above.
6. The boundary block is non-negotiable: every artifact carries it verbatim.
7. RESISTANCE.md discipline applies: no rush to green-flag, no NULL-as-out, no efficiency-as-corner-cutting, no flattery-as-freedom.

## Authority chain

- GitHub canonical: https://github.com/Zer0pa/Materials
- gh CLI authenticated as Zer0pa-Architect-Prime
- git config: user.name=Zer0pa-Architect-Prime, user.email=architects@zer0pa.ai
- Working dir: `/Users/zer0palab/Materials Pipeline/`
- Python venv: `.venv/` (Python 3.13.12)
- Package: editable-installed via `pip install -e .`

## Open questions still pending lead-agent attention

1. EMMO IRI verification against the live ontology (Wave 2a flagged — `ontology/emmo.py` static mapping should be cross-checked).
2. Phase 0 extraction page/table/figure references (Wave 2b flagged — DOIs are real but page-level granularity is plausible-only). Resolution: deep-research subagent.
3. LLZO Materials Project IDs `mp-942733`/`mp-942790` need confirmation.
4. Bi2Te3 ZT review citation `10.1088/2515-7639/acc550` may have a more authoritative primary source.
5. Li-Mg-Zr-Cl-seed numeric values are family-level proxies (Li3InCl6/Li3YCl6), not measurements of the exact seed compound — manifest already documents this; whether to refresh on first real DFT run is a Wave 4c integration-test design call.
6. PhaseForgePlus license verification (default-blocked currently — Wave 3B.2 emitted BlockedSourceManifest; lead agent should verify MIT license + current maturity before unblocking).

These do NOT block CPU-side completion. They are research/citation lookups appropriate for a deep-research subagent (Perplexity Pro / Gemini Advanced) per PRD §Deep Research Policy.

## Pause-state attestation

All work to this point is committed and pushed to `Zer0pa/Materials@main`. No uncommitted state. No partial subagent runs in flight.
