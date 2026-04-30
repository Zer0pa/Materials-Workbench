"""Falsification wave: Li-metal route violation.

A synthetic candidate with li_metal_unstable_coating_required interface
classification AND mode != coating_interlayer must trigger
``li_metal_reduction_route_compatibility`` with status ``fail``.

The mirror case (same instability, mode == coating_interlayer) must
pass.
"""

from __future__ import annotations

import pytest

from zer0pa_materials.adapters.ionic.base import IonicJobParams
from zer0pa_materials.adapters.ionic.interface_stability import (
    InterfaceStabilityAdapter,
)
from zer0pa_materials.falsifiers.ionic_falsifiers import (
    li_metal_reduction_route_compatibility,
)


def test_unstable_default_mode_fails() -> None:
    """Li6PS5Cl in li_metal mode triggers the route violation."""
    p = IonicJobParams(
        structure_hash="sha256:8d7b217550c751a08bd6bc85d74a166ff0b4966266552d254ca53527607c40bc",
        fixture_id="fixture:Li6PS5Cl:8d7b2175",
        candidate_id="candidate:test/route-violation",
        interface_mode="li_metal",
    )
    env = InterfaceStabilityAdapter().compute(p)
    item = li_metal_reduction_route_compatibility(env)
    assert item.status == "fail"
    assert "PRD" in (item.rationale or "")


def test_unstable_with_coating_passes() -> None:
    """Same instability + coating_interlayer mode is allowed."""
    p = IonicJobParams(
        structure_hash="sha256:8d7b217550c751a08bd6bc85d74a166ff0b4966266552d254ca53527607c40bc",
        fixture_id="fixture:Li6PS5Cl:8d7b2175",
        candidate_id="candidate:test/route-coated",
        interface_mode="coating_interlayer",
    )
    env = InterfaceStabilityAdapter().compute(p)
    item = li_metal_reduction_route_compatibility(env)
    assert item.status == "pass"


def test_synthetic_candidate_no_classification_blocks() -> None:
    """Unknown classification routes to blocked, not fail."""
    body = {"output": {"interface_stability": "unknown"}}
    item = li_metal_reduction_route_compatibility(body, interface_mode="li_metal")
    assert item.status == "blocked"


def test_explicit_classification_unstable_no_coating_fails() -> None:
    """Construct a synthetic envelope with unstable classification."""
    body = {
        "output": {
            "interface_stability": "li_metal_unstable_coating_required",
            "defect_disorder_assumptions": ["interface_mode=li_metal"],
        }
    }
    item = li_metal_reduction_route_compatibility(body)
    assert item.status == "fail"


def test_explicit_classification_unstable_with_coating_passes() -> None:
    body = {
        "output": {
            "interface_stability": "li_metal_unstable_coating_required",
            "defect_disorder_assumptions": ["interface_mode=coating_interlayer"],
        }
    }
    item = li_metal_reduction_route_compatibility(body)
    assert item.status == "pass"


def test_explicit_classification_stable_passes_regardless_of_mode() -> None:
    body = {
        "output": {
            "interface_stability": "li_metal_stable",
            "defect_disorder_assumptions": ["interface_mode=li_metal"],
        }
    }
    item = li_metal_reduction_route_compatibility(body)
    assert item.status == "pass"


def test_falsifier_rationale_invokes_prd() -> None:
    """The fail rationale must explicitly cite the PRD."""
    body = {
        "output": {
            "interface_stability": "li_metal_unstable_coating_required",
            "defect_disorder_assumptions": ["interface_mode=li_metal"],
        }
    }
    item = li_metal_reduction_route_compatibility(body)
    assert item.rationale is not None
    assert "PRD" in item.rationale
