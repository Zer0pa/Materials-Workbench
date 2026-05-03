"""L2 ensemble runner — DPA-3 + MACE mandatory by construction.

This is the PRIMARY USER-FACING L2 adapter.

Design invariants (RESISTANCE.md §DPA+MACE mandatory):
    1. DPA-3 AND MACE BOTH run on every L2 candidate. There is no code path
       where only one model runs and ``routing_decision = "promote"``.
    2. The ``single_model_promotion_block`` falsifier MUST fail any envelope
       that claims ``routing_decision = "promote"`` with < 2 distinct models.
    3. UMA is an optional third model, added via ``add_optional_model``; its
       presence in ``per_model_predictions`` does NOT relax the DPA+MACE
       requirement.

PRD-mandated routing thresholds:
    queue DFT  if energy disagreement > 25 meV/atom
    queue DFT  if force RMSE > 0.15 eV/Å
    queue DFT  if relaxation endpoint differs by > 0.08 Å/atom, > 2% volume,
               or different space group (relaxation endpoints handled by
               the service layer; not in scope here)
    HARD REJECT if energy disagreement > 75 meV/atom
    HARD REJECT if force RMSE > 0.35 eV/Å

KG writes:
    SimulationJob            one per run
    SimulationResult         one per ensemble member
    SimulationResult -[MEMBER_OF_ENSEMBLE]-> EnsembleSimulationResult
    DisagreementMetric node + AGREES_WITH / CONTRADICTS edges
    Decision node, Decision -[ROUTED_TO]-> SimulationJob
"""

from __future__ import annotations

from typing import Any

from zer0pa_materials_workbench.adapters.l2.base import L2MlipAdapter, L2PredictRequest
from zer0pa_materials_workbench.adapters.l2.deepmd_dpa import DeepmdDpaCalculatorAdapter
from zer0pa_materials_workbench.adapters.l2.mace_mp import MaceMpCalculatorAdapter
from zer0pa_materials_workbench.boundary import RESEARCH_BOUNDARY
from zer0pa_materials_workbench.envelope.hashing import sha256_of, structure_hash
from zer0pa_materials_workbench.envelope.layer_outputs import L2MlipOutput
from zer0pa_materials_workbench.runpod.dispatcher import (
    RunpodDispatcher,
)

# ---------------------------------------------------------------------------
# Routing threshold constants (PRD §L2)
# ---------------------------------------------------------------------------

_PROMOTE_ENERGY_THRESHOLD_MEV = 25.0   # queue DFT above this
_HARD_REJECT_ENERGY_THRESHOLD_MEV = 75.0  # hard reject above this
_PROMOTE_FORCE_THRESHOLD_EV_ANG = 0.15    # queue DFT above this
_HARD_REJECT_FORCE_THRESHOLD_EV_ANG = 0.35  # hard reject above this


def _decide_routing(
    energy_disagreement_meV: float,
    force_rmse_disagreement_eV_Ang: float,
) -> str:
    """Apply PRD routing thresholds and return a routing decision string."""
    # Hard reject takes precedence over queue_dft.
    if (
        energy_disagreement_meV > _HARD_REJECT_ENERGY_THRESHOLD_MEV
        or force_rmse_disagreement_eV_Ang > _HARD_REJECT_FORCE_THRESHOLD_EV_ANG
    ):
        return "hard_reject"
    if (
        energy_disagreement_meV > _PROMOTE_ENERGY_THRESHOLD_MEV
        or force_rmse_disagreement_eV_Ang > _PROMOTE_FORCE_THRESHOLD_EV_ANG
    ):
        return "queue_dft"
    return "promote"


