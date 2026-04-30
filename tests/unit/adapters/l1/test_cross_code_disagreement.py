"""Tests for cross_code_disagreement — two L1 envelopes for Si, DisagreementMetric emitted."""

from __future__ import annotations

import pytest

from zer0pa_materials.adapters.l1.qe_aiida import QuantumEspressoAiiDASolver
from zer0pa_materials.adapters.l1.cp2k_aiida import Cp2kAiiDASolver
from zer0pa_materials.adapters.l1.abinit_aiida import AbinitAiiDASolver
from zer0pa_materials.adapters.l1.base import L1JobParams
from zer0pa_materials.envelope import L1DftOutput, cif_hash_from_text
from zer0pa_materials.falsifiers.l1_falsifiers import cross_code_disagreement, _SCREENING_THRESHOLD_MEV

SI_CIF = open("/Users/zer0palab/Materials Pipeline/fixtures/structures/Si/structure.cif").read()


@pytest.fixture
def si_params() -> L1JobParams:
    return L1JobParams(
        structure_cif=SI_CIF,
        structure_hash=cif_hash_from_text(SI_CIF),
        campaign_id="campaign:test-cross-code",
        candidate_id="candidate:test-si",
    )


@pytest.fixture
def qe_envelope(si_params: L1JobParams):
    return QuantumEspressoAiiDASolver().submit_job(SI_CIF, si_params)


@pytest.fixture
def cp2k_envelope(si_params: L1JobParams):
    return Cp2kAiiDASolver().submit_job(SI_CIF, si_params)


@pytest.fixture
def abinit_envelope(si_params: L1JobParams):
    return AbinitAiiDASolver().submit_job(SI_CIF, si_params)


def test_cross_code_returns_falsifier_and_metric(qe_envelope, cp2k_envelope) -> None:
    item, metric = cross_code_disagreement([qe_envelope, cp2k_envelope])
    from zer0pa_materials.envelope import FalsifierItem, DisagreementMetric
    assert isinstance(item, FalsifierItem)
    assert isinstance(metric, DisagreementMetric)


def test_falsifier_name(qe_envelope, cp2k_envelope) -> None:
    item, _ = cross_code_disagreement([qe_envelope, cp2k_envelope])
    assert item.name == "l1.cross_code_disagreement"


def test_disagreement_metric_unit(qe_envelope, cp2k_envelope) -> None:
    _, metric = cross_code_disagreement([qe_envelope, cp2k_envelope])
    assert metric.unit == "meV/f.u."


def test_disagreement_metric_value_is_float(qe_envelope, cp2k_envelope) -> None:
    _, metric = cross_code_disagreement([qe_envelope, cp2k_envelope])
    assert isinstance(metric.value, float)
    assert metric.value >= 0.0


def test_disagreement_metric_references_contain_codes(qe_envelope, cp2k_envelope) -> None:
    _, metric = cross_code_disagreement([qe_envelope, cp2k_envelope])
    refs = " ".join(metric.references)
    assert "QE" in refs or "CP2K" in refs


def test_three_code_disagreement(qe_envelope, cp2k_envelope, abinit_envelope) -> None:
    """Three adapters: disagreement is range of all three energies."""
    item, metric = cross_code_disagreement([qe_envelope, cp2k_envelope, abinit_envelope])
    assert metric.value >= 0.0
    assert len(metric.references) == 3


def test_single_envelope_returns_blocked() -> None:
    qe = QuantumEspressoAiiDASolver()
    params = L1JobParams(
        structure_cif=SI_CIF,
        structure_hash=cif_hash_from_text(SI_CIF),
        campaign_id="campaign:test-single",
        candidate_id="candidate:test-single",
    )
    envelope = qe.submit_job(SI_CIF, params)
    item, metric = cross_code_disagreement([envelope])
    assert item.status == "blocked"


def test_empty_list_returns_blocked() -> None:
    item, metric = cross_code_disagreement([])
    assert item.status == "blocked"


def test_stub_adapters_disagree_in_energy(qe_envelope, cp2k_envelope) -> None:
    """QE and CP2K stubs have different synthetic energies — ensures non-zero disagreement."""
    qe_out = L1DftOutput.model_validate(qe_envelope.output)
    cp2k_out = L1DftOutput.model_validate(cp2k_envelope.output)
    assert qe_out.total_energy_eV != cp2k_out.total_energy_eV


def test_disagreement_falsifier_pass_for_small_delta() -> None:
    """When energies agree to within 50 meV, status is pass."""
    # Construct two envelopes with identical energies
    from zer0pa_materials.adapters.l1.qe_aiida import QuantumEspressoAiiDASolver
    from zer0pa_materials.envelope import Envelope
    params = L1JobParams(
        structure_cif=SI_CIF,
        structure_hash=cif_hash_from_text(SI_CIF),
        campaign_id="campaign:test-agree",
        candidate_id="candidate:test-agree",
    )
    e1 = QuantumEspressoAiiDASolver().submit_job(SI_CIF, params)
    # Clone envelope with same energy (same adapter)
    e2 = QuantumEspressoAiiDASolver().submit_job(SI_CIF, params)
    item, _ = cross_code_disagreement([e1, e2])
    # Two identical adapters → zero disagreement → pass
    assert item.status == "pass"
