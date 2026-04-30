"""Quantum slot falsifiers (PRD §Layer-Specific Falsifiers And Gates — Quantum).

Functions
---------
vqe_h2_classical_match(vqe_envelope, fci_reference_Ha) -> FalsifierItem
    Pass if |VQE - FCI| <= 1e-3 Ha (H2 gate; PRD §L1 exact threshold).

vqe_lih_active_space_match(vqe_envelope, ref_Ha) -> FalsifierItem
    Pass if |VQE - CASCI| <= 5e-3 Ha (LiH gate; PRD §L1 exact threshold).

quantum_slot_classical_simulation_only(envelope) -> FalsifierItem
    Fail if envelope claims real quantum hardware but backend != expected.
"""

from __future__ import annotations

from zer0pa_materials.envelope import (
    Envelope,
    FalsifierItem,
    L1QuantumVqeOutput,
)

__all__ = [
    "vqe_h2_classical_match",
    "vqe_lih_active_space_match",
    "quantum_slot_classical_simulation_only",
]

# PRD §L1 exact thresholds (do NOT loosen)
_H2_THRESHOLD_Ha = 1e-3
_LIH_THRESHOLD_Ha = 5e-3


def _extract_vqe_output(envelope: Envelope) -> L1QuantumVqeOutput:
    return L1QuantumVqeOutput.model_validate(envelope.output)


def vqe_h2_classical_match(
    vqe_envelope: Envelope,
    fci_reference_Ha: float | None = None,
) -> FalsifierItem:
    """Gate: H2 VQE energy within 1e-3 Ha of PySCF FCI (PRD §L1).

    Parameters
    ----------
    vqe_envelope:
        Envelope carrying an L1QuantumVqeOutput for H2.
    fci_reference_Ha:
        Override the FCI reference. If None, uses the reference stored in
        the output (``classical_reference_Ha``).
    """
    output = _extract_vqe_output(vqe_envelope)
    ref = fci_reference_Ha if fci_reference_Ha is not None else output.classical_reference_Ha
    delta = abs(output.ground_state_energy_Ha - ref)
    status = "pass" if delta <= _H2_THRESHOLD_Ha else "fail"
    return FalsifierItem(
        name="l1.h2_vqe_vs_fci",
        threshold=f"<= {_H2_THRESHOLD_Ha} Ha",
        actual=round(delta, 8),
        status=status,
    )


def vqe_lih_active_space_match(
    vqe_envelope: Envelope,
    ref_Ha: float | None = None,
) -> FalsifierItem:
    """Gate: LiH VQE energy within 5e-3 Ha of PySCF CASCI (PRD §L1).

    Parameters
    ----------
    vqe_envelope:
        Envelope carrying an L1QuantumVqeOutput for LiH.
    ref_Ha:
        Override the CASCI reference. If None, uses the stored reference.
    """
    output = _extract_vqe_output(vqe_envelope)
    ref = ref_Ha if ref_Ha is not None else output.classical_reference_Ha
    delta = abs(output.ground_state_energy_Ha - ref)
    status = "pass" if delta <= _LIH_THRESHOLD_Ha else "fail"
    return FalsifierItem(
        name="l1.lih_vqe_vs_fci",
        threshold=f"<= {_LIH_THRESHOLD_Ha} Ha",
        actual=round(delta, 8),
        status=status,
    )


def quantum_slot_classical_simulation_only(envelope: Envelope) -> FalsifierItem:
    """Gate: quantum slot must NOT claim real hardware unless backend is approved.

    Passes when ``tool_adapter.backend`` is ``"stub"`` or ``"local_cpu"``
    (classical simulation). Fails if backend is ``"runpod_rest"`` but
    the engine does not carry the hardware tag (``"hardware"`` in engine name),
    indicating a misconfigured real-hardware claim.

    The rule: if you say ``runpod_rest`` but the engine is still a software
    simulator (``default.qubit``, ``statevector``, etc.), that is a false
    hardware claim and must fail.
    """
    adapter = envelope.tool_adapter
    backend = adapter.backend
    engine = adapter.engine.lower()

    is_hardware_backend = backend == "runpod_rest"
    is_software_engine = any(
        sw in engine
        for sw in ("default.qubit", "statevector", "lightning", "stub", "simulator")
    )

    if is_hardware_backend and is_software_engine:
        return FalsifierItem(
            name="quantum.slot_classical_simulation_only",
            threshold="runpod_rest backend requires hardware engine tag",
            actual={"backend": backend, "engine": adapter.engine},
            status="fail",
        )
    return FalsifierItem(
        name="quantum.slot_classical_simulation_only",
        threshold="classical simulation or approved hardware backend",
        actual={"backend": backend, "engine": adapter.engine},
        status="pass",
    )
