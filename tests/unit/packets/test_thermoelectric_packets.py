"""Thermoelectric sidecar packets — Si, Bi2Te3, PbTe, SnSe.

Boundary
--------
Research infrastructure for in silico materials science discovery. Outputs are
research artifacts. No regulatory certification claims. No clinical or
human-subject use. ITAR / weapons applications are out of scope (Meta UMA
Acceptable Use Policy and operator policy).

Per ``phases/L1.5-phonon/PHASE-REPORT.md``, the L1.5 ZT rank-stability gate
correctly fires on stub data (BoltzTraP2 vs AMSET disagreement above 15%):
"This is the intended behaviour for the sidecar falsifier. Real DFT-driven
calculations with proper temperature-dependent scattering rates will produce
tighter agreement."

Therefore in stub mode every thermoelectric packet records ``decision=reject``;
the validator reports overall=pass because the packet itself is well-formed,
the rejection mechanism is shown transparently (zt_rank_stable=False, gate
threshold = 15%), and the publishable target is set.
"""

from __future__ import annotations

import pytest

from zer0pa_materials_workbench.packets import (
    assemble_thermoelectric_packet,
    validate_evidence_packet,
)
from zer0pa_materials_workbench.packets.validators import THERMOELECTRIC_REQUIRED_SECTIONS


@pytest.mark.parametrize("fixture", ["Si", "Bi2Te3", "PbTe", "SnSe"])
def test_thermoelectric_packet_assembles(fixture: str) -> None:
    """Each thermoelectric fixture produces a valid packet."""
    packet = assemble_thermoelectric_packet(fixture)
    assert packet.objective == "thermoelectric_zt"
    assert packet.candidate_id == f"candidate:thermoelectric:{fixture}"
    assert "zt_assembly" in packet.bundle.sections


@pytest.mark.parametrize("fixture", ["Si", "Bi2Te3", "PbTe", "SnSe"])
def test_thermoelectric_packet_required_sections(fixture: str) -> None:
    """Every required thermoelectric section is present (NO ionic, NO L4)."""
    packet = assemble_thermoelectric_packet(fixture)
    for required in THERMOELECTRIC_REQUIRED_SECTIONS:
        assert required in packet.bundle.sections, f"missing {required}"
    # No ionic / L3 / L4 / AlabOS sections in thermoelectric.
    assert "ionic_transport_full_evidence" not in packet.bundle.sections
    assert "alabos_recipe_only_protocol" not in packet.bundle.sections
    assert "l3_calphad_phase_set_posterior" not in packet.bundle.sections


@pytest.mark.parametrize("fixture", ["Si", "Bi2Te3", "PbTe", "SnSe"])
def test_thermoelectric_validation_overall_pass(fixture: str) -> None:
    """Packet itself passes the validator suite (decision separate)."""
    packet = assemble_thermoelectric_packet(fixture)
    report = validate_evidence_packet(packet)
    assert report.overall_status == "pass"


@pytest.mark.parametrize("fixture", ["Si", "Bi2Te3", "PbTe", "SnSe"])
def test_thermoelectric_zt_rank_stability_gate_fires_in_stub_mode(fixture: str) -> None:
    """Stub-mode ZT rank-stability gate correctly fires (per L1.5 phase report)."""
    packet = assemble_thermoelectric_packet(fixture)
    zt_section = packet.bundle.section("zt_assembly")
    assert zt_section is not None
    assert zt_section.raw_payload["zt_rank_stable"] is False
    assert zt_section.raw_payload["zt_fractional_disagreement"] > 0.15
    # Decision must be reject when rank-stability fails.
    assert packet.promotion_decision == "reject"


def test_bi2te3_journal_target() -> None:
    """Bi2Te3 default journal target is npj Comp Mat / J. Mater. Chem. A."""
    packet = assemble_thermoelectric_packet("Bi2Te3")
    target = packet.publishable_paper_target
    assert target.primary_journal == "npj Computational Materials"
    assert target.alternative_journal == "J. Mater. Chem. A"


def test_snse_journal_target() -> None:
    """SnSe targets Nature Materials (record ZT 2.6)."""
    packet = assemble_thermoelectric_packet("SnSe")
    target = packet.publishable_paper_target
    assert target.primary_journal == "Nature Materials"
