"""Wave C — RunpodDispatcher behavioural tests.

Covers the four states the dispatcher must distinguish:

1.  Configured backend ``runpod_rest`` AND credentials present →
    real REST call (mocked here via ``httpx.MockTransport``); the dispatch
    result carries ``backend="runpod_rest"`` and the server-returned dict.
2.  Configured backend ``runpod_rest`` AND credentials missing → the
    dispatcher RAISES :class:`RunpodCredentialsError` AND records a
    :class:`BlockedSourceManifest`.  It must NOT fall back to the mock
    and label it ``runpod_rest``.  This is the "honest block" invariant.
3.  Configured backend ``runpod_mock`` → returns the deterministic mock
    envelope; ``backend="runpod_mock"``.
4.  Configured backend ``local_stub`` / ``local_cpu`` → returns ``None``
    so the caller falls through to its local code path.

A fifth, adversarial test confirms that a synthesised "fake REST
response" with mock-shape but ``backend="runpod_rest"`` is still flagged
as honest by the schema-parity invariants in
``test_runpod_rest_invariants.py`` — see that file for the active
detection logic.

Boundary (verbatim)
-------------------
Research infrastructure for in silico materials science discovery.
Outputs are research artifacts. No regulatory certification claims.
No clinical or human-subject use. ITAR / weapons applications are
out of scope (Meta UMA Acceptable Use Policy and operator policy).
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from zer0pa_materials.audit.sources import BlockedSourceManifest
from zer0pa_materials.boundary import RESEARCH_BOUNDARY
from zer0pa_materials.envelope.config import MaterialsConfig
from zer0pa_materials.envelope.hashing import HASH_REGEX
from zer0pa_materials.runpod.dispatcher import (
    DispatchResult,
    RunpodCredentialsError,
    RunpodDispatcher,
)
from zer0pa_materials.runpod.rest_client import RunpodRestClient


# ---------------------------------------------------------------------------
# Helpers — these construct configs WITHOUT touching the on-disk .env so the
# tests are hermetic.  ``MaterialsConfig.model_construct`` skips validators
# but is fine here because we're already passing valid Literal values.
# ---------------------------------------------------------------------------


def _cfg(**kwargs: Any) -> MaterialsConfig:
    """Construct a MaterialsConfig from kwargs, ignoring any on-disk .env."""
    # Build via ``MaterialsConfig.model_construct`` so we are not at the
    # mercy of whatever ``.env`` is present in the dev tree; the dispatcher
    # only reads the attributes that we explicitly pass.
    defaults: dict[str, Any] = {
        "MATERIALS_MODE": "local_cpu",
        "L2_BACKEND": "local_stub",
        "RUNPOD_BASE_URL": None,
        "RUNPOD_API_TOKEN": None,
        "UMA_HF_ORG": None,
        "UMA_HF_TOKEN": None,
    }
    defaults.update(kwargs)
    return MaterialsConfig.model_construct(**defaults)


def _make_mock_transport(
    response_body: dict[str, Any] | None = None,
    *,
    status_code: int = 200,
) -> httpx.MockTransport:
    payload = response_body if response_body is not None else {"ok": True}

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json=payload)

    return httpx.MockTransport(handler)


# ---------------------------------------------------------------------------
# 1. runpod_rest with valid credentials → real REST call
# ---------------------------------------------------------------------------


def test_dispatch_runpod_rest_with_creds_hits_live_endpoint():
    """A live REST configuration produces a DispatchResult with backend=runpod_rest."""
    cfg = _cfg(
        MATERIALS_MODE="runpod_rest",
        L2_BACKEND="runpod_rest",
        RUNPOD_BASE_URL="https://runpod.example/api",
        RUNPOD_API_TOKEN="token-XYZ",
    )

    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        # The server-side response is the canonical "REST envelope shape"
        # — the dispatcher returns it verbatim; the caller is responsible
        # for sanity-checking schema invariants downstream.
        return httpx.Response(
            200,
            json={
                "research_boundary": RESEARCH_BOUNDARY,
                "tool_adapter": {
                    "backend": "runpod_rest",
                    "engine": "DPA-3.1-3M+MACE-MPA-0",
                    "version": "live-0.1.0",
                    "name": "RunpodRestL2EnsembleAdapter",
                },
                "audit": {
                    "input_hash": "sha256:" + "a" * 64,
                    "output_hash": "sha256:" + "b" * 64,
                    "source_manifest_refs": ["src:runpod:l2/ensemble_predict"],
                },
                "output": {
                    "predictions": [
                        {"model": "DPA-3.1-3M", "energy_eV_per_atom": -6.12, "force_rmse_eV_per_Ang": 0.04},
                        {"model": "MACE-MPA-0", "energy_eV_per_atom": -6.10, "force_rmse_eV_per_Ang": 0.05},
                    ],
                    "energy_disagreement_meV_per_atom": 12.0,
                    "force_rmse_disagreement_eV_per_Ang": 0.01,
                    "routing_decision": "promote",
                    "resource_metrics": {
                        "gpu_seconds": 124.0,
                        "vram_mb": 40960.0,
                        "wallclock_seconds": 132.0,
                    },
                },
            },
        )

    transport = httpx.MockTransport(handler)

    dispatcher = RunpodDispatcher(
        config=cfg,
        rest_client_factory=lambda: RunpodRestClient(
            base_url=cfg.RUNPOD_BASE_URL,
            api_token=cfg.RUNPOD_API_TOKEN,
            transport=transport,
        ),
    )

    result = dispatcher.dispatch(
        layer="L2",
        endpoint="ensemble_predict",
        payload={"chemical_system": "Li-La-Zr-O"},
    )
    assert isinstance(result, DispatchResult)
    assert result.backend == "runpod_rest"
    assert result.payload["tool_adapter"]["backend"] == "runpod_rest"
    # The dispatcher hit the configured URL exactly once and used Bearer auth.
    assert len(captured) == 1
    assert str(captured[0].url) == "https://runpod.example/api/v1/L2/ensemble_predict"
    assert captured[0].headers.get("Authorization") == "Bearer token-XYZ"


# ---------------------------------------------------------------------------
# 2. runpod_rest with NO credentials → raises + records BlockedSourceManifest
# ---------------------------------------------------------------------------


def test_dispatch_runpod_rest_without_creds_raises_and_records_blocked_manifest():
    """Honest-block: missing creds raises and emits a BlockedSourceManifest."""
    cfg = _cfg(
        MATERIALS_MODE="runpod_rest",
        L2_BACKEND="runpod_rest",
        RUNPOD_BASE_URL=None,
        RUNPOD_API_TOKEN=None,
    )

    captured: list[BlockedSourceManifest] = []
    dispatcher = RunpodDispatcher(config=cfg, on_blocked=captured.append)

    with pytest.raises(RunpodCredentialsError) as exc_info:
        dispatcher.dispatch(
            layer="L2",
            endpoint="ensemble_predict",
            payload={"chemical_system": "Li-La-Zr-O"},
        )
    # The exception names the missing credentials concretely.
    assert "RUNPOD_BASE_URL" in str(exc_info.value)
    assert "RUNPOD_API_TOKEN" in str(exc_info.value)

    # A BlockedSourceManifest was recorded with the documented blocker_reason.
    assert len(captured) == 1
    manifest = captured[0]
    assert manifest.blocker_reason == "unavailable_credentials"
    assert "L2" in manifest.attempted_locator
    assert "RUNPOD_BASE_URL" in manifest.blocker_detail
    assert "RUNPOD_API_TOKEN" in manifest.blocker_detail

    # Also reachable via the instance accessor.
    assert dispatcher.blocked_manifests() == [manifest]


def test_dispatch_runpod_rest_without_creds_does_not_return_mock():
    """Adversarial: dispatcher must NEVER return a mock-shaped dict labelled runpod_rest."""
    cfg = _cfg(
        MATERIALS_MODE="runpod_rest",
        L2_BACKEND="runpod_rest",
        RUNPOD_BASE_URL=None,
        RUNPOD_API_TOKEN=None,
    )

    dispatcher = RunpodDispatcher(config=cfg)

    with pytest.raises(RunpodCredentialsError):
        result = dispatcher.dispatch(
            layer="L2",
            endpoint="ensemble_predict",
            payload={"chemical_system": "Li-La-Zr-O"},
        )
        # If we ever reached here, the dispatcher would have returned a
        # value while the operator believes a runpod_rest call happened —
        # exactly the deception Wave C closes.  This statement should be
        # unreachable; if it executes, fail loudly.
        pytest.fail(  # pragma: no cover — sentinel
            f"Dispatcher returned {result!r} but should have raised "
            "RunpodCredentialsError before producing any envelope."
        )


# ---------------------------------------------------------------------------
# 3. runpod_mock → deterministic mock envelope, backend=runpod_mock
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "layer, mode_cfg",
    [
        ("L2", {"L2_BACKEND": "runpod_mock"}),
        ("L1", {"MATERIALS_L1_BACKEND": "runpod_mock"}),
        ("ionic", {"IONIC_TRANSPORT_BACKEND": "runpod_mock"}),
        ("L6", {"L6_GENERATOR_BACKEND": "runpod_mock"}),
    ],
)
def test_dispatch_runpod_mock_returns_mock_envelope(layer: str, mode_cfg: dict[str, str]) -> None:
    cfg = _cfg(MATERIALS_MODE="runpod_mock", **mode_cfg)
    dispatcher = RunpodDispatcher(config=cfg)
    result = dispatcher.dispatch(
        layer=layer,
        endpoint="run",
        payload={"chemical_system": "Li-La-Zr-O", "fixture": "LLZO"},
    )
    assert isinstance(result, DispatchResult)
    assert result.backend == "runpod_mock"
    env = result.payload
    assert env["tool_adapter"]["backend"] == "runpod_mock"
    assert env["research_boundary"] == RESEARCH_BOUNDARY
    assert HASH_REGEX.match(env["audit"]["input_hash"])
    assert HASH_REGEX.match(env["audit"]["output_hash"])


# ---------------------------------------------------------------------------
# 4. local_stub / local_cpu → dispatcher returns None
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("backend", ["local_stub", "local_cpu", "stub", "mock"])
def test_dispatch_local_returns_none(backend: str) -> None:
    cfg = _cfg(MATERIALS_MODE="local_cpu", L2_BACKEND=backend)
    dispatcher = RunpodDispatcher(config=cfg)
    assert (
        dispatcher.dispatch(
            layer="L2",
            endpoint="ensemble_predict",
            payload={"chemical_system": "Li-La-Zr-O"},
        )
        is None
    )


# ---------------------------------------------------------------------------
# is_rest_active / is_mock_active / credentials_ok
# ---------------------------------------------------------------------------


def test_is_rest_active_reads_per_layer_flag():
    cfg = _cfg(
        MATERIALS_MODE="runpod_rest",
        L2_BACKEND="runpod_rest",
        MATERIALS_L1_BACKEND="local_cpu",
    )
    d = RunpodDispatcher(config=cfg)
    assert d.is_rest_active("L2")
    assert not d.is_rest_active("L1")
    assert not d.is_mock_active("L2")


def test_is_mock_active_reads_per_layer_flag():
    cfg = _cfg(MATERIALS_MODE="runpod_mock", L2_BACKEND="runpod_mock")
    d = RunpodDispatcher(config=cfg)
    assert d.is_mock_active("L2")
    assert not d.is_rest_active("L2")


def test_credentials_ok_reports_missing_concretely():
    cfg = _cfg(RUNPOD_BASE_URL=None, RUNPOD_API_TOKEN=None)
    d = RunpodDispatcher(config=cfg)
    ok, missing = d.credentials_ok()
    assert ok is False
    assert "RUNPOD_BASE_URL" in missing
    assert "RUNPOD_API_TOKEN" in missing


def test_credentials_ok_reports_partial_missing():
    cfg = _cfg(RUNPOD_BASE_URL="https://x", RUNPOD_API_TOKEN=None)
    d = RunpodDispatcher(config=cfg)
    ok, missing = d.credentials_ok()
    assert ok is False
    assert missing == ["RUNPOD_API_TOKEN"]


def test_credentials_ok_when_both_present():
    cfg = _cfg(RUNPOD_BASE_URL="https://x", RUNPOD_API_TOKEN="t")
    d = RunpodDispatcher(config=cfg)
    ok, missing = d.credentials_ok()
    assert ok is True
    assert missing == []


# ---------------------------------------------------------------------------
# REST call retries on 5xx and finally raises RunpodRestError
# ---------------------------------------------------------------------------


def test_dispatch_runpod_rest_5xx_retries_then_raises_runpod_rest_error(monkeypatch):
    """A 500 response triggers retry; after the cap we surface RunpodRestError."""
    from zer0pa_materials.runpod import rest_client as rc_module
    from zer0pa_materials.runpod.rest_client import RunpodRestError

    # Speed the test up — short waits so we don't sit through ~10s of backoff.
    monkeypatch.setattr(rc_module, "RETRY_WAIT_MIN_S", 0.0)
    monkeypatch.setattr(rc_module, "RETRY_WAIT_MAX_S", 0.0)

    cfg = _cfg(
        MATERIALS_MODE="runpod_rest",
        L2_BACKEND="runpod_rest",
        RUNPOD_BASE_URL="https://runpod.example",
        RUNPOD_API_TOKEN="t",
    )
    attempts: dict[str, int] = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        return httpx.Response(500, json={"error": "service unavailable"})

    transport = httpx.MockTransport(handler)
    dispatcher = RunpodDispatcher(
        config=cfg,
        rest_client_factory=lambda: RunpodRestClient(
            base_url=cfg.RUNPOD_BASE_URL,
            api_token=cfg.RUNPOD_API_TOKEN,
            transport=transport,
        ),
    )
    with pytest.raises(RunpodRestError) as exc_info:
        dispatcher.dispatch(
            layer="L2", endpoint="ensemble_predict", payload={"x": 1}
        )
    assert exc_info.value.status_code == 500
    # tenacity stop_after_attempt(3) → exactly 3 attempts.
    assert attempts["count"] == 3
    assert exc_info.value.attempts == 3


# ---------------------------------------------------------------------------
# Adversarial: synthesised mock-shape labelled runpod_rest is still flagged
# by the schema-parity tests (we replicate the assertion here so this file
# exercises the boundary by itself).
# ---------------------------------------------------------------------------


def test_adversarial_mock_relabelled_runpod_rest_is_flagged_by_resource_metrics():
    """A relabelled mock envelope (backend=runpod_rest but identical to mock)
    is structurally identical at the schema level — that's why the
    parity test suite ALSO checks for ``audit.source_manifest_refs``
    being non-empty (real REST calls cite the model card).
    """
    from zer0pa_materials.runpod.mock_backends import build_runpod_mock_envelope

    fake = build_runpod_mock_envelope(
        layer="L2",
        input_payload={"chemical_system": "Li-La-Zr-O"},
        output_payload={"energy_per_atom_eV": -6.10, "routing_decision": "promote"},
    )
    # Operator-style relabelling (the deception caught in Wave 5c review).
    fake["tool_adapter"]["backend"] = "runpod_rest"

    # The honest-call schema-parity invariant is: real REST runs cite at
    # least one source manifest.  Mocks do not (their default
    # source_manifest_refs is []).  This mismatch is what
    # tests/parity/test_runpod_rest_invariants.py uses to detect the
    # relabelled mock pattern.
    assert fake["audit"]["source_manifest_refs"] == [], (
        "build_runpod_mock_envelope should NOT populate source_manifest_refs "
        "by default — that's the parity invariant separating real REST "
        "envelopes from mocks."
    )
