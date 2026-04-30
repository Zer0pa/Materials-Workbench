"""Layer-bound services (FastAPI).

Public surface:

* :data:`ionic_app` — FastAPI app for the IonicTransportService
  (PRD §Ionic Transport).
* :func:`run_full_battery_evidence` — orchestrator that runs every
  ionic adapter for a single candidate and returns the full evidence
  chain (six envelopes) used by the MVP packet generator.
* :func:`promote_battery_candidate` — battery promotion gate. Returns
  a :class:`PromotionDecision` with a documented promote/defer/reject
  outcome derived from the PRD §Ionic Transport gates.
"""

from zer0pa_materials.services.ionic_transport_service import (
    IONIC_SERVICE_NAME,
    IONIC_SERVICE_VERSION,
    BatteryEvidenceBundle,
    PromotionDecision,
    PromotionStatus,
    create_ionic_app,
    ionic_app,
    promote_battery_candidate,
    run_full_battery_evidence,
)

__all__ = [
    "ionic_app",
    "create_ionic_app",
    "IONIC_SERVICE_NAME",
    "IONIC_SERVICE_VERSION",
    "BatteryEvidenceBundle",
    "PromotionDecision",
    "PromotionStatus",
    "run_full_battery_evidence",
    "promote_battery_candidate",
]
