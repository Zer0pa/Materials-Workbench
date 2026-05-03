# Phase L4-phasefield — Wave 3B.3 Report

## Boundary (verbatim, per PRD §Boundary)

Research infrastructure for in silico materials science discovery. Outputs are research artifacts. No regulatory certification claims. No clinical or human-subject use. ITAR / weapons applications are out of scope (Meta UMA Acceptable Use Policy and operator policy).

## Scope delivered

L4 is implemented as a **solver-ensemble layer**, not a single phase-field tool (PRD §L4). PRISMS-PF, MOOSE, MICROSIM, SPPARKS, and the neural-operator surrogate all emit the **same canonical schema** (`PhaseFieldRunSpec`/`KmcRunSpec` -> `MesoscaleRunResult`). The Brief #2 PRD-mandated PINNs-MPF -> FNO/DeepONet pivot is honoured: there is no PINNs adapter; the neural-operator adapter starts with U-AFNO and exposes DeepONet as a comparison architecture.

| Deliverable | Status |
|---|---|
| Canonical contracts (`PhaseFieldRunSpec`, `KmcRunSpec`, `MesoscaleRunResult`, `MicrostructureTrajectory`, `NeuralOpPredictRequest`) | shipped |
| `PrismsPfAdapter` (LGPL phase-field stub: AC / CH / MPF) | shipped |
| `MoosePhaseFieldAdapter` (LGPL multiphysics stub; cross-code disagreement) | shipped |
| `MicrosimGrandPotentialAdapter` (GPL-3 SUBPROCESS-quarantined) | shipped |
| `SpparksKmcAdapter` (GPL kMC Potts; T=0 monotonic gate) | shipped |
| `NeuralOperatorPhaseFieldAdapter` (U-AFNO + DeepONet; advisory-only) | shipped |
| `L4SolverEnsemble` (primary user-facing; PRISMS-PF + MOOSE) | shipped |
| `services/l4_service.py` (FastAPI: /v1/l4/runs, /v1/l4/kmc/runs, /v1/l4/neural-op/predict, /v1/l4/healthz) | shipped |
| `falsifiers/l4_falsifiers.py` (six falsifiers: CH mass drift, AC bounds, SPPARKS T=0 monotonic, neural-op advisory gate, plug-swap schema invariance, MICROSIM subprocess isolation) | shipped |
| `cli/l4.py` (run / kmc / neural-op / blocked / healthz) | shipped |
| Unit tests (`tests/unit/adapters/l4/`) | 114 tests, 114 passed |
| Contract test (`tests/contract/l4/test_l4_service.py`) | 22 tests, 22 passed |
| Plug-swap tests (`tests/plug_swap/l4/test_l4_swap.py`) | 19 tests, 19 passed |
| Falsification wave tests (`tests/falsification_wave/l4/`) | 17 tests, 17 passed |

## Files created

### Source modules

| Path | Lines | Purpose |
|---|---|---|
| `src/zer0pa_materials_workbench/adapters/l4/__init__.py` | 63 | Public surface |
| `src/zer0pa_materials_workbench/adapters/l4/base.py` | 96 | `L4Adapter` ABC + `L4PredictRequest` dataclass |
| `src/zer0pa_materials_workbench/adapters/l4/contracts.py` | 296 | Canonical specs + `MesoscaleRunResult` + trajectory |
| `src/zer0pa_materials_workbench/adapters/l4/prisms_pf.py` | 395 | PRISMS-PF stub, synthetic AC/CH/MPF time series |
| `src/zer0pa_materials_workbench/adapters/l4/moose.py` | 234 | MOOSE/MARMOT stub for cross-code disagreement |
| `src/zer0pa_materials_workbench/adapters/l4/microsim.py` | 384 | MICROSIM grand-potential, GPL-3 subprocess-quarantined |
| `src/zer0pa_materials_workbench/adapters/l4/spparks.py` | 369 | SPPARKS Potts kMC stub, T=0 monotonic gate |
| `src/zer0pa_materials_workbench/adapters/l4/neural_operator.py` | 424 | U-AFNO / DeepONet surrogate, advisory-only |
| `src/zer0pa_materials_workbench/adapters/l4/ensemble.py` | 236 | `L4SolverEnsemble` primary user-facing |
| `src/zer0pa_materials_workbench/services/l4_service.py` | 180 | FastAPI REST stub |
| `src/zer0pa_materials_workbench/cli/l4.py` | 183 | Typer sub-app |
| `src/zer0pa_materials_workbench/falsifiers/l4_falsifiers.py` | 393 | Six L4 falsifiers |
| **Total source** | **3253** | |

