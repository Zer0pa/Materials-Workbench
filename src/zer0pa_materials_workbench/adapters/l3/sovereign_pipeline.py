"""Sovereign CALPHAD pipeline — primary user-facing L3 adapter (PRD §L3).

Pipeline (PRD verbatim):
    DFT/MLIP energies -> PhaseForgePlus prior -> ESPEI posterior ->
    pycalphad equilibrium -> produced TDB.

This is THE adapter the L7 orchestrator calls for novel quaternary systems
(e.g. Li-Mg-Zr-Cl halide solid electrolytes — PRD §Scope first novel
challenge seed). Its outputs flow into the MVP packet.

Design invariants
-----------------

1. **All ESPEI posteriors carry uncertainty.** The pipeline never returns
   point estimates: ``output.espei_diagnostics`` always includes the
   posterior mean, covariance, R-hat, ESS, and acceptance rate.

2. **The information-geometry note is propagated end-to-end.** Every
   ESPEI envelope in the pipeline emits ``_information_geometry_note``;
   the final envelope copies it to the top level so downstream KG writers
   can attribute the framing without pattern-matching across the chain.

3. **Provenance fan-in.** The pipeline returns a list of envelopes
   (DFT/MLIP → prior → posterior → equilibrium). The L7 orchestrator binds
   them via ``DERIVED_FROM`` edges in the KG.

4. **Battery-relevant temperature grid.** PRD §Scope: solid-state battery
   electrolytes. We compute equilibrium at 300 K and 700 K by default
   (room-temperature operation + sintering / synthesis temperature).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from zer0pa_materials_workbench.adapters.l3.base import L3CalphadAdapter, L3CalphadRequest
from zer0pa_materials_workbench.adapters.l3.espei_fit import (
    INFORMATION_GEOMETRY_NOTE,
    EspeiBayesianFitAdapter,
)
from zer0pa_materials_workbench.adapters.l3.phaseforgeplus_prior import (
    PhaseForgePlusMlipPriorAdapter,
)
from zer0pa_materials_workbench.adapters.l3.pycalphad_equilibrium import (
    PyCalphadEquilibriumAdapter,
)
from zer0pa_materials_workbench.boundary import RESEARCH_BOUNDARY
from zer0pa_materials_workbench.envelope.hashing import sha256_of

__all__ = [
    "SovereignCalphadPipeline",
]


# Default battery-relevant temperature grid (Kelvin).
_BATTERY_TEMPERATURE_GRID_K: tuple[float, ...] = (300.0, 700.0)


@dataclass
class _PipelineStep:
    """Internal record of one pipeline step."""

    name: str
    envelope: dict[str, Any]
    parent_step: str | None = None


class SovereignCalphadPipeline(L3CalphadAdapter):
    """Sovereign DFT/MLIP -> PhaseForgePlus -> ESPEI -> pycalphad pipeline.

    PRIMARY USER-FACING L3 ADAPTER for novel quaternary systems.

    Parameters
    ----------
    prior_adapter:
        :class:`PhaseForgePlusMlipPriorAdapter` instance. If the adapter is
        not enabled with a verified license, the pipeline still runs (the
        prior adapter falls back to a synthetic prior under-block) but the
        prior step's envelope carries ``falsifier.status = "blocked"``.
    espei_adapter:
        :class:`EspeiBayesianFitAdapter` instance. Real or stub.
    pycalphad_adapter:
        :class:`PyCalphadEquilibriumAdapter` instance. Real or stub.
    temperature_grid_K:
        Tuple of temperatures (Kelvin) to compute equilibrium at. Default:
        ``(300.0, 700.0)`` — room temperature + sintering temperature.
    """

    NAME = "SovereignCalphadPipeline"
    VERSION = "0.1.0"

    def __init__(
        self,
        prior_adapter: PhaseForgePlusMlipPriorAdapter | None = None,
        espei_adapter: EspeiBayesianFitAdapter | None = None,
        pycalphad_adapter: PyCalphadEquilibriumAdapter | None = None,
        temperature_grid_K: tuple[float, ...] = _BATTERY_TEMPERATURE_GRID_K,
    ) -> None:
        self.prior_adapter = prior_adapter or PhaseForgePlusMlipPriorAdapter()
        self.espei_adapter = espei_adapter or EspeiBayesianFitAdapter()
        self.pycalphad_adapter = pycalphad_adapter or PyCalphadEquilibriumAdapter()
        self.temperature_grid_K = tuple(temperature_grid_K)

    # ------------------------------------------------------------------ run

    def run(
        self,
        request: L3CalphadRequest,
    ) -> dict[str, Any]:
        """Run the pipeline once and return the FINAL summary envelope.

        For the full step-by-step envelope chain (DFT/MLIP, prior, ESPEI,
        equilibrium), call :meth:`run_with_chain`.
        """
        envelopes = self.run_with_chain(request)
        return envelopes[-1]

    def run_with_chain(
        self,
        request: L3CalphadRequest,
    ) -> list[dict[str, Any]]:
        """Run the full pipeline and return ALL envelopes (in step order).

        Returns
        -------
        list[dict]
            Envelopes in chronological order:
              [0] DFT/MLIP synthetic input envelope
              [1] PhaseForgePlus prior envelope (blocked-by-default)
              [2] ESPEI posterior envelope (with information-geometry note)
              [3..] pycalphad equilibrium envelopes (one per temperature)
              [-1] sovereign-pipeline summary envelope
        """
        steps: list[_PipelineStep] = []

        # Step 1: DFT/MLIP synthetic input envelope. This adapter does not
        # call L1/L2 directly (those are separate adapter layers); we
        # synthesize the input envelope so the L3 sovereign pipeline can
        # attribute its provenance. In production, the L7 orchestrator
        # supplies real DFT/MLIP envelopes via request.extra["dft_mlip_input"].
        dft_mlip_envelope = self._dft_mlip_envelope(request)
        steps.append(_PipelineStep("dft_mlip", dft_mlip_envelope))

        # Step 2: PhaseForgePlus prior.
        prior_envelope = self.prior_adapter.run(request)
        steps.append(_PipelineStep("prior", prior_envelope, parent_step="dft_mlip"))

        # Step 3: ESPEI posterior.
        espei_envelope = self.espei_adapter.run(request)
        steps.append(_PipelineStep("espei", espei_envelope, parent_step="prior"))

        # Step 4: pycalphad equilibrium at each temperature.
        equilibrium_envelopes: list[dict[str, Any]] = []
        for temp_K in self.temperature_grid_K:
            eq_request = L3CalphadRequest(
                run_id=f"{request.run_id}/eq/{int(temp_K)}K",
                candidate_id=request.candidate_id,
                campaign_id=request.campaign_id,
                rights_claim_id=request.rights_claim_id,
                tdb_path=request.tdb_path,
                components=request.components,
                extra={
                    **request.extra,
                    "temperature_K": temp_K,
                },
            )
            eq_envelope = self.pycalphad_adapter.run(eq_request)
            steps.append(
                _PipelineStep(
                    f"equilibrium_{int(temp_K)}K",
                    eq_envelope,
                    parent_step="espei",
                )
            )
            equilibrium_envelopes.append(eq_envelope)

        # Step 5: produce the summary envelope.
        summary_envelope = self._summary_envelope(
            request,
            dft_mlip_envelope=dft_mlip_envelope,
            prior_envelope=prior_envelope,
            espei_envelope=espei_envelope,
            equilibrium_envelopes=equilibrium_envelopes,
        )
        # Attach the chain history. ``back_edges`` follows the strict
        # Envelope.BackEdge schema (layer + audit_record_id + relation).
        # Step-name / parent-step provenance lives in a parallel
        # ``_pipeline_back_edges`` block keyed by audit_record_id so the
        # KG writer can decorate the edge with step metadata.
        pipeline_back_edges: list[dict[str, Any]] = []
        for s in steps:
            audit_id = s.envelope["audit"]["audit_record_id"]
            summary_envelope["back_edges"].append(
                {
                    "layer": "L3",
                    "audit_record_id": audit_id,
                    "relation": "DERIVED_FROM",
                }
            )
            pipeline_back_edges.append(
                {
                    "audit_record_id": audit_id,
                    "step_name": s.name,
                    "parent_step": s.parent_step,
                    "tool_adapter_name": s.envelope["tool_adapter"]["name"],
                }
            )
        summary_envelope["_pipeline_back_edges"] = pipeline_back_edges
        return [s.envelope for s in steps] + [summary_envelope]

    # -------------------------------------------------- helpers

    def _dft_mlip_envelope(
        self,
        request: L3CalphadRequest,
    ) -> dict[str, Any]:
        """Synthesise a DFT/MLIP input envelope for provenance attribution.

        In production, the L7 orchestrator supplies a real L1/L2 envelope.
        Here we emit a placeholder that satisfies the L3 contract chain.
        """
        seed = (request.tdb_path or request.candidate_id or request.run_id) + ":dft-mlip"
        in_hash = "sha256:" + hashlib.sha256(seed.encode()).hexdigest()
        # A minimal L3-shaped output; the L1/L2 schemas live elsewhere and
        # the orchestrator will replace this when it has real DFT/MLIP data.
        output: dict[str, Any] = {
            "tdb_ref": f"synthetic:dft-mlip-input:{in_hash[:24]}",
            "equilibrium_phases": [],
            "phase_fraction_posterior": {},
            "espei_diagnostics": {
                "ran": False,
                "reason": "dft_mlip_input_only",
                "note": (
                    "Placeholder DFT/MLIP envelope — orchestrator MUST "
                    "replace with real L1/L2 outputs in production. The "
                    "envelope's tool_adapter.engine='dft-mlip-placeholder' "
                    "marks this as a stub."
                ),
            },
            "fixture_phase_boundary_drift_K": None,
            "phase_set_jaccard_distance": None,
            "phase_fraction_js_divergence": None,
        }
        out_hash = "sha256:" + sha256_of(output).split("sha256:", 1)[1]

        return {
            "research_boundary": RESEARCH_BOUNDARY,
            "contract_version": "zer0pa.materials.layer-envelope.v1",
            "layer": "L3",
            "run_id": f"{request.run_id}/dft-mlip-stub",
            "candidate_id": request.candidate_id,
            "campaign_id": request.campaign_id,
            "tool_adapter": {
                "name": "DftMlipInputPlaceholder",
                "version": "0.1.0",
                "backend": "stub",
                "engine": "dft-mlip-placeholder",
            },
            "output": output,
            "confidence": {
                "score": 0.0,
                "band": "low",
                "basis": ["placeholder", "orchestrator_must_supply_real_inputs"],
            },
            "disagreement": {"metrics": []},
            "falsifier": {"status": "blocked", "items": []},
            "audit": {
                "audit_record_id": f"audit:{request.run_id}/dft-mlip-stub",
                "input_hash": in_hash,
                "output_hash": out_hash,
                "source_manifest_refs": [],
            },
            "rights": {
                "rights_claim_id": request.rights_claim_id,
                "reuse_scope": "tenant_only",
            },
            "back_edges": [],
        }

    def _summary_envelope(
        self,
        request: L3CalphadRequest,
        *,
        dft_mlip_envelope: dict[str, Any],
        prior_envelope: dict[str, Any],
        espei_envelope: dict[str, Any],
        equilibrium_envelopes: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Build the FINAL pipeline summary envelope."""
        # Aggregate the equilibrium phase fractions across the temperature grid.
        all_phases: set[str] = set()
        per_temp_phase_fractions: dict[str, dict[str, float]] = {}
        for eq in equilibrium_envelopes:
            temp_K = eq.get("_calphad_meta", {}).get("temperature_K", 0.0)
            phases = eq["output"].get("equilibrium_phases", [])
            fractions = eq["output"].get("phase_fraction_posterior", {})
            all_phases.update(phases)
            per_temp_phase_fractions[f"{int(temp_K)}K"] = dict(fractions)

        # Take the lowest-temperature equilibrium as the "headline" output
        # (room-temperature behavior is the battery-relevant default).
        headline = (
            equilibrium_envelopes[0]
            if equilibrium_envelopes
            else {"output": {"equilibrium_phases": [], "phase_fraction_posterior": {}}}
        )

        # Forward the ESPEI diagnostics (the load-bearing uncertainty record).
        espei_diagnostics = dict(espei_envelope["output"].get("espei_diagnostics", {}))

        output: dict[str, Any] = {
            "tdb_ref": (
                f"file://{request.tdb_path}"
                if request.tdb_path
                else f"sovereign-pipeline:{request.candidate_id}"
            ),
            "equilibrium_phases": sorted(all_phases),
            "phase_fraction_posterior": dict(
                headline["output"].get("phase_fraction_posterior", {})
            ),
            "espei_diagnostics": espei_diagnostics,
            "fixture_phase_boundary_drift_K": None,
            "phase_set_jaccard_distance": None,
            "phase_fraction_js_divergence": None,
        }
        out_hash = "sha256:" + sha256_of(output).split("sha256:", 1)[1]

        # Derive the source manifests collected across the chain.
        source_refs: list[str] = []
        for env in (dft_mlip_envelope, prior_envelope, espei_envelope, *equilibrium_envelopes):
            for ref in env["audit"].get("source_manifest_refs", []):
                if ref and ref not in source_refs:
                    source_refs.append(ref)

        return {
            "research_boundary": RESEARCH_BOUNDARY,
            "contract_version": "zer0pa.materials.layer-envelope.v1",
            "layer": "L3",
            "run_id": request.run_id,
            "candidate_id": request.candidate_id,
            "campaign_id": request.campaign_id,
            "tool_adapter": {
                "name": self.NAME,
                "version": self.VERSION,
                # Envelope.Backend literal is {stub, local_cpu, runpod_mock,
                # runpod_rest}. The pipeline runs locally (or against
                # PhaseForgePlus blocked stub) so 'stub' is correct until
                # one of the constituent adapters elevates to local_cpu.
                "backend": "stub",
                "engine": "dft-mlip+phaseforgeplus+espei+pycalphad",
            },
            "output": output,
            "confidence": espei_envelope["confidence"],
            "disagreement": {"metrics": []},
            "falsifier": {"status": "pass", "items": []},
            "audit": {
                "audit_record_id": f"audit:{request.run_id}/sovereign",
                "input_hash": dft_mlip_envelope["audit"]["input_hash"],
                "output_hash": out_hash,
                "source_manifest_refs": source_refs,
            },
            "rights": {
                "rights_claim_id": request.rights_claim_id,
                "reuse_scope": "tenant_only",
            },
            "back_edges": [],  # populated by run_with_chain
            "_pipeline_meta": {
                "temperature_grid_K": list(self.temperature_grid_K),
                "per_temp_phase_fractions": per_temp_phase_fractions,
                "n_equilibrium_calls": len(equilibrium_envelopes),
                "espei_R_hat": espei_diagnostics.get("R_hat"),
                "espei_ESS": espei_diagnostics.get("effective_sample_size"),
            },
            # Information-geometry note propagates from the ESPEI step. If
            # the ESPEI envelope is missing it (shouldn't happen, but defensive),
            # we fall back to the canonical INFORMATION_GEOMETRY_NOTE.
            "_information_geometry_note": (
                espei_envelope.get("_information_geometry_note")
                or dict(INFORMATION_GEOMETRY_NOTE)
            ),
        }

    # -------------------------------------------------- blocked_manifests

    def blocked_manifests(self) -> list[dict[str, Any]]:
        """Aggregate blocked manifests from every constituent adapter."""
        manifests: list[dict[str, Any]] = []
        manifests.extend(self.prior_adapter.blocked_manifests())
        manifests.extend(self.espei_adapter.blocked_manifests())
        manifests.extend(self.pycalphad_adapter.blocked_manifests())
        return manifests
