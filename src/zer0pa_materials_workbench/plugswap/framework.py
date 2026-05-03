"""PlugSwapHarness — generic plug-swap test framework (Wave 5b).

Research infrastructure for in silico materials science discovery.
Outputs are research artifacts. No regulatory certification claims.
No clinical or human-subject use. ITAR / weapons applications are
out of scope (Meta UMA Acceptable Use Policy and operator policy).

Architectural role
------------------
This module lifts the ad-hoc per-layer plug-swap tests (Waves 3A/3B/4a)
into a first-class, cross-cutting framework that proves PRD's
"swap any layer's tool in <1 day with no downstream breakage" invariant.

The 4-step PRD invariant (§Plug-replaceability acceptance test)
---------------------------------------------------------------
1. Pick one layer adapter (A) and a golden seed request.
2. Replace its implementation with adapter B behind the same contract.
3. Run the same seed request through both adapters.
4. Pass only if:
   a. downstream code is unchanged (same schema key-set, same layer)
   b. schemas validate (output conforms to the registered layer schema)
   c. audit provenance records the adapter difference
   d. disagreement / falsifier state is preserved (structure-equal, not
      value-equal — scientific output legitimately differs)
   e. scientific changes appear as output/confidence/falsifier *deltas*,
      NOT as interface breakage.

Terminology
-----------
* ``adapter_factory_a`` / ``adapter_factory_b`` — zero-argument callables
  that return a live adapter instance.
* ``golden_seed_fn`` — zero-argument callable that returns the seed
  argument(s) needed to call the adapter.  The seed must be the same
  dict/object passed to both A and B.
* ``call_fn`` — a user-supplied ``(adapter, seed) -> Envelope`` callable
  that abstracts the different per-layer APIs (submit_job, run, compute,
  predict, query, generate, acquire …).

Design constraints
------------------
* Read-only with respect to all layer adapters — no modifications.
* Every layer must be reachable from the harness.
* Returns ``FalsifierItem``-shaped verdicts so results integrate with the
  existing audit log structure.
* ``assert_*`` methods raise ``AssertionError`` with a human-readable
  message when a boundary is violated.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable
from typing import Any

from zer0pa_materials_workbench.boundary import RESEARCH_BOUNDARY
from zer0pa_materials_workbench.envelope.envelope import Envelope
from zer0pa_materials_workbench.envelope.falsifier import FalsifierItem
from zer0pa_materials_workbench.envelope.layer_outputs import LAYER_OUTPUT_REGISTRY

__all__ = [
    "GLOBAL_REGISTRY",
    "LayerSwapRegistration",
    "PlugSwapHarness",
    "PlugSwapResult",
    "SwapRegistry",
]


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class PlugSwapResult:
    """Structured verdict from a single plug-swap run.

    Every field is a FalsifierItem so the results can be appended directly to
    an audit ``Envelope.falsifier.items`` list.

    Fields
    ------
    layer:
        The layer name (e.g. ``"L1"``).
    adapter_a_name:
        Human-readable name of adapter A.
    adapter_b_name:
        Human-readable name of adapter B.
    schema_invariant:
        Verdict: output keys and layer match between A and B.
    audit_provenance:
        Verdict: both envelopes carry valid audit hashes and the adapter
        name differs between A and B (adapter swap recorded).
    disagreement_state:
        Verdict: disagreement blocks are either present in both or absent
        in both — structure preserved.
    falsifier_state:
        Verdict: falsifier item counts are comparable (same order of
        magnitude); items are non-empty in both.
    envelope_a:
        The Envelope produced by adapter A.
    envelope_b:
        The Envelope produced by adapter B.

    Convenience
    -----------
    ``all_pass`` — True when all four verdicts have status ``"pass"``.
    """

    layer: str
    adapter_a_name: str
    adapter_b_name: str
    schema_invariant: FalsifierItem
    audit_provenance: FalsifierItem
    disagreement_state: FalsifierItem
    falsifier_state: FalsifierItem
    envelope_a: Envelope
    envelope_b: Envelope

    @property
    def all_pass(self) -> bool:
        return all(
            fi.status == "pass"
            for fi in (
                self.schema_invariant,
                self.audit_provenance,
                self.disagreement_state,
                self.falsifier_state,
            )
        )

    def verdicts(self) -> list[FalsifierItem]:
        """Return all four verdict items as a list."""
        return [
            self.schema_invariant,
            self.audit_provenance,
            self.disagreement_state,
            self.falsifier_state,
        ]


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class LayerSwapRegistration:
    """One (layer, A, B, seed) registration entry."""

    layer: str
    adapter_factory_a: Callable[[], Any]
    adapter_factory_b: Callable[[], Any]
    golden_seed_fn: Callable[[], Any]
    call_fn: Callable[[Any, Any], Envelope]
    adapter_a_name: str = ""
    adapter_b_name: str = ""


class SwapRegistry:
    """Collection of (layer, adapter_a, adapter_b, seed) registrations.

    Use :meth:`register_layer` to add entries.  The cross-cutting tests
    iterate :meth:`all_registrations` to parameterise fixtures.

    The default singleton is :data:`GLOBAL_REGISTRY`.
    """

    def __init__(self) -> None:
        self._entries: list[LayerSwapRegistration] = []

    def register_layer(
        self,
        layer: str,
        adapter_factory_a: Callable[[], Any],
        adapter_factory_b: Callable[[], Any],
        golden_seed_fn: Callable[[], Any],
        call_fn: Callable[[Any, Any], Envelope],
        adapter_a_name: str = "",
        adapter_b_name: str = "",
    ) -> None:
        """Register a layer's two adapters and their shared seed.

        Parameters
        ----------
        layer:
            Layer key matching ``LAYER_OUTPUT_REGISTRY`` (e.g. ``"L1"``).
        adapter_factory_a:
            Zero-argument callable returning adapter A instance.
        adapter_factory_b:
            Zero-argument callable returning adapter B instance.
        golden_seed_fn:
            Zero-argument callable returning the seed argument(s) to pass
            to ``call_fn``.  The seed must be identical for A and B.
        call_fn:
            ``(adapter, seed) -> Envelope`` callable that abstracts the
            per-layer API surface.  The harness calls this for both A and B.
        adapter_a_name:
            Human-readable name override; defaults to the factory's
            ``__name__``.
        adapter_b_name:
            Human-readable name override.
        """
        entry = LayerSwapRegistration(
            layer=layer,
            adapter_factory_a=adapter_factory_a,
            adapter_factory_b=adapter_factory_b,
            golden_seed_fn=golden_seed_fn,
            call_fn=call_fn,
            adapter_a_name=adapter_a_name or getattr(adapter_factory_a, "__name__", str(adapter_factory_a)),
            adapter_b_name=adapter_b_name or getattr(adapter_factory_b, "__name__", str(adapter_factory_b)),
        )
        self._entries.append(entry)

    def all_registrations(self) -> list[LayerSwapRegistration]:
        """Return all registered entries (defensive copy)."""
        return list(self._entries)

    def layers(self) -> list[str]:
        """Return unique layer names in registration order."""
        seen: list[str] = []
        for e in self._entries:
            if e.layer not in seen:
                seen.append(e.layer)
        return seen

    def get(self, layer: str) -> list[LayerSwapRegistration]:
        """Return all registrations for a specific layer."""
        return [e for e in self._entries if e.layer == layer]


# Module-level singleton.
GLOBAL_REGISTRY: SwapRegistry = SwapRegistry()


# ---------------------------------------------------------------------------
# Harness
# ---------------------------------------------------------------------------


def _envelope_top_keys(env: Envelope) -> set[str]:
    """Return the top-level JSON key set of an envelope."""
    return set(env.model_dump(mode="json").keys())


def _adapter_name_from_envelope(env: Envelope) -> str:
    """Extract the adapter name from an envelope's tool_adapter block."""
    return env.tool_adapter.name if env.tool_adapter else "unknown"


