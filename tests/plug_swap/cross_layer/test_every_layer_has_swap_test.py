"""PRD requirement: "Each layer has at least one plug-replaceability test."

Research infrastructure for in silico materials science discovery.
Outputs are research artifacts. No regulatory certification claims.
No clinical or human-subject use. ITAR / weapons applications are
out of scope (Meta UMA Acceptable Use Policy and operator policy).

This test discovers all existing per-layer plug-swap test modules and
asserts that every mandatory layer has at least one test function. The
discovery is purely static (path-based) so it does not import per-layer
tests or duplicate their execution.

PRD §Acceptance Gates / Engineering:
    "Each layer has at least one plug-replaceability test."
"""

from __future__ import annotations

from pathlib import Path

import pytest

# The 11 canonical layers that PRD §Architecture Invariant mandates coverage for.
REQUIRED_LAYERS: list[str] = [
    "phase0",
    "l6",
    "l1",
    "quantum",
    "l2",
    "ionic",
    "l1_5",
    "l3",
    "l4",
    "l5",
    "l7",
]

# Root of the per-layer plug_swap test tree (sibling directories to cross_layer/).
_PLUG_SWAP_ROOT = Path(__file__).parents[1]


def _discover_test_functions_in_dir(directory: Path) -> list[str]:
    """Return all test function/class names from .py files in a directory."""
    test_names: list[str] = []
    for py_file in directory.rglob("test_*.py"):
        text = py_file.read_text()
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("def test_") or stripped.startswith("class Test"):
                test_names.append(stripped.split("(")[0].split(":")[0].strip())
    return test_names


@pytest.mark.parametrize("layer", REQUIRED_LAYERS)
def test_layer_has_plug_swap_directory(layer: str) -> None:
    """Each mandatory layer must have a dedicated plug_swap subdirectory."""
    layer_dir = _PLUG_SWAP_ROOT / layer
    assert layer_dir.is_dir(), (
        f"Missing plug-swap directory for layer {layer!r}: {layer_dir}\n"
        "PRD §Acceptance Gates / Engineering requires at least one "
        "plug-replaceability test per layer."
    )


@pytest.mark.parametrize("layer", REQUIRED_LAYERS)
def test_layer_has_at_least_one_test_file(layer: str) -> None:
    """Each layer directory must contain at least one test_*.py file."""
    layer_dir = _PLUG_SWAP_ROOT / layer
    test_files = list(layer_dir.glob("test_*.py"))
    assert test_files, (
        f"No test_*.py files found in {layer_dir}. "
        "PRD §Acceptance Gates / Engineering requires at least one "
        "plug-replaceability test per layer."
    )


@pytest.mark.parametrize("layer", REQUIRED_LAYERS)
def test_layer_has_at_least_one_test_function(layer: str) -> None:
    """Each layer's test files must define at least one test function or class."""
    layer_dir = _PLUG_SWAP_ROOT / layer
    test_names = _discover_test_functions_in_dir(layer_dir)
    assert test_names, (
        f"No test functions or classes found in {layer_dir}. "
        "PRD §Acceptance Gates / Engineering requires at least one "
        "plug-replaceability test per layer."
    )
