"""InterfaceStabilityAdapter — Li-metal / cathode interface classification.

Classifies the interface stability of a solid electrolyte with respect
to Li metal and a cathode placeholder. Returns one of the values in the
:data:`IonicInterfaceClass` literal (envelope schema):

* ``li_metal_stable`` — stable against Li metal anode.
* ``li_metal_unstable_coating_required`` — unstable but coatable; the
  PRD allows promotion only if ``mode == coating_interlayer``.
* ``cathode_facing_stable`` — stable on the cathode side.
* ``cathode_facing_unstable`` — fails the cathode-side gate.
* ``unknown`` — insufficient evidence; route to AIMD interface
  simulation before promotion.

Real backend
------------

Real interface classification requires:

* DFT decomposition energies vs Li metal across a Li chemical-potential
  scan (gated by L1).
* AIMD interface relaxation (gated by the AIMD adapter's blocked
  manifest).
* A cathode chemistry placeholder that selects a representative
  surface termination (currently NMC811 only).

All three are parked behind the L1 source manifest. See
:data:`INTERFACE_STABILITY_BLOCKED_MANIFEST`.

Classification table (literature-aligned)
-----------------------------------------

The stub uses a fixed lookup table for the three battery fixtures:

| Fixture                  | vs Li metal                              | vs cathode |
|--------------------------|------------------------------------------|------------|
| LLZO cubic               | li_metal_stable                          | cathode_facing_stable |
| LLZO tetragonal          | li_metal_stable                          | cathode_facing_stable |
| Li6PS5Cl                 | li_metal_unstable_coating_required       | cathode_facing_unstable |
| Li-Mg-Zr-Cl-seed         | li_metal_unstable_coating_required       | cathode_facing_unstable |

Unknown fixtures default to ``unknown``.
"""

from __future__ import annotations

from typing import Any

from zer0pa_materials_workbench.adapters.ionic.base import (
    IonicJobParams,
    IonicTransportAdapter,
)
from zer0pa_materials_workbench.audit.sources import BlockedSourceManifest
from zer0pa_materials_workbench.envelope import (
    Envelope,
    IonicTransportOutput,
)

__all__ = [
    "INTERFACE_STABILITY_BLOCKED_MANIFEST",
    "InterfaceStabilityAdapter",
    "classify_interface",
]


INTERFACE_STABILITY_BLOCKED_MANIFEST: BlockedSourceManifest = BlockedSourceManifest(
    source_manifest_id="src:blocked:interface-stability-real-backend",
    attempted_locator="DFT-AIMD-interface-decomposition-vs-Li-and-cathode",
    blocker_reason="unavailable_credentials",
    blocker_detail=(
        "Real interface classification requires DFT decomposition "
        "energies vs Li metal (gated by L1), AIMD interface "
        "relaxation (gated by AIMD adapter), and a curated cathode "
        "chemistry table. Stub returns deterministic literature "
        "classifications for the three battery fixtures."
    ),
    retry_strategy=(
        "Wire the real backend after L1 enables AIMD-class runs and a "
        "cathode chemistry table is curated. Run on every promoted "
        "candidate before MVP packet generation."
    ),
)


# Literature-aligned classifications.
# Each entry is (vs Li metal, vs cathode).
_LITERATURE_CLASSIFICATION: dict[str, tuple[str, str]] = {
    "fixture:LLZO_cubic:d45cb2bf": ("li_metal_stable", "cathode_facing_stable"),
    "fixture:LLZO_tetragonal:": ("li_metal_stable", "cathode_facing_stable"),
    "fixture:Li6PS5Cl:8d7b2175": (
        "li_metal_unstable_coating_required",
        "cathode_facing_unstable",
    ),
    "fixture:Li-Mg-Zr-Cl-seed:ea01c76f": (
        "li_metal_unstable_coating_required",
        "cathode_facing_unstable",
    ),
}


def classify_interface(
    fixture_id: str | None,
    interface_mode: str,
) -> str:
    """Return the interface_stability literal for the chosen mode.

    ``interface_mode`` selects which face we report:

    * ``li_metal``           -> the vs-Li-metal classification.
    * ``cathode_facing``     -> the vs-cathode classification.
    * ``coating_interlayer`` -> the vs-Li-metal classification (the
      coating route is a downstream routing decision; this adapter
      reports the bare interface classification).

    Unknown fixtures or modes fall back to ``"unknown"``.
    """
    if fixture_id is None or fixture_id not in _LITERATURE_CLASSIFICATION:
        return "unknown"
    li_class, cathode_class = _LITERATURE_CLASSIFICATION[fixture_id]
    if interface_mode in ("li_metal", "coating_interlayer"):
        return li_class
    if interface_mode == "cathode_facing":
        return cathode_class
    return "unknown"


class InterfaceStabilityAdapter(IonicTransportAdapter):
    """Li-metal / cathode interface classification (CPU-first stub)."""

    ADAPTER_NAME = "InterfaceStabilityAdapter"
    ADAPTER_VERSION = "0.1.0"
    BACKEND = "stub"
    ENGINE = "interface-stability-stub-v1"

    def compute(self, params: IonicJobParams) -> Envelope:
        classification = classify_interface(params.fixture_id, params.interface_mode)
        is_known = params.fixture_id in _LITERATURE_CLASSIFICATION
        confidence = 0.80 if is_known else 0.20
        # Disorder assumption: ordered fixture, no AIMD interface relaxation.
        output = IonicTransportOutput(
            interface_stability=classification,  # type: ignore[arg-type]
            defect_disorder_assumptions=[
                f"interface_mode={params.interface_mode}",
                f"cathode_chemistry={params.cathode_chemistry}",
                "stub: lookup-table classification; no AIMD interface relaxation",
            ],
            confidence=confidence,
        )
        extra_input: dict[str, Any] = {
            "interface_mode": params.interface_mode,
            "cathode_chemistry": params.cathode_chemistry,
        }
        return self.make_envelope(output, params, extra_input=extra_input)
