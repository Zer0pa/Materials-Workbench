"""Unit tests for ContinuumHandoffCodec — VTK / Exodus / FMI round-trips.

PRD hard gate: every artifact carries units sidecar + sha256 hash.
The round-trip test verifies that units and hash survive emit → parse.
"""

from __future__ import annotations

import pytest

from zer0pa_materials_workbench.adapters.l5.codec import (
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
from zer0pa_materials_workbench.boundary import RESEARCH_BOUNDARY

# ---------------------------------------------------------------------------
# VTK artifact tests
# ---------------------------------------------------------------------------

class TestVTKEmit:
    def test_emit_returns_dict(self):
        art = emit_vtk_artifact({"velocity": [1.0, 0.0, 0.0]}, run_id="run:test/001")
        assert isinstance(art, dict)

    def test_emit_has_units(self):
        art = emit_vtk_artifact({"velocity": [1.0, 0.0, 0.0]}, run_id="run:test/001")
        assert "units" in art
        assert art["units"]

    def test_emit_has_sha256(self):
        art = emit_vtk_artifact({"velocity": [1.0, 0.0, 0.0]}, run_id="run:test/001")
        assert "sha256" in art
        assert art["sha256"].startswith("sha256:")

    def test_emit_has_boundary(self):
        art = emit_vtk_artifact({"velocity": [1.0]}, run_id="run:test/001")
        assert art["research_boundary"] == RESEARCH_BOUNDARY

    def test_emit_default_units_match_schema(self):
        art = emit_vtk_artifact({"velocity": [1.0]}, run_id="run:test/001")
        for k in VTK_UNITS_SCHEMA:
            assert k in art["units"]

    def test_emit_custom_units_preserved(self):
        custom = {"velocity_unit": "cm/s", "stress_unit": "MPa"}
        art = emit_vtk_artifact({"v": [1.0]}, run_id="run:test/custom", units=custom)
        assert art["units"]["velocity_unit"] == "cm/s"

    def test_emit_empty_units_raises(self):
        with pytest.raises(ValueError, match="units sidecar"):
            emit_vtk_artifact({"v": [1.0]}, run_id="run:test/empty", units={})


class TestVTKParse:
    def test_parse_valid_artifact(self):
        art = emit_vtk_artifact({"v": [1.0]}, run_id="run:test/001")
        parsed = parse_vtk_artifact(art)
        assert parsed["format"] == "vtk"

    def test_parse_missing_units_raises(self):
        art = emit_vtk_artifact({"v": [1.0]}, run_id="run:test/001")
        del art["units"]
        with pytest.raises(ValueError, match="units sidecar"):
            parse_vtk_artifact(art)

    def test_parse_missing_sha256_raises(self):
        art = emit_vtk_artifact({"v": [1.0]}, run_id="run:test/001")
        del art["sha256"]
        with pytest.raises(ValueError, match="sha256"):
            parse_vtk_artifact(art)

    def test_parse_tampered_hash_raises(self):
        art = emit_vtk_artifact({"v": [1.0]}, run_id="run:test/001")
        art["sha256"] = "sha256:" + "a" * 64
        with pytest.raises(ValueError, match="hash mismatch"):
            parse_vtk_artifact(art)


class TestVTKRoundtrip:
    def test_roundtrip_preserves_format(self):
        result = roundtrip_vtk({"velocity": [1.0, 2.0]}, run_id="run:rt/001")
        assert result["format"] == "vtk"

    def test_roundtrip_preserves_units(self):
        result = roundtrip_vtk({"v": [1.0]}, run_id="run:rt/001")
        assert result["units"]

    def test_roundtrip_preserves_hash(self):
        result = roundtrip_vtk({"v": [1.0]}, run_id="run:rt/001")
        assert result["sha256"].startswith("sha256:")

    def test_roundtrip_preserves_data(self):
        result = roundtrip_vtk({"velocity": [1.0, 2.0, 3.0]}, run_id="run:rt/001")
        assert result["data"]["velocity"] == [1.0, 2.0, 3.0]


# ---------------------------------------------------------------------------
# Exodus artifact tests
# ---------------------------------------------------------------------------

class TestExodusRoundtrip:
    def test_emit_has_units_and_hash(self):
        art = emit_exodus_artifact({"nodes": 4, "elements": 2}, run_id="run:ex/001")
        assert "units" in art
        assert "sha256" in art

    def test_parse_valid(self):
        art = emit_exodus_artifact({"nodes": 4}, run_id="run:ex/001")
        parsed = parse_exodus_artifact(art)
        assert parsed["format"] == "exodus"

    def test_roundtrip_preserves_units(self):
        result = roundtrip_exodus({"nodes": 4}, run_id="run:rt/ex/001")
        assert result["units"]

    def test_empty_units_raises(self):
        with pytest.raises(ValueError, match="units sidecar"):
            emit_exodus_artifact({"n": 1}, run_id="run:ex/empty", units={})

    def test_tampered_hash_raises(self):
        art = emit_exodus_artifact({"n": 1}, run_id="run:ex/001")
        art["sha256"] = "sha256:" + "b" * 64
        with pytest.raises(ValueError, match="hash mismatch"):
            parse_exodus_artifact(art)


# ---------------------------------------------------------------------------
# FMI artifact tests
# ---------------------------------------------------------------------------

class TestFMIRoundtrip:
    def test_emit_has_units_and_hash(self):
        art = emit_fmi_artifact(
            {"modelName": "PipeFlow", "version": "2.0"},
            run_id="run:fmi/001",
        )
        assert "units" in art
        assert "sha256" in art

    def test_parse_valid(self):
        art = emit_fmi_artifact({"modelName": "PF"}, run_id="run:fmi/001")
        parsed = parse_fmi_artifact(art)
        assert parsed["format"] == "fmi"
        assert parsed["fmi_version"] == "2.0"

    def test_roundtrip_preserves_units(self):
        result = roundtrip_fmi({"modelName": "PF"}, run_id="run:rt/fmi/001")
        assert result["units"]

    def test_empty_units_raises(self):
        with pytest.raises(ValueError, match="units sidecar"):
            emit_fmi_artifact({"m": 1}, run_id="run:fmi/empty", units={})

    def test_tampered_hash_raises(self):
        art = emit_fmi_artifact({"m": 1}, run_id="run:fmi/001")
        art["sha256"] = "sha256:" + "c" * 64
        with pytest.raises(ValueError, match="hash mismatch"):
            parse_fmi_artifact(art)


# ---------------------------------------------------------------------------
# ContinuumHandoffCodec unified interface
# ---------------------------------------------------------------------------

class TestContinuumHandoffCodec:
    def test_emit_vtk(self):
        codec = ContinuumHandoffCodec()
        art = codec.emit("vtk", {"velocity": [1.0]}, run_id="run:codec/001")
        assert art["format"] == "vtk"

    def test_emit_exodus(self):
        codec = ContinuumHandoffCodec()
        art = codec.emit("exodus", {"nodes": 4}, run_id="run:codec/001")
        assert art["format"] == "exodus"

    def test_emit_fmi(self):
        codec = ContinuumHandoffCodec()
        art = codec.emit("fmi", {"modelName": "PF"}, run_id="run:codec/001")
        assert art["format"] == "fmi"

    def test_unsupported_format_raises(self):
        codec = ContinuumHandoffCodec()
        with pytest.raises(ValueError, match="Unsupported format"):
            codec.emit("netcdf", {}, run_id="run:codec/001")

    def test_roundtrip_vtk(self):
        codec = ContinuumHandoffCodec()
        result = codec.roundtrip("vtk", {"v": [1.0]}, run_id="run:codec/001")
        assert result["units"]
        assert result["sha256"].startswith("sha256:")

    def test_roundtrip_exodus(self):
        codec = ContinuumHandoffCodec()
        result = codec.roundtrip("exodus", {"n": 4}, run_id="run:codec/001")
        assert result["units"]

    def test_roundtrip_fmi(self):
        codec = ContinuumHandoffCodec()
        result = codec.roundtrip("fmi", {"m": 1}, run_id="run:codec/001")
        assert result["units"]

    def test_parse_vtk(self):
        codec = ContinuumHandoffCodec()
        art = codec.emit("vtk", {"v": [1.0]}, run_id="run:codec/001")
        parsed = codec.parse("vtk", art)
        assert parsed["format"] == "vtk"

    def test_supported_formats(self):
        codec = ContinuumHandoffCodec()
        assert "vtk" in codec.SUPPORTED_FORMATS
        assert "exodus" in codec.SUPPORTED_FORMATS
        assert "fmi" in codec.SUPPORTED_FORMATS
