# Zer0pa Materials

> Live window into the Zer0pa lab. Materials is research infrastructure, not a productized materials service.

> Boundary: Research infrastructure for in silico materials science discovery. Outputs are research artifacts. No regulatory certification claims. No clinical or human-subject use. ITAR / weapons applications are out of scope (Meta UMA Acceptable Use Policy and operator policy).

## What This Is

Materials is an in silico discovery pipeline workbench for battery and thermoelectric research, now entering H100 completion.

This repository is the Materials workstream's live engineering and research surface. It holds the CPU-side control plane for a multi-layer materials-discovery pipeline: contracts, schemas, layer adapters, audit trail, falsifiers, packet validators, Runpod dispatcher, parity tests, and H100 completion plan. The current pipeline is built around a battery MVP wedge (LLZO, Li6PS5Cl, and Li-Mg-Zr-Cl seed) with a thermoelectric sidecar (Bi2Te3, PbTe, and SnSe).

The repo is intentionally visible as work-in-progress. It should not be read as a finished service, a commercial materials database, a regulatory artifact, or a claim that real H100-backed discovery is complete. The next gate is real GPU-backed `runpod_rest` execution producing artifacts that survive parity, hard-failure detectors, recompute acceptance gates, packet validation, and a falsification wave.

## Pipeline Mechanics

| Field | Value |
| --- | --- |
| Architecture | Seven-layer in silico materials pipeline with audit-first orchestration |
| Layers | Phase 0 extraction; L1 DFT; L1.5 phonon/transport; L2 MLIP; L3 CALPHAD; L4 phase-field; L5 continuum; L6 generative; L7 orchestration/lab |
| MVP Wedge | Solid-state battery evidence chain: LLZO, Li6PS5Cl, Li-Mg-Zr-Cl seed |
| Sidecar | Thermoelectric evidence chain: Bi2Te3, PbTe, SnSe |
| Execution | CPU-side complete; H100 Runpod completion required for real `runpod_rest` GPU artifacts |
| Mechanics | universal envelopes, source manifests, rights claims, KG/audit trail, parity, falsification, raw-evidence recompute gates |
| Open Gate | Real H100 endpoint/service execution and falsification over real outputs |

## Key Metrics

| Metric | Value | Baseline |
| --- | --- | --- |
| Test surface | 3,547 passing; 2 pycalphad skips | post-Wave-F local verification |
| Falsification surface | 16 PRD failures + 7 raw-evidence recompute gates | Wave F production wiring |
| Runpod status | ready to start H100 completion; not pipeline-complete | `runpod_rest` must produce real artifacts |
| H100 completion estimate | 40-80 hours MVP; 120-250 hours hardening | single-H100 wall-clock planning |

> Source: `EXECUTION-REPORT.md`, `phases/Falsification-wave/PHASE-REPORT-WAVE-F5.md`, `docs/RUNPOD-CUTOVER.md`, and the current README H100 mandate.

## Repo Identity

| Field | Value |
| --- | --- |
| Identifier | Zer0pa Materials |
| Repository | https://github.com/Zer0pa/Materials |
| Portfolio | Materials |
| Visibility | INTERNAL |
| Default Branch | main |
| Authority Source | `PRD.md`; `EXECUTION-REPORT.md`; `phases/Falsification-wave/PHASE-REPORT-WAVE-F5.md` |
| License | Proprietary Zer0pa research artifact unless superseded by repository legal files |

## Readiness

| Field | Value |
| --- | --- |
| Evidence posture | CPU-side control plane complete; H100 completion pending |
| Current gate | real `runpod_rest` endpoints must execute GPU-backed layer jobs |
| Verified locally | tests, parity, falsification, raw-evidence recompute production wiring |
| Not complete until | real H100 artifacts survive acceptance, packet validation, and falsification |
| Operator posture | anti-demo; no mock-equivalent success path |

### Honest Blocker

The repo can begin H100 work, but the pipeline is not complete until real GPU-backed artifacts exist. A schema-valid mock, local stub, or green first-base cutover does not satisfy the workstream objective.

## What We Prove

- The CPU-side pipeline contracts are present: envelopes, layer schemas, source manifests, rights claims, KG/audit records, and packet validators.
- Runpod dispatch has an honest `runpod_rest` path that blocks without credentials and tests against mock-in-rest deception.
- Production gates include raw-evidence recomputation for L2 disagreement, source linkage, novelty, ionic back-edges, NEB barrier, L3 sovereign state, and L5 artifact sidecars.
- The falsification wave and Wave F recompute wiring catch forged evidence chains that the older shape-only gates would have accepted.
- The H100 completion path is explicit: stand up real layer endpoints, produce real artifacts, run parity, run falsification, then promote evidence packets.

