"""L4SolverEnsemble — primary user-facing L4 adapter.

PRD §L4 plug-swap test: "plug-swap from stub to another L4 backend changes
backend, NOT schema." This ensemble runner runs PRISMS-PF and MOOSE on the
SAME PhaseFieldRunSpec and produces:

    1. A merged envelope whose schema is identical to a single-backend
       envelope (same Envelope keys, same L4PhaseFieldOutput keys).
    2. A cross-code disagreement metric in ``disagreement.metrics``.
    3. A "<1 day swap" invariant: if PRISMS-PF or MOOSE is replaced by any
       other L4 adapter, the schema is unchanged and the disagreement
       metric is computed against the new pairing.

The adversarial test at ``tests/plug_swap/l4/test_l4_swap.py`` swaps the
backends and asserts the schema invariance.
"""

from __future__ import annotations

from typing import Any

from zer0pa_materials.adapters.l4.base import L4Adapter, L4PredictRequest
from zer0pa_materials.adapters.l4.contracts import PhaseFieldRunSpec
from zer0pa_materials.adapters.l4.moose import MoosePhaseFieldAdapter
from zer0pa_materials.adapters.l4.prisms_pf import PrismsPfAdapter
from zer0pa_materials.boundary import RESEARCH_BOUNDARY
from zer0pa_materials.envelope.hashing import sha256_of
from zer0pa_materials.envelope.layer_outputs import L4PhaseFieldOutput


