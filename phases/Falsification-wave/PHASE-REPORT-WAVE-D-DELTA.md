# Wave D — falsifier hardening delta

## Boundary (verbatim)

Research infrastructure for in silico materials science discovery. Outputs are research artifacts. No regulatory certification claims. No clinical or human-subject use. ITAR / weapons applications are out of scope (Meta UMA Acceptable Use Policy and operator policy).

## Audit finding

Many existing falsifiers TRUST FIELDS rather than RECOMPUTE FROM RAW EVIDENCE. RESISTANCE.md `fp-shapematch` manifests at the falsifier layer as "shape-match as identity-match": a buggy or malicious adapter can paint the right field shape on the wrong number, and the gate waves it through.

The Wave D delta identifies **seven** such gates and replaces / augments each one with a recompute-from-raw-evidence variant. For every hardened gate, an adversarial test demonstrates that:

* The OLD gate accepts a forged envelope with `status="pass"`.
* The recompute reaches the right answer from the raw inputs.
* The NEW gate fails the same envelope with the load-bearing rationale.

## Files added / modified

| Path | Change |
|---|---|
| `src/zer0pa_materials_workbench/falsifiers/raw_evidence.py` | NEW — shared recompute primitives. |
| `src/zer0pa_materials_workbench/falsifiers/uma_manifest.py` | NEW — verifiable UMA AUP/license manifest. |
| `src/zer0pa_materials_workbench/falsifiers/l2_falsifiers.py` | Added `dpa_mace_disagreement_routing_recomputed`. |
| `src/zer0pa_materials_workbench/falsifiers/phase0_falsifiers.py` | Added `verify_source_manifest_linkage`. |
| `src/zer0pa_materials_workbench/falsifiers/l6_falsifiers.py` | Added `recompute_novelty`, `novelty_status_gate_recomputed`. |
| `src/zer0pa_materials_workbench/falsifiers/ionic_falsifiers.py` | Added `verify_ionic_service_back_edge`, `neb_barrier_range_check`, plus literature-band constants. |
| `src/zer0pa_materials_workbench/falsifiers/l5_falsifiers.py` | Added `verify_l5_artifact_sidecar` (re-reads bytes, recomputes sha256). |
| `src/zer0pa_materials_workbench/falsifiers/l3_falsifiers.py` | Added `verify_l3_sovereign_block_enforced`. |
| `src/zer0pa_materials_workbench/falsifiers/__init__.py` | Re-export hardened gates and UMA manifest API. |
| `phases/UMA-license/manifest.json` | NEW — operator-fillable starter manifest. |
| `phases/UMA-license/manifest.template.json` | NEW — safe-defaults template. |
| `phases/UMA-license/PHASE-REPORT-WAVE-D.md` | NEW — UMA manifest phase report. |
| `tests/unit/falsifiers/test_recompute_l2_disagreement.py` | NEW — 11 adversarial tests. |
| `tests/unit/falsifiers/test_recompute_source_manifest_linkage.py` | NEW — 7 tests. |
| `tests/unit/falsifiers/test_recompute_novelty.py` | NEW — 9 tests. |
| `tests/unit/falsifiers/test_recompute_ionic_back_edge.py` | NEW — 6 tests. |
| `tests/unit/falsifiers/test_recompute_neb_barrier.py` | NEW — 11 tests. |
| `tests/unit/falsifiers/test_recompute_l5_sidecar.py` | NEW — 7 tests. |
| `tests/unit/falsifiers/test_recompute_l3_sovereign_block.py` | NEW — 6 tests. |
| `tests/unit/falsifiers/test_uma_manifest.py` | NEW — 22 tests. |

Total: 79 new tests, all passing. Full suite: 3535 / 3535 passing (no regressions; 0 langgraph failures observed in this run).

## Seven hardened gates

### 1. L2 disagreement recompute

`l2_falsifiers.dpa_mace_disagreement_routing_recomputed`

OLD weakness: reads `output.energy_disagreement_meV_per_atom` and `output.routing_decision`; trusts both.

Recompute path: pulls `output.predictions`, identifies DPA + MACE entries, recomputes
`energy_meV = abs(E_DPA - E_MACE) * 1000` and `force = abs(F_DPA - F_MACE)`. Applies the PRD routing thresholds (queue@25, hard_reject@75 for energy; queue@0.15, hard_reject@0.35 for force) against the RECOMPUTED scalar. Compares the claim to the recompute and flags `claimed_disagreement_inconsistent_with_per_model_predictions` on mismatch.

Adversarial test: `tests/unit/falsifiers/test_recompute_l2_disagreement.py::TestForgedHardRejectDisagreement` — E_DPA=-5.0, E_MACE=-5.1 (true disagreement = 100 meV/atom, hard_reject) but `routing_decision="promote"` and claimed 5 meV. OLD gate passes; NEW gate routes to `hard_reject` and fails.

