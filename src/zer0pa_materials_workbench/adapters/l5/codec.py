"""ContinuumHandoffCodec — VTK / Exodus / FMI artifact emitters and parsers.

PRD hard gate: every VTK / Exodus / FMI artifact MUST carry:
1. A units sidecar (``units`` dict in the artifact JSON).
2. A content hash (``sha256`` field).

Round-trip contract: emit → parse → compare → identical payload + units + hash.

Supported artifact formats
--------------------------
* ``vtk``    — lightweight JSON-VTK representation (no VTK library needed).
* ``exodus`` — NetCDF-style stub (name only; real Exodus requires PyEXODUS).
* ``fmi``    — Functional Mock-up Unit sidecar (JSON envelope for FMI 2.0).

Each artifact type carries its own minimal units sidecar schema so
downstream adapters and the KG can reconstruct dimensional quantities.
"""

from __future__ import annotations

from typing import Any

from zer0pa_materials_workbench.boundary import RESEARCH_BOUNDARY
from zer0pa_materials_workbench.envelope.hashing import sha256_of

# ---------------------------------------------------------------------------
# Units sidecar schemas (one per artifact type)
# ---------------------------------------------------------------------------

VTK_UNITS_SCHEMA = {
    "velocity_unit": "m/s",
    "stress_unit": "GPa",
    "displacement_unit": "m",
    "temperature_unit": "K",
}

EXODUS_UNITS_SCHEMA = {
    "stress_unit": "GPa",
    "strain_unit": "dimensionless",
    "displacement_unit": "m",
    "time_unit": "s",
}

FMI_UNITS_SCHEMA = {
    "velocity_unit": "m/s",
    "pressure_unit": "Pa",
    "temperature_unit": "K",
    "mass_flow_unit": "kg/s",
}


# ---------------------------------------------------------------------------
# VTK artifact
# ---------------------------------------------------------------------------

