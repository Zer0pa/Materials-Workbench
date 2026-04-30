"""Test the AlabOSProtocolCompilerStub — recipe-only enforcement."""

from __future__ import annotations

import pytest

from zer0pa_materials.adapters.l7 import (
    AlabosExecutableInRecipeOnlyError,
    AlabOSProtocolCompilerStub,
)
from zer0pa_materials.adapters.l7.base import L7CampaignParams


def test_default_mode_is_recipe_only():
    compiler = AlabOSProtocolCompilerStub()
    assert compiler.alabos_mode == "recipe_only"


def test_compile_default_recipe():
    compiler = AlabOSProtocolCompilerStub()
    p = compiler.compile("candidate:test/c1")
    assert p.alabos_mode == "recipe_only"
    assert p.hardware_executable is False
    assert len(p.synthesis_steps) >= 1


def test_compile_with_user_recipe():
    compiler = AlabOSProtocolCompilerStub()
    recipe = {
        "synthesis_steps": [
            {"step": 1, "operation": "ball_mill", "parameters": {"rpm": 400}}
        ],
        "pre_synthesis_checks": ["check_glove_box"],
    }
    p = compiler.compile("candidate:test/c1", recipe=recipe)
    assert len(p.synthesis_steps) == 1
    assert p.synthesis_steps[0].operation == "ball_mill"
    assert "check_glove_box" in p.pre_synthesis_checks


def test_hardware_executable_under_recipe_only_raises():
    compiler = AlabOSProtocolCompilerStub(alabos_mode="recipe_only")
    recipe = {"hardware_executable": True}
    with pytest.raises(AlabosExecutableInRecipeOnlyError):
        compiler.compile("candidate:test/c1", recipe=recipe)


def test_phase2_hardware_mode_allows_executable():
    compiler = AlabOSProtocolCompilerStub(alabos_mode="phase2_hardware")
    recipe = {"hardware_executable": True}
    p = compiler.compile("candidate:test/c1", recipe=recipe)
    assert p.hardware_executable is True


def test_envelope_alabos_falsifier_pass():
    compiler = AlabOSProtocolCompilerStub()
    env = compiler.execute(L7CampaignParams(
        campaign_id="campaign:test/c1", candidate_id="candidate:test/c1"
    ))
    items = {fi.name: fi for fi in env.falsifier.items}
    assert items["l7.alabos_recipe_only_enforcement"].status == "pass"