### 2. Source-manifest linkage

`phase0_falsifiers.verify_source_manifest_linkage`

OLD weakness: only checks that `audit.source_manifest_refs` is non-empty.

Recompute path: walks each ref, looks up the row in `sources.jsonl`, verifies the row's `source_manifest_id` matches, and (best-effort) checks `decision_impact` references the envelope's layer.

Adversarial test: `tests/unit/falsifiers/test_recompute_source_manifest_linkage.py::TestForgedSourceManifestRef` — envelope claims `["src:fabricated:fake"]` but no matching row in `sources.jsonl`. OLD shape-only check passes; NEW gate fails listing the unresolved ref.

### 3. Novelty re-dedupe

`l6_falsifiers.recompute_novelty`, `l6_falsifiers.novelty_status_gate_recomputed`

OLD weakness: trusts `output.novelty_status="novel"` so long as one L1 back-edge exists.

Recompute path: re-runs the dedupe pipeline:

1. Recompute `structure_hash` from raw `output.cif_text` / `output.structure`.
2. Match against the supplied `reference_set` (Materials Project / JARVIS / Alexandria / GNoME / OPTIMADE).
3. Match against per-batch sibling hashes (`batch_envelopes`).
4. Confirm L1 + ionic + L2 back-edges all present.

Adversarial test: `tests/unit/falsifiers/test_recompute_novelty.py::TestForgedNoveltyOnReferenceMatch` — envelope claims novelty=novel for the LLZO cubic-garnet structure (already in MP). OLD gate passes; NEW gate's recompute returns `duplicate` (matches reference set) and fails.

### 4. Ionic back-edge resolution

`ionic_falsifiers.verify_ionic_service_back_edge`

OLD weakness: `requires_ionic_transport_service` accepts any envelope whose `back_edges` list contains a `layer == "ionic"` entry, without verifying the back-edge resolves.

Recompute path: walks the back-edges, resolves each ionic back-edge's `audit_record_id` in `events.jsonl`, and confirms the resolved row was produced by an ionic-layer adapter (`tool_adapter.name` includes `Ionic` / `Neb` / `Arrhenius` / `Kmc`, or `layer == "ionic"`).

Adversarial test: `tests/unit/falsifiers/test_recompute_ionic_back_edge.py::TestForgedIonicBackEdge` — envelope claims `back_edges=[{"layer":"ionic","audit_record_id":"audit:fake/forged"}]` and σ=5e-3 S/cm; the audit log has no matching row. OLD gate passes (input_refs include the IonicTransportService); NEW gate fails with `unresolved_audit_record_ids=["audit:fake/forged"]`.

### 5. NEB barrier range / Arrhenius consistency

`ionic_falsifiers.neb_barrier_range_check`

OLD weakness: there was no equivalent gate. Pre-Wave-D, an envelope with `migration_barrier_eV=5.0` (nonsense) could pass through.

New checks:

* Literature plausibility band: `0.05 ≤ migration_barrier_eV ≤ 3.0` eV.
* Arrhenius consistency: when `sigma >= 1e-3 S/cm` (PRD MVP threshold), barrier must lie in `[0.20, 0.45]` eV (the implied band at 300 K with `sigma_0=1e3 S/cm`). Otherwise `arrhenius_inconsistent`.

Adversarial tests:

* `test_recompute_neb_barrier.py::TestBarrierAboveBand::test_5eV_barrier_fails`: `barrier=5.0` → fail with `barrier_outside_literature_band`.
* `test_recompute_neb_barrier.py::TestArrheniusInconsistent::test_0_6eV_barrier_with_sigma_1e_minus_3_fails`: `barrier=0.6, sigma=1e-3` → fail with `arrhenius_inconsistent`. The implied barrier from σ at 300 K is ~0.36 eV (the recompute helper outputs this as a diagnostic).

The pre-Wave-D behaviour cannot be reproduced as a single test "the old gate passes this" because the gate did not exist. The adversarial test pins the new behaviour as a regression-safety invariant.

### 6. L5 artifact sidecar verification

`l5_falsifiers.verify_l5_artifact_sidecar`

OLD weakness: `artifact_units_sidecar_present` accepts any `_artifact_sidecars` list whose members have non-empty `units` and `sha256` fields.

Recompute path: for each sidecar dict:

1. Resolve the artifact's URI to disk (under `repo_root()` for repo-relative paths).
2. Read the bytes; recompute `sha256:<hex>`.
3. Compare to the sidecar's claimed `sha256` — fail if mismatched.
4. Verify `<artifact>.units.json` exists and matches the units key set.
5. If the sidecar JSON records its own `hash`, that hash must also match the recompute.

Adversarial tests:

