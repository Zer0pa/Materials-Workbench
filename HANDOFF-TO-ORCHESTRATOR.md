# Handoff to the Materials Orchestrator — Materials Work Stream

You are the materials orchestrator for the Zer0pa Materials Workbench work stream. This document briefs you on what you inherit, what is expected of you, and what you produce. It does not pre-bake the structure of your PRD — that is your job. The substrate is on the table; shape it with your fresh eyes.

## Boundary

Research infrastructure for in silico materials science discovery. Outputs are research artifacts. No regulatory certification claims. No clinical or human-subject use. ITAR / weapons applications are out of scope (per Meta UMA Acceptable Use Policy and general operator policy).

## What you inherit

### Source briefs (`source-briefs/`)

- **`00-research-agent-handover-note.md`** — Read first. The prior research agent's self-assessment of Briefs #1 and #2. Lists what was got right, what was missed, the five pending decisions specifically flagged for you, the eight intersectional signals (these are the framing language Zer0pa uses that domain-native competitors cannot), and the strategic framing ("the materials open-source path is more complete than the pharma path").
- **`01-full-technology-landscape.md`** — Brief #1. ~117K characters. The seven-layer multi-scale materials simulation pipeline catalogue: tools, datasets, commercial sub-domains, intersectional science framework, and a preliminary Executive Map. Structurally sound; main limitations are of omission, not error.
- **`02-corrections-and-architecture.md`** — Brief #2. ~88K characters. Higher-value document. Four corrections (UMA license, MatterGen novelty, PINNs-MPF → neural-operator pivot, CALPHAD TDB sovereignty). Eight gaps A through H (phonon stack, DPA-3 / DeePMD ecosystem, ESPEI / CALPHAD sovereignty, AlabOS, Phase 0 literature mining, e3nn / equivariant substrate, quantum horizon, battery MVP). The Combined Master Tool Selection Table supersedes Brief #1's Executive Map.

### Synthesis (`synthesis/`)

- **`01-fresh-eyes-on-materials-briefs.md`** — Fresh-eyes reading of Briefs #1 and #2 plus the handover note by the prior synthesis agent (Claude Opus 4.7, 2026-04-29). Surfaces:
  - The architectural reframe: 7-layer pipeline collapses to 3 functional layers via variational unification (knowledge / hypothesis → variational solver → active-inference loop). The eight intersectional signals are not commentary; they are load-bearing architecture.
  - DPA-3 + MACE ensemble disagreement as a universal falsification primitive (cross-model disagreement at every layer).
  - The publishable-paper MVP framing — materials outputs face no regulatory ceiling and can publish in *Nature Materials* or *npj Computational Materials*.
  - Property-targeted (not domain-targeted) productisation — engine reasons over a property target; battery is one parameterisation; year-3 expansion is "same engine, different chemistry."
  - The data-sovereignty contract schema is missing and will block the first sale.
  - The 7→3 layer collapse is the customer-facing abstraction; the 7-layer view is the orchestrator-facing one.
  - The quantum slot belongs at the variational-engine abstraction layer, not at L1 specifically — quantum can plug into VQE, QAOA on phase-field discretisation, or quantum amplitude amplification on BoTorch acquisition.
  - Three-named-compound MVP test (LLZO known-good, Li₆PS₅Cl known-borderline, novel quaternary outside MP-20 coverage) — analogous to dofetilide / verapamil / ranolazine in the Health workstream.
  - Year-3 price ceiling estimate (~$1M/campaign) as the data-asset compounds.
  - **A cross-workstream substrate proposal** that the operator has explicitly rejected. See § Operator override below.

## Operator override — keep workstreams independent

The synthesis agent proposed a shared `Zer0pa/zer0pa-substrate` repo for variational engine + audit log + KG schema + active-inference loop, with `Zer0pa/Health` and `Zer0pa/Materials-Workbench` as domain configurations on top.

**The operator has rejected this proposal.** The binding policy is the *Parallel-exploration principle* in `MODUS-OPERANDI.md`:

- Build Materials end-to-end as an independent pipeline with its own variational engine, its own audit log, its own KG, its own active-inference loop.
- Do not propose substrate sharing in your PRD.
- Do not depend on `Zer0pa/Health` for any architectural component.
- Cross-pollination is allowed at the *fresh-eyes* level — you may *read* `Zer0pa/Health` as reference for how a sibling orchestrator approached comparable engineering problems — but the Materials pipeline is an independent build.
- A future Energy workstream is forthcoming. Do not anticipate it. Do not pre-share with it.

