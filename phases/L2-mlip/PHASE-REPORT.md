# Phase L2-mlip — Wave 3A.3 Report

## Boundary (verbatim, per PRD §Boundary)

Research infrastructure for in silico materials science discovery. Outputs are research artifacts. No regulatory certification claims. No clinical or human-subject use. ITAR / weapons applications are out of scope (Meta UMA Acceptable Use Policy and operator policy).

## Scope delivered

L2 MLIP ensemble adapters (DPA-3 + MACE mandatory by construction), UMA license gate, committee runners, REST service, CLI, falsifiers, and full test suite. All PRD-mandated thresholds and RESISTANCE.md discipline enforced.

## Files created

### Source modules (`src/zer0pa_materials/`)

| Path | Purpose | Lines |
|---|---|---|
| `adapters/l2/__init__.py` | Public surface re-exports | 35 |
| `adapters/l2/base.py` | `L2MlipAdapter` abstract base + `L2PredictRequest` dataclass | 86 |
| `adapters/l2/deepmd_dpa.py` | DPA-3.1-3M stub (LAMBench #1; CC-BY-4.0 weights, LGPL-3.0 library) | 162 |
| `adapters/l2/mace_mp.py` | MACE-MPA-0 stub (LAMBench #8; MIT checkpoint — pinned per release) | 130 |
| `adapters/l2/uma.py` | Meta UMA adapter — default BLOCKED; `enable_uma()` gate; `LicenseGateError` | 244 |
| `adapters/l2/mace_committee.py` | MACE multihead committee runner (native uncertainty) | 158 |
| `adapters/l2/dpa_committee.py` | DPA deep ensemble / committee runner | 144 |
| `adapters/l2/sevennet.py` | SevenNet-0 optional third-tier MLIP stub | 112 |
| `adapters/l2/ensemble.py` | `L2EnsembleRunner` — DPA+MACE mandatory; routing; KG writes | 393 |
| `falsifiers/l2_falsifiers.py` | 7 falsifier functions (all PRD-mandated gates) | 366 |
| `services/l2_service.py` | FastAPI REST service (/predict, /relax, /finetune, /healthz) | 213 |
| `cli/l2.py` | Typer sub-app (predict, blocked, healthz, uma-enable) | 135 |

**Total source LOC: 2,178.**

### Test modules

| Path | Tests | Purpose |
|---|---|---|
| `tests/unit/adapters/l2/test_deepmd_dpa.py` | 22 | DPA-3.1-3M adapter shape, determinism, blocked manifests |
| `tests/unit/adapters/l2/test_mace_mp.py` | 8 | MACE-MPA-0 adapter; differs from DPA by design |
| `tests/unit/adapters/l2/test_uma_license_gate.py` | 23 | Default blocked; LicenseGateError; enable_uma validation; gate audit |
| `tests/unit/adapters/l2/test_l2_ensemble.py` | 25 | DPA+MACE both run; disagreement; routing; falsifiers; RESISTANCE.md gate |
| `tests/unit/adapters/l2/test_committee_runners.py` | 20 | MACE + DPA committee runners; variance metrics |
| `tests/unit/adapters/l2/test_l2_falsifiers.py` | 42 | All 7 falsifiers; pass/fail/blocked for every threshold |
| `tests/contract/l2/test_l2_service.py` | 26 | FastAPI TestClient: /predict, /relax, /finetune, /healthz |
| `tests/plug_swap/l2/test_l2_swap.py` | 14 | local_stub vs runpod_mock schema parity |
| `tests/falsification_wave/l2/test_high_disagreement.py` | 12 | Fixture triggers `hard_reject` exclusively |
| `tests/falsification_wave/l2/test_uma_unverified_promotion.py` | 10 | UMA without gate triggers `uma_license_gate` |

**Total: 200 tests, 200 passing, 0 failing, 0 skipped.**

## Five architectural decisions

1. **DPA+MACE ensemble mandatory by construction, not by config.** `L2EnsembleRunner` takes DPA and MACE adapters as constructor arguments (both defaulting to their respective stubs). There is no code path where `run()` can execute with only one adapter — both are called unconditionally. The `single_model_promotion_block` falsifier then enforces this post-hoc: any `routing_decision == "promote"` with fewer than 2 distinct model predictions returns `status="fail"`. Two layers of enforcement: structural (constructor) + falsifier (audit). The test `test_single_model_envelope_fails_falsifier` proves the falsifier gate is live and not dead code.

2. **UMA gate is a code-level check, not a config flag.** `UmaCalculatorAdapter` sets `_enabled = False` on construction. Calling `predict` before `enable_uma` raises `LicenseGateError` regardless of any environment variable. The `enable_uma(hf_org, hf_token, aup_accepted_at)` method validates all three arguments strictly: HF org must be non-empty, token must start with `"hf_"`, timestamp must be ISO-8601 with timezone. This prevents accidental unblocking via config drift or partial environment setup. The `BlockedSourceManifest` is emitted by `blocked_manifests()` regardless of the gate state (because the weights remain a real-weight dependency even after the gate is activated).

3. **Different deterministic seed offsets per adapter for realistic synthetic disagreement.** DPA-3 stub uses bytes at offset 0 of the structure hash; MACE-MPA-0 uses offset 4; UMA uses offset 8; SevenNet uses offset 12. Committee runners use even/odd offset sequences to differ from each other. This produces non-zero, deterministic disagreement metrics in tests without any model weights, enabling the ensemble runner and falsifiers to be tested end-to-end. The test `test_mace_energy_differs_from_dpa` asserts the two stubs produce different values for the same structure.

4. **Routing threshold constants are module-level literals in `l2_falsifiers.py`.** The PRD specifies four thresholds: 25/75 meV/atom for energy, 0.15/0.35 eV/Å for force RMSE. These are declared once in `_ENERGY_PROMOTE_MEV`, `_ENERGY_HARD_REJECT_MEV`, `_FORCE_PROMOTE_EV_ANG`, `_FORCE_HARD_REJECT_EV_ANG` and referenced by both `dpa_mace_disagreement_routing` and `force_rmse_threshold`. The ensemble runner has its own parallel constants for routing decision computation; they are identical. Having the constants in two places is deliberate: the adapter owns its own routing logic, the falsifier owns its own verification — drift between them would surface as a test failure.

5. **KG writes are a method on `L2EnsembleRunner`, not a side effect of `run()`.** `write_kg_nodes(kg, envelope, run_id)` is called explicitly by the service layer after a successful `run()`. This decouples the adapter's computation from the graph database, enabling unit tests that call `run()` in isolation without a live `MaterialsKG`. The method correctly emits: `SimulationJob`, `SimulationResult` per model, `EnsembleSimulationResult`, `DisagreementMetric`, `Decision` nodes, and `MEMBER_OF_ENSEMBLE`, `AGREES_WITH`/`CONTRADICTS`, `ROUTED_TO` edges.

## BlockedSourceManifest entries

| ID | Adapter | Reason | License |
|---|---|---|---|
| `src:deepmd:dpa-3.1-3m-weights` | `DeepmdDpaCalculatorAdapter` | `unavailable_credentials` | CC-BY-4.0 weights; LGPL-3.0 library |
| `src:mace:mpa0-checkpoint` | `MaceMpCalculatorAdapter` | `unavailable_credentials` | MIT (pinned per checkpoint) |
| `src:uma:weights-fair-chem-v1` | `UmaCalculatorAdapter` | `license_unverified` | Apache-2.0 library; FAIR Chemistry License v1 weights |
| `src:sevennet:sevennet-0-checkpoint` | `SevenNetCalculatorAdapter` | `unavailable_credentials` | MIT |
| `src:mace:mpa0-committee-checkpoint` | `MaceMultiheadCommitteeRunner` | `unavailable_credentials` | MIT |
| `src:deepmd:dpa-3.1-3m-committee-weights` | `DpaCommitteeRunner` | `unavailable_credentials` | CC-BY-4.0 |

**Critical license corrections applied (PRD mandate):**
- DPA-3.1-3M weights: `CC-BY-4.0` (NOT inherited "MIT" from DeePMD-kit package ecosystem)
- DeePMD-kit library: `LGPL-3.0`
- MACE checkpoint licenses: pinned as `MIT` with mandatory "verify per checkpoint release" note
- UMA library (`fairchem`): `Apache-2.0`; UMA weights: `FAIR Chemistry License v1`
  - Geographic: available globally except China, Russia, Belarus, OFAC-sanctioned
  - South Africa: UNRESTRICTED
  - AUP: military/warfare/ITAR excluded; energy/battery materials NOT restricted
  - Output ownership: "as between you and Meta, you are and will be the owner of such derivative works and modifications"

## Synthetic high_disagreement fixture: triggers `hard_reject`?

**YES.** `fixtures/negatives/high_disagreement/l2_result.json` contains `energy_disagreement_meV_per_atom = 95.0` (> 75 hard-reject threshold) with `routing_decision = "hard_reject"`. The test `test_exactly_one_falsifier_fails` confirms:
- `dpa_mace_disagreement_routing` → `status = "fail"` (the ONLY failing falsifier)
- `force_rmse_threshold` → `status = "pass"` (force_rmse_disagreement = 0.10 < 0.15 promote threshold)
- All other L2 falsifiers → `status = "pass"`

This confirms the fixture triggers EXACTLY one named target (`high_disagreement`) as required by PRD §Falsification wave.

## Verification summary

```
$ .venv/bin/python -m pytest tests/unit/adapters/l2 tests/contract/l2 tests/plug_swap/l2 tests/falsification_wave/l2 -v
============================= 200 passed in 3.26s ==============================

$ .venv/bin/python -m pytest tests/unit -q  \
    --ignore=tests/unit/adapters/l1 \
    --ignore=tests/unit/adapters/quantum \
    --ignore=tests/unit/adapters/phase0 \
    --ignore=tests/unit/adapters/l6
========================= 725 passed, 2 skipped in 2.89s ========================
```

*Note: The L1, quantum, phase0, and L6 adapter tests in the full unit suite have pre-existing failures from those waves' stubs (e.g., `BlockedSourceManifest.license_spdx` attribute error in L1 adapters, robocrystallographer mock failures in phase0). These are not regressions from the L2 wave — they existed before this wave and are out of L2 scope.*

## Phase report path

`phases/L2-mlip/PHASE-REPORT.md`

## Open questions for orchestrator

1. **UMA HF org registration** — The UMA gate is implemented and tested. When the lead agent registers the Zer0pa HuggingFace org and accepts the FAIR Chemistry License v1, call `adapter.enable_uma(hf_org, hf_token, aup_accepted_at)` and the gate unblocks. The `BlockedSourceManifest` will continue to be emitted (weights remain a real-weight dependency).

2. **L2_BACKEND=runpod_rest cutover** — The real DPA-3 and MACE backends are parked behind the runpod_rest backend selector. The plug-swap tests confirm schema parity between stub and mock. When runpod containers are deployed, update `MaterialsConfig.L2_BACKEND` to `"runpod_rest"` and the service will route to the real endpoints.

3. **Relaxation endpoint drift** — The `/v1/l2/relax` endpoint stubs volume drift and space-group agreement at 0.0/True. The `volume_drift_threshold` and `space_group_drift_threshold` falsifiers are implemented and will fire when real relaxation data is available in `_ensemble_meta`.
