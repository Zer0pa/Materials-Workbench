# Research State

## Project Reference

Authority lineage: `PRD.md`, `EXECUTION-REPORT.md`, `phases/Falsification-wave/PHASE-REPORT-WAVE-F5.md`.

**Core research question:** What discipline must in-silico materials evidence carry before any GPU layer is allowed to produce a promotable artefact?
**Current focus:** The CPU-side control plane for a nine-stage L1–L7 battery + thermoelectric pipeline is post-Wave-F hardened; the H100 evidence campaign is staged but has not run; promotion of any chain remains gated on raw-evidence recompute over real GPU outputs.

## Current Position

**Current Phase:** Post-Wave-F · Runpod-cutover staging (pre-H100)
**Current Phase Name:** CPU control plane hardened; H100 evidence campaign pending
**Status:** Public-ready bounded surface · Authority-gated for the GPU campaign
**Last Activity:** 2026-05-08
**Last Activity Description:** R5 cleanup landed on `main` — `docs/RUNPOD-CUTOVER.md` corrected (A100→H100 ×2; doubled `zer0pa_materials_workbench_workbench` import path repaired ×2; redundant `cd Materials` step removed). Prior wave landed G1 README visibility row `INTERNAL → PUBLIC` (commit `91145e5d`) and G4 GitHub description + eight bounded topics. PR #1 (`pypi-zenodo-readiness`) merged 2026-05-03; tag `v0.1.0` pushed; PyPI `zer0pa-materials-workbench` v0.1.0 publish-success (Actions run 25294036777).

**Progress:** [█████████░] CPU substrate + Runpod parity complete; H100 wave not yet run.

## Active Hypothesis

**Branch:** `main`
**Posture:** falsifier-first audit before any GPU layer runs.

The seven raw-evidence recompute gates — L2 disagreement, source linkage, novelty, ionic back-edges, NEB barrier, L3 sovereign state, L5 artifact sidecars — re-derive every layer's hash from inputs. Any divergence rejects the chain. The discipline runs today on CPU strict-full (3,547 / 3,547 PASS, 2 pycalphad skips, 0 fail) and on the Runpod-sim parity surface (588 / 588 PASS; mock-in-rest deception rejected). The falsification surface is 16 PRD failures + 7 recompute gates = 23/23 fired correctly, 0 misses.

The H100 wave will run the same gates against real `runpod_rest` GPU artefacts. Until that wave lands, the lane carries CPU control-plane evidence only.

## What We Don't Claim

- No real GPU-backed `runpod_rest` artefact has been produced.
- Discovery is not claimed.
- A `runpod_mock` envelope is not evidence of scientific completion.
- A passing schema or first green test is not a promoted materials result.
- No novelty, ionic-conductivity, stability, or paper-grade packet claim is valid without raw evidence and audit provenance.
- ITAR, weapons, regulatory certification, and human-subject applications are out of scope.

## Pending — gates the next wave must clear

1. UMA acceptable-use closure (Materials Workbench HuggingFace org name is an operator decision pending UMA acceptance).
2. HuggingFace org registration + access plumbing.
3. Materials Project credential path (sourcing rights for L0/L1 inputs).
4. PhaseForgePlus license clarity (CALPHAD layer authority).
5. EMMO UUID cleanup (ontology authority).
6. Real H100 endpoint stand-up + `runpod_rest` execution.
7. Parity over real GPU outputs.
8. Hard-failure detector run over real outputs.
9. Acceptance gate run over real outputs.
10. Packet validation over real outputs.
11. Falsification wave over real outputs.
12. Evidence promotion (only after the eleven gates above clear).

H100 wall-clock estimate: 40–80 hours MVP; 120–250 hours hardening (single-H100 planning).

## Authority Source

- `PRD.md`
- `EXECUTION-REPORT.md`
- `phases/Falsification-wave/PHASE-REPORT-WAVE-F5.md`
- `tests/integration/test_recompute_wired_into_production.py`
- `phases/Deep-Research/sources.jsonl`

## Surface Receipts

- README at `main` HEAD (post-G1 visibility row, post-R5 cutover-doc cleanup).
- PyPI `zer0pa-materials-workbench` v0.1.0 (Publish-to-PyPI Actions run 25294036777, 2026-05-03).
- GitHub repository description + 8 bounded topics (G4 wave-1 metadata pass).
- Landing card slot 07 populated on Zer0pa landing-rd-v3 (`Materials you can falsify.`).
- Product page draft cell-for-cell against locked ZPE prototype (FPO §A.218–234 truth basis).
