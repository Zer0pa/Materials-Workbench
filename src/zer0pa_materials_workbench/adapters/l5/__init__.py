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

from zer0pa_materials_workbench.adapters.l5.base import L5Adapter, L5ContinuumRequest
from zer0pa_materials_workbench.adapters.l5.codec import (
    EXODUS_UNITS_SCHEMA,
    FMI_UNITS_SCHEMA,
    VTK_UNITS_SCHEMA,
    ContinuumHandoffCodec,
    emit_exodus_artifact,
    emit_fmi_artifact,
    emit_vtk_artifact,
    parse_exodus_artifact,
    parse_fmi_artifact,
    parse_vtk_artifact,
    roundtrip_exodus,
    roundtrip_fmi,
    roundtrip_vtk,
)
from zer0pa_materials_workbench.adapters.l5.dealii import DealIIStructuralAdapter
from zer0pa_materials_workbench.adapters.l5.fenicsx import FEniCSxContinuumAdapter
from zer0pa_materials_workbench.adapters.l5.homogenisation import (
    DEFAULT_MATERIAL_LIBRARY,
    HomogenisationOperator,
)
from zer0pa_materials_workbench.adapters.l5.openfoam import OpenFOAMProcessAdapter

__all__ = [
    "DEFAULT_MATERIAL_LIBRARY",
    "EXODUS_UNITS_SCHEMA",
    "FMI_UNITS_SCHEMA",
    "VTK_UNITS_SCHEMA",
    "ContinuumHandoffCodec",
    "DealIIStructuralAdapter",
    "FEniCSxContinuumAdapter",
    "HomogenisationOperator",
    "L5Adapter",
    "L5ContinuumRequest",
    "OpenFOAMProcessAdapter",
    "emit_exodus_artifact",
    "emit_fmi_artifact",
    "emit_vtk_artifact",
    "parse_exodus_artifact",
    "parse_fmi_artifact",
    "parse_vtk_artifact",
    "roundtrip_exodus",
    "roundtrip_fmi",
    "roundtrip_vtk",
]
