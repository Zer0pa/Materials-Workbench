# A1-audit-kg — implementation notes and ambiguity resolutions

## Boundary (verbatim, per PRD §Boundary)

Research infrastructure for in silico materials science discovery. Outputs are research artifacts. No regulatory certification claims. No clinical or human-subject use. ITAR / weapons applications are out of scope (Meta UMA Acceptable Use Policy and operator policy).

## Defensible calls (PRD ambiguity → resolution)

| # | PRD ambiguity | Resolution | Rationale |
|---|---|---|---|
| 1 | Hash chain construction not specified beyond "sha256". | `event_hash = sha256(canonical_json({"_chain": prev_hash, "_recorded_at": recorded_at, "_payload": payload}))`. | Binding the timestamp prevents identical-payload row swaps. Using A0's `canonical_json_bytes` ensures determinism across machines. |
| 2 | "Concurrent appenders should not interleave rows." | POSIX `fcntl.flock` on a `.lock` sidecar file with 10 s timeout; Windows fallback is `O_CREAT \| O_EXCL` busy-wait. | Stdlib only, zero new dependency, proven by a multi-thread test that writes 100 rows from 4 threads and validates the chain. |
| 3 | "Atomic append" — exact semantics unspecified. | Copy-then-rename: create a temp file in the same directory, copy existing content + new line, fsync, then `os.replace`. | Crash-safe even under SIGKILL; `os.replace` is POSIX-atomic. |
| 4 | KG backend choice (PRD §Open Questions Executor #2). | SQLite property graph with RDF/Turtle export. | Avoids a heavy RDF-native dependency; SQLite plus rdflib for export is enough for the CPU-side acceptance gate. The round-trip test verifies node + edge counts match SQLite ↔ Turtle. |
| 5 | "Indexes on `(src_id, edge_type)` and `(dst_id, edge_type)`." | Created in DDL plus a `kg_node_type_idx` on node_type. | The PRD-specified indexes are present; the extra index makes per-type queries (e.g., "show all CandidateMaterial nodes") O(log n). |
| 6 | EMMO live IRI fetch was not feasible (CPU-side, no `WebFetch` in A1). | Embedded a static subset of EMMO 1.x IRIs with documented note in module docstring. | Deferred live verification to a downstream "deep research" subagent that can emit a `SourceManifest` with retrieval date. |
| 7 | OPTIMADE version pinning. | `OPTIMADE_VERSION = "1.3"` constant. | Matches PRD §Audit Trail And KG: "OPTIMADE v1.3-first, v1.2-compatible". |
| 8 | RDF property predicates for arbitrary node properties. | Map every property `k: v` to `<zer0pa:k> -> Literal(str(v))`. | The Zer0pa extension namespace is the natural sink for non-EMMO properties; values are typed (bool/int/float/string) via XSD datatypes. |
| 9 | Reuse-scope widening rules under `shared_advantage` / `open_science`. | Encoded as `_CONTRACT_MODE_WIDENINGS` table in `audit/rights.py`. | One table to read; default rules in `RIGHTS_TABLE` plus per-(class, mode) widenings. Tested across the four cardinal violations. |
| 10 | Reasoner-tuple reuse-scope export rule. | Tuple's scope must be `>=` the corpus scope. `enforce_reuse_scope_export` raises `RightsViolationError` otherwise. | Strictest interpretation of PRD §Self-Bootstrapping Reasoner: "If rights are unresolved, tuple reuse_scope is tenant_only." |
| 11 | Decision supersession algorithm. | `reconstruct_supersession_chain(decisions, starting_id)` walks backward through `supersedes` to find the oldest known ancestor, then forward through reverse-`supersedes` to the newest. Tolerates orphan references. | Lets a starting decision be any chain member; orphan references (cross-corpus supersedes pointer) don't break reconstruction. |
| 12 | "EMMO IRI for License." | Map License KG node to SPDX base IRI plus the Zer0pa extension. | EMMO does not have a License class out of the box; SPDX is the right vocabulary for license expressions. |
| 13 | Episodic memory path resolution under no `.env`. | Default to repo-root-relative `audit/runtime/` and `audit/runtime/kg.sqlite`. Use `MaterialsConfig` only when `<repo_root>/.env` exists, AND pass `_env_file=str(repo_root/.env)` so the resolution doesn't leak the caller's cwd. | Strict reading of brain-functionality gate: result depends only on `repo_root`. |

## Known implementation limitations

1. **EMMO IRIs are placeholders.** The UUIDs I embedded follow the EMMO 1.x convention but were not cross-checked against the live published ontology (no `WebFetch` in this wave). A downstream deep-research subagent should emit a `SourceManifest` for "EMMO IRI verification" and patch any divergent IRIs. The shape of the API and the mapping table will not change.

2. **No SPARQL endpoint.** The KG is queryable only via SQL (or via rdflib in-memory after Turtle export). PRD §Audit Trail And KG does not require SPARQL at A1; downstream waves that need it can mount the Turtle export in a triple store.

3. **No SHACL validation of the Turtle export.** PRD §Open Questions For User #3 mentions "RDF-native with SHACL validation" as a design choice. We chose property graph + RDF export instead. SHACL validation could be added downstream by emitting a SHACL shapes file from the KG node/edge type catalogue.

4. **Concurrent append uses `fcntl.flock` on POSIX.** The Windows fallback is a busy-wait `O_CREAT|O_EXCL` loop. The CI runs on macOS/Linux so the POSIX path is exercised; the Windows fallback is documented and tested syntactically but not under multi-process load.

5. **Validator reports all divergences after the first, but stops at the first that prevents structural parsing.** A row with malformed JSON gets skipped (with an error logged); rows that *parse* but don't chain-link get reported individually. This is intentional: a forensic dump should show the full damage, not just the first divergence.

6. **`assert_rights_for` checks scope-equals, not scope-compatible.** A claim's `reuse_scope` must equal the envelope's `reuse_scope`; we don't auto-widen. Justification: at envelope-emission time, the orchestrator already knows the customer's contract mode and can pick the right scope. Auto-widening at validation would mask a class of "envelope was constructed with the wrong scope" bug.

7. **Reasoner tuple's `output` and `ground_truth` are loosely typed `dict`.** A future Wave (probably L7) will add per-layer output schemas under `simulation_or_experiment.layer`. At A1, we accept any JSON-shape so the reasoner queue doesn't block layer-specific schema work.

8. **RO-Crate writer emits a manifest but not the actual files.** Wave 5 (MVP packet) populates the artifact entries. The manifest writer accepts a list of `RoCrateEntry` — it does NOT scan a directory or compute hashes. This is intentional: the entry list and hashes are owned by the packet generator, not the manifest writer.

## Test coverage notes

* **`test_audit_log.py`** covers: append+chain wiring, head_hash, all 11 categories writable, chain validation OK / empty file, all four PRD-mandated tampering modes (tamper, reorder, insert, delete), first-row tamper, all-divergences-reported, malformed JSON detection, category field swap detection, threading concurrency (4 × 25 rows), interrupted-write tolerance, row model rejects naive timestamps / bad hashes / extra fields.

* **`test_sources.py`** covers: `SourceManifest` round trip, missing fields rejected, bad ID/timestamp/hash rejected, `BlockedSourceManifest` round trip, default `blocked_at` is timezone-aware, integration with `AuditLog` (chain holds across mixed Source + Blocked rows).

* **`test_rights.py`** covers: rights table covers all 8 data classes, defaults match PRD, `is_reuse_scope_compatible` matrix (strict_sovereign blocks shared_learning, shared_advantage widens MLIP finetune, etc.), `assert_rights_for` four-violation parametric, tenant-only-tuple-cannot-promote-to-open-science (the falsification gate).

* **`test_kg.py`** covers: all 28 node types insertable, all 25 edge types insertable, non-canonical types rejected with `KGTypeError`, properties round-trip, default ontology IRI inferred, get_node returns None for missing, edge filters by type, indexes exist in sqlite_master, count_nodes_by_type, resume capture/reload, resume upsert overwrites, reopen existing DB.

* **`test_emmo.py`** covers: namespace constants, OPTIMADE 1.3, every node maps to ≥1 IRI, every IRI is a valid URI, `iri_for_kg_node` returns primary, every edge maps to ≥1 IRI, PROV-O edges use `prov:` IRIs, License → SPDX, OPTIMADEResource includes "1.3", Provenance subClassOf prov:Activity, EmmoTerm immutability, extra fields rejected.

* **`test_rdf_export.py`** covers: graph emission, PROV-O Activity for SimulationJob, PROV-O Entity for Artifact, PROV-O Agent for Actor, Turtle file written, round-trip node and edge counts match, properties preserved in Turtle, empty KG produces parseable Turtle.

* **`test_decisions.py`** covers: model round-trip, bad ID rejected, empty options rejected, bad supersedes ID rejected, bad made_by rejected, supersession chain reconstruction (3-step from any starting point, singleton, unknown ID raises, orphan supersedes tolerated), audit-log integration including supersession via JSONL.

* **`test_reasoner_tuples.py`** covers: model round-trip, default scope is tenant_only, bad ID rejected, bad audit_ref rejected, invalid proposed_action rejected, `is_reasoner_tuple_exportable` matrix (tenant_only / shared_learning / open_science), `enforce_reuse_scope_export` falsification gate, `filter_exportable_tuples`, audit-log integration.

* **`test_episodic.py`** covers: empty-state snapshot, snapshot after events, open falsifiers (fail/blocked), pending decisions excludes superseded, holding tuples, KG counts in snapshot, snapshot detects chain corruption, `reconstruct_from_repo` clean state, surfaces open falsifiers / pending decisions / chain integrity issues, **does NOT require chat history** (the brain-functionality gate), tolerates missing KG db.

## Subsequent-wave consumption checklist

When downstream waves spawn:

1. `from zer0pa_materials.audit import AuditLog, MaterialsKG, SourceManifest, BlockedSourceManifest, RightsClaim, assert_rights_for, Decision, ReasonerTuple` (or via `from zer0pa_materials.reasoner import ReasonerTuple`).
2. Resolve the audit dir via `MaterialsConfig.from_env().runtime_paths()["audit_dir"]`.
3. Open one shared `AuditLog` per process.
4. For every adapter call, append a `runs.jsonl` row at start, an `events.jsonl` row at completion, and the layer-specific JSONL (`disagreement`, `falsifiers`, `parameters`).
5. For every artifact emitted, append a row to `artifacts.jsonl` (use `ArtifactManifest.model_dump(mode="json")` as the payload).
6. For every decision, write a `Decision` row to `decisions.jsonl`. Use `back_edges` to point at the event_hashes that motivated it.
7. For every candidate evaluation, write a `ReasonerTuple` row. Default `reuse_scope = "tenant_only"` until the customer's contract mode is verified.
8. For every KG insert, use the canonical `KGNodeType` / `KGEdgeType` enums; non-canonical types raise immediately.
9. For every cross-customer export, run `enforce_reuse_scope_export(tup, target_scope)` first.
10. For brain-functionality recovery, call `reconstruct_from_repo(repo_root)` and read `state.next_actions`.
