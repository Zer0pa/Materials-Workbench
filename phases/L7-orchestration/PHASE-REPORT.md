# Wave 4a — L7 Orchestration / Active-Learning Loop

## Boundary

Research infrastructure for in silico materials science discovery. Outputs are research artifacts. No regulatory certification claims. No clinical or human-subject use. ITAR / weapons applications are out of scope (Meta UMA Acceptable Use Policy and operator policy).

## Status

- All 11 layer slots are now wired. L7 is the active-learning engine that ties them together.
- Foundation baseline before this wave: 2343 passed, 2 skipped.
- After this wave: **2469 passed, 2 skipped, 0 failed**. +126 L7 tests.
- All seven sub-gates of the AcceptanceGate are composable and the failure-closed roll-up is enforced.
- Resume protocol verified: a fresh agent reading only `runs.jsonl` + `events.jsonl` + `decisions.jsonl` reconstructs full campaign + candidate state.

## Source files

| File | LOC | Purpose |
|---|---|---|
| `src/zer0pa_materials_workbench/orchestration/__init__.py` | 69 | Public surface |
| `src/zer0pa_materials_workbench/orchestration/campaign.py` | 687 | Central Campaign + CampaignState + CampaignSpec; transitions write Decision rows + KG nodes; `resume_from_audit` rebuilds state from JSONL alone |
| `src/zer0pa_materials_workbench/orchestration/candidate_state.py` | 186 | Per-candidate state machine `proposed → screened → validated → evidence_complete → {promoted | rejected | queued_higher_fidelity}` |
| `src/zer0pa_materials_workbench/orchestration/acceptance_gates.py` | 480 | 7-gate composition: boundary, audit-provenance, disagreement, rights, duplicate-rejection, layer-falsifiers, ionic-evidence |
| `src/zer0pa_materials_workbench/orchestration/disagreement_aggregator.py` | 177 | Universal-disagreement primitive (weighted L2 norm of normalised per-layer metrics) |
| `src/zer0pa_materials_workbench/orchestration/self_bootstrapping.py` | 166 | Dirichlet-Categorical posterior over `proposed_action`; per-(tenant, scope) isolation |
| `src/zer0pa_materials_workbench/adapters/l7/__init__.py` | 54 | Public surface |
| `src/zer0pa_materials_workbench/adapters/l7/base.py` | 183 | `L7Adapter` ABC + `make_l7_envelope` |
| `src/zer0pa_materials_workbench/adapters/l7/prefect_campaign.py` | 122 | Prefect lifecycle (stub or real); 5 lifecycle keys baked in |
| `src/zer0pa_materials_workbench/adapters/l7/parsl_fanout.py` | 113 | Fan-out N candidates with `back_edges` pointing at parent |
| `src/zer0pa_materials_workbench/adapters/l7/aiida_provenance.py` | 150 | networkx-style provenance graph with USED/GENERATED/WAS_DERIVED_FROM |
| `src/zer0pa_materials_workbench/adapters/l7/atomate2_workflow.py` | 138 | 6 templated workflows (relax+static, phonon, elastic, dielectric, lobster, lobster_descriptors) |
| `src/zer0pa_materials_workbench/adapters/l7/langgraph_reasoner.py` | 168 | 5-node state graph; **does not write to audit log** (hard architectural boundary) |
| `src/zer0pa_materials_workbench/adapters/l7/botorch_acquisition.py` | 307 | qMFKG + qLogEI; `qExpectedImprovement` raises `ForbiddenAcquisitionError` unless `allow_legacy_qei=True` |
| `src/zer0pa_materials_workbench/adapters/l7/alabos_protocol.py` | 181 | Recipe-only compiler; raises `AlabosExecutableInRecipeOnlyError` on `hardware_executable=True` under recipe_only |
| `src/zer0pa_materials_workbench/services/l7_service.py` | 511 | FastAPI service: 8 endpoints (healthz, create, dispatch, acquire, promote, resume, state, alabos compile); BLOCKED_SOURCES list |
| `src/zer0pa_materials_workbench/falsifiers/l7_falsifiers.py` | 467 | 10 L7 falsifiers (langgraph_is_not_audit, prefect_lifecycle, parsl_fanout, aiida/atomate2 provenance, botorch_acq_allowed, botorch_mf_routing, alabos_recipe_only, candidate_promotion_provenance, cross_layer_disagreement_attribution, tenant_only_tuple_leak) |
| `src/zer0pa_materials_workbench/cli/l7.py` | 283 | Typer subapp: 9 commands (create-campaign, dispatch, acquire, promote, resume, state, alabos-compile, blocked, healthz) |

