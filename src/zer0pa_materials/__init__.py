"""Zer0pa Materials — research infrastructure for in silico materials science discovery.

Boundary
--------
Research infrastructure for in silico materials science discovery. Outputs are
research artifacts. No regulatory certification claims. No clinical or
human-subject use. ITAR / weapons applications are out of scope (Meta UMA
Acceptable Use Policy and operator policy).
"""

__version__ = "0.1.0"

from zer0pa_materials.boundary import RESEARCH_BOUNDARY, assert_boundary

__all__ = ["RESEARCH_BOUNDARY", "assert_boundary", "__version__"]
