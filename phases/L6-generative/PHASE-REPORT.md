# Phase L6-generative — Wave 3A.1 Report

## Boundary (verbatim, per PRD §Boundary)

Research infrastructure for in silico materials science discovery. Outputs are research artifacts. No regulatory certification claims. No clinical or human-subject use. ITAR / weapons applications are out of scope (Meta UMA Acceptable Use Policy and operator policy).

## Scope delivered

L6 (generative crystal structure discovery) implements four generator adapters, the LeMat-GenBench evaluator, L6 falsifiers, FastAPI service, Typer CLI, and full test suite. All real inference backends are parked behind `BlockedSourceManifest` gates. `novelty_status` is always `"pending"` at generation time — the `novelty_status_gate` falsifier enforces that `"novel"` cannot be set without L1+ionic+L2 back-edges. LeMat-GenBench S (stability) is always `None` at L6 — deferred to L1 DFT.

## Files created

### Source modules (under `src/zer0pa_materials_workbench/`)

| Path | Purpose |
|---|---|
| `adapters/l6/__init__.py` | Public re-exports |
| `adapters/l6/base.py` | `L6GeneratorAdapter` abstract base — envelope construction, `_emit_blocked_manifest`, `generate()` public method |
| `adapters/l6/mattergen.py` | `MatterGenGeneratorAdapter` — perturbed LLZO cubic candidates (±0.05–0.15 Å); real backend parked |
| `adapters/l6/diffcsp.py` | `DiffCspGeneratorAdapter` — Li6PS5Cl-derived candidates; real backend parked |
| `adapters/l6/crystallm.py` | `CrystaLlmCifGeneratorAdapter` — single Li2MgZrCl6 candidate; real backend parked |
| `adapters/l6/lematgen_eval.py` | `LeMatGenBenchEvaluatorAdapter` — S/U/N scoring; S always None; U/N counted from hash dedup |
| `falsifiers/l6_falsifiers.py` | 7 falsifier functions + 7 error classes |
| `services/l6_service.py` | FastAPI — `GET /v1/l6/healthz`, `POST /v1/l6/generate` |
| `cli/l6.py` | Typer sub-app — `l6 generate`, `l6 evaluate` |
| `cli/main.py` | Extended to register `l6_app` under `l6` prefix |

### Test modules

| Path | Tests | Scope |
|---|---|---|
| `tests/unit/adapters/l6/test_mattergen_adapter.py` | Envelope schema, structure_hash, dedup, novelty_status="pending", blocked manifest | Unit |
| `tests/unit/adapters/l6/test_diffcsp_adapter.py` | Li6PS5Cl candidates, lattice perturbations, envelope invariants | Unit |
| `tests/unit/adapters/l6/test_crystallm_adapter.py` | Li2MgZrCl6 candidate, single result, blocked manifest on wrong backend | Unit |
| `tests/unit/adapters/l6/test_lematgen_eval.py` | S/U/N scoring, unique batch, duplicate detection, reference hash match | Unit |
| `tests/unit/adapters/l6/test_l6_falsifiers.py` | All 7 falsifiers, all 7 error types, inconclusive / blocked / pass / fail paths | Unit |
| `tests/contract/l6/test_l6_service.py` | FastAPI endpoint contracts, response envelope list | Contract |
| `tests/plug_swap/l6/test_l6_plug_swap.py` | All 3 generators satisfy common contract, envelope invariants | Plug-swap |
| `tests/falsification_wave/l6/test_duplicate_candidate.py` | `duplicate_candidate` fixture triggers `structure_hash_dedupe` and `reference_expansion_dedupe` | Falsification-wave |
| `tests/falsification_wave/l6/test_invalid_cif.py` | `invalid_cif` fixture triggers exactly `valid_cif_only` | Falsification-wave |

**Total new L6 tests: 170 (all passing).**

## LeMat-GenBench S.U.N. implementation

| Metric | Implementation | Status in L6 stub |
|---|---|---|
| **S** — Stability | DFT total energy / force convergence (L1) | Always `None` — deferred |
| **U** — Uniqueness | `structure_hash_dedupe` within batch | Computed |
| **N** — Novelty | `reference_expansion_dedupe` vs MP/JARVIS/Alexandria/GNoME/OPTIMADE hashes | Computed (stub: empty ref set) |

## Key architectural decisions

1. **`structure_hash` key discipline.** `zer0pa_materials_workbench.envelope.hashing.structure_hash()` expects `lattice_vectors` and `fractional_coords` (not `lattice`/`frac_coords`). All three generator adapters and the falsifier `min_interatomic_distance` were corrected to use these canonical keys. `min_interatomic_distance` additionally accepts `lattice`/`frac_coords` as fallback aliases for test convenience.

2. **`novelty_status` never `"novel"` at generation time.** All four generators set `output["novelty_status"] = "pending"`. The `novelty_status_gate` falsifier raises `PrematureNoveltyError` if `novelty_status == "novel"` and no L1 back-edge exists on the envelope.

3. **`lematgen_s_stable` always `None`.** MatterGen and DiffCSP stubs set `"lematgen_s_stable": None` in output. This is intentional — S requires L1 DFT ground-state energy evaluation.

4. **`BlockedSourceManifest` for all real backends.** MatterGen, DiffCSP, and CrystaLLM emit `BlockedSourceManifest(blocker_reason="license_unverified")` when `L6_GENERATOR_BACKEND` requests the real backend. The stub path always activates on `"stub"` backend (the default).

5. **Fixture path from falsification-wave tests is now via `read_fixture()`.** Test files in `tests/falsification_wave/l6/` originally used `Path(__file__).parents[N]` arithmetic which depended on per-machine layout. The Wave A `repo_root` helper plus `read_fixture(...)` replaces all such arithmetic; tests no longer depend on absolute paths.

6. **`pymatgen_structure_matcher` always returns `"inconclusive"`.** The function gracefully handles both "pymatgen absent" and "pymatgen present but no reference Structure objects" cases by returning `status="inconclusive"` with `actual={"status": "parked_pending_pymatgen"}`. No external dependency is required.

## Falsifier summary

| Falsifier | Error type | Trigger condition |
|---|---|---|
| `valid_cif_only` | `InvalidCifError` | `cif_hash_from_text(cif_text)` raises or cif_text is empty |
| `charge_neutrality_check` | `ChargeNeutralityError` | Sum of known oxidation states ≠ 0 |
| `min_interatomic_distance` | `MinDistanceError` | Any pair distance < `threshold_angstrom` (default 0.7 Å) |
| `structure_hash_dedupe` | `DuplicateStructureError` | Duplicate `structure_hash` within batch |
| `reference_expansion_dedupe` | `ReferenceMatchError` | Candidate `structure_hash` in reference set |
| `pymatgen_structure_matcher` | — | Always returns `"inconclusive"` (parked) |
| `novelty_status_gate` | `PrematureNoveltyError` | `novelty_status="novel"` without L1 back-edge |

Inconclusive paths: `charge_neutrality_check` returns `"inconclusive"` when any element is not in the lookup table. `min_interatomic_distance` returns `"inconclusive"` when lattice or coords are absent.

## Test counts by category

| Category | Passing | Failing | Skipped |
|---|---|---|---|
| Phase0 + L6 target suite | 233 | 0 | 0 |
| **Full suite** | **1444** | **0** | **2** |

The 2 skips are pre-existing (`pycalphad not installed`), unrelated to L6.
