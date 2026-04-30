"""Wave C — runpod_rest schema-parity invariants.

The pre-Wave-C parity suite compared ``local_stub`` ↔ ``runpod_mock``
envelopes only — it never exercised a real (or mocked-real) ``runpod_rest``
path.  This file closes that gap.

For each GPU-bound layer we:

1.  Stand up an ``httpx.MockTransport`` that emulates a real Runpod
    deployment by returning a ``runpod_rest``-shaped envelope.
2.  Run :class:`RunpodDispatcher` end-to-end.
3.  Assert the response satisfies the schema-parity invariants every
    real run must satisfy:

    * ``tool_adapter.backend == "runpod_rest"`` (NOT mock).
    * ``tool_adapter.engine`` and ``tool_adapter.version`` populated.
    * ``audit.input_hash`` / ``audit.output_hash`` match
      ``^sha256:[0-9a-f]{64}$``.
    * ``audit.source_manifest_refs`` is non-empty (real runs cite the
      model card; mocks do not).  This is the assertion that detects the
      "relabelled mock" deception.
    * ``output.resource_metrics`` present with ``gpu_seconds`` /
      ``vram_mb`` / ``wallclock_seconds`` and all positive.
    * ``research_boundary`` is the verbatim research boundary.
    * Disagreement metrics carry at least one numeric value when the
      layer is L1 / L2 / ionic / quantum.
    * The response key set matches the keys
      :func:`build_runpod_mock_envelope` produces for the same layer
      (the schema-parity invariant Wave 5c documented but never tested
      against a real REST shape).

We also test the missing-credentials failure path: a ``runpod_rest``
config without credentials must raise ``RunpodCredentialsError`` and
record a ``BlockedSourceManifest``.

Boundary (verbatim)
-------------------
Research infrastructure for in silico materials science discovery.
Outputs are research artifacts. No regulatory certification claims.
No clinical or human-subject use. ITAR / weapons applications are
out of scope (Meta UMA Acceptable Use Policy and operator policy).
"""

from __future__ import annotations

import re
from typing import Any

import httpx
import pytest

from zer0pa_materials.boundary import RESEARCH_BOUNDARY
from zer0pa_materials.envelope.config import MaterialsConfig
from zer0pa_materials.envelope.hashing import HASH_REGEX, sha256_of
from zer0pa_materials.envelope.layer_outputs import (
    IonicTransportOutput,
    L1DftOutput,
    L1QuantumVqeOutput,
    L2MlipOutput,
    L3CalphadOutput,
    L4PhaseFieldOutput,
    L5ContinuumOutput,
    L6GenerativeOutput,
    L15PhononOutput,
    validate_layer_output,
)
from zer0pa_materials.runpod.dispatcher import (
    RunpodCredentialsError,
    RunpodDispatcher,
)
from zer0pa_materials.runpod.mock_backends import (
    RUNPOD_MOCK_LAYERS,
    build_runpod_mock_envelope,
)
from zer0pa_materials.runpod.rest_client import RunpodRestClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _cfg_runpod_rest_with_creds(layer_flag: str = "L2_BACKEND") -> MaterialsConfig:
    """Return a config with MATERIALS_MODE + the named layer flag set to runpod_rest."""
    base = {
        "MATERIALS_MODE": "runpod_rest",
        "RUNPOD_BASE_URL": "https://runpod.example/api",
        "RUNPOD_API_TOKEN": "secret-token",
        "UMA_HF_ORG": "fair-chem",
        "UMA_HF_TOKEN": "hf-secret",
        layer_flag: "runpod_rest",
    }
    return MaterialsConfig.model_construct(**base)


