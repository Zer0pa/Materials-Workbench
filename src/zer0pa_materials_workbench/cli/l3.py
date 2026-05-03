"""L3 CALPHAD CLI commands — typer sub-application.

Commands:
    equilibrium        Run pycalphad equilibrium on a TDB
    fit                Run an ESPEI Bayesian TDB fit (synthetic posterior in stub)
    sovereign          Run the full DFT/MLIP -> prior -> ESPEI -> pycalphad pipeline
    quarantine-status  Show ThermoCalcTdbReadOnlyAdapter posture
    blocked            List BlockedSourceManifest entries for the L3 layer
    healthz            Local L3 service health check
    pfp-enable         Show instructions for enabling PhaseForgePlus

This module exposes ``l3_app`` for registration via the main app's
``add_typer`` call.
"""

from __future__ import annotations

import json
from pathlib import Path

try:
    import typer
    _TYPER_AVAILABLE = True
except ImportError:  # pragma: no cover
    _TYPER_AVAILABLE = False

from zer0pa_materials_workbench.adapters.l3 import (
    EspeiBayesianFitAdapter,
    L3CalphadRequest,
    PhaseForgePlusMlipPriorAdapter,
    PyCalphadEquilibriumAdapter,
    SovereignCalphadPipeline,
    ThermoCalcTdbReadOnlyAdapter,
)
from zer0pa_materials_workbench.adapters.l3.espei_fit import ESPEI_AVAILABLE
from zer0pa_materials_workbench.adapters.l3.pycalphad_equilibrium import PYCALPHAD_AVAILABLE
from zer0pa_materials_workbench.boundary import RESEARCH_BOUNDARY

if _TYPER_AVAILABLE:
    l3_app = typer.Typer(name="l3", help="L3 CALPHAD commands (sovereign pycalphad/ESPEI).")
else:  # pragma: no cover
    l3_app = None  # type: ignore[assignment]


