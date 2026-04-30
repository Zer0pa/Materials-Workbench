# Phase A2-fixtures — Wave 2b Report

## Boundary (verbatim, per PRD §Boundary)

Research infrastructure for in silico materials science discovery. Outputs are research artifacts. No regulatory certification claims. No clinical or human-subject use. ITAR / weapons applications are out of scope (Meta UMA Acceptable Use Policy and operator policy).

## Scope delivered

Wave 2b authored the tiny, well-structured fixture set every layer subagent will rely on for unit tests, contract conformance, plug-swap tests, and the falsification wave. All four fixture categories shipped with manifests and tests.

| Category | Count | Path |
|---|---|---|
| Positive structures | 11 | `fixtures/structures/` |
| Negatives (one per falsifier target) | 13 | `fixtures/negatives/` |
| Phase 0 extractions | 3 | `fixtures/extractions/` |
| TDBs (toy CALPHAD) | 2 | `fixtures/tdb/` |

**Total committed fixture footprint: 73,459 bytes (7.35% of the 1 MB budget).**

## Files created

### Positive structure fixtures (`fixtures/structures/`)

Each fixture has its own subdirectory with `structure.cif` and `manifest.json`:

| Path | n_atoms | structure_hash | Layers used |
|---|---|---|---|
| `H2/` | 2 | `4df34f15…` | L1, quantum |
| `LiH/` | 2 | `951be753…` | L1, quantum |
| `Si/` | 2 | `6ed1b2a0…` | L1, L1.5, L2 |
| `NaCl/` | 2 | `1b074e3a…` | L1, L1.5, ionic |
| `LLZO/cubic/` | 24 | `d45cb2bf…` | L1, L1.5, ionic, L2 |
| `LLZO/tetragonal/` | 24 | `3fa3bab4…` | L1, L1.5, ionic, L2 |
| `Li6PS5Cl/` | 13 | `8d7b2175…` | L1, L1.5, ionic, L2 |
| `Li-Mg-Zr-Cl-seed/` | 10 | `ea01c76f…` | L6, L1, L1.5, ionic, L2, L7 |
| `Bi2Te3/` | 5 | `cfee960f…` | L1, L1.5 |
| `PbTe/` | 2 | `5bcfe45e…` | L1, L1.5 |
| `SnSe/` | 8 | `6cb5daa5…` | L1, L1.5 |

Both LLZO phases shipped (cubic + tetragonal) — the size budget allowed it (24 atoms × 2 ≈ 4.5 KB combined CIF). The cubic-vs-tetragonal contrast is the canonical "known-good control" in PRD §Scope.

LLZO and Li6PS5Cl fixtures are **REDUCED** (single formula unit on the canonical lattice metric) — the real 192-atom cell would explode the budget and is not needed at A2. Manifests state this explicitly and direct downstream adapters to the full cell from Materials Project when materials-extras is installed.

### Negative fixtures (`fixtures/negatives/`)

Each negative fixture maps 1:1 to a falsifier target named in PRD §Falsification wave:

| Directory | Falsifier target | Trigger mechanism |
|---|---|---|
| `invalid_cif/` | `invalid_cif` | parse_minimal_cif raises ValueError |
| `duplicate_candidate/` | `duplicate_candidate` | structure_hash equals LLZO cubic hash |
| `missing_boundary/` | `missing_boundary` | research_boundary not verbatim |
| `ungrounded_property/` | `ungrounded_property` | grounding=null fails Phase0Output validation |
| `unstable_phonon/` | `unstable_phonon` | imaginary_mode_max_THz = 1.42 > 0.25 |
| `unreadable_tdb/` | `unreadable_tdb` | broken.tdb fails syntactic-shape parser |
| `high_disagreement/` | `high_disagreement` | energy_disagreement = 95 meV/atom > 75 hard-reject |
| `non_spd_tensor/` | `non_spd_tensor` | 3x3 matrix has negative smallest eigenvalue |
| `tdb_quarantine_breach/` | `tdb_quarantine_breach` | provider=ThermoCalc + redistributable=true |
| `alabos_executable_in_recipe_only/` | `alabos_executable_in_recipe_only` | mode=recipe_only + hardware_executable=true |
| `runpod_schema_drift/` | `runpod_schema_drift` | extra schema-illegal field rejected by Envelope |
| `tenant_only_tuple_leak/` | `tenant_only_tuple_leak` | tenant_only tuple inside shared_learning bundle |
| `ionic_overclaim_no_service/` | `ionic_overclaim_no_service` | conductivity > 1e-3 + null IonicTransportService ref |

