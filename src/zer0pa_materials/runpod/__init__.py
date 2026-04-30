"""Runpod migration scaffold — Wave 5c + Wave C.

This module makes the Runpod cutover a *config-flag-only* swap when the GPU
machine comes online.  Wave C adds the live REST client + central dispatcher
so that an envelope labelled ``backend = "runpod_rest"`` is always backed
by a real HTTP call, never a relabelled mock.

Public surface
--------------
* :mod:`~zer0pa_materials.runpod.mock_backends`  — per-layer runpod_mock backends.
* :mod:`~zer0pa_materials.runpod.cutover`        — cutover orchestrator.
* :mod:`~zer0pa_materials.runpod.hard_failures`  — 10 PRD-mandated detectors.
* :mod:`~zer0pa_materials.runpod.rest_client`    — Wave C live REST client.
* :mod:`~zer0pa_materials.runpod.dispatcher`     — Wave C honest-block dispatch.

Boundary (verbatim)
-------------------
Research infrastructure for in silico materials science discovery.
Outputs are research artifacts. No regulatory certification claims.
No clinical or human-subject use. ITAR / weapons applications are
out of scope (Meta UMA Acceptable Use Policy and operator policy).
"""

from zer0pa_materials.runpod.cutover import RunpodCutover
from zer0pa_materials.runpod.dispatcher import (
    DispatchResult,
    LAYER_BACKEND_FLAG_MAP,
    RunpodDispatcher,
)
from zer0pa_materials.runpod.hard_failures import HardFailureDetector
from zer0pa_materials.runpod.mock_backends import (
    RUNPOD_MOCK_LAYERS,
    build_runpod_mock_envelope,
)
from zer0pa_materials.runpod.rest_client import (
    RunpodCredentialsError,
    RunpodRestClient,
    RunpodRestError,
)

__all__ = [
    "RunpodCutover",
    "HardFailureDetector",
    "build_runpod_mock_envelope",
    "RUNPOD_MOCK_LAYERS",
    # Wave C
    "RunpodRestClient",
    "RunpodCredentialsError",
    "RunpodRestError",
    "RunpodDispatcher",
    "DispatchResult",
    "LAYER_BACKEND_FLAG_MAP",
]