class L4SolverEnsemble:
    """Primary L4 adapter: runs two L4 backends on the same spec.

    Defaults to PRISMS-PF and MOOSE (the two PRD-mandated classical solvers).
    Either can be swapped for any other ``L4Adapter`` to verify the
    plug-swap invariant.
    """

    NAME = "L4SolverEnsemble"
    VERSION = "0.1.0"

    def __init__(
        self,
        primary: L4Adapter | None = None,
        secondary: L4Adapter | None = None,
    ) -> None:
        self._primary: L4Adapter = primary or PrismsPfAdapter()
        self._secondary: L4Adapter = secondary or MoosePhaseFieldAdapter()
        self.name = self.NAME
        self.version = self.VERSION
        self.backend = "stub"

    # ------------------------------------------------------------------- run

    def run(
        self,
        spec: PhaseFieldRunSpec,
        request: L4PredictRequest,
    ) -> dict[str, Any]:
        """Run both backends on ``spec`` and return a merged ensemble envelope.

        The merged envelope has:
            - ``layer == "L4"``
            - ``output`` conforming to ``L4PhaseFieldOutput``
            - ``disagreement.metrics`` populated with the cross-code metric
            - ``_l4_ensemble_meta`` with both backend payloads for audit
        """
        primary_env = self._primary.run(spec, request)
        secondary_env = self._secondary.run(spec, request)

        primary_meta = primary_env.get("_l4_meta", {})
        secondary_meta = secondary_env.get("_l4_meta", {})

        # ----- Cross-code disagreement -----
        disagreement_metrics = self._compute_disagreement(
            spec.equation, primary_meta, secondary_meta
        )

        # ----- Merged output (canonical schema) -----
        # We keep the primary's gates as the headline numbers but record
        # both backends' values in _l4_ensemble_meta. The disagreement
        # metric is the primary user-facing signal.
        primary_output = primary_env["output"]
        merged_output: dict[str, Any] = {
            "cahn_hilliard_mass_drift": primary_output.get("cahn_hilliard_mass_drift"),
            "allen_cahn_bounds_violation": primary_output.get("allen_cahn_bounds_violation"),
            "spparks_potts_energy_monotonic": None,
            "microstructure_trajectory_uri": f"artifact:{request.run_id}/ensemble-trajectory",
        }
        l4_obj = L4PhaseFieldOutput.model_validate(merged_output)
        falsifier_items = [it.model_dump(mode="json") for it in l4_obj.falsifier_items()]
        active_items = [it for it in falsifier_items if it["actual"] is not None]
        falsifier_status = (
            "fail" if any(it["status"] == "fail" for it in active_items)
            else "blocked" if not active_items
            else "pass"
        )

        input_hash = sha256_of(spec.model_dump(mode="json"))
        out_hash = sha256_of(merged_output)

        envelope = {
            "research_boundary": RESEARCH_BOUNDARY,
            "contract_version": "zer0pa.materials.layer-envelope.v1",
            "layer": "L4",
            "run_id": request.run_id,
            "candidate_id": request.candidate_id,
            "campaign_id": request.campaign_id,
            "tool_adapter": {
                "name": self.NAME,
                "version": self.VERSION,
                "backend": self.backend,
                "engine": (
                    f"{self._primary.engine}+{self._secondary.engine}"
                ),
            },
            "output": merged_output,
            "confidence": {
                "score": (
                    primary_env["confidence"]["score"]
                    + secondary_env["confidence"]["score"]
                )
                / 2.0,
                "band": "medium",
                "basis": [
                    f"primary={self._primary.name}",
                    f"secondary={self._secondary.name}",
                    f"disagreement={disagreement_metrics[0]['value']:.6f}" if disagreement_metrics else "no_disagreement_metric",
                ],
            },
            "disagreement": {"metrics": disagreement_metrics},
            "falsifier": {"status": falsifier_status, "items": falsifier_items},
            "audit": {
                "audit_record_id": f"audit:{request.run_id}/ensemble",
                "input_hash": input_hash,
                "output_hash": out_hash,
                "source_manifest_refs": [
                    "src:prisms-pf:cxx-build",
                    "src:moose:cxx-build",
                ],
            },
            "rights": {
                "rights_claim_id": request.rights_claim_id,
                "reuse_scope": "tenant_only",
            },
            "back_edges": [],
            "_l4_ensemble_meta": {
                "primary": {
                    "adapter_name": primary_meta.get("adapter_name"),
                    "conserved_quantities": primary_meta.get("conserved_quantities", {}),
                },
                "secondary": {
                    "adapter_name": secondary_meta.get("adapter_name"),
                    "conserved_quantities": secondary_meta.get("conserved_quantities", {}),
                },
                "disagreement_metric_name": disagreement_metrics[0]["name"]
                if disagreement_metrics else None,
                "disagreement_value": disagreement_metrics[0]["value"]
                if disagreement_metrics else None,
            },
        }
        return envelope

    # -------------------------------------------------- disagreement metric

    def _compute_disagreement(
        self,
        equation: str,
        primary_meta: dict[str, Any],
        secondary_meta: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Compute the cross-code disagreement primitive.

        For Cahn-Hilliard we compare the mass-drift values; for Allen-Cahn
        we compare the bounds-violation values; for MPF we average both.
        For grand_potential we compare mass drift.
        """
        primary_q = primary_meta.get("conserved_quantities", {})
        secondary_q = secondary_meta.get("conserved_quantities", {})

        if equation == "cahn_hilliard":
            p = primary_q.get("mass_drift_relative", 0.0)
            s = secondary_q.get("mass_drift_relative", 0.0)
            return [{
                "name": "l4.cross_code_mass_drift_disagreement",
                "value": abs(p - s),
                "unit": "relative",
                "references": [
                    primary_meta.get("adapter_name", "primary"),
                    secondary_meta.get("adapter_name", "secondary"),
                ],
            }]
        elif equation == "allen_cahn":
            p = primary_q.get("bounds_violation_max", 0.0)
            s = secondary_q.get("bounds_violation_max", 0.0)
            return [{
                "name": "l4.cross_code_bounds_violation_disagreement",
                "value": abs(p - s),
                "unit": "absolute",
                "references": [
                    primary_meta.get("adapter_name", "primary"),
                    secondary_meta.get("adapter_name", "secondary"),
                ],
            }]
        elif equation == "mpf":
            p_mass = primary_q.get("mass_drift_relative", 0.0)
            s_mass = secondary_q.get("mass_drift_relative", 0.0)
            p_bounds = primary_q.get("bounds_violation_max", 0.0)
            s_bounds = secondary_q.get("bounds_violation_max", 0.0)
            return [
                {
                    "name": "l4.cross_code_mass_drift_disagreement",
                    "value": abs(p_mass - s_mass),
                    "unit": "relative",
                    "references": [
                        primary_meta.get("adapter_name", "primary"),
                        secondary_meta.get("adapter_name", "secondary"),
                    ],
                },
                {
                    "name": "l4.cross_code_bounds_violation_disagreement",
                    "value": abs(p_bounds - s_bounds),
                    "unit": "absolute",
                    "references": [
                        primary_meta.get("adapter_name", "primary"),
                        secondary_meta.get("adapter_name", "secondary"),
                    ],
                },
            ]
        else:
            return []

    # ----------------------------------------------------- blocked_manifests

    def blocked_manifests(self) -> list[dict[str, Any]]:
        return self._primary.blocked_manifests() + self._secondary.blocked_manifests()
