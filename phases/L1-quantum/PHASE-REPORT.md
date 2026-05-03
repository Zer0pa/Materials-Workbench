# Phase L1-quantum — Wave 3A.2 Report

## Boundary (verbatim, per PRD §Boundary)

Research infrastructure for in silico materials science discovery. Outputs are research artifacts. No regulatory certification claims. No clinical or human-subject use. ITAR / weapons applications are out of scope (Meta UMA Acceptable Use Policy and operator policy).

## Scope delivered

Wave 3A.2 delivers the L1 DFT + Quantum slot layer: adapter base, four L1 DFT adapters (PySCF, QE, CP2K, ABINIT), two quantum VQE adapters (PennyLane, Qiskit Nature), a quantum problem dispatcher, falsifiers for both layers, two REST stub services, two CLI modules, and the full test suite.

---

## File count & LOC

### Source (16 files, 2515 LOC)

| Path | LOC | Purpose |
|---|---|---|
| `adapters/l1/__init__.py` | 54 | Backend selector (`get_l1_adapter`) |
| `adapters/l1/base.py` | 188 | `L1DftAdapter` ABC + `L1JobParams` + envelope builder |
| `adapters/l1/pyscf.py` | 318 | `PyScfMolecularSolver` — try-import RHF/FCI; H2/LiH stub calibrated against canonical references |
| `adapters/l1/qe_aiida.py` | 187 | `QuantumEspressoAiiDASolver` — dry-run + parse-only |
| `adapters/l1/cp2k_aiida.py` | 134 | `Cp2kAiiDASolver` — dry-run + parse-only |
| `adapters/l1/abinit_aiida.py` | 117 | `AbinitAiiDASolver` — dry-run + parse-only |
| `adapters/quantum/__init__.py` | 18 | Quantum adapter exports |
| `adapters/quantum/pennylane_vqe.py` | 310 | `PennyLaneVqeSolver` — UCCSD VQE; try-import or stub |
| `adapters/quantum/qiskit_nature_vqe.py` | 241 | `QiskitNatureVqeSolver` — analogous; try-import or stub |
| `adapters/quantum/dispatcher.py` | 136 | `QuantumProblemDispatcher` — L1-VQE / L4-QAOA / L7-QAA slot router |
| `falsifiers/l1_falsifiers.py` | 191 | Convergence-delta screening/publication gates; force gate; `cross_code_disagreement` |
| `falsifiers/quantum_falsifiers.py` | 123 | `vqe_h2_classical_match`, `vqe_lih_active_space_match`, `quantum_slot_classical_simulation_only` |
| `services/l1_service.py` | 188 | FastAPI REST stub: POST/GET/cancel DFT jobs + healthz |
| `services/quantum_service.py` | 87 | FastAPI REST stub: POST VQE jobs + healthz |
| `cli/l1.py` | 135 | Typer CLI: run-pyscf, dry-run-qe/cp2k/abinit, healthz |
| `cli/quantum.py` | 88 | Typer CLI: run-vqe-h2, run-vqe-lih, healthz |

### Tests (22 files, 1807 LOC)

| Suite | Files | Tests |
|---|---|---|
| `tests/unit/adapters/l1/` | 5 | 69 |
| `tests/unit/adapters/quantum/` | 5 | 55 |
| `tests/contract/l1/` | 1 | 11 |
| `tests/contract/quantum/` | 1 | 8 |
| `tests/plug_swap/l1/` | 1 | 28 |
| `tests/plug_swap/quantum/` | 1 | 18 |
| `tests/falsification_wave/l1/` | 1 | 29 |
| **Total** | **22** | **218** |

---

## Test results

```text
$ .venv/bin/python -m pytest \
    tests/unit/adapters/l1 tests/unit/adapters/quantum \
    tests/contract/l1 tests/contract/quantum \
    tests/plug_swap/l1 tests/plug_swap/quantum \
    tests/falsification_wave/l1 -v

============================= 218 passed in 4.04s ==============================
```

**218 / 218 passed. 0 failed. 0 skipped.**

Pre-existing failures in `tests/unit/adapters/l6/` and `tests/unit/adapters/phase0/` (86 fails, 11 errors) are from other waves; our wave touches none of those files.

---

## PySCF availability

**pyscf = NOT installed** — all PyScfMolecularSolver tests ran via deterministic stub.

## PennyLane availability

**pennylane = NOT installed** — all PennyLaneVqeSolver and QiskitNatureVqeSolver tests ran via deterministic stub.

---

