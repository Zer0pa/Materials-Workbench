"""EvidencePacket — the publishable-paper deliverable model (Wave 5a).

Per PRD §Final Output Required:

    9. Solid-state battery MVP evidence packet generator for LLZO, Li6PS5Cl,
       and the Li-Mg-Zr-Cl challenge family.
    10. Thermoelectric sidecar lane for Si plus Bi2Te3/PbTe/SnSe-style
        fixtures.

A packet bundles every layer envelope + the orchestration metadata + the
KG subgraph + the audit-chain head + the AlabOS recipe-only protocol +
the rights claim per data class for one candidate. The
:class:`EvidencePacket` is the canonical Pydantic shape.

Boundary
--------

Per ``zer0pa_materials.boundary.RESEARCH_BOUNDARY``, every artifact this
module emits carries the boundary block verbatim. Validation through the
existing :class:`Envelope` model already enforces the boundary on every
nested envelope; the packet's top-level ``research_boundary`` field is
checked by ``model_validator``.
"""

from __future__ import annotations

import datetime as _dt
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from zer0pa_materials.boundary import RESEARCH_BOUNDARY
from zer0pa_materials.envelope import Envelope


__all__ = [
    "PacketObjective",
    "PromotionVerdict",
    "PacketPublishableTarget",
    "PacketSection",
    "EvidencePacket",
    "PacketBundle",
]


# ----------------------------------------------------------------------------
# Type aliases
# ----------------------------------------------------------------------------

PacketObjective = Literal[
    "battery_solid_electrolyte",
    "thermoelectric_zt",
]

# ``promote`` and ``reject`` mirror the IonicTransportService promotion
# decision; ``defer`` signals "more evidence needed before final routing".
PromotionVerdict = Literal["promote", "defer", "reject"]


_PACKET_ID_RE = re.compile(r"^packet:[A-Za-z0-9._\-:/]+$")


def _utc_now_iso() -> str:
    return _dt.datetime.now(tz=_dt.timezone.utc).isoformat(timespec="microseconds")


# ----------------------------------------------------------------------------
# Helper sections
# ----------------------------------------------------------------------------


class PacketPublishableTarget(BaseModel):
    """Journal / venue target for the publishable paper deliverable.

    PRD §Scope: "the first MVP should produce a publishable paper, not just
    a customer deliverable". This block names the journal the operator
    intends to submit to and the alternative venue if the primary target
    rejects.

    No field is allowed to be empty — RESISTANCE.md ("publishable target
    must be a real journal name") requires both fields to be non-empty.
    """

    model_config = ConfigDict(extra="forbid")

    primary_journal: str = Field(
        ...,
        min_length=1,
        description="Primary journal target, e.g. 'npj Computational Materials'.",
    )
    alternative_journal: str = Field(
        ...,
        min_length=1,
        description="Fallback journal, e.g. 'J. Mater. Chem. A'.",
    )
    target_paper_kind: str = Field(
        default="research_article",
        description="Paper kind: 'research_article', 'short_communication', etc.",
    )
    rationale: str = Field(
        default="",
        description="Short rationale tying the target to the packet's evidence.",
    )


class PacketSection(BaseModel):
    """One section of an EvidencePacket.

    Each section names the section purpose (e.g. ``"phase0_literature"``,
    ``"l2_ensemble"``) and carries the canonical envelope (or list of
    envelopes / dicts) that section captures. The section itself is an
    audit-record-anchored unit: it carries the ``audit_record_ids`` for
    every envelope it contains, so a downstream reader can resolve the
    full chain.
    """

    model_config = ConfigDict(extra="forbid")

    section_name: str = Field(
        ...,
        min_length=1,
        description="Section identifier, e.g. 'l2_ensemble', 'ionic_transport'.",
    )
    summary: str = Field(
        default="",
        description="One-line summary of what this section contains.",
    )
    envelopes: list[dict[str, Any]] = Field(
        default_factory=list,
        description=(
            "Canonical-dict form of every Envelope this section contains. "
            "Round-tripped through ``Envelope.model_validate`` by the validator."
        ),
    )
    raw_payload: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Optional raw payload (e.g. BatteryEvidenceBundle dump, ZtAssemblyResult "
            "dump, Phase 0 extraction summary) that supplements the envelopes."
        ),
    )

    @property
    def audit_record_ids(self) -> list[str]:
        """Return audit_record_ids from every envelope in this section."""
        out: list[str] = []
        for env in self.envelopes:
            audit = env.get("audit", {})
            rec = audit.get("audit_record_id") if isinstance(audit, dict) else None
            if rec:
                out.append(rec)
        return out


