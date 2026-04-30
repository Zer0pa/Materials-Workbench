"""ElectrochemicalWindowAdapter — oxidative / reductive stability vs Li/Li+.

Computes the electrochemical stability window (volts vs Li/Li+) for a
solid electrolyte against both Li metal (reduction at the anode side)
and a cathode chemistry placeholder. Stub mode returns deterministic
literature-canonical values for the three battery fixtures.

Real backend
------------

The "real" path computes the window from a DFT phase diagram against
Li metal and the cathode chemistry: identify the most exoergic
decomposition product on each side, infer the chemical potential
required to suppress it, and convert to V vs Li/Li+ via the standard
electrochemistry relation. That backend requires:

* DFT energies for the parent electrolyte and all decomposition
  products (gated by L1).
* A maintained lookup of common cathode chemistries (NMC, NCA, LFP, LCO).
* Phase-diagram software (pymatgen / Materials Project lookup).

All three are parked behind the L1 source manifest. See
:data:`ELECTROCHEMICAL_WINDOW_BLOCKED_MANIFEST`.

Calibration anchors
-------------------

* LLZO: ~0–6 V vs Li/Li+. Highly stable (no oxidation up to ~6 V) and
  Li-metal stable (no reduction at low V). Literature: Murugan et al.
  (2007), Awaka et al. (2009).
* Li6PS5Cl: ~1.7–2.5 V vs Li/Li+. Reduces against Li metal (forms
  Li2S, LiCl decomposition layer) and oxidises around 2.5 V (S²⁻ ->
  PS_n ladder). Borderline gate failure unless coated.
* Li-Mg-Zr-Cl-seed (Li3MCl6 family): ~1.4–4.3 V vs Li/Li+. Reduces at
  low V (Cl⁻ → Cl₂ disprop avoidance), oxidises near ~4 V. Marginal
  cathode-facing, unstable vs Li metal.
"""

from __future__ import annotations

from typing import Any

from zer0pa_materials.adapters.ionic.base import (
    IonicJobParams,
    IonicTransportAdapter,
)
from zer0pa_materials.audit.sources import BlockedSourceManifest
from zer0pa_materials.envelope import (
    Envelope,
    IonicTransportOutput,
)

__all__ = [
    "ElectrochemicalWindowAdapter",
    "ELECTROCHEMICAL_WINDOW_BLOCKED_MANIFEST",
    "fixture_window_V",
]


ELECTROCHEMICAL_WINDOW_BLOCKED_MANIFEST: BlockedSourceManifest = BlockedSourceManifest(
    source_manifest_id="src:blocked:electrochemical-window-real-backend",
    attempted_locator="DFT-phase-diagram-with-Li-metal-and-cathode-chemistries",
    blocker_reason="unavailable_credentials",
    blocker_detail=(
        "Real electrochemical window computation requires DFT energies "
        "for the parent electrolyte and all relevant decomposition "
        "products (gated by L1) plus a curated cathode chemistry lookup "
        "(NMC, NCA, LFP, LCO). Stub returns deterministic literature-"
        "canonical windows for the three battery fixtures and unknown "
        "structures default to a tight 2.0–3.5 V envelope."
    ),
    retry_strategy=(
        "Wire DFT phase-diagram computation after L1 publishes a "
        "convex-hull-capable solver and an authoritative cathode "
        "chemistry table is curated."
    ),
)


# Literature-canonical (reduction, oxidation) windows in V vs Li/Li+ for
# the three battery fixtures.
_LITERATURE_WINDOWS: dict[str, tuple[float, float]] = {
    "fixture:LLZO_cubic:d45cb2bf": (0.05, 6.00),  # very stable
    "fixture:LLZO_tetragonal:": (0.05, 6.00),
    "fixture:Li6PS5Cl:8d7b2175": (1.70, 2.50),  # narrow oxidation window
    "fixture:Li-Mg-Zr-Cl-seed:ea01c76f": (1.40, 4.30),  # marginal cathode-side
}


def fixture_window_V(fixture_id: str | None) -> tuple[float, float]:
    """Return the (reduction, oxidation) potentials in V vs Li/Li+.

    Falls back to a default-pessimistic 2.0-3.5 V window for unknown
    fixtures so a novel candidate exercises the oxidation gate by
    default until evidence demonstrates a wider window.
    """
    if fixture_id is not None and fixture_id in _LITERATURE_WINDOWS:
        return _LITERATURE_WINDOWS[fixture_id]
    return (2.0, 3.5)


class ElectrochemicalWindowAdapter(IonicTransportAdapter):
    """Electrochemical window adapter (CPU-first stub)."""

    ADAPTER_NAME = "ElectrochemicalWindowAdapter"
    ADAPTER_VERSION = "0.1.0"
    BACKEND = "stub"
    ENGINE = "ec-window-stub-v1"

    def compute(self, params: IonicJobParams) -> Envelope:
        red, ox = fixture_window_V(params.fixture_id)
        is_known = params.fixture_id is not None and params.fixture_id in _LITERATURE_WINDOWS
        confidence = 0.85 if is_known else 0.30
        output = IonicTransportOutput(
            electrochemical_window_V_vs_LiLi=(red, ox),
            interface_stability="unknown",
            defect_disorder_assumptions=[
                f"reduction_onset_V={red}",
                f"oxidation_onset_V={ox}",
                "stub: literature-canonical window; not from DFT phase diagram",
            ],
            confidence=confidence,
        )
        extra_input: dict[str, Any] = {
            "cathode_chemistry": params.cathode_chemistry,
        }
        return self.make_envelope(output, params, extra_input=extra_input)