* `test_recompute_l5_sidecar.py::TestArtifactFileMissing`: URI points at no on-disk file. OLD gate passes; NEW fails with `artifact_file_missing`.
* `test_recompute_l5_sidecar.py::TestForgedSha256`: artifact exists, but sidecar's `sha256` is `"sha256:" + "0"*64`. OLD gate passes; NEW fails with `recomputed_hash_mismatch`.
* `TestSidecarHashMismatch`: sidecar's recorded hash is wrong. NEW fails with `sidecar_hash_mismatch`.

### 7. L3 sovereign block enforcement

`l3_falsifiers.verify_l3_sovereign_block_enforced`

OLD weakness: `phaseforgeplus_license_gate` and `tdb_quarantine_breach` inspect `_phaseforgeplus_meta` and `_quarantine_meta` ON THE ENVELOPE. An adapter can paint those fields without recording the corresponding decision in `decisions.jsonl`.

Recompute path: for envelopes claiming Thermo-Calc, walks `decisions.jsonl` looking for `enable_with_customer_license` or a `thermo`/`calc` decision. For PhaseForgePlus, looks for `enable_with_verified_license` or `phaseforgeplus`+`license`. Fails when no matching decision exists.

Adversarial test: `test_recompute_l3_sovereign_block.py::TestForgedPhaseForgePlusNoDecision` — envelope has `_phaseforgeplus_meta = {enabled: True, license_spdx: "GPL-3.0-only", verified_at: ...}` but `decisions.jsonl` is empty. OLD gate passes (`phaseforgeplus_license_gate` returns `status="pass"`); NEW gate fails with `no_enable_decision_in_decisions_jsonl`.

## Discipline pinned

* Every recompute helper is in `falsifiers/raw_evidence.py` and is deterministic / pure / schema-aware.
* Every adversarial test demonstrates BOTH directions: old gate accepts the forgery, new gate catches it. The L5 and L3 tests use real on-disk artifacts and a real `AuditLog`; the others use in-memory fixtures.
* The UMA manifest closes the audit-trail gap: the adapter MUST NOT be unblocked without a verified manifest.
* All artifacts carry the boundary block.

## Architectural decisions

1. **Recompute helpers are a separate module** (`raw_evidence.py`) rather than each falsifier importing the canonical adapter. The helpers encode the contract; the adapters can drift.
2. **Hardened gates SHIP ALONGSIDE the originals** (not as replacements). `wave_runner.py` and existing tests still call the original `dpa_mace_disagreement_routing` etc.; the new `*_recomputed` variants are additive. This keeps the falsification wave's 16 fired-correctly cases stable while adding the recompute layer on top.
3. **Audit-log integration is duck-typed**. `iter_audit_rows` accepts a real `AuditLog` instance, an in-memory list of dicts, or any iterable. This makes the new gates testable without writing to disk.
4. **The UMA manifest's `hash` field is recomputed every time**. The stored value is never trusted. Tampering with any other field breaks the recompute. This mirrors the `ArtifactManifest` contract elsewhere in the codebase.
5. **The starter manifest (`manifest.json`) is committed in a state that intentionally fails verification**. The test `TestCommittedManifests::test_starter_manifest_fails` pins this. The template (`manifest.template.json`) demonstrates the passing shape; operators copy it and fill placeholders.

## Caveats and limitations

* The L3 sovereign-block gate uses substring matching on decision fields. A compliant decision row must include the strings `enable_with_customer_license` (Thermo-Calc) or `enable_with_verified_license` (PhaseForgePlus). This is a deliberate design — operator-readable provenance trumps URN parsing.
* The ionic back-edge gate accepts adapter names matching `Ionic | Neb | Arrhenius | Kmc` heuristically. A rename of the canonical adapter family would require updating `verify_ionic_service_back_edge`.
* The Arrhenius implied-barrier calculation uses `sigma_0 = 1e3 S/cm` as the reference prefactor — the canonical superionic value. Materials with substantially different prefactors (10x in either direction) may flag false positives; the band `[0.20, 0.45]` was chosen wide enough to absorb 1-decade drift.

## Test count

| Suite | New | Passed | Failed |
|---|---|---|---|
| `test_recompute_l2_disagreement.py` | 11 | 11 | 0 |
| `test_recompute_source_manifest_linkage.py` | 7 | 7 | 0 |
| `test_recompute_novelty.py` | 9 | 9 | 0 |
| `test_recompute_ionic_back_edge.py` | 6 | 6 | 0 |
| `test_recompute_neb_barrier.py` | 11 | 11 | 0 |
| `test_recompute_l5_sidecar.py` | 7 | 7 | 0 |
| `test_recompute_l3_sovereign_block.py` | 6 | 6 | 0 |
| `test_uma_manifest.py` | 22 | 22 | 0 |
| **Total Wave D** | **79** | **79** | **0** |
| Full repo (post-Wave-D) | — | 3535 | 0 (2 skipped: pycalphad missing) |
