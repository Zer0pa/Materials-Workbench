"""EMMO-aligned ontology bindings for the Zer0pa Materials KG (PRD §Audit Trail And KG).

The PRD requires:

    Adopt an EMMO-aligned Phase 0 schema with a Zer0pa proprietary extension
    namespace. Runtime APIs use JSON Schema/Pydantic. Each entity carries
    JSON-LD ontology bindings so the KG can export RDF/OWL-compatible views.

This module embeds a *minimal* static subset of EMMO classes covering
``Material``, ``Composition``, ``Phase``, ``Property``, ``Process``, ``Model``,
``Simulation``, ``Measurement``, ``Reasoning``, and ``Provenance``. We do
NOT fetch the EMMO ontology at runtime (that would create a network
dependency in CPU-side build); instead we cite canonical IRIs by
reference.

Namespaces
----------

* ``EMMO_BASE_IRI`` — `https://w3id.org/emmo#` is the EMMO 1.x stable IRI.
  EMMO 1.0 was released in March 2024; the IRIs are documented at
  https://emmo-repo.github.io/.

* ``OPTIMADE_BASE_IRI`` — `https://schema.optimade.org/` for the OPTIMADE
  spec; the live spec version we target is 1.3 (PRD §Audit Trail And KG:
  "OPTIMADE v1.3-first, v1.2-compatible structure/database interop").

* ``PROV_BASE_IRI`` — `http://www.w3.org/ns/prov#` for PROV-O.

* ``SPDX_BASE_IRI`` — `http://spdx.org/licenses/` for SPDX license IRIs.

* ``ZER0PA_EXTENSION_BASE_IRI`` — `https://schema.zer0pa.ai/materials#` for
  fields EMMO does not cover (Zer0pa-specific decisions, falsifiers,
  audit-chain edges).

KG-node → EMMO mapping
----------------------

The 27 KG node types from PRD §Audit Trail And KG each map to one or more
EMMO terms via ``MAPS_TO_ONTOLOGY`` edges. Where EMMO doesn't have a term,
we map to a ``zer0pa:`` IRI with a documented rationale.

Implementation note: EMMO uses UUID-suffixed IRIs (e.g.
``EMMO_4207e895_8b83_4318_996a_72cfb32acd94`` for Material). Because
overnight-execution must be CPU-only and offline, the UUIDs we encode here
are taken from the published EMMO 1.x stable terms. If a downstream wave
imports a richer ontology, it can map our short Zer0pa-extension IRIs to
the canonical EMMO IRIs without breaking the chain.

Verification status (deep-research, 2026-04-30 — see
``phases/Deep-Research/emmo-iri-verification.md``):
* Live-verified against EMMO 1.0.3 / domain ontologies: ``Material``,
  ``Property``, ``Process``, ``Measurement``.
* UUID resolution unverified (annotation-only, runtime not affected):
  ``Composition``, ``Structure``, ``Phase``, ``Model``, ``Simulation``,
  ``Reasoning``. Pending Wave 4c EMMOntoPy-based resolution; downstream
  waves can patch the UUIDs in place without code changes elsewhere
  because the KG ``MAPS_TO_ONTOLOGY`` edge layer references these
  constants by name.
* See ``audit/runtime/sources.jsonl`` for per-IRI ``SourceManifest`` /
  ``BlockedSourceManifest`` rows from the deep-research subagent.
"""

from __future__ import annotations

from typing import Final

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "EMMO_BASE_IRI",
    "OPTIMADE_BASE_IRI",
    "OPTIMADE_VERSION",
    "PROV_BASE_IRI",
    "SPDX_BASE_IRI",
    "ZER0PA_EXTENSION_BASE_IRI",
    "EmmoTerm",
    "OntologyMapping",
    "EMMO_TERMS",
    "KG_NODE_TO_EMMO",
    "KG_EDGE_TO_EMMO",
    "iri_for_kg_node",
    "iri_for_kg_edge",
]


# ----------------------------------------------------------------------------
# Namespace constants
# ----------------------------------------------------------------------------


