"""Research-only boundary enforcement.

The boundary block is mandated to appear verbatim in every artifact produced by
the overnight executor (PRD §Boundary; HANDOFF-TO-OVERNIGHT-EXECUTOR §Boundary).
This module is the single source of truth for the string and the assertion
helpers used by adapters, services, packet generators, and audit emitters.

Forbidden domains (HARD):
    * regulatory / certification claims
    * clinical / human-subject inference
    * ITAR / weapons applications (Meta UMA AUP + operator policy)

Anything that imports this module gets the canonical text. Anything that
EMITS an artifact must call ``assert_boundary`` on the artifact dict / model
before promotion.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

RESEARCH_BOUNDARY: str = (
    "Research infrastructure for in silico materials science discovery. "
    "Outputs are research artifacts. No regulatory certification claims. "
    "No clinical or human-subject use. ITAR / weapons applications are "
    "out of scope (Meta UMA Acceptable Use Policy and operator policy)."
)


# Phrases that, if present in an artifact's claims/output text, indicate a
# boundary violation. These are conservative substrings; the falsifier wave
# tests both the verbatim block AND the violation detector.
FORBIDDEN_PHRASE_FRAGMENTS: tuple[str, ...] = (
    "FDA-approved",
    "FDA approved",
    "clinically approved",
    "regulatory approval",
    "ITAR",
    "weapons-grade",
    "weapons grade",
    "munition",
    "human subject",
    "human-subject",
    "patient",
    "diagnosis",
    "therapeutic",  # in the regulated-claim sense; allowed when scoped to "therapeutic candidate"
)


# Phrases that pass the conservative "therapeutic" check above by being
# legitimate scientific shorthand. These are explicit allow-list overrides.
ALLOWED_PHRASE_FRAGMENTS: tuple[str, ...] = (
    "therapeutic candidate",
    "therapeutic target",
    "in vitro",
    "in silico",
    "molecular target",
)


@dataclass(frozen=True)
class BoundaryViolation:
    """Concrete reason an artifact failed boundary assertion."""

    field_path: str
    violating_phrase: str
    reason: str

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"BoundaryViolation @ {self.field_path}: {self.violating_phrase!r} — {self.reason}"


class BoundaryError(ValueError):
    """Raised when an artifact violates the research-only boundary.

    Carries the list of concrete violations so the falsifier ledger can record
    each one. The falsification wave deliberately triggers this error to
    confirm the gate is real.
    """

    def __init__(self, violations: list[BoundaryViolation]):
        self.violations = violations
        super().__init__(
            f"Boundary violation ({len(violations)}): "
            + "; ".join(str(v) for v in violations)
        )


def _walk(obj: Any, path: str = "$") -> list[tuple[str, str]]:
    """Yield (path, string-value) pairs for every string in a nested structure."""
    out: list[tuple[str, str]] = []
    if isinstance(obj, str):
        out.append((path, obj))
    elif isinstance(obj, Mapping):
        for k, v in obj.items():
            out.extend(_walk(v, f"{path}.{k}"))
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            out.extend(_walk(v, f"{path}[{i}]"))
    return out


def find_violations(artifact: Any) -> list[BoundaryViolation]:
    """Return list of concrete BoundaryViolation findings.

    The check is two-stage:
        1. The artifact must contain ``RESEARCH_BOUNDARY`` verbatim under
           ``research_boundary`` (envelope contract requirement).
        2. No string anywhere in the artifact may contain a forbidden
           phrase except via the ALLOWED_PHRASE_FRAGMENTS escape hatch.

    A missing boundary block is itself a violation (PRD §Falsification wave:
    "missing boundary block").
    """
    violations: list[BoundaryViolation] = []

    if isinstance(artifact, Mapping):
        block = artifact.get("research_boundary")
        if block != RESEARCH_BOUNDARY:
            violations.append(
                BoundaryViolation(
                    field_path="$.research_boundary",
                    violating_phrase=str(block)[:64] + ("..." if block and len(str(block)) > 64 else ""),
                    reason="research_boundary missing or not verbatim",
                )
            )
    else:
        violations.append(
            BoundaryViolation(
                field_path="$",
                violating_phrase=type(artifact).__name__,
                reason="artifact is not a mapping; cannot carry boundary block",
            )
        )

    for path, s in _walk(artifact):
        # Skip the canonical block itself — it legitimately mentions ITAR.
        if path == "$.research_boundary":
            continue
        # Mask out allow-listed phrases first so forbidden-phrase substring
        # checks don't fire when the phrase is part of a sanctioned term.
        masked = s.lower()
        for allowed in ALLOWED_PHRASE_FRAGMENTS:
            masked = masked.replace(allowed.lower(), "_" * len(allowed))
        for bad in FORBIDDEN_PHRASE_FRAGMENTS:
            if bad.lower() in masked:
                violations.append(
                    BoundaryViolation(
                        field_path=path,
                        violating_phrase=bad,
                        reason="forbidden phrase fragment in artifact text",
                    )
                )

    return violations


def assert_boundary(artifact: Any) -> None:
    """Raise BoundaryError if ``artifact`` violates the research boundary.

    Adapters call this on every output BEFORE promoting it to the audit log.
    The falsifier wave includes a deliberate "missing boundary block" case
    (PRD §Falsification wave) which must trigger BoundaryError exactly.
    """
    violations = find_violations(artifact)
    if violations:
        raise BoundaryError(violations)