class PacketBundle(BaseModel):
    """The canonical mapping from section name to PacketSection.

    Required sections per PRD §Audit Trail And KG (item 9 + 10):

    * ``phase0_literature``                (Phase 0 grounding)
    * ``l6_generated_structure``           (or known control)
    * ``l2_ensemble``                      (DPA + MACE ensemble)
    * ``l1_dft_validation``                (cross-code DFT)
    * ``quantum_slot_h2_lih_gate``         (VQE-vs-FCI gate evidence)
    * ``ionic_transport_full_evidence``    (battery: 6 ionic envelopes)
    * ``l1_5_phonon_dynamical_stability``  (no imaginary modes)
    * ``l3_calphad_phase_set_posterior``   (300/700 K phase posteriors)
    * ``l4_phase_field_morphology``        (advisory)
    * ``l7_orchestration_metadata``        (campaign id, BoTorch trace, decisions)
    * ``alabos_recipe_only_protocol``      (synthesis recipe JSON)
    * ``cross_layer_disagreement``         (aggregator output)
    * ``rights_claim``                     (per data class)
    * ``kg_snapshot``                      (subset of nodes + edges)
    * ``audit_trail_head``                 (hash chain head per category)

    Thermoelectric packets replace ``ionic_transport_full_evidence`` with
    ``zt_assembly`` and drop ``alabos_recipe_only_protocol`` (the
    operator may opt-in to a thermoelectric synthesis recipe in a later
    wave; we still record the recipe-only constraint for transparency).
    """

    model_config = ConfigDict(extra="allow")

    sections: dict[str, PacketSection] = Field(
        ...,
        description="section_name -> PacketSection. Required minimum sections enforced.",
    )

    def section(self, name: str) -> PacketSection | None:
        """Return the named section, or None if absent."""
        return self.sections.get(name)

    def section_names(self) -> list[str]:
        return sorted(self.sections.keys())


# ----------------------------------------------------------------------------
# EvidencePacket — the top-level model
# ----------------------------------------------------------------------------


class EvidencePacket(BaseModel):
    """The Wave 5a publishable-paper packet.

    Constructed by :func:`zer0pa_materials.packets.assemble_battery_packet`
    or :func:`zer0pa_materials.packets.assemble_thermoelectric_packet` and
    consumed by:

    * :func:`zer0pa_materials.packets.validate_evidence_packet`
    * :func:`zer0pa_materials.packets.export_packet_to_ro_crate`
    * the FastAPI ``packets_service`` endpoints
    """

    model_config = ConfigDict(extra="forbid")

    # ---- identification ----------------------------------------------------

    contract_version: Literal["zer0pa.materials.evidence-packet.v1"] = Field(
        default="zer0pa.materials.evidence-packet.v1"
    )
    packet_id: str = Field(
        ..., description="URN starting with 'packet:'."
    )
    objective: PacketObjective = Field(
        ..., description="Packet objective: battery_solid_electrolyte or thermoelectric_zt."
    )
    candidate_id: str = Field(..., pattern=r"^candidate:.+$")
    campaign_id: str = Field(..., pattern=r"^campaign:.+$")
    structure_hash: str = Field(
        ..., pattern=r"^sha256:[0-9a-f]{64}|sha256:none$"
    )
    fixture_id: str | None = Field(
        default=None, description="Stable fixture URN if from a calibrated fixture."
    )

    # ---- boundary block (verbatim) -----------------------------------------

    research_boundary: str = Field(
        ...,
        description="Verbatim copy of zer0pa_materials.boundary.RESEARCH_BOUNDARY.",
    )

    # ---- bundle of sections ------------------------------------------------

    bundle: PacketBundle = Field(..., description="Mapping of section_name -> PacketSection.")

    # ---- orchestration verdict ---------------------------------------------

    promotion_decision: PromotionVerdict = Field(
        ...,
        description=(
            "Final promotion verdict. For battery: from "
            "promote_battery_candidate. For thermoelectric: from the ZT assembler "
            "rank-stability + threshold gate."
        ),
    )
    promotion_rationale: str = Field(
        default="",
        description="One-line rationale aligned with the gate that fired.",
    )

    # ---- publishable paper target ------------------------------------------

    publishable_paper_target: PacketPublishableTarget = Field(
        ..., description="Journal target chosen for this packet's evidence."
    )

    # ---- creation metadata -------------------------------------------------

    created_at: str = Field(default_factory=_utc_now_iso)
    creator: str = Field(default="Zer0pa Materials MVP Packet Generator (Wave 5a)")

    # ---- validators --------------------------------------------------------

    @field_validator("packet_id")
    @classmethod
    def _v_packet_id(cls, v: str) -> str:
        if not _PACKET_ID_RE.match(v):
            raise ValueError(f"packet_id must match {_PACKET_ID_RE.pattern!r}; got {v!r}")
        return v

    @field_validator("research_boundary")
    @classmethod
    def _v_boundary(cls, v: str) -> str:
        if v != RESEARCH_BOUNDARY:
            raise ValueError(
                "EvidencePacket.research_boundary must equal RESEARCH_BOUNDARY exactly. "
                "See zer0pa_materials.boundary.RESEARCH_BOUNDARY."
            )
        return v

    @model_validator(mode="after")
    def _enforce_boundary_in_every_envelope(self) -> "EvidencePacket":
        """Verify every nested envelope round-trips through ``Envelope.model_validate``.

        ``Envelope.model_validate`` itself runs the boundary check, so passing
        every envelope through validation is sufficient to guarantee the
        boundary block is verbatim throughout the packet.
        """
        for section in self.bundle.sections.values():
            for env_dict in section.envelopes:
                # Round-trip; raises BoundaryError if any envelope is missing
                # or has a non-verbatim boundary block.
                Envelope.model_validate(env_dict)
        return self

    # ---- helpers -----------------------------------------------------------

    def section(self, name: str) -> PacketSection | None:
        return self.bundle.section(name)

    def all_envelopes(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for section in self.bundle.sections.values():
            out.extend(section.envelopes)
        return out

    def all_audit_record_ids(self) -> list[str]:
        out: list[str] = []
        for section in self.bundle.sections.values():
            out.extend(section.audit_record_ids)
        return out