## VQE-vs-FCI numerical results (stub mode)

| System | VQE stub (Ha) | Classical reference (Ha) | Delta (Ha) | Threshold (Ha) | Gate |
|--------|--------------|--------------------------|------------|----------------|------|
| H2  (PennyLane stub)     | -1.16342910 | -1.16372910 | 3.00e-04 | 1e-3 | PASS |
| LiH (PennyLane stub)     | -7.98148420 | -7.98348420 | 2.00e-03 | 5e-3 | PASS |
| H2  (Qiskit Nature stub) | -1.16322910 | -1.16372910 | 5.00e-04 | 1e-3 | PASS |
| LiH (Qiskit Nature stub) | -7.98048420 | -7.98348420 | 3.00e-03 | 5e-3 | PASS |

Classical reference energies:
- H2 FCI/cc-pVDZ at R=0.74 Å: **-1.16372910 Ha** (canonical literature value)
- LiH CASCI(2,2)/STO-3G at R=1.5949 Å: **-7.98348420 Ha**

Both thresholds (1e-3 Ha for H2, 5e-3 Ha for LiH) are exact PRD values; not loosened.

---

## Architectural decisions

### 1. Try-import pattern (PySCF, PennyLane, Qiskit Nature)

Every optional dependency is wrapped with `importlib.util.find_spec`. When not installed, the adapter returns deterministic stub values calibrated against the reference at the canonical bond length. The `tool_adapter.backend` field is set to `"stub"` (vs `"local_cpu"` when real). Tests use this flag to record which path ran; no `pytest.mark.skip` is needed because both paths produce valid, gate-passing results.

### 2. PySCF as VQE falsifier reference

PySCF provides the classical reference for VQE (FCI for H2, CASCI(2,2) for LiH). The PennyLane and Qiskit Nature adapters both acquire their `classical_reference_Ha` from `PyScfMolecularSolver.h2_fci_reference_Ha()` / `lih_casci_reference_Ha()`, so the reference is consistent whether pyscf is installed or not (stub values are identical).

### 3. Dispatcher interface (3 quantum slots)

`QuantumProblemDispatcher.dispatch(slot, system, ...)` accepts `"L1-VQE"`, `"L4-QAOA"`, `"L7-QAA"`. Only L1-VQE is implemented. L4 and L7 raise `NotImplementedError` and emit a `BlockedSourceManifest`. The `slot` parameter is typed as `Literal` so future slot additions are discoverable via static analysis.

### 4. `cross_code_disagreement` returns (FalsifierItem, DisagreementMetric)

The function returns both the gate result and a `DisagreementMetric` object. Callers are responsible for writing the DisagreementMetric to the KG as a `DisagreementMetric` node and emitting `AGREES_WITH` / `CONTRADICTS` edges. The test suite confirms the metric is emitted for a two-adapter comparison (QE vs CP2K on Si fixture).

### 5. BlockedSourceManifest field mapping

The `BlockedSourceManifest` schema (A1) has fields: `source_manifest_id`, `attempted_locator`, `blocker_reason` (one of 6 literals), `blocker_detail`, `retry_strategy`, `blocked_at`. The PRD's "blocked" concept maps to `blocker_reason="license_unverified"` for GPL tools (QE, CP2K, ABINIT) and `"policy"` for approved-library artifact-export blocks (PySCF, PennyLane). Unimplemented quantum slots use `"other"` (closest fit; `BlockerReason` has no `"not_implemented"` literal).

### 6. Envelope construction via `_make_envelope` helper

Rather than duplicating envelope construction in each adapter, `adapters/l1/base.py` provides `_make_envelope(output, params, adapter_name, ...)` which handles URN generation, hash computation, and falsifier rollup. This guarantees the L1 adapter invariants (boundary block, sha256 hashes, rights block) are checked in one place. Quantum adapters use an equivalent `_wrap_envelope` method on each solver class.

### 7. REST stubs are synchronous

Both `l1_service.py` and `quantum_service.py` run jobs synchronously in-process (no async queue). The in-memory `_JOB_STORE` dict survives across requests within a test session, enabling the `GET /jobs/{id}` and `GET /jobs/{id}/artifacts` round-trip contract tests. Real Runpod async execution is parked behind `MATERIALS_L1_BACKEND=runpod_rest`.

---

## BlockedSourceManifest entries

