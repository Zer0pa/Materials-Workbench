# Phase Report: Cross-Layer Integration (Wave 4c)

**Status:** COMPLETE  
**Date:** 2026-04-30  
**Baseline:** 2469 passed (pre-Wave-4c)  
**Final:** 3362 passed, 2 skipped (3364 total collected)  
**New tests:** 170 integration campaign tests (all pass)  

---

## Scope

Wave 4c integration test suite proving the full campaign chain runs end-to-end across all 11 layer slots and the brain-functionality gate (resume from repo without chat history).

**Files written (Wave 4c scope only):**

- `tests/integration/campaigns/__init__.py` — boundary comment
- `tests/integration/campaigns/test_battery_campaign.py` — 23 tests
- `tests/integration/campaigns/test_thermoelectric_campaign.py` — 26 tests
- `tests/integration/campaigns/test_audit_chain_full_campaign.py` — 16 tests
- `tests/integration/campaigns/test_kg_full_campaign.py` — 22 tests
- `tests/integration/campaigns/test_brain_functionality.py` — 11 tests
- `tests/integration/campaigns/test_plug_swap_through_campaign.py` — 21 tests
- `tests/integration/campaigns/test_falsification_wave_dryrun.py` — 44 tests (13 negative fixtures)

---

## Results by Test Scope

### 1. Battery Campaign End-to-End (23 tests — all pass)

**Verdicts confirmed:**

| Seed | Verdict | Fixture ID |
|------|---------|------------|
| LLZO/cubic | promote (li_metal) | `fixture:LLZO_cubic:d45cb2bf` |
| LLZO/tetragonal | promote (with caveat) | `fixture:LLZO_tetragonal:` |
| Li6PS5Cl | reject (oxidative_stability fail) | `fixture:Li6PS5Cl:8d7b2175` |
| Li-Mg-Zr-Cl-seed | promote only in coating_interlayer mode | `fixture:Li-Mg-Zr-Cl-seed:ea01c76f` |

**Gate integration:** `AcceptanceGate.evaluate()` tested with real L2 envelopes. Note: stub adapters produce disagreeing energies → `layer_falsifier_gate` correctly fires for disagreement. `promote_battery_candidate()` promotes LLZO cubic independently via `IonicTransportService`.

### 2. Thermoelectric Campaign (26 tests — all pass)

**Materials covered:** Si, Bi2Te3, PbTe, SnSe

**Key assertions:**
- ZT > 0 for all four materials via `ThermoelectricZtAssembler`
- `ZT_THRESHOLD_HIGH = 1.5` gate tested
- L1.5 envelopes confirmed: **no** `ionic_conductivity_S_per_cm` field present
- Phono3py BTE > Phonopy harmonic for all materials
- SnSe has highest ZT among the four

### 3. Audit Hash-Chain End-to-End (16 tests — all pass)

**11 audit categories populated and validated:** runs, events, decisions, disagreement, falsifiers, rights, models, parameters, sources, artifacts, reasoner_tuples.

**Tampering modes tested:**

| Mode | Target | Detection method |
|------|--------|------------------|
| Edit content | events | event_hash mismatch |
| Insert row | events | prev_hash mismatch |
| Delete row | runs (first row), events (middle), decisions | prev_hash mismatch |
| Reorder rows | events (adjacent), decisions (non-adjacent) | event_hash or prev_hash mismatch |

**Bug found and fixed:** `runs` category requires >= 2 rows for deletion/tampering tests; Campaign.create() only writes 1 row. Fixed by appending a second `run_resumed` event in `_seed_campaign`.

### 4. KG End-to-End (22 tests — all pass)

**Coverage:** 28 `KGNodeType` values + 25 `KGEdgeType` values all exercised.

**RDF round-trip:** Turtle export + rdflib parse verified with 5 manually-created nodes (Campaign-internal edges use `src->dst` format containing `>` which breaks RDF URI serialization — noted as a production code issue separate from Wave 4c scope).

**reconstruct_from_repo:** Uses `_make_audit_kg_at_defaults()` placing audit/KG at `repo_root/audit/runtime/` matching `_resolve_audit_paths()` defaults. Full round-trip: seed → snapshot → verify node counts match.

### 5. Brain-Functionality Gate (11 tests — all pass)

**Subprocess isolation tests (5 tests):** Fresh `sys.executable` subprocess calls `reconstruct_from_repo(repo_root)`. No in-memory state from test process leaks. Verifies repo_root, kg_node_count, category_rows, chain integrity, next_actions.

**In-process resume tests (6 tests):** `Campaign.resume_from_audit()` reconstructs status, candidates, promoted/rejected IDs without the original Campaign object.

