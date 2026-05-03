"""Plug-swap tests for L5 adapters — local_stub vs runpod_mock schema parity.

Verifies that all L5 adapters (FEniCSx, deal.II, OpenFOAM) produce
Envelope-valid output with the same wire-level top-level keys regardless
of the backend label.  This is the plug-replaceability acceptance test
per PRD §Architecture Invariant.
"""

from __future__ import annotations

import pytest

from zer0pa_materials_workbench.adapters.l5.base import L5ContinuumRequest
from zer0pa_materials_workbench.adapters.l5.dealii import DealIIStructuralAdapter
from zer0pa_materials_workbench.adapters.l5.fenicsx import FEniCSxContinuumAdapter
from zer0pa_materials_workbench.adapters.l5.openfoam import OpenFOAMProcessAdapter
from zer0pa_materials_workbench.envelope.envelope import Envelope
from zer0pa_materials_workbench.envelope.layer_outputs import L5ContinuumOutput

_REQ_STUB = L5ContinuumRequest(
    run_id="run:swap/l5/stub/001",
    candidate_id="candidate:Si:001",
    campaign_id="campaign:swap/001",
    rights_claim_id="rights:swap/001",
)
_REQ_MOCK = L5ContinuumRequest(
    run_id="run:swap/l5/runpod_mock/001",
    candidate_id="candidate:Si:001",
    campaign_id="campaign:swap/001",
    rights_claim_id="rights:swap/001",
)


class LocalStubRunner:
    """Runs L5 adapters in default stub mode."""
    def __init__(self, adapter_cls, **kwargs):
        self._adapter = adapter_cls(**kwargs)

    def run(self, request: L5ContinuumRequest) -> dict:
        return self._adapter.run(request)


class RunpodMockRunner:
    """Simulates a runpod_rest response by overriding the backend label."""
    def __init__(self, adapter_cls, **kwargs):
        self._adapter = adapter_cls(**kwargs)

    def run(self, request: L5ContinuumRequest) -> dict:
        result = self._adapter.run(request)
        result["tool_adapter"]["backend"] = "runpod_mock"
        return result


def _clean(env: dict) -> dict:
    """Strip private keys before Envelope validation."""
    return {k: v for k, v in env.items() if not k.startswith("_")}


# ---------------------------------------------------------------------------
# FEniCSx plug-swap
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def fenicsx_local():
    return LocalStubRunner(FEniCSxContinuumAdapter).run(_REQ_STUB)


@pytest.fixture(scope="module")
def fenicsx_mock():
    return RunpodMockRunner(FEniCSxContinuumAdapter).run(_REQ_MOCK)


class TestFEniCSxSchemaParity:
    def test_local_validates(self, fenicsx_local):
        env = Envelope.model_validate(_clean(fenicsx_local))
        assert env.layer == "L5"

    def test_mock_validates(self, fenicsx_mock):
        env = Envelope.model_validate(_clean(fenicsx_mock))
        assert env.layer == "L5"

    def test_same_top_level_keys(self, fenicsx_local, fenicsx_mock):
        local_keys = {k for k in fenicsx_local if not k.startswith("_")}
        mock_keys = {k for k in fenicsx_mock if not k.startswith("_")}
        assert local_keys == mock_keys

    def test_both_have_tensors(self, fenicsx_local, fenicsx_mock):
        assert "tensors" in fenicsx_local["output"]
        assert "tensors" in fenicsx_mock["output"]

    def test_output_validates_against_l5_schema(self, fenicsx_local):
        out = fenicsx_local["output"]
        # Strip private keys before validation.
        out_clean = {k: v for k, v in out.items() if not k.startswith("_")}
        L5ContinuumOutput.model_validate(out_clean)


# ---------------------------------------------------------------------------
# deal.II plug-swap
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def dealii_local():
    return LocalStubRunner(DealIIStructuralAdapter).run(_REQ_STUB)


