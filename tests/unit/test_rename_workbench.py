"""Rename gate tests — verifies Materials Workbench identity is complete.

These tests enforce the non-negotiable outcome from the Materials Workbench
rename PRD: new package imports, old package is absent, CLI command is correct,
repo-root resolver uses the new env var and pyproject needle, and no active
source/doc contains a forbidden old-identity string.

Boundary
--------
Research infrastructure for in silico materials science discovery. Outputs are
research artifacts. No regulatory certification claims. No clinical or
human-subject use. ITAR / weapons applications are out of scope (Meta UMA
Acceptable Use Policy and operator policy).
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

from zer0pa_materials_workbench.repo_root import (
    repo_root,
)

# ---------------------------------------------------------------------------
# Gate 1: Package identity — new imports, old package absent
# ---------------------------------------------------------------------------


def test_new_package_imports_and_old_package_is_absent() -> None:
    assert importlib.util.find_spec("zer0pa_materials_workbench") is not None
    assert importlib.util.find_spec("zer0pa_materials") is None


def test_new_package_name_attribute() -> None:
    import zer0pa_materials_workbench as pkg

    assert pkg.__name__ == "zer0pa_materials_workbench"


# ---------------------------------------------------------------------------
# Gate 2: CLI wiring — new command name works, old command absent in venv
# ---------------------------------------------------------------------------


def test_cli_new_command_runs_via_python_module() -> None:
    """New CLI entry point is reachable as a Python module."""
    from typer.testing import CliRunner

    from zer0pa_materials_workbench.cli.main import app

    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0, result.output
    assert result.output.strip(), "CLI --help produced empty output"


def test_old_cli_command_absent_in_virtual_env() -> None:
    """zer0pa-materials must not exist in the active virtual env bin."""
    venv = os.environ.get("VIRTUAL_ENV")
    if venv is None:
        pytest.skip("Not running inside a virtual environment")
    old_bin = Path(venv) / "bin" / "zer0pa-materials"
    assert not old_bin.exists(), (
        f"Old CLI command still installed at {old_bin}. "
        "The rename is incomplete: stale editable-install metadata may remain."
    )


# ---------------------------------------------------------------------------
# Gate 3: Repo-root resolver — new env var, new needle; old env var rejected
# ---------------------------------------------------------------------------


def test_repo_root_walks_up_from_module_path() -> None:
    root = repo_root()
    assert (root / "pyproject.toml").exists()
    content = (root / "pyproject.toml").read_text(encoding="utf-8")
    assert 'name = "zer0pa-materials-workbench"' in content


def test_repo_root_new_env_var_is_honoured(tmp_path: Path) -> None:
    """ZER0PA_MATERIALS_WORKBENCH_REPO_ROOT overrides the walk."""
    repo = repo_root()
    env = {**os.environ, "ZER0PA_MATERIALS_WORKBENCH_REPO_ROOT": str(repo)}
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from zer0pa_materials_workbench.repo_root import repo_root; print(repo_root())",
        ],
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert str(repo) in result.stdout


def test_old_env_var_does_not_silently_work(tmp_path: Path) -> None:
    """ZER0PA_MATERIALS_REPO_ROOT (old) must NOT be honoured by the new resolver."""
    repo = repo_root()
    # Set old env var to the real repo path; new resolver should not pick it up.
    env = {
        k: v
        for k, v in os.environ.items()
        if k != "ZER0PA_MATERIALS_WORKBENCH_REPO_ROOT"
    }
    old_var = "ZER0PA_MATERIALS_REPO_ROOT"
    env[old_var] = str(repo)
    # The resolver should still find the root via the walk, but should NOT
    # use the old env var as an authoritative override.  We verify that the
    # old var does not appear in the resolver source.
    import importlib
    rr_module = importlib.import_module("zer0pa_materials_workbench.repo_root")

    source = Path(rr_module.__file__).read_text(encoding="utf-8")
    # Strip the new env var string before checking, to avoid false-positive
    source_stripped = source.replace("ZER0PA_MATERIALS_WORKBENCH_REPO_ROOT", "")
    assert old_var not in source_stripped, (
        f"Old env var {old_var} is still referenced in repo_root.py"
    )


def test_old_pyproject_needle_does_not_identify_repo(tmp_path: Path) -> None:
    """A pyproject.toml with old dist name must not be accepted as the repo root."""
    fake_pyproject = tmp_path / "pyproject.toml"
    fake_pyproject.write_text('[project]\nname = "zer0pa-materials"\n', encoding="utf-8")

    from zer0pa_materials_workbench.repo_root import _is_zer0pa_materials_root

    assert not _is_zer0pa_materials_root(tmp_path), (
        "Old distribution name 'zer0pa-materials' was accepted as the repo root — "
        "the pyproject needle was not updated."
    )


# ---------------------------------------------------------------------------
# Gate 4: Stale identity scan — no forbidden strings in active source/docs
# ---------------------------------------------------------------------------

_FORBIDDEN_PATTERNS = [
    "zer0pa" + "_materials.",     # old import prefix (split to avoid self-match)
    "import zer0pa" + "_materials\n",
    "from zer0pa" + "_materials ",
    "zer0pa" + "-materials --",   # old CLI command in docs/strings
    "ZER0PA" + "_MATERIALS_REPO_ROOT",  # old env var
    "Zer0pa" + "/Materials.git",  # old GitHub URL
]

_SCAN_ROOTS = [
    "src/zer0pa_materials_workbench",
    "tests",
]

_SKIP_FILES: frozenset[str] = frozenset(
    [
        "MATERIALS-WORKBENCH-RENAME-PRD.md",
        "MATERIALS-WORKBENCH-RENAME-STARTUP-PROMPT.md",
        "MATERIALS-WORKBENCH-RENAME-EXECUTION-REPORT.md",
        # This file itself references old patterns in _FORBIDDEN_PATTERNS strings
        "tests/unit/test_rename_workbench.py",
    ]
)


@pytest.mark.parametrize("pattern", _FORBIDDEN_PATTERNS)
def test_forbidden_identity_absent_in_source_and_tests(pattern: str) -> None:
    """No active source or test file may contain the old identity string."""
    repo = repo_root()
    hits: list[str] = []
    for root_rel in _SCAN_ROOTS:
        scan_root = repo / root_rel
        if not scan_root.exists():
            continue
        for path in scan_root.rglob("*.py"):
            rel = str(path.relative_to(repo))
            if rel in _SKIP_FILES or any(rel.endswith(skip) for skip in _SKIP_FILES):
                continue
            if "__pycache__" in str(path):
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if pattern.rstrip("\n") in text:
                # Extra check: ensure it's actually the bare old name, not the new one
                # (e.g. "zer0pa_materials_workbench." could appear as part of "_workbench")
                import re

                escaped = re.escape(pattern.rstrip("\n"))
                # Negative lookahead: not followed by _workbench or -workbench
                negative = re.compile(escaped + r"(?!_workbench|[-]workbench)")
                if negative.search(text):
                    hits.append(rel)
    assert not hits, (
        f"Forbidden pattern {pattern!r} found in {len(hits)} active source file(s):\n"
        + "\n".join(f"  {h}" for h in hits[:10])
    )
