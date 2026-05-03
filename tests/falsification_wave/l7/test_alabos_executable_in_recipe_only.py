"""Falsification wave: AlabOS hardware_executable=True under recipe_only mode.

Fixture: ``fixtures/negatives/alabos_executable_in_recipe_only/``.
Expected: the falsifier ``alabos_recipe_only_enforcement`` MUST trigger
on this exact input. The compiler-stub MUST raise.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from zer0pa_materials_workbench.adapters.l7 import (
    AlabosExecutableInRecipeOnlyError,
    AlabOSProtocolCompilerStub,
)
from zer0pa_materials_workbench.falsifiers.l7_falsifiers import alabos_recipe_only_enforcement

FIXTURE_ROOT = Path(__file__).resolve().parents[3] / "fixtures" / "negatives" / "alabos_executable_in_recipe_only"


def test_fixture_protocol_triggers_alabos_falsifier():
    payload = json.loads((FIXTURE_ROOT / "protocol.json").read_text())
    item = alabos_recipe_only_enforcement(payload)
    assert item.status == "fail"
    assert item.actual["violation"] is True


def test_fixture_compiler_raises():
    payload = json.loads((FIXTURE_ROOT / "protocol.json").read_text())
    compiler = AlabOSProtocolCompilerStub(alabos_mode=payload["alabos_mode"])
    recipe = {
        "hardware_executable": payload["hardware_executable"],
        "synthesis_steps": [
            {"step": s.get("step", i + 1), "operation": s["operation"], "parameters": s}
            for i, s in enumerate(payload["synthesis_steps"])
        ],
    }
    with pytest.raises(AlabosExecutableInRecipeOnlyError):
        compiler.compile(payload["candidate_id"], recipe=recipe)


def test_fixture_negative_falsifier_target_metadata():
    """The fixture manifest must explicitly target this falsifier."""
    manifest = json.loads((FIXTURE_ROOT / "manifest.json").read_text())
    assert manifest["negative_falsifier_target"] == "alabos_executable_in_recipe_only"
    assert "L7" in manifest["expected_use_layers"]