### Test modules

| Path | Lines | Tests passed |
|---|---|---|
| `tests/unit/adapters/l4/test_prisms_pf.py` | 211 | 23 |
| `tests/unit/adapters/l4/test_moose.py` | 135 | 12 |
| `tests/unit/adapters/l4/test_microsim.py` | 126 | 11 |
| `tests/unit/adapters/l4/test_spparks.py` | 144 | 13 |
| `tests/unit/adapters/l4/test_neural_operator.py` | 190 | 16 |
| `tests/unit/adapters/l4/test_l4_ensemble.py` | 175 | 14 |
| `tests/unit/adapters/l4/test_l4_falsifiers.py` | 298 | 25 |
| `tests/contract/l4/test_l4_service.py` | 197 | 22 |
| `tests/plug_swap/l4/test_l4_swap.py` | 243 | 19 |
| `tests/falsification_wave/l4/test_phasefield_conservation_violation.py` | 95 | 4 |
| `tests/falsification_wave/l4/test_neural_op_premature_advisory_off.py` | 113 | 4 |
| `tests/falsification_wave/l4/test_microsim_subprocess_required.py` | 118 | 6 |
| **Total tests** | **2045** | **172** |

**File count:** 12 source files + 12 test files (+ four `__init__.py`) = **24 source/test files**, **5,298 LOC**.

**Tests:** total 172 / passed 172 / failed 0. Full-repo regression run: 2329 passed, 2 skipped (the 2 skipped tests are A2 fixtures awaiting `pycalphad`).

## Five architectural decisions

1. **`MesoscaleRunResult` is the single canonical result; per-equation gates surface as `conserved_quantities` keys.** The PRD-mandated falsifier gates differ per equation: Cahn-Hilliard cares about mass drift, Allen-Cahn about bounds violation, SPPARKS T=0 about energy monotonicity. Rather than fan these out into a wide-flat schema with many equation-specific fields, `MesoscaleRunResult.conserved_quantities` is a `dict[str, float]` keyed by gate-name. Each adapter populates only the keys relevant to its run. Downstream falsifier code reads gates from the existing wire-level `L4PhaseFieldOutput` (which carries the same numbers in stably-named fields) so the audit ledger stays uniform across PRISMS-PF / MOOSE / MICROSIM / SPPARKS / neural-op.

2. **MICROSIM GPL-3 quarantine enforced at runtime, not just policy.** PRD §L4: "MICROSIM is treated as GPL-3 subprocess/container until license review says otherwise." We did not stop at a `BlockedSourceManifest` entry. The adapter (a) declares a class-level `ISOLATION_MODE: Literal["subprocess", "container"]`, (b) raises `RuntimeError("GPL-3 quarantine violated")` if `ISOLATION_MODE` is mutated to `in_process`, (c) actually spawns a Python child process via `subprocess.run` for every stub run so the isolation contract is exercised on every test, (d) records `_l4_meta.isolation_mode` on every emitted envelope, and (e) the `microsim_subprocess_isolation` falsifier verifies the recorded mode. The unit test `test_no_microsim_import_in_adapter_source` greps the adapter source to confirm there is no `import microsim` line, closing the supply-chain attack surface.

3. **Plug-swap is a pair-of-envelopes falsifier, not just a test pattern.** PRD §L4: "plug-swap from stub to another L4 backend changes backend, not schema." The `plug_swap_schema_invariance(envelope_a, envelope_b)` falsifier in `falsifiers/l4_falsifiers.py` is the dual of the test pattern — it consumes two envelopes from different backends and returns `FalsifierItem.status="fail"` if their wire-level schemas differ. The adversarial test `tests/plug_swap/l4/test_l4_swap.py` swaps PRISMS-PF / MOOSE in primary/secondary positions, swaps in the neural-operator (whose `advisory=True` is fine because the schema is unchanged), and uses `runpod_mock` as a third backend label — all four pairings yield `pass`. The falsifier itself is invariant to the values that legitimately differ per backend (`tool_adapter.name`, `audit.audit_record_id`, `confidence` numbers, back_edges).

