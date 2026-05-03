"""Real REST client for the Runpod-hosted GPU layer endpoints (Wave C).

This module is the **only** place in the codebase that issues real HTTP
requests against a remote Runpod deployment.  It is wrapped by
:class:`zer0pa_materials_workbench.runpod.dispatcher.RunpodDispatcher` which decides
when a real call is permitted (credentials present + ``MATERIALS_MODE`` is
``runpod_rest``).  The client does not synthesise envelopes, does not
fall back to the mock backend, and does not silently swallow non-2xx
responses.

Background
----------
Wave 5c shipped ``runpod_mock`` envelopes but no live REST client.  Any code
path emitting an envelope with ``tool_adapter.backend == "runpod_rest"`` was
in fact relabelling a mock — the deception flagged in the Wave 5c review.
Wave C closes that hole by providing this module plus the dispatcher.

Behaviour summary
-----------------
* Bearer auth via ``Authorization: Bearer <api_token>``.
* :mod:`tenacity` retry envelope: ``stop_after_attempt(3)`` and
  ``wait_exponential(min=1, max=10)``.  Idempotent ``healthz`` and
  ``call`` POSTs are retried; ``RunpodCredentialsError`` is NOT retried
  because the operator must intervene.
* Per-request timeout via ``httpx.Timeout`` (default 60s, configurable).
* Non-2xx after retries raises :class:`RunpodRestError` carrying the
  status code and (truncated) response body for forensic logging.
* Empty / missing ``base_url`` or ``api_token`` raises
  :class:`RunpodCredentialsError` at construction time so the dispatcher
  can convert the failure into a :class:`BlockedSourceManifest`.

Boundary (verbatim)
-------------------
Research infrastructure for in silico materials science discovery.
Outputs are research artifacts. No regulatory certification claims.
No clinical or human-subject use. ITAR / weapons applications are
out of scope (Meta UMA Acceptable Use Policy and operator policy).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Final, Literal

import httpx

# tenacity is in the [runpod] extra; without it, retries are disabled and a
# clear error tells the operator to install the extra. Importing lazily here
# means a `pip install -e ".[dev]"` install still imports this module
# successfully — only invoking the real REST client without [runpod]
# installed raises. The previous eager import broke test collection.
try:
    from tenacity import (
        RetryError,
        retry,
        retry_if_exception_type,
        stop_after_attempt,
        wait_exponential,
    )
    _TENACITY_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised in [dev]-only installs
    _TENACITY_AVAILABLE = False

    class RetryError(Exception):  # type: ignore[no-redef]
        """Stand-in surfaced when tenacity is not installed.

        The real ``tenacity.RetryError`` is raised when a retry envelope
        exhausts.  In [dev]-only installs we cannot retry; if a caller
        reaches this point it means the production REST path was invoked
        without the [runpod] extra installed, which is a configuration
        error to surface, not silently mask.
        """

    def retry(*args: Any, **kwargs: Any) -> Callable[[Callable[..., Any]], Callable[..., Any]]:  # type: ignore[no-redef]
        """No-op decorator surfaced when tenacity is not installed.

        Returns the function unchanged; calls into the REST client without
        retries.  Production deployments MUST install ``[runpod]`` so the
        real retry envelope is active — see ``RunpodRestClient.__init__``.
        """
        def deco(fn: Callable[..., Any]) -> Callable[..., Any]:
            return fn
        return deco

    def retry_if_exception_type(*args: Any, **kwargs: Any) -> None:  # type: ignore[no-redef]
        return None

    def stop_after_attempt(*args: Any, **kwargs: Any) -> None:  # type: ignore[no-redef]
        return None

    def wait_exponential(*args: Any, **kwargs: Any) -> None:  # type: ignore[no-redef]
        return None


from zer0pa_materials_workbench.boundary import RESEARCH_BOUNDARY

__all__ = [
    "DEFAULT_TIMEOUT_S",
    "RETRY_MAX_ATTEMPTS",
    "RETRY_WAIT_MAX_S",
    "RETRY_WAIT_MIN_S",
    "Layer",
    "RunpodCredentialsError",
    "RunpodRestClient",
    "RunpodRestError",
]


# Layers that have GPU-bound endpoints behind the runpod REST surface.  Aligned
# with :data:`zer0pa_materials_workbench.runpod.mock_backends.RUNPOD_MOCK_LAYERS`.
Layer = Literal[
    "L1",
    "L2",
    "ionic",
    "L1.5",
    "L3",
    "L4",
    "L5",
    "L6",
    "quantum",
    "L7",
]

# Configuration constants — exposed at module scope so tests can monkey-patch.
DEFAULT_TIMEOUT_S: Final[float] = 60.0
RETRY_MAX_ATTEMPTS: Final[int] = 3
RETRY_WAIT_MIN_S: Final[float] = 1.0
RETRY_WAIT_MAX_S: Final[float] = 10.0


class RunpodCredentialsError(RuntimeError):
    """Raised when ``base_url`` or ``api_token`` is missing/empty.

    The dispatcher converts this into a
    :class:`zer0pa_materials_workbench.audit.BlockedSourceManifest`.  This is the
    "honest block" pattern — we do NOT fall back to the mock and label it
    ``runpod_rest``; we surface the missing-credentials condition so the
    operator can see exactly what is wrong.
    """

    def __init__(self, missing: list[str]) -> None:
        self.missing = list(missing)
        super().__init__(
            "Runpod REST credentials missing: "
            f"{', '.join(missing) or '<unspecified>'}.  Set RUNPOD_BASE_URL and "
            "RUNPOD_API_TOKEN before invoking the runpod_rest backend."
        )


class RunpodRestError(RuntimeError):
    """Raised after the retry envelope exhausts on a non-2xx response."""

    def __init__(
        self,
        *,
        status_code: int,
        url: str,
        body_preview: str,
        attempts: int,
    ) -> None:
        self.status_code = status_code
        self.url = url
        self.body_preview = body_preview
        self.attempts = attempts
        super().__init__(
            f"Runpod REST call to {url!r} failed after {attempts} attempts "
            f"(HTTP {status_code}); body preview: {body_preview!r}"
        )


class RunpodRestClient:
    """Real REST client for the Runpod GPU endpoints.

    All POST requests are emitted as ``{base_url}/v1/{layer}/{endpoint}``.
    Construction fails fast when credentials are absent so the calling
    dispatcher cannot accidentally instantiate a "live" client without a
    backing token.
    """

    def __init__(
        self,
        base_url: str | None,
        api_token: str | None,
        *,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        missing: list[str] = []
        if not base_url:
            missing.append("RUNPOD_BASE_URL")
        if not api_token:
            missing.append("RUNPOD_API_TOKEN")
        if missing:
            raise RunpodCredentialsError(missing)

        # Strip any trailing slash so the path concatenation below remains
        # idempotent regardless of how the operator wrote ``RUNPOD_BASE_URL``.
        self.base_url: str = (base_url or "").rstrip("/")
        self.api_token: str = api_token or ""
        self.timeout_s: float = float(timeout_s)
        self.research_boundary: str = RESEARCH_BOUNDARY

        # ``transport`` exists for tests — ``httpx.MockTransport`` is the
        # canonical injection point.  Production code passes ``None`` and
        # gets the default sync transport (real network).
        self._transport = transport

        if not _TENACITY_AVAILABLE:
            # Honest surface: tell the operator the [runpod] extra is required.
            # Construction still succeeds so unit tests exercising the schema
            # of a "configured" client (without actually calling) still work.
            import warnings
            warnings.warn(
                "tenacity is not installed; Runpod REST retries are disabled. "
                "Install with: pip install -e '.[runpod]' before invoking "
                "RunpodRestClient.call() in production.",
                RuntimeWarning,
                stacklevel=2,
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def call(
        self,
        layer: Layer,
        endpoint: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """POST ``payload`` to ``{base_url}/v1/{layer}/{endpoint}``.

        Retries on ``httpx.HTTPError`` (transport errors and 5xx surfaced
        as ``HTTPStatusError``) up to :data:`RETRY_MAX_ATTEMPTS` times with
        exponential backoff.  4xx responses are retried as well because the
        Runpod gateway sometimes returns 429 for transient capacity
        pressure; if the final attempt is non-2xx, a
        :class:`RunpodRestError` is raised carrying the status and body
        preview.

        Returns the parsed JSON body as a dict.
        """
        url = self._url_for(layer, endpoint)
        try:
            return self._post_with_retry(url=url, payload=payload)
        except RetryError as exc:  # pragma: no cover — translated below
            last = exc.last_attempt.exception()
            raise RunpodRestError(
                status_code=getattr(last, "status_code", 0) or 0,
                url=url,
                body_preview=str(last)[:200],
                attempts=RETRY_MAX_ATTEMPTS,
            ) from exc

    def healthz(self, layer: Layer) -> bool:
        """Return True if ``{base_url}/v1/{layer}/healthz`` responds 2xx.

        Used by :meth:`zer0pa_materials_workbench.runpod.cutover.RunpodCutover.precheck`
        — if no creds are configured this method returns False rather than
        raising (the precheck records the absence as evidence).  Actual
        transport errors against a configured host are surfaced as False
        (not as a raise) so the precheck can continue and report all
        evidence at once.
        """
        url = self._url_for(layer, "healthz")
        try:
            with self._client() as client:
                resp = client.get(url, headers=self._headers())
            return 200 <= resp.status_code < 300
        except httpx.HTTPError:
            return False

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _url_for(self, layer: str, endpoint: str) -> str:
        endpoint_clean = endpoint.lstrip("/")
        return f"{self.base_url}/v1/{layer}/{endpoint_clean}"

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            # Tag every outgoing request so server logs can correlate to
            # the Zer0pa Materials Workbench boundary.  Servers that don't recognise
            # the header simply ignore it.
            "X-Zer0pa-Boundary": "research-only",
        }

    def _client(self) -> httpx.Client:
        kwargs: dict[str, Any] = {
            "timeout": httpx.Timeout(self.timeout_s),
            "follow_redirects": False,
        }
        if self._transport is not None:
            kwargs["transport"] = self._transport
        return httpx.Client(**kwargs)

    def _post_with_retry(self, *, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        # We use a closure-bound retrier so each call gets its own attempt
        # count.  The retrier explicitly DOES NOT retry on
        # RunpodCredentialsError (we never reach this code path with bad
        # creds anyway because construction fails) or on RunpodRestError
        # raised from within the closure — those are terminal.
        attempts_used: dict[str, int] = {"count": 0}

        @retry(
            stop=stop_after_attempt(RETRY_MAX_ATTEMPTS),
            wait=wait_exponential(
                multiplier=1.0,
                min=RETRY_WAIT_MIN_S,
                max=RETRY_WAIT_MAX_S,
            ),
            retry=retry_if_exception_type(httpx.HTTPError),
            reraise=True,
        )
        def _do() -> dict[str, Any]:
            attempts_used["count"] += 1
            with self._client() as client:
                resp = client.post(url, headers=self._headers(), json=payload)
            if 200 <= resp.status_code < 300:
                return resp.json()
            # Convert any non-2xx into an httpx.HTTPStatusError so tenacity
            # retries within the configured envelope.  On the final
            # attempt the helper below converts it to RunpodRestError.
            raise httpx.HTTPStatusError(
                f"Runpod REST returned {resp.status_code}",
                request=resp.request,
                response=resp,
            )

        try:
            return _do()
        except httpx.HTTPStatusError as exc:
            raise RunpodRestError(
                status_code=exc.response.status_code,
                url=url,
                body_preview=exc.response.text[:200],
                attempts=attempts_used["count"],
            ) from exc
        except httpx.HTTPError as exc:
            # Transport-level error after retries (timeouts, connection
            # resets).  We surface a RunpodRestError with status_code=0 to
            # signal "we never got a response body".
            raise RunpodRestError(
                status_code=0,
                url=url,
                body_preview=str(exc)[:200],
                attempts=attempts_used["count"],
            ) from exc
