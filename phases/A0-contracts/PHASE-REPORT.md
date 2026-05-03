# Phase A0-contracts — Wave 1 Report

## Boundary (verbatim, per PRD §Boundary)

Research infrastructure for in silico materials science discovery. Outputs are research artifacts. No regulatory certification claims. No clinical or human-subject use. ITAR / weapons applications are out of scope (Meta UMA Acceptable Use Policy and operator policy).

## Scope delivered

A0-contracts builds the foundational contract layer that all 9 downstream layer subagents will consume. The PRD §CPU-First Build Sequence step 1 lists the deliverables: boundary enforcement, runtime layout, schema package, artifact manifest, stable structure hashing, unit registry, config registry, universal envelope. All eight items shipped here. Tests + JSON Schema export complete.

## Files created

### Source modules (under `src/zer0pa_materials_workbench/`)

| Path | Purpose | Lines |
|---|---|---|
| `envelope/envelope.py` | Universal Layer Envelope (PRD §Architecture Invariant) | 248 |
| `envelope/layer_outputs.py` | Per-layer output schemas + registry | 555 |
| `envelope/falsifier.py` | `FalsifierItem` model | 60 |
| `envelope/units.py` | Canonical unit registry (pint wrapper) | 162 |
| `envelope/hashing.py` | Deterministic structure / JSON / CIF hashing | 286 |
| `envelope/config.py` | `MaterialsConfig` (PRD §Core Config Flags) | 245 |
| `envelope/artifacts.py` | `ArtifactManifest` model + JSONL IO | 113 |
| `envelope/__init__.py` | Public surface re-exports | 119 |
| `cli/__init__.py` | CLI entry-point shim | 4 |
| `cli/main.py` | Typer CLI (`envelope-schema`, `check-config`, `version`, `run-falsification-wave`) | 91 |

### Test modules (under `tests/unit/`)

| Path | Tests |
|---|---|
| `test_envelope.py` | 33 envelope round-trip / validation / boundary / hash format / URN-id / determinism / falsifier / disagreement / back-edge tests |
| `test_layer_outputs.py` | 35 per-layer instantiation / falsifier-item correctness / registry coverage tests (all 11 layers) |
| `test_units.py` | 47 parse / convert / round-trip / dimensionality / canonical-units coverage tests |
| `test_hashing.py` | 22 canonical-json / sha256 / structure-hash invariance + sensitivity / minimal-CIF parser tests |
| `test_config.py` | 9 config / cutover-gate / runtime-paths tests |
| `test_artifacts.py` | 7 manifest round-trip / JSONL append+iter / format-rejection tests |

**Total: 157 unit tests, 157 passing, 0 failing, 0 skipped.**

### Contract artifacts (under `runtime/schemas/`)

| File | Bytes | Purpose |
|---|---|---|
| `envelope.v1.schema.json` | 11034 | Universal envelope schema |
| `phase0.output.v1.schema.json` | 3578 | Phase 0 extraction output |
| `l1.output.v1.schema.json` | 1775 | L1 DFT output |
| `quantum.output.v1.schema.json` | 1380 | L1 quantum (VQE) output |
| `ionic.output.v1.schema.json` | 3480 | Ionic transport output |
| `l1_5.output.v1.schema.json` | 2238 | L1.5 phonon / TE output |
| `l2.output.v1.schema.json` | 1745 | L2 MLIP ensemble output |
| `l3.output.v1.schema.json` | 1974 | L3 CALPHAD output |
| `l4.output.v1.schema.json` | 1378 | L4 phase-field / kMC output |
| `l5.output.v1.schema.json` | 3019 | L5 continuum output |
| `l6.output.v1.schema.json` | 2433 | L6 generative output |
| `l7.output.v1.schema.json` | 1232 | L7 campaign output |

All 12 schemas validate cleanly against the JSON Schema Draft 2020-12 meta-schema (`jsonschema.Draft202012Validator.check_schema` — zero errors).

## Key architectural decisions

1. **Layer-output registry vs discriminated union.** Chose a registry pattern keyed by the envelope's `layer` literal. The envelope already carries a top-level `layer` discriminator; adding a redundant tagged-union discriminator inside `output` would create two sources of truth and a class of falsifier ("layer says L2 but output type says L3") that does not add scientific value at A0. The registry is `LAYER_OUTPUT_REGISTRY: dict[str, type[LayerOutputBase]]`, with the convenience function `validate_layer_output(layer, output_dict)` for boundary validation. Rationale documented in `layer_outputs.py` module docstring.

2. **Quantum slot exposed as both `L1` and `quantum` registry keys.** The envelope's `layer` literal lists `phase0|L1|L1.5|ionic|L2|L3|L4|L5|L6|L7` (no separate `quantum`). The PRD describes the quantum slot as part of L1. We registered `L1QuantumVqeOutput` under the `quantum` registry key so adapters that emit specifically VQE results can self-describe, but orchestrators MUST set `layer="L1"` on the envelope. This is documented in `LAYER_OUTPUT_REGISTRY` comment.

