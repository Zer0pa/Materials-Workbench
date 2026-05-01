# Zer0pa Materials — Workstream Repository

Canonical home for the Zer0pa Materials work stream. Multi-agent handoff: synthesis → orchestrator → overnight executor → Runpod migration. Repo is the source of truth across machines.

## Boundary

Research infrastructure for in silico materials science discovery. Outputs are research artifacts. No regulatory certification claims. No clinical or human-subject use. ITAR / weapons applications are out of scope (Meta UMA Acceptable Use Policy and operator policy).

## What is in here

| Path | Purpose | Author role |
|---|---|---|
| `MODUS-OPERANDI.md` | Reusable multi-agent pattern + parallel-exploration principle (Health, Materials, Energy run independently in parallel; convergence happens after all complete, not during) | Synthesis agent |
| `HANDOFF-TO-ORCHESTRATOR.md` | Materials-specific brief for the next agent (the materials orchestrator) — defines what they inherit and what they must produce | Synthesis agent |
| `ORCHESTRATOR-STARTUP-PROMPT.md` | The exact prompt the user pastes into a fresh agent session to spin up the materials orchestrator | Synthesis agent |
| `source-briefs/` | Inherited research input — the research-agent handover note plus two technology-landscape briefs | External (consumer of synthesis) |
| `synthesis/` | Fresh-eyes reading of the briefs and handover note — what is not yet seen, the variational-unification reframe, what an orchestrator should pressure-test | Synthesis agent |
| `PRD.md` | The PRD that drives the overnight long-horizon execution on a Runpod-bound machine | Materials orchestrator |
| `HANDOFF-TO-OVERNIGHT-EXECUTOR.md` | Materials-specific brief for the overnight executor — defines what they inherit, what they must produce, and the no-user-engagement execution mandate | Materials orchestrator |
| `OVERNIGHT-EXECUTOR-STARTUP-PROMPT.md` | Paste-ready startup prompt for the dedicated overnight executor agent on another machine | Materials orchestrator |

## Build status (post-overnight execution + post-review remediation, 2026-04-30)

The CPU-side control plane is **complete and post-review-hardened**. That means the repo has the contracts, schemas, audit trail, falsifiers, dispatcher, parity tests, packet validators, and acceptance-gate machinery required to begin H100 completion work. It does **not** mean the materials-discovery pipeline is scientifically complete. Pipeline completion requires real GPU-backed Runpod execution, real layer artifacts, and a successful falsification wave over those real outputs.

