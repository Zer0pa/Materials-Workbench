"""L4 phase-field / kMC / neural-operator CLI commands — typer sub-app.

Commands:
    run                  Run the L4 ensemble (PRISMS-PF + MOOSE) on a spec JSON.
    kmc                  Run the SPPARKS kMC adapter on a kmc-spec JSON.
    neural-op            Run the neural-operator surrogate (U-AFNO / DeepONet).
    blocked              List all blocked source manifests for L4 backends.
    healthz              Stub liveness check.

The module exposes ``l4_app`` for registration via the main app's
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

from zer0pa_materials_workbench.adapters.l4.base import L4PredictRequest
from zer0pa_materials_workbench.adapters.l4.contracts import (
    KmcRunSpec,
    PhaseFieldRunSpec,
)
from zer0pa_materials_workbench.adapters.l4.ensemble import L4SolverEnsemble
from zer0pa_materials_workbench.adapters.l4.microsim import MicrosimGrandPotentialAdapter
from zer0pa_materials_workbench.adapters.l4.neural_operator import NeuralOperatorPhaseFieldAdapter
from zer0pa_materials_workbench.adapters.l4.spparks import SpparksKmcAdapter
from zer0pa_materials_workbench.boundary import RESEARCH_BOUNDARY

if _TYPER_AVAILABLE:
    l4_app = typer.Typer(name="l4", help="L4 phase-field / kMC / neural-operator commands.")
else:  # pragma: no cover
    l4_app = None  # type: ignore[assignment]


def _load_spec(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Spec file not found: {path}")
    with path.open() as f:
        return json.load(f)


if _TYPER_AVAILABLE:

    @l4_app.command("run")
    def run_cmd(
        spec_json: Path = typer.Argument(
            ..., help="Path to PhaseFieldRunSpec JSON."
        ),
        run_id: str = typer.Option("run:l4/cli/001"),
        candidate_id: str = typer.Option("candidate:cli/001"),
        campaign_id: str = typer.Option("campaign:cli/001"),
        rights_claim_id: str = typer.Option("rights:cli/001"),
        output_json: Path | None = typer.Option(
            None, help="Write envelope JSON here (stdout if not set)."
        ),
    ) -> None:
        """Run the L4 ensemble (PRISMS-PF + MOOSE) on a spec JSON."""
        raw = _load_spec(spec_json)
        spec = PhaseFieldRunSpec.model_validate(raw)
        runner = L4SolverEnsemble()
        req = L4PredictRequest(
            run_id=run_id,
            candidate_id=candidate_id,
            campaign_id=campaign_id,
            rights_claim_id=rights_claim_id,
        )
        envelope = runner.run(spec, req)
        envelope_json = json.dumps(envelope, indent=2, default=str)
        if output_json:
            output_json.write_text(envelope_json)
            typer.echo(f"Envelope written to {output_json}")
        else:
            typer.echo(envelope_json)

    @l4_app.command("kmc")
    def kmc_cmd(
        spec_json: Path = typer.Argument(
            ..., help="Path to KmcRunSpec JSON."
        ),
        run_id: str = typer.Option("run:l4/kmc/cli/001"),
        candidate_id: str = typer.Option("candidate:cli/001"),
        campaign_id: str = typer.Option("campaign:cli/001"),
        rights_claim_id: str = typer.Option("rights:cli/001"),
        output_json: Path | None = typer.Option(None),
    ) -> None:
        """Run SPPARKS kMC stub on a spec JSON."""
        raw = _load_spec(spec_json)
        spec = KmcRunSpec.model_validate(raw)
        adapter = SpparksKmcAdapter()
        req = L4PredictRequest(
            run_id=run_id,
            candidate_id=candidate_id,
            campaign_id=campaign_id,
            rights_claim_id=rights_claim_id,
        )
        envelope = adapter.run(spec, req)
        envelope_json = json.dumps(envelope, indent=2, default=str)
        if output_json:
            output_json.write_text(envelope_json)
            typer.echo(f"Envelope written to {output_json}")
        else:
            typer.echo(envelope_json)

    @l4_app.command("neural-op")
    def neural_op_cmd(
        spec_json: Path = typer.Argument(
            ..., help="Path to PhaseFieldRunSpec JSON."
        ),
        architecture: str = typer.Option(
            "u_afno", help="Neural-op architecture: 'u_afno' or 'deeponet'."
        ),
        run_id: str = typer.Option("run:l4/neural-op/cli/001"),
        candidate_id: str = typer.Option("candidate:cli/001"),
        campaign_id: str = typer.Option("campaign:cli/001"),
        rights_claim_id: str = typer.Option("rights:cli/001"),
        output_json: Path | None = typer.Option(None),
    ) -> None:
        """Run the neural-operator surrogate (advisory-only until gates pass)."""
        if architecture not in ("u_afno", "deeponet"):
            raise typer.BadParameter(
                f"architecture must be 'u_afno' or 'deeponet'; got {architecture!r}"
            )
        raw = _load_spec(spec_json)
        spec = PhaseFieldRunSpec.model_validate(raw)
        adapter = NeuralOperatorPhaseFieldAdapter(architecture=architecture)  # type: ignore[arg-type]
        req = L4PredictRequest(
            run_id=run_id,
            candidate_id=candidate_id,
            campaign_id=campaign_id,
            rights_claim_id=rights_claim_id,
        )
        envelope = adapter.run(spec, req)
        envelope_json = json.dumps(envelope, indent=2, default=str)
        if output_json:
            output_json.write_text(envelope_json)
            typer.echo(f"Envelope written to {output_json}")
        else:
            typer.echo(envelope_json)

    @l4_app.command("blocked")
    def blocked_cmd() -> None:
        """List all blocked source manifests for L4 backends."""
        manifests: list[dict] = []
        manifests.extend(L4SolverEnsemble().blocked_manifests())
        manifests.extend(SpparksKmcAdapter().blocked_manifests())
        manifests.extend(NeuralOperatorPhaseFieldAdapter().blocked_manifests())
        manifests.extend(MicrosimGrandPotentialAdapter().blocked_manifests())
        # de-duplicate by source_manifest_id
        seen: set[str] = set()
        unique: list[dict] = []
        for m in manifests:
            mid = m.get("source_manifest_id")
            if mid in seen:
                continue
            seen.add(mid)
            unique.append(m)
        typer.echo(json.dumps(unique, indent=2, default=str))

    @l4_app.command("healthz")
    def healthz_cmd() -> None:
        """Check L4 service health (local stub)."""
        import datetime as _dt
        typer.echo(
            json.dumps(
                {
                    "status": "ok",
                    "service": "l4_phase_field",
                    "backend": "stub",
                    "research_boundary": RESEARCH_BOUNDARY,
                    "timestamp": _dt.datetime.now(tz=_dt.timezone.utc).isoformat(timespec="seconds"),
                },
                indent=2,
            )
        )