## What We Don't Claim

- Materials is not a finished commercial service, certification system, regulatory submission, or human-subject/clinical workflow.
- The repo does not claim real H100-backed discovery is already complete.
- A `runpod_mock` envelope is not evidence of scientific completion.
- A passing schema or first green test is not a promoted materials result.
- No novelty, ionic-conductivity, stability, or paper-grade packet claim is valid without raw evidence and audit provenance.
- ITAR, weapons, regulatory certification, and human-subject applications are out of scope.

## Verification Status

| Code | Check | Verdict |
| --- | --- | --- |
| V_01 | CPU-side contracts, schemas, audit, falsifiers, packets, and dispatcher present | PASS |
| V_02 | Full local suite: 3,547 passing, 2 pycalphad skips | PASS |
| V_03 | `zer0pa-materials runpod parity`: 588 parity tests | PASS |
| V_04 | Mock-in-rest-report deception rejected by parity tests | PASS |
| V_05 | Raw-evidence recompute gates wired into production paths | PASS |
| V_06 | Real H100 outputs survive falsification wave | OPEN |

## Proof Anchors

| Path | State |
| --- | --- |
| `PRD.md` | VERIFIED |
| `EXECUTION-REPORT.md` | VERIFIED |
| `docs/RUNPOD-CUTOVER.md` | VERIFIED |
| `phases/Falsification-wave/PHASE-REPORT-WAVE-F5.md` | VERIFIED |
| `tests/integration/test_recompute_wired_into_production.py` | VERIFIED |
| `phases/Deep-Research/sources.jsonl` | VERIFIED |

## Repo Shape

| Field | Value |
| --- | --- |
| Proof Anchors | 6 display anchors |
| Portfolio | Materials |
| Authority Source | `PRD.md`; `EXECUTION-REPORT.md`; `phases/Falsification-wave/PHASE-REPORT-WAVE-F5.md` |
| Pipeline Specs | `source-briefs/`; `synthesis/`; `PRD.md` |
| Execution Surface | `src/zer0pa_materials/`; `tests/`; `fixtures/` |
| Audit / Phases | `audit/`; `phases/`; `phases/Deep-Research/sources.jsonl` |
| Support Sections | Build Status; H100 Completion Mandate; Workstream Contents; Read Order; Provenance; Cross-Workstream Principle |

## Build Status

The CPU-side control plane is **complete and post-review-hardened**. That means the repo has the contracts, schemas, audit trail, falsifiers, dispatcher, parity tests, packet validators, and acceptance-gate machinery required to begin H100 completion work. It does **not** mean the materials-discovery pipeline is scientifically complete. Pipeline completion requires real GPU-backed Runpod execution, real layer artifacts, and a successful falsification wave over those real outputs.