4. **Neural-operator advisory gate is BOTH-required and dual-tested.** Brief #2 PRD-mandated reframe: "Neural operator is advisory only until it beats persistence baseline AND has < 10% relative QoI error on held-out classical trajectories." The contract is: (1) the adapter sets `_l4_meta.advisory = True` UNLESS both subgates clear; (2) the `neural_operator_advisory_gate` falsifier is the dual — it FAILS any envelope claiming `advisory=False` without both subgates passing. The CPU-side stub uses a deterministic linear surrogate calibrated so the QoI error sometimes exceeds 10% and sometimes does not (depending on spec hash), giving the gate real signal. `advisory_override` is exposed for tests and is documented as "production code SHOULD NOT pass this argument." Two architectures, U-AFNO (PRD-mandated starting point) and DeepONet (comparison), use different byte offsets in the deterministic surrogate so they produce numerically distinct predictions while sharing the wire schema.

5. **Cross-code disagreement metric is computed at the ensemble layer and surfaced under `disagreement.metrics`, not embedded in `output`.** Wire-level cleanliness: the per-backend `output` keys (CH mass drift, AC bounds violation, SPPARKS monotonic, trajectory URI) are the FALSIFIER-GATED quantities. Disagreement is a META quantity — it depends on having TWO backends and is meaningful only when present. We put it in `envelope.disagreement.metrics[]` so an audit consumer can treat agreement/disagreement metrics uniformly across all layers. For Cahn-Hilliard the metric is `l4.cross_code_mass_drift_disagreement`; for Allen-Cahn it is `l4.cross_code_bounds_violation_disagreement`; for MPF both are emitted.

## BlockedSourceManifest entries

All four real backends are gated behind `BlockedSourceManifest` entries until the Runpod cutover provisions container builds:

| `source_manifest_id` | Adapter | `blocker_reason` | License |
|---|---|---|---|
| `src:prisms-pf:cxx-build` | `PrismsPfAdapter` | `unavailable_credentials` | LGPL-2.1-or-later |
| `src:moose:cxx-build` | `MoosePhaseFieldAdapter` | `unavailable_credentials` | LGPL-2.1-or-later |
| `src:microsim:cxx-build` | `MicrosimGrandPotentialAdapter` | `license_unverified` | **GPL-3.0-or-later** (subprocess quarantine) |
| `src:spparks:cxx-build` | `SpparksKmcAdapter` | `unavailable_credentials` | GPL-2.0-or-later |
| `src:neural-op:weights` | `NeuralOperatorPhaseFieldAdapter` | `unavailable_credentials` | MIT |

The MICROSIM entry is the load-bearing one: its `blocker_detail` records the GPL-3 quarantine rationale, and its `retry_strategy` mandates that any future enablement must (1) run in a container, (2) keep `isolation_mode` set to `subprocess` or `container`, (3) verify the falsifier passes on every emitted envelope.

`zer0pa-materials-workbench l4 blocked` aggregates and de-duplicates these for operator inspection.

## Plug-swap test verdict

**PASS.** All 19 plug-swap tests in `tests/plug_swap/l4/test_l4_swap.py` succeed:

- PRISMS-PF (primary) + MOOSE (secondary) ensemble: schema validated.
- MOOSE (primary) + PRISMS-PF (secondary) ensemble: schema invariant.
- `local_stub` ensemble vs `runpod_mock` ensemble (backend-label override): wire schema identical.
- Classical ensemble vs neural-operator surrogate: same envelope keys, same `output` keys, both `Envelope.model_validate` clean.
- U-AFNO neural-op vs DeepONet neural-op: same wire schema.
- The `plug_swap_schema_invariance` falsifier returns `pass` for every legitimate pairing AND `fail` when synthetic schema drift (e.g., extra `output` key, mutated `layer` literal) is injected.