**Counts (yours exclusively):**
- `src/zer0pa_materials_workbench/orchestration/` — 6 files, **1,765 LOC**
- `src/zer0pa_materials_workbench/adapters/l7/` — 9 files, **1,416 LOC**
- `src/zer0pa_materials_workbench/services/l7_service.py` — **511 LOC**
- `src/zer0pa_materials_workbench/falsifiers/l7_falsifiers.py` — **467 LOC**
- `src/zer0pa_materials_workbench/cli/l7.py` — **283 LOC**

**Total source: 17 files, 4,442 LOC.**

## Tests

| Bucket | Files | LOC | Tests |
|---|---|---|---|
| `tests/unit/orchestration/` | 5 | 763 | 35 |
| `tests/unit/adapters/l7/` | 8 | 568 | 65 |
| `tests/contract/l7/` | 1 | 254 | 11 |
| `tests/plug_swap/l7/` | 2 | 90 | 5 |
| `tests/falsification_wave/l7/` | 4 | 196 | 10 |

**Total tests: 20 files, ~1,900 LOC, 126 tests.**

## Test results

```
.venv/bin/python -m pytest tests -q | tail -5
2469 passed, 2 skipped in 26.36s
```

(Baseline was 2343; +126 from this wave. Foundation tests unchanged.)

## Optional-backend availability

CPU-first build; all real backends absent so every adapter ran the deterministic stub path.

| Backend | Available |
|---|---|
| `prefect` | False |
| `parsl` | False |
| `aiida` | False |
| `atomate2` | False |
| `langgraph` | False |
| `botorch` | False |

When these become available (Runpod cutover or first-class install), the adapters route to the real backend; the envelope schema is invariant by construction (verified by `tests/plug_swap/l7/test_botorch_swap.py` and `tests/plug_swap/l7/test_prefect_swap.py`).

## BlockedSourceManifest entries

Eight static blocked-source records exposed via `services.l7_service.BLOCKED_SOURCES` and `cli/l7.py l7 blocked`:

1. `src:l7:prefect`           — Prefect (Apache-2.0)
2. `src:l7:parsl`             — Parsl (Apache-2.0)
3. `src:l7:aiida`             — AiiDA (MIT)
4. `src:l7:atomate2`          — atomate2 (BSD)
5. `src:l7:langgraph`         — LangGraph (MIT)
6. `src:l7:botorch`           — BoTorch (MIT)
7. `src:l7:ax`                — Ax (MIT)
8. `src:l7:alabos`            — AlabOS (MIT) — Phase 1 is recipe_only; hardware closure deferred

Each entry carries `blocker_reason`, `blocker_detail`, and `retry_strategy` for the operator at cutover time.

## Five architectural decisions

### 1. State-machine resume rests on three JSONL families, not a snapshot file

`Campaign.resume_from_audit` reads `runs.jsonl` (for the spec), `decisions.jsonl` (for transitions), and `events.jsonl` (for envelope-attached events) and replays them. There is no snapshot file. **Why**: the PRD §Brain-functionality gate explicitly demands "a fresh agent can reconstruct state from repo artifacts without chat history." A snapshot file would be a separate truth source and could drift; replay is forced-consistent because it depends only on the chain of decisions which are themselves hash-chained. The unit test `test_resume_from_audit_reconstructs_campaign` exercises a four-transition campaign and confirms the resumed state machine matches the live one.

### 2. BoTorch acquisition routing is double-gated: select_acquisition + falsifier

The PRD says plain `qExpectedImprovement` is forbidden as default. Two gates enforce this:

   1. `BoTorchAcquisitionAdapter.select_acquisition` raises `ForbiddenAcquisitionError` immediately if `requested == 'qExpectedImprovement'` and `allow_legacy_qei` is False.
   2. The falsifier `botorch_acquisition_function_allowed` reads the envelope's recorded acquisition_function and emits `status='fail'` independently.