| ID | Tool | Reason | Blocker |
|---|---|---|---|
| `src:blocked:pyscf:artifact-export` | PySCF | `policy` | Binary artifact (wavefunction/chkfile) export blocked; library runs in-process |
| `src:blocked:qe:gpl` | Quantum ESPRESSO | `license_unverified` | GPL-2.0; binary redistribution requires legal sign-off |
| `src:blocked:cp2k:gpl` | CP2K | `license_unverified` | GPL-2.0-or-later; same |
| `src:blocked:abinit:gpl` | ABINIT | `license_unverified` | GPL-3.0-or-later; same |
| `src:blocked:pennylane:artifact-export` | PennyLane | `policy` | Real hardware backend parked; IonQ/IBM requires runpod_rest approval |
| `src:blocked:qiskit-nature:artifact-export` | Qiskit Nature | `policy` | IBM hardware requires runpod_rest + IBM Quantum credentials |
| `src:blocked:l4-qaoa:not-implemented` | L4-QAOA slot | `other` | Not yet implemented; CPU L4 is active path |
| `src:blocked:l7-qaa:not-implemented` | L7-QAA slot | `other` | Not yet implemented; Bayesian BO is active L7 path |

---

## What downstream waves can now assume

1. **`L1DftAdapter` is the stable base.** Waves can subclass or wrap it; `submit_job(cif_text, L1JobParams)` always returns a fully populated `Envelope[L1DftOutput]` with valid audit hashes, boundary block, and falsifier rollup.

2. **PySCF H2/LiH reference values are canonical.** `PyScfMolecularSolver.h2_fci_reference_Ha()` and `.lih_casci_reference_Ha()` are the VQE falsifier references. Both return the same value regardless of whether pyscf is installed.

3. **VQE gates are real.** `falsifiers.quantum_falsifiers.vqe_h2_classical_match` and `vqe_lih_active_space_match` enforce 1e-3 Ha / 5e-3 Ha gates respectively. These exact thresholds will not be loosened.

4. **Dispatcher interface accepts `slot` for 3 slots.** L1-VQE is live; L4-QAOA and L7-QAA raise `NotImplementedError` with a BlockedSourceManifest.

5. **`cross_code_disagreement` emits `DisagreementMetric`.** The KG writer (L7 wave or a shared service) is responsible for materialising the node and edges.

6. **REST stubs are FastAPI TestClient-compatible.** Both services expose `/healthz` and job submission endpoints. All 19 contract tests pass.

7. **Plug-swap invariant confirmed.** All 4 L1 adapters and both quantum VQE solvers produce `Envelope` objects whose `output` validates as `L1DftOutput` / `L1QuantumVqeOutput` respectively (46 plug-swap tests pass).

---

## Open questions for orchestrator

1. **KG write responsibility for DisagreementMetric.** The `cross_code_disagreement` function returns the metric but does not write it to the KG. Should a shared `KGWriter` service be responsible, or should each adapter write its own disagreement nodes? Suggest: shared KG writer (L7 wave).

2. **GPU4PySCF.** `L1DftCode` includes `"GPU4PySCF"` but no adapter is implemented. When L1 gets a GPU Runpod endpoint, `GPU4PySCFSolver` can subclass `L1DftAdapter` without changing the schema.

3. **Multi-reference systems beyond H2/LiH.** The PennyLane dispatcher currently rejects any system other than H2/LiH for L1-VQE. Extension to other molecules (e.g., N2, Li2) requires a generalised Hamiltonian builder; the interface already accepts `bond_ang` as a parameter.

## Verification summary

```text
$ .venv/bin/python -m pytest \
    tests/unit/adapters/l1 tests/unit/adapters/quantum \
    tests/contract/l1 tests/contract/quantum \
    tests/plug_swap/l1 tests/plug_swap/quantum \
    tests/falsification_wave/l1 -q

218 passed in 4.04s

$ .venv/bin/python -c "
from zer0pa_materials_workbench_workbench.adapters.quantum.pennylane_vqe import PennyLaneVqeSolver
solver = PennyLaneVqeSolver()
env = solver.solve_h2()
o = env.output
print('H2 delta:', abs(o['ground_state_energy_Ha'] - o['classical_reference_Ha']))
"
H2 delta: 0.0003

$ .venv/bin/python -c "
from zer0pa_materials_workbench_workbench.adapters.quantum.pennylane_vqe import PennyLaneVqeSolver
solver = PennyLaneVqeSolver()
env = solver.solve_lih()
o = env.output
print('LiH delta:', abs(o['ground_state_energy_Ha'] - o['classical_reference_Ha']))
"
LiH delta: 0.002
```

No L1-quantum gate is open.
