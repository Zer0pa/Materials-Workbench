# A2-fixtures — implementation notes

## Boundary (verbatim, per PRD §Boundary)

Research infrastructure for in silico materials science discovery. Outputs are research artifacts. No regulatory certification claims. No clinical or human-subject use. ITAR / weapons applications are out of scope (Meta UMA Acceptable Use Policy and operator policy).

## Why each negative fixture has its own *machine-checkable* trigger

The brief insists "negative fixtures must trigger ONLY their named target" and "make this enforceable in the test, not just hopeful". The pattern we settled on:

1. Each negative subdirectory ships a single small data file (CIF / JSON / TDB) carrying just enough state to make the violation literally observable.
2. The shared `tests/unit/fixtures/conftest.detect_falsifier(fixture_dir)` function maps each directory name to its specific check and returns a list of fired target names.
3. `tests/unit/fixtures/test_negative_targets.py::test_negative_fixture_triggers_named_target` asserts `detect_falsifier(fixture_dir) == [manifest["negative_falsifier_target"]]` — exactly, no superset and no empty.

This means a future Wave 9 (real falsifier package) replaces the stub `detect_falsifier` body with the real falsifier engine without changing the test contract: the test still asserts the *list* of fired targets equals the manifest's expected target. If the real falsifier is correct, the test passes; if it is over-eager (fires extra), the test catches the leak.

## Why the LLZO / Li6PS5Cl / Li-Mg-Zr-Cl fixtures are REDUCED

The real conventional cells are 192 atoms (LLZO), 52 atoms (Li6PS5Cl), and require an SQS-disordered supercell (Li-Mg-Zr-Cl-seed). All three would blow the 1 MB fixture budget if shipped in full. Our reduction policy:

* keep the **real lattice metric** so downstream symmetry detection (when spglib / pymatgen are installed under materials-extras) can recover the canonical space group from the fixture-derived structure
* keep the **stoichiometry exact** for one formula unit
* place atoms at illustrative-but-deterministic positions (NOT the relaxed Wyckoff coordinates)
* document this verbatim in each manifest's `notes` field
* point downstream adapters at the Materials Project ID for the full relaxed cell

The CIF parser that ships with A0 only handles P1 cells with a single `loop_`. Every fixture is therefore expressed in P1 even when its real space group is e.g. Fd-3m or I41/acd. The real space group is recorded in manifest notes.

## Why the TDB tests are split into "syntactic shape" + "pycalphad parse"

`pycalphad` is not currently in the venv. The brief says "If pycalphad is not installed, document the test as `parked_pending_pycalphad_install` and write a parser-only smoke test that verifies the TDB syntactic shape." We did exactly this:

* `_tdb_syntactically_well_formed` (in conftest) is a small pure-Python check that:
  - requires at least one `!`-terminated statement after stripping `$`-comments,
  - requires every ELEMENT line to have ≥ 5 fields,
  - requires every FUNCTION block to contain a `;`,
  - requires every PHASE to be paired with CONSTITUENT + PARAMETER,
  - rejects the deliberately broken `unreadable_tdb/broken.tdb` fixture.

* The pycalphad parse test (`test_tdb_parses_in_pycalphad`) is `@pytest.mark.skipif(not PYCALPHAD_AVAILABLE)` — it skips today, runs automatically when pycalphad is installed under materials-extras, and provides the L3-grade gate the PRD demands.

The shape parser is intentionally permissive: it accepts the toy Cu-Mg and Li-halide TDBs which are real fitted-shape (LIQUID/FCC_A1/HCP_A3 + LIQUID/LICL_RS) but with synthetic numerical parameters. Its only adversary is the negative `unreadable_tdb` fixture, which it correctly rejects.

## Why we shipped both LLZO/cubic and LLZO/tetragonal

The brief said "include both cubic AND tetragonal variants under `LLZO/cubic/` and `LLZO/tetragonal/` if size budget allows; otherwise pick one and document the trade." Total size for the two LLZO fixtures was ~4.6 KB; the budget had 99% headroom; the cubic↔tetragonal **conductivity contrast** is itself the science fixture (PRD §Scope: "Recover literature behavior while distinguishing cubic high-conductivity LLZO from tetragonal low-conductivity behavior"). Trivial choice.

## DOIs marked verified=false

Every Phase 0 extraction manifest carries `verified=false`. The DOIs themselves are real and resolvable (anie.200701144 is the Murugan/Thangadurai/Weppner LLZO paper; jssc.2009.05.020 is Awaka's tetragonal LLZO; anie.200703900 is Deiseroth's argyrodite paper; etc.). What is NOT verified is the page / table / figure granularity — those require live-paper consultation by the lead agent.

The fixture-level convention: shipping `verified=false` is preferable to omitting the citation entirely or to shipping a `TODO`. Downstream contract tests treat `verified=false` as "use it for adapter wiring; do not promote a candidate that depends on this number to publication-grade until verified=true".

## Dependencies introduced

None at A2. Only stdlib + `numpy` + `orjson` (used for hash) + `pydantic` (already present, used to validate Phase0Output during the negative-fixture test for `ungrounded_property`).
