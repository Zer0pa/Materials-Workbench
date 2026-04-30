"""RDF / PROV-O export for the SQLite KG.

Walks every node/edge in :class:`zer0pa_materials.audit.kg.MaterialsKG` and
emits a Turtle (.ttl) document. Round-trips through ``rdflib``: loading the
emitted Turtle back into a graph yields the same node/edge counts.

The export uses:

* PROV-O Entity / Activity / Agent classes for ``Artifact``, ``SimulationJob``,
  ``Actor`` (and their cousins).
* SPDX license IRIs for ``License`` nodes (the SPDX expression is a node
  property; we attach it via ``rdfs:label`` plus a Zer0pa extension predicate).
* EMMO IRIs (or Zer0pa-extension IRIs) per the mapping in
  :mod:`zer0pa_materials.ontology.emmo`.

The Turtle file lives at ``${AUDIT_DIR}/kg_export.ttl`` by default; the
caller can override the path.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF, RDFS, XSD

from zer0pa_materials.audit.kg import KGEdge, KGNode, MaterialsKG
from zer0pa_materials.ontology.emmo import (
    KG_EDGE_TO_EMMO,
    KG_NODE_TO_EMMO,
    PROV_BASE_IRI,
    SPDX_BASE_IRI,
    ZER0PA_EXTENSION_BASE_IRI,
)

__all__ = [
    "export_kg_to_turtle",
    "export_kg_graph",
    "round_trip_validate",
]


# ----------------------------------------------------------------------------
# Namespaces
# ----------------------------------------------------------------------------


PROV = Namespace(PROV_BASE_IRI)
ZER0PA = Namespace(ZER0PA_EXTENSION_BASE_IRI)
SPDX = Namespace(SPDX_BASE_IRI)


# Map KG node IDs to a stable URN (so they have a hashable IRI).
def _node_iri(node_id: str) -> URIRef:
    safe = node_id.replace(":", "/")
    return URIRef(f"{ZER0PA_EXTENSION_BASE_IRI}node/{safe}")


def _edge_iri(edge_id: str) -> URIRef:
    safe = edge_id.replace(":", "/")
    return URIRef(f"{ZER0PA_EXTENSION_BASE_IRI}edge/{safe}")


# ----------------------------------------------------------------------------
# Export
# ----------------------------------------------------------------------------


def export_kg_graph(kg: MaterialsKG) -> Graph:
    """Build an in-memory :class:`rdflib.Graph` from the KG."""
    g = Graph()
    g.bind("prov", PROV)
    g.bind("zer0pa", ZER0PA)
    g.bind("spdx", SPDX)

    nodes_seen: set[str] = set()
    for node in kg.iter_nodes():
        nodes_seen.add(node.node_id)
        _emit_node(g, node)
    for edge in kg.iter_edges():
        _emit_edge(g, edge, nodes_seen)
    return g


def export_kg_to_turtle(kg: MaterialsKG, path: str | Path) -> Path:
    """Export the KG to a Turtle file.

    Returns the resolved path on success.
    """
    out = Path(path).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    g = export_kg_graph(kg)
    g.serialize(destination=str(out), format="turtle", encoding="utf-8")
    return out


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------


def _emit_node(g: Graph, node: KGNode) -> None:
    """Emit RDF triples for a single KG node."""
    iri = _node_iri(node.node_id)

    # rdf:type ← ontology IRI
    g.add((iri, RDF.type, URIRef(node.ontology_term)))

    # rdf:type ← KGNodeType IRI (the named type so RDF consumers see e.g.
    # the EMMO Material type AND the canonical KGNodeType label).
    type_mapping = KG_NODE_TO_EMMO.get(node.node_type.value)
    if type_mapping is not None:
        for additional_iri in type_mapping.iris:
            if additional_iri != node.ontology_term:
                g.add((iri, RDF.type, URIRef(additional_iri)))

    # rdfs:label ← node_id
    g.add((iri, RDFS.label, Literal(node.node_id)))

    # zer0pa:nodeType
    g.add((iri, ZER0PA.nodeType, Literal(node.node_type.value)))
    # zer0pa:runId
    g.add((iri, ZER0PA.runId, Literal(node.run_id)))
    # zer0pa:createdAt
    g.add(
        (iri, ZER0PA.createdAt, Literal(node.created_at, datatype=XSD.dateTime))
    )

    # PROV-O attribution: SimulationJob / Actor / Artifact get prov: triples.
    if node.node_type.value == "SimulationJob":
        g.add((iri, RDF.type, PROV.Activity))
    if node.node_type.value == "Actor":
        g.add((iri, RDF.type, PROV.Agent))
    if node.node_type.value == "Artifact":
        g.add((iri, RDF.type, PROV.Entity))

    # Properties → predicates under zer0pa: prefix.
    for k, v in node.properties.items():
        pred = URIRef(f"{ZER0PA_EXTENSION_BASE_IRI}{k}")
        if isinstance(v, bool):
            g.add((iri, pred, Literal(v, datatype=XSD.boolean)))
        elif isinstance(v, int):
            g.add((iri, pred, Literal(v, datatype=XSD.integer)))
        elif isinstance(v, float):
            g.add((iri, pred, Literal(v, datatype=XSD.double)))
        else:
            g.add((iri, pred, Literal(str(v))))


def _emit_edge(g: Graph, edge: KGEdge, nodes_seen: set[str]) -> None:
    """Emit RDF triples for a single KG edge."""
    src_iri = _node_iri(edge.src_id)
    dst_iri = _node_iri(edge.dst_id)

    mapping = KG_EDGE_TO_EMMO.get(edge.edge_type.value)
    if mapping is None:
        # Should never happen — KGEdgeType enum is the source of truth.
        return
    pred_iri = URIRef(mapping.primary_iri)
    g.add((src_iri, pred_iri, dst_iri))

    # Reify the edge so we can attach properties / metadata.
    eiri = _edge_iri(edge.edge_id)
    g.add((eiri, RDF.type, RDF.Statement))
    g.add((eiri, RDF.subject, src_iri))
    g.add((eiri, RDF.predicate, pred_iri))
    g.add((eiri, RDF.object, dst_iri))
    g.add((eiri, ZER0PA.edgeType, Literal(edge.edge_type.value)))
    g.add((eiri, ZER0PA.runId, Literal(edge.run_id)))
    g.add((eiri, ZER0PA.createdAt, Literal(edge.created_at, datatype=XSD.dateTime)))
    for k, v in edge.properties.items():
        pred = URIRef(f"{ZER0PA_EXTENSION_BASE_IRI}{k}")
        g.add((eiri, pred, Literal(str(v))))


# ----------------------------------------------------------------------------
# Round-trip validation
# ----------------------------------------------------------------------------


def round_trip_validate(kg: MaterialsKG, ttl_path: str | Path) -> tuple[int, int]:
    """Round-trip validate: SQLite → Turtle → load → count.

    Re-loads the just-emitted Turtle and counts:

    * distinct *node* IRIs in subject/object position
    * distinct *edge* IRIs (via reified Statement subjects)

    Returns ``(loaded_node_count, loaded_edge_count)``. The caller asserts
    against ``kg.count_nodes()`` / ``kg.count_edges()``.
    """
    g = Graph()
    g.parse(str(ttl_path), format="turtle")
    # Count node IRIs by selecting subjects with rdfs:label (we always emit
    # a label per node).
    node_subjects = {s for s, _, _ in g.triples((None, RDFS.label, None))}
    edge_subjects = {s for s, _, _ in g.triples((None, RDF.type, RDF.Statement))}
    return len(node_subjects), len(edge_subjects)
