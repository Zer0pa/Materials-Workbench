"""Unit tests for MaterialsConfig."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from zer0pa_materials.envelope import MaterialsConfig


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------


@pytest.fixture
def isolated_env(monkeypatch, tmp_path):
    """Clear all PRD config env vars so MaterialsConfig sees a clean slate."""
    keys = [
        "MATERIALS_MODE", "ARTIFACT_BACKEND", "KG_BACKEND", "PHASE0_SCHEMA",
        "PHASE0_LLM_PROVIDER", "PHASE0_EXTRACTION_BACKEND",
        "PHASE0_DATABASE_BACKEND", "L6_GENERATOR_BACKEND",
        "MATERIALS_L1_BACKEND", "IONIC_TRANSPORT_BACKEND",
        "L15_FORCE_BACKEND", "L15_BAND_BACKEND", "L15_TRANSPORT_BACKEND",
        "L2_BACKEND", "L2_REQUIRE_DUAL_MODEL",
        "L3_CALPHAD_PROVIDER", "L3_TDB_FIT_PROVIDER",
        "L3_MLIP_PRIOR_PROVIDER", "L3_COMMERCIAL_TDB_PROVIDER",
        "L4_SOLVER", "L4_COMPUTE_URL",
        "L5_EXECUTION_MODE", "L5_BACKEND",
        "L7_ORCHESTRATOR_BACKEND", "ALABOS_MODE",
        "RUNPOD_BASE_URL", "RUNPOD_API_TOKEN",
        "UMA_HF_ORG", "UMA_HF_TOKEN",
        "AUDIT_DIR", "KG_DB_PATH", "ARTIFACTS_DIR",
    ]
    for k in keys:
        monkeypatch.delenv(k, raising=False)
    monkeypatch.chdir(tmp_path)


def _write_env_example(target_dir: Path) -> Path:
    """Write the .env.example baseline into target_dir/.env so the loader picks it up."""
    project_root = Path(__file__).resolve().parents[2]
    src = project_root / ".env.example"
    text = src.read_text()
    dest = target_dir / ".env"
    dest.write_text(text)
    return dest


# ----------------------------------------------------------------------------
# Defaults
# ----------------------------------------------------------------------------


def test_config_loads_defaults(isolated_env):
    cfg = MaterialsConfig()
    assert cfg.MATERIALS_MODE == "local_cpu"
    assert cfg.ALABOS_MODE == "recipe_only"
    assert cfg.L2_REQUIRE_DUAL_MODEL is True


def test_config_loads_from_env_example(isolated_env, tmp_path):
    _write_env_example(tmp_path)
    cfg = MaterialsConfig()
    assert cfg.MATERIALS_MODE == "local_cpu"
    assert cfg.ARTIFACT_BACKEND == "local_manifest"
    assert cfg.KG_BACKEND == "sqlite_stub"
    assert cfg.PHASE0_SCHEMA == "emmo_aligned"
    assert cfg.PHASE0_LLM_PROVIDER == "stub"
    assert cfg.IONIC_TRANSPORT_BACKEND == "stub"
    assert cfg.L2_BACKEND == "local_stub"
    assert cfg.L2_REQUIRE_DUAL_MODEL is True
    assert cfg.L3_CALPHAD_PROVIDER == "pycalphad_cpu"
    assert cfg.L3_COMMERCIAL_TDB_PROVIDER == "disabled"
    assert cfg.L4_SOLVER == "stub"
    assert cfg.L5_BACKEND == "fenicsx"
    assert cfg.L7_ORCHESTRATOR_BACKEND == "local_prefect"


def test_config_rejects_invalid_literal(isolated_env, monkeypatch):
    monkeypatch.setenv("MATERIALS_MODE", "kubernetes")
    with pytest.raises(Exception):
        MaterialsConfig()


def test_config_rejects_invalid_l3_commercial_provider(isolated_env, monkeypatch):
    monkeypatch.setenv("L3_COMMERCIAL_TDB_PROVIDER", "expensive_proprietary")
    with pytest.raises(Exception):
        MaterialsConfig()


# ----------------------------------------------------------------------------
# Cutover gate
# ----------------------------------------------------------------------------


def test_runpod_cutover_no_blockers_when_local_mode(isolated_env, tmp_path):
    _write_env_example(tmp_path)
    cfg = MaterialsConfig()
    blockers = cfg.validate_for_runpod_cutover()
    # Cutover gate is a no-op when MATERIALS_MODE != runpod_rest.
    assert blockers == []


def test_runpod_cutover_blockers_when_stubs_present(isolated_env, monkeypatch):
    """When MATERIALS_MODE=runpod_rest but backends are still stubs/local, cutover is blocked."""
    monkeypatch.setenv("MATERIALS_MODE", "runpod_rest")
    monkeypatch.setenv("ARTIFACT_BACKEND", "local_manifest")
    monkeypatch.setenv("KG_BACKEND", "sqlite_stub")
    monkeypatch.setenv("L2_BACKEND", "local_stub")
    monkeypatch.setenv("IONIC_TRANSPORT_BACKEND", "stub")
    cfg = MaterialsConfig()
    blockers = cfg.validate_for_runpod_cutover()
    assert any("ARTIFACT_BACKEND" in b for b in blockers)
    assert any("KG_BACKEND" in b for b in blockers)
    assert any("L2_BACKEND" in b for b in blockers)
    assert any("IONIC_TRANSPORT_BACKEND" in b for b in blockers)


def test_runpod_cutover_requires_uma_credentials(isolated_env, monkeypatch):
    """Even all backends at runpod_rest, missing UMA HF credentials block cutover."""
    monkeypatch.setenv("MATERIALS_MODE", "runpod_rest")
    monkeypatch.setenv("ARTIFACT_BACKEND", "runpod_rest")
    monkeypatch.setenv("KG_BACKEND", "runpod_rest")
    monkeypatch.setenv("PHASE0_LLM_PROVIDER", "runpod_rest")
    monkeypatch.setenv("PHASE0_EXTRACTION_BACKEND", "runpod_rest")
    monkeypatch.setenv("PHASE0_DATABASE_BACKEND", "runpod_rest")
    monkeypatch.setenv("L6_GENERATOR_BACKEND", "runpod_rest")
    monkeypatch.setenv("MATERIALS_L1_BACKEND", "runpod_rest")
    monkeypatch.setenv("IONIC_TRANSPORT_BACKEND", "runpod_rest")
    monkeypatch.setenv("L15_FORCE_BACKEND", "runpod_rest")
    monkeypatch.setenv("L15_BAND_BACKEND", "runpod_rest")
    monkeypatch.setenv("L15_TRANSPORT_BACKEND", "runpod_rest")
    monkeypatch.setenv("L2_BACKEND", "runpod_rest")
    monkeypatch.setenv("L3_CALPHAD_PROVIDER", "runpod_rest")
    monkeypatch.setenv("L3_TDB_FIT_PROVIDER", "runpod_rest")
    monkeypatch.setenv("L3_MLIP_PRIOR_PROVIDER", "runpod_rest")
    monkeypatch.setenv("L4_SOLVER", "runpod_rest")
    monkeypatch.setenv("L5_EXECUTION_MODE", "runpod_rest")
    monkeypatch.setenv("L5_BACKEND", "runpod_rest")
    monkeypatch.setenv("L7_ORCHESTRATOR_BACKEND", "runpod_rest")
    cfg = MaterialsConfig()
    blockers = cfg.validate_for_runpod_cutover()
    assert any("UMA_HF_ORG" in b for b in blockers)
    assert any("RUNPOD_BASE_URL" in b for b in blockers)


def test_runpod_cutover_passes_when_all_set(isolated_env, monkeypatch):
    monkeypatch.setenv("MATERIALS_MODE", "runpod_rest")
    for k in [
        "ARTIFACT_BACKEND", "KG_BACKEND", "PHASE0_LLM_PROVIDER",
        "PHASE0_EXTRACTION_BACKEND", "PHASE0_DATABASE_BACKEND",
        "L6_GENERATOR_BACKEND", "MATERIALS_L1_BACKEND",
        "IONIC_TRANSPORT_BACKEND", "L15_FORCE_BACKEND", "L15_BAND_BACKEND",
        "L15_TRANSPORT_BACKEND", "L2_BACKEND", "L3_CALPHAD_PROVIDER",
        "L3_TDB_FIT_PROVIDER", "L3_MLIP_PRIOR_PROVIDER", "L4_SOLVER",
        "L5_EXECUTION_MODE", "L5_BACKEND", "L7_ORCHESTRATOR_BACKEND",
    ]:
        monkeypatch.setenv(k, "runpod_rest")
    monkeypatch.setenv("UMA_HF_ORG", "zer0pa")
    monkeypatch.setenv("UMA_HF_TOKEN", "hf_xxx")
    monkeypatch.setenv("RUNPOD_BASE_URL", "https://api.runpod.ai/x")
    monkeypatch.setenv("RUNPOD_API_TOKEN", "rpa_xxx")
    cfg = MaterialsConfig()
    assert cfg.validate_for_runpod_cutover() == []


# ----------------------------------------------------------------------------
# Runtime paths
# ----------------------------------------------------------------------------


def test_runtime_paths_returns_pathlib(isolated_env, tmp_path, monkeypatch):
    monkeypatch.setenv("AUDIT_DIR", str(tmp_path / "audit"))
    monkeypatch.setenv("KG_DB_PATH", str(tmp_path / "audit" / "kg.sqlite"))
    monkeypatch.setenv("ARTIFACTS_DIR", str(tmp_path / "artifacts"))
    cfg = MaterialsConfig()
    paths = cfg.runtime_paths()
    assert paths["audit_dir"] == (tmp_path / "audit").resolve()
    assert paths["kg_db_path"] == (tmp_path / "audit" / "kg.sqlite").resolve()
    assert paths["artifacts_dir"] == (tmp_path / "artifacts").resolve()


# ----------------------------------------------------------------------------
# from_env helper
# ----------------------------------------------------------------------------


def test_from_env_with_overrides(isolated_env):
    cfg = MaterialsConfig.from_env(MATERIALS_MODE="runpod_mock")
    assert cfg.MATERIALS_MODE == "runpod_mock"
