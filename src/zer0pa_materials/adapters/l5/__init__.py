"""L5 continuum / process adapters — FEniCSx, deal.II, OpenFOAM, Codec, Homogenisation.

Public surface:

* :class:`L5Adapter` — abstract base.
* :class:`L5ContinuumRequest` — caller-supplied run context.
* :class:`FEniCSxContinuumAdapter` — FEM heat slab + elasticity patch test.
* :class:`DealIIStructuralAdapter` — deal.II structural mechanics stub.
* :class:`OpenFOAMProcessAdapter` — OpenFOAM CFD Poiseuille stub.
* :class:`ContinuumHandoffCodec` — VTK / Exodus / FMI artifact emitter/parser.
* :class:`HomogenisationOperator` — L4 microstructure → L5 effective properties.
"""

from zer0pa_materials.adapters.l5.base import L5Adapter, L5ContinuumRequest
from zer0pa_materials.adapters.l5.fenicsx import FEniCSxContinuumAdapter
from zer0pa_materials.adapters.l5.dealii import DealIIStructuralAdapter
from zer0pa_materials.adapters.l5.openfoam import OpenFOAMProcessAdapter
from zer0pa_materials.adapters.l5.codec import (
    ContinuumHandoffCodec,
    emit_vtk_artifact,
    parse_vtk_artifact,
    roundtrip_vtk,
    emit_exodus_artifact,
    parse_exodus_artifact,
    roundtrip_exodus,
    emit_fmi_artifact,
    parse_fmi_artifact,
    roundtrip_fmi,
    VTK_UNITS_SCHEMA,
    EXODUS_UNITS_SCHEMA,
    FMI_UNITS_SCHEMA,
)
from zer0pa_materials.adapters.l5.homogenisation import (
    HomogenisationOperator,
    DEFAULT_MATERIAL_LIBRARY,
)

__all__ = [
    "L5Adapter",
    "L5ContinuumRequest",
    "FEniCSxContinuumAdapter",
    "DealIIStructuralAdapter",
    "OpenFOAMProcessAdapter",
    "ContinuumHandoffCodec",
    "emit_vtk_artifact",
    "parse_vtk_artifact",
    "roundtrip_vtk",
    "emit_exodus_artifact",
    "parse_exodus_artifact",
    "roundtrip_exodus",
    "emit_fmi_artifact",
    "parse_fmi_artifact",
    "roundtrip_fmi",
    "VTK_UNITS_SCHEMA",
    "EXODUS_UNITS_SCHEMA",
    "FMI_UNITS_SCHEMA",
    "HomogenisationOperator",
    "DEFAULT_MATERIAL_LIBRARY",
]
