"""Falsification wave: tenant_only tuple inside a shared_learning bundle.

Fixture: ``fixtures/negatives/tenant_only_tuple_leak/``.
Expected: the falsifier ``tenant_only_tuple_leak`` MUST trigger.
"""

from __future__ import annotations

import json
from pathlib import Path

from zer0pa_materials_workbench.falsifiers.l7_falsifiers import tenant_only_tuple_leak

FIXTURE_ROOT = Path(__file__).resolve().parents[3] / "fixtures" / "negatives" / "tenant_only_tuple_leak"


def test_fixture_triggers_tuple_leak_falsifier():
    bundle = json.loads((FIXTURE_ROOT / "tuple_export.json").read_text())
    item = tenant_only_tuple_leak(bundle)
    assert item.status == "fail"
    assert "tuple:test/leaked-1" in item.actual["leaks"]


def test_fixture_negative_falsifier_target_metadata():
    manifest = json.loads((FIXTURE_ROOT / "manifest.json").read_text())
    assert manifest["negative_falsifier_target"] == "tenant_only_tuple_leak"
    assert "L7" in manifest["expected_use_layers"]
