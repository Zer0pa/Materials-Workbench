"""Li6PS5Cl battery packet — correctly REJECTS on the oxidation gate.

Boundary
--------
Research infrastructure for in silico materials science discovery. Outputs are
research artifacts. No regulatory certification claims. No clinical or
human-subject use. ITAR / weapons applications are out of scope (Meta UMA
Acceptable Use Policy and operator policy).

Discipline (RESISTANCE.md "Calibrated uncertainty"): the Li6PS5Cl rejection is
part of the publishable claim. The packet must show the rejection mechanism
transparently — which gate fired, what threshold, what evidence. Per
``phases/Ionic-transport/PHASE-REPORT.md``: "Li6PS5Cl is a borderline candidate
that cannot pass the cathode-side oxidation gate without a cathode coating
that is out of scope for this wave."
"""

from __future__ import annotations

from zer0pa_materials_workbench.packets import (
    assemble_battery_packet,
    validate_evidence_packet,
)


def test_li6ps5cl_packet_rejects_in_li_metal_mode() -> None:
    """Li6PS5Cl rejects on the oxidation gate in default li_metal mode."""
    packet = assemble_battery_packet("Li6PS5Cl", interface_mode="li_metal")
    assert packet.promotion_decision == "reject"
    assert "PRD §Ionic Transport gates failed" in packet.promotion_rationale


def test_li6ps5cl_packet_validation_still_passes() -> None:
    """Even though the candidate REJECTS, the packet itself is well-formed.

    The validator reports overall=pass because:
    - boundary block present in every envelope,
    - audit chain head complete,
    - all required sections present,
    - AlabOS section is recipe-only,
    - publishable target set.

    The promotion verdict (=reject) is recorded as the packet's own
    decision; that does NOT make the packet invalid — it's the
    calibrated-uncertainty deliverable PRD targets.
    """
    packet = assemble_battery_packet("Li6PS5Cl", interface_mode="li_metal")
    report = validate_evidence_packet(packet)
    assert report.overall_status == "pass"


def test_li6ps5cl_packet_records_rejection_evidence_in_ionic_section() -> None:
    """The ionic_transport_full_evidence section carries the gate items.

    The bundled mlip_md envelope carries the room-temperature conductivity
    threshold check; the electrochemical_window envelope carries the
    oxidation-stability threshold (which is the gate that fires for Li6PS5Cl).
    """
    packet = assemble_battery_packet("Li6PS5Cl", interface_mode="li_metal")
    ionic = packet.bundle.section("ionic_transport_full_evidence")
    assert ionic is not None
    # 6 ionic envelopes
    assert len(ionic.envelopes) == 6
    # The electrochemical_window envelope is the one whose tool_adapter
    # emitted the window numbers; it's the ONLY envelope where the field is
    # non-null (the orchestrator returns dependency-ordered envelopes and
    # each adapter only fills its own slice of IonicTransportOutput).
    ec_window_env = next(
        (
            env
            for env in ionic.envelopes
            if env.get("tool_adapter", {}).get("name") == "ElectrochemicalWindowAdapter"
        ),
        None,
    )
    assert ec_window_env is not None
    window = ec_window_env["output"]["electrochemical_window_V_vs_LiLi"]
    assert window is not None
    # PRD §Ionic Transport: oxidation stability must be ≥ 4.0 V vs Li/Li+.
    # Li6PS5Cl literature value ≈ 2.5 V. Gate fires as expected.
    oxidation_V = window[1]
    assert oxidation_V < 4.0, f"expected Li6PS5Cl oxidation < 4 V, got {oxidation_V}"


def test_li6ps5cl_packet_journal_target_set() -> None:
    """Default Li6PS5Cl journal target is set."""
    packet = assemble_battery_packet("Li6PS5Cl")
    assert packet.publishable_paper_target.primary_journal == "Chem. Mater."
    assert packet.publishable_paper_target.alternative_journal == "ACS Energy Lett."