Each negative is enforced single-target by `tests/unit/fixtures/conftest.detect_falsifier`, which the test asserts returns `[target]` exactly (not a superset, not empty).

### Phase 0 extraction fixtures (`fixtures/extractions/`)

Each fixture is a `Phase0Output`-shaped JSON with three or more grounded properties:

| Path | Properties | DOI count |
|---|---|---|
| `LLZO/` | RT conductivity, activation energy, lattice parameter | 2 |
| `Li6PS5Cl/` | RT conductivity, activation energy, oxidative stability | 2 |
| `Li-Mg-Zr-Cl-seed/` | RT conductivity, activation energy, lattice parameter | 3 |

DOIs are real and resolvable. Page numbers / table / figure references are plausible primary-source guesses; manifests carry `verified=false` until lead-agent live citation verification.

### TDB fixtures (`fixtures/tdb/`)

| Path | Phases | Elements | License |
|---|---|---|---|
| `Cu-Mg-toy.tdb` | LIQUID, FCC_A1, HCP_A3 | Cu, Mg | synthetic / internal |
| `Li-halide-toy.tdb` | LIQUID, LICL_RS | Li, Cl | synthetic / internal |

Both files are syntactically valid CALPHAD TDBs that pass the parser-only syntactic-shape test. `pycalphad` is not currently installed in the venv, so the full pycalphad parse test is **skipped** rather than parked — when pycalphad is added under `materials-extras`, the test runs automatically (see `test_tdb_parses_in_pycalphad`). Manifests carry `novelty_status: synthetic_known`.

## Tests delivered

`tests/unit/fixtures/`:

| Test file | Collected | Pass | Skip | Fail |
|---|---|---|---|---|
| `test_structure_hashes.py` | 35 | 35 | 0 | 0 |
| `test_negative_targets.py` | 28 | 28 | 0 | 0 |
| `test_manifests.py` | 206 | 206 | 0 | 0 |
| `test_phase0_extractions.py` | 11 | 11 | 0 | 0 |
| `test_tdb_parses.py` | 6 | 4 | 2 | 0 |
| **Total A2 tests** | **286** | **284** | **2** | **0** |

Plus the conftest module that holds the shared falsifier-detection stub, manifest iteration helpers, the budget constant, and the parser-only TDB syntactic-shape parser.

Combined with A0 (157 tests) and A1 (149 tests): **590 unit tests pass, 0 fail, 2 skip (pycalphad).**

```text
$ .venv/bin/python -m pytest tests/unit/fixtures -v
======================== 284 passed, 2 skipped in 2.09s ========================

$ .venv/bin/python -m pytest tests/unit -v
======================== 590 passed, 2 skipped in 4.39s ========================
```

## Manifest schema (delivered)

Every manifest shipped with the keys mandated by the brief plus a couple of audit-friendly defaults:

```jsonc
{
  "research_boundary": "<verbatim>",
  "fixture_id": "fixture:<name>:<sha-prefix>",
  "name": "<descriptive name>",
  "kind": "structure|extraction|tdb|negative",
  "purpose": "<one-line>",
  "sources": [{ "type": "...", "locator": "...", "license": "..." }],
  "expected_use_layers": ["L1", "L1.5", ...],
  "structure_hash": "sha256:..." | null,
  "size_bytes": <int>,
  "novelty_status": "pending|known|synthetic_known|deliberate_violation",
  "negative_falsifier_target": null | "<name>",
  "verified": false,
  "notes": "<short>"
}
```