class L2EnsembleRunner:
    """Primary L2 adapter: runs DPA-3 AND MACE on every candidate.

    Optionally runs additional models (UMA, SevenNet) when provided.

    Parameters
    ----------
    dpa_adapter:
        DPA-3 adapter instance.  Defaults to ``DeepmdDpaCalculatorAdapter``.
    mace_adapter:
        MACE-MPA-0 adapter instance.  Defaults to ``MaceMpCalculatorAdapter``.
    optional_adapters:
        Additional L2 adapters (UMA, SevenNet).  Their predictions are
        recorded in ``per_model_predictions`` but do NOT change the routing
        logic which is based solely on DPA vs MACE disagreement.
    """

    def __init__(
        self,
        dpa_adapter: L2MlipAdapter | None = None,
        mace_adapter: L2MlipAdapter | None = None,
        optional_adapters: list[L2MlipAdapter] | None = None,
        *,
        dispatcher: RunpodDispatcher | None = None,
    ) -> None:
        self._dpa = dpa_adapter or DeepmdDpaCalculatorAdapter()
        self._mace = mace_adapter or MaceMpCalculatorAdapter()
        self._optional: list[L2MlipAdapter] = optional_adapters or []
        # Wave C: optional Runpod dispatcher. When provided AND its
        # configured backend for L2 is "runpod_rest", :meth:`run` routes
        # the call through the live REST client; the local DPA/MACE
        # ensemble fires only when the dispatcher is absent or returns
        # ``None`` (i.e. the configured backend is local).  Passing
        # ``dispatcher=None`` (the default) preserves all pre-Wave-C
        # behaviour, which is why the existing test suite continues to
        # pass without modification.
        self._dispatcher = dispatcher

    def add_optional_model(self, adapter: L2MlipAdapter) -> None:
        """Register an optional third model (UMA, SevenNet, etc.)."""
        self._optional.append(adapter)

    # ----------------------------------------------------------------------- run

    def run(
        self,
        structure: dict[str, Any],
        request: L2PredictRequest,
    ) -> dict[str, Any]:
        """Run DPA-3 + MACE (+ optionals) and return a merged ensemble envelope.

        The ensemble envelope contains:
        - ``output.predictions``: list of per-model predictions
        - ``output.energy_disagreement_meV_per_atom``: |E_DPA - E_MACE| in meV/atom
        - ``output.force_rmse_disagreement_eV_per_Ang``: |F_DPA - F_MACE|
        - ``output.routing_decision``: one of promote|queue_dft|hard_reject

        The falsifier block is populated by ``L2MlipOutput.falsifier_items()``.

        Returns
        -------
        dict
            Ensemble Envelope dict ready for ``Envelope.model_validate``.
        """
        # ---- Wave C: dispatch hook ---------------------------------------
        # When a RunpodDispatcher is attached AND its configured L2 backend
        # is ``runpod_rest``, hit the live REST endpoint and return the
        # decoded envelope verbatim (the server is responsible for emitting
        # an envelope-shaped response with backend="runpod_rest").  When
        # the configured backend is ``runpod_mock``, return the mock
        # envelope.  Any other backend (``local_stub`` / ``local_cpu``)
        # makes ``dispatch()`` return None and we fall through to the
        # mandatory DPA-3 + MACE local ensemble below.
        #
        # CRITICAL: if ``runpod_rest`` is configured but credentials are
        # missing, ``dispatcher.dispatch`` raises ``RunpodCredentialsError``
        # — we MUST propagate that exception rather than silently falling
        # back to the local ensemble or to the mock backend.  This is the
        # honest-block invariant Wave C enforces (see the docstring on
        # :class:`RunpodDispatcher` and the tests in
        # tests/parity/test_runpod_dispatcher.py).
        if self._dispatcher is not None:
            structure_for_payload = {**structure, "request_id": request.run_id}
            mock_output_payload = {
                "energy_per_atom_eV": -6.10,
                "routing_decision": "promote",
                "committee_size": 2,
            }
            dispatch_result = self._dispatcher.dispatch(
                layer="L2",
                endpoint="ensemble_predict",
                payload=structure_for_payload,
                mock_output=mock_output_payload,
            )
            if dispatch_result is not None:
                return dispatch_result.payload

        # ---- mandatory adapters -------------------------------------------
        dpa_envelope = self._dpa.predict(structure, request)
        mace_envelope = self._mace.predict(structure, request)

        dpa_pred = dpa_envelope["output"]["predictions"][0]
        mace_pred = mace_envelope["output"]["predictions"][0]

        # ---- optional adapters -------------------------------------------
        optional_preds: list[dict[str, Any]] = []
        for opt in self._optional:
            try:
                opt_env = opt.predict(structure, request)
                optional_preds.extend(opt_env["output"]["predictions"])
            except Exception:
                # Optional adapters failing (e.g., LicenseGateError) do not
                # abort the mandatory ensemble.
                pass

        # ---- disagreement metrics ----------------------------------------
        energy_disagreement_eV = abs(
            dpa_pred["energy_eV_per_atom"] - mace_pred["energy_eV_per_atom"]
        )
        energy_disagreement_meV = energy_disagreement_eV * 1000.0
        force_rmse_disagreement = abs(
            dpa_pred["force_rmse_eV_per_Ang"] - mace_pred["force_rmse_eV_per_Ang"]
        )

        routing = _decide_routing(energy_disagreement_meV, force_rmse_disagreement)

        all_predictions = [dpa_pred, mace_pred] + optional_preds

        output = {
            "predictions": all_predictions,
            "energy_disagreement_meV_per_atom": energy_disagreement_meV,
            "force_rmse_disagreement_eV_per_Ang": force_rmse_disagreement,
            "routing_decision": routing,
        }

        # ---- falsifier items from output model ---------------------------
        l2_out = L2MlipOutput.model_validate(output)
        falsifier_items = [f.model_dump(mode="json") for f in l2_out.falsifier_items()]
        falsifier_status = (
            "fail" if any(f["status"] == "fail" for f in falsifier_items) else "pass"
        )

        # ---- disagreement metrics for envelope ---------------------------
        agrees_or_contradicts = (
            "AGREES_WITH"
            if energy_disagreement_meV <= _PROMOTE_ENERGY_THRESHOLD_MEV
            else "CONTRADICTS"
        )
        disagreement_metrics = [
            {
                "name": "dpa_mace_energy_disagreement",
                "value": energy_disagreement_meV,
                "unit": "meV/atom",
                "references": [dpa_pred["model"], mace_pred["model"]],
            },
            {
                "name": "dpa_mace_force_rmse_disagreement",
                "value": force_rmse_disagreement,
                "unit": "eV/Ang",
                "references": [dpa_pred["model"], mace_pred["model"]],
            },
        ]

        # ---- hashing -------------------------------------------------------
        s_hash = structure_hash(structure)
        out_hash = "sha256:" + sha256_of(output).split("sha256:", 1)[1]

        return {
            "research_boundary": RESEARCH_BOUNDARY,
            "contract_version": "zer0pa.materials.layer-envelope.v1",
            "layer": "L2",
            "run_id": request.run_id,
            "candidate_id": request.candidate_id,
            "campaign_id": request.campaign_id,
            "tool_adapter": {
                "name": "L2EnsembleRunner",
                "version": "0.1.0",
                "backend": "stub",
                "engine": "DPA-3.1-3M+MACE-MPA-0",
            },
            "output": output,
            "confidence": {
                "score": max(0.0, 1.0 - energy_disagreement_meV / 100.0),
                "band": (
                    "high" if energy_disagreement_meV < 10.0
                    else "medium" if energy_disagreement_meV < 25.0
                    else "low"
                ),
                "basis": [
                    f"dpa_mace_energy_disagreement={energy_disagreement_meV:.3f}_meV",
                    f"routing={routing}",
                ],
            },
            "disagreement": {"metrics": disagreement_metrics},
            "falsifier": {
                "status": falsifier_status,
                "items": falsifier_items,
            },
            "audit": {
                "audit_record_id": f"audit:{request.run_id}/ensemble",
                "input_hash": s_hash,
                "output_hash": out_hash,
                "source_manifest_refs": [
                    "src:deepmd:dpa-3.1-3m-weights",
                    "src:mace:mpa0-checkpoint",
                ],
            },
            "rights": {
                "rights_claim_id": request.rights_claim_id,
                "reuse_scope": "tenant_only",
            },
            "back_edges": [],
            # Routing decision is duplicated at the envelope top level for
            # the falsifier gate (dpa_mace_disagreement_routing) to consume
            # without parsing the output dict.
            "_ensemble_meta": {
                "routing_decision": routing,
                "dpa_model": dpa_pred["model"],
                "mace_model": mace_pred["model"],
                "energy_disagreement_meV": energy_disagreement_meV,
                "force_rmse_disagreement_eV_Ang": force_rmse_disagreement,
                "dpa_mace_relation": agrees_or_contradicts,
            },
        }

    def blocked_manifests(self) -> list[dict[str, Any]]:
        """Return all blocked manifests from DPA, MACE, and optional adapters."""
        manifests: list[dict[str, Any]] = []
        manifests.extend(self._dpa.blocked_manifests())
        manifests.extend(self._mace.blocked_manifests())
        for opt in self._optional:
            manifests.extend(opt.blocked_manifests())
        # Wave C: surface manifests recorded by the Runpod dispatcher when
        # ``runpod_rest`` was requested but credentials were missing.  The
        # dispatcher already raised ``RunpodCredentialsError`` upstream;
        # this list is the structured trail the operator inspects to see
        # *why* the run was blocked.
        if self._dispatcher is not None:
            for m in self._dispatcher.blocked_manifests():
                manifests.append(m.model_dump(mode="json"))
        return manifests

    # ------------------------------------------------------------------ KG writes

    def write_kg_nodes(
        self,
        kg: Any,  # MaterialsKG — typed as Any to avoid circular import at module level
        envelope: dict[str, Any],
        run_id: str,
    ) -> None:
        """Write L2 KG nodes and edges from a completed ensemble envelope.

        Nodes emitted:
            - SimulationJob (ensemble run)
            - SimulationResult per model prediction
            - EnsembleSimulationResult (the merged result)
            - DisagreementMetric
            - Decision (routing)

        Edges emitted:
            - SimulationResult -[MEMBER_OF_ENSEMBLE]-> EnsembleSimulationResult
            - DisagreementMetric (AGREES_WITH or CONTRADICTS)
            - Decision -[ROUTED_TO]-> SimulationJob
        """
        from zer0pa_materials_workbench.audit.kg import KGEdgeType, KGNodeType

        output = envelope.get("output", {})
        meta = envelope.get("_ensemble_meta", {})
        routing = meta.get("routing_decision", output.get("routing_decision", "promote"))

        job_id = f"sim_job:{run_id}"
        ensemble_result_id = f"sim_result:{run_id}/ensemble"
        decision_id = f"decision:{run_id}/routing"

        # SimulationJob
        kg.add_node(
            node_id=job_id,
            node_type=KGNodeType.SimulationJob,
            properties={"run_id": run_id, "backend": "stub", "layer": "L2"},
            run_id=run_id,
        )

        # EnsembleSimulationResult
        kg.add_node(
            node_id=ensemble_result_id,
            node_type=KGNodeType.SimulationResult,
            properties={
                "energy_disagreement_meV": output.get("energy_disagreement_meV_per_atom"),
                "force_rmse_disagreement_eV_Ang": output.get(
                    "force_rmse_disagreement_eV_per_Ang"
                ),
                "routing_decision": routing,
                "result_type": "ensemble",
            },
            run_id=run_id,
        )

        # Per-model SimulationResult nodes + MEMBER_OF_ENSEMBLE edges.
        for pred in output.get("predictions", []):
            pred_id = f"sim_result:{run_id}/{pred['model'].lower().replace('.', '-').replace('+', '-')}"
            kg.add_node(
                node_id=pred_id,
                node_type=KGNodeType.SimulationResult,
                properties={
                    "model": pred["model"],
                    "energy_eV_per_atom": pred["energy_eV_per_atom"],
                    "force_rmse_eV_per_Ang": pred["force_rmse_eV_per_Ang"],
                },
                run_id=run_id,
            )
            kg.add_edge(
                src_id=pred_id,
                dst_id=ensemble_result_id,
                edge_type=KGEdgeType.MEMBER_OF_ENSEMBLE,
                properties={"model": pred["model"]},
                run_id=run_id,
            )

        # DisagreementMetric node.
        disagree_id = f"disagree:{run_id}/energy"
        kg.add_node(
            node_id=disagree_id,
            node_type=KGNodeType.DisagreementMetric,
            properties={
                "metric_name": "dpa_mace_energy_disagreement",
                "value": output.get("energy_disagreement_meV_per_atom"),
                "unit": "meV/atom",
            },
            run_id=run_id,
        )

        # AGREES_WITH or CONTRADICTS edge between the two model result nodes.
        relation = meta.get("dpa_mace_relation", "AGREES_WITH")
        dpa_id = f"sim_result:{run_id}/dpa-3-1-3m"
        mace_id = f"sim_result:{run_id}/mace-mpa-0"
        for src_id, dst_id in [(dpa_id, mace_id), (mace_id, dpa_id)]:
            try:
                edge_type = (
                    KGEdgeType.AGREES_WITH
                    if relation == "AGREES_WITH"
                    else KGEdgeType.CONTRADICTS
                )
                kg.add_edge(
                    src_id=src_id,
                    dst_id=dst_id,
                    edge_type=edge_type,
                    properties={"basis": "energy_disagreement", "routing": routing},
                    run_id=run_id,
                )
            except Exception:
                # Nodes may not exist if model names differ; skip edge safely.
                pass

        # Decision node + ROUTED_TO edge.
        kg.add_node(
            node_id=decision_id,
            node_type=KGNodeType.Decision,
            properties={
                "routing_decision": routing,
                "energy_disagreement_meV": output.get("energy_disagreement_meV_per_atom"),
                "force_rmse_disagreement": output.get("force_rmse_disagreement_eV_per_Ang"),
            },
            run_id=run_id,
        )
        kg.add_edge(
            src_id=decision_id,
            dst_id=job_id,
            edge_type=KGEdgeType.ROUTED_TO,
            properties={"routing_decision": routing},
            run_id=run_id,
        )
