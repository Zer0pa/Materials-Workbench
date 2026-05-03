"""Runpod mock backends — per-layer ``runpod_mock`` envelopes.

For every GPU-bound layer the function :func:`build_runpod_mock_envelope`
returns a schema-identical :class:`~zer0pa_materials_workbench.envelope.Envelope` with:

* ``tool_adapter.backend = "runpod_mock"``
* Synthetic resource metrics (``gpu_seconds``, ``vram_mb``, ``wallclock_seconds``)
  injected into ``output["resource_metrics"]``.
* Deterministic hashes that match the ``local_stub`` backend for the same
  input payload (same seed → same hash).
* Boundary block carried verbatim.

GPU-bound layers (PRD §Runpod Migration):
    L6  — MatterGen / DiffCSP / CrystaLLM
    L1  — QE / CP2K / GPU4PySCF
    Quantum — PennyLane real-hardware
    L2  — DPA-3.1-3M / MACE-MPA-0 / UMA at scale
    Ionic — real NEB / AIMD / MLIP-MD
    L1.5 — Phonopy / Phono3py / HiPhive / BoltzTraP2 / AMSET
    L3  — ESPEI quaternary fits / PhaseForgePlus real
    L4  — PRISMS-PF / MOOSE / MICROSIM / SPPARKS / neural-op training
    L5  — FEniCSx / deal.II / OpenFOAM at production mesh

Phase 0 does not have a GPU layer; parity between optimade_mock and
optimade_live is covered separately in tests/parity/test_phase0_parity.py.

Boundary (verbatim)
-------------------
Research infrastructure for in silico materials science discovery.
Outputs are research artifacts. No regulatory certification claims.
No clinical or human-subject use. ITAR / weapons applications are
out of scope (Meta UMA Acceptable Use Policy and operator policy).
"""

from __future__ import annotations

import uuid
from typing import Any

from zer0pa_materials_workbench.boundary import RESEARCH_BOUNDARY
from zer0pa_materials_workbench.envelope.hashing import sha256_of

__all__ = [
    "MOCK_RESOURCE_METRICS",
    "RUNPOD_MOCK_LAYERS",
    "build_runpod_mock_envelope",
]

# Layers that have GPU-bound runpod_mock backends.
RUNPOD_MOCK_LAYERS: tuple[str, ...] = (
    "L6",
    "L1",
    "quantum",
    "L2",
    "ionic",
    "L1.5",
    "L3",
    "L4",
    "L5",
)

# Deterministic synthetic resource metrics per layer.
# These are *schema-constant* — the values change when the real backend runs,
# but the schema (keys) must be present in every runpod_mock envelope.
MOCK_RESOURCE_METRICS: dict[str, dict[str, float]] = {
    "L6": {"gpu_seconds": 47.2, "vram_mb": 18432.0, "wallclock_seconds": 52.1},
    "L1": {"gpu_seconds": 312.5, "vram_mb": 24576.0, "wallclock_seconds": 340.0},
    "quantum": {"gpu_seconds": 88.0, "vram_mb": 8192.0, "wallclock_seconds": 95.0},
    "L2": {"gpu_seconds": 124.3, "vram_mb": 40960.0, "wallclock_seconds": 135.0},
    "ionic": {"gpu_seconds": 580.0, "vram_mb": 24576.0, "wallclock_seconds": 620.0},
    "L1.5": {"gpu_seconds": 95.0, "vram_mb": 16384.0, "wallclock_seconds": 102.0},
    "L3": {"gpu_seconds": 720.0, "vram_mb": 32768.0, "wallclock_seconds": 760.0},
    "L4": {"gpu_seconds": 1840.0, "vram_mb": 81920.0, "wallclock_seconds": 1920.0},
    "L5": {"gpu_seconds": 2560.0, "vram_mb": 81920.0, "wallclock_seconds": 2700.0},
}

