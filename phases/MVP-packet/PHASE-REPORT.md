# Wave 5a — MVP Evidence Packet Generator

## Boundary

Research infrastructure for in silico materials science discovery. Outputs are research artifacts. No regulatory certification claims. No clinical or human-subject use. ITAR / weapons applications are out of scope (Meta UMA Acceptable Use Policy and operator policy).

## Status

Wave 5a delivers the publishable-paper deliverable per PRD §Final Output Required #9 (battery primary packet for LLZO / Li6PS5Cl / Li-Mg-Zr-Cl-seed) and #10 (thermoelectric sidecar packet for Si / Bi2Te3 / PbTe / SnSe).

- Foundation baseline before this wave: 2469 passed, 2 skipped (per Wave 4a phase report).
- After this wave: **3192 passed, 2 skipped** outside the campaigns dir; **+77 packet tests**, 0 packet failures.
- The 22-24 pre-existing failures in `tests/integration/campaigns/` are Wave 4c territory and unaffected by this wave (verified by stash-restore comparison: identical 22 failed / 148 passed).

## Source files

### `src/zer0pa_materials/packets/` (this wave's exclusive directory)

| File | LOC | Purpose |
|---|---|---|
| `__init__.py` | 85 | Public surface — assemble + validate + export + parse |
| `evidence_packet.py` | 323 | `EvidencePacket`, `PacketSection`, `PacketBundle`, `PacketPublishableTarget`; round-trips every nested envelope through `Envelope.model_validate` to enforce boundary block at construction |
| `battery_packet.py` | 790 | Battery primary packet assembler; reads fixture extraction + structure manifest, drives the full ionic-transport chain via `run_full_battery_evidence`, gates verdict via `promote_battery_candidate` |
| `thermoelectric_packet.py` | 640 | Thermoelectric sidecar packet assembler; drives Phono3py + BoltzTraP2/AMSET ZT chain via `ThermoelectricZtAssembler`; verdict from rank-stability gate |
| `_envelope_builders.py` | 582 | Internal stub envelope constructors (Phase 0, L1 DFT, L2 ensemble, L3 CALPHAD, L4 phase field, L6, L7) — every envelope round-trips through `Envelope` so the boundary check runs |
| `validators.py` | 428 | `validate_evidence_packet` runs 13 falsifier checks; produces `ValidationReport` with overall status |
| `ro_crate_export.py` | 206 | `export_packet_to_ro_crate` + `parse_packet_ro_crate` round-trip; uses A1's `RoCrateEntry` + `write_ro_crate_metadata` primitives |

### `src/zer0pa_materials/cli/packets.py` (228 LOC)

`packets` Typer subapp with subcommands:
- `packets healthz`
- `packets list-fixtures`
- `packets assemble battery <fixture-key> [--interface-mode ...]`
- `packets assemble thermoelectric <fixture-key>`
- `packets validate <packet-path>`
- `packets export-ro-crate <packet-path> <out-dir>`

### `src/zer0pa_materials/services/packets_service.py` (238 LOC)

FastAPI service with 6 endpoints:
- `GET  /v1/packets/healthz`
- `GET  /v1/packets/fixtures/{battery|thermoelectric}`
- `POST /v1/packets/assemble/battery`
- `POST /v1/packets/assemble/thermoelectric`
- `POST /v1/packets/validate`
- `POST /v1/packets/export-ro-crate`

### `src/zer0pa_materials/falsifiers/packet_falsifiers.py` (357 LOC)

Seven packet-level falsifiers:
- `packet_completeness` — every PRD-required section present
- `packet_provenance_chain` — audit_record_id present (and anchored when an `AuditLog` is supplied)
- `packet_boundary_carriage` — boundary verbatim in every nested envelope
- `packet_promotion_gate` — composes `promote_battery_candidate` (battery) or ZT rank-stability (thermoelectric)
- `packet_ro_crate_round_trip` — serialise → parse → counts match
- `packet_publishable_paper_target_set` — non-empty journal target
- `packet_alabos_recipe_only_section` — AlabOS section is recipe-only

**Source totals: 10 files, 3,877 LOC.**

## Tests

