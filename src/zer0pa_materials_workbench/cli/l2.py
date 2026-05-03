"""L2 MLIP CLI commands — typer sub-application.

Commands:
    predict     Run DPA-3 + MACE ensemble on a structure CIF or JSON
    blocked     List all blocked manifests for the L2 ensemble
    healthz     Check L2 service health (local stub only)
    uma-enable  Show instructions for enabling the UMA adapter

Do NOT modify cli/main.py to add these — register via the main app's
``add_typer`` call. This module exposes ``l2_app`` for that purpose.
"""

from __future__ import annotations

import json
from pathlib import Path

try:
    import typer
    _TYPER_AVAILABLE = True
except ImportError:  # pragma: no cover
    _TYPER_AVAILABLE = False

from zer0pa_materials_workbench.adapters.l2.base import L2PredictRequest
from zer0pa_materials_workbench.adapters.l2.ensemble import L2EnsembleRunner
from zer0pa_materials_workbench.boundary import RESEARCH_BOUNDARY

if _TYPER_AVAILABLE:
    l2_app = typer.Typer(name="l2", help="L2 MLIP ensemble commands.")
else:  # pragma: no cover
    l2_app = None  # type: ignore[assignment]


def _load_structure(path: Path) -> dict:
    """Load a structure from a JSON file (lattice/species/frac_coords keys)."""
    if not path.exists():
        raise FileNotFoundError(f"Structure file not found: {path}")
    with path.open() as f:
        return json.load(f)


if _TYPER_AVAILABLE:

    @l2_app.command("predict")
    def predict_cmd(
        structure_json: Path = typer.Argument(
            ..., help="Path to structure JSON (lattice, species, frac_coords)."
        ),
        run_id: str = typer.Option(
            "run:l2/cli/001",
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
        """Run DPA-3 + MACE ensemble on a structure and print/write the envelope."""
        structure = _load_structure(structure_json)
        runner = L2EnsembleRunner()
        req = L2PredictRequest(
            run_id=run_id,
            candidate_id=candidate_id,
            campaign_id=campaign_id,
            rights_claim_id=rights_claim_id,
        )
        envelope = runner.run(structure, req)
        envelope_json = json.dumps(envelope, indent=2, default=str)
        if output_json:
            output_json.write_text(envelope_json)
            typer.echo(f"Envelope written to {output_json}")
        else:
            typer.echo(envelope_json)

    @l2_app.command("blocked")
    def blocked_cmd() -> None:
        """List all blocked source manifests for the L2 ensemble."""
        runner = L2EnsembleRunner()
        manifests = runner.blocked_manifests()
        typer.echo(json.dumps(manifests, indent=2, default=str))

    @l2_app.command("healthz")
    def healthz_cmd() -> None:
        """Check L2 service health (local stub)."""
        import datetime as _dt
        typer.echo(
            json.dumps(
                {
                    "status": "ok",
                    "service": "l2_mlip",
                    "backend": "stub",
                    "research_boundary": RESEARCH_BOUNDARY,
                    "timestamp": _dt.datetime.now(tz=_dt.timezone.utc).isoformat(timespec="seconds"),
                },
                indent=2,
            )
        )

    @l2_app.command("uma-enable")
    def uma_enable_cmd() -> None:
        """Show instructions for enabling the UMA adapter."""
        typer.echo(
            "\n".join([
                "UMA adapter is BLOCKED by default.",
                "",
                "To enable:",
                "  1. Register Zer0pa HuggingFace org with accurate organisational info.",
                "  2. Accept FAIR Chemistry License v1 on the UMA model page.",
                "  3. Generate a HuggingFace access token (read scope).",
                "  4. Call in Python:",
                "       from zer0pa_materials_workbench.adapters.l2.uma import UmaCalculatorAdapter",
                "       adapter = UmaCalculatorAdapter()",
                "       adapter.enable_uma(hf_org='<org>', hf_token='hf_...', aup_accepted_at='<iso-utc>')",
                "",
                "License: fairchem library = MIT; UMA weights = FAIR Chemistry License v1.",
                "Geographic: Available globally EXCEPT China, Russia, Belarus, OFAC-sanctioned.",
                "South Africa: UNRESTRICTED.",
                "AUP: Military/warfare/ITAR/weapons EXCLUDED. Energy/battery: NOT restricted.",
                "Output ownership: you own derivative works per FAIR Chemistry License v1.",
            ])
        )
