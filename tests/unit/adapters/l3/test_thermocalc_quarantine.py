"""Unit tests for ``ThermoCalcTdbReadOnlyAdapter`` (PRD §L3 quarantine).

Coverage:
    - Default-blocked: run() raises CommercialTdbQuarantineError
    - enable_with_customer_license requires customer URN starting with 'customer:'
    - After enable: reads TDB by hash; NEVER copies plaintext into output
    - Quarantine metadata block present and consistent
    - tdb_ref is hash:// URI (no plaintext leak)
    - disable() resets to blocked posture
    - Customer license proof URI recorded
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from zer0pa_materials_workbench.adapters.l3 import (
    CommercialTdbQuarantineError,
    L3CalphadRequest,
    ThermoCalcTdbReadOnlyAdapter,
)
from zer0pa_materials_workbench.envelope import Envelope, L3CalphadOutput
from zer0pa_materials_workbench.falsifiers.l3_falsifiers import tdb_quarantine_breach

REPO_ROOT = Path(__file__).resolve().parents[4]
CU_MG_TDB = REPO_ROOT / "fixtures" / "tdb" / "Cu-Mg-toy.tdb"


def _req(suffix: str = "001") -> L3CalphadRequest:
    return L3CalphadRequest(
        run_id=f"run:l3/quarantine/{suffix}",
        candidate_id=f"candidate:customer:{suffix}",
        campaign_id="campaign:customer-engagement/001",
        rights_claim_id="rights:customer-engagement/001",
        tdb_path=str(CU_MG_TDB),
    )


class TestDefaultBlocked:
    def test_default_disabled(self):
        adapter = ThermoCalcTdbReadOnlyAdapter()
        assert adapter.enabled is False

    def test_run_raises_quarantine_error(self):
        adapter = ThermoCalcTdbReadOnlyAdapter()
        with pytest.raises(CommercialTdbQuarantineError) as exc_info:
            adapter.run(_req())
        assert "BLOCKED" in str(exc_info.value)
        assert "enable_with_customer_license" in str(exc_info.value)

    def test_run_raises_with_no_tdb_path(self):
        adapter = ThermoCalcTdbReadOnlyAdapter()
        adapter.enable_with_customer_license(
            customer_id="customer:acme:001",
            license_proof_uri="https://acme.example.com/license-proof.pdf",
        )
        req = L3CalphadRequest(
            run_id="r", candidate_id="c", campaign_id="ca", rights_claim_id="ri",
            tdb_path=None,
        )
        with pytest.raises(CommercialTdbQuarantineError):
            adapter.run(req)

    def test_blocked_manifest_emitted_default(self):
        adapter = ThermoCalcTdbReadOnlyAdapter()
        manifests = adapter.blocked_manifests()
        assert len(manifests) >= 1
        m = manifests[0]
        assert "thermocalc" in m["source_manifest_id"].lower()


class TestEnableValidation:
    def test_customer_id_must_start_with_customer(self):
        adapter = ThermoCalcTdbReadOnlyAdapter()
        with pytest.raises(ValueError):
            adapter.enable_with_customer_license(
                customer_id="not-a-customer",
                license_proof_uri="https://example.com/proof",
            )

    def test_empty_license_proof_uri_raises(self):
        adapter = ThermoCalcTdbReadOnlyAdapter()
        with pytest.raises(ValueError):
            adapter.enable_with_customer_license(
                customer_id="customer:acme:001",
                license_proof_uri="",
            )

    def test_enabled_marker(self):
        adapter = ThermoCalcTdbReadOnlyAdapter()
        adapter.enable_with_customer_license(
            customer_id="customer:acme:001",
            license_proof_uri="https://acme.example.com/license.pdf",
        )
        assert adapter.enabled is True
        assert adapter.customer_id == "customer:acme:001"
        assert adapter.license_proof_uri == "https://acme.example.com/license.pdf"
        assert adapter.enabled_at is not None


class TestEnabledRun:
    @pytest.fixture
    def adapter(self) -> ThermoCalcTdbReadOnlyAdapter:
        a = ThermoCalcTdbReadOnlyAdapter()
        a.enable_with_customer_license(
            customer_id="customer:acme:001",
            license_proof_uri="https://acme.example.com/license-proof.pdf",
        )
        return a

    @pytest.fixture
    def envelope(self, adapter) -> dict:
        return adapter.run(_req())

    def test_envelope_returned(self, envelope):
        assert envelope["layer"] == "L3"

    def test_envelope_validates(self, envelope):
        clean = {k: v for k, v in envelope.items() if not k.startswith("_")}
        Envelope.model_validate(clean)

    def test_output_validates(self, envelope):
        L3CalphadOutput.model_validate(envelope["output"])

    def test_backend_is_local_cpu(self, envelope):
        # Envelope.Backend literal cannot carry 'thermo_calc_quarantined';
        # the quarantine discriminator lives in engine + _quarantine_meta.
        assert envelope["tool_adapter"]["backend"] == "local_cpu"

    def test_engine_marks_quarantined(self, envelope):
        assert "quarantined" in envelope["tool_adapter"]["engine"]
        assert "thermo-calc" in envelope["tool_adapter"]["engine"]

    def test_quarantine_meta_present(self, envelope):
        assert "_quarantine_meta" in envelope

    def test_redistributable_false(self, envelope):
        assert envelope["_quarantine_meta"]["redistributable"] is False

    def test_committed_to_repo_false(self, envelope):
        assert envelope["_quarantine_meta"]["committed_to_repo"] is False

    def test_included_in_training_corpus_false(self, envelope):
        assert envelope["_quarantine_meta"]["included_in_training_corpus"] is False

    def test_customer_id_propagated(self, envelope):
        assert envelope["_quarantine_meta"]["customer_id"] == "customer:acme:001"

    def test_license_proof_uri_propagated(self, envelope):
        assert "license-proof.pdf" in envelope["_quarantine_meta"]["license_proof_uri"]

    def test_tdb_hash_recorded(self, envelope):
        h = envelope["_quarantine_meta"]["tdb_hash"]
        assert h.startswith("sha256:")

    def test_tdb_size_recorded(self, envelope):
        assert envelope["_quarantine_meta"]["tdb_size_bytes"] > 0


class TestNoPlaintextLeakage:
    """Critical: TDB plaintext content MUST NOT leak into outputs."""

    @pytest.fixture
    def envelope(self) -> dict:
        adapter = ThermoCalcTdbReadOnlyAdapter()
        adapter.enable_with_customer_license(
            customer_id="customer:acme:001",
            license_proof_uri="https://acme.example.com/license-proof.pdf",
        )
        return adapter.run(_req())

    def test_tdb_ref_is_hash_uri(self, envelope):
        assert envelope["output"]["tdb_ref"].startswith("hash://")

    def test_tdb_ref_does_not_contain_path(self, envelope):
        # tdb_ref must NOT echo a filesystem path or a URL the operator
        # could use to refetch the file.
        ref = envelope["output"]["tdb_ref"]
        assert "/" not in ref.split("hash://")[1]  # No path separators after hash:
        assert "Cu-Mg-toy.tdb" not in ref

    def test_phase_fraction_posterior_empty(self, envelope):
        # Quarantine adapter doesn't compute equilibrium — no plaintext data.
        assert envelope["output"]["phase_fraction_posterior"] == {}

    def test_espei_diagnostics_did_not_run(self, envelope):
        diags = envelope["output"]["espei_diagnostics"]
        assert diags["ran"] is False

    def test_envelope_serialises_without_tdb_text(self, envelope):
        # Round-trip through JSON. The serialised form MUST NOT contain
        # CALPHAD parameter text like '+12964.84-9.452*T+GHSERCU'.
        as_json = json.dumps(envelope, default=str)
        assert "+12964.84-9.452*T" not in as_json
        assert "GHSERCU" not in as_json
        assert "PARAMETER G(LIQUID" not in as_json

    def test_phase_names_metadata_only(self, envelope):
        # Phase names (LIQUID, FCC_A1, etc.) ARE allowed — they're
        # CALPHAD nomenclature, not commercial content.
        phases = envelope["output"]["equilibrium_phases"]
        assert all(isinstance(p, str) and len(p) < 30 for p in phases)


class TestQuarantineBreachFalsifier:
    """The tdb_quarantine_breach falsifier passes for a clean envelope."""

    def test_clean_envelope_passes(self):
        adapter = ThermoCalcTdbReadOnlyAdapter()
        adapter.enable_with_customer_license(
            customer_id="customer:acme:001",
            license_proof_uri="https://acme.example.com/license-proof.pdf",
        )
        envelope = adapter.run(_req())
        result = tdb_quarantine_breach(envelope)
        assert result.status == "pass"

    def test_envelope_with_redistributable_true_fails(self):
        adapter = ThermoCalcTdbReadOnlyAdapter()
        adapter.enable_with_customer_license(
            customer_id="customer:acme:001",
            license_proof_uri="https://acme.example.com/license-proof.pdf",
        )
        envelope = adapter.run(_req())
        # Tamper.
        envelope["_quarantine_meta"]["redistributable"] = True
        result = tdb_quarantine_breach(envelope)
        assert result.status == "fail"

    def test_envelope_with_committed_true_fails(self):
        adapter = ThermoCalcTdbReadOnlyAdapter()
        adapter.enable_with_customer_license(
            customer_id="customer:acme:001",
            license_proof_uri="https://acme.example.com/license-proof.pdf",
        )
        envelope = adapter.run(_req())
        envelope["_quarantine_meta"]["committed_to_repo"] = True
        result = tdb_quarantine_breach(envelope)
        assert result.status == "fail"

    def test_envelope_with_training_corpus_true_fails(self):
        adapter = ThermoCalcTdbReadOnlyAdapter()
        adapter.enable_with_customer_license(
            customer_id="customer:acme:001",
            license_proof_uri="https://acme.example.com/license-proof.pdf",
        )
        envelope = adapter.run(_req())
        envelope["_quarantine_meta"]["included_in_training_corpus"] = True
        result = tdb_quarantine_breach(envelope)
        assert result.status == "fail"


class TestDisable:
    def test_disable_resets(self):
        adapter = ThermoCalcTdbReadOnlyAdapter()
        adapter.enable_with_customer_license(
            customer_id="customer:acme:001",
            license_proof_uri="https://acme.example.com/license.pdf",
        )
        assert adapter.enabled
        adapter.disable()
        assert adapter.enabled is False
        assert adapter.customer_id is None
        assert adapter.license_proof_uri is None

    def test_run_after_disable_raises(self):
        adapter = ThermoCalcTdbReadOnlyAdapter()
        adapter.enable_with_customer_license(
            customer_id="customer:acme:001",
            license_proof_uri="https://acme.example.com/license.pdf",
        )
        adapter.disable()
        with pytest.raises(CommercialTdbQuarantineError):
            adapter.run(_req())


class TestEnabledBlockedManifest:
    def test_enabled_manifest_records_customer(self):
        adapter = ThermoCalcTdbReadOnlyAdapter()
        adapter.enable_with_customer_license(
            customer_id="customer:acme:001",
            license_proof_uri="https://acme.example.com/license.pdf",
        )
        manifests = adapter.blocked_manifests()
        assert len(manifests) == 1
        m = manifests[0]
        assert "customer:acme:001" in m["source_manifest_id"]
        assert m["blocker_reason"] == "policy"