3. **Hashing tolerance default 1e-5.** Documented in `hashing.py`. This is conservative relative to typical DFT-relaxed positions and tighter than typical fixture noise. Downstream layers (e.g., L6 vs L1-relaxed comparison) can override via the `coord_tol` parameter.

4. **Pure-Python structure canonicalisation (no spglib dependency).** `pyproject.toml` declares spglib only under `materials-extras`; A0 must run without it. The `_canonicalise_lattice` function sorts lattice vectors by length then by lex order — sufficient for translation invariance and lattice-row permutation invariance, NOT a Niggli-reduced cell. Crystallographic primitive-cell normalisation is downstream L1/L1.5 work, not A0 hashing scope. Documented in `hashing.py` module docstring.

5. **`pint` `Ha` alias + `atom` counting unit.** pint 0.23+ already understands `eV`, `hartree`, `bohr`, `angstrom` (and `Å`), `picosecond`/`ps`, `terahertz`/`THz`, `cm**-1`, `GPa`, `S/cm`, `mS/cm`, `cm**2/s`, `W/(m*K)`. We add only:
   - `atom = [_atom_count] = atoms` so `meV/atom` has a clean dimension.
   - `@alias hartree = Ha = ha` so PySCF/PennyLane convention `Ha` parses.
   This minimises drift risk against future pint releases.

6. **Spectroscopy context required for cm⁻¹ ↔ THz.** Wavenumber is 1/length and frequency is 1/time. pint's built-in `spectroscopy` context bridges them via `c`. The materials pipeline performs this conversion inside the L1.5 phonon adapter; the unit registry exposes the canonical strings but does not auto-bridge the dimensions (would require a global context). Documented and tested.

7. **Boundary enforcement at envelope validation time.** `Envelope` runs `assert_boundary` on its dict form via a Pydantic `model_validator(mode='after')`. Pydantic wraps the underlying `BoundaryError` into a `ValidationError`; the `boundary` module's `assert_boundary` is still callable directly and raises `BoundaryError` unwrapped (covered by `test_envelope_directly_raises_boundary_error_when_called_via_dict_walker`).

8. **URN-like ID prefixes enforced via regex.** Each ID class has its own per-class regex (`run:`, `campaign:`, `candidate:`, `audit:`, `rights:`, `artifact:`). A common helper `_validate_urn` keeps the message format consistent. The pattern allows `[A-Za-z0-9._\-:/]+` after the prefix so internal namespacing (`run:overnight/2026-04-30/A0`) is supported without extra escaping.

9. **`L4_COMPUTE_URL` is a free-form string.** PRD §Core Config Flags shows `L4_COMPUTE_URL=http://localhost:8044`. Treating this as `Literal[...]` would be wrong — it's a URL the operator changes per-environment. Stays a `str` field; only backend-selection flags are `Literal`.

10. **Cutover gate strictness.** `validate_for_runpod_cutover()` is a no-op unless `MATERIALS_MODE=runpod_rest`. When in runpod mode, ANY backend at a stub or local value is a blocker; missing UMA HF credentials or `RUNPOD_BASE_URL`/`RUNPOD_API_TOKEN` are blockers. The list of blockers is returned (not raised) so downstream automation can produce a structured cutover-readiness report.

## Falsifier coverage

Every layer-output model implements `falsifier_items()` returning a list of `FalsifierItem` rows aligned with PRD §Layer-Specific Falsifiers And Gates. Coverage matrix:

| Layer | Falsifier rows produced |
|---|---|
| `phase0` | `phase0.grounding_required`, `phase0.units_normalised`, `phase0.contradictions_resolved` |
| `L1` | `l1.publication_convergence_delta` (when `publication_grade=True`), `l1.screening_convergence_delta` |
| `quantum` | `l1.h2_vqe_vs_fci` (H2 system) or `l1.lih_vqe_vs_fci` (LiH system) |
| `ionic` | `ionic.activation_barrier_target`, `ionic.activation_barrier_stretch`, `ionic.rt_conductivity_target`, `ionic.oxidative_stability` |
| `L1.5` | `l15.imaginary_mode_threshold`, `l15.mlip_vs_dft_force_rmse`, `l15.phono3py_qmesh_convergence` |
| `L2` | `l2.energy_disagreement_promote`, `l2.force_rmse_promote`, `l2.energy_disagreement_hard_reject`, `l2.force_rmse_hard_reject` |
| `L3` | `l3.fixture_boundary_drift`, `l3.phase_set_jaccard`, `l3.phase_fraction_js_divergence`, `l3.espei_diagnostics_recorded` |
| `L4` | `l4.cahn_hilliard_mass_drift`, `l4.allen_cahn_bounds_violation`, `l4.spparks_potts_energy_monotonic` |
| `L5` | `l5.tensors_spd`, `l5.analytic_heat_slab_error`, `l5.elastic_patch_residual`, `l5.fenicsx_vs_dealii`, `l5.openfoam_poiseuille_error`, `l5.cfd_mass_balance`, `l5.cfd_heat_balance` |
| `L6` | `l6.cif_valid`, `l6.charge_neutral`, `l6.minimum_distance_ok`, `l6.dedup_unique`, `l6.novelty_resolved` |
| `L7` | `l7.acquisition_default`, `l7.audit_provenance_attached`, `l7.gate_verdict` |