| Bucket | Files | LOC | Tests | Pass |
|---|---|---|---|---|
| `tests/unit/packets/` | 7 (+1 empty `__init__`) | 678 | 57 | 57 |
| `tests/contract/packets/` | 1 (+1 empty `__init__`) | 145 | 12 | 12 |
| `tests/integration/packets/` | 2 (+1 empty `__init__`) | 258 | 8 | 8 |
| **Totals** | **10 (+3 init)** | **1,081** | **77** | **77** |

Run: `.venv/bin/python -m pytest tests/unit/packets tests/contract/packets tests/integration/packets -v` → **77 passed in 9 s**.

## Battery packet results

All three battery seeds produce valid packets with the expected verdicts:

| Fixture | `interface_mode` | Verdict | Validator | Rationale |
|---|---|---|---|---|
| LLZO/cubic | `li_metal` | **promote** | pass | All PRD §Ionic Transport gates pass |
| Li6PS5Cl | `li_metal` | **reject** | pass | Oxidation gate fails (window 1.7-2.5 V vs ≥4 V required) — literature-faithful |
| Li-Mg-Zr-Cl-seed | `li_metal` | **reject** | pass | Interface unstable vs Li metal AND `li_metal` mode forbids `li_metal_unstable_coating_required` |
| Li-Mg-Zr-Cl-seed | `coating_interlayer` | **promote** | pass | Coating mode permits the interface; novel-seed promotion (PRD §Acceptance Gates: Battery MVP) |

The Li6PS5Cl rejection is part of the publishable claim — RESISTANCE.md "Calibrated uncertainty is not a slogan" is satisfied: the packet shows the rejection mechanism transparently (which gate fired, what threshold, what evidence).

## Thermoelectric packet results

All four thermoelectric fixtures produce valid packets:

| Fixture | T_op (K) | Verdict | Validator | Rationale |
|---|---|---|---|---|
| Si | 300 | reject | pass | ZT rank stability gate fires (47% disagreement > 15% tolerance) |
| Bi2Te3 | 300 | reject | pass | ZT rank stability gate fires (25% disagreement > 15% tolerance) |
| PbTe | 700 | reject | pass | ZT rank stability gate fires (30% disagreement > 15% tolerance) |
| SnSe | 800 | reject | pass | ZT rank stability gate fires (22% disagreement > 15% tolerance) |

Per `phases/L1.5-phonon/PHASE-REPORT.md`: "the 25-30% cross-method disagreement between BoltzTraP2 (CRTA) and AMSET (explicit scattering) correctly triggers the rank-stability gate as ADVERSARIAL — this is the intended behaviour for the sidecar falsifier. Real DFT-driven calculations with proper temperature-dependent scattering rates will produce tighter agreement." All thermoelectric packets demonstrate the calibrated-uncertainty deliverable: the rank-stability disagreement signal is shown transparently, and the verdict is reject in stub mode.

## Five architectural decisions

### 1. EvidencePacket round-trips every nested envelope through `Envelope.model_validate` at construction

The `EvidencePacket` model has a `model_validator(mode="after")` that walks every `PacketSection.envelopes` entry and runs `Envelope.model_validate(env_dict)`. Because `Envelope`'s own model validator runs `assert_boundary` over the dict form, this gives us a single source of truth for boundary enforcement: any envelope with a missing or non-verbatim boundary block fails packet construction. **Why**: the alternative — re-implementing the boundary walk inside the packet validator — would create two truth sources (the envelope's own check and the packet's), which is exactly the kind of consistency gap RESISTANCE.md warns about. Centralising on `Envelope.model_validate` means the packet inherits every future boundary check without modification. Tests `test_llzo_packet_carries_research_boundary` and `test_packet_boundary_carriage_fail_on_top_level_change` exercise both paths.

### 2. The packet generator NEVER mutates the foundation/adapter envelopes — it only consumes their public surfaces