A reviewer audit caught real weaknesses (silent runpod_rest fallback, "assumed-pass" precheck, falsifier-trust-fields anti-pattern, absolute-path tests) which have been fixed in Waves A-F. Run `git log` for the canonical commit chain; latest is the HEAD of `main` on [Zer0pa/Materials](https://github.com/Zer0pa/Materials).

* **Tests:** **3,547** passing post-Wave-F (the count grows as adversarial tests are added; run `pytest -q | tail -3` for the canonical current count), 2 skipped (pycalphad), 0 failed.
* **Falsification wave:** 16 of 16 PRD-mandated deliberate failures fired correctly with hash-chained audit proof, plus **7 newly-hardened gates** that recompute from raw evidence.
* **Hard gates:** scientific PASS, engineering PASS, brain-functionality PASS on the CPU control plane.
* **runpod_rest dispatch:** real `httpx`-based REST client with `tenacity` retries when installed; honest-block when credentials are missing.
* **Precheck:** runs `pytest` subprocesses; the literal string "Assumed pass" is a hard reject in any precheck row.
* **Repo hygiene:** tests use repo fixtures rather than machine-specific absolute paths; `.env.*`, `*.sqlite`, `*.lock` gitignored; deep-research source manifests committed at `phases/Deep-Research/sources.jsonl`.

For a 5-minute orientation see [`REVIEWER-GUIDE.md`](REVIEWER-GUIDE.md). For the full operator-facing report including the post-review remediation summary see [`EXECUTION-REPORT.md`](EXECUTION-REPORT.md). For the Runpod cutover runbook see [`docs/RUNPOD-CUTOVER.md`](docs/RUNPOD-CUTOVER.md).

## H100 Completion Mandate

This is not a demo, mock showcase, or first-green-test milestone. The next workstream is enterprise-grade H100 completion: every layer that claims `runpod_rest` must be backed by real GPU execution or must block honestly. No result may be promoted because a schema-compatible stub exists, and no novelty, ionic-transport, stability, or packet claim may pass without raw-evidence recomputation and audit provenance.

The repository is ready to **start** H100 completion work. It is not complete until the H100 run produces real artifacts and those artifacts survive parity, hard-failure detectors, acceptance gates, packet validation, and a falsification wave.

### Work Required To Complete The Pipeline

1. **Runpod service layer**
   - Stand up real `/v1/{layer}/{endpoint}` services on the H100.
   - Wire `runpod_rest` through `RunpodDispatcher` to real jobs, not mock-compatible responses.
   - Persist job IDs, stdout/stderr tails, resource metrics, artifact URIs, hashes, and audit rows.
   - Make failed CUDA/package/solver calls return structured blocked or failed envelopes, never green placeholders.

2. **GPU-backed layer adapters**
   - **L1 DFT:** run real QE/CP2K/ABINIT or PySCF/GPU4PySCF jobs for sentinel structures.
   - **L2 MLIP:** run DPA-3 + MACE ensemble inference with disagreement metrics and routing decisions derived from raw model outputs.
   - **Ionic:** run NEB, MLIP-MD/AIMD where configured, Arrhenius fit, electrochemical-window, and interface-stability gates.
   - **L6 generative:** run real generation or explicitly bounded seeded-candidate mode, followed by deduplication and L1/L2/ionic back-edges before any novelty claim.
   - **L1.5/L3/L4/L5:** execute the production solver path where H100/MPI is required; otherwise record an explicit CPU-sovereign or blocked result with provenance.

3. **Real campaign data and artifacts**
   - Battery MVP: LLZO, Li6PS5Cl, and the Li-Mg-Zr-Cl seed.
   - Thermoelectric sidecar: Bi2Te3, PbTe, and SnSe.
   - Data intake remains manifest-first: OPTIMADE / Materials Project metadata and small fixtures only; no bulk local datasets.
   - Every DFT output, MLIP prediction, trajectory, phase-field/FEM artifact, generated structure, and packet must have provenance, units, hashes, and falsifier rows.

4. **End-to-end evidence campaign**
   - Execute candidate generation or seeded-candidate intake.
   - Run L1/L2 screening and disagreement routing.
   - Run ionic evidence and promotion gates.
   - Run L3 stability/prior checks where applicable.
   - Generate battery and sidecar evidence packets.
   - Run parity, hard-failure detectors, recompute acceptance gates, and falsification wave on real H100 outputs.
   - Produce a paper-grade evidence packet only if the real artifacts pass the gates.

5. **No-pass-unless gates**
   - No mock envelope may appear in a `runpod_rest` report.
   - No promoted candidate may lack DFT/MLIP/ionic/audit back-edges.
   - No novelty claim may pass without deduplication plus L2, ionic, and L1 validation.
   - No acceptance gate may trust claimed scalar fields where raw recomputation is available.
   - No pipeline-complete claim is valid until real H100 outputs survive the falsification wave.

### H100 Wall-Clock Estimate

For one H100, budget the workstream as follows:

| Work package | Expected H100 wall-clock |
|---|---:|
| Clone, environment, CUDA, Python, package reconciliation, smoke tests | 4-12 hours |
| Real endpoint/service bring-up and `runpod_rest` health checks | 6-12 hours |
| First real battery MVP campaign across L1/L2/ionic/core gates | 18-36 hours |
| Parity, hard-failure detectors, packet regeneration, falsification wave | 4-8 hours |
| Fix loop after first real failures | 12-36 hours |

**Credible end-to-end MVP completion estimate:** 40-80 H100 wall-clock hours.

**Enterprise hardening estimate beyond MVP:** 120-250 H100 wall-clock hours, covering repeated campaigns, convergence checks, solver failure recovery, artifact-store hardening, and falsification expansion.

The H100 agent's first objective is not visible progress. Its objective is to turn the CPU-complete control plane into a real GPU-backed materials-discovery pipeline whose outputs can be defended from raw evidence through audit trail to falsification.

## Workstream Contents

| Path | Purpose | Author role |
|---|---|---|
| `MODUS-OPERANDI.md` | Reusable multi-agent pattern + parallel-exploration principle (Health, Materials, Energy run independently in parallel; convergence happens after all complete, not during) | Synthesis agent |
| `HANDOFF-TO-ORCHESTRATOR.md` | Materials-specific brief for the next agent (the materials orchestrator) | Synthesis agent |
| `ORCHESTRATOR-STARTUP-PROMPT.md` | Prompt the user pastes into a fresh agent session to spin up the materials orchestrator | Synthesis agent |
| `source-briefs/` | Research-agent handover note plus two technology-landscape briefs | External research input |
| `synthesis/` | Fresh-eyes reading of briefs and handover note | Synthesis agent |
| `PRD.md` | Product/research requirements for overnight long-horizon execution | Materials orchestrator |
| `HANDOFF-TO-OVERNIGHT-EXECUTOR.md` | Overnight executor brief and no-user-engagement mandate | Materials orchestrator |
| `OVERNIGHT-EXECUTOR-STARTUP-PROMPT.md` | Paste-ready startup prompt for the dedicated overnight executor agent | Materials orchestrator |

## Read Order

For a fresh reviewer landing on this repo on another machine, read in this order:

1. **[`README.md`](README.md)** - front door, status, proof anchors, H100 completion mandate.
2. **[`REVIEWER-GUIDE.md`](REVIEWER-GUIDE.md)** - how to clone, install, run the test suite, and navigate the codebase.
3. **[`EXECUTION-REPORT.md`](EXECUTION-REPORT.md)** - what was built, gate verdict, parked-for-Runpod table, open blockers, next actions.
4. **[`docs/RUNPOD-CUTOVER.md`](docs/RUNPOD-CUTOVER.md)** - operator runbook for the Runpod machine.
5. **[`phases/Falsification-wave/FALSIFICATION-WAVE-REPORT.md`](phases/Falsification-wave/FALSIFICATION-WAVE-REPORT.md)** - 16-case falsification wave verdict.
6. **[`phases/Falsification-wave/PHASE-REPORT-WAVE-F5.md`](phases/Falsification-wave/PHASE-REPORT-WAVE-F5.md)** - raw-evidence recompute gates wired into production.
7. **[`PRD.md`](PRD.md)** - original specification.
8. **`phases/<wave-name>/PHASE-REPORT.md`** - per-wave detail.

For a previous-role agent reconstructing the pre-execution context:

1. `MODUS-OPERANDI.md` - multi-agent workstream pattern.
2. `HANDOFF-TO-ORCHESTRATOR.md` - materials orchestrator brief.
3. `source-briefs/00-research-agent-handover-note.md` - research agent self-assessment and five pending decisions.
4. `source-briefs/01-full-technology-landscape.md` - seven-layer pipeline catalogue.
5. `source-briefs/02-corrections-and-architecture.md` - corrections, gaps A-H, master tool table.
6. `synthesis/01-fresh-eyes-on-materials-briefs.md` - synthesis-agent reframe.
7. `synthesis/02-digest-of-source-briefs.md` - Wave 0 digest.
8. `HANDOFF-TO-OVERNIGHT-EXECUTOR.md` - overnight executor brief.
9. `phases/Pause-state-handoff/PAUSE-STATE.md` - mid-execution pause/resume handoff.

## Provenance

- Initial commit: 2026-04-30.
- Research agent: Perplexity (Briefs #1 and #2 plus handover note).
- Synthesis agent: Claude Opus 4.7 (1M context), 2026-04-29.
- Materials orchestrator: wrote `PRD.md`, `HANDOFF-TO-OVERNIGHT-EXECUTOR.md`, and `OVERNIGHT-EXECUTOR-STARTUP-PROMPT.md`, 2026-04-30.
- Overnight executor: implemented CPU-side control plane, falsification wave, Runpod scaffold, and post-review hardening waves.
- H100 completion agent: next role; must produce real GPU-backed artifacts and falsification-surviving evidence.

## Cross-Workstream Principle

This workstream runs in parallel with `Zer0pa/Health` and `Zer0pa/Energy`. Each workstream is built end-to-end as an independent pipeline. **No substrate is shared during build.** Redundancy across workstreams is a deliberate asset: surplus coding capacity buys diversity of architecture, not duplicated cost. Convergence, if any, happens in a separate merge step after all three workstreams complete. See `MODUS-OPERANDI.md` § Parallel-exploration principle.