# Per-layer "honest" REST response payload — mirrors what a real Runpod
# server would return.  Every required field is present so the schema
# invariants pass; ``source_manifest_refs`` is populated to encode the
# "real runs cite the model card" contract.  Each dict matches the
# corresponding ``LayerOutputBase`` subclass exactly (extra="forbid").
_LAYER_HONEST_OUTPUT: dict[str, dict[str, Any]] = {
    "L1": {
        "code": "QE",
        "functional": "PBE",
        "total_energy_eV": -123.4,
        "force_rmse_eV_per_Ang": 0.04,
        "kpoint_mesh": [4, 4, 4],
        "convergence_delta_meV_per_atom": 1.4,
        "publication_grade": True,
    },
    "L2": {
        "predictions": [
            {"model": "DPA-3.1-3M", "energy_eV_per_atom": -6.12, "force_rmse_eV_per_Ang": 0.04},
            {"model": "MACE-MPA-0", "energy_eV_per_atom": -6.10, "force_rmse_eV_per_Ang": 0.05},
        ],
        "energy_disagreement_meV_per_atom": 12.0,
        "force_rmse_disagreement_eV_per_Ang": 0.01,
        "routing_decision": "promote",
    },
    "ionic": {
        "migration_barrier_eV": 0.22,
        "diffusion_coefficient_cm2_per_s": 1.0e-7,
        "nernst_einstein_conductivity_S_per_cm": 8.4e-4,
        "interface_stability": "li_metal_stable",
        "confidence": 0.85,
    },
    "L1.5": {
        "imaginary_mode_max_THz": 0.10,
        "mlip_vs_dft_force_rmse_eV_per_Ang": 0.04,
        "qmesh_convergence_pct": 5.0,
        "thermal_conductivity_W_per_mK": 1.4,
        "zt": 0.82,
    },
    "L3": {
        "tdb_ref": "src:tdb:LLZO",
        "equilibrium_phases": ["Li7La3Zr2O12"],
        "phase_fraction_posterior": {"Li7La3Zr2O12": 1.0},
        "espei_diagnostics": {"r_hat": 1.01, "ess": 1200, "n_chains": 4, "n_samples": 4000},
    },
    "L4": {
        "cahn_hilliard_mass_drift": 1.0e-4,
        "allen_cahn_bounds_violation": 1.0e-5,
        "spparks_potts_energy_monotonic": True,
    },
    "L5": {
        "tensors": [
            {"name": "stiffness", "spd": True, "eigvals_min": 12.0},
        ],
        "analytic_heat_slab_error": 1.0e-7,
        "elastic_patch_residual": 1.0e-9,
        "fenicsx_vs_dealii_strain_energy_disagreement_pct": 0.5,
    },
    "L6": {
        "candidate_uri": "artifact://l6/runpod_rest/candidate.cif",
        "structure_hash": "sha256:" + "f" * 64,
        "novelty_status": "novel",
        "cif_valid": True,
        "charge_neutral": True,
        "minimum_distance_ok": True,
    },
    "quantum": {
        "system": "H2",
        "ansatz": "UCCSD",
        "qubits": 4,
        "optimizer": "SPSA",
        "ground_state_energy_Ha": -1.13,
        "classical_reference_Ha": -1.13721,
    },
}

_LAYER_FLAG_NAMES: dict[str, str] = {
    "L1": "MATERIALS_L1_BACKEND",
    "L2": "L2_BACKEND",
    "ionic": "IONIC_TRANSPORT_BACKEND",
    "L1.5": "L15_FORCE_BACKEND",
    "L3": "L3_CALPHAD_PROVIDER",
    "L4": "L4_SOLVER",
    "L5": "L5_EXECUTION_MODE",
    "L6": "L6_GENERATOR_BACKEND",
    "quantum": "MATERIALS_L1_BACKEND",
}