The double gating ensures that even if a downstream component bypasses the adapter and submits a hand-crafted envelope, the falsifier still fires. This matches PRD §L7 Falsifiers' "promotion fails if ... bypasses disagreement gates" pattern: defence in depth.

### 3. AlabOS recipe-only enforcement raises at compile time, not at audit time

The most adversarial test: a payload with `alabos_mode='recipe_only'` AND `hardware_executable=True` MUST hard-fail. The compiler raises `AlabosExecutableInRecipeOnlyError` synchronously inside `compile()`, before any envelope is emitted. The falsifier `alabos_recipe_only_enforcement` is the secondary gate that runs against the JSON payload (used for the falsification-wave fixture sweep). **Why two gates**: the compiler is the producer-side enforcement; the falsifier is the consumer-side enforcement when the payload arrives from elsewhere (e.g. a different process, a future Phase-2 hardware envelope that was incorrectly downgraded). Either gate must fire; tests confirm both do.

### 4. LangGraph state vs audit log is enforced by separating writers

The PRD's hard architectural boundary: "LangGraph is reasoning state, NOT scientific audit." The implementation:

   * `LangGraphReasonerAdapter` builds a `ReasonerState` model and returns it inside `extra_input` of the envelope. It NEVER calls `AuditLog.append_event`.
   * The only writer to `events.jsonl` / `decisions.jsonl` / `reasoner_tuples.jsonl` is `Campaign` (in `orchestration/campaign.py`).
   * The falsifier `langgraph_is_not_audit` accepts a chain of known event_hashes and verifies the envelope's `audit_record_id` is anchored. If anchored only by an out-of-chain locally-generated UUID — which is the only thing a misbehaving LangGraph adapter could do — the falsifier fails.

This way, "LangGraph wrote to audit" cannot happen by accident: the only adapter capable of audit-chain anchoring is the one with an `AuditLog` reference, and that's `Campaign`, not the reasoner.

### 5. AcceptanceGate is failure-closed; missing signal is `blocked`, not `pass`

The seven-gate composition rolls up by strict precedence: any `fail` → `fail`; else any `blocked` → `blocked`; else any `inconclusive` → `inconclusive`; else `pass`. Specifically:

   * Missing `aggregate_disagreement_score` → `blocked`, not `pass`. PRD: "promotion fails if ... bypasses disagreement gates" — a missing score is a bypass.
   * Missing required-layer envelopes → `blocked`. The campaign's `expected_layers` field is per-objective (battery: L6/L2/L1/ionic; thermoelectric: L6/L2/L1/L1.5).
   * Ionic-evidence-incomplete → `fail`, not `blocked`. The PRD's six required keys must be filled; partial fill is a failure mode (vs. having no ionic envelope at all, which is `blocked`).

This is the load-bearing design choice: a candidate cannot reach `promoted` by exploiting a hole in the evidence; the gate fails closed on every form of incompleteness. Tests `test_disagreement_missing_blocks` and `test_ionic_evidence_incomplete_blocks` cover both shapes.

## CLI integration

`l7_app` is wired into `cli/main.py` via `app.add_typer(l7_app, name="l7")`. The lead agent does not need to do additional wiring — the L7 CLI is now first-class:

```
zer0pa-materials-workbench l7 healthz
zer0pa-materials-workbench l7 blocked
zer0pa-materials-workbench l7 create-campaign campaign:demo/llzo --tenant demo --objective "..."
zer0pa-materials-workbench l7 dispatch campaign:demo/llzo --candidates candidate:demo/c1,candidate:demo/c2
zer0pa-materials-workbench l7 acquire campaign:demo/llzo --candidates candidate:demo/c1
zer0pa-materials-workbench l7 state campaign:demo/llzo
zer0pa-materials-workbench l7 resume campaign:demo/llzo
zer0pa-materials-workbench l7 alabos-compile candidate:demo/c1
```

## Pre-existing failures / blockers

None encountered. Foundation baseline (2343 passed) carried forward unchanged. All `prefect`/`parsl`/`aiida`/`atomate2`/`langgraph`/`botorch` imports are conditional, so the absent backends don't break the test run.

## Phase report path

`phases/L7-orchestration/PHASE-REPORT.md` (this file).