if _TYPER_AVAILABLE:

    @l3_app.command("equilibrium")
    def equilibrium_cmd(
        tdb_path: Path = typer.Argument(
            ..., help="Path to a TDB file (sovereign open path)."
        ),
        run_id: str = typer.Option("run:l3/cli/eq/001", help="URN run identifier."),
        candidate_id: str = typer.Option(
            "candidate:cli/eq/001", help="URN candidate identifier."
        ),
        campaign_id: str = typer.Option(
            "campaign:cli/001", help="URN campaign identifier."
        ),
        rights_claim_id: str = typer.Option(
            "rights:cli/001", help="URN rights claim identifier."
        ),
        temperature_K: float = typer.Option(1000.0, help="Equilibrium temperature (K)."),
        output_json: Path | None = typer.Option(
            None, help="Write envelope JSON to this path (stdout if omitted)."
        ),
    ) -> None:
        """Run a pycalphad equilibrium calculation."""
        adapter = PyCalphadEquilibriumAdapter()
        req = L3CalphadRequest(
            run_id=run_id,
            candidate_id=candidate_id,
            campaign_id=campaign_id,
            rights_claim_id=rights_claim_id,
            tdb_path=str(tdb_path),
            extra={"temperature_K": temperature_K},
        )
        envelope = adapter.run(req)
        envelope_json = json.dumps(envelope, indent=2, default=str)
        if output_json:
            output_json.write_text(envelope_json)
            typer.echo(f"Envelope written to {output_json}")
        else:
            typer.echo(envelope_json)

    @l3_app.command("fit")
    def fit_cmd(
        tdb_path: Path | None = typer.Option(
            None, help="Optional starting TDB path."
        ),
        run_id: str = typer.Option("run:l3/cli/fit/001", help="URN run identifier."),
        candidate_id: str = typer.Option(
            "candidate:cli/fit/001", help="URN candidate identifier."
        ),
        campaign_id: str = typer.Option(
            "campaign:cli/001", help="URN campaign identifier."
        ),
        rights_claim_id: str = typer.Option(
            "rights:cli/001", help="URN rights claim identifier."
        ),
        n_walkers: int = typer.Option(16, help="Number of MCMC walkers."),
        n_steps: int = typer.Option(200, help="MCMC steps per walker."),
        n_burn_in: int = typer.Option(50, help="Burn-in steps to drop."),
        output_json: Path | None = typer.Option(
            None, help="Write envelope JSON to this path."
        ),
    ) -> None:
        """Run an ESPEI Bayesian TDB fit (real or calibrated synthetic)."""
        adapter = EspeiBayesianFitAdapter(
            n_walkers=n_walkers, n_steps=n_steps, n_burn_in=n_burn_in
        )
        req = L3CalphadRequest(
            run_id=run_id,
            candidate_id=candidate_id,
            campaign_id=campaign_id,
            rights_claim_id=rights_claim_id,
            tdb_path=str(tdb_path) if tdb_path else None,
        )
        envelope = adapter.run(req)
        envelope_json = json.dumps(envelope, indent=2, default=str)
        if output_json:
            output_json.write_text(envelope_json)
            typer.echo(f"Envelope written to {output_json}")
        else:
            typer.echo(envelope_json)

    @l3_app.command("sovereign")
    def sovereign_cmd(
        tdb_path: Path | None = typer.Option(
            None, help="Optional starting TDB path."
        ),
        run_id: str = typer.Option(
            "run:l3/cli/sovereign/001", help="URN run identifier."
        ),
        candidate_id: str = typer.Option(
            "candidate:cli/sovereign/001", help="URN candidate identifier."
        ),
        campaign_id: str = typer.Option(
            "campaign:cli/001", help="URN campaign identifier."
        ),
        rights_claim_id: str = typer.Option(
            "rights:cli/001", help="URN rights claim identifier."
        ),
        output_json: Path | None = typer.Option(
            None, help="Write envelope chain JSON to this path."
        ),
    ) -> None:
        """Run the sovereign pipeline (DFT/MLIP -> prior -> ESPEI -> pycalphad)."""
        pipeline = SovereignCalphadPipeline()
        req = L3CalphadRequest(
            run_id=run_id,
            candidate_id=candidate_id,
            campaign_id=campaign_id,
            rights_claim_id=rights_claim_id,
            tdb_path=str(tdb_path) if tdb_path else None,
        )
        envelopes = pipeline.run_with_chain(req)
        result = {
            "envelopes": envelopes,
            "summary_envelope": envelopes[-1],
            "n_steps": len(envelopes),
        }
        result_json = json.dumps(result, indent=2, default=str)
        if output_json:
            output_json.write_text(result_json)
            typer.echo(f"Pipeline result written to {output_json}")
        else:
            typer.echo(result_json)

    @l3_app.command("quarantine-status")
    def quarantine_status_cmd() -> None:
        """Show the Thermo-Calc QUARANTINE adapter posture."""
        adapter = ThermoCalcTdbReadOnlyAdapter()
        typer.echo(
            json.dumps(
                {
                    "adapter": adapter.NAME,
                    "version": adapter.VERSION,
                    "enabled": adapter.enabled,
                    "customer_id": adapter.customer_id,
                    "license_proof_uri": adapter.license_proof_uri,
                    "enabled_at": adapter.enabled_at,
                    "policy_summary": (
                        "Default-blocked. Commercial Thermo-Calc TDBs are "
                        "ALLOWED only as quarantined read-only inputs for "
                        "customer projects with valid license coverage. "
                        "NEVER committed, copied to fixtures, redistributed, "
                        "or used as training data."
                    ),
                },
                indent=2,
            )
        )

    @l3_app.command("blocked")
    def blocked_cmd() -> None:
        """List all BlockedSourceManifest entries for the L3 layer."""
        manifests: list[dict] = []
        manifests.extend(PyCalphadEquilibriumAdapter().blocked_manifests())
        manifests.extend(EspeiBayesianFitAdapter().blocked_manifests())
        manifests.extend(PhaseForgePlusMlipPriorAdapter().blocked_manifests())
        manifests.extend(ThermoCalcTdbReadOnlyAdapter().blocked_manifests())
        typer.echo(json.dumps(manifests, indent=2, default=str))

    @l3_app.command("healthz")
    def healthz_cmd() -> None:
        """Local L3 health check."""
        import datetime as _dt

        typer.echo(
            json.dumps(
                {
                    "status": "ok",
                    "service": "l3_calphad",
                    "pycalphad_available": PYCALPHAD_AVAILABLE,
                    "espei_available": ESPEI_AVAILABLE,
                    "research_boundary": RESEARCH_BOUNDARY,
                    "timestamp": _dt.datetime.now(tz=_dt.timezone.utc).isoformat(timespec="seconds"),
                },
                indent=2,
            )
        )

    @l3_app.command("pfp-enable")
    def pfp_enable_cmd() -> None:
        """Show instructions for enabling the PhaseForgePlus prior adapter."""
        typer.echo(
            "\n".join(
                [
                    "PhaseForgePlus prior adapter is BLOCKED by default.",
                    "",
                    "To enable (PRD §L3 mandate — license verification required):",
                    "  1. Visit https://github.com/dogusariturk/PhaseForgePlus",
                    "  2. Confirm the LICENSE file (Brief #2 claims MIT; verify live).",
                    "  3. Pin a release tag.",
                    "  4. Call in Python:",
                    "       from zer0pa_materials_workbench.adapters.l3 import (",
                    "           PhaseForgePlusMlipPriorAdapter,",
                    "       )",
                    "       adapter = PhaseForgePlusMlipPriorAdapter()",
                    "       adapter.enable_with_verified_license(",
                    "           license_proof_uri='<URI of LICENSE file>',",
                    "           license_spdx='MIT',",
                    "           verified_at='<iso-utc>',",
                    "       )",
                    "",
                    "Until enabled, the adapter serves a synthetic prior so",
                    "downstream ESPEI/pycalphad still has a numerically-valid",
                    "input, but the envelope's _phaseforgeplus_meta.enabled=False",
                    "and the falsifier l3.phaseforgeplus_license_gate returns",
                    "status='blocked'.",
                ]
            )
        )