The deliberate redundancy across Health, Materials, and Energy is the point. The synthesis agent's cross-workstream proposal is captured in `synthesis/01-fresh-eyes-on-materials-briefs.md` for traceability, but it is not the operating instruction.

## What you must do

Write `PRD.md` at the top of this repo. The PRD specifies a long-horizon overnight execution by a separate set of overnight-executor agents on a different machine that will eventually have Runpod GPU access. The PRD must front-load every CPU-side build before GPU bring-up.

You are expected to:

- **Apply recursive fresh eyes.** Where the prior synthesis is incomplete, close gaps. Where it sketches, lock interface contracts. Where it gestures, specify falsifiers and acceptance gates. Where it notes a frontier development, evaluate whether deeper specification is warranted. **Augment and innovate; do not paraphrase.** If your PRD is not substantively richer than the synthesis it inherited from, you have not done your job.
- **Spawn sub-agents** in parallel worktrees per pipeline layer (L1 DFT, L1.5 phonon, L2 MLIP, L3 CALPHAD, L4 phase field, L5 FEM/CFD, L6 generative, L7 orchestration / lab) and per cross-cutting concern you identify (falsification ledger, audit-trail schema, interface contracts, MVP evidence packet, AlabOS integration scaffold, Phase 0 literature mining, KG schema, ontology layer if you adopt EMMO, quantum slot scaffold, data-sovereignty schema, pricing model).
- **Use Perplexity Pro / Gemini Advanced deep research** at the points the prior agents left open. The handover note flags five missed items — three of those are stuck-point lookups (LAMBench should be Issue 5, PennyLane + PySCF integration verification, neural-operator phase-field starting point). Surface strategic lookups to the user; resolve tactical ones in the PRD itself.
- **Decide and document** the five pending decisions the handover note explicitly flagged for you: L2 architecture (DPA-3 alone or DPA-3 + MACE ensemble), L3 build vs buy, AlabOS integration timeline (Phase 1 in silico vs Phase 2 with hardware), Phase 0 schema (EMMO-aligned or proprietary), thermoelectrics vs solid-state batteries as the MVP wedge.
- **Maximally front-load pre-Runpod engineering.** The PRD must specify what every overnight-executor agent does without GPU access. Acceptance criterion: when the Runpod machine comes online, the entire CPU-side of the pipeline is complete and GPU layers are stubs ready to be swapped. The cutover must be a config-flag-shaped change, not an architectural rewrite.

## Shape of the PRD

The structure is yours. Mirror Health's `PRD.md` if it helps (the Zer0pa/Health repo is canonical at `https://github.com/Zer0pa/Health`); depart where your fresh eyes warrant. The PRD must cover at minimum:

- **Scope and boundary** with the verbatim research-only block and the explicit MVP wedge selection.
- **Architecture** that the overnight executor can decompose into parallel sub-streams without further user input. Specify interface contracts (CIF / SMILES / mmCIF / FMI / OPTIMADE / SBML / JSON Schema function calls) and the plug-replaceability invariant ("swap any layer's tool in <1 day with no downstream breakage").
- **Falsification framing** with cross-model disagreement specified as a first-class quantity flowing through the audit log.
- **Build sequence** that front-loads CPU work and stubs GPU layers.
- **Agent topology** — Opus + GPT-5+ + domain LLMs + Perplexity / Gemini + KG with episodic memory.
- **Audit-trail spec** — campaign-grade per-discovery provenance log; KG schema; per-layer log shape. The materials-equivalent of pharma's ICH M15 framing.
- **MVP first deliverable** — a concrete chemistry choice with named compounds (the three-compound seed test from the synthesis is one option; you may improve on it), pre-registered acceptance thresholds, and a target publishable paper.
- **Self-bootstrapping reasoner** — how (input, simulation, output, falsifier, ground-truth) tuples flow from each campaign into a private dataset that compounds the moat.
- **AlabOS integration plan** — when physical synthesis closure is enabled (Phase 1 vs Phase 2), and the in-silico-only fallback for Phase 1.
- **Quantum slot specification** — at the variational-engine abstraction layer per the synthesis recommendation, or at L1 per Brief #2's framing — your choice with reasoning.
- **Runpod migration plan** — exact stub-swap procedure; per-layer GPU requirements; cost shape; cutover acceptance gates.
- **Acceptance gates** — scientific, engineering, brain-functionality.
- **Productisation and pricing** — campaign vs subscription, year-1 floor, year-3 ceiling, cross-domain transfer story.
- **Data-sovereignty schema** — contract structure for who owns customer DFT outputs, MLIP fine-tunes, posteriors, audit trails. Surface as an open question for the user if you cannot resolve.
- **Open questions for the user / for the next agent** — explicitly. Things you could not resolve. Things that require user innovation input. Things the overnight executor needs that you could not prefigure.