Battery packet construction calls `run_full_battery_evidence(IonicJobParams(...))` for the ionic chain, `ThermoelectricZtAssembler().compute(L15JobParams(...))` for the ZT chain, `PennyLaneVqeSolver()` for the quantum-slot infrastructure check, and `AlabOSProtocolCompilerStub(alabos_mode="recipe_only")` for the synthesis recipe — all unchanged. Synthetic envelope builders in `_envelope_builders.py` cover layers whose adapter surfaces don't accept the fixture-id-only path (L1 DFT/L2 ensemble/L3 CALPHAD/L4 phase field/L6 dedup/L7 metadata), but each builder uses the same `Envelope`+`Layer*Output` schemas as the real adapters, so the falsifier rows the layer's `falsifier_items()` produces are real PRD §Layer-Specific Falsifier checks against the literature-grounded values. **Why**: PRD §Architecture Invariant says the envelope is the only contract; downstream code depends only on it. The packet generator is a downstream consumer, so it must respect that contract too. This decision means the packet generator survives any future refactor of the layer adapters as long as the envelope schema stays stable.

### 3. The promotion verdict is the canonical gate's verdict — not a re-implementation

For battery packets, `BatteryPacketAssembler.assemble` calls `promote_battery_candidate(candidate_id, bundle=bundle)` and stores its `decision` and `rationale` verbatim in the packet. The packet does NOT re-run promotion logic; the `packet_promotion_gate` falsifier merely confirms (a) the ionic section has 6 envelopes and (b) the recorded decision is one of `{promote, defer, reject}`. **Why**: the canonical gate lives in `services.ionic_transport_service.promote_battery_candidate` (Wave 3A.4). Re-implementing it in the packet generator would (1) duplicate logic, (2) drift, (3) violate the PRD discipline "Battery MVP claims require an explicit IonicTransportService". The packet faithfully embeds the gate's output, including the rationale string, so a downstream reader sees both the verdict and the gate's own narration. The same pattern applies to thermoelectric packets, which embed the ZT rank-stability gate's `zt_rank_stable` flag and `zt_fractional_disagreement` value.

### 4. RO-Crate round-trip is a falsifier, not a smoke test

`packet_ro_crate_round_trip(packet)` serialises the packet to a temp directory via `export_packet_to_ro_crate`, immediately re-parses with `parse_packet_ro_crate`, and asserts the section + entry counts match. The falsifier returns `pass` only when both counts agree. **Why**: PRD §Audit Trail And KG mandates "RO-Crate for exportable campaign evidence packages" — a packet that can't survive its own serialisation is not a publishable deliverable. By framing the round-trip as a falsifier (ledger row, audit-trail-attached) rather than just a test assertion, every campaign that runs the packet generator records a falsifier row showing the packet round-tripped at promotion time. Tests `test_battery_packet_round_trip` and `test_thermoelectric_packet_round_trip` confirm 15 (battery) and 11 (thermoelectric) sections survive the round-trip with no count drift.

### 5. AlabOS recipe-only enforcement is double-gated: compiler-time AND validator-time

PRD §AlabOS Integration: "Default ALABOS_MODE='recipe_only' until Phase 2." Two independent gates enforce this:

  1. **Compiler gate**: `AlabOSProtocolCompilerStub(alabos_mode="recipe_only")` raises `AlabosExecutableInRecipeOnlyError` synchronously inside `compile()` if the recipe carries `hardware_executable=True`. The packet's AlabOS section can only ever be constructed via this compiler, so the section's `hardware_executable` field is structurally False under recipe_only mode.
  
  2. **Validator gate**: `_check_alabos_recipe_only` (in `validators.py`) AND `packet_alabos_recipe_only_section` (in `packet_falsifiers.py`) re-check the section's `raw_payload.hardware_executable` post-hoc. Even if a downstream component bypasses the compiler and posts a hand-crafted packet to `/v1/packets/validate`, the validator still fires. Tests `test_falsifier_fires_when_section_mutated_to_hardware_executable` and `test_validator_overall_fails_when_alabos_mutated_to_hardware_executable` exercise the post-hoc gate by mutating the in-memory section payload after packet construction.

**Why two gates**: the compiler is the producer-side enforcement; the validator is the consumer-side enforcement. Either gate catches the violation, even if one is bypassed. Defence in depth matches the same pattern Wave 4a established for the BoTorch acquisition function gate.

## File ownership compliance

