# Falsification Wave Report — Wave 6

## Boundary

Research infrastructure for in silico materials science discovery. Outputs are research artifacts. No regulatory certification claims. No clinical or human-subject use. ITAR / weapons applications are out of scope (Meta UMA Acceptable Use Policy and operator policy).

## Run metadata

- **Started at:** `2026-04-30T06:19:18.702669+00:00`
- **Finished at:** `2026-04-30T06:19:18.750486+00:00`
- **Operator:** `wave6-final`
- **Repo commit:** `cf374d07972eb7d03bf79cbcf2e1f1f8a1308c01` (branch `main`)
- **Audit dir:** `/Users/zer0palab/Materials Pipeline/audit/wave6`
- **Python:** `3.13.12` on `Darwin`

## Verdict semantics (inverted)

This wave is **adversarial**. A `PASS` verdict means the gate FIRED CORRECTLY when shown its deliberate failure. A `FAIL` verdict means the gate DID NOT FIRE — that is a real bug in the layer's falsifier and must be surfaced for a fix loop. A `WARN` (spurious) verdict means the target fired but at least one undocumented extra falsifier also fired; the wave still detected the deliberate failure but the per-layer attribution discipline weakened. A `chain_break` verdict means the audit hash chain failed validation after the case was recorded — that is also a hard failure.

## Aggregate

| Metric | Count |
|---|---|
| Cases run | 16 |
| Fired correctly (target = target, no extras, chain valid) | 16 |
| Missed (target did NOT fire — real bug) | 0 |
| Spurious extras (target fired but >0 undocumented co-fires) | 0 |
| Audit chain broke after case | 0 |
| Total falsifier rows in `falsifiers.jsonl` | 18 |
| Total decision rows in `decisions.jsonl` | 16 |
| KG nodes after wave | 16 |
| Audit hash chain validates (post-wave) | **yes** |

## Per-case verdict

| Case | Fixture | Expected layer | Target falsifier | Fired (status=fail) | Verdict |
|---|---|---|---|---|---|
| invalid_cif | invalid_cif | L6 | l6.cif_valid | l6.cif_valid=fail | PASS |
| duplicate_candidate | duplicate_candidate | L6 | l6.dedup_unique | l6.dedup_unique=fail | PASS |
| missing_boundary | missing_boundary | A0 | boundary.missing_or_wrong | boundary.missing_or_wrong=fail | PASS |
| missing_source_manifest | (synthesizer) | phase0 | phase0.kg_literature_source_written | phase0.kg_literature_source_written=fail, phase0.kg_property_observation_written=fail | PASS |
| ungrounded_property | ungrounded_property | phase0 | phase0.grounding_required | phase0.grounding_required=fail | PASS |
| high_disagreement | high_disagreement | L2 | l2.dpa_mace_disagreement_routing | l2.dpa_mace_disagreement_routing=fail | PASS |
| dft_convergence_failure | (synthesizer) | L1 | l1.screening_convergence_delta | l1.screening_convergence_delta=fail | PASS |
| ionic_overclaim_no_service | ionic_overclaim_no_service | ionic | ionic.requires_ionic_transport_service | ionic.requires_ionic_transport_service=fail | PASS |
| unstable_phonon | unstable_phonon | L1.5 | l15.dynamical_stability | l15.dynamical_stability=fail | PASS |
| unreadable_tdb | unreadable_tdb | L3 | l3.tdb_parses_in_pycalphad | l3.tdb_parses_in_pycalphad=fail | PASS |
| phasefield_conservation_violation | (synthesizer) | L4 | l4.cahn_hilliard_mass_drift | l4.cahn_hilliard_mass_drift=fail | PASS |
| non_spd_tensor | non_spd_tensor | L5 | l5.tensor_spd | l5.tensor_spd=fail | PASS |
| alabos_executable_in_recipe_only | alabos_executable_in_recipe_only | L7 | l7.alabos_recipe_only_enforcement | l7.alabos_recipe_only_enforcement=fail | PASS |
| tenant_only_tuple_leak | tenant_only_tuple_leak | L7 | l7.tenant_only_tuple_leak | l7.candidate_promotion_provenance=fail, l7.tenant_only_tuple_leak=fail | PASS |
| runpod_schema_drift | runpod_schema_drift | L7 | runpod.hard_failure.schema_drift | runpod.hard_failure.schema_drift=fail | PASS |
| tdb_quarantine_breach | tdb_quarantine_breach | L3 | l3.tdb_quarantine_breach | l3.tdb_quarantine_breach=fail | PASS |

## Documented co-fires (allowed extras)

- `ionic_overclaim_no_service` → also accepts: ['l15.phonon_does_not_substitute_for_ionic']
- `missing_source_manifest` → also accepts: ['phase0.kg_property_observation_written']
- `runpod_schema_drift`: (none — single-trigger only)
- `tenant_only_tuple_leak` → also accepts: ['l7.candidate_promotion_provenance']
- `ungrounded_property`: (none — single-trigger only)

## Verified working

The following 16 adversarial case(s) fired their PRD-mandated target falsifier with `status=fail`, with no undocumented co-fires and a clean audit hash chain after the row was recorded:

- `invalid_cif` → `l6.cif_valid`
- `duplicate_candidate` → `l6.dedup_unique`
- `missing_boundary` → `boundary.missing_or_wrong`
- `missing_source_manifest` → `phase0.kg_literature_source_written`
- `ungrounded_property` → `phase0.grounding_required`
- `high_disagreement` → `l2.dpa_mace_disagreement_routing`
- `dft_convergence_failure` → `l1.screening_convergence_delta`
- `ionic_overclaim_no_service` → `ionic.requires_ionic_transport_service`
- `unstable_phonon` → `l15.dynamical_stability`
- `unreadable_tdb` → `l3.tdb_parses_in_pycalphad`
- `phasefield_conservation_violation` → `l4.cahn_hilliard_mass_drift`
- `non_spd_tensor` → `l5.tensor_spd`
- `alabos_executable_in_recipe_only` → `l7.alabos_recipe_only_enforcement`
- `tenant_only_tuple_leak` → `l7.tenant_only_tuple_leak`
- `runpod_schema_drift` → `runpod.hard_failure.schema_drift`
- `tdb_quarantine_breach` → `l3.tdb_quarantine_breach`

---

_This report is the artifact cited by `EXECUTION-REPORT.md` per PRD §Acceptance Gates / Falsification wave. The 16 cases include the 15 PRD-mandated deliberate failures plus the L3 quarantine-breach negative fixture delivered in A2. Every case must show: input that should fail → exactly the right falsifier fires → no others fire spuriously._