All falsifier names follow the convention `<layer>.<gate>` for stable cross-run grouping in the audit ledger.

## What downstream waves can now assume

1. **Envelope contract is stable and validated.** Adapters import `Envelope`, `ToolAdapter`, `AuditBlock`, `RightsBlock` from `zer0pa_materials_workbench.envelope` and emit instances. `model_validate_json` round-trips bit-stably. `canonical_bytes()` is deterministic for hashing.
2. **Layer-output registry is queryable.** `LAYER_OUTPUT_REGISTRY[layer]` returns the Pydantic class for that layer slot; `validate_layer_output(layer, dict)` validates a payload against it.
3. **`FalsifierItem` is the row primitive.** Audit writers and the falsification wave consume rows produced by `LayerOutputBase.falsifier_items()`.
4. **`MaterialsConfig` is the only env-loader.** No service or adapter needs to read `os.environ` directly. `MaterialsConfig.from_env()` is the entry. `validate_for_runpod_cutover()` is the cutover gate.
5. **`ArtifactManifest` and the JSONL append helpers are ready** for `audit/artifacts.jsonl` use.
6. **Hashing primitives are deterministic.** `sha256_of` for arbitrary JSON; `structure_hash` for crystals; `cif_hash_from_text` for tiny CIFs; `canonical_json_bytes` for the audit hash chain.
7. **`pint` registry is canonical.** `parse_quantity`, `to_canonical`, `format_canonical` from `zer0pa_materials_workbench.envelope.units`. Adapters convert their tool's native units into canonical units before emitting an envelope.
8. **CLI surface is stable.** `zer0pa-materials-workbench envelope-schema [--layer <name>]`, `check-config`, `version`, `run-falsification-wave` (placeholder until Wave 9).
9. **JSON Schema artifacts are committed.** `runtime/schemas/envelope.v1.schema.json` and `runtime/schemas/<layer>.output.v1.schema.json` (×11 layer files) — Runpod parity tests and downstream contract tests validate against these files.

## Divergence from PRD spec

None of the deviations below change wire-level semantics; they are documented for visibility:

1. **`quantum` is not a top-level `Envelope.layer` literal.** PRD JSON literal lists `phase0|L1|L1.5|ionic|L2|L3|L4|L5|L6|L7`. We respect the literal exactly — quantum results ride under `layer="L1"` with the `L1QuantumVqeOutput` schema in `output`. Registry exposes both `L1` and `quantum` keys for adapter self-description.
2. **`L4_COMPUTE_URL` typed as `str`, not `Literal[...]`.** It's a URL, not a backend selector. Documented above.
3. **Hashing falls back to a deterministic length-sort canonicalisation when spglib is absent.** Niggli reduction is not implemented. This is sufficient for translation / site-permutation / lattice-row-permutation invariance — the contract-layer guarantees we need at A0. Crystallographic primitive-cell normalisation is downstream L1/L1.5 work.
4. **Spectroscopy unit conversion (cm⁻¹ ↔ THz) requires the pint `spectroscopy` context.** Not auto-bridged in the registry. Tested separately so the L1.5 adapter knows the contract.
5. **CIF parser is minimal (pure Python, no pymatgen/ASE).** Supports only the subset needed for tiny test fixtures: cell parameters, single `loop_` with `_atom_site_type_symbol` + fractional coords. Real Phase 0 adapters in later waves will use pymatgen/ASE/gemmi when those are installed.

## Open questions for orchestrator

None blocking Wave 2. All A0 acceptance gates pass.

## Verification summary

```text
$ .venv/bin/python -m pytest tests/unit -v
============================= 157 passed in 1.13s ==============================

$ .venv/bin/zer0pa-materials-workbench version
0.1.0

$ .venv/bin/zer0pa-materials-workbench check-config
Config loaded.
  MATERIALS_MODE = local_cpu
  ALABOS_MODE    = recipe_only
  ARTIFACT_BACKEND = local_manifest
  KG_BACKEND       = sqlite_stub
No cutover blockers.

$ ls runtime/schemas/
envelope.v1.schema.json
ionic.output.v1.schema.json
l1.output.v1.schema.json
l1_5.output.v1.schema.json
l2.output.v1.schema.json
l3.output.v1.schema.json
l4.output.v1.schema.json
l5.output.v1.schema.json
l6.output.v1.schema.json
l7.output.v1.schema.json
phase0.output.v1.schema.json
quantum.output.v1.schema.json
```
