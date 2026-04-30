# Phase A1-audit-kg-ontology — Wave 2a Report

## Boundary (verbatim, per PRD §Boundary)

Research infrastructure for in silico materials science discovery. Outputs are research artifacts. No regulatory certification claims. No clinical or human-subject use. ITAR / weapons applications are out of scope (Meta UMA Acceptable Use Policy and operator policy).

## Scope delivered

A1 is the audit-and-knowledge-graph foundation: every layer subagent and the falsification wave depends on the components built here. The PRD §CPU-First Build Sequence step 2 lists the deliverables: append-only audit hash chain, EMMO-aligned KG, source manifests, rights claims, decision log, episodic memory. All ten items in the work plan shipped.

## Files created

### Source modules (`src/zer0pa_materials/`)

| Path | Purpose | Lines |
|---|---|---|
| `audit/log.py` | Append-only JSONL hash-chained audit log family (11 categories) | 525 |
| `audit/sources.py` | `SourceManifest` + `BlockedSourceManifest` (PRD §Deep Research Policy) | 173 |
| `audit/rights.py` | `RightsClaim`, `assert_rights_for`, `RIGHTS_TABLE` (PRD §Data Sovereignty) | 332 |
| `audit/kg.py` | SQLite-backed property graph with 28 node types, 25 edge types | 574 |
| `audit/rdf_export.py` | Turtle / PROV-O export via `rdflib` | 199 |
| `audit/ro_crate.py` | RO-Crate 1.1 manifest writer | 130 |
| `audit/decisions.py` | `Decision` model + supersession-chain reconstructor | 145 |
| `audit/episodic.py` | `snapshot_state` + `reconstruct_from_repo` (brain-functionality gate) | 302 |
| `audit/__init__.py` | Public surface re-exports | 135 |
| `ontology/emmo.py` | EMMO term subset + 28-node + 25-edge ontology mappings | 573 |
| `ontology/__init__.py` | Public surface re-exports | 39 |
| `reasoner/tuples.py` | `ReasonerTuple` + `enforce_reuse_scope_export` | 209 |
| `reasoner/__init__.py` | Public surface re-exports | 19 |
| `cli/main.py` | Extended with `audit add-source`, `add-blocked-source`, `validate-chain`, `reconstruct` | +120 LOC |

**Total new/changed source LOC: ~3,475.**

### Test modules (`tests/unit/`)

| Path | Tests |
|---|---|
| `audit/test_audit_log.py` | 25 — append, head_hash, all 11 categories, all four tampering modes (tamper, reorder, insert, delete), threading concurrency, malformed JSON, naive timestamp rejection |
| `audit/test_sources.py` | 13 — `SourceManifest` + `BlockedSourceManifest` round-trip, missing fields rejected, bad ID/timestamp/hash rejected, integration with `AuditLog` |
| `audit/test_rights.py` | 22 — table coverage, `is_reuse_scope_compatible` matrix, `assert_rights_for` four-violation parametric, tenant-only-tuple-cannot-promote |
| `audit/test_kg.py` | 14 — all 28 node types insertable, all 25 edge types insertable, non-canonical types rejected, indexes exist, resume capture/reload, reopen idempotent |
| `ontology/test_emmo.py` | 22 — namespaces, OPTIMADE v1.3, every node/edge type maps to an IRI, valid URIs, PROV-O bindings, SPDX bindings, immutability |
| `audit/test_rdf_export.py` | 8 — empty/seeded export, PROV-O Activity/Entity/Agent triples, Turtle round-trip preserves node count, edge count, properties |
| `audit/test_decisions.py` | 14 — model round-trip, validation, supersession chain reconstruction (3-step, singleton, orphan reference), audit-log integration |
| `audit/test_reasoner_tuples.py` | 18 — model, default scope, `is_reasoner_tuple_exportable`, `enforce_reuse_scope_export` (the falsification gate), filtered exports, audit-log integration |
| `audit/test_episodic.py` | 13 — snapshot of empty state / events / falsifiers / decisions / KG counts; `reconstruct_from_repo` surfaces open falsifiers, pending decisions, chain corruption; gate test that no chat history is needed |

