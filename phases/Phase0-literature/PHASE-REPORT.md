# Phase Phase0-literature — Wave 3A.1 Report

## Boundary (verbatim, per PRD §Boundary)

Research infrastructure for in silico materials science discovery. Outputs are research artifacts. No regulatory certification claims. No clinical or human-subject use. ITAR / weapons applications are out of scope (Meta UMA Acceptable Use Policy and operator policy).

## Scope delivered

Phase 0 (literature/knowledge mining) implements the four adapters, falsifiers, FastAPI service, Typer CLI, and full test suite specified in PRD §Phase 0. All backends are stub-mode only; the real OPTIMADE, LangGraph, robocrystallographer, and MaterialsBERT backends are parked behind `BlockedSourceManifest` gates. `novelty_status` is not applicable at Phase 0 (that gate lives at L6). All Phase 0 envelopes carry `layer="phase0"`, `research_boundary` enforced, and `confidence.score=0.0` (stub band "low").

## Files created

### Source modules (under `src/zer0pa_materials_workbench/`)

| Path | Purpose |
|---|---|
| `adapters/phase0/__init__.py` | Public re-exports |
| `adapters/phase0/base.py` | `Phase0Adapter` abstract base — envelope construction, `_make_source_manifest`, `_make_blocked_manifest` |
| `adapters/phase0/optimade.py` | `OptimadeFederatedQueryAdapter` — OPTIMADE v1.3 stub; real backend parked |
| `adapters/phase0/langgraph_extraction.py` | `LangGraphExtractionWorkflow` — reads fixture extractions from `fixtures/extractions/` |
| `adapters/phase0/robocrys.py` | `RobocrystallographerStructureNarrator` — stub narrative from `_STUB_DESCRIPTIONS` |
| `adapters/phase0/materialsbert.py` | `MaterialsBertNerAdapter` — gated; `BlockedSourceManifest` until `license_verified=True` |
| `falsifiers/phase0_falsifiers.py` | `reject_ungrounded_property`, `reject_unit_unparseable`, `reject_unresolved_contradiction`, `assert_kg_nodes_for` |
| `services/phase0_service.py` | FastAPI — `GET /v1/phase0/healthz`, `POST /v1/phase0/extract`, `POST /v1/phase0/optimade/query` |
| `cli/phase0.py` | Typer sub-app — `phase0 extract`, `phase0 query-optimade` |
| `cli/main.py` | Extended to register `phase0_app` under `phase0` prefix |

### Test modules

| Path | Tests | Scope |
|---|---|---|
| `tests/unit/adapters/phase0/test_optimade_adapter.py` | Envelope schema, stub hits, blocked manifest, source manifest fields | Unit |
| `tests/unit/adapters/phase0/test_langgraph_adapter.py` | LLZO/Li6PS5Cl/seed fixtures, extraction output schema, back-edges | Unit |
| `tests/unit/adapters/phase0/test_robocrys_adapter.py` | Stub narratives, envelope schema, source manifest type="repo" | Unit |
| `tests/unit/adapters/phase0/test_materialsbert_adapter.py` | Blocked path, license-verified path, `is_blocked()` method | Unit |
| `tests/unit/adapters/phase0/test_phase0_falsifiers.py` | All 4 falsifier functions, error types, item names | Unit |
| `tests/contract/phase0/test_phase0_service.py` | FastAPI endpoint contracts, KG write round-trip | Contract |
| `tests/plug_swap/phase0/test_phase0_plug_swap.py` | All 4 adapters satisfy common contract, envelope invariants | Plug-swap |
| `tests/falsification_wave/phase0/test_ungrounded_property.py` | `ungrounded_property` fixture triggers exactly `reject_ungrounded_property` | Falsification-wave |

**Total new Phase 0 tests: 63 (all passing).**

## Key architectural decisions

1. **`doi` field allows `None` but rejects empty string.** `Phase0PropertyGrounding.doi` is `str | None` (default `None`) with a `@field_validator` that raises `ValidationError` on `""`. This preserves the existing contract test (`test_phase0_grounding_missing_doi_rejected_at_schema`) while enabling test helpers to create "missing doi" groundings via `doi=None` without violating the model. The falsifier `reject_ungrounded_property` checks `bool(g.doi and g.doi.strip())` to detect both `None` and empty.

2. **`source_type="api"` for OPTIMADE.** The `SourceManifest` type literal is `"api"` (not `"database"`). OPTIMADE is a federated REST API, not a file-format database. Corrected from initial draft.

3. **`source_type="repo"` for robocrystallographer.** Software library accessed as a git repository is `"repo"` per the `SourceManifest` spec. Corrected from `"code_library"`.

4. **MaterialsBERT gated by default.** `MaterialsBertNerAdapter._generate` emits `BlockedSourceManifest(blocker_reason="license_unverified")` and returns an envelope with `output["entities"] = []` unless `constraints["license_verified"] == True`. The `is_blocked()` method checks `isinstance(self._last_manifest, BlockedSourceManifest)`. This ensures the license gate is not skipped by accident.

5. **`assert_kg_nodes_for` uses `KGNodeType.LiteratureSource` and `KGNodeType.PropertyObservation`.** The `MaterialsKG` enum members are PascalCase (`.LiteratureSource`, `.PropertyObservation`), not SCREAMING_SNAKE_CASE. Initial draft used `.LITERATURE_SOURCE` which would silently pass all nodes without filtering.

6. **LangGraph adapter reads from `fixtures/extractions/` at runtime.** Originally used `Path(__file__).parents[4] / "fixtures" / "extractions"`; replaced (Wave A) with the central `zer0pa_materials_workbench.repo_root.fixtures_root() / "extractions"` so the adapter works on any machine and any clone path. Fixture keys: `LLZO`, `Li6PS5Cl`, `Li-Mg-Zr-Cl-seed`.

## Falsifier summary

| Falsifier | Error type | Trigger condition |
|---|---|---|
| `reject_ungrounded_property` | `UngroundedPropertyError` | `doi` is `None`/empty or no page/table/figure |
| `reject_unit_unparseable` | `UnparseableUnitError` | `pint.UnitRegistry().parse_expression(unit)` fails |
| `reject_unresolved_contradiction` | `UnresolvedContradictionError` | >20% relative difference, `contradiction_flag=False` |
| `assert_kg_nodes_for` | `KGWriteError` | No `LiteratureSource` or `PropertyObservation` node in KG |

## Test counts by category

| Category | Passing | Failing | Skipped |
|---|---|---|---|
| Unit | 233 | 0 | 0 |
| Contract | included above | 0 | 0 |
| Plug-swap | included above | 0 | 0 |
| Falsification-wave | included above | 0 | 0 |
| **Full suite** | **1444** | **0** | **2** |

The 2 skips are pre-existing (`pycalphad not installed`), unrelated to Phase 0.