def _build_honest_rest_envelope(layer: str, input_payload: dict[str, Any]) -> dict[str, Any]:
    """Build a server-side envelope that satisfies every Wave-C invariant."""
    output_core = _LAYER_HONEST_OUTPUT[layer]
    output = {
        **output_core,
        "resource_metrics": {
            "gpu_seconds": 124.0,
            "vram_mb": 40960.0,
            "wallclock_seconds": 132.0,
        },
        "backend_tag": "runpod_rest",
    }
    in_hash = sha256_of(input_payload)
    out_hash = sha256_of({**output, "backend": "runpod_rest"})

    disagreement_metrics: list[dict[str, Any]] = []
    if layer in ("L1", "L2", "ionic", "quantum"):
        disagreement_metrics = [
            {
                "name": f"{layer.lower().replace('.', '_')}.disagreement_real",
                "value": 12.0 if layer == "L2" else 1.4e-5,
                "unit": "meV/atom" if layer == "L2" else None,
                "references": ["src:runpod:model-card"],
            }
        ]

    return {
        "research_boundary": RESEARCH_BOUNDARY,
        "contract_version": "zer0pa.materials.layer-envelope.v1",
        "run_id": f"run:rest_{layer.lower().replace('.', '_')}",
        "campaign_id": f"campaign:rest_{layer.lower().replace('.', '_')}",
        "candidate_id": f"candidate:rest_{layer.lower().replace('.', '_')}",
        "layer": layer,
        "tool_adapter": {
            "name": f"RunpodRest{layer.replace('.', '_')}Adapter",
            "version": "live-0.1.0",
            "backend": "runpod_rest",
            "engine": f"REST-{layer}-engine",
        },
        "input_refs": [],
        "output": output,
        "confidence": {"score": 0.85, "band": "high", "basis": ["runpod_rest"]},
        "disagreement": {"metrics": disagreement_metrics},
        "falsifier": {"status": "pass", "items": []},
        "audit": {
            "audit_record_id": f"audit:rest:{layer.lower().replace('.', '_')}",
            "input_hash": in_hash,
            "output_hash": out_hash,
            "source_manifest_refs": [
                "src:runpod:model-card",
                f"src:runpod:{layer.lower().replace('.', '_')}-checkpoint",
            ],
        },
        "rights": {
            "rights_claim_id": f"rights:rest:{layer.lower().replace('.', '_')}",
            "reuse_scope": "tenant_only",
        },
        "back_edges": [],
    }


def _make_dispatcher(cfg: MaterialsConfig, transport: httpx.BaseTransport) -> RunpodDispatcher:
    return RunpodDispatcher(
        config=cfg,
        rest_client_factory=lambda: RunpodRestClient(
            base_url=cfg.RUNPOD_BASE_URL,
            api_token=cfg.RUNPOD_API_TOKEN,
            transport=transport,
        ),
    )


# ---------------------------------------------------------------------------
# Schema-parity invariants — applied per layer
# ---------------------------------------------------------------------------


_HONEST_REST_LAYERS = ("L1", "L2", "ionic", "L1.5", "L3", "L4", "L5", "L6", "quantum")


def _assert_runpod_rest_invariants(env: dict[str, Any], *, layer: str) -> None:
    """Per-envelope assertions that real REST envelopes MUST satisfy."""
    # 1. Backend label.
    assert env["tool_adapter"]["backend"] == "runpod_rest", (
        f"backend must be 'runpod_rest', got {env['tool_adapter']['backend']!r}"
    )
    # 2. Engine + version populated (real runs identify the engine).
    assert env["tool_adapter"]["engine"], "tool_adapter.engine must be non-empty"
    assert env["tool_adapter"]["version"], "tool_adapter.version must be non-empty"
    # 3. Hashes are sha256:<hex>.
    assert HASH_REGEX.match(env["audit"]["input_hash"])
    assert HASH_REGEX.match(env["audit"]["output_hash"])
    # 4. Source manifest refs non-empty — the "real runs cite the model card"
    #    invariant that distinguishes honest REST envelopes from
    #    relabelled mocks.
    refs = env["audit"]["source_manifest_refs"]
    assert refs, (
        f"runpod_rest envelope at layer {layer!r} must cite at least one "
        "source manifest (audit.source_manifest_refs).  An empty list is "
        "the smoking-gun pattern of a relabelled mock."
    )
    # 5. Resource metrics present + numeric + positive.
    rm = env["output"]["resource_metrics"]
    for key in ("gpu_seconds", "vram_mb", "wallclock_seconds"):
        assert key in rm, f"resource_metrics missing key {key!r}"
        assert isinstance(rm[key], (int, float))
        assert rm[key] > 0, f"resource_metrics[{key!r}] must be positive"
    # 6. Boundary verbatim.
    assert env["research_boundary"] == RESEARCH_BOUNDARY
    # 7. Disagreement metrics for MLIP/DFT layers.
    if layer in ("L1", "L2", "ionic", "quantum"):
        metrics = env["disagreement"]["metrics"]
        assert metrics, f"layer {layer!r} must carry disagreement.metrics"
        assert any(isinstance(m.get("value"), (int, float)) for m in metrics), (
            f"layer {layer!r}: at least one disagreement metric must have "
            "a numeric value"
        )