EMMO_BASE_IRI: Final[str] = "https://w3id.org/emmo#"
OPTIMADE_BASE_IRI: Final[str] = "https://schema.optimade.org/"
OPTIMADE_VERSION: Final[str] = "1.3"
PROV_BASE_IRI: Final[str] = "http://www.w3.org/ns/prov#"
SPDX_BASE_IRI: Final[str] = "http://spdx.org/licenses/"
ZER0PA_EXTENSION_BASE_IRI: Final[str] = "https://schema.zer0pa.ai/materials#"


# ----------------------------------------------------------------------------
# Term model
# ----------------------------------------------------------------------------


class EmmoTerm(BaseModel):
    """Minimal EMMO term descriptor."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    iri: str = Field(..., description="Full IRI (EMMO_<UUID> or zer0pa: extension).")
    pref_label: str = Field(..., description="Human-readable preferred label.")
    parents: tuple[str, ...] = Field(
        default_factory=tuple, description="Parent IRIs (subClassOf chain)."
    )
    properties: tuple[str, ...] = Field(
        default_factory=tuple, description="Object properties associated with this term."
    )
    note: str = Field(default="", description="Documentation / rationale.")


class OntologyMapping(BaseModel):
    """Mapping from a KG node/edge type to one or more ontology IRIs."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(..., description="KG node or edge type name.")
    iris: tuple[str, ...] = Field(..., description="Ontology term IRIs.")
    primary_iri: str = Field(..., description="The canonical IRI to emit in MAPS_TO_ONTOLOGY.")
    note: str = Field(default="", description="Documentation / rationale.")


# ----------------------------------------------------------------------------
# Static EMMO term subset
# ----------------------------------------------------------------------------

# Each term carries its EMMO 1.x UUID (where one exists in EMMO Materials and
# Process branches). Where EMMO doesn't have a term, we use the Zer0pa
# extension namespace with a clear note.
#
# The UUIDs are *examples* drawn from the public EMMO 1.x release; downstream
# adapters may override the IRI without changing the keys here.

EMMO_TERMS: Final[dict[str, EmmoTerm]] = {
    "Material": EmmoTerm(
        iri=f"{EMMO_BASE_IRI}EMMO_4207e895_8b83_4318_996a_72cfb32acd94",
        pref_label="Material",
        parents=(f"{EMMO_BASE_IRI}EMMO_2d23bf12_b6a8_4824_b0a4_2ebd33fc15a4",),  # Substantial
        properties=(),
        note="EMMO Material; the substantial entity with composition and structure.",
    ),
    "Composition": EmmoTerm(
        iri=f"{EMMO_BASE_IRI}EMMO_25aacccd_5d10_4dad_a6d7_4d5e35e18d10",
        pref_label="Composition",
        parents=(f"{EMMO_BASE_IRI}EMMO_4207e895_8b83_4318_996a_72cfb32acd94",),
        properties=(),
        note="EMMO Composition; the relational structure between Material and constituents.",
    ),
    "Structure": EmmoTerm(
        iri=f"{EMMO_BASE_IRI}EMMO_8aa4afc1_3e57_4afe_84d1_caa0c4dc5a72",
        pref_label="Structure",
        parents=(f"{EMMO_BASE_IRI}EMMO_4207e895_8b83_4318_996a_72cfb32acd94",),
        properties=(),
        note="EMMO crystal/atomic structure; lattice vectors plus site basis.",
    ),
    "Phase": EmmoTerm(
        iri=f"{EMMO_BASE_IRI}EMMO_b35e92d7_7fa0_4661_b6cb_1be7f9d6f6e0",
        pref_label="Phase",
        parents=(f"{EMMO_BASE_IRI}EMMO_4207e895_8b83_4318_996a_72cfb32acd94",),
        properties=(),
        note="EMMO Phase; equilibrium state with bounded composition + structure.",
    ),
    "Property": EmmoTerm(
        iri=f"{EMMO_BASE_IRI}EMMO_b7bcff25_ffc3_474e_9ab5_01b1664bd4ba",
        pref_label="Property",
        parents=(f"{EMMO_BASE_IRI}EMMO_2d23bf12_b6a8_4824_b0a4_2ebd33fc15a4",),
        properties=(),
        note="EMMO Property; intrinsic measurable quantity of a Material.",
    ),
    "Process": EmmoTerm(
        iri=f"{EMMO_BASE_IRI}EMMO_43e9a05d_98af_41b4_92f6_00f79a09bfce",
        pref_label="Process",
        parents=(f"{EMMO_BASE_IRI}EMMO_2d23bf12_b6a8_4824_b0a4_2ebd33fc15a4",),
        properties=(),
        note="EMMO Process; time-extended causal evolution of substantial entities.",
    ),
    "Model": EmmoTerm(
        iri=f"{EMMO_BASE_IRI}EMMO_5079e106_4f4f_4e98_897a_a4a4d2bbed47",
        pref_label="Model",
        parents=(f"{EMMO_BASE_IRI}EMMO_2d23bf12_b6a8_4824_b0a4_2ebd33fc15a4",),
        properties=(),
        note="EMMO Model; a representational mathematical structure.",
    ),
    "Simulation": EmmoTerm(
        iri=f"{EMMO_BASE_IRI}EMMO_e97af6ec_4371_4bbc_8936_2c2ace4d2293",
        pref_label="Simulation",
        parents=(f"{EMMO_BASE_IRI}EMMO_43e9a05d_98af_41b4_92f6_00f79a09bfce",),  # Process
        properties=(),
        note="EMMO Simulation; a Process whose participants are Models.",
    ),
    "Measurement": EmmoTerm(
        iri=f"{EMMO_BASE_IRI}EMMO_463bcfda_867b_41d8_a96d_a26034775c0d",
        pref_label="Measurement",
        parents=(f"{EMMO_BASE_IRI}EMMO_43e9a05d_98af_41b4_92f6_00f79a09bfce",),
        properties=(),
        note="EMMO Measurement; a Process producing a Property value.",
    ),
    "Reasoning": EmmoTerm(
        iri=f"{EMMO_BASE_IRI}EMMO_b863702a_4a3c_4d24_b62f_98edcabd4b07",
        pref_label="Reasoning",
        parents=(f"{EMMO_BASE_IRI}EMMO_43e9a05d_98af_41b4_92f6_00f79a09bfce",),
        properties=(),
        note="EMMO Reasoning; an inference Process over Models and observations.",
    ),
    "Provenance": EmmoTerm(
        iri=f"{ZER0PA_EXTENSION_BASE_IRI}Provenance",
        pref_label="Provenance",
        parents=(f"{PROV_BASE_IRI}Activity",),
        properties=(),
        note=(
            "Zer0pa extension: bundles PROV-O Entity/Activity/Agent triples with "
            "the audit hash chain anchor. Maps to PROV-O for export."
        ),
    ),
}


