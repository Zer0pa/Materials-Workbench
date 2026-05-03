"""QuantumProblemDispatcher — quantum slot router (PRD §Synthesis "3 quantum slots").

Quantum slot mapping (PRD):
    L1-VQE      — electronic structure via VQE (implemented)
    L4-QAOA     — QAOA on phase-field discretisation (PARKED)
    L7-QAA      — quantum amplitude amplification for campaign search (PARKED)

The dispatcher accepts a ``slot`` parameter and routes to the correct solver.
Unimplemented slots raise a ``BlockedSourceManifest`` rather than silently
returning wrong results.

Usage
-----
    dispatcher = QuantumProblemDispatcher()
    envelope = dispatcher.dispatch(slot="L1-VQE", system="H2")
    envelope = dispatcher.dispatch(slot="L4-QAOA", ...)  # raises NotImplementedError + emits BlockedSourceManifest
"""

from __future__ import annotations

from typing import Any, Literal

from zer0pa_materials_workbench.adapters.quantum.pennylane_vqe import PennyLaneVqeSolver
from zer0pa_materials_workbench.audit.sources import BlockedSourceManifest
from zer0pa_materials_workbench.envelope import Envelope

__all__ = ["QuantumProblemDispatcher", "QuantumSlot"]

QuantumSlot = Literal["L1-VQE", "L4-QAOA", "L7-QAA"]

# Blocked manifests for unimplemented quantum slots
_L4_QAOA_BLOCKED = BlockedSourceManifest(
    source_manifest_id="src:blocked:l4-qaoa:not-implemented",
    attempted_locator="https://zer0pa.ai/quantum/l4-qaoa",
    blocker_reason="other",
    blocker_detail="L4-QAOA quantum slot — QAOA on phase-field discretisation. NOT YET IMPLEMENTED. L4 phase-field quantum acceleration deferred to post-MVP. CPU L4 adapter (Cahn-Hilliard FEniCSx) is the active path.",
    retry_strategy="Implement L4 QAOA solver after Phase L4 CPU adapter is validated. See PRD §Synthesis.",
)

_L7_QAA_BLOCKED = BlockedSourceManifest(
    source_manifest_id="src:blocked:l7-qaa:not-implemented",
    attempted_locator="https://zer0pa.ai/quantum/l7-qaa",
    blocker_reason="other",
    blocker_detail="L7-QAA quantum amplitude amplification — campaign search acceleration. NOT YET IMPLEMENTED. L7 QAA deferred until L7 campaign layer is built. Bayesian BO is the active L7 path.",
    retry_strategy="Implement L7 QAA after L7 BO is validated. Requires quadratic speedup analysis vs BO baseline.",
)


class QuantumProblemDispatcher:
    """Routes quantum problems to the correct slot solver.

    Only L1-VQE is implemented. L4-QAOA and L7-QAA raise
    ``NotImplementedError`` and emit a ``BlockedSourceManifest``.
    """

    def __init__(self) -> None:
        self._vqe_solver = PennyLaneVqeSolver()

    def dispatch(
        self,
        slot: QuantumSlot,
        system: str = "H2",
        bond_ang: float | None = None,
        campaign_id: str = "campaign:quantum-dispatch",
        candidate_id: str = "candidate:quantum-dispatch",
        **kwargs: Any,
    ) -> Envelope:
        """Route the quantum problem to the appropriate solver.

        Parameters
        ----------
        slot:
            Quantum slot identifier: ``"L1-VQE"``, ``"L4-QAOA"``, or ``"L7-QAA"``.
        system:
            Molecular system for L1-VQE: ``"H2"`` or ``"LiH"``.
        bond_ang:
            Bond length in Ångström for L1-VQE. Uses fixture default if None.
        campaign_id / candidate_id:
            Forwarded to the solver.
        **kwargs:
            Additional keyword arguments forwarded to the solver.

        Raises
        ------
        NotImplementedError
            For ``L4-QAOA`` and ``L7-QAA`` slots (with BlockedSourceManifest in exception).
        ValueError
            For unknown slot values.
        """
        if slot == "L1-VQE":
            return self._dispatch_l1_vqe(system, bond_ang, campaign_id, candidate_id)
        elif slot == "L4-QAOA":
            raise NotImplementedError(
                f"Quantum slot {slot!r} is not yet implemented. "
                f"BlockedSourceManifest: {_L4_QAOA_BLOCKED.source_manifest_id}"
            )
        elif slot == "L7-QAA":
            raise NotImplementedError(
                f"Quantum slot {slot!r} is not yet implemented. "
                f"BlockedSourceManifest: {_L7_QAA_BLOCKED.source_manifest_id}"
            )
        else:
            raise ValueError(
                f"Unknown quantum slot {slot!r}. "
                "Valid slots: 'L1-VQE', 'L4-QAOA', 'L7-QAA'."
            )

    def _dispatch_l1_vqe(
        self,
        system: str,
        bond_ang: float | None,
        campaign_id: str,
        candidate_id: str,
    ) -> Envelope:
        """Route L1-VQE to the PennyLane solver."""
        if system == "H2":
            from zer0pa_materials_workbench.adapters.l1.pyscf import _H2_BOND_A
            bl = bond_ang or _H2_BOND_A
            return self._vqe_solver.solve_h2(bl, campaign_id, candidate_id)
        elif system == "LiH":
            from zer0pa_materials_workbench.adapters.l1.pyscf import _LIH_BOND_A
            bl = bond_ang or _LIH_BOND_A
            return self._vqe_solver.solve_lih(bl, campaign_id, candidate_id)
        else:
            raise ValueError(
                f"L1-VQE supports 'H2' and 'LiH'; got {system!r}. "
                "Other molecular systems are parked pending multi-reference extension."
            )

    @property
    def blocked_manifests(self) -> dict[str, BlockedSourceManifest]:
        """Return the blocked manifests for unimplemented slots."""
        return {
            "L4-QAOA": _L4_QAOA_BLOCKED,
            "L7-QAA": _L7_QAA_BLOCKED,
        }