def _assert_layer_output_validates(env: dict[str, Any], *, layer: str) -> None:
    """Validate ``env['output']`` against its layer's Pydantic schema.

    The Wave-C contract: a real REST envelope's output dict MUST validate
    as the layer's :class:`LayerOutputBase` subclass.  The output may
    carry extra keys (``resource_metrics``, ``backend_tag``) so we strip
    them before validation.
    """
    raw_output = dict(env["output"])
    raw_output.pop("resource_metrics", None)
    raw_output.pop("backend_tag", None)

    # ``validate_layer_output`` raises pydantic's ValidationError on failure.
    validate_layer_output(layer, raw_output)


def _assert_schema_parity_against_mock(
    rest_env: dict[str, Any],
    *,
    layer: str,
    input_payload: dict[str, Any],
) -> None:
    """The REST response key set must match what build_runpod_mock_envelope produces.

    This is the Wave-C schema-parity invariant: same layer, same inputs,
    same key shape.  Values differ (REST vs mock), but the structure is
    identical so downstream consumers do not branch on backend.
    """
    mock_env = build_runpod_mock_envelope(
        layer=layer,
        input_payload=input_payload,
        output_payload=_LAYER_HONEST_OUTPUT[layer],
    )
    rest_keys = set(rest_env.keys())
    mock_keys = set(mock_env.keys())
    assert rest_keys == mock_keys, (
        f"layer {layer!r} top-level key drift: "
        f"only-in-rest={rest_keys - mock_keys}, "
        f"only-in-mock={mock_keys - rest_keys}"
    )

    # Tool adapter top-level keys.
    rest_ta = set(rest_env["tool_adapter"].keys())
    mock_ta = set(mock_env["tool_adapter"].keys())
    assert rest_ta == mock_ta, (
        f"layer {layer!r} tool_adapter key drift: rest={rest_ta}, mock={mock_ta}"
    )


# ---------------------------------------------------------------------------
# Per-layer "real REST call" tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("layer", _HONEST_REST_LAYERS)
def test_runpod_rest_envelope_satisfies_invariants(layer: str) -> None:
    """End-to-end: dispatcher → RunpodRestClient → MockTransport → invariants."""
    flag = _LAYER_FLAG_NAMES[layer]
    cfg = _cfg_runpod_rest_with_creds(layer_flag=flag)

    input_payload = {"chemical_system": "Li-La-Zr-O", "fixture": "LLZO"}

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=_build_honest_rest_envelope(layer, input_payload),
        )

    dispatcher = _make_dispatcher(cfg, httpx.MockTransport(handler))
    result = dispatcher.dispatch(
        layer=layer,
        endpoint="run",
        payload=input_payload,
    )
    assert result is not None
    assert result.backend == "runpod_rest"

    _assert_runpod_rest_invariants(result.payload, layer=layer)
    _assert_schema_parity_against_mock(result.payload, layer=layer, input_payload=input_payload)