# ----------------------------------------------------------------------------
# KG node types → EMMO mapping
# ----------------------------------------------------------------------------

# The 27 node types from PRD §Audit Trail And KG. Each maps to one or more
# of the EMMO terms above (or to a zer0pa: extension IRI when no EMMO term
# exists).

_E = EMMO_TERMS  # short alias


KG_NODE_TO_EMMO: Final[dict[str, OntologyMapping]] = {
    "Campaign": OntologyMapping(
        name="Campaign",
        iris=(f"{ZER0PA_EXTENSION_BASE_IRI}Campaign", _E["Process"].iri),
        primary_iri=f"{ZER0PA_EXTENSION_BASE_IRI}Campaign",
        note="Zer0pa concept; subClassOf EMMO Process for export.",
    ),
    "CustomerTenant": OntologyMapping(
        name="CustomerTenant",
        iris=(f"{ZER0PA_EXTENSION_BASE_IRI}CustomerTenant", f"{PROV_BASE_IRI}Agent"),
        primary_iri=f"{ZER0PA_EXTENSION_BASE_IRI}CustomerTenant",
        note="Zer0pa data-sovereignty entity; subClassOf prov:Agent.",
    ),
    "Objective": OntologyMapping(
        name="Objective",
        iris=(f"{ZER0PA_EXTENSION_BASE_IRI}Objective",),
        primary_iri=f"{ZER0PA_EXTENSION_BASE_IRI}Objective",
        note="Goal/target description for a campaign.",
    ),
    "AcceptanceGate": OntologyMapping(
        name="AcceptanceGate",
        iris=(f"{ZER0PA_EXTENSION_BASE_IRI}AcceptanceGate",),
        primary_iri=f"{ZER0PA_EXTENSION_BASE_IRI}AcceptanceGate",
        note="Threshold-style gate associated with a falsifier.",
    ),
    "Hypothesis": OntologyMapping(
        name="Hypothesis",
        iris=(f"{ZER0PA_EXTENSION_BASE_IRI}Hypothesis", _E["Reasoning"].iri),
        primary_iri=f"{ZER0PA_EXTENSION_BASE_IRI}Hypothesis",
        note="Pre-validation candidate claim; subClassOf EMMO Reasoning.",
    ),
    "CandidateMaterial": OntologyMapping(
        name="CandidateMaterial",
        iris=(_E["Material"].iri,),
        primary_iri=_E["Material"].iri,
        note="EMMO Material; the substantial entity under evaluation.",
    ),
    "Composition": OntologyMapping(
        name="Composition",
        iris=(_E["Composition"].iri,),
        primary_iri=_E["Composition"].iri,
        note="EMMO Composition.",
    ),
    "Structure": OntologyMapping(
        name="Structure",
        iris=(_E["Structure"].iri,),
        primary_iri=_E["Structure"].iri,
        note="EMMO Structure.",
    ),
    "Phase": OntologyMapping(
        name="Phase",
        iris=(_E["Phase"].iri,),
        primary_iri=_E["Phase"].iri,
        note="EMMO Phase.",
    ),
    "PropertyObservation": OntologyMapping(
        name="PropertyObservation",
        iris=(_E["Property"].iri, _E["Measurement"].iri),
        primary_iri=_E["Property"].iri,
        note="A measured / computed Property value.",
    ),
    "SimulationJob": OntologyMapping(
        name="SimulationJob",
        iris=(_E["Simulation"].iri, f"{PROV_BASE_IRI}Activity"),
        primary_iri=_E["Simulation"].iri,
        note="EMMO Simulation; PROV-O Activity for export.",
    ),
    "SimulationResult": OntologyMapping(
        name="SimulationResult",
        iris=(_E["Property"].iri, f"{PROV_BASE_IRI}Entity"),
        primary_iri=_E["Property"].iri,
        note="Output of a SimulationJob; PROV-O Entity for export.",
    ),
    "ModelCheckpoint": OntologyMapping(
        name="ModelCheckpoint",
        iris=(_E["Model"].iri, f"{PROV_BASE_IRI}Entity"),
        primary_iri=_E["Model"].iri,
        note="A versioned MLIP/CALPHAD/etc model artifact.",
    ),
    "Dataset": OntologyMapping(
        name="Dataset",
        iris=(f"{ZER0PA_EXTENSION_BASE_IRI}Dataset", f"{PROV_BASE_IRI}Entity"),
        primary_iri=f"{ZER0PA_EXTENSION_BASE_IRI}Dataset",
        note="Curated structured data input.",
    ),
    "LiteratureSource": OntologyMapping(
        name="LiteratureSource",
        iris=(f"{ZER0PA_EXTENSION_BASE_IRI}LiteratureSource", f"{PROV_BASE_IRI}Entity"),
        primary_iri=f"{ZER0PA_EXTENSION_BASE_IRI}LiteratureSource",
        note="DOI/page/table-grounded scientific literature reference.",
    ),
    "OPTIMADEResource": OntologyMapping(
        name="OPTIMADEResource",
        iris=(
            f"{OPTIMADE_BASE_IRI}{OPTIMADE_VERSION}/Resource",
            f"{ZER0PA_EXTENSION_BASE_IRI}OPTIMADEResource",
        ),
        primary_iri=f"{OPTIMADE_BASE_IRI}{OPTIMADE_VERSION}/Resource",
        note=f"OPTIMADE v{OPTIMADE_VERSION} resource; structure/property/database entry.",
    ),
    "SynthesisRecipe": OntologyMapping(
        name="SynthesisRecipe",
        iris=(_E["Process"].iri, f"{ZER0PA_EXTENSION_BASE_IRI}SynthesisRecipe"),
        primary_iri=f"{ZER0PA_EXTENSION_BASE_IRI}SynthesisRecipe",
        note="EMMO Process specialised to synthesis; AlabOS protocol candidate.",
    ),
    "Artifact": OntologyMapping(
        name="Artifact",
        iris=(f"{PROV_BASE_IRI}Entity", f"{ZER0PA_EXTENSION_BASE_IRI}Artifact"),
        primary_iri=f"{PROV_BASE_IRI}Entity",
        note="PROV-O Entity for any produced binary/structured file.",
    ),
    "SourceManifest": OntologyMapping(
        name="SourceManifest",
        iris=(f"{ZER0PA_EXTENSION_BASE_IRI}SourceManifest",),
        primary_iri=f"{ZER0PA_EXTENSION_BASE_IRI}SourceManifest",
        note="Zer0pa source manifest (PRD §Deep Research Policy).",
    ),
    "Falsifier": OntologyMapping(
        name="Falsifier",
        iris=(f"{ZER0PA_EXTENSION_BASE_IRI}Falsifier",),
        primary_iri=f"{ZER0PA_EXTENSION_BASE_IRI}Falsifier",
        note="Zer0pa falsifier; threshold check with status.",
    ),
    "DisagreementMetric": OntologyMapping(
        name="DisagreementMetric",
        iris=(f"{ZER0PA_EXTENSION_BASE_IRI}DisagreementMetric",),
        primary_iri=f"{ZER0PA_EXTENSION_BASE_IRI}DisagreementMetric",
        note="Cross-model / cross-solver disagreement metric.",
    ),
    "Decision": OntologyMapping(
        name="Decision",
        iris=(f"{ZER0PA_EXTENSION_BASE_IRI}Decision", _E["Reasoning"].iri),
        primary_iri=f"{ZER0PA_EXTENSION_BASE_IRI}Decision",
        note="A recorded routing/architecture decision; subClassOf EMMO Reasoning.",
    ),
    "Actor": OntologyMapping(
        name="Actor",
        iris=(f"{PROV_BASE_IRI}Agent",),
        primary_iri=f"{PROV_BASE_IRI}Agent",
        note="PROV-O Agent (lead, subagent, policy, user).",
    ),
    "Tool": OntologyMapping(
        name="Tool",
        iris=(f"{PROV_BASE_IRI}SoftwareAgent", _E["Model"].iri),
        primary_iri=f"{PROV_BASE_IRI}SoftwareAgent",
        note="PROV-O SoftwareAgent; the tool/adapter/engine.",
    ),
    "ComputeEnvironment": OntologyMapping(
        name="ComputeEnvironment",
        iris=(f"{ZER0PA_EXTENSION_BASE_IRI}ComputeEnvironment",),
        primary_iri=f"{ZER0PA_EXTENSION_BASE_IRI}ComputeEnvironment",
        note="Hardware + OS + driver + CUDA stack identifier.",
    ),
    "License": OntologyMapping(
        name="License",
        iris=(f"{SPDX_BASE_IRI}", f"{ZER0PA_EXTENSION_BASE_IRI}License"),
        primary_iri=f"{SPDX_BASE_IRI}",
        note="SPDX license expression; nodes carry the expression as a property.",
    ),
    "RightsClaim": OntologyMapping(
        name="RightsClaim",
        iris=(f"{ZER0PA_EXTENSION_BASE_IRI}RightsClaim",),
        primary_iri=f"{ZER0PA_EXTENSION_BASE_IRI}RightsClaim",
        note="Zer0pa data-sovereignty rights claim.",
    ),
    "OntologyTerm": OntologyMapping(
        name="OntologyTerm",
        iris=(f"{ZER0PA_EXTENSION_BASE_IRI}OntologyTerm",),
        primary_iri=f"{ZER0PA_EXTENSION_BASE_IRI}OntologyTerm",
        note="A reified ontology term; carries its own IRI as a property.",
    ),
}


