"""L5 continuum CLI commands — Typer sub-application.

Commands:
    run          Run FEniCSx + deal.II + OpenFOAM continuum adapters
    homogenise   Homogenise a microstructure trajectory (L4 → L5)
    blocked      List all blocked manifests for L5 adapters
    healthz      Check L5 service health (local stub only)

Do NOT modify cli/main.py to add these — register via the main app's
``add_typer`` call.  This module exposes ``l5_app`` for that purpose.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

try:
    import typer
    _TYPER_AVAILABLE = True
except ImportError:  # pragma: no cover
    _TYPER_AVAILABLE = False

from zer0pa_materials_workbench.adapters.l5.base import L5ContinuumRequest
from zer0pa_materials_workbench.adapters.l5.dealii import DealIIStructuralAdapter
from zer0pa_materials_workbench.adapters.l5.fenicsx import FEniCSxContinuumAdapter
from zer0pa_materials_workbench.adapters.l5.homogenisation import HomogenisationOperator
from zer0pa_materials_workbench.adapters.l5.openfoam import OpenFOAMProcessAdapter
from zer0pa_materials_workbench.boundary import RESEARCH_BOUNDARY

if _TYPER_AVAILABLE:
    l5_app = typer.Typer(name="l5", help="L5 continuum FEM/CFD commands.")
else:  # pragma: no cover
    l5_app = None  # type: ignore[assignment]


def _make_request(
    run_id: str,
    candidate_id: str,
    campaign_id: str,
    rights_claim_id: str,
) -> L5ContinuumRequest:
    return L5ContinuumRequest(
        run_id=run_id,
        candidate_id=candidate_id,
        campaign_id=campaign_id,
        rights_claim_id=rights_claim_id,
    )


if _TYPER_AVAILABLE:

    @l5_app.command("run")
    def run_cmd(
        run_id: str = typer.Option(
            "run:l5/cli/001",
            help="URN run identifier.",
        ),
        candidate_id: str = typer.Option(
            "candidate:cli/001",
            help="URN candidate identifier.",
        ),
        campaign_id: str = typer.Option(
            "campaign:cli/001",
            help="URN campaign identifier.",
        ),
        rights_claim_id: str = typer.Option(
            "rights:cli/001",
            help="URN rights claim identifier.",
        ),
        output_json: Path | None = typer.Option(
            None, help="Write envelope JSON to this path (stdout if not set)."
        ),
    ) -> None:
        """Run FEniCSx + deal.II + OpenFOAM L5 adapters; print/write the envelope."""
        req = _make_request(run_id, candidate_id, campaign_id, rights_claim_id)
        fenicsx = FEniCSxContinuumAdapter()
        dealii = DealIIStructuralAdapter()
        openfoam = OpenFOAMProcessAdapter()

        env_fenicsx = fenicsx.run(req)
        env_dealii = dealii.run(req)
        env_openfoam = openfoam.run(req)

        # Merge cross-adapter metrics into FEniCSx envelope.
        env_fenicsx["output"]["fenicsx_vs_dealii_strain_energy_disagreement_pct"] = (
            env_dealii["output"].get("fenicsx_vs_dealii_strain_energy_disagreement_pct")
        )
        env_fenicsx["output"]["openfoam_poiseuille_error_pct"] = (
            env_openfoam["output"].get("openfoam_poiseuille_error_pct")
        )
        env_fenicsx["output"]["cfd_mass_balance_error"] = (
            env_openfoam["output"].get("cfd_mass_balance_error")
        )
        env_fenicsx["output"]["cfd_heat_balance_error"] = (
            env_openfoam["output"].get("cfd_heat_balance_error")
        )

        result = {
            "envelope": env_fenicsx,
            "dealii_envelope": env_dealii,
            "openfoam_envelope": env_openfoam,
        }
        output_text = json.dumps(result, indent=2, default=str)
        if output_json:
            output_json.write_text(output_text)
            typer.echo(f"Envelope written to {output_json}")
        else:
            typer.echo(output_text)

    @l5_app.command("homogenise")
    def homogenise_cmd(
        trajectory_json: Path = typer.Argument(
            ..., help="Path to trajectory JSON (list of {phase, volume_fraction, time_step})."
        ),
        run_id: str = typer.Option(
            "run:l5/homogenise/001",
            help="URN run identifier.",
        ),
        output_json: Path | None = typer.Option(
            None, help="Write result JSON to this path (stdout if not set)."
        ),
    ) -> None:
        """Homogenise a microstructure trajectory from L4 to L5 effective properties."""
        if not trajectory_json.exists():
            typer.echo(f"ERROR: trajectory file not found: {trajectory_json}", err=True)
            sys.exit(1)
        trajectory = json.loads(trajectory_json.read_text())

        operator = HomogenisationOperator()
        result = operator.homogenise(trajectory)

        output_text = json.dumps(
            {"run_id": run_id, "effective_properties": result, "research_boundary": RESEARCH_BOUNDARY},
            indent=2,
            default=str,
        )
        if output_json:
            output_json.write_text(output_text)
            typer.echo(f"Result written to {output_json}")
        else:
            typer.echo(output_text)

    @l5_app.command("blocked")
    def blocked_cmd() -> None:
        """List all blocked source manifests for the L5 adapters."""
        fenicsx = FEniCSxContinuumAdapter()
        dealii = DealIIStructuralAdapter()
        openfoam = OpenFOAMProcessAdapter()
        manifests = (
            fenicsx.blocked_manifests()
            + dealii.blocked_manifests()
            + openfoam.blocked_manifests()
        )
        typer.echo(json.dumps(manifests, indent=2, default=str))

    @l5_app.command("healthz")
    def healthz_cmd() -> None:
        """Check L5 service health (local stub)."""
        import datetime as _dt
        typer.echo(
            json.dumps(
                {
                    "status": "ok",
                    "service": "l5_continuum",
                    "backend": "stub",
                    "research_boundary": RESEARCH_BOUNDARY,
                    "timestamp": _dt.datetime.now(tz=_dt.timezone.utc).isoformat(timespec="seconds"),
                },
                indent=2,
            )
        )
