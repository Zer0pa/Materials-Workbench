"""Li-Mg-Zr-Cl-seed battery packet — coating-only promotion path.

Boundary
--------
Research infrastructure for in silico materials science discovery. Outputs are
research artifacts. No regulatory certification claims. No clinical or
human-subject use. ITAR / weapons applications are out of scope (Meta UMA
Acceptable Use Policy and operator policy).

Per ``phases/Ionic-transport/PHASE-REPORT.md``: the Li-Mg-Zr-Cl-seed
"promotes only with `coating_interlayer` mode; rejects in default `li_metal`
mode (route compatibility correctly enforces the PRD's 'coating only'
exception)." This is the central PRD §Acceptance Gates: Battery MVP test
case.
"""

from __future__ import annotations

from zer0pa_materials_workbench.packets import (
    assemble_battery_packet,
    validate_evidence_packet,
)


def test_seed_rejects_in_li_metal_mode() -> None:
    """Default li_metal mode REJECTS the seed — interface unstable vs Li metal."""
    packet = assemble_battery_packet("Li-Mg-Zr-Cl-seed", interface_mode="li_metal")
    assert packet.promotion_decision == "reject"


def test_seed_promotes_in_coating_interlayer_mode() -> None:
    """coating_interlayer mode PROMOTES the seed — gate passes with coating."""
    packet = assemble_battery_packet(
        "Li-Mg-Zr-Cl-seed",
        interface_mode="coating_interlayer",
    )
    assert packet.promotion_decision == "promote"


def test_seed_l6_envelope_marks_novelty() -> None:
    """The L6 envelope reports novelty_status=novel for the seed."""
    packet = assemble_battery_packet("Li-Mg-Zr-Cl-seed")
    l6 = packet.bundle.section("l6_generated_structure")
    assert l6 is not None
    assert l6.envelopes[0]["output"]["novelty_status"] == "novel"


def test_seed_packet_validates_in_both_modes() -> None:
    """Validator overall=pass in both modes; promotion_decision differs."""
    p1 = assemble_battery_packet("Li-Mg-Zr-Cl-seed", interface_mode="li_metal")
    p2 = assemble_battery_packet(
        "Li-Mg-Zr-Cl-seed", interface_mode="coating_interlayer"
    )
    r1 = validate_evidence_packet(p1)
    r2 = validate_evidence_packet(p2)
    assert r1.overall_status == "pass"
    assert r2.overall_status == "pass"
    assert p1.promotion_decision == "reject"
    assert p2.promotion_decision == "promote"


def test_seed_journal_target_is_top_tier() -> None:
    """The novel-seed packet targets a top-tier journal."""
    packet = assemble_battery_packet("Li-Mg-Zr-Cl-seed")
    target = packet.publishable_paper_target
    assert target.primary_journal == "Nature Materials"
    assert target.alternative_journal == "Joule"
