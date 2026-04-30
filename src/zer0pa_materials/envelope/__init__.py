"""Universal layer envelope and contracts (A0).

Public surface:

* :class:`Envelope` — universal layer envelope (PRD §Architecture Invariant).
* :func:`assert_boundary` — re-export from :mod:`zer0pa_materials.boundary`.
* :class:`MaterialsConfig` — typed loader for PRD §Core Config Flags.
* :class:`ArtifactManifest` — entry shape for ``artifacts.jsonl``.
* :class:`FalsifierItem` — row of ``Envelope.falsifier.items``.
* layer-output schemas — :class:`Phase0Output`, :class:`L1DftOutput`,
  :class:`L1QuantumVqeOutput`, :class:`IonicTransportOutput`,
  :class:`L15PhononOutput`, :class:`L2MlipOutput`, :class:`L3CalphadOutput`,
  :class:`L4PhaseFieldOutput`, :class:`L5ContinuumOutput`,
  :class:`L6GenerativeOutput`, :class:`L7CampaignOutput`.
* hashing — :func:`canonical_json_bytes`, :func:`sha256_of`,
  :func:`structure_hash`, :func:`cif_hash_from_text`.
* units — :data:`UREG`, :data:`CANONICAL_UNITS`, :func:`to_canonical`,
  :func:`parse_quantity`.
"""

from zer0pa_materials.boundary import RESEARCH_BOUNDARY, assert_boundary
from zer0pa_materials.envelope.artifacts import (
    ArtifactManifest,
    append_artifact_manifest_jsonl,
    iter_artifact_manifest_jsonl,
    read_artifact_manifest,
    write_artifact_manifest,
)
from zer0pa_materials.envelope.config import MaterialsConfig
from zer0pa_materials.envelope.envelope import (
    AuditBlock,
    BackEdge,
    Backend,
    ConfidenceBand,
    ConfidenceBlock,
    DisagreementBlock,
    DisagreementMetric,
    Envelope,
    EnvelopeContractVersion,
    FalsifierBlock,
    Layer,
    ReuseScope,
    RightsBlock,
    ToolAdapter,
    ENVELOPE_KEY_ORDER,
)
from zer0pa_materials.envelope.falsifier import FalsifierItem, FalsifierStatus
from zer0pa_materials.envelope.hashing import (
    HASH_REGEX,
    canonical_json_bytes,
    cif_hash_from_text,
    parse_minimal_cif,
    sha256_of,
    structure_hash,
)
from zer0pa_materials.envelope.layer_outputs import (
    IonicTransportOutput,
    L15PhononOutput,
    L1DftOutput,
    L1QuantumVqeOutput,
    L2MlipOutput,
    L3CalphadOutput,
    L4PhaseFieldOutput,
    L5ContinuumOutput,
    L6GenerativeOutput,
    L7CampaignOutput,
    LAYER_OUTPUT_REGISTRY,
    LayerOutputBase,
    Phase0Output,
    Phase0ExtractedProperty,
    Phase0PropertyGrounding,
    validate_layer_output,
)
from zer0pa_materials.envelope.units import (
    CANONICAL_UNITS,
    DimensionalityError,
    Quantity,
    UREG,
    format_canonical,
    parse_quantity,
    to_canonical,
)

__all__ = [
    # boundary
    "RESEARCH_BOUNDARY",
    "assert_boundary",
    # envelope
    "Envelope",
    "EnvelopeContractVersion",
    "Layer",
    "Backend",
    "ConfidenceBand",
    "ReuseScope",
    "ToolAdapter",
    "ConfidenceBlock",
    "DisagreementBlock",
    "DisagreementMetric",
    "FalsifierBlock",
    "AuditBlock",
    "RightsBlock",
    "BackEdge",
    "ENVELOPE_KEY_ORDER",
    # falsifier
    "FalsifierItem",
    "FalsifierStatus",
    # layer outputs
    "LayerOutputBase",
    "Phase0Output",
    "Phase0ExtractedProperty",
    "Phase0PropertyGrounding",
    "L1DftOutput",
    "L1QuantumVqeOutput",
    "IonicTransportOutput",
    "L15PhononOutput",
    "L2MlipOutput",
    "L3CalphadOutput",
    "L4PhaseFieldOutput",
    "L5ContinuumOutput",
    "L6GenerativeOutput",
    "L7CampaignOutput",
    "LAYER_OUTPUT_REGISTRY",
    "validate_layer_output",
    # hashing
    "HASH_REGEX",
    "canonical_json_bytes",
    "sha256_of",
    "structure_hash",
    "cif_hash_from_text",
    "parse_minimal_cif",
    # units
    "UREG",
    "Quantity",
    "CANONICAL_UNITS",
    "to_canonical",
    "parse_quantity",
    "format_canonical",
    "DimensionalityError",
    # config
    "MaterialsConfig",
    # artifacts
    "ArtifactManifest",
    "write_artifact_manifest",
    "read_artifact_manifest",
    "append_artifact_manifest_jsonl",
    "iter_artifact_manifest_jsonl",
]
