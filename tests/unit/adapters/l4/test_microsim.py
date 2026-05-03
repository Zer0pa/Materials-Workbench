"""Unit tests for MicrosimGrandPotentialAdapter — GPL-3 SUBPROCESS QUARANTINE."""

from __future__ import annotations

import pytest

from zer0pa_materials_workbench.adapters.l4.base import L4PredictRequest
from zer0pa_materials_workbench.adapters.l4.contracts import (
    PhaseFieldDomain,
    PhaseFieldMaterial,
    PhaseFieldMesh,
    PhaseFieldRunSpec,
)
from zer0pa_materials_workbench.adapters.l4.microsim import MicrosimGrandPotentialAdapter
from zer0pa_materials_workbench.boundary import RESEARCH_BOUNDARY
from zer0pa_materials_workbench.envelope.envelope import Envelope


@pytest.fixture
def adapter():
    return MicrosimGrandPotentialAdapter()


@pytest.fixture
def request_obj():
    return L4PredictRequest(
        run_id="run:test/microsim/001",
        candidate_id="candidate:test/001",
        campaign_id="campaign:test/001",
        rights_claim_id="rights:test/001",
    )


@pytest.fixture
def grand_potential_spec():
    return PhaseFieldRunSpec(
        equation="grand_potential",
        domain=PhaseFieldDomain(dimension=2, extents=[10.0, 10.0], units="nm"),
        mesh=PhaseFieldMesh(nodes=[10, 10]),
        materials=[PhaseFieldMaterial(phase_name="alpha", initial_fraction=0.5)],
        time_steps=5,
        dt=0.01,
        n_dumps=4,
    )


class TestMicrosimShape:
    def test_layer_is_L4(self, adapter, grand_potential_spec, request_obj):
        result = adapter.run(grand_potential_spec, request_obj)
        assert result["layer"] == "L4"

    def test_envelope_validates(self, adapter, grand_potential_spec, request_obj):
        result = adapter.run(grand_potential_spec, request_obj)
        clean = {k: v for k, v in result.items() if not k.startswith("_")}
        env = Envelope.model_validate(clean)
        assert env.layer == "L4"

    def test_boundary_verbatim(self, adapter, grand_potential_spec, request_obj):
        result = adapter.run(grand_potential_spec, request_obj)
        assert result["research_boundary"] == RESEARCH_BOUNDARY


class TestSubprocessIsolationContract:
    """PRD §L4: MICROSIM is treated as GPL-3 subprocess/container until
    license review says otherwise."""

    def test_class_isolation_mode_is_subprocess(self, adapter):
        assert adapter.ISOLATION_MODE == "subprocess"

    def test_envelope_records_isolation_mode(self, adapter, grand_potential_spec, request_obj):
        result = adapter.run(grand_potential_spec, request_obj)
        assert result["_l4_meta"]["isolation_mode"] == "subprocess"

    def test_engine_label_microsim(self, adapter, grand_potential_spec, request_obj):
        result = adapter.run(grand_potential_spec, request_obj)
        assert "MICROSIM" in result["tool_adapter"]["engine"]

    def test_license_recorded(self, adapter, grand_potential_spec, request_obj):
        result = adapter.run(grand_potential_spec, request_obj)
        license_str = result["_l4_meta"]["license"]
        assert "GPL-3" in license_str

    def test_invalid_isolation_mode_raises(self, request_obj, grand_potential_spec):
        """If a future code change breaks the subprocess invariant, the run
        MUST raise instead of silently violating GPL-3 quarantine."""
        adapter_local = MicrosimGrandPotentialAdapter()
        # Force a violation by setting ISOLATION_MODE to something illegal
        adapter_local.ISOLATION_MODE = "in_process"  # type: ignore[assignment]
        with pytest.raises(RuntimeError, match="GPL-3 quarantine"):
            adapter_local.run(grand_potential_spec, request_obj)


class TestMassDriftConservation:
    def test_mass_drift_below_threshold(self, adapter, grand_potential_spec, request_obj):
        result = adapter.run(grand_potential_spec, request_obj)
        drift = result["output"]["cahn_hilliard_mass_drift"]
        assert drift is not None
        assert drift < 1e-3


class TestBlockedManifest:
    def test_microsim_blocked_manifest(self, adapter):
        manifests = adapter.blocked_manifests()
        ids = [m["source_manifest_id"] for m in manifests]
        assert "src:microsim:cxx-build" in ids

    def test_blocker_reason_is_license(self, adapter):
        manifests = adapter.blocked_manifests()
        for m in manifests:
            if m["source_manifest_id"] == "src:microsim:cxx-build":
                assert m["blocker_reason"] == "license_unverified"
                assert "GPL-3" in m["blocker_detail"]


class TestNoMicrosimImport:
    """MICROSIM modules MUST NOT be importable from the adapter module
    (subprocess quarantine)."""

    def test_no_microsim_import_in_adapter_source(self):
        from pathlib import Path

        adapter_path = Path(__file__).parent.parent.parent.parent.parent / "src" / "zer0pa_materials_workbench" / "adapters" / "l4" / "microsim.py"
        text = adapter_path.read_text()
        # Must not have ``import microsim`` or similar
        assert "import microsim" not in text.lower()
        assert "from microsim" not in text.lower()