# ----------------------------------------------------------------------------
# KG edge types → EMMO/PROV mapping
# ----------------------------------------------------------------------------

KG_EDGE_TO_EMMO: Final[dict[str, OntologyMapping]] = {
    "DERIVED_FROM": OntologyMapping(
        name="DERIVED_FROM",
        iris=(f"{PROV_BASE_IRI}wasDerivedFrom",),
        primary_iri=f"{PROV_BASE_IRI}wasDerivedFrom",
        note="PROV-O wasDerivedFrom.",
    ),
    "USED": OntologyMapping(
        name="USED",
        iris=(f"{PROV_BASE_IRI}used",),
        primary_iri=f"{PROV_BASE_IRI}used",
        note="PROV-O used.",
    ),
    "GENERATED": OntologyMapping(
        name="GENERATED",
        iris=(f"{PROV_BASE_IRI}generated",),
        primary_iri=f"{PROV_BASE_IRI}generated",
        note="PROV-O generated.",
    ),
    "ATTRIBUTED_TO": OntologyMapping(
        name="ATTRIBUTED_TO",
        iris=(f"{PROV_BASE_IRI}wasAttributedTo",),
        primary_iri=f"{PROV_BASE_IRI}wasAttributedTo",
        note="PROV-O wasAttributedTo.",
    ),
    "HAS_STRUCTURE": OntologyMapping(
        name="HAS_STRUCTURE",
        iris=(f"{ZER0PA_EXTENSION_BASE_IRI}hasStructure",),
        primary_iri=f"{ZER0PA_EXTENSION_BASE_IRI}hasStructure",
        note="Material has crystal structure.",
    ),
    "HAS_COMPOSITION": OntologyMapping(
        name="HAS_COMPOSITION",
        iris=(f"{ZER0PA_EXTENSION_BASE_IRI}hasComposition",),
        primary_iri=f"{ZER0PA_EXTENSION_BASE_IRI}hasComposition",
        note="Material has composition.",
    ),
    "HAS_PROPERTY": OntologyMapping(
        name="HAS_PROPERTY",
        iris=(f"{ZER0PA_EXTENSION_BASE_IRI}hasProperty",),
        primary_iri=f"{ZER0PA_EXTENSION_BASE_IRI}hasProperty",
        note="Material has property observation.",
    ),
    "PREDICTED_BY": OntologyMapping(
        name="PREDICTED_BY",
        iris=(f"{ZER0PA_EXTENSION_BASE_IRI}predictedBy",),
        primary_iri=f"{ZER0PA_EXTENSION_BASE_IRI}predictedBy",
        note="Property predicted by simulation/model.",
    ),
    "MEASURED_BY": OntologyMapping(
        name="MEASURED_BY",
        iris=(f"{ZER0PA_EXTENSION_BASE_IRI}measuredBy",),
        primary_iri=f"{ZER0PA_EXTENSION_BASE_IRI}measuredBy",
        note="Property measured by experiment/instrument.",
    ),
    "HAS_UNCERTAINTY": OntologyMapping(
        name="HAS_UNCERTAINTY",
        iris=(f"{ZER0PA_EXTENSION_BASE_IRI}hasUncertainty",),
        primary_iri=f"{ZER0PA_EXTENSION_BASE_IRI}hasUncertainty",
        note="Property has stated uncertainty (sigma, CI, etc).",
    ),
    "AGREES_WITH": OntologyMapping(
        name="AGREES_WITH",
        iris=(f"{ZER0PA_EXTENSION_BASE_IRI}agreesWith",),
        primary_iri=f"{ZER0PA_EXTENSION_BASE_IRI}agreesWith",
        note="Two model/measurement results agree within tolerance.",
    ),
    "CONTRADICTS": OntologyMapping(
        name="CONTRADICTS",
        iris=(f"{ZER0PA_EXTENSION_BASE_IRI}contradicts",),
        primary_iri=f"{ZER0PA_EXTENSION_BASE_IRI}contradicts",
        note="Two model/measurement results contradict.",
    ),
    "PASSES_GATE": OntologyMapping(
        name="PASSES_GATE",
        iris=(f"{ZER0PA_EXTENSION_BASE_IRI}passesGate",),
        primary_iri=f"{ZER0PA_EXTENSION_BASE_IRI}passesGate",
        note="Candidate passes acceptance gate.",
    ),
    "FAILS_GATE": OntologyMapping(
        name="FAILS_GATE",
        iris=(f"{ZER0PA_EXTENSION_BASE_IRI}failsGate",),
        primary_iri=f"{ZER0PA_EXTENSION_BASE_IRI}failsGate",
        note="Candidate fails acceptance gate.",
    ),
    "ROUTED_TO": OntologyMapping(
        name="ROUTED_TO",
        iris=(f"{ZER0PA_EXTENSION_BASE_IRI}routedTo",),
        primary_iri=f"{ZER0PA_EXTENSION_BASE_IRI}routedTo",
        note="Disagreement metric routes candidate to higher fidelity.",
    ),
    "CITES": OntologyMapping(
        name="CITES",
        iris=(f"{PROV_BASE_IRI}wasInfluencedBy", f"{ZER0PA_EXTENSION_BASE_IRI}cites"),
        primary_iri=f"{ZER0PA_EXTENSION_BASE_IRI}cites",
        note="Hypothesis/decision cites a literature source.",
    ),
    "MAPS_TO_ONTOLOGY": OntologyMapping(
        name="MAPS_TO_ONTOLOGY",
        iris=(f"{ZER0PA_EXTENSION_BASE_IRI}mapsToOntology",),
        primary_iri=f"{ZER0PA_EXTENSION_BASE_IRI}mapsToOntology",
        note="KG node maps to one or more ontology terms (EMMO/OPTIMADE/SPDX/PROV-O).",
    ),
    "LICENSED_UNDER": OntologyMapping(
        name="LICENSED_UNDER",
        iris=(f"{ZER0PA_EXTENSION_BASE_IRI}licensedUnder",),
        primary_iri=f"{ZER0PA_EXTENSION_BASE_IRI}licensedUnder",
        note="Artifact / dataset / model is licensed under SPDX expression.",
    ),
    "OWNED_BY": OntologyMapping(
        name="OWNED_BY",
        iris=(f"{ZER0PA_EXTENSION_BASE_IRI}ownedBy",),
        primary_iri=f"{ZER0PA_EXTENSION_BASE_IRI}ownedBy",
        note="Asset ownership (customer/zer0pa/public/split).",
    ),
    "PERMITTED_FOR": OntologyMapping(
        name="PERMITTED_FOR",
        iris=(f"{ZER0PA_EXTENSION_BASE_IRI}permittedFor",),
        primary_iri=f"{ZER0PA_EXTENSION_BASE_IRI}permittedFor",
        note="Asset permitted-for use scope (tenant_only/shared_learning/open_science).",
    ),
    "REDACTED_AS": OntologyMapping(
        name="REDACTED_AS",
        iris=(f"{ZER0PA_EXTENSION_BASE_IRI}redactedAs",),
        primary_iri=f"{ZER0PA_EXTENSION_BASE_IRI}redactedAs",
        note="Asset's required redaction policy for cross-tenant export.",
    ),
    "SUPERSEDES": OntologyMapping(
        name="SUPERSEDES",
        iris=(f"{PROV_BASE_IRI}wasRevisionOf", f"{ZER0PA_EXTENSION_BASE_IRI}supersedes"),
        primary_iri=f"{PROV_BASE_IRI}wasRevisionOf",
        note="A new node revises (supersedes) a prior node.",
    ),
    "CALIBRATED_ON": OntologyMapping(
        name="CALIBRATED_ON",
        iris=(f"{ZER0PA_EXTENSION_BASE_IRI}calibratedOn",),
        primary_iri=f"{ZER0PA_EXTENSION_BASE_IRI}calibratedOn",
        note="Model checkpoint was calibrated on a dataset.",
    ),
    "FINETUNED_FROM": OntologyMapping(
        name="FINETUNED_FROM",
        iris=(f"{ZER0PA_EXTENSION_BASE_IRI}finetunedFrom",),
        primary_iri=f"{ZER0PA_EXTENSION_BASE_IRI}finetunedFrom",
        note="Model checkpoint was fine-tuned from a parent checkpoint.",
    ),
    "MEMBER_OF_ENSEMBLE": OntologyMapping(
        name="MEMBER_OF_ENSEMBLE",
        iris=(f"{ZER0PA_EXTENSION_BASE_IRI}memberOfEnsemble",),
        primary_iri=f"{ZER0PA_EXTENSION_BASE_IRI}memberOfEnsemble",
        note="Model checkpoint is a member of an ensemble (DPA/MACE).",
    ),
}


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------


def iri_for_kg_node(node_type: str) -> str:
    """Return the primary IRI for a KG node type."""
    if node_type not in KG_NODE_TO_EMMO:
        raise KeyError(f"unknown KG node type: {node_type!r}")
    return KG_NODE_TO_EMMO[node_type].primary_iri


def iri_for_kg_edge(edge_type: str) -> str:
    """Return the primary IRI for a KG edge type."""
    if edge_type not in KG_EDGE_TO_EMMO:
        raise KeyError(f"unknown KG edge type: {edge_type!r}")
    return KG_EDGE_TO_EMMO[edge_type].primary_iri
