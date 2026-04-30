"""Falsification wave: DFT convergence failure scenarios.

These tests deliberately trigger the L1 convergence gates and verify
that the falsifier correctly raises FAIL / BLOCKED status.
"""

from __future__ import annotations

import pytest

from zer0pa_materials.adapters.l1.pyscf import PyScfMolecularSolver
from zer0pa_materials.adapters.l1.base import L1JobParams
from zer0pa_materials.envelope import L1DftOutput, cif_hash_from_text
from zer0pa_materials.falsifiers.l1_falsifiers import (
    convergence_delta_screening_threshold,
    convergence_delta_publication_threshold,
    force_threshold_check,
    cross_code_disagreement,
)

H2_CIF = open("/Users/zer0palab/Materials Pipeline/fixtures/structures/H2/structure.cif").read()


def _output_with_delta(delta: float | None, force: float = 0.001) -> L1DftOutput:
    return L1DftOutput(
        code="PySCF",
        functional="PBE",
        total_energy_eV=-31.6,
        force_rmse_eV_per_Ang=force,
        kpoint_mesh=[1, 1, 1],
        convergence_delta_meV_per_atom=delta,
        publication_grade=True,
    )


# ---------------------------------------------------------------------------
# SCREENING threshold failures
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("delta", [50.0, 51.0, 75.0, 100.0, 200.0])
def test_screening_fails_for_large_delta(delta: float) -> None:
    output = _output_with_delta(delta)
    item = convergence_delta_screening_threshold(output)
    assert item.status == "fail", f"Expected fail for delta={delta}, got {item.status}"


@pytest.mark.parametrize("delta", [0.0, 1.0, 10.0, 49.0, 49.9])
def test_screening_passes_for_small_delta(delta: float) -> None:
    output = _output_with_delta(delta)
    item = convergence_delta_screening_threshold(output)
    assert item.status == "pass", f"Expected pass for delta={delta}"


def test_screening_blocked_for_none_delta() -> None:
    output = _output_with_delta(None)
    item = convergence_delta_screening_threshold(output)
    assert item.status == "blocked"


# ---------------------------------------------------------------------------
# PUBLICATION threshold failures
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("delta", [5.1, 6.0, 10.0, 50.0])
def test_publication_fails_for_large_delta(delta: float) -> None:
    output = _output_with_delta(delta)
    item = convergence_delta_publication_threshold(output)
    assert item.status == "fail"


@pytest.mark.parametrize("delta", [0.0, 1.0, 4.9, 5.0])
def test_publication_passes_for_small_delta(delta: float) -> None:
    output = _output_with_delta(delta)
    item = convergence_delta_publication_threshold(output)
    assert item.status == "pass"


# ---------------------------------------------------------------------------
# FORCE threshold failures
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("force", [0.06, 0.1, 0.5, 1.0])
def test_force_fails_above_default(force: float) -> None:
    output = _output_with_delta(10.0, force=force)
    item = force_threshold_check(output, threshold_eV_per_Ang=0.05)
    assert item.status == "fail"


@pytest.mark.parametrize("force", [0.0, 0.01, 0.049, 0.05])
def test_force_passes_at_or_below_default(force: float) -> None:
    output = _output_with_delta(10.0, force=force)
    item = force_threshold_check(output, threshold_eV_per_Ang=0.05)
    assert item.status == "pass"


# ---------------------------------------------------------------------------
# Cross-code disagreement gate (negative: large disagreement)
# ---------------------------------------------------------------------------

def test_cross_code_disagreement_fails_for_large_energy_spread() -> None:
    """Manually construct two envelopes with large energy difference."""
    from zer0pa_materials.adapters.l1.qe_aiida import QuantumEspressoAiiDASolver
    from zer0pa_materials.envelope import (
        Envelope, AuditBlock, RightsBlock, ToolAdapter, sha256_of, canonical_json_bytes
    )
    from zer0pa_materials.boundary import RESEARCH_BOUNDARY

    def _envelope(energy_eV: float, code: str) -> Envelope:
        output = L1DftOutput(
            code=code,  # type: ignore
            functional="PBE",
            total_energy_eV=energy_eV,
            force_rmse_eV_per_Ang=0.001,
            kpoint_mesh=[1, 1, 1],
        )
        out_dict = output.model_dump(mode="json")
        return Envelope(
            research_boundary=RESEARCH_BOUNDARY,
            run_id="run:disagree:000001",
            campaign_id="campaign:test-disagree",
            candidate_id="candidate:test-disagree",
            layer="L1",
            tool_adapter=ToolAdapter(
                name="TestAdapter",
                version="0.1.0",
                backend="stub",  # type: ignore
                engine=code,
            ),
            output=out_dict,
            audit=AuditBlock(
                audit_record_id="audit:disagree:000001",
                input_hash=sha256_of(canonical_json_bytes({"code": code})),
                output_hash=sha256_of(canonical_json_bytes(out_dict)),
            ),
            rights=RightsBlock(
                rights_claim_id="rights:disagree:000001",
                reuse_scope="tenant_only",
            ),
        )

    # 200 meV difference (well above 50 meV screening threshold)
    e1 = _envelope(-100.0, "QE")
    e2 = _envelope(-100.2, "CP2K")  # -100.2 - (-100.0) = -0.2 eV = 200 meV

    item, metric = cross_code_disagreement([e1, e2])
    assert item.status == "fail"
    assert metric.value > 50.0  # > 50 meV threshold


def test_cross_code_disagreement_passes_for_small_spread() -> None:
    """Two envelopes with same energy → pass."""
    from zer0pa_materials.envelope import (
        Envelope, AuditBlock, RightsBlock, ToolAdapter, sha256_of, canonical_json_bytes
    )
    from zer0pa_materials.boundary import RESEARCH_BOUNDARY

    def _envelope(energy_eV: float) -> Envelope:
        output = L1DftOutput(
            code="QE",
            functional="PBE",
            total_energy_eV=energy_eV,
            force_rmse_eV_per_Ang=0.001,
            kpoint_mesh=[1, 1, 1],
        )
        out_dict = output.model_dump(mode="json")
        return Envelope(
            research_boundary=RESEARCH_BOUNDARY,
            run_id="run:agree:000001",
            campaign_id="campaign:test-agree",
            candidate_id="candidate:test-agree",
            layer="L1",
            tool_adapter=ToolAdapter(
                name="TestAdapter",
                version="0.1.0",
                backend="stub",  # type: ignore
                engine="QE",
            ),
            output=out_dict,
            audit=AuditBlock(
                audit_record_id="audit:agree:000001",
                input_hash=sha256_of(canonical_json_bytes({"energy": energy_eV})),
                output_hash=sha256_of(canonical_json_bytes(out_dict)),
            ),
            rights=RightsBlock(
                rights_claim_id="rights:agree:000001",
                reuse_scope="tenant_only",
            ),
        )

    e1 = _envelope(-31.6)
    e2 = _envelope(-31.601)  # 1 meV difference → pass
    item, metric = cross_code_disagreement([e1, e2])
    assert item.status == "pass"
    assert metric.value < 50.0
