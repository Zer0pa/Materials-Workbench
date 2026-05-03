"""Materials pipeline configuration registry (PRD §Core Config Flags).

Loads the canonical ``.env`` shape into a strongly-typed Pydantic settings
model. Backend-selection flags are typed as ``Literal[...]`` of the allowed
values so an invalid value is rejected at startup, not at the moment a
candidate hits the layer that needs it.

This module is the only place that knows the env-var spelling. Adapters and
services depend on the typed model, never on ``os.environ``.

Cutover semantics
-----------------

The Runpod cutover (§Runpod Migration) moves ``MATERIALS_MODE`` to
``runpod_rest`` and replaces every backend flag's value with the real
remote backend. ``validate_for_runpod_cutover()`` enumerates which flags
are still pointing at stubs/local backends so the operator can see exactly
what work remains. This is the same gate the orchestrator uses before
issuing the "promote backend from mock to real" step.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final, Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

__all__ = [
    "AlabOSMode",
    "ArtifactBackend",
    "IonicTransportBackend",
    "KGBackend",
    "L1Backend",
    "L2Backend",
    "L3CalphadProvider",
    "L3CommercialTdbProvider",
    "L3MlipPriorProvider",
    "L3TdbFitProvider",
    "L4Solver",
    "L5Backend",
    "L5ExecutionMode",
    "L6GeneratorBackend",
    "L7OrchestratorBackend",
    "L15BandBackend",
    "L15ForceBackend",
    "L15TransportBackend",
    "MaterialsConfig",
    "MaterialsMode",
    "Phase0DatabaseBackend",
    "Phase0ExtractionBackend",
    "Phase0LLMProvider",
    "Phase0Schema",
]


# ----------------------------------------------------------------------------
# Literal enums for each backend flag (matching .env.example exactly)
# ----------------------------------------------------------------------------


MaterialsMode = Literal["local_cpu", "runpod_mock", "runpod_rest"]
ArtifactBackend = Literal["local_manifest", "runpod_mock", "runpod_rest"]
KGBackend = Literal["sqlite_stub", "rdf_native", "runpod_mock", "runpod_rest"]
Phase0Schema = Literal["emmo_aligned", "proprietary"]
Phase0LLMProvider = Literal["stub", "openai", "anthropic", "vertex", "runpod_rest"]
Phase0ExtractionBackend = Literal["local_stub", "langgraph", "runpod_mock", "runpod_rest"]
Phase0DatabaseBackend = Literal[
    "optimade_mock", "optimade_live", "runpod_mock", "runpod_rest"
]
L6GeneratorBackend = Literal["stub", "mattergen", "diffcsp", "crystallm", "runpod_mock", "runpod_rest"]
L1Backend = Literal["local_cpu", "runpod_mock", "runpod_rest"]
IonicTransportBackend = Literal["stub", "local_cpu", "runpod_mock", "runpod_rest"]
L15ForceBackend = Literal["mock", "local_cpu", "runpod_mock", "runpod_rest"]
L15BandBackend = Literal["mock", "local_cpu", "runpod_mock", "runpod_rest"]
L15TransportBackend = Literal["local_cpu", "runpod_mock", "runpod_rest"]
L2Backend = Literal["local_stub", "local_cpu", "runpod_mock", "runpod_rest"]
L3CalphadProvider = Literal["pycalphad_cpu", "runpod_mock", "runpod_rest"]
L3TdbFitProvider = Literal["espei_cpu", "runpod_mock", "runpod_rest"]
L3MlipPriorProvider = Literal["phaseforgeplus_stub", "phaseforgeplus_local", "runpod_mock", "runpod_rest"]
L3CommercialTdbProvider = Literal["disabled", "thermo_calc_quarantined"]
L4Solver = Literal["stub", "prisms_pf", "moose", "microsim", "spparks", "neural_operator", "runpod_mock", "runpod_rest"]
L5ExecutionMode = Literal["local_stub", "local_cpu", "runpod_mock", "runpod_rest"]
L5Backend = Literal["fenicsx", "dealii", "openfoam", "runpod_mock", "runpod_rest"]
L7OrchestratorBackend = Literal["local_prefect", "prefect_cloud", "runpod_mock", "runpod_rest"]
AlabOSMode = Literal["recipe_only", "phase2_hardware"]


# ----------------------------------------------------------------------------
# Stub-marker classification
# ----------------------------------------------------------------------------


# Values that mean "still stub / mock" for the purpose of cutover gating.
_STUB_VALUES: Final[frozenset[str]] = frozenset(
    {
        "stub",
        "local_stub",
        "mock",
        "optimade_mock",
        "phaseforgeplus_stub",
        "sqlite_stub",
    }
)
# Values that are NOT runpod_rest but represent legitimate local/CPU work.
# Cutover blocks these only when MATERIALS_MODE == 'runpod_rest'.
_LOCAL_VALUES: Final[frozenset[str]] = frozenset(
    {
        "local_cpu",
        "pycalphad_cpu",
        "espei_cpu",
        "fenicsx",
        "dealii",
        "openfoam",
        "local_prefect",
        "phaseforgeplus_local",
        "local_manifest",
    }
)


# ----------------------------------------------------------------------------
# The settings model
# ----------------------------------------------------------------------------


class MaterialsConfig(BaseSettings):
    """Typed loader for the PRD §Core Config Flags surface.

    Reads ``.env`` in the project root by default; values can be overridden
    by environment variables of the same name. Backend literals reject any
    value that is not in the allowed set.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # PRD §Core Config Flags — match .env.example exactly.
    MATERIALS_MODE: MaterialsMode = Field(default="local_cpu")
    ARTIFACT_BACKEND: ArtifactBackend = Field(default="local_manifest")
    KG_BACKEND: KGBackend = Field(default="sqlite_stub")
    PHASE0_SCHEMA: Phase0Schema = Field(default="emmo_aligned")
    PHASE0_LLM_PROVIDER: Phase0LLMProvider = Field(default="stub")

    PHASE0_EXTRACTION_BACKEND: Phase0ExtractionBackend = Field(default="local_stub")
    PHASE0_DATABASE_BACKEND: Phase0DatabaseBackend = Field(default="optimade_mock")
    L6_GENERATOR_BACKEND: L6GeneratorBackend = Field(default="stub")

    MATERIALS_L1_BACKEND: L1Backend = Field(default="local_cpu")
    IONIC_TRANSPORT_BACKEND: IonicTransportBackend = Field(default="stub")

    L15_FORCE_BACKEND: L15ForceBackend = Field(default="mock")
    L15_BAND_BACKEND: L15BandBackend = Field(default="mock")
    L15_TRANSPORT_BACKEND: L15TransportBackend = Field(default="local_cpu")

    L2_BACKEND: L2Backend = Field(default="local_stub")
    L2_REQUIRE_DUAL_MODEL: bool = Field(default=True)

    L3_CALPHAD_PROVIDER: L3CalphadProvider = Field(default="pycalphad_cpu")
    L3_TDB_FIT_PROVIDER: L3TdbFitProvider = Field(default="espei_cpu")
    L3_MLIP_PRIOR_PROVIDER: L3MlipPriorProvider = Field(default="phaseforgeplus_stub")
    L3_COMMERCIAL_TDB_PROVIDER: L3CommercialTdbProvider = Field(default="disabled")

    L4_SOLVER: L4Solver = Field(default="stub")
    L4_COMPUTE_URL: str = Field(default="http://localhost:8044")

    L5_EXECUTION_MODE: L5ExecutionMode = Field(default="local_stub")
    L5_BACKEND: L5Backend = Field(default="fenicsx")

    L7_ORCHESTRATOR_BACKEND: L7OrchestratorBackend = Field(default="local_prefect")

    # PRD §L7 Falsifiers: plain qExpectedImprovement is forbidden as default.
    # This flag (default False) is the only opt-in path; the BoTorch
    # acquisition adapter consults it before raising ForbiddenAcquisitionError.
    allow_legacy_qei: bool = Field(default=False)

    ALABOS_MODE: AlabOSMode = Field(default="recipe_only")

    # Optional Runpod cutover envelope (lookup at cutover time).
    RUNPOD_BASE_URL: str | None = Field(default=None)
    RUNPOD_API_TOKEN: str | None = Field(default=None)
    UMA_HF_ORG: str | None = Field(default=None)
    UMA_HF_TOKEN: str | None = Field(default=None)

    # Runtime paths.
    AUDIT_DIR: str = Field(default="./audit/runtime")
    KG_DB_PATH: str = Field(default="./audit/runtime/kg.sqlite")
    ARTIFACTS_DIR: str = Field(default="./artifacts/runtime")

    # ---- Constructors ------------------------------------------------------

    @classmethod
    def from_env(cls, **overrides: object) -> MaterialsConfig:
        """Load from .env / env vars and apply Python-level overrides."""
        return cls(**overrides)  # type: ignore[arg-type]

    # ---- Cutover gate ------------------------------------------------------

    def validate_for_runpod_cutover(self) -> list[str]:
        """Return a list of cutover blockers.

        Empty list means cutover may proceed. Non-empty list means at least
        one backend flag is still set to a stub/mock and the user MUST move
        it to ``runpod_rest`` (or accept the documented exception in
        ``phases/A0-contracts/NOTES.md``).

        We are intentionally strict: when MATERIALS_MODE is ``runpod_rest``,
        EVERY backend flag should also be at ``runpod_rest`` unless an
        explicit local-CPU exemption applies (Phase 0 schema flag, audit
        runtime paths, etc).
        """
        blockers: list[str] = []
        if self.MATERIALS_MODE != "runpod_rest":
            return blockers

        # Map of backend-style flag -> current value.
        flags: dict[str, str] = {
            "ARTIFACT_BACKEND": self.ARTIFACT_BACKEND,
            "KG_BACKEND": self.KG_BACKEND,
            "PHASE0_LLM_PROVIDER": self.PHASE0_LLM_PROVIDER,
            "PHASE0_EXTRACTION_BACKEND": self.PHASE0_EXTRACTION_BACKEND,
            "PHASE0_DATABASE_BACKEND": self.PHASE0_DATABASE_BACKEND,
            "L6_GENERATOR_BACKEND": self.L6_GENERATOR_BACKEND,
            "MATERIALS_L1_BACKEND": self.MATERIALS_L1_BACKEND,
            "IONIC_TRANSPORT_BACKEND": self.IONIC_TRANSPORT_BACKEND,
            "L15_FORCE_BACKEND": self.L15_FORCE_BACKEND,
            "L15_BAND_BACKEND": self.L15_BAND_BACKEND,
            "L15_TRANSPORT_BACKEND": self.L15_TRANSPORT_BACKEND,
            "L2_BACKEND": self.L2_BACKEND,
            "L3_CALPHAD_PROVIDER": self.L3_CALPHAD_PROVIDER,
            "L3_TDB_FIT_PROVIDER": self.L3_TDB_FIT_PROVIDER,
            "L3_MLIP_PRIOR_PROVIDER": self.L3_MLIP_PRIOR_PROVIDER,
            "L4_SOLVER": self.L4_SOLVER,
            "L5_EXECUTION_MODE": self.L5_EXECUTION_MODE,
            "L5_BACKEND": self.L5_BACKEND,
            "L7_ORCHESTRATOR_BACKEND": self.L7_ORCHESTRATOR_BACKEND,
        }
        for name, value in flags.items():
            if value in _STUB_VALUES or value in _LOCAL_VALUES:
                blockers.append(f"{name}={value} is not a runpod_rest value")
        # UMA gate: under runpod_rest we must have HF org + token registered.
        if self.UMA_HF_ORG is None or self.UMA_HF_TOKEN is None:
            blockers.append(
                "UMA_HF_ORG and UMA_HF_TOKEN must be set for UMA access under runpod_rest"
            )
        if self.RUNPOD_BASE_URL is None or self.RUNPOD_API_TOKEN is None:
            blockers.append(
                "RUNPOD_BASE_URL and RUNPOD_API_TOKEN must be set under MATERIALS_MODE=runpod_rest"
            )
        return blockers

    # ---- Runtime paths -----------------------------------------------------

    def runtime_paths(self) -> dict[str, Path]:
        """Return resolved Path objects for audit, KG, and artifact roots."""
        return {
            "audit_dir": Path(self.AUDIT_DIR).resolve(),
            "kg_db_path": Path(self.KG_DB_PATH).resolve(),
            "artifacts_dir": Path(self.ARTIFACTS_DIR).resolve(),
        }