`tests/unit/fixtures/test_manifests.py` schema-validates every manifest, asserts the boundary is verbatim, asserts size_bytes == actual file size (per fixture, indirectly via the budget rollup), confirms fixture_id uniqueness, requires non-empty `sources`, and refuses suspicious bulk-data extensions (.h5, .npz, .tar.gz, etc.) anywhere under `fixtures/`.

## Defensible calls (PRD ambiguity → resolution)

| # | Ambiguity | Resolution | Rationale |
|---|---|---|---|
| 1 | LLZO conventional cell is 192 atoms; A2 says "tiny fixtures only". | REDUCED 24-atom cells for both cubic and tetragonal phases at the real lattice parameter. | Preserves the cubic-vs-tetragonal contrast (PRD §Scope known-good control) at minimal atom count. Real 192-atom cell loaded by downstream adapters from MP. |
| 2 | Li6PS5Cl has S/Cl partial occupancy disorder (the source of the "borderline" PRD §Scope classification). | Ordered 13-atom representation. | SOD-disordered supercell is a downstream Phase 0 / L1 task (materials-extras + spglib + pymatgen). Fixture is for stoichiometry/wiring only. |
| 3 | Li-Mg-Zr-Cl-seed exact stoichiometry (Li2.2Mg0.1Zr0.9Cl6) cannot be expressed in a 10-atom cell. | Reduced-stoichiometry seed Li2 Mg1 Zr1 Cl6 with `novelty_status: pending`. | The seed is the *starting point* for the L6 SQS expansion; it is NOT a novelty claim. PRD §Scope explicitly classifies this composition as a pre-registered challenge seed, not a novelty result. |
| 4 | LLZO/tetragonal vs LLZO/cubic — brief permits picking one. | Shipped both. | Size budget is 73 KB committed (7% of 1 MB cap); the cubic↔tetragonal contrast is itself the science fixture. |
| 5 | DOIs for Phase 0 extractions need verification. | Used real DOIs that resolve; marked `verified=false` everywhere. | The brief explicitly authorises "plausible primary-source citations" in early waves with `verified=false`; lead agent is on the hook for live licence-checking. |
| 6 | pycalphad not installed; brief says "if pycalphad is not installed, document the test as parked_pending_pycalphad_install". | Implemented the full pycalphad parse test guarded by `pytest.mark.skipif`, plus a parser-only syntactic-shape test that ALWAYS runs. | Skip via importlib.util.find_spec is the standard pytest idiom; the test will fire automatically once pycalphad is installed. The shape parser is the load-bearing check today — and it does correctly reject the deliberately broken `unreadable_tdb` fixture. |
| 7 | What goes in `Cu-Mg-toy.tdb`? Brief says "well-known sublattice phase set; values can be small/synthetic". | LIQUID + FCC_A1 + HCP_A3 (canonical Cu-Mg phase set) with synthetic Redlich-Kister parameters. | Standard Cu-Mg description is well-documented; synthesising the phase set is bullet-proof, synthesising fitted L parameters is not. The TDB parses syntactically; numerical values are illustrative. |
| 8 | Negative fixtures must trigger ONLY their named target, "enforceable in the test". | Built `detect_falsifier(fixture_dir) -> list[str]` in conftest, asserted `==[target]` per fixture. | The test is the contract. Adding a negative that triggers two targets fails the test. |
| 9 | What CIF schema does the LLZO/Li6PS5Cl/Li-Mg-Zr-Cl seed use given the minimal-CIF parser only handles P1 + cell params + one loop_? | Always wrote P1 cells (declared `_symmetry_space_group_name_H-M 'P 1'`) so the A0 parser accepts them; documented the real space group in the manifest notes. | A0 parser is the contract today; downstream pymatgen/ASE adapters in materials-extras will handle real symmetry groups. |
| 10 | Should `fixture_id` use the full sha256 or a prefix? | 8-character prefix (`sha-prefix`). | Brief says "sha-prefix"; full hash duplicates structure_hash field. The prefix is short enough to be human-eyeballable in an audit trail. |

## What downstream waves can now assume