@pytest.fixture(scope="module")
def dealii_mock():
    return RunpodMockRunner(DealIIStructuralAdapter).run(_REQ_MOCK)


class TestDealIISchemaParity:
    def test_local_validates(self, dealii_local):
        env = Envelope.model_validate(_clean(dealii_local))
        assert env.layer == "L5"

    def test_mock_validates(self, dealii_mock):
        env = Envelope.model_validate(_clean(dealii_mock))
        assert env.layer == "L5"

    def test_same_top_level_keys(self, dealii_local, dealii_mock):
        local_keys = {k for k in dealii_local if not k.startswith("_")}
        mock_keys = {k for k in dealii_mock if not k.startswith("_")}
        assert local_keys == mock_keys

    def test_disagree_field_present(self, dealii_local):
        assert "fenicsx_vs_dealii_strain_energy_disagreement_pct" in dealii_local["output"]


# ---------------------------------------------------------------------------
# OpenFOAM plug-swap
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def openfoam_local():
    return LocalStubRunner(OpenFOAMProcessAdapter).run(_REQ_STUB)


@pytest.fixture(scope="module")
def openfoam_mock():
    return RunpodMockRunner(OpenFOAMProcessAdapter).run(_REQ_MOCK)


class TestOpenFOAMSchemaParity:
    def test_local_validates(self, openfoam_local):
        env = Envelope.model_validate(_clean(openfoam_local))
        assert env.layer == "L5"

    def test_mock_validates(self, openfoam_mock):
        env = Envelope.model_validate(_clean(openfoam_mock))
        assert env.layer == "L5"

    def test_same_top_level_keys(self, openfoam_local, openfoam_mock):
        local_keys = {k for k in openfoam_local if not k.startswith("_")}
        mock_keys = {k for k in openfoam_mock if not k.startswith("_")}
        assert local_keys == mock_keys

    def test_poiseuille_field_present(self, openfoam_local):
        assert "openfoam_poiseuille_error_pct" in openfoam_local["output"]

    def test_mass_balance_field_present(self, openfoam_local):
        assert "cfd_mass_balance_error" in openfoam_local["output"]


# ---------------------------------------------------------------------------
# Cross-adapter schema uniformity (L5 output fields must match across adapters)
# ---------------------------------------------------------------------------

class TestCrossAdapterOutputUniformity:
    """All L5 adapters must produce the same top-level output field names."""

    REQUIRED_OUTPUT_FIELDS = {
        "tensors",
        "analytic_heat_slab_error",
        "elastic_patch_residual",
        "fenicsx_vs_dealii_strain_energy_disagreement_pct",
        "openfoam_poiseuille_error_pct",
        "cfd_mass_balance_error",
        "cfd_heat_balance_error",
        "artifact_uris",
    }

    def _run(self, adapter_cls, **kwargs):
        adapter = adapter_cls(**kwargs)
        return adapter.run(L5ContinuumRequest(
            run_id="run:swap/parity",
            candidate_id="candidate:parity",
            campaign_id="campaign:parity",
            rights_claim_id="rights:parity",
        ))

    def test_fenicsx_has_all_required_fields(self):
        env = self._run(FEniCSxContinuumAdapter)
        public_out = {k for k in env["output"] if not k.startswith("_")}
        assert self.REQUIRED_OUTPUT_FIELDS.issubset(public_out), (
            f"Missing: {self.REQUIRED_OUTPUT_FIELDS - public_out}"
        )

    def test_dealii_has_all_required_fields(self):
        env = self._run(DealIIStructuralAdapter)
        public_out = {k for k in env["output"] if not k.startswith("_")}
        assert self.REQUIRED_OUTPUT_FIELDS.issubset(public_out)

    def test_openfoam_has_all_required_fields(self):
        env = self._run(OpenFOAMProcessAdapter)
        public_out = {k for k in env["output"] if not k.startswith("_")}
        assert self.REQUIRED_OUTPUT_FIELDS.issubset(public_out)