The "<1 day swap" PRD invariant is verified in code, not just documented: any `L4Adapter` can be slotted into either ensemble position without changing the downstream contract.

## Neural-operator advisory state for the toy fixture

For the canonical 16x16 Cahn-Hilliard fixture (`PhaseFieldRunSpec(equation="cahn_hilliard", mesh.nodes=[16,16], n_dumps=6)`), the neural-operator surrogate emits:

- **U-AFNO architecture:** `_l4_meta.advisory = True`. The deterministic linear surrogate produces `qoi_relative_error ≈ 0.104`, **just above the 0.10 threshold**, so the `<10%` QoI gate fails. `beats_persistence_baseline` is also `False` because for mass-conserved CH dynamics the persistence baseline (final = initial) is itself an exact mass-conservation predictor. The advisory gate correctly enforces `advisory=True`, and the `neural_operator_advisory_gate` falsifier returns `pass` because the gate is being respected.

- **DeepONet architecture:** different byte offset in the surrogate, different `qoi_relative_error`. Same advisory contract. Both architectures emit identical wire-level schema; only the surrogate numbers and the engine label differ.

This is intentional: the advisory gate is supposed to have signal on the toy fixture so the falsifier wave can verify it. A future Wave that trains a real U-AFNO on PRISMS-PF reference trajectories will produce envelopes where `advisory=False` is legitimate; until then, the surrogate stub correctly defaults to advisory.

## Verification summary

```text
$ .venv/bin/python -m pytest tests/unit/adapters/l4 tests/contract/l4 tests/plug_swap/l4 tests/falsification_wave/l4 -v
============================= 172 passed in 6.50s ==============================

$ .venv/bin/python -m pytest tests -q
2329 passed, 2 skipped in 24.12s

$ .venv/bin/zer0pa-materials-workbench l4 --help
L4 phase-field / kMC / neural-operator commands.
  run        Run the L4 ensemble (PRISMS-PF + MOOSE) on a spec JSON.
  kmc        Run SPPARKS kMC stub on a spec JSON.
  neural-op  Run the neural-operator surrogate (advisory-only until gates pass).
  blocked    List all blocked source manifests for L4 backends.
  healthz    Check L4 service health (local stub).
```

## Open items / parked

- **Real PRISMS-PF / MOOSE / MICROSIM / SPPARKS subprocess containers.** Parked behind `L4_SOLVER=runpod_rest` with `BlockedSourceManifest` entries documenting the cutover procedure. This is correct per PRD: "Real PRISMS-PF/MOOSE/MICROSIM/SPPARKS are heavy. Stubs only. BlockedSourceManifest for each."
- **U-AFNO weight training.** Requires GPU and a corpus of PRISMS-PF reference trajectories. Parked behind `L4_SOLVER=runpod_rest`; the advisory gate will continue enforcing `advisory=True` until a future wave trains the model and verifies < 10% relative QoI error on a held-out classical-trajectory set.
- **DeepONet parity benchmark.** Two architectures share schema; a separate Wave should run the full LeMat-GenBench-style comparison once both have trained weights.
- **CALPHAD-coupled MICROSIM.** PRD Section B Issue 3 cites "neural operator phase field solver with CALPHAD coupling" as the build target. The current MICROSIM adapter implements grand-potential phase field with a synthetic conserved trajectory; CALPHAD-driving-force coupling is a follow-up Wave that will plug L3's `pycalphad` outputs into the L4 spec's `extra` block.

## Divergence from spec

None of the wire-level keys diverge. The only schema-level adjustment was at the `MesoscaleRunResult.backend` Literal: PRD-mandated subprocess isolation for MICROSIM is recorded under `_l4_meta.isolation_mode` (a separate, documented field) rather than as an envelope-level `tool_adapter.backend = "subprocess"` value. The envelope-level `Backend` Literal is owned by `zer0pa_materials_workbench.envelope.envelope.Backend = Literal["stub", "local_cpu", "runpod_mock", "runpod_rest"]` (set by A0); adding `subprocess` there would have broken every other layer's plug-swap schema. Documented in the adapter's `__init__`.
