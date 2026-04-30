"""Plug-swap test: PySCF and QE produce envelopes with matching schemas.

The plug-swap invariant (PRD §Plug-replaceability acceptance test):
    Two adapters for the same layer MUST produce envelopes whose ``output``
    field validates against the same schema (L1DftOutput).
"""

from __future__ import annotations

import pytest

from zer0pa_materials.adapters.l1.pyscf import PyScfMolecularSolver
from zer0pa_materials.adapters.l1.qe_aiida import QuantumEspressoAiiDASolver
from zer0pa_materials.adapters.l1.cp2k_aiida import Cp2kAiiDASolver
from zer0pa_materials.adapters.l1.abinit_aiida import AbinitAiiDASolver
from zer0pa_materials.adapters.l1.base import L1JobParams
from zer0pa_materials.envelope import L1DftOutput, Envelope, cif_hash_from_text

from zer0pa_materials import read_fixture

H2_CIF = read_fixture("structures", "H2", "structure.cif")
H2_HASH = cif_hash_from_text(H2_CIF)

ADAPTERS = [
    PyScfMolecularSolver,
    QuantumEspressoAiiDASolver,
    Cp2kAiiDASolver,
    AbinitAiiDASolver,
]


@pytest.fixture(params=ADAPTERS, ids=[a.__name__ for a in ADAPTERS])
def adapter(request):
    return request.param()


@pytest.fixture
def h2_params() -> L1JobParams:
    return L1JobParams(
        structure_cif=H2_CIF,
        structure_hash=H2_HASH,
        campaign_id="campaign:plug-swap-l1",
        candidate_id="candidate:plug-swap-h2",
    )


def test_all_adapters_return_envelope(adapter, h2_params: L1JobParams) -> None:
    envelope = adapter.submit_job(H2_CIF, h2_params)
    assert isinstance(envelope, Envelope)


def test_all_adapters_layer_is_l1(adapter, h2_params: L1JobParams) -> None:
    envelope = adapter.submit_job(H2_CIF, h2_params)
    assert envelope.layer == "L1"


def test_all_adapters_output_validates_l1dftoutput(adapter, h2_params: L1JobParams) -> None:
    """The plug-swap invariant: output must validate as L1DftOutput."""
    envelope = adapter.submit_job(H2_CIF, h2_params)
    output = L1DftOutput.model_validate(envelope.output)
    assert output is not None


def test_all_adapters_output_has_required_fields(adapter, h2_params: L1JobParams) -> None:
    envelope = adapter.submit_job(H2_CIF, h2_params)
    output = L1DftOutput.model_validate(envelope.output)
    assert output.code in ("PySCF", "QE", "CP2K", "ABINIT", "GPU4PySCF")
    assert isinstance(output.total_energy_eV, float)
    assert output.total_energy_eV < 0.0
    assert output.force_rmse_eV_per_Ang >= 0.0
    assert len(output.kpoint_mesh) == 3


def test_all_adapters_have_audit_hashes(adapter, h2_params: L1JobParams) -> None:
    import re
    envelope = adapter.submit_job(H2_CIF, h2_params)
    assert re.match(r"sha256:[0-9a-f]{64}", envelope.audit.input_hash)
    assert re.match(r"sha256:[0-9a-f]{64}", envelope.audit.output_hash)


def test_all_adapters_have_boundary(adapter, h2_params: L1JobParams) -> None:
    from zer0pa_materials.boundary import RESEARCH_BOUNDARY
    envelope = adapter.submit_job(H2_CIF, h2_params)
    assert envelope.research_boundary == RESEARCH_BOUNDARY


def test_all_adapters_rights_block_present(adapter, h2_params: L1JobParams) -> None:
    envelope = adapter.submit_job(H2_CIF, h2_params)
    assert envelope.rights.rights_claim_id.startswith("rights:")
    assert envelope.rights.reuse_scope in ("tenant_only", "shared_learning", "open_science")
