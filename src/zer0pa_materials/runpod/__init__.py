"""Runpod migration scaffold — Wave 5c.

This module makes the Runpod cutover a *config-flag-only* swap when the GPU
machine comes online.  No architecture changes to adapters, services, or
falsifiers are required.

Public surface
--------------
* :mod:`~zer0pa_materials.runpod.mock_backends`  — per-layer runpod_mock backends.
* :mod:`~zer0pa_materials.runpod.cutover`        — cutover orchestrator.
* :mod:`~zer0pa_materials.runpod.hard_failures`  — 10 PRD-mandated detectors.

Boundary (verbatim)
-------------------
Research infrastructure for in silico materials science discovery.
Outputs are research artifacts. No regulatory certification claims.
No clinical or human-subject use. ITAR / weapons applications are
out of scope (Meta UMA Acceptable Use Policy and operator policy).
"""

from zer0pa_materials.runpod.cutover import RunpodCutover
from zer0pa_materials.runpod.hard_failures import HardFailureDetector
from zer0pa_materials.runpod.mock_backends import (
    build_runpod_mock_envelope,
    RUNPOD_MOCK_LAYERS,
)

__all__ = [
    "RunpodCutover",
    "HardFailureDetector",
    "build_runpod_mock_envelope",
    "RUNPOD_MOCK_LAYERS",
]