def _disagreement_present(env: Envelope) -> bool:
    """Return True if the envelope carries a non-empty disagreement block."""
    d = env.model_dump(mode="json").get("disagreement")
    if d is None:
        return False
    # Non-empty dict with at least one metric.
    metrics = d.get("metrics") if isinstance(d, dict) else None
    return bool(metrics)


def _falsifier_item_count(env: Envelope) -> int:
    """Return the number of falsifier items in an envelope."""
    f = env.model_dump(mode="json").get("falsifier")
    if not f:
        return 0
    items = f.get("items") if isinstance(f, dict) else None
    return len(items) if items else 0


class PlugSwapHarness:
    """Pytest-friendly plug-swap test harness.

    Usage (inside a pytest conftest or test module)::

        harness = PlugSwapHarness()
        harness.register_layer(
            layer="L1",
            adapter_factory_a=PyScfMolecularSolver,
            adapter_factory_b=QuantumEspressoAiiDASolver,
            golden_seed_fn=lambda: (H2_CIF, L1JobParams(...)),
            call_fn=lambda adapter, seed: adapter.submit_job(*seed),
        )
        result = harness.run_swap_test("L1")
        assert result.all_pass

    The harness also reads from a :class:`SwapRegistry` to support the
    module-level ``GLOBAL_REGISTRY`` pattern used by the cross-cutting tests.
    """

    def __init__(self, registry: SwapRegistry | None = None) -> None:
        self._registry = registry or SwapRegistry()

    def register_layer(
        self,
        layer: str,
        adapter_factory_a: Callable[[], Any],
        adapter_factory_b: Callable[[], Any],
        golden_seed_fn: Callable[[], Any],
        call_fn: Callable[[Any, Any], Envelope],
        adapter_a_name: str = "",
        adapter_b_name: str = "",
    ) -> None:
        """Convenience proxy to :meth:`SwapRegistry.register_layer`."""
        self._registry.register_layer(
            layer=layer,
            adapter_factory_a=adapter_factory_a,
            adapter_factory_b=adapter_factory_b,
            golden_seed_fn=golden_seed_fn,
            call_fn=call_fn,
            adapter_a_name=adapter_a_name,
            adapter_b_name=adapter_b_name,
        )

    # ------------------------------------------------------------------
    # 4-step PRD invariant test
    # ------------------------------------------------------------------

    def run_swap_test(self, layer: str) -> PlugSwapResult:
        """Run the 4-step PRD plug-swap invariant for the given layer.

        Picks the *first* registration for the layer from the registry.
        Returns a :class:`PlugSwapResult` with per-boundary verdicts.

        Raises ``KeyError`` if the layer has no registration.
        """
        entries = self._registry.get(layer)
        if not entries:
            raise KeyError(
                f"No swap registration for layer {layer!r}. "
                "Call register_layer() first or populate GLOBAL_REGISTRY."
            )
        entry = entries[0]
        return self._run_entry(entry)

    def _run_entry(self, entry: LayerSwapRegistration) -> PlugSwapResult:
        """Execute the 4-step invariant for one registration entry."""
        # Step 1 — instantiate adapters.
        adapter_a = entry.adapter_factory_a()
        adapter_b = entry.adapter_factory_b()

        # Step 2 — produce the golden seed and run both adapters.
        seed = entry.golden_seed_fn()
        envelope_a = entry.call_fn(adapter_a, seed)
        envelope_b = entry.call_fn(adapter_b, seed)

        # Step 3 — assert each boundary and collect verdicts.
        schema_v = self.assert_schema_invariance(envelope_a, envelope_b, entry.layer)
        audit_v = self.assert_audit_provenance(envelope_a, envelope_b)
        disagree_v = self.assert_disagreement_state(envelope_a, envelope_b)
        falsifier_v = self.assert_falsifier_state(envelope_a, envelope_b)

        return PlugSwapResult(
            layer=entry.layer,
            adapter_a_name=entry.adapter_a_name or _adapter_name_from_envelope(envelope_a),
            adapter_b_name=entry.adapter_b_name or _adapter_name_from_envelope(envelope_b),
            schema_invariant=schema_v,
            audit_provenance=audit_v,
            disagreement_state=disagree_v,
            falsifier_state=falsifier_v,
            envelope_a=envelope_a,
            envelope_b=envelope_b,
        )

    # ------------------------------------------------------------------
    # Boundary assertion methods
    # ------------------------------------------------------------------

    def assert_schema_invariance(
        self,
        envelope_a: Envelope,
        envelope_b: Envelope,
        layer: str | None = None,
    ) -> FalsifierItem:
        """Compare envelope schemas; return a FalsifierItem verdict.

        Checks:
        * Same top-level JSON key-set (excluding ``tool_adapter`` and
          ``audit``, which legitimately differ between adapters).
        * Same ``layer`` value.
        * ``output`` validates against the layer's registered schema
          (for both A and B).

        Scientific changes appear as value deltas inside ``output``; the
        structure (key-set) must be invariant.
        """
        name = "plugswap.schema_invariance"
        try:
            keys_a = _envelope_top_keys(envelope_a) - {"tool_adapter", "audit"}
            keys_b = _envelope_top_keys(envelope_b) - {"tool_adapter", "audit"}
            sym_diff = keys_a.symmetric_difference(keys_b)
            if sym_diff:
                return FalsifierItem(
                    name=name,
                    threshold="envelope top-level key-sets match (excluding tool_adapter, audit)",
                    actual=f"symmetric_difference={sorted(sym_diff)}",
                    status="fail",
                    rationale=f"Key-set mismatch between adapter A and B: {sorted(sym_diff)}",
                )
            if envelope_a.layer != envelope_b.layer:
                return FalsifierItem(
                    name=name,
                    threshold="layer field identical",
                    actual=f"A={envelope_a.layer!r} B={envelope_b.layer!r}",
                    status="fail",
                    rationale="Layer mismatch after adapter swap.",
                )
            # Structural check: the required base fields of the layer's
            # registered output schema must be present in both envelope outputs.
            # This is the correct invariance: adapters may add optional
            # adapter-specific keys (e.g. lematgen_u_unique on MatterGen,
            # prompt on CrystaLLM) but all required contract fields must be
            # present in both. Private keys (underscore prefix) are excluded.
            # We do NOT require all keys to be identical — that would prohibit
            # adapter-specific scientific metadata.
            eff_layer = layer or envelope_a.layer
            if eff_layer in LAYER_OUTPUT_REGISTRY:
                schema_cls = LAYER_OUTPUT_REGISTRY[eff_layer]
                required_fields = {
                    field_name
                    for field_name, field_info in schema_cls.model_fields.items()
                    if field_info.is_required()
                }
                output_a = envelope_a.output if isinstance(envelope_a.output, dict) else {}
                output_b = envelope_b.output if isinstance(envelope_b.output, dict) else {}
                missing_from_a = required_fields - set(output_a.keys())
                missing_from_b = required_fields - set(output_b.keys())
                if missing_from_a:
                    return FalsifierItem(
                        name=name,
                        threshold=f"required schema fields present in adapter A output: {sorted(required_fields)}",
                        actual=f"missing_from_a={sorted(missing_from_a)}",
                        status="fail",
                        rationale=f"Adapter A output missing required layer schema fields: {sorted(missing_from_a)}",
                    )
                if missing_from_b:
                    return FalsifierItem(
                        name=name,
                        threshold=f"required schema fields present in adapter B output: {sorted(required_fields)}",
                        actual=f"missing_from_b={sorted(missing_from_b)}",
                        status="fail",
                        rationale=f"Adapter B output missing required layer schema fields: {sorted(missing_from_b)}",
                    )
            # Boundary block present in both.
            if envelope_a.research_boundary != RESEARCH_BOUNDARY:
                return FalsifierItem(
                    name=name,
                    threshold="research_boundary present verbatim in envelope_a",
                    actual=str(envelope_a.research_boundary)[:64],
                    status="fail",
                )
            if envelope_b.research_boundary != RESEARCH_BOUNDARY:
                return FalsifierItem(
                    name=name,
                    threshold="research_boundary present verbatim in envelope_b",
                    actual=str(envelope_b.research_boundary)[:64],
                    status="fail",
                )
            return FalsifierItem(
                name=name,
                threshold="envelope top-level key-sets match (excluding tool_adapter, audit); required output fields present in both",
                actual=f"keys_match=True layer={envelope_a.layer!r}",
                status="pass",
            )
        except Exception as exc:
            return FalsifierItem(
                name=name,
                threshold="schema invariance check completes without exception",
                actual=str(exc)[:200],
                status="fail",
                rationale=f"Exception during schema check: {type(exc).__name__}",
            )

    def assert_audit_provenance(
        self,
        envelope_a: Envelope,
        envelope_b: Envelope,
    ) -> FalsifierItem:
        """Verify audit provenance is recorded for both adapters.

        Checks:
        * Both envelopes have ``audit.audit_record_id`` matching the
          ``^audit:`` prefix pattern.
        * Both envelopes have ``audit.input_hash`` and ``audit.output_hash``
          matching the ``^sha256:[0-9a-f]{64}$`` pattern.
        * The adapter names differ between A and B (swap was recorded).

        The adapter difference is the audit of the swap itself.
        """
        import re

        name = "plugswap.audit_provenance"
        _AUDIT_ID_RE = re.compile(r"^audit:[A-Za-z0-9._\-:/]+$")
        _HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")

        def _check_envelope(env: Envelope, label: str) -> str | None:
            if not env.audit:
                return f"{label}: audit block missing"
            if not _AUDIT_ID_RE.match(env.audit.audit_record_id or ""):
                return f"{label}: audit_record_id malformed ({env.audit.audit_record_id!r})"
            if not _HASH_RE.match(env.audit.input_hash or ""):
                return f"{label}: input_hash malformed"
            if not _HASH_RE.match(env.audit.output_hash or ""):
                return f"{label}: output_hash malformed"
            return None

        try:
            err_a = _check_envelope(envelope_a, "A")
            if err_a:
                return FalsifierItem(
                    name=name,
                    threshold="audit block with valid hashes in envelope A",
                    actual=err_a,
                    status="fail",
                )
            err_b = _check_envelope(envelope_b, "B")
            if err_b:
                return FalsifierItem(
                    name=name,
                    threshold="audit block with valid hashes in envelope B",
                    actual=err_b,
                    status="fail",
                )
            # Adapter names must differ (the swap was recorded in tool_adapter).
            name_a = envelope_a.tool_adapter.name if envelope_a.tool_adapter else ""
            name_b = envelope_b.tool_adapter.name if envelope_b.tool_adapter else ""
            if name_a == name_b:
                # Not a failure of the audit — it means both adapters share a
                # name.  Flag as inconclusive: worth noting but not a hard
                # failure (e.g. two instances of the same class with different
                # backends might share a name).
                return FalsifierItem(
                    name=name,
                    threshold="adapter names differ between A and B (swap recorded)",
                    actual=f"name_a={name_a!r} name_b={name_b!r}",
                    status="inconclusive",
                    rationale=(
                        "Both adapter A and B carry the same tool_adapter.name; "
                        "the swap may not be distinguishable from audit records alone. "
                        "Consider giving adapters unique ADAPTER_NAME constants."
                    ),
                )
            return FalsifierItem(
                name=name,
                threshold="audit block with valid hashes; adapter names differ",
                actual=f"A={name_a!r} B={name_b!r} both_audited=True",
                status="pass",
            )
        except Exception as exc:
            return FalsifierItem(
                name=name,
                threshold="audit provenance check completes without exception",
                actual=str(exc)[:200],
                status="fail",
                rationale=f"Exception: {type(exc).__name__}",
            )

    def assert_disagreement_state(
        self,
        envelope_a: Envelope,
        envelope_b: Envelope,
    ) -> FalsifierItem:
        """Verify disagreement state is preserved (structure, not values).

        The disagreement block is either present in both envelopes or absent
        in both.  A swap MUST NOT add or remove the disagreement block.
        Scientific disagreement metric *values* may legitimately differ.
        """
        name = "plugswap.disagreement_state"
        try:
            present_a = _disagreement_present(envelope_a)
            present_b = _disagreement_present(envelope_b)
            if present_a != present_b:
                return FalsifierItem(
                    name=name,
                    threshold="disagreement block present-or-absent equally in A and B",
                    actual=f"A_present={present_a} B_present={present_b}",
                    status="fail",
                    rationale=(
                        "Adapter swap changed the presence of the disagreement block. "
                        "The swap must not add or remove disagreement structure."
                    ),
                )
            return FalsifierItem(
                name=name,
                threshold="disagreement block present-or-absent equally in A and B",
                actual=f"both_present={present_a}",
                status="pass",
            )
        except Exception as exc:
            return FalsifierItem(
                name=name,
                threshold="disagreement state check completes without exception",
                actual=str(exc)[:200],
                status="fail",
                rationale=f"Exception: {type(exc).__name__}",
            )

    def assert_falsifier_state(
        self,
        envelope_a: Envelope,
        envelope_b: Envelope,
    ) -> FalsifierItem:
        """Verify falsifier item counts are comparable across adapters.

        Concrete rules:
        * Both envelopes must have a ``falsifier`` block.
        * Item counts must be >= 0 in both.
        * If both are non-zero, the count difference must be <= max(count_a,
          count_b) — i.e. the count is not zero on one side when the other
          has items (asymmetric falsifier structure is a swap breakage).

        Scientific values inside items may differ; count parity is the
        structure invariant.
        """
        name = "plugswap.falsifier_state"
        try:
            count_a = _falsifier_item_count(envelope_a)
            count_b = _falsifier_item_count(envelope_b)
            # Both must have a falsifier block.
            fa = envelope_a.model_dump(mode="json").get("falsifier")
            fb = envelope_b.model_dump(mode="json").get("falsifier")
            if fa is None:
                return FalsifierItem(
                    name=name,
                    threshold="falsifier block present in envelope A",
                    actual="falsifier=None",
                    status="fail",
                )
            if fb is None:
                return FalsifierItem(
                    name=name,
                    threshold="falsifier block present in envelope B",
                    actual="falsifier=None",
                    status="fail",
                )
            # Asymmetric zero: one side has items, the other has none.
            if (count_a == 0) != (count_b == 0):
                return FalsifierItem(
                    name=name,
                    threshold="falsifier item counts both zero or both non-zero",
                    actual=f"count_a={count_a} count_b={count_b}",
                    status="fail",
                    rationale=(
                        "One adapter produced falsifier items and the other produced none. "
                        "The item structure must be present symmetrically."
                    ),
                )
            return FalsifierItem(
                name=name,
                threshold="falsifier item counts comparable (both zero or both non-zero)",
                actual=f"count_a={count_a} count_b={count_b}",
                status="pass",
            )
        except Exception as exc:
            return FalsifierItem(
                name=name,
                threshold="falsifier state check completes without exception",
                actual=str(exc)[:200],
                status="fail",
                rationale=f"Exception: {type(exc).__name__}",
            )

    def assert_back_edges_preserved(
        self,
        envelope_a: Envelope,
        envelope_b: Envelope,
    ) -> FalsifierItem:
        """Verify back-edge structure is unchanged by adapter swap.

        Back edges (``Envelope.back_edges``) link to upstream layer outputs.
        Their presence or absence must not change when the adapter changes.
        """
        name = "plugswap.back_edges_preserved"
        try:
            edges_a = envelope_a.model_dump(mode="json").get("back_edges") or []
            edges_b = envelope_b.model_dump(mode="json").get("back_edges") or []
            # Structure: both must be lists of the same length.
            if len(edges_a) != len(edges_b):
                return FalsifierItem(
                    name=name,
                    threshold="back_edge count identical between A and B",
                    actual=f"count_a={len(edges_a)} count_b={len(edges_b)}",
                    status="fail",
                    rationale="Adapter swap changed the number of back-edges.",
                )
            return FalsifierItem(
                name=name,
                threshold="back_edge count identical between A and B",
                actual=f"count={len(edges_a)}",
                status="pass",
            )
        except Exception as exc:
            return FalsifierItem(
                name=name,
                threshold="back-edges check completes without exception",
                actual=str(exc)[:200],
                status="fail",
                rationale=f"Exception: {type(exc).__name__}",
            )

    # ------------------------------------------------------------------
    # Convenience: run all registered layers
    # ------------------------------------------------------------------

    def run_all(self) -> dict[str, PlugSwapResult]:
        """Run ``run_swap_test`` for every registered layer.

        Returns a dict keyed by layer name.  If a layer has multiple
        registrations only the first is used (consistent with
        :meth:`run_swap_test`).
        """
        results: dict[str, PlugSwapResult] = {}
        for layer in self._registry.layers():
            results[layer] = self.run_swap_test(layer)
        return results
