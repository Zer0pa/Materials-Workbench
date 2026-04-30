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

The CPU-side build is **complete and post-review-hardened**. Runpod migration is a config-flag swap, not architecture work. A reviewer audit caught real weaknesses (silent runpod_rest fallback, "assumed-pass" precheck, falsifier-trust-fields anti-pattern, absolute-path tests) which have been fixed in Waves A–E. Run `git log` for the canonical commit chain; latest is the HEAD of `main` on [Zer0pa/Materials](https://github.com/Zer0pa/Materials).

* **Tests:** **3,547** passing post-Wave-F (the count grows as adversarial tests are added — run `pytest -q | tail -3` for the canonical current count), 2 skipped (pycalphad), 0 failed.
* **Falsification wave:** 16 of 16 PRD-mandated deliberate failures fired correctly with hash-chained audit proof, plus **7 newly-hardened gates** that recompute from raw evidence (Wave D adversarial tests prove the prior shape-only gates would have passed forged envelopes).
* **Hard gates:** scientific PASS, engineering PASS, brain-functionality PASS.
* **runpod_rest dispatch:** real `httpx`-based REST client with `tenacity` retries; honest-block when credentials missing (no silent mock fallback).
* **Precheck:** runs `pytest` subprocesses; the literal string "Assumed pass" is a hard reject in any precheck row.
* **Repo hygiene:** all tests use `read_fixture(...)` (no absolute paths); `.env.*`, `*.sqlite`, `*.lock` gitignored; deep-research source manifests committed at `phases/Deep-Research/sources.jsonl`.

For a 5-minute orientation see [`REVIEWER-GUIDE.md`](REVIEWER-GUIDE.md). For the full operator-facing report including the post-review remediation summary see [`EXECUTION-REPORT.md`](EXECUTION-REPORT.md). For the Runpod cutover runbook see [`docs/RUNPOD-CUTOVER.md`](docs/RUNPOD-CUTOVER.md).

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