1. `from tests.unit.fixtures.conftest import FIXTURES_ROOT, RESEARCH_BOUNDARY, iter_manifests, detect_falsifier` — all share the same fixture root.
2. Every positive structure fixture parses via `parse_minimal_cif` and the recomputed `structure_hash` matches the value committed in the manifest. Tests asserting these are committed.
3. Every negative fixture has a `negative_falsifier_target` matching its directory name and a machine-checkable trigger that the falsification wave's stub can replicate.
4. Every Phase 0 extraction validates as a `Phase0Output`, has DOI grounding, and produces three passing falsifier rows (`phase0.grounding_required`, `phase0.units_normalised`, `phase0.contradictions_resolved`).
5. Both TDBs pass the parser-only syntactic shape check; the broken TDB negative fixture is rejected by it.
6. Total fixture footprint is 73,459 bytes (well under the 1 MB cap). The budget test in `test_manifests.py::test_total_footprint_under_budget` keeps later waves honest.

## Things that need lead-agent deep research

The following items are explicitly marked `verified=false` and need lead-agent verification before promotion:

1. **Phase 0 extraction DOIs and page references** — DOIs resolve, but page numbers / table / figure citations are operator-confirmed plausible only. Lead agent should cross-check each value against the cited paper. Affected fixtures: `fixtures/extractions/{LLZO,Li6PS5Cl,Li-Mg-Zr-Cl-seed}/`.
2. **Material licence verification** — Bi2Te3 ZT review citation `10.1088/2515-7639/acc550` (J. Phys. Mater. 2023) was the most recent open-access TE roadmap I had at hand; lead agent should confirm the cited primary source and substitute the canonical Bi2Te3 ZT paper if there's a more authoritative one.
3. **LLZO MP entry ID confirmation** — `mp-942733` (cubic) and `mp-942790` (tetragonal) are the entries I cited; lead agent should verify via `https://materials.project.org/materials/mp-942733` and re-cite if the canonical ID has shifted.
4. **Li-Mg-Zr-Cl seed family DOIs** — the three halide-electrolyte DOIs are real and seminal in the field, but the *specific* numeric values cited in the seed extraction (1.5e-3 S/cm, 0.27 eV) are family-level proxies (Li3InCl6 / Li3YCl6), not measurements of the exact Li2.2Mg0.1Zr0.9Cl6 composition (which has no published characterisation — that's why it is a "pre-registered novel-challenge seed").
5. **TDB licence freedom** — synthesised toy TDBs are internal/synthetic. If lead agent decides to swap to a real fitted Cu-Mg TDB later, must verify SGTE-or-equivalent-open licence terms before commit (PRD §L3 quarantine policy).

## Verification summary

```text
$ .venv/bin/python -m pytest tests/unit/fixtures -v
======================== 284 passed, 2 skipped in 2.09s ========================

$ .venv/bin/python -m pytest tests/unit -v
======================== 590 passed, 2 skipped in 4.39s ========================

$ python -c "from tests.unit.fixtures.conftest import total_committed_bytes, BUDGET_BYTES; \
             total = total_committed_bytes(); \
             print(f'fixture footprint: {total}/{BUDGET_BYTES} bytes ({100*total/BUDGET_BYTES:.2f}%)')"
fixture footprint: 73459/1000000 bytes (7.35%)

$ ls fixtures/structures/
H2/  LiH/  Si/  NaCl/  LLZO/  Li6PS5Cl/  Li-Mg-Zr-Cl-seed/  Bi2Te3/  PbTe/  SnSe/

$ ls fixtures/negatives/
alabos_executable_in_recipe_only/  duplicate_candidate/  high_disagreement/
invalid_cif/  ionic_overclaim_no_service/  missing_boundary/  non_spd_tensor/
runpod_schema_drift/  tdb_quarantine_breach/  tenant_only_tuple_leak/
ungrounded_property/  unreadable_tdb/  unstable_phonon/

$ ls fixtures/extractions/
LLZO/  Li-Mg-Zr-Cl-seed/  Li6PS5Cl/

$ ls fixtures/tdb/
Cu-Mg-toy.tdb            Li-halide-toy.tdb
Cu-Mg-toy.manifest.json  Li-halide-toy.manifest.json
```

## Open questions for orchestrator

None blocking Wave 3 / downstream layer waves. All A2 acceptance gates pass.