**Total: 149 unit tests, 149 passing, 0 failing, 0 skipped.**

Plus the existing 157 A0 tests still pass — full unit suite is 588 passed (the 2 pre-existing fixture-related failures are in `tests/unit/fixtures/` from Wave 2's A2 package and are out of A1 scope).

## Five most architecturally consequential decisions

1. **Hash-chain construction binds (chain head, timestamp, payload).** Each row's `event_hash` is `sha256(canonical_json({"_chain": prev_hash, "_recorded_at": recorded_at, "_payload": payload}))`. Binding the timestamp is what makes a *swap of two rows with identical payloads but different timestamps* still detectable — without it, two rows with the same payload would have the same event_hash and could be silently reordered. This is documented in `audit/log.py::_compute_event_hash_v2`. All four PRD-mandated tampering modes (tamper, reorder, insert, delete) are detected; all four have dedicated tests.

2. **SQLite property graph + RDF/Turtle export, NOT RDF-native.** PRD §Open Questions For Overnight Executor #2 leaves the choice to the executor. RDF-native (e.g., GraphDB, Stardust, Apache Jena) would have:
   - Required a heavy dependency (Java for Jena, or rdflib's slow in-memory store with no real SPARQL planner).
   - Slowed the CPU-side acceptance gate.
   - Added a moving part the falsifier wave does not need.

   SQLite gives O(1) indexed lookups for `(src_id, edge_type)` and `(dst_id, edge_type)`, fits in a single file, has zero dependency tax, and round-trips through Turtle for ontology consumers. The export uses PROV-O Entity/Activity/Agent triples per PRD §Audit Trail And KG; the round-trip test verifies node and edge counts match SQLite ↔ Turtle.

3. **Property dict is JSON-serialized in a single column rather than EAV.** The KG schema has `properties_json TEXT` per node and per edge. The alternative (entity-attribute-value rows) would have:
   - Quadrupled the table count (node, edge, node_property, edge_property).
   - Required JOINs on every property read.
   - Added a class of constraint ("which key/value types are allowed?") that the property graph metaphor explicitly does not constrain.

   The single-column approach is the standard property-graph idiom (Neo4j, JanusGraph, AWS Neptune all do this). Searching by property is OUT of A1 scope; downstream waves (e.g., L7 acquisition) can either build a derived index or run a JSON path query.

4. **Rights enforcement is a pure function, no contextual state.** `assert_rights_for(envelope_rights, rights_claim)` operates only on its two arguments. There is no "current contract mode" registry. This means:
   - The function is testable in isolation (proven by 22 tests covering the four cardinal contract-mode × data-class violations).
   - The falsification wave can construct a `RightsClaim` and an envelope dict in-line and trigger the gate without any setup ceremony.
   - Cross-cutting policy changes (e.g., a customer flips from `strict_sovereign` to `shared_advantage` mid-campaign) are explicit: they require writing a new `RightsClaim` row, not mutating a shared module.

5. **Episodic memory uses the audit chain as ground truth, not a derived cache.** `reconstruct_from_repo(repo_root)` reads JSONL files directly via `AuditLog.iter_rows`, walks the rows, and computes the snapshot in O(N) on demand. There is no `kg_resume.last_event_hash` index that the snapshot trusts; the snapshot is *the* current state, not a checkpoint. The `kg_resume` table exists for downstream waves (e.g., L7 incremental campaign restoration) but is OFF the brain-functionality critical path. This is what makes "a fresh agent can reconstruct from repo artifacts without chat history" actually true: there is no metadata-out-of-band layer to corrupt or get out of sync.

## What downstream waves can rely on

1. **`AuditLog` — eleven categories, hash-chained, atomic-append.** Every layer subagent imports `from zer0pa_materials.audit import AuditLog` and writes via `log.append_event(category, payload)`. Concurrent writers serialise on a per-file `fcntl` lock; the chain holds under threading (proven).

2. **`SourceManifest` / `BlockedSourceManifest`.** Every strategic lookup (Phase 0 literature mining, model card retrieval, license verification, OPTIMADE database queries) emits one of these into `sources.jsonl`. Blocked stubs do NOT silently fail — they record a structured manifest with `blocker_reason` + `retry_strategy`.

3. **`RightsClaim` + `assert_rights_for`.** Wave 7 (L7 orchestration) calls `assert_rights_for` before promoting any candidate. The falsification wave's "private tuple reuse outside `reuse_scope`" gate is exactly `enforce_reuse_scope_export`. The rights table is canonical and tested.

4. **`MaterialsKG` — 28 node types, 25 edge types, all enum-typed.** Adapters that emit envelopes also emit one or more KG nodes (typically `CandidateMaterial`, `SimulationJob`, `SimulationResult`, `Artifact`) and the relevant `MAPS_TO_ONTOLOGY` edges. Non-canonical types raise `KGTypeError` immediately, not at export time.

5. **`export_kg_to_turtle` + `round_trip_validate`.** Wave 5 (MVP packet) calls `export_kg_to_turtle(kg, packet_dir / "kg.ttl")` and then `round_trip_validate` to confirm the export is intact. The reproducibility-package builder uses this to ship a Turtle artifact alongside the SQLite.

6. **`Decision` + `reconstruct_supersession_chain`.** Every architectural decision (e.g., "L4 default solver = stub", "Quaternary halide seed family = Li-Mg-Zr-Cl") is written as a `Decision` row in `decisions.jsonl`. `reconstruct_supersession_chain(decisions, decision_id)` reads the chain from any starting point and returns the [oldest..newest] timeline.

7. **`ReasonerTuple` + `enforce_reuse_scope_export`.** L7 emits one `ReasonerTuple` per candidate evaluation. Default `reuse_scope = "tenant_only"`; the gate fires when a tenant-only tuple is requested for a wider-scope corpus.

8. **`reconstruct_from_repo(repo_root)` — the brain-functionality entry.** A fresh agent on a new shell calls `reconstruct_from_repo(repo_root())` (using the central `zer0pa_materials.repo_root.repo_root()` helper, NOT a hardcoded absolute path) and gets a `CampaignState` with `next_actions` derived from the audit chains. Chain integrity errors come first; then open falsifiers; then pending decisions; then holding tuples; then "all clean — proceed".

9. **CLI surface stable.** Subagents and the orchestrator can run:
   - `zer0pa-materials audit add-source ...`
   - `zer0pa-materials audit add-blocked-source ...`
   - `zer0pa-materials audit validate-chain <category>`
   - `zer0pa-materials audit reconstruct [repo_root]`

10. **EMMO term subset embedded; no network fetch needed.** `ontology/emmo.py` carries the canonical EMMO IRIs for the ten classes the PRD lists (Material, Composition, Phase, Property, Process, Model, Simulation, Measurement, Reasoning, Provenance). The mapping from KG node type to EMMO IRI is in `KG_NODE_TO_EMMO`. Every node type has at least one ontology IRI.

## Divergence from PRD spec

1. **PRD names "27 node types" in the prompt, but the verbatim PRD §Audit Trail And KG list contains 28 entries** (Campaign through OntologyTerm — count is 28, not 27). I implemented all 28; both `KGNodeType` and `KG_NODE_TO_EMMO` have 28 entries. This is a count fix, not a semantic change.

2. **Episodic memory's `_resolve_audit_paths` deliberately ignores cwd-based config.** A naive `MaterialsConfig()` reads from the calling shell's cwd `.env`, which can leak the executor's environment into a fresh agent's reconstruction. We instead resolve `.env` only against `repo_root`, falling back to repo-root-relative defaults if no `.env` exists. This is a strict reading of the brain-functionality gate ("no chat history" → also "no caller env").

3. **`_compute_event_hash_v2` name reserved for future migration.** The name carries `_v2` to signal the chain construction is versioned; if a future wave changes the binding shape (e.g., adds a session salt), the hash function gets a `_v3` and the chain validator checks both. There is no v1 in this codebase.

4. **`EMMO_TERMS` IRIs are placeholders against the live EMMO 1.x release.** The UUIDs I encoded match the EMMO 1.x stable IRI conventions but I did NOT cross-check every UUID against the live repository — that would have required a network fetch and a `BlockedSourceManifest`. Downstream waves that integrate live EMMO can patch the IRIs with no change to the API. Note documented in `ontology/emmo.py` module docstring.

## Open questions for the lead agent

1. **Live EMMO IRI verification** — the PRD §Audit Trail And KG says EMMO-aligned. The IRIs I encoded in `ontology/emmo.py::EMMO_TERMS` use the EMMO 1.x convention but were not cross-checked against the live ontology (offline build, no `WebFetch`). Should the orchestrator emit a `BlockedSourceManifest` for "EMMO IRI verification" and have the deep-research subagent reconcile?

2. **OPTIMADE v1.3 schema fetch policy** — `OPTIMADE_VERSION = "1.3"` is hardcoded. PRD §Audit Trail And KG says "OPTIMADE v1.3-first, v1.2-compatible". Should the live OPTIMADE v1.3 JSON Schema be downloaded (with a SourceManifest) and validated against during a future wave, or is the static IRI mapping sufficient for the CPU-side acceptance gate?

3. **RO-Crate population** — A1 ships the manifest writer (`write_ro_crate_metadata`); Wave 5 (MVP packet) populates the entries. Does the lead agent want a default entry list (audit JSONLs + KG SQLite + Turtle export + source manifests) wired up here so Wave 5 only adds the campaign-specific artifacts, or should Wave 5 own the full entry list?

4. **Rights claim audit integration** — Currently a `RightsClaim` lives in code; to write one to the audit ledger, callers do `log.append_event("rights", rc.model_dump(mode="json"))`. Should we add a thin `audit_rights_claim(log, rc)` helper that also auto-creates a corresponding `KGNode` of type `RightsClaim`? That feels like an L7 concern, not A1; deferring unless lead disagrees.

## Verification summary

```text
$ .venv/bin/python -m pytest tests/unit/audit tests/unit/ontology -v
============================= 149 passed in 2.78s ==============================

$ .venv/bin/python -m pytest tests/unit -q
============= 588 passed, 2 failed, 2 skipped in 5.48s ============
# (the 2 failed + 2 skipped are in tests/unit/fixtures/, A2 wave, out of A1 scope)

$ .venv/bin/zer0pa-materials --help
# Shows: version, envelope-schema, check-config, run-falsification-wave, audit
$ .venv/bin/zer0pa-materials audit --help
# Shows: add-source, add-blocked-source, validate-chain, reconstruct

$ .venv/bin/zer0pa-materials audit add-source \
    --source-manifest-id "src:doi:10.1038/s41586-020-2649-2" \
    --source-type paper --locator "10.1038/s41586-020-2649-2" \
    --license-spdx "CC-BY-4.0" --summary "MatBench reference paper" \
    --decision-impact "L2 disagreement threshold" \
    --audit-dir /tmp/a1-cli-smoke
appended sources row event_hash=sha256:266d3ff7cb...

$ .venv/bin/zer0pa-materials audit validate-chain sources --audit-dir /tmp/a1-cli-smoke
chain OK category=sources rows=1
```

Hash-chain integrity: all four tampering modes (tamper, reorder, insert, delete) detected — see `tests/unit/audit/test_audit_log.py::test_validate_chain_detects_*` and the smoke run above. No A1 gate is open.
