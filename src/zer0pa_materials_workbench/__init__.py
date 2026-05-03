"""Zer0pa Materials Workbench — research infrastructure for in silico materials science discovery.

Boundary
--------
Research infrastructure for in silico materials science discovery. Outputs are
research artifacts. No regulatory certification claims. No clinical or
human-subject use. ITAR / weapons applications are out of scope (Meta UMA
Acceptable Use Policy and operator policy).
"""

__version__ = "0.1.0"

from zer0pa_materials_workbench.boundary import RESEARCH_BOUNDARY, assert_boundary
from zer0pa_materials_workbench.repo_root import (
    RepoRootNotFoundError,
    artifacts_root,
    audit_root,
    fixture,
    fixtures_root,
    phase_dir,
    read_fixture,
    repo_root,
)

__all__ = [
    "RESEARCH_BOUNDARY",
    "RepoRootNotFoundError",
    "__version__",
    "artifacts_root",
    "assert_boundary",
    "audit_root",
    "fixture",
    "fixtures_root",
    "phase_dir",
    "read_fixture",
    "repo_root",
]