# Canonical layer-to-adapter-name map for the mock backend.
_LAYER_ADAPTER_NAMES: dict[str, str] = {
    "L6": "RunpodMockL6GenerativeAdapter",
    "L1": "RunpodMockL1DftAdapter",
    "quantum": "RunpodMockQuantumAdapter",
    "L2": "RunpodMockL2MlipAdapter",
    "ionic": "RunpodMockIonicTransportAdapter",
    "L1.5": "RunpodMockL15PhononAdapter",
    "L3": "RunpodMockL3CalphadAdapter",
    "L4": "RunpodMockL4PhaseFieldAdapter",
    "L5": "RunpodMockL5ContinuumAdapter",
}

# Canonical layer-to-engine map for the mock backend.
_LAYER_ENGINES: dict[str, str] = {
    "L6": "MatterGen/DiffCSP/CrystaLLM-runpod_mock",
    "L1": "QE/CP2K/GPU4PySCF-runpod_mock",
    "quantum": "PennyLane-real-hardware-runpod_mock",
    "L2": "DPA-3.1-3M/MACE-MPA-0/UMA-runpod_mock",
    "ionic": "NEB/AIMD/MLIP-MD-runpod_mock",
    "L1.5": "Phonopy/Phono3py/HiPhive/BoltzTraP2/AMSET-runpod_mock",
    "L3": "ESPEI-quaternary/PhaseForgePlus-runpod_mock",
    "L4": "PRISMS-PF/MOOSE/MICROSIM/SPPARKS/neural-op-runpod_mock",
    "L5": "FEniCSx/dealII/OpenFOAM-runpod_mock",
}


