# A0-contracts — implementation notes and ambiguity resolutions

## Boundary (verbatim, per PRD §Boundary)

Research infrastructure for in silico materials science discovery. Outputs are research artifacts. No regulatory certification claims. No clinical or human-subject use. ITAR / weapons applications are out of scope (Meta UMA Acceptable Use Policy and operator policy).

## Defensible calls (PRD ambiguity → resolution)

| # | PRD ambiguity | Resolution | Rationale |
|---|---|---|---|
| 1 | Envelope `layer` literal does not include `quantum` (lists only `L1`, `L1.5`, `ionic`, ...). | `quantum` registered as a registry key for `L1QuantumVqeOutput`; envelope literal kept verbatim. Orchestrator MUST set `layer="L1"` when emitting VQE results. | PRD literal is load-bearing; the quantum slot is described as part of L1 in the layer-contracts table. |
| 2 | PRD says "URN-like" without specifying allowed character set. | Per-class regex `^<prefix>:[A-Za-z0-9._\-:/]+$`. | Permits namespace separators (`run:overnight/2026-04-30/A0`) without escaping; matches OPTIMADE-ish URN style. |
| 3 | Hash canonicalisation: PRD says sha256 but does not name a canonicalisation algorithm. | orjson `OPT_SORT_KEYS` (RFC 8785-ish). NaN/inf coerced to canonical strings to avoid hash collisions across machines. | Orjson is faster than stdlib json and doesn't suffer from Python's float repr drift. |
| 4 | "Stable structure hashing" — PRD does not specify tolerance. | 1e-5 fractional coord tolerance, 1e-5 lattice tolerance; both overridable via parameter. | Tighter than typical fixture noise; conservative relative to DFT-relaxed positions. |
| 5 | Niggli reduction expected by some interpretations of "stable structure hashing". | Pure-Python length-sort canonicalisation; spglib-based primitive-cell normalisation deferred to downstream layers (with optional spglib import). | spglib is not a hard dep at A0 (`pyproject.toml` puts it under `materials-extras`); the sort-based canonicalisation already gives translation / site-permutation / lattice-row-permutation invariance. |
| 6 | `cm**-1 ↔ THz` is a dimensional conversion (1/length vs 1/time). | Required pint `spectroscopy` context; not auto-bridged. | Auto-bridging would silently mask wrong conversions in non-spectroscopic contexts. |
| 7 | `L4_COMPUTE_URL` shown in `.env.example` as `http://localhost:8044`. | Typed as `str`. | URLs change per environment; not a backend selector. |
| 8 | PRD §Audit Trail And KG lists JSONL files but doesn't specify per-line format. | One JSON object per line, `\n`-terminated, written via orjson `OPT_SORT_KEYS`. | Standard JSONL convention; deterministic for hash-chain integrity. |
| 9 | "Phase 0 grounding" — PRD says DOI/page/table/figure. | DOI required (`min_length=1`); page is `int >= 1`; table and figure are free-form strings; all three of page/table/figure are optional individually. | Some sources cite a figure only (no page); rigid combination would over-reject. |
| 10 | `confidence.score` numeric domain. | `[0, 1]` enforced via `ge=0`, `le=1`. | Implicit Bayesian-probability convention from the PRD's audit/disagreement language. |
| 11 | What `meV/atom` means as a pint unit. | Defined `atom` as a counting dimension `[_atom_count]` so `meV/atom` has a clean dimension. | Without this, pint treats "atom" as undefined and parse_quantity rejects "5 meV/atom". |

## Known implementation limitations

1. **No spglib-based Niggli reduction.** The structure hash is invariant under translation, site permutation, and lattice-row permutation but does NOT canonicalise to the crystallographic primitive cell. Downstream L1/L1.5 layers may need to install spglib (under `materials-extras`) and supply a primitive-cell view to `structure_hash` if they need that level of canonicalisation.
2. **Minimal CIF parser only.** Supports cubic / orthorhombic / triclinic with one `loop_` and the `_atom_site_type_symbol` / `_atom_site_fract_*` columns. Production CIFs with symmetry operators, partial occupancies, or anisotropic displacement parameters require pymatgen/ASE/gemmi (downstream `materials-extras`).
3. **Boundary detector substring-based.** Forbidden phrase fragments are matched as case-insensitive substrings, with explicit allow-list overrides for terms like `"in silico"` and `"therapeutic candidate"`. Adversarial inputs (e.g., zero-width separators) would slip past; this is consistent with the PRD's intent (operator-policy gate, not a hostile-adversary defence).
4. **`degC` is non-multiplicative.** pint flags arithmetic on offset units. The canonical-units table includes `temperature_celsius` for documentation, but conversion from `degC` to `K` requires `UREG.Quantity(value, "degC").to("K")` (NOT bare arithmetic).
5. **CLI `run-falsification-wave` is a placeholder.** Wired to a stub message until Wave 9 ships the real falsifier package.

## Test coverage notes

* `test_envelope.py` covers round-trip, validator catches missing/truncated boundary, validator catches malformed hashes, validator catches malformed URN IDs, every layer/backend literal accepted, canonical_bytes determinism, falsifier integration, back-edge round trip, disagreement metric round trip, sealed extra-fields rejection.
* `test_layer_outputs.py` covers every layer-output class (smoke instantiation, falsifier-item generation, threshold pass/fail/blocked semantics, schema-level rejections like missing DOI / non-distinct L2 model names / bad URN format).
* `test_units.py` covers parse, conversion, dimensional-mismatch raising, every entry in `CANONICAL_UNITS` is parseable, round-trips through canonical units, spectroscopy context for cm⁻¹ ↔ THz.
* `test_hashing.py` covers all four invariance properties (translation, fractional translation by 1, site reorder, lattice-row permutation), one positive sub-tolerance perturbation case, one negative perturbation case, species sensitivity, mismatched species/coords rejection, minimal CIF parsing of NaCl, CIF round trip via structure_hash, CIF malformed inputs (no atoms, no cell), uncertainty-digit handling.
* `test_config.py` covers default load, .env.example load, invalid literal rejection, cutover gate (no-op when local; blocked by stubs; UMA + Runpod credential gates), runtime paths.
* `test_artifacts.py` covers manifest round trip, JSONL append+iter, bad-id / bad-hash / naive-timestamp rejections, missing-file iter empty.

## Subsequent-wave consumption checklist

When Wave 2 spawns, downstream subagents should:

1. `from zer0pa_materials_workbench_workbench.envelope import Envelope, ToolAdapter, AuditBlock, RightsBlock` — never construct envelope dicts by hand.
2. Import the layer-specific output class for their layer (e.g., L2 imports `L2MlipOutput`).
3. Import `MaterialsConfig` for any backend-flag dispatch.
4. Import `sha256_of`, `structure_hash`, `cif_hash_from_text` from `zer0pa_materials_workbench.envelope` for hashing.
5. Convert tool-native units to canonical units via `to_canonical(value, target_unit)` before emitting envelope output.
6. Validate JSON-shape outputs against `runtime/schemas/<layer>.output.v1.schema.json` in contract tests.
