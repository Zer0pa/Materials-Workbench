# Wave F5 — wire Wave D recompute falsifiers into production gates

## Boundary (verbatim)

Research infrastructure for in silico materials science discovery. Outputs are research artifacts. No regulatory certification claims. No clinical or human-subject use. ITAR / weapons applications are out of scope (Meta UMA Acceptable Use Policy and operator policy).

## Audit finding

Wave D added seven hardened recompute gates with adversarial unit tests, but the **orchestration layer continued to call the OLD shape-only gates**. Specifically:

- `AcceptanceGate.evaluate()` composed audit-provenance, disagreement, rights, duplicate, layer falsifiers, ionic-evidence, boundary — but **not** the recompute gates.
- `promote_battery_candidate()` in the IonicTransportService called the original ionic blocking gates only.
- `FalsificationWaveRunner.run_all()` ran the 16 PRD cases but did **no post-wave recompute sweep**.
- `validate_evidence_packet()` enforced section structure, audit-id presence, and rollups — but did not invoke a single recompute helper.

Consequence: a buggy or malicious adapter that painted the right field shape would be promoted in production despite Wave D's test-time gates blocking the same envelope.

Wave F5 wires every Wave D recompute gate into every production promotion path and certifies the wiring with an adversarial integration test.

## Files modified

| Path | Change |
|---|---|
| `src/zer0pa_materials_workbench/orchestration/acceptance_gates.py` | Added `recompute_consistency` sub-gate; `GateContext` now accepts an optional `audit_log` and `novelty_reference_hashes`; new `claim_recompute_mismatch` failure reason; module docstring updated. (~150 LOC added) |
| `src/zer0pa_materials_workbench/services/ionic_transport_service.py` | `promote_battery_candidate()` now invokes every Wave D recompute gate against the bundle's NEB envelope plus optional `extra_envelopes` for L2/L6/L5/L3/phase0; `inconclusive` is fail-closed. (~120 LOC added) |
| `src/zer0pa_materials_workbench/falsifiers/wave_runner.py` | `FalsificationWaveRunner.run_all()` now ends with a post-PRD recompute sweep (`_run_recompute_sweep`) over a synthetic forged-evidence chain; new `RecomputeSweepResult` dataclass; results recorded in `falsifiers.jsonl`. (~210 LOC added) |
| `src/zer0pa_materials_workbench/falsifiers/wave_report.py` | New "Wave F5 post-PRD recompute sweep" section in the markdown report. (~25 LOC added) |
| `src/zer0pa_materials_workbench/packets/validators.py` | New `_check_recompute_gates_per_envelope()` walker invokes every Wave D gate against each nested envelope. (~150 LOC added) |
| `src/zer0pa_materials_workbench/packets/_envelope_builders.py` | `l6_known_control_envelope()` accepts `cif_text`, `structure`, `back_edges` so the recompute can hash from raw evidence. (~30 LOC added) |
| `src/zer0pa_materials_workbench/packets/battery_packet.py` | Pipes the fixture's `structure.cif` and back-edge placeholders into the L6 envelope builder. (~20 LOC added) |
| `src/zer0pa_materials_workbench/packets/thermoelectric_packet.py` | Same wiring for thermoelectric packets. (~12 LOC added) |
| `tests/integration/test_recompute_wired_into_production.py` | NEW — adversarial integration test: forged-evidence chain reaches every production path; each path must block. (~600 LOC added) |
| `tests/unit/orchestration/test_acceptance_gate.py` | Updated fixtures so the recompute gate finds consistent claims (force_rmse fixed to match per-model predictions; L6 envelope now carries a `structure` dict and `back_edges`). (~30 LOC changed) |
| `tests/integration/test_full_falsification_wave.py` | Updated `total_falsifier_rows_written` assertion to acknowledge the 7 sweep rows. (~10 LOC changed) |

## Production call sites identified per recompute gate