Be granular. The overnight executor is a separate agent on a separate machine with no conversation context. Every interface, every contract, every threshold, every fallback must be readable from the PRD alone.

## Constraints

- Mac storage tight on the originating machine (~40 GiB free at last check, was 20 GiB earlier this week — bulk artefacts go to private Hugging Face under Architect-Prime when offload is needed).
- HF token at `~/.cache/huggingface/token` on the originating machine. Cross-machine, the user provides.
- No Docker on the originating Mac. Overnight executor on Runpod may use Docker.
- No bulk local datasets — manifests + metadata + small slices only. The Materials Project / OPTIMADE / Materials-Project API access is sufficient for everything CPU-side.
- GitHub canonical. All sub-agent work commits back to `Zer0pa/Materials-Workbench` before PRD finalisation.
- No regulatory or clinical claims. No human-subject inference.
- ITAR / weapons applications excluded by Meta UMA Acceptable Use Policy and operator policy.
- **No cross-workstream substrate sharing.** See § Operator override.

## Authorities and tooling

- `gh` CLI authenticated as Zer0pa-Architect-Prime on the originating machine; cross-machine, the user provides.
- HF token at `~/.cache/huggingface/token` on the originating machine; cross-machine, the user provides. UMA weight access requires accurate organisational registration on HuggingFace — verify before any UMA work.
- Anthropic Opus 4.7 + Claude Code SDK or Anthropic Console — primary planning + code review at maximum reasoning effort.
- OpenAI GPT-5+ at xhigh reasoning — primary heavy-code generator.
- Perplexity Pro / Gemini Advanced — stuck-point and innovation deep research. Use specifically for the three lookups the handover note flags as missed: LAMBench corrections-level positioning, PennyLane + PySCF integration verification, neural-operator phase-field starting point.
- LangGraph + Prefect + Parsl as a reference orchestration stack. The handover does not lock you to it.
- Combined Master Tool Selection Table in Brief #2 § Section 3 — the canonical L1 → L7 tool roster.

## Where the PRD lands and what comes next

Commit `PRD.md` to the top level of `Zer0pa/Materials-Workbench`. Push to GitHub. After the PRD is final, write `HANDOFF-TO-OVERNIGHT-EXECUTOR.md` describing what the next role inherits, what they produce, and the constraints / authorities they operate under. Mirror the structure of this document.

The user will then trigger the overnight execution on a separate Runpod-bound machine using a startup prompt analogous to `ORCHESTRATOR-STARTUP-PROMPT.md`.

## Success criteria

- A PRD that the overnight executor can decompose into parallel sub-streams without further user input.
- Every interface contract locked. Every falsifier specified. Every acceptance gate measurable.
- A clear MVP first deliverable with a publishable-paper target.
- The five pending decisions from the handover note explicitly resolved with reasoning.
- The three lookups the handover note flags as missed, resolved (or escalated to the user as strategic).
- A clear plug-replaceability test that proves the architecture survives the next four frontier-model releases.
- Open questions explicitly listed so the user can innovate on the strategic ones without re-reading everything.
- No cross-workstream substrate dependency.

## What you should pressure-test before locking the PRD

The synthesis agent committed to several positions that you should pressure-test with your fresh eyes:

- **Is the variational-unification reframe (7 layers → 3 functional layers) the right architectural primitive?** The synthesis argues yes; you may have a stronger frame.
- **Is solid-state Li-ion electrolyte the right MVP wedge, or is thermoelectrics the cleaner first publishable result?** The synthesis leaned battery-first; the handover note explicitly flags this as your decision.
- **Are LLZO + Li₆PS₅Cl + a novel quaternary the right three-compound seed test?** Or do you propose a different triple?
- **Is the publishable-paper deliverable the right credibility signal for the MVP?** Or is there a stronger first-customer signal?
- **Do you adopt EMMO / MatML as the Phase 0 ontology layer?** The handover flags this as missing; the synthesis does not commit.

These are pressure-test points, not pre-baked answers. Take them or override them with reasoning.