**Bug found and fixed:** Subprocess script used `{{...}}` (double-brace literal) instead of `{...}` for dict comprehensions — caused `TypeError: unhashable type: 'dict'`.

### 6. Plug-Replaceability Through Full Chain (21 tests — all pass)

**Layers tested:** L1 (PyScf ↔ QE-AiiDA), L2 (MACE ↔ DeepMD + Ensemble), Ionic (NEB ↔ MLIP-MD), L1.5 (Phonopy ↔ Phono3py), L7 (Prefect ↔ LangGraph).

**Schema invariant:** Both adapters in each pair produce identical Envelope key sets.

**Fragility report:** L1 flagged as most fragile (schema drift detected, reported via `UserWarning`) — documented, not a failure.

**Bugs found and fixed:**
- `L1JobParams` requires `structure_cif` field — all test L1 instantiations updated with stub CIF text
- L1 adapters use `submit_job(structure_cif, params)` not `compute(params)` — all calls updated
- L2 `EnsembleRunner.run()` returns `_ensemble_meta` private key — stripped before `Envelope.model_validate()`

### 7. Falsification Wave Dry-Run (44 tests — all pass)

**13 negative fixtures covered:**

| Fixture | Falsifier | Status |
|---------|-----------|--------|
| ionic_overclaim_no_service | `requires_ionic_transport_service` | fail |
| unstable_phonon | `dynamical_stability` | fail |
| high_disagreement | ensemble disagreement gate | fail |
| missing_boundary | `_boundary_gate` (AcceptanceGate) | fail |
| alabos_executable_in_recipe_only | `alabos_recipe_only_enforcement` | raises `AlabosExecutableInRecipeOnlyError` |
| duplicate_candidate | `_duplicate_gate` (AcceptanceGate) | fail |
| tenant_only_tuple_leak | `tenant_only_tuple_leak` | fail |
| ungrounded_property | `oxidative_stability_threshold` | fail |
| oxidative_stability_li6ps5cl | `oxidative_stability_threshold` | fail |
| runpod_schema_drift | schema contract check | fail |
| non_spd_tensor | tensor check | fail |
| unreadable_tdb | TDB quarantine | fail |
| tdb_quarantine_breach | TDB quarantine | fail |

**API differences found and fixed:**
- `AlabOSProtocolCompilerStub` (not `AlabosProtocolCompiler`) — compile API updated
- `candidate_promotion_provenance(env, audit_provenance_chain=...)` (not `audit_record_ids_in_chain`)
- `RightsClaim` requires `data_class`, `ownership`, `contract_mode`, `rationale` fields
- `AcceptanceGate` boundary test uses `Envelope.model_construct` + `GateContext.model_construct` to bypass validators and inject wrong boundary

---

## API Surface Corrections (bugs found during Wave 4c)

These are discrepancies between the test's initial assumptions and the actual production API:

1. **`L1JobParams` requires `structure_cif`** — not optional. All callers must supply CIF text.
2. **L1 adapter method is `submit_job(cif, params)`** — not `compute(params)`.
3. **`Envelope.falsifier` is `FalsifierBlock` (Pydantic model)** — use `.items`, not `.get("items")`.
4. **`IonicTransportOutput.electrochemical_window_V_vs_LiLi`** — tuple `(reduction, oxidation)`, not `oxidation_limit_V_vs_Li`.
5. **`L2EnsembleRunner.run()` returns `_ensemble_meta`** — strip `_`-prefixed keys before `Envelope.model_validate()`.
6. **`RightsClaim` schema** — requires `data_class`, `ownership`, `contract_mode`, `rationale`; no `owner_org`.
7. **`AuditLog("events")` only populated by `attach_envelope()`** — `Campaign.create()` and `transition_to()` do not write to events.
8. **Campaign-internal KG edges use `src_id->dst_id` format** — contains `>` which breaks RDF URI serialization.
9. **`reconstruct_from_repo` defaults** — expects `repo_root/audit/runtime/` and `repo_root/audit/runtime/kg.sqlite`.

---

## Test Count Summary

| File | Tests |
|------|-------|
| test_battery_campaign.py | 23 |
| test_thermoelectric_campaign.py | 26 |
| test_audit_chain_full_campaign.py | 16 |
| test_kg_full_campaign.py | 22 |
| test_brain_functionality.py | 11 |
| test_plug_swap_through_campaign.py | 21 |
| test_falsification_wave_dryrun.py | 44 |
| **Total** | **170** |

**Baseline preservation:** 2469 pre-Wave-4c tests all still pass (no regressions). Full suite: **3362 passed, 2 skipped**.