def emit_vtk_artifact(
    field_data: dict[str, Any],
    run_id: str,
    units: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Emit a minimal JSON-VTK artifact with units sidecar and content hash.

    Parameters
    ----------
    field_data:
        Scalar or vector field data, e.g. ``{"velocity": [[1.0, 0.0, 0.0], ...]}``.
    run_id:
        Run URN for provenance.
    units:
        Units sidecar dict.  Defaults to :data:`VTK_UNITS_SCHEMA`.

    Returns
    -------
    dict
        Artifact dict with ``format``, ``data``, ``units``, ``sha256`` fields.

    Raises
    ------
    ValueError
        If ``units`` is empty or None after defaulting — the PRD hard gate
        requires a non-empty units sidecar.
    """
    resolved_units = units if units is not None else VTK_UNITS_SCHEMA.copy()
    if not resolved_units:
        raise ValueError("VTK artifact must carry a non-empty units sidecar (PRD hard gate).")

    artifact: dict[str, Any] = {
        "format": "vtk",
        "run_id": run_id,
        "data": field_data,
        "units": resolved_units,
        "research_boundary": RESEARCH_BOUNDARY,
    }
    content_hash = sha256_of(artifact)
    artifact["sha256"] = content_hash
    return artifact


def parse_vtk_artifact(artifact: dict[str, Any]) -> dict[str, Any]:
    """Parse and validate a VTK artifact emitted by :func:`emit_vtk_artifact`.

    Returns
    -------
    dict
        Parsed artifact with units and verified hash.

    Raises
    ------
    ValueError
        If the artifact is missing ``units``, ``sha256``, or the hash does
        not match (units sidecar or data was tampered).
    """
    if "units" not in artifact or not artifact["units"]:
        raise ValueError("VTK artifact is missing units sidecar (PRD hard gate).")
    if "sha256" not in artifact:
        raise ValueError("VTK artifact is missing sha256 hash.")

    # Verify hash: recompute without the sha256 field.
    artifact_no_hash = {k: v for k, v in artifact.items() if k != "sha256"}
    expected_hash = sha256_of(artifact_no_hash)
    if artifact["sha256"] != expected_hash:
        raise ValueError(
            f"VTK artifact hash mismatch: stored={artifact['sha256']!r}, "
            f"computed={expected_hash!r}"
        )
    return artifact


# ---------------------------------------------------------------------------
# Exodus artifact
# ---------------------------------------------------------------------------

def emit_exodus_artifact(
    mesh_data: dict[str, Any],
    run_id: str,
    units: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Emit a minimal Exodus (JSON stub) artifact with units sidecar and hash.

    Real Exodus: binary NetCDF4 file via PyEXODUS/NetCDF4-Python.
    Stub: JSON envelope with mesh topology summary.

    Raises
    ------
    ValueError
        If units sidecar is empty.
    """
    resolved_units = units if units is not None else EXODUS_UNITS_SCHEMA.copy()
    if not resolved_units:
        raise ValueError("Exodus artifact must carry a non-empty units sidecar (PRD hard gate).")

    artifact: dict[str, Any] = {
        "format": "exodus",
        "run_id": run_id,
        "mesh_data": mesh_data,
        "units": resolved_units,
        "research_boundary": RESEARCH_BOUNDARY,
    }
    artifact["sha256"] = sha256_of(artifact)
    return artifact


def parse_exodus_artifact(artifact: dict[str, Any]) -> dict[str, Any]:
    """Parse and validate an Exodus artifact; verify units + hash."""
    if "units" not in artifact or not artifact["units"]:
        raise ValueError("Exodus artifact is missing units sidecar.")
    if "sha256" not in artifact:
        raise ValueError("Exodus artifact is missing sha256 hash.")

    artifact_no_hash = {k: v for k, v in artifact.items() if k != "sha256"}
    expected_hash = sha256_of(artifact_no_hash)
    if artifact["sha256"] != expected_hash:
        raise ValueError(
            f"Exodus artifact hash mismatch: stored={artifact['sha256']!r}, "
            f"computed={expected_hash!r}"
        )
    return artifact


# ---------------------------------------------------------------------------
# FMI artifact
# ---------------------------------------------------------------------------

def emit_fmi_artifact(
    model_description: dict[str, Any],
    run_id: str,
    units: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Emit an FMI 2.0 sidecar artifact with units sidecar and hash.

    FMI = Functional Mock-up Interface (co-simulation / model exchange).
    The stub carries the model description dict (normally an XML document
    inside a .fmu archive) serialised to JSON.

    Raises
    ------
    ValueError
        If units sidecar is empty.
    """
    resolved_units = units if units is not None else FMI_UNITS_SCHEMA.copy()
    if not resolved_units:
        raise ValueError("FMI artifact must carry a non-empty units sidecar (PRD hard gate).")

    artifact: dict[str, Any] = {
        "format": "fmi",
        "fmi_version": "2.0",
        "run_id": run_id,
        "model_description": model_description,
        "units": resolved_units,
        "research_boundary": RESEARCH_BOUNDARY,
    }
    artifact["sha256"] = sha256_of(artifact)
    return artifact


def parse_fmi_artifact(artifact: dict[str, Any]) -> dict[str, Any]:
    """Parse and validate an FMI artifact; verify units + hash."""
    if "units" not in artifact or not artifact["units"]:
        raise ValueError("FMI artifact is missing units sidecar.")
    if "sha256" not in artifact:
        raise ValueError("FMI artifact is missing sha256 hash.")

    artifact_no_hash = {k: v for k, v in artifact.items() if k != "sha256"}
    expected_hash = sha256_of(artifact_no_hash)
    if artifact["sha256"] != expected_hash:
        raise ValueError(
            f"FMI artifact hash mismatch: stored={artifact['sha256']!r}, "
            f"computed={expected_hash!r}"
        )
    return artifact


# ---------------------------------------------------------------------------
# Round-trip helpers
# ---------------------------------------------------------------------------

def roundtrip_vtk(
    field_data: dict[str, Any],
    run_id: str,
    units: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Emit and immediately parse a VTK artifact; return the parsed result.

    This is the round-trip gate test from the PRD.
    """
    artifact = emit_vtk_artifact(field_data, run_id, units)
    return parse_vtk_artifact(artifact)


def roundtrip_exodus(
    mesh_data: dict[str, Any],
    run_id: str,
    units: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Round-trip an Exodus artifact."""
    artifact = emit_exodus_artifact(mesh_data, run_id, units)
    return parse_exodus_artifact(artifact)


def roundtrip_fmi(
    model_description: dict[str, Any],
    run_id: str,
    units: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Round-trip an FMI artifact."""
    artifact = emit_fmi_artifact(model_description, run_id, units)
    return parse_fmi_artifact(artifact)


# ---------------------------------------------------------------------------
# ContinuumHandoffCodec
# ---------------------------------------------------------------------------

class ContinuumHandoffCodec:
    """Unified codec for VTK, Exodus, and FMI artifact emission and parsing.

    Usage::

        codec = ContinuumHandoffCodec()
        vtk_art = codec.emit("vtk", field_data, run_id="run:l5/001")
        parsed  = codec.parse("vtk", vtk_art)

    All emitted artifacts carry:
    * ``units`` sidecar (mandatory, PRD hard gate).
    * ``sha256`` content hash.
    * ``research_boundary`` verbatim block.
    """

    _EMITTERS = {
        "vtk": emit_vtk_artifact,
        "exodus": emit_exodus_artifact,
        "fmi": emit_fmi_artifact,
    }
    _PARSERS = {
        "vtk": parse_vtk_artifact,
        "exodus": parse_exodus_artifact,
        "fmi": parse_fmi_artifact,
    }
    _ROUNDTRIPPERS = {
        "vtk": roundtrip_vtk,
        "exodus": roundtrip_exodus,
        "fmi": roundtrip_fmi,
    }

    SUPPORTED_FORMATS = frozenset(["vtk", "exodus", "fmi"])

    def emit(
        self,
        fmt: str,
        data: dict[str, Any],
        run_id: str,
        units: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Emit an artifact in the given format.

        Parameters
        ----------
        fmt:
            One of ``"vtk"``, ``"exodus"``, ``"fmi"``.
        data:
            Payload dict (field data for VTK, mesh data for Exodus, model
            description for FMI).
        run_id:
            Run URN.
        units:
            Units sidecar.  Uses format-default if None.
        """
        if fmt not in self._EMITTERS:
            raise ValueError(f"Unsupported format {fmt!r}. Supported: {sorted(self.SUPPORTED_FORMATS)}")
        return self._EMITTERS[fmt](data, run_id, units)

    def parse(self, fmt: str, artifact: dict[str, Any]) -> dict[str, Any]:
        """Parse and verify an artifact."""
        if fmt not in self._PARSERS:
            raise ValueError(f"Unsupported format {fmt!r}.")
        return self._PARSERS[fmt](artifact)

    def roundtrip(
        self,
        fmt: str,
        data: dict[str, Any],
        run_id: str,
        units: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Emit and immediately parse; verify units + hash survive."""
        if fmt not in self._ROUNDTRIPPERS:
            raise ValueError(f"Unsupported format {fmt!r}.")
        return self._ROUNDTRIPPERS[fmt](data, run_id, units)
