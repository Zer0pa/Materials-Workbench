"""MVP Evidence Packet generator (Wave 5a, PRD §Final Output Required #9 + #10).

The Wave 5a packet is the **publishable-paper deliverable** the operator's
PRD targets:

  * battery primary packet — quaternary halide / LLZO / Li6PS5Cl evidence
    with calibrated DFT/MLIP/CALPHAD disagreement and AlabOS recipe-only
    protocol candidate JSON;
  * thermoelectric sidecar packet — Si / Bi2Te3 / PbTe / SnSe family with
    Phono3py + BoltzTraP2/AMSET disagreement-driven ZT.

Both packet shapes share the :class:`EvidencePacket` Pydantic model
(:mod:`zer0pa_materials_workbench.packets.evidence_packet`). Per-objective generators
live in :mod:`zer0pa_materials_workbench.packets.battery_packet` and
:mod:`zer0pa_materials_workbench.packets.thermoelectric_packet`. The RO-Crate
exporter in :mod:`zer0pa_materials_workbench.packets.ro_crate_export` round-trips
serialise → parse → counts-match without loss; the validator suite in
:mod:`zer0pa_materials_workbench.packets.validators` enforces the PRD §Audit Trail
And KG promotion gate "every claim must have evidence + source manifest +
audit record + falsifier + rights scope" on the assembled packet.

Public surface
--------------

* :class:`EvidencePacket`           — the universal packet shape.
* :class:`PacketSection`            — one section of a packet (literature,
  L2 ensemble, ionic transport, L1.5 phonon, L7 metadata, AlabOS protocol,
  KG snapshot, audit chain head).
* :class:`PacketPublishableTarget`  — Pydantic model for the journal target.
* :func:`assemble_battery_packet`   — primary battery packet generator.
* :func:`assemble_thermoelectric_packet` — thermoelectric sidecar generator.
* :func:`validate_evidence_packet`  — multi-falsifier validation.
* :func:`export_packet_to_ro_crate` — RO-Crate 1.1 exporter.

The packet generator NEVER touches the foundation/adapter envelope
implementations; it only consumes their public surfaces.
"""

from zer0pa_materials_workbench.packets.battery_packet import (
    BatteryPacketAssembler,
    assemble_battery_packet,
)
from zer0pa_materials_workbench.packets.evidence_packet import (
    EvidencePacket,
    PacketBundle,
    PacketObjective,
    PacketPublishableTarget,
    PacketSection,
    PromotionVerdict,
)
from zer0pa_materials_workbench.packets.ro_crate_export import (
    PacketRoCrateBundle,
    export_packet_to_ro_crate,
    parse_packet_ro_crate,
)
from zer0pa_materials_workbench.packets.thermoelectric_packet import (
    ThermoelectricPacketAssembler,
    assemble_thermoelectric_packet,
)
from zer0pa_materials_workbench.packets.validators import (
    ValidationReport,
    validate_evidence_packet,
)

__all__ = [
    # core packet
    "EvidencePacket",
    "PacketSection",
    "PacketBundle",
    "PacketObjective",
    "PacketPublishableTarget",
    "PromotionVerdict",
    # generators
    "BatteryPacketAssembler",
    "assemble_battery_packet",
    "ThermoelectricPacketAssembler",
    "assemble_thermoelectric_packet",
    # validators
    "ValidationReport",
    "validate_evidence_packet",
    # ro-crate export
    "PacketRoCrateBundle",
    "export_packet_to_ro_crate",
    "parse_packet_ro_crate",
]
