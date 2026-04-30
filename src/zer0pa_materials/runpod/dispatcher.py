"""Runpod backend dispatcher (Wave C — central honest-block routing).

Adapter code that wishes to honour ``MATERIALS_MODE=runpod_rest`` MUST
route through :class:`RunpodDispatcher`.  The dispatcher reads the
:class:`~zer0pa_materials.envelope.config.MaterialsConfig` and decides
which physical backend serves a given layer/endpoint:

* ``runpod_rest``   → :class:`~zer0pa_materials.runpod.rest_client.RunpodRestClient`
                      (real HTTP), provided credentials are present.
* ``runpod_mock``   → :func:`~zer0pa_materials.runpod.mock_backends.build_runpod_mock_envelope`
                      (synthetic, deterministic).
* anything else (``local_stub``/``local_cpu``/etc.) → returns ``None``
                      so the calling adapter falls through to its own
                      local code.

Honest-block contract
---------------------
The Wave 5c review caught a deception: code paths produced envelopes
labelled ``backend = "runpod_rest"`` even when no real REST call was
made — they were silently relabelled mocks.  This module exists to make
that impossible:

1.  When the layer's ``*_BACKEND`` is ``runpod_rest`` AND credentials are
    valid, the dispatcher hits the REST endpoint and returns the real
    response.  The caller wraps it into an envelope with
    ``tool_adapter.backend = "runpod_rest"``.
2.  When the layer's ``*_BACKEND`` is ``runpod_rest`` AND credentials are
    MISSING, the dispatcher RAISES :class:`RunpodCredentialsError` AND
    appends a :class:`~zer0pa_materials.audit.BlockedSourceManifest` to
    the audit log.  It does NOT silently fall back to the mock; it does
    NOT return a mock-shaped dict labelled ``runpod_rest``.

Tests in ``tests/parity/test_runpod_dispatcher.py`` enforce both the
success path and the missing-credentials failure path adversarially.

Boundary (verbatim)
-------------------
Research infrastructure for in silico materials science discovery.
Outputs are research artifacts. No regulatory certification claims.
No clinical or human-subject use. ITAR / weapons applications are
out of scope (Meta UMA Acceptable Use Policy and operator policy).
"""

from __future__ import annotations

import datetime as _dt
import uuid
from dataclasses import dataclass
from typing import Any, Final, Iterable

from zer0pa_materials.audit.sources import BlockedSourceManifest
from zer0pa_materials.boundary import RESEARCH_BOUNDARY
from zer0pa_materials.envelope.config import MaterialsConfig
from zer0pa_materials.runpod.mock_backends import (
    RUNPOD_MOCK_LAYERS,
    build_runpod_mock_envelope,
)
from zer0pa_materials.runpod.rest_client import (
    RunpodCredentialsError,
    RunpodRestClient,
    RunpodRestError,
)

__all__ = [
    "RunpodDispatcher",
    "DispatchResult",
    "DispatchMode",
    # Re-export so callers do not need to import from rest_client directly.
    "RunpodCredentialsError",
    "RunpodRestError",
    "LAYER_BACKEND_FLAG_MAP",
]


# Flag-name on :class:`MaterialsConfig` for each layer's backend selector.
# A few layers expose more than one knob; the dispatcher picks the
# *most specific* one for the layer.  When a layer is not present in
# this map we fall back to ``MATERIALS_MODE``.
LAYER_BACKEND_FLAG_MAP: Final[dict[str, str]] = {
    "L1": "MATERIALS_L1_BACKEND",
    "L2": "L2_BACKEND",
    "ionic": "IONIC_TRANSPORT_BACKEND",
    "L1.5": "L15_FORCE_BACKEND",
    "L3": "L3_CALPHAD_PROVIDER",
    "L4": "L4_SOLVER",
    "L5": "L5_EXECUTION_MODE",
    "L6": "L6_GENERATOR_BACKEND",
    "quantum": "MATERIALS_L1_BACKEND",  # quantum runs alongside L1 backends.
    "L7": "L7_ORCHESTRATOR_BACKEND",
}


DispatchMode = str  # alias — values: "runpod_rest", "runpod_mock", or "local"