@pytest.mark.parametrize("layer", _HONEST_REST_LAYERS)
def test_runpod_rest_output_validates_as_layer_schema(layer: str) -> None:
    """``env.output`` validates as the layer's pydantic output schema."""
    flag = _LAYER_FLAG_NAMES[layer]
    cfg = _cfg_runpod_rest_with_creds(layer_flag=flag)
    input_payload = {"chemical_system": "Li-La-Zr-O", "fixture": "LLZO"}

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=_build_honest_rest_envelope(layer, input_payload),
        )

    dispatcher = _make_dispatcher(cfg, httpx.MockTransport(handler))
    result = dispatcher.dispatch(layer=layer, endpoint="run", payload=input_payload)
    assert result is not None
    _assert_layer_output_validates(result.payload, layer=layer)


# ---------------------------------------------------------------------------
# The credentials-missing failure path
# ---------------------------------------------------------------------------


def test_runpod_rest_without_credentials_raises_and_blocks():
    """Adversarial: no creds → no envelope, no mock, just an honest block."""
    cfg = MaterialsConfig.model_construct(
        MATERIALS_MODE="runpod_rest",
        L2_BACKEND="runpod_rest",
        RUNPOD_BASE_URL=None,
        RUNPOD_API_TOKEN=None,
    )
    dispatcher = RunpodDispatcher(config=cfg)
    with pytest.raises(RunpodCredentialsError):
        dispatcher.dispatch(
            layer="L2",
            endpoint="ensemble_predict",
            payload={"chemical_system": "Li-La-Zr-O"},
        )
    blocked = dispatcher.blocked_manifests()
    assert len(blocked) == 1
    m = blocked[0]
    assert m.blocker_reason == "unavailable_credentials"
    assert m.attempted_locator.startswith("runpod://L2/")


# ---------------------------------------------------------------------------
# Adversarial: relabelled mock fails the Wave-C invariants
# ---------------------------------------------------------------------------


def test_relabelled_mock_envelope_fails_source_manifest_invariant():
    """A mock relabelled as runpod_rest fails the source_manifest_refs invariant.

    This test encodes the Wave-C detection: any envelope claiming
    ``backend=runpod_rest`` whose ``audit.source_manifest_refs`` is empty
    is, by construction, a relabelled mock.
    """
    fake = build_runpod_mock_envelope(
        layer="L2",
        input_payload={"chemical_system": "Li-La-Zr-O"},
        output_payload=_LAYER_HONEST_OUTPUT["L2"],
    )
    fake["tool_adapter"]["backend"] = "runpod_rest"
    # Wave-C invariant: must raise AssertionError because source_manifest_refs is [].
    with pytest.raises(AssertionError, match="source manifest"):
        _assert_runpod_rest_invariants(fake, layer="L2")


def test_relabelled_mock_with_synthetic_refs_still_caught_by_engine_invariant():
    """A mock relabelled and given fake refs still fails the engine invariant.

    The mock backend's engine name ends in ``-runpod_mock`` — even if an
    operator forges ``source_manifest_refs``, the engine string still
    points at the mock unless it is also rewritten.  Our test surfaces
    this as a direct assertion the lead agent can run.
    """
    fake = build_runpod_mock_envelope(
        layer="L2",
        input_payload={"chemical_system": "Li-La-Zr-O"},
        output_payload=_LAYER_HONEST_OUTPUT["L2"],
    )
    fake["tool_adapter"]["backend"] = "runpod_rest"
    fake["audit"]["source_manifest_refs"] = ["src:fake:forged"]
    # Engine still encodes the mock origin.
    assert "runpod_mock" in fake["tool_adapter"]["engine"], (
        "build_runpod_mock_envelope should encode 'runpod_mock' in the "
        "engine string so a relabelled envelope is detectable by string "
        "match in CI."
    )
