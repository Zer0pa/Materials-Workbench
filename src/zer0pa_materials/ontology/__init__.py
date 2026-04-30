"""Ontology bindings for the Zer0pa Materials KG.

Public surface:

* :mod:`zer0pa_materials.ontology.emmo` — EMMO term bindings, KG-node-to-EMMO
  mapping, OPTIMADE / Zer0pa-extension namespaces.
"""

from zer0pa_materials.ontology.emmo import (
    EMMO_BASE_IRI,
    EMMO_TERMS,
    KG_NODE_TO_EMMO,
    KG_EDGE_TO_EMMO,
    OPTIMADE_BASE_IRI,
    OPTIMADE_VERSION,
    PROV_BASE_IRI,
    SPDX_BASE_IRI,
    ZER0PA_EXTENSION_BASE_IRI,
    EmmoTerm,
    OntologyMapping,
    iri_for_kg_edge,
    iri_for_kg_node,
)

__all__ = [
    "EMMO_BASE_IRI",
    "EMMO_TERMS",
    "KG_NODE_TO_EMMO",
    "KG_EDGE_TO_EMMO",
    "OPTIMADE_BASE_IRI",
    "OPTIMADE_VERSION",
    "PROV_BASE_IRI",
    "SPDX_BASE_IRI",
    "ZER0PA_EXTENSION_BASE_IRI",
    "EmmoTerm",
    "OntologyMapping",
    "iri_for_kg_edge",
    "iri_for_kg_node",
]
