"""Tests for quantum falsifiers."""

from __future__ import annotations

import pytest

from zer0pa_materials.adapters.quantum.pennylane_vqe import PennyLaneVqeSolver
from zer0pa_materials.adapters.l1.pyscf import _H2_FCI_Ha, _LIH_CASCI_Ha
from zer0pa_materials.envelope import (
    AuditBlock,
    Envelope,
    L1QuantumVqeOutput,
    RightsBlock,
    ToolAdapter,
    sha256_of,
    canonical_json_bytes,
)
from zer0pa_materials.boundary import RESEARCH_BOUNDARY
from zer0pa_materials.falsifiers.quantum_falsifiers import (
    vqe_h2_classical_match,
    vqe_lih_active_space_match,
    quantum_slot_classical_simulation_only,
)


def _make_vqe_envelope(
    system: str,
    vqe_Ha: float,
    ref_Ha: float,
    backend: str = "stub",
    engine: str = "PennyLane/default.qubit",
) -> Envelope:
    output = L1QuantumVqeOutput(
        system=system,  # type: ignore
        ansatz="UCCSD",
        qubits=4,
        optimizer="COBYLA",
        ground_state_energy_Ha=vqe_Ha,
        classical_reference_Ha=ref_Ha,
    )
    out_dict = output.model_dump(mode="json")
    return Envelope(
        research_boundary=RESEARCH_BOUNDARY,
        run_id="run:test:000001",
        campaign_id="campaign:test-falsifier",
        candidate_id="candidate:test-vqe",
        layer="L1",
        tool_adapter=ToolAdapter(
            name="TestVqe",
            version="0.1.0",
            backend=backend,  # type: ignore
            engine=engine,
        ),
        output=out_dict,
        audit=AuditBlock(
            audit_record_id="audit:test:000001",
            input_hash=sha256_of(canonical_json_bytes({"system": system})),
            output_hash=sha256_of(canonical_json_bytes(out_dict)),
        ),
        rights=RightsBlock(
            rights_claim_id="rights:test:000001",
            reuse_scope="tenant_only",
        ),
    )


# ---------------------------------------------------------------------------
# H2 gate
# ---------------------------------------------------------------------------

def test_h2_gate_passes_within_threshold() -> None:
    env = _make_vqe_envelope("H2", _H2_FCI_Ha + 5e-4, _H2_FCI_Ha)
    item = vqe_h2_classical_match(env)
    assert item.status == "pass"
    assert item.actual <= 1e-3


def test_h2_gate_fails_above_1e3_ha() -> None:
    env = _make_vqe_envelope("H2", _H2_FCI_Ha + 0.002, _H2_FCI_Ha)
    item = vqe_h2_classical_match(env)
    assert item.status == "fail"


def test_h2_gate_passes_at_exactly_1e3() -> None:
    env = _make_vqe_envelope("H2", _H2_FCI_Ha + 1e-3, _H2_FCI_Ha)
    item = vqe_h2_classical_match(env)
    assert item.status == "pass"


def test_h2_gate_with_override_reference() -> None:
    env = _make_vqe_envelope("H2", -1.163, -1.163)  # zero delta
    item = vqe_h2_classical_match(env, fci_reference_Ha=-1.163)
    assert item.status == "pass"
    assert item.actual == pytest.approx(0.0, abs=1e-9)


# ---------------------------------------------------------------------------
# LiH gate
# ---------------------------------------------------------------------------

def test_lih_gate_passes_within_threshold() -> None:
    env = _make_vqe_envelope("LiH", _LIH_CASCI_Ha + 2e-3, _LIH_CASCI_Ha)
    item = vqe_lih_active_space_match(env)
    assert item.status == "pass"


def test_lih_gate_fails_above_5e3_ha() -> None:
    env = _make_vqe_envelope("LiH", _LIH_CASCI_Ha + 0.01, _LIH_CASCI_Ha)
    item = vqe_lih_active_space_match(env)
    assert item.status == "fail"


def test_lih_gate_passes_at_exactly_5e3() -> None:
    env = _make_vqe_envelope("LiH", _LIH_CASCI_Ha + 5e-3, _LIH_CASCI_Ha)
    item = vqe_lih_active_space_match(env)
    assert item.status == "pass"


# ---------------------------------------------------------------------------
# Classical simulation only gate
# ---------------------------------------------------------------------------

def test_classical_sim_passes_for_stub_backend() -> None:
    env = _make_vqe_envelope("H2", _H2_FCI_Ha, _H2_FCI_Ha, backend="stub", engine="default.qubit")
    item = quantum_slot_classical_simulation_only(env)
    assert item.status == "pass"


def test_classical_sim_passes_for_local_cpu() -> None:
    env = _make_vqe_envelope("H2", _H2_FCI_Ha, _H2_FCI_Ha, backend="local_cpu", engine="statevector")
    item = quantum_slot_classical_simulation_only(env)
    assert item.status == "pass"


def test_classical_sim_fails_for_runpod_with_simulator_engine() -> None:
    """runpod_rest + statevector engine = false hardware claim."""
    env = _make_vqe_envelope("H2", _H2_FCI_Ha, _H2_FCI_Ha, backend="runpod_rest", engine="default.qubit")
    item = quantum_slot_classical_simulation_only(env)
    assert item.status == "fail"


def test_classical_sim_passes_for_runpod_with_hardware_engine() -> None:
    """runpod_rest + hardware engine tag is OK."""
    env = _make_vqe_envelope("H2", _H2_FCI_Ha, _H2_FCI_Ha, backend="runpod_rest", engine="IonQ-hardware-v1")
    item = quantum_slot_classical_simulation_only(env)
    assert item.status == "pass"
