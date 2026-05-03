"""AlabOSProtocolCompilerStub — recipe-only protocol compiler (PRD §AlabOS Integration).

Default ``ALABOS_MODE=recipe_only``. The adapter compiles a candidate's
synthesis route into an :class:`AlabOSProtocolCandidate` JSON. The output
must NEVER carry hardware-executable instructions while
``ALABOS_MODE=recipe_only``. If a caller passes a payload with
``hardware_executable=True``, the adapter raises
:class:`AlabosExecutableInRecipeOnlyError`.

PRD §AlabOS Integration (verbatim):

    Default ALABOS_MODE='recipe_only' until Phase 2. ... Any attempt to
    emit hardware-executable instructions while this flag is active is a
    hard failure.

The adversarial test in
``tests/falsification_wave/l7/test_alabos_executable_in_recipe_only.py``
constructs a payload with ``hardware_executable=True`` and verifies the
adapter raises.
"""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from zer0pa_materials_workbench.adapters.l7.base import L7Adapter, L7CampaignParams
from zer0pa_materials_workbench.envelope import Envelope, FalsifierItem, L7CampaignOutput
from zer0pa_materials_workbench.envelope.config import AlabOSMode

__all__ = [
    "AlabOSProtocolCandidate",
    "AlabOSProtocolCompilerStub",
    "AlabOSSynthesisStep",
    "AlabosExecutableInRecipeOnlyError",
]


class AlabosExecutableInRecipeOnlyError(ValueError):
    """Raised when an AlabOS payload carries hardware_executable=True under recipe_only.

    PRD §AlabOS Integration: recipe-only output ONLY in Phase 1.
    """


class AlabOSSynthesisStep(BaseModel):
    """One step of an AlabOS synthesis recipe (no hardware-executable fields)."""

    model_config = ConfigDict(extra="forbid")

    step: int = Field(..., ge=1)
    operation: str = Field(..., min_length=1)
    parameters: dict[str, Any] = Field(default_factory=dict)
    notes: str = Field(default="")


class AlabOSProtocolCandidate(BaseModel):
    """Recipe-only AlabOS protocol candidate."""

    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    alabos_mode: AlabOSMode
    hardware_executable: bool
    synthesis_steps: list[AlabOSSynthesisStep]
    pre_synthesis_checks: list[str] = Field(default_factory=list)
    post_synthesis_characterisation: list[str] = Field(default_factory=list)


class AlabOSProtocolCompilerStub(L7Adapter):
    """Compile a synthesis route into a recipe-only AlabOS protocol candidate.

    Construction:

        compiler = AlabOSProtocolCompilerStub(alabos_mode="recipe_only")
        protocol = compiler.compile(candidate_id="candidate:foo", recipe={...})

    Calling :meth:`compile` with a recipe whose ``hardware_executable`` is
    ``True`` while the compiler is in ``recipe_only`` mode raises
    :class:`AlabosExecutableInRecipeOnlyError` immediately.
    """

    ADAPTER_NAME = "AlabOSProtocolCompilerStub"
    ADAPTER_VERSION = "0.1.0"
    ENGINE = "alabos"
    BACKEND = "stub"

    def __init__(self, alabos_mode: AlabOSMode = "recipe_only") -> None:
        self.alabos_mode = alabos_mode

    @staticmethod
    def is_real_backend() -> bool:
        return False

    def compile(
        self,
        candidate_id: str,
        recipe: dict[str, Any] | None = None,
    ) -> AlabOSProtocolCandidate:
        """Compile ``recipe`` into a recipe-only :class:`AlabOSProtocolCandidate`.

        ``recipe`` shape:

            {
                "hardware_executable": False,           # MUST be False in recipe_only
                "synthesis_steps": [
                    {"step": 1, "operation": "ball_mill", "parameters": {...}},
                    ...
                ],
                "pre_synthesis_checks": [...],
                "post_synthesis_characterisation": [...],
            }
        """
        recipe = recipe or {}
        hardware_executable = bool(recipe.get("hardware_executable", False))
        if self.alabos_mode == "recipe_only" and hardware_executable:
            raise AlabosExecutableInRecipeOnlyError(
                f"alabos_mode='recipe_only' but hardware_executable=True for {candidate_id!r} "
                "(PRD §AlabOS Integration: hard failure)"
            )
        # Default templated steps if none provided.
        if "synthesis_steps" in recipe:
            steps = [AlabOSSynthesisStep.model_validate(s) for s in recipe["synthesis_steps"]]
        else:
            steps = [
                AlabOSSynthesisStep(
                    step=1,
                    operation="ball_mill",
                    parameters={"duration_min": 30, "rpm": 400},
                ),
                AlabOSSynthesisStep(
                    step=2,
                    operation="calcine",
                    parameters={"temperature_C": 600, "duration_min": 120},
                ),
            ]
        protocol = AlabOSProtocolCandidate(
            candidate_id=candidate_id,
            alabos_mode=self.alabos_mode,
            hardware_executable=hardware_executable,
            synthesis_steps=steps,
            pre_synthesis_checks=list(recipe.get("pre_synthesis_checks", [])),
            post_synthesis_characterisation=list(
                recipe.get("post_synthesis_characterisation", [])
            ),
        )
        return protocol

    def execute(self, params: L7CampaignParams) -> Envelope:
        """Compile and emit an L7 envelope wrapping the recipe-only protocol."""
        protocol = self.compile(params.candidate_id, recipe={})
        extra_items: list[FalsifierItem] = [
            FalsifierItem(
                name="l7.alabos_recipe_only_enforcement",
                threshold="alabos_mode='recipe_only' implies hardware_executable=False",
                actual={
                    "alabos_mode": protocol.alabos_mode,
                    "hardware_executable": protocol.hardware_executable,
                },
                status=(
                    "pass"
                    if (protocol.alabos_mode != "recipe_only" or not protocol.hardware_executable)
                    else "fail"
                ),
            ),
        ]
        output = L7CampaignOutput(
            candidate_id=params.candidate_id,
            acquisition="qLogExpectedImprovement",
            promotion_decision="hold",
            audit_provenance_ref=f"audit:l7:alabos:{uuid.uuid4().hex[:12]}",
            gate_verdict="pass",
        )
        return self.make_envelope(
            output=output,
            params=params,
            extra_falsifier_items=extra_items,
            extra_input={"alabos_protocol": protocol.model_dump(mode="json")},
        )