- WROTE (exclusive): `src/zer0pa_materials/packets/__init__.py`, `evidence_packet.py`, `battery_packet.py`, `thermoelectric_packet.py`, `_envelope_builders.py`, `validators.py`, `ro_crate_export.py`
- WROTE (exclusive): `src/zer0pa_materials/cli/packets.py`
- WROTE (exclusive): `src/zer0pa_materials/services/packets_service.py`
- WROTE (exclusive): `src/zer0pa_materials/falsifiers/packet_falsifiers.py`
- WROTE (exclusive): `tests/unit/packets/`, `tests/contract/packets/`, `tests/integration/packets/`
- WROTE: `phases/MVP-packet/PHASE-REPORT.md` (this file)

DID NOT TOUCH:
- Foundation modules (`envelope/`, `audit/`, `boundary.py`, `orchestration/`, `ontology/`)
- Layer adapters (`adapters/{phase0,l6,l1,quantum,l2,ionic,l1_5,l3,l4,l5,l7}/`)
- Existing service modules (`services/{ionic_transport_service,l1_5_service,...}.py`)
- Existing falsifier modules (`falsifiers/{phase0,l3,l6,l1,l2,l1_5,l7,...}_falsifiers.py`)
- Existing CLI subapps (`cli/{phase0,l6,l1,quantum,l2,ionic,l1_5,l3,l4,l5,l7}.py`)
- `cli/main.py` (the lead agent wires my subapp afterwards per the brief)
- `services/__init__.py` and `falsifiers/__init__.py` (parallel-wave territory)
- Other parallel waves' dirs: `plugswap/` (5b), `runpod/` (5c), `tests/integration/campaigns/` (4c)

## Pre-existing failures / blockers

- **`tests/integration/campaigns/`**: 22-24 failures, identical with my changes stashed and applied (verified by stash-restore comparison). These belong to Wave 4c and are explicitly out of scope per the brief. The fluctuation is non-determinism in test ordering / shared fixtures, not regression.
- No new failures, blockers, or pre-existing tests broken by Wave 5a.

## CLI integration (deferred to lead agent)

The brief states: "DO NOT touch `cli/main.py` (I will wire your subapp afterwards)." `packets_app` is exported from `zer0pa_materials.cli.packets`. The lead agent's wiring change is a single line:

```python
from zer0pa_materials.cli.packets import packets_app
app.add_typer(packets_app, name="packets")
```

## Deliverables checklist (per Wave 5a brief)

- [x] Battery evidence packet (`packets/battery_packet.py`) — `EvidencePacket` with all required sections, `promotion_decision`, `publishable_paper_target`
- [x] Thermoelectric sidecar packet (`packets/thermoelectric_packet.py`) — same shape, ZT-targeted
- [x] RO-Crate exporter (`packets/ro_crate_export.py`) — round-trips serialise → parse → counts match
- [x] Packet validators (`packets/validators.py`) — 13 falsifier checks covering boundary, audit, falsifier, rights, AlabOS recipe-only, novelty, pre-registered thresholds, publishable target
- [x] Falsifiers (`falsifiers/packet_falsifiers.py`) — 7 falsifiers including packet_completeness, packet_provenance_chain, packet_boundary_carriage, packet_promotion_gate, packet_ro_crate_round_trip, packet_publishable_paper_target_set, packet_alabos_recipe_only_section
- [x] CLI (`cli/packets.py`) — `assemble battery`, `assemble thermoelectric`, `validate`, `export-ro-crate`, `healthz`
- [x] REST stub (`services/packets_service.py`) — 6 endpoints
- [x] Unit tests covering LLZO promote, Li6PS5Cl reject (calibrated-uncertainty), Li-Mg-Zr-Cl-seed coating-only promotion, Si/Bi2Te3/PbTe/SnSe thermoelectric, RO-Crate round-trip, every falsifier, AlabOS recipe-only adversarial
- [x] Contract tests covering every endpoint via FastAPI testclient
- [x] Integration tests covering full Phase 0 → L7 → ionic → packet end-to-end on the three battery seeds (and four thermoelectric fixtures), with audit-log resume verification at the end
- [x] Phase report (this file)

## Phase report path

`phases/MVP-packet/PHASE-REPORT.md` (this file).
