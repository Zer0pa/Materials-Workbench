"""Tests for QuantumProblemDispatcher — slot routing and graceful failure."""

from __future__ import annotations

import pytest

from zer0pa_materials.adapters.quantum.dispatcher import QuantumProblemDispatcher
from zer0pa_materials.envelope import Envelope, L1QuantumVqeOutput


@pytest.fixture
def dispatcher() -> QuantumProblemDispatcher:
    return QuantumProblemDispatcher()


def test_l1_vqe_h2_returns_envelope(dispatcher: QuantumProblemDispatcher) -> None:
    envelope = dispatcher.dispatch(slot="L1-VQE", system="H2")
    assert isinstance(envelope, Envelope)
    assert envelope.layer == "L1"


def test_l1_vqe_lih_returns_envelope(dispatcher: QuantumProblemDispatcher) -> None:
    envelope = dispatcher.dispatch(slot="L1-VQE", system="LiH")
    assert isinstance(envelope, Envelope)
    output = L1QuantumVqeOutput.model_validate(envelope.output)
    assert output.system == "LiH"


def test_l1_vqe_with_custom_bond_ang(dispatcher: QuantumProblemDispatcher) -> None:
    envelope = dispatcher.dispatch(slot="L1-VQE", system="H2", bond_ang=0.80)
    assert isinstance(envelope, Envelope)


def test_l4_qaoa_raises_not_implemented(dispatcher: QuantumProblemDispatcher) -> None:
    with pytest.raises(NotImplementedError) as exc_info:
        dispatcher.dispatch(slot="L4-QAOA", system="H2")
    assert "L4-QAOA" in str(exc_info.value)


def test_l7_qaa_raises_not_implemented(dispatcher: QuantumProblemDispatcher) -> None:
    with pytest.raises(NotImplementedError) as exc_info:
        dispatcher.dispatch(slot="L7-QAA", system="H2")
    assert "L7-QAA" in str(exc_info.value)


def test_unknown_slot_raises_value_error(dispatcher: QuantumProblemDispatcher) -> None:
    with pytest.raises(ValueError, match="Unknown quantum slot"):
        dispatcher.dispatch(slot="L99-UNKNOWN", system="H2")  # type: ignore


def test_unknown_system_raises_value_error(dispatcher: QuantumProblemDispatcher) -> None:
    with pytest.raises(ValueError, match="L1-VQE supports"):
        dispatcher.dispatch(slot="L1-VQE", system="CH4")


def test_blocked_manifests_for_unimplemented_slots(dispatcher: QuantumProblemDispatcher) -> None:
    manifests = dispatcher.blocked_manifests
    assert "L4-QAOA" in manifests
    assert "L7-QAA" in manifests


def test_l4_blocked_manifest_id(dispatcher: QuantumProblemDispatcher) -> None:
    m = dispatcher.blocked_manifests["L4-QAOA"]
    assert "l4-qaoa" in m.source_manifest_id.lower() or "l4" in m.source_manifest_id.lower()


def test_l7_blocked_manifest_id(dispatcher: QuantumProblemDispatcher) -> None:
    m = dispatcher.blocked_manifests["L7-QAA"]
    assert "l7-qaa" in m.source_manifest_id.lower() or "l7" in m.source_manifest_id.lower()


def test_l4_blocked_reason_is_other(dispatcher: QuantumProblemDispatcher) -> None:
    m = dispatcher.blocked_manifests["L4-QAOA"]
    # "other" is the correct BlockerReason for unimplemented slots (schema has no "not_implemented")
    assert m.blocker_reason == "other"


def test_l1_vqe_envelope_passes_falsifier_gate(dispatcher: QuantumProblemDispatcher) -> None:
    from zer0pa_materials.falsifiers.quantum_falsifiers import vqe_h2_classical_match
    envelope = dispatcher.dispatch(slot="L1-VQE", system="H2")
    item = vqe_h2_classical_match(envelope)
    assert item.status == "pass"