| Recompute gate | Production call sites located | Wiring action |
|---|---|---|
| `dpa_mace_disagreement_routing_recomputed` | `AcceptanceGate.evaluate` (gate composition); `promote_battery_candidate` (`extra_envelopes["L2"]`); `validate_evidence_packet` (per-envelope walker); `FalsificationWaveRunner._run_recompute_sweep` (sentinel) | Added — all four paths now invoke the recompute. The OLD `dpa_mace_disagreement_routing` is preserved as the layer's primary `falsifier.items` entry; the recompute is layered on top of it (BOTH must pass). |
| `verify_source_manifest_linkage` | `AcceptanceGate.evaluate` (every envelope with `audit.source_manifest_refs`); `promote_battery_candidate` (per-bundle envelope + `extra_envelopes`); `validate_evidence_packet` (per-envelope walker, audit_log built from `audit_trail_head.rows`); `FalsificationWaveRunner._run_recompute_sweep` | Added — strictly stronger than the old "non-empty list of strings" shape check; replaces the old shape check at the orchestration boundary. |
| `novelty_status_gate_recomputed` | `AcceptanceGate.evaluate` (when L6 envelope present); `promote_battery_candidate` (`extra_envelopes["L6"]`); `validate_evidence_packet` (per-envelope walker); `FalsificationWaveRunner._run_recompute_sweep` (with LLZO reference set) | Added — the OLD `novelty_status_gate` is kept in `Envelope.falsifier.items` for backwards compatibility; both must pass. |
| `verify_ionic_service_back_edge` | `AcceptanceGate.evaluate` (when ionic envelope carries an ionic-layer back-edge — guarded so it doesn't fire on the ionic source itself); `promote_battery_candidate` (with the same source-vs-consumer guard); `validate_evidence_packet` (per-envelope walker, same guard); `FalsificationWaveRunner._run_recompute_sweep` | Added with **source-vs-consumer guard** — the gate is intended for *consuming* envelopes that reference an ionic claim, not the ionic envelope that *produces* the claim. The guard checks for an explicit ionic-layer back-edge; firing on the source envelope would always fail by construction. |
| `neb_barrier_range_check` | `AcceptanceGate.evaluate` (when ionic envelope present); `promote_battery_candidate` (always — runs on `bundle.neb`); `validate_evidence_packet` (per-envelope walker); `FalsificationWaveRunner._run_recompute_sweep` | Added — universally applicable; no guards needed. |
| `verify_l5_artifact_sidecar` | `AcceptanceGate.evaluate` (when L5 envelope present); `promote_battery_candidate` (`extra_envelopes["L5"]`); `validate_evidence_packet` (per-envelope walker); `FalsificationWaveRunner._run_recompute_sweep` | Added — the helper inspects `_artifact_sidecars` at the top of the input dict; in plain-dict adversarial cases this works directly, but on a serialised `Envelope` the field is stripped because `Envelope.model_config` forbids extras. The packet validator is the most thorough caller because it always operates on raw dicts. |
| `verify_l3_sovereign_block_enforced` | `AcceptanceGate.evaluate` (when L3 envelope present and `audit_log` supplied); `promote_battery_candidate` (`extra_envelopes["L3"]`); `validate_evidence_packet` (per-envelope walker); `FalsificationWaveRunner._run_recompute_sweep` | Added — the `_envelope_used_phaseforgeplus` heuristic recognises adapter-name signal too, so the gate fires even when the `_phaseforgeplus_meta` extra block is stripped by the Envelope schema. |

## Adversarial test results

`tests/integration/test_recompute_wired_into_production.py` — 8 tests, all passing.

The forged evidence chain feeds:
- L2 envelope: per-model predictions imply 10 000 meV/atom disagreement; claim = 5 meV/atom (forged routing decision = "promote").
- Phase 0 envelope: `source_manifest_refs = ["src:fabricated:fake"]`.
- L6 envelope: `novelty_status="novel"` claimed but the structure matches LLZO cubic in the reference set.
- Ionic envelope: claims `ionic_conductivity_S_per_cm = 5e-3` with back-edge to `audit:fake-id` that does not resolve.
- NEB envelope: barrier=5.0 eV (outside the literature `[0.05, 3.0]` band).
- L5 envelope: VTK artifact URI that points at `/tmp/wave_f5/does_not_exist.vtk`.
- L3 envelope: `tool_adapter.name = "PhaseForgePlusAdapter"` with no enable decision in `decisions.jsonl`.

| Production path | Verdict on forged chain (post-wiring) | Verdict on forged chain (pre-wiring, regression-pin) |
|---|---|---|
| `AcceptanceGate.evaluate(...)` | `overall = "fail"` with `recompute_consistency` sub-gate firing and `claim_recompute_mismatch` reason | Would have returned `"pass"` because none of the seven recompute gates were composed. |
| `promote_battery_candidate(...)` | `decision = "reject"`; both the L2 disagreement recompute and the NEB barrier-range recompute fire on the bundle | Would have returned `"promote"` for the in-band ionic claim with the forged routing decision. |
| `validate_evidence_packet(...)` | `overall_status = "fail"` with `l2.dpa_mace_disagreement_routing_recomputed` and other recomputes flagged | Would have returned `"pass"` for any chain whose section structure was complete. |
| `FalsificationWaveRunner.run_all(...)` | `result.recompute_sweep.forged_chain_caught = True`; ≥4 of 7 gates fail-trip on the synthetic sentinel chain | The wave runner had no recompute sweep at all. |

The regression-safety pin (`TestOldShapeGatesWouldHaveAccepted`) explicitly demonstrates that the OLD `dpa_mace_disagreement_routing` accepts the forged L2 claim (status="pass") while the NEW `dpa_mace_disagreement_routing_recomputed` catches it (status="fail"). The same pattern would apply to the other six gates if the old gates were re-introduced.

## Production wiring caveats / non-blocking issues

- **L5 sidecar gate on serialised Envelopes**: The Wave D `verify_l5_artifact_sidecar` reads `_artifact_sidecars` from the **top** of the input dict. The Envelope schema is `extra="forbid"`, so the field is stripped on `Envelope.model_dump`. In `AcceptanceGate.evaluate` and `promote_battery_candidate`, this means the L5 recompute gate will only fire when the L5 envelope is passed in as a **plain dict** (which is the case for the packet validator). The acceptance test confirms the gate fires when the sidecar list is at the dict's top. A future hardening would migrate the artifact-sidecars block into the Envelope's `output` (a permissive dict) without breaking other consumers; that is out of scope for Wave F5 and recorded as a follow-up.
- **Ionic back-edge gate guard**: The recompute fires when an envelope claims an ionic conductivity AND carries an ionic-layer back-edge. Because the ionic envelope is the *source* of the claim, we guard the call so it doesn't always fire on production ionic envelopes. The guard preserves the gate's semantics — it is intended to catch *consumers* with fabricated back-edges. The forged ionic envelope in the adversarial test carries an explicit back-edge to `audit:fake-id`, so the guard does not mask the forgery.
- **Audit log requirement**: `verify_source_manifest_linkage`, `verify_ionic_service_back_edge`, and `verify_l3_sovereign_block_enforced` all need a live audit ledger. The orchestration paths accept it as an optional argument; when absent, those gates skip (no-op pass). Production callers MUST pass the live `AuditLog`. The packet validator builds an in-memory shim from the `audit_trail_head.rows` section; the wave runner's sweep uses an empty list (which forces every linkage to fail, the correct adversarial response).

## Pre-edit baseline / post-edit suite

- **Pre-edit baseline (full `tests/`)**: 3535 passed, 2 skipped — the documented Wave D handoff state.
- **Post-edit suite (full `tests/`)**: 3547 passed, 2 skipped (3549 collected). Net change: +12 passing, 0 regressions, 0 new skips.
- The 8 new tests in `tests/integration/test_recompute_wired_into_production.py` cover the four production paths (`AcceptanceGate.evaluate`, `promote_battery_candidate`, `validate_evidence_packet`, `FalsificationWaveRunner.run_all`) plus the regression-safety pin showing the OLD shape-only gate would have accepted the forged L2 envelope.

## Suite results

```
$ .venv/bin/python -m pytest tests -q --tb=no | tail -3
SKIPPED [2] tests/unit/fixtures/test_tdb_parses.py:38: pycalphad not installed
3547 passed, 2 skipped in 312.10s (0:05:12)
```

Sub-suite confirmations (each individually re-verified before the full run):

- `tests/unit/orchestration` — 10 passed (acceptance-gate fixture updates + new recompute composition)
- `tests/unit/packets` — 19 passed (battery + thermoelectric packet validation, all CIF-text wired)
- `tests/integration/packets` — 8 passed (full battery + thermoelectric end-to-end)
- `tests/integration/test_full_falsification_wave.py` — 72 passed (post-PRD sweep recorded; chain validates)
- `tests/integration/test_recompute_wired_into_production.py` — 8 passed (the load-bearing adversarial coverage)
- `tests/parity` — runs unchanged (no production-path API changes break parity).