def build_runpod_mock_envelope(
    layer: str,
    input_payload: dict[str, Any],
    output_payload: dict[str, Any] | None = None,
    candidate_id: str | None = None,
    campaign_id: str | None = None,
    run_id: str | None = None,
    disagreement_metrics: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a schema-valid runpod_mock envelope for *layer*.

    The envelope is deterministic for the same ``input_payload``: the
    ``input_hash`` is ``sha256_of(input_payload)``; the ``output_hash`` is
    ``sha256_of({**output_payload, "backend": "runpod_mock"})``.

    Resource metrics are injected into ``output["resource_metrics"]`` so
    parity tests can assert they are *present* in ``runpod_mock`` envelopes and
    *absent* (or zero) in ``local_stub`` envelopes.

    Args:
        layer: One of :data:`RUNPOD_MOCK_LAYERS`.
        input_payload: The same dict passed to the local_stub adapter.
        output_payload: Layer output payload; if None a minimal placeholder is
            used.  The function merges resource_metrics into whatever is passed.
        candidate_id: Override; defaults to a fresh URN.
        campaign_id: Override; defaults to ``"campaign:<layer>-runpod-mock"``.
        run_id: Override; defaults to a fresh URN.
        disagreement_metrics: Optional list of disagreement metric dicts
            (``{name, value, unit, references}``).  Injected verbatim into
            ``disagreement.metrics``.  If None or empty the layer uses its
            own sensible defaults.

    Returns:
        A dict conforming to :class:`~zer0pa_materials_workbench.envelope.Envelope`.

    Raises:
        ValueError: if *layer* is not in :data:`RUNPOD_MOCK_LAYERS`.
    """
    if layer not in RUNPOD_MOCK_LAYERS:
        raise ValueError(
            f"layer {layer!r} is not a GPU-bound runpod_mock layer. "
            f"Valid layers: {RUNPOD_MOCK_LAYERS}"
        )

    cid = candidate_id or f"candidate:{layer.lower().replace('.', '_')}:{uuid.uuid4().hex[:12]}"
    cmp = campaign_id or f"campaign:{layer.lower().replace('.', '_')}-runpod-mock"
    rid = run_id or f"run:{layer.lower().replace('.', '_')}:{uuid.uuid4().hex[:12]}"

    # Inject resource metrics into the output payload.
    resource_metrics = MOCK_RESOURCE_METRICS.get(layer, {
        "gpu_seconds": 1.0, "vram_mb": 1024.0, "wallclock_seconds": 2.0
    })
    merged_output = dict(output_payload or {})
    merged_output["resource_metrics"] = resource_metrics
    merged_output["backend_tag"] = "runpod_mock"

    input_hash = sha256_of(input_payload)
    output_hash = sha256_of({**merged_output, "backend": "runpod_mock"})

    # Default disagreement metrics per layer.
    if disagreement_metrics is None:
        disagreement_metrics = _default_disagreement_metrics(layer)

    envelope: dict[str, Any] = {
        "contract_version": "zer0pa.materials.layer-envelope.v1",
        "research_boundary": RESEARCH_BOUNDARY,
        "run_id": rid,
        "campaign_id": cmp,
        "candidate_id": cid,
        "layer": layer,
        "tool_adapter": {
            "name": _LAYER_ADAPTER_NAMES[layer],
            "version": "0.1.0-runpod_mock",
            "backend": "runpod_mock",
            "engine": _LAYER_ENGINES[layer],
        },
        "input_refs": [],
        "output": merged_output,
        "confidence": {"score": 0.5, "band": "medium", "basis": ["runpod_mock"]},
        "disagreement": {"metrics": disagreement_metrics},
        "falsifier": {"status": "pass", "items": []},
        "audit": {
            "audit_record_id": f"audit:{layer.lower().replace('.', '_')}:{uuid.uuid4().hex[:12]}",
            "input_hash": input_hash,
            "output_hash": output_hash,
            "source_manifest_refs": [],
        },
        "rights": {
            "rights_claim_id": f"rights:{layer.lower().replace('.', '_')}:{uuid.uuid4().hex[:12]}",
            "reuse_scope": "tenant_only",
        },
        "back_edges": [],
    }
    return envelope


def _default_disagreement_metrics(layer: str) -> list[dict[str, Any]]:
    """Return sensible default disagreement metrics for each layer.

    MLIP/DFT layers MUST carry disagreement metrics (PRD hard-failure:
    "model response without disagreement metrics").
    """
    defaults: dict[str, list[dict[str, Any]]] = {
        "L6": [
            {"name": "l6.novelty_score_std", "value": 0.03, "unit": None, "references": []},
            {"name": "l6.generator_ensemble_disagreement", "value": 0.05, "unit": None, "references": []},
        ],
        "L1": [
            {"name": "l1.dft_code_energy_mae_eV", "value": 0.012, "unit": "eV/atom", "references": []},
            {"name": "l1.convergence_delta_eV", "value": 1.4e-5, "unit": "eV", "references": []},
        ],
        "quantum": [
            {"name": "quantum.vqe_fci_delta_Ha", "value": 1.8e-4, "unit": "Ha", "references": []},
            {"name": "quantum.ansatz_circuit_variance", "value": 0.002, "unit": None, "references": []},
        ],
        "L2": [
            {"name": "l2.energy_disagreement_meV_per_atom", "value": 8.4, "unit": "meV/atom", "references": []},
            {"name": "l2.force_disagreement_eV_per_ang", "value": 0.04, "unit": "eV/Å", "references": []},
        ],
        "ionic": [
            {"name": "ionic.neb_mlmd_barrier_mae_eV", "value": 0.022, "unit": "eV", "references": []},
            {"name": "ionic.diffusivity_relative_spread", "value": 0.15, "unit": None, "references": []},
        ],
        "L1.5": [
            {"name": "l15.boltztraP2_amset_ZT_relative_diff", "value": 0.08, "unit": None, "references": []},
            {"name": "l15.phonon_free_energy_std_eV", "value": 0.005, "unit": "eV", "references": []},
        ],
        "L3": [
            {"name": "l3.espei_mcmc_posterior_std_J_per_mol", "value": 120.0, "unit": "J/mol", "references": []},
            {"name": "l3.phase_boundary_disagreement_K", "value": 25.0, "unit": "K", "references": []},
        ],
        "L4": [
            {"name": "l4.solver_ensemble_field_mae", "value": 0.031, "unit": None, "references": []},
            {"name": "l4.neural_op_vs_pde_relative_err", "value": 0.042, "unit": None, "references": []},
        ],
        "L5": [
            {"name": "l5.fem_cfd_stress_mae_MPa", "value": 1.2, "unit": "MPa", "references": []},
            {"name": "l5.solver_convergence_residual", "value": 1.3e-8, "unit": None, "references": []},
        ],
    }
    return defaults.get(layer, [
        {"name": f"{layer.lower().replace('.','_')}.mock_disagreement", "value": 0.0, "unit": None, "references": []},
    ])
