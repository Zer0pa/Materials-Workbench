"""AlabOS section is recipe-only — adversarial test of the gate.

Boundary
--------
Research infrastructure for in silico materials science discovery. Outputs are
research artifacts. No regulatory certification claims. No clinical or
human-subject use. ITAR / weapons applications are out of scope (Meta UMA
Acceptable Use Policy and operator policy).

PRD §AlabOS Integration: ALABOS_MODE='recipe_only' is non-negotiable in
Phase 1. The compiler raises ``AlabosExecutableInRecipeOnlyError`` if a
caller passes ``hardware_executable=True`` while in recipe_only mode. The
packet's AlabOS section MUST therefore always carry
``hardware_executable=False`` AND the validator + the dedicated falsifier
must surface a fail if the section is mutated to claim otherwise.
"""

from __future__ import annotations

import pytest

from zer0pa_materials.adapters.l7.alabos_protocol import (
    AlabOSProtocolCompilerStub,
    AlabosExecutableInRecipeOnlyError,
)
from zer0pa_materials.falsifiers.packet_falsifiers import (
    packet_alabos_recipe_only_section,
)
from zer0pa_materials.packets import (
    assemble_battery_packet,
    validate_evidence_packet,
)


def test_battery_packet_alabos_section_is_recipe_only() -> None:
    """Default battery packet's AlabOS section: hardware_executable=False."""
    packet = assemble_battery_packet("LLZO")
    section = packet.bundle.section("alabos_recipe_only_protocol")
    assert section is not None
    payload = section.raw_payload
    assert payload["alabos_mode"] == "recipe_only"
    assert payload["hardware_executable"] is False


def test_compiler_raises_on_hardware_executable_in_recipe_only() -> None:
    """The underlying compiler raises rather than emitting an unsafe protocol."""
    compiler = AlabOSProtocolCompilerStub(alabos_mode="recipe_only")
    with pytest.raises(AlabosExecutableInRecipeOnlyError):
        compiler.compile(
            candidate_id="candidate:adversarial",
            recipe={"hardware_executable": True},
        )


def test_falsifier_fires_when_section_mutated_to_hardware_executable() -> None:
    """Mutating the section to claim hardware_executable=True triggers fail."""
    packet = assemble_battery_packet("LLZO")
    section = packet.bundle.section("alabos_recipe_only_protocol")
    assert section is not None
    bad_payload = dict(section.raw_payload)
    bad_payload["hardware_executable"] = True
    object.__setattr__(section, "raw_payload", bad_payload)
    item = packet_alabos_recipe_only_section(packet)
    assert item.status == "fail"


def test_validator_overall_fails_when_alabos_mutated_to_hardware_executable() -> None:
    """The full validator suite reports fail when the AlabOS gate fires."""
    packet = assemble_battery_packet("LLZO")
    section = packet.bundle.section("alabos_recipe_only_protocol")
    assert section is not None
    bad_payload = dict(section.raw_payload)
    bad_payload["hardware_executable"] = True
    object.__setattr__(section, "raw_payload", bad_payload)
    report = validate_evidence_packet(packet)
    assert report.overall_status == "fail"
    fail_names = {fi.name for fi in report.falsifier_items if fi.status == "fail"}
    assert "packet.alabos_recipe_only" in fail_names


def test_alabos_section_synthesis_steps_are_present() -> None:
    """The recipe carries non-empty synthesis steps and pre/post checks."""
    packet = assemble_battery_packet("Li-Mg-Zr-Cl-seed")
    section = packet.bundle.section("alabos_recipe_only_protocol")
    assert section is not None
    payload = section.raw_payload
    steps = payload["synthesis_steps"]
    assert len(steps) >= 1
    # Step shape from AlabOSSynthesisStep.
    for step in steps:
        assert "step" in step
        assert "operation" in step
        assert "parameters" in step
    pre = payload.get("pre_synthesis_checks", [])
    post = payload.get("post_synthesis_characterisation", [])
    assert isinstance(pre, list)
    assert isinstance(post, list)