A reviewer audit caught real weaknesses (silent runpod_rest fallback, "assumed-pass" precheck, falsifier-trust-fields anti-pattern, absolute-path tests) which have been fixed in Waves A–F. Run `git log` for the canonical commit chain; latest is the HEAD of `main` on [Zer0pa/Materials](https://github.com/Zer0pa/Materials).

* **Tests:** **3,547** passing post-Wave-F (the count grows as adversarial tests are added — run `pytest -q | tail -3` for the canonical current count), 2 skipped (pycalphad), 0 failed.
* **Falsification wave:** 16 of 16 PRD-mandated deliberate failures fired correctly with hash-chained audit proof, plus **7 newly-hardened gates** that recompute from raw evidence (Wave D adversarial tests prove the prior shape-only gates would have passed forged envelopes).
* **Hard gates:** scientific PASS, engineering PASS, brain-functionality PASS.
* **runpod_rest dispatch:** real `httpx`-based REST client with `tenacity` retries; honest-block when credentials missing (no silent mock fallback).
* **Precheck:** runs `pytest` subprocesses; the literal string "Assumed pass" is a hard reject in any precheck row.
* **Repo hygiene:** all tests use `read_fixture(...)` (no absolute paths); `.env.*`, `*.sqlite`, `*.lock` gitignored; deep-research source manifests committed at `phases/Deep-Research/sources.jsonl`.

For a 5-minute orientation see [`REVIEWER-GUIDE.md`](REVIEWER-GUIDE.md). For the full operator-facing report including the post-review remediation summary see [`EXECUTION-REPORT.md`](EXECUTION-REPORT.md). For the Runpod cutover runbook see [`docs/RUNPOD-CUTOVER.md`](docs/RUNPOD-CUTOVER.md).

## H100 completion mandate

This is not a demo, mock showcase, or first-green-test milestone. The next workstream is enterprise-grade H100 completion: every layer that claims `runpod_rest` must be backed by real GPU execution or must block honestly. No result may be promoted because a schema-compatible stub exists, and no novelty, ionic-transport, stability, or packet claim may pass without raw-evidence recomputation and audit provenance.

The repository is ready to **start** H100 completion work. It is not complete until the H100 run produces real artifacts and those artifacts survive parity, hard-failure detectors, acceptance gates, packet validation, and a falsification wave.

### Work required to complete the pipeline

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

### H100 wall-clock estimate

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

## Read order

For a fresh reviewer landing on this repo on another machine, read in this order:

1. **[`REVIEWER-GUIDE.md`](REVIEWER-GUIDE.md)** — how to clone, install, run the test suite, and navigate the codebase.
2. **[`EXECUTION-REPORT.md`](EXECUTION-REPORT.md)** — what was built, gates verdict, parked-for-Runpod table, open blockers, next actions.
3. **[`docs/RUNPOD-CUTOVER.md`](docs/RUNPOD-CUTOVER.md)** — operator runbook for the Runpod machine.
4. **[`phases/Falsification-wave/FALSIFICATION-WAVE-REPORT.md`](phases/Falsification-wave/FALSIFICATION-WAVE-REPORT.md)** — the 16-case wave verdict.
5. **[`PRD.md`](PRD.md)** — original specification (the build is its implementation).
6. **`phases/<wave-name>/PHASE-REPORT.md`** — per-wave detail (19 phase reports for the curious reviewer).

For a previous-role agent reconstructing the pre-execution context:

1. `MODUS-OPERANDI.md` — multi-agent work-stream pattern (reusable across Health / Materials / Energy).
2. `HANDOFF-TO-ORCHESTRATOR.md` — materials orchestrator brief.
3. `source-briefs/00-research-agent-handover-note.md` — research agent's self-assessment and the 5 pending decisions.
4. `source-briefs/01-full-technology-landscape.md` — the 7-layer pipeline catalogue (Brief #1).
5. `source-briefs/02-corrections-and-architecture.md` — corrections, gaps A-H, master tool table (Brief #2).
6. `synthesis/01-fresh-eyes-on-materials-briefs.md` — synthesis-agent reframe.
7. `synthesis/02-digest-of-source-briefs.md` — Wave 0 digest of Briefs #1+#2 for working-reference use.
8. `HANDOFF-TO-OVERNIGHT-EXECUTOR.md` — overnight executor brief (this role's input).
9. `phases/Pause-state-handoff/PAUSE-STATE.md` — mid-execution pause/resume handoff (historical).

## Provenance

- Initial commit: 2026-04-30.
- Research agent: Perplexity (Briefs #1 and #2 plus handover note).
- Synthesis agent: Claude Opus 4.7 (1M context), 2026-04-29.
- Materials orchestrator: wrote `PRD.md`, `HANDOFF-TO-OVERNIGHT-EXECUTOR.md`, and `OVERNIGHT-EXECUTOR-STARTUP-PROMPT.md`, 2026-04-30.
- Next agent: overnight executor on a Runpod-bound machine.

## Cross-workstream principle (deliberate)

This workstream runs in parallel with `Zer0pa/Health` and (forthcoming) `Zer0pa/Energy`. Each workstream is built end-to-end as an independent pipeline. **No substrate is shared during build.** Redundancy across workstreams is a deliberate asset — surplus coding capacity buys diversity of architecture, not duplicated cost. Convergence (if any) happens in a separate merge step after all three workstreams complete. See `MODUS-OPERANDI.md` § Parallel-exploration principle.