@dataclass(frozen=True)
class DispatchResult:
    """Returned envelope payload + which backend produced it."""

    backend: str
    payload: dict[str, Any]


class RunpodDispatcher:
    """Central dispatch helper for adapters.

    Construct once per pipeline run (or per adapter instance) and call
    :meth:`dispatch` from the adapter's predict/run/submit_job code BEFORE
    falling through to the local stub.

    Args:
        config: Loaded :class:`MaterialsConfig`.  If None, ``MaterialsConfig()``
            is constructed (which reads ``.env``).
        rest_client_factory: Callable that returns a
            :class:`RunpodRestClient`.  Tests inject a fake here.  The
            default uses ``cfg.RUNPOD_BASE_URL`` and ``cfg.RUNPOD_API_TOKEN``.
        on_blocked: Optional callback ``(BlockedSourceManifest) -> None``.
            Tests use it to capture blocked manifests without configuring
            a full :class:`AuditLog`.  If None, manifests are stashed on the
            instance and reachable via :meth:`blocked_manifests`.
    """

    def __init__(
        self,
        config: MaterialsConfig | None = None,
        *,
        rest_client_factory: Any | None = None,
        on_blocked: Any | None = None,
    ) -> None:
        self.config = config or MaterialsConfig()
        self._rest_client_factory = rest_client_factory or self._default_factory
        self._on_blocked = on_blocked
        self._blocked_manifests: list[BlockedSourceManifest] = []
        self.research_boundary: str = RESEARCH_BOUNDARY

    # ------------------------------------------------------------------
    # Mode resolution
    # ------------------------------------------------------------------

    def backend_for_layer(self, layer: str) -> str:
        """Return the configured backend value for *layer*.

        Reads the per-layer ``*_BACKEND`` flag and falls back to
        ``MATERIALS_MODE`` when no per-layer flag exists.  The returned
        value is the literal recorded in :class:`MaterialsConfig` (e.g.
        ``"runpod_rest"``, ``"runpod_mock"``, ``"local_cpu"``).
        """
        flag_name = LAYER_BACKEND_FLAG_MAP.get(layer)
        if flag_name and hasattr(self.config, flag_name):
            value = getattr(self.config, flag_name)
            if value:
                return str(value)
        # Default to the global mode.
        return str(getattr(self.config, "MATERIALS_MODE", "local_cpu"))

    def is_rest_active(self, layer: str) -> bool:
        """True if this layer should hit the live REST endpoint.

        Used by adapter dispatch hooks: if False, the adapter runs its
        local stub.  If True, the adapter calls :meth:`dispatch`.
        """
        return self.backend_for_layer(layer) == "runpod_rest"

    def is_mock_active(self, layer: str) -> bool:
        """True if this layer should use the deterministic mock backend."""
        return self.backend_for_layer(layer) == "runpod_mock"

    def credentials_ok(self) -> tuple[bool, list[str]]:
        """Return ``(ok, missing)`` for ``RUNPOD_BASE_URL`` + ``RUNPOD_API_TOKEN``.

        The precheck consumes this directly so the operator sees a
        single, machine-readable list of which env vars need to be set.
        """
        missing: list[str] = []
        if not getattr(self.config, "RUNPOD_BASE_URL", None):
            missing.append("RUNPOD_BASE_URL")
        if not getattr(self.config, "RUNPOD_API_TOKEN", None):
            missing.append("RUNPOD_API_TOKEN")
        return (not missing, missing)

    def blocked_manifests(self) -> list[BlockedSourceManifest]:
        """Return a copy of all blocked manifests accumulated by this dispatcher."""
        return list(self._blocked_manifests)

    # ------------------------------------------------------------------
    # Core dispatch
    # ------------------------------------------------------------------

    def dispatch(
        self,
        layer: str,
        endpoint: str,
        payload: dict[str, Any],
        *,
        mock_output: dict[str, Any] | None = None,
    ) -> DispatchResult | None:
        """Route a layer call to the configured backend.

        Returns:
            :class:`DispatchResult` carrying ``backend`` and the raw
            ``payload`` (for ``runpod_rest``: the JSON body returned by
            the server; for ``runpod_mock``: the dict from
            :func:`build_runpod_mock_envelope`).  Returns ``None`` when
            the configured backend is something the dispatcher does NOT
            handle — namely ``local_stub`` / ``local_cpu`` / ``stub``
            and friends.  The caller falls through to its local code.

        Raises:
            RunpodCredentialsError: when the configured backend is
                ``runpod_rest`` but credentials are missing.  A
                :class:`BlockedSourceManifest` is also recorded so
                downstream auditing has a structured entry.
            RunpodRestError: when the live REST call fails after the
                retry envelope.

        The keyword arg ``mock_output`` is forwarded to
        :func:`build_runpod_mock_envelope` — the caller may pass a
        layer-specific output dict for richer mock parity.
        """
        backend = self.backend_for_layer(layer)

        if backend == "runpod_rest":
            ok, missing = self.credentials_ok()
            if not ok:
                manifest = self._record_blocked(
                    layer=layer,
                    endpoint=endpoint,
                    missing=missing,
                )
                # Honest block: raise so the adapter cannot pretend the
                # call succeeded.  The dispatcher already recorded the
                # blocked manifest so the operator sees a structured
                # diagnostic in the audit log.
                raise RunpodCredentialsError(missing) from _BlockedManifestSentinel(manifest)
            client = self._rest_client_factory()
            response = client.call(layer=layer, endpoint=endpoint, payload=payload)
            return DispatchResult(backend="runpod_rest", payload=response)

        if backend == "runpod_mock":
            if layer not in RUNPOD_MOCK_LAYERS:
                # Layer is configured for runpod_mock but the mock factory
                # has no layer-specific build path.  We still route — the
                # caller is expected to know which layers are valid.  We
                # surface this as a ValueError below by passing through to
                # the factory which raises the appropriate error.
                pass
            envelope_dict = build_runpod_mock_envelope(
                layer=layer,
                input_payload=payload,
                output_payload=mock_output,
            )
            return DispatchResult(backend="runpod_mock", payload=envelope_dict)

        # Anything else — local_stub, local_cpu, stub, mock, etc.
        # Caller falls through to their local adapter implementation.
        return None

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _default_factory(self) -> RunpodRestClient:
        return RunpodRestClient(
            base_url=getattr(self.config, "RUNPOD_BASE_URL", None),
            api_token=getattr(self.config, "RUNPOD_API_TOKEN", None),
        )

    def _record_blocked(
        self,
        *,
        layer: str,
        endpoint: str,
        missing: Iterable[str],
    ) -> BlockedSourceManifest:
        manifest = BlockedSourceManifest(
            source_manifest_id=f"src:runpod:{layer}/{endpoint}:{uuid.uuid4().hex[:12]}",
            attempted_locator=f"runpod://{layer}/{endpoint}",
            blocker_reason="unavailable_credentials",
            blocker_detail=(
                f"runpod_rest dispatch for layer={layer!r} endpoint={endpoint!r} "
                f"blocked: missing {sorted(missing)}.  Dispatcher refused to "
                "fall back to runpod_mock to avoid mislabelling output."
            ),
            retry_strategy=(
                "Set RUNPOD_BASE_URL and RUNPOD_API_TOKEN in the pod environment "
                "or .env, then re-run the layer.  See docs/RUNPOD-CUTOVER.md."
            ),
            blocked_at=_dt.datetime.now(_dt.timezone.utc).isoformat(timespec="microseconds"),
        )
        self._blocked_manifests.append(manifest)
        if self._on_blocked is not None:
            self._on_blocked(manifest)
        return manifest


class _BlockedManifestSentinel(Exception):
    """Internal sentinel chaining the BlockedSourceManifest to the raise.

    The exception is *not* part of the public API — callers should catch
    :class:`RunpodCredentialsError` and fish the manifest out of
    :meth:`RunpodDispatcher.blocked_manifests`.  This sentinel exists only
    so ``raise X from Y`` carries the manifest for forensic logging.
    """

    def __init__(self, manifest: BlockedSourceManifest) -> None:
        self.manifest = manifest
        super().__init__(
            f"Blocked manifest {manifest.source_manifest_id!r} recorded; "
            "see RunpodDispatcher.blocked_manifests()."
        )
