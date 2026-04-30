"""CLI integration tests — every layer subapp is reachable from the root entrypoint.

This test pins the Wave 4b CLI integration: ``zer0pa-materials <layer> --help``
must succeed for every layer that has been built. When Wave 4a (L7) lands, its
subapp is added here too.

Boundary
--------
Research infrastructure for in silico materials science discovery. Outputs are
research artifacts. No regulatory certification claims. No clinical or
human-subject use. ITAR / weapons applications are out of scope (Meta UMA
Acceptable Use Policy and operator policy).
"""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from zer0pa_materials.cli.main import app


# Layers wired in Wave 4b. The "l7" entry is added once Wave 4a completes;
# until then, the test suite still passes for the layers that exist.
WIRED_LAYERS: tuple[str, ...] = (
    "phase0",
    "l6",
    "l1",
    "quantum",
    "l2",
    "ionic",
    "l15",  # PRD writes "L1.5"; typer doesn't accept dots in command names
    "l3",
    "l4",
    "l5",
    "l7",
    "packets",
    "falsification",
    "runpod",
)


@pytest.fixture(scope="module")
def runner() -> CliRunner:
    return CliRunner()


def test_root_help_lists_every_wired_layer(runner: CliRunner) -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0, result.output
    for layer in WIRED_LAYERS:
        assert layer in result.output, f"layer {layer!r} not in CLI root help"


@pytest.mark.parametrize("layer", WIRED_LAYERS)
def test_layer_subapp_help(runner: CliRunner, layer: str) -> None:
    """Every wired layer subapp returns help text without error."""
    result = runner.invoke(app, [layer, "--help"])
    assert result.exit_code == 0, f"{layer} --help failed:\n{result.output}"
    # Help output should mention the layer name (case-insensitive).
    assert layer.lower() in result.output.lower(), (
        f"{layer} --help output does not mention the layer name:\n{result.output}"
    )


def test_root_version(runner: CliRunner) -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert result.output.strip(), "version command produced empty output"


def test_envelope_schema_for_each_layer(runner: CliRunner) -> None:
    """The envelope-schema --layer flag accepts every layer-output registry key."""
    from zer0pa_materials.envelope import LAYER_OUTPUT_REGISTRY

    for layer in LAYER_OUTPUT_REGISTRY:
        result = runner.invoke(app, ["envelope-schema", "--layer", layer, "--compact"])
        assert result.exit_code == 0, f"envelope-schema --layer {layer} failed:\n{result.output}"
        # Output is JSON; trivial sanity check.
        assert result.output.strip().startswith("{"), (
            f"envelope-schema --layer {layer} did not produce JSON:\n{result.output[:200]}"
        )


def test_audit_subapp_help(runner: CliRunner) -> None:
    result = runner.invoke(app, ["audit", "--help"])
    assert result.exit_code == 0
    for cmd in ("add-source", "add-blocked-source", "validate-chain", "reconstruct"):
        assert cmd in result.output, f"audit subcommand {cmd!r} not in help"
