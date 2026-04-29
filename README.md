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

## Read order for the next agent

1. `MODUS-OPERANDI.md` — how the role chain works and why these workstreams stay independent.
2. `HANDOFF-TO-ORCHESTRATOR.md` — what you (materials orchestrator) inherit and produce.
3. `source-briefs/00-research-agent-handover-note.md` — the prior research agent's self-assessment, what it got right, what it missed, the five pending decisions.
4. `source-briefs/01-full-technology-landscape.md` — the full seven-layer pipeline catalogue.
5. `source-briefs/02-corrections-and-architecture.md` — corrections, the eight gaps, the master tool selection table that supersedes Brief #1, the eight intersectional signals.
6. `synthesis/01-fresh-eyes-on-materials-briefs.md` — synthesis-agent reframe; this is the substrate for your own fresh-eyes augmentation.
7. `PRD.md` — overnight execution specification.
8. `HANDOFF-TO-OVERNIGHT-EXECUTOR.md` — operational handoff for the next role.

## Provenance

- Initial commit: 2026-04-30.
- Research agent: Perplexity (Briefs #1 and #2 plus handover note).
- Synthesis agent: Claude Opus 4.7 (1M context), 2026-04-29.
- Materials orchestrator: wrote `PRD.md`, `HANDOFF-TO-OVERNIGHT-EXECUTOR.md`, and `OVERNIGHT-EXECUTOR-STARTUP-PROMPT.md`, 2026-04-30.
- Next agent: overnight executor on a Runpod-bound machine.

## Cross-workstream principle (deliberate)

This workstream runs in parallel with `Zer0pa/Health` and (forthcoming) `Zer0pa/Energy`. Each workstream is built end-to-end as an independent pipeline. **No substrate is shared during build.** Redundancy across workstreams is a deliberate asset — surplus coding capacity buys diversity of architecture, not duplicated cost. Convergence (if any) happens in a separate merge step after all three workstreams complete. See `MODUS-OPERANDI.md` § Parallel-exploration principle.
