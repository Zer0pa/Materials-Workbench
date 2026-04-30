"""CLI surface for the L1.5 phonon and thermoelectric transport service.

Subcommands:

* ``zer0pa-materials l1-5 phonopy-harmonic --material-id Si`` — harmonic phonon spectrum.
* ``zer0pa-materials l1-5 phono3py-bte --material-id Bi2Te3 --temperature 300`` — κ_L.
* ``zer0pa-materials l1-5 hiphive-fit --material-id Bi2Te3`` — HiPhive FC fit.
* ``zer0pa-materials l1-5 boltztrap2-transport --material-id Bi2Te3`` — BoltzTraP2 S, σ, κ_e.
* ``zer0pa-materials l1-5 amset-transport --material-id Bi2Te3`` — AMSET transport.
* ``zer0pa-materials l1-5 zt-assemble --material-id Bi2Te3 --temperature 300`` — full ZT chain.
* ``zer0pa-materials l1-5 serve`` — start the FastAPI service via uvicorn.

The L1.5 CLI is intentionally thin — every command serialises the adapter or
service result to canonical JSON for piping into the audit log.
"""

from __future__ import annotations

import json
from typing import Annotated, Optional

import typer
from rich.console import Console

from zer0pa_materials.adapters.l1_5.amset import AmsetScatteringTransportAdapter
from zer0pa_materials.adapters.l1_5.base import L15JobParams
from zer0pa_materials.adapters.l1_5.boltztrap2 import BoltzTraP2RigidBandTransportAdapter
from zer0pa_materials.adapters.l1_5.hiphive_fit import HiPhiveForceConstantFitAdapter
from zer0pa_materials.adapters.l1_5.phono3py_bte import Phono3pyAnharmonicBTEAdapter
from zer0pa_materials.adapters.l1_5.phonopy_harmonic import PhonopyHarmonicAdapter
from zer0pa_materials.services.l1_5_service import (
    L15_SERVICE_NAME,
    L15_SERVICE_VERSION,
    run_zt_assembly,
)

app = typer.Typer(
    name="l1-5",
    help="L1.5 phonon and thermoelectric transport service.",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()


def _make_params(
    *,
    structure_hash: str,
    fixture_id: str | None,
    material_id: str | None,
    candidate_id: str,
    campaign_id: str,
    temperature_K: float,
    q_mesh: str,
    carrier_type: str,
) -> L15JobParams:
    parsed_q_mesh = [int(x) for x in q_mesh.split(",")]
    if len(parsed_q_mesh) != 3:
        raise typer.BadParameter(f"q-mesh must be 3 comma-separated ints, got: {q_mesh!r}")
    return L15JobParams(
        structure_hash=structure_hash,
        fixture_id=fixture_id,
        material_id=material_id,
        candidate_id=candidate_id,
        campaign_id=campaign_id,
        temperature_K=temperature_K,
        q_mesh=parsed_q_mesh,
        carrier_type=carrier_type,
    )


def _print_envelope(env_dict: dict) -> None:
    console.print_json(json.dumps(env_dict))


# Common options
_STRUCTURE_HASH = Annotated[
    str,
    typer.Option("--structure-hash", help="sha256: hash of the structure."),
]
_FIXTURE_ID = Annotated[
    Optional[str],
    typer.Option("--fixture-id", help="Fixture identifier, e.g. 'fixture:Bi2Te3:ae87f3b2'."),
]
_MATERIAL_ID = Annotated[
    Optional[str],
    typer.Option("--material-id", help="Material label: Si, Bi2Te3, PbTe, SnSe, NaCl."),
]
_CANDIDATE_ID = Annotated[
    str,
    typer.Option("--candidate-id", help="Candidate identifier."),
]
_CAMPAIGN_ID = Annotated[
    str,
    typer.Option("--campaign-id", help="Campaign identifier."),
]
_TEMPERATURE = Annotated[
    float,
    typer.Option("--temperature", help="Temperature in K (default 300)."),
]
_Q_MESH = Annotated[
    str,
    typer.Option("--q-mesh", help="q-point mesh as 'n1,n2,n3' (default '6,6,6')."),
]
_CARRIER_TYPE = Annotated[
    str,
    typer.Option("--carrier-type", help="Carrier type: 'p' or 'n' (default 'p')."),
]


@app.command("phonopy-harmonic")
def cmd_phonopy_harmonic(
    structure_hash: _STRUCTURE_HASH = "sha256:none",
    fixture_id: _FIXTURE_ID = None,
    material_id: _MATERIAL_ID = None,
    candidate_id: _CANDIDATE_ID = "candidate:l1-5-cli",
    campaign_id: _CAMPAIGN_ID = "campaign:l1-5-cli",
    temperature: _TEMPERATURE = 300.0,
    q_mesh: _Q_MESH = "6,6,6",
    carrier_type: _CARRIER_TYPE = "p",
) -> None:
    """Compute the harmonic phonon spectrum (Phonopy or synthetic stub)."""
    params = _make_params(
        structure_hash=structure_hash,
        fixture_id=fixture_id,
        material_id=material_id,
        candidate_id=candidate_id,
        campaign_id=campaign_id,
        temperature_K=temperature,
        q_mesh=q_mesh,
        carrier_type=carrier_type,
    )
    env = PhonopyHarmonicAdapter().compute(params)
    _print_envelope(env.model_dump(mode="json"))


@app.command("phono3py-bte")
def cmd_phono3py_bte(
    structure_hash: _STRUCTURE_HASH = "sha256:none",
    fixture_id: _FIXTURE_ID = None,
    material_id: _MATERIAL_ID = None,
    candidate_id: _CANDIDATE_ID = "candidate:l1-5-cli",
    campaign_id: _CAMPAIGN_ID = "campaign:l1-5-cli",
    temperature: _TEMPERATURE = 300.0,
    q_mesh: _Q_MESH = "6,6,6",
    carrier_type: _CARRIER_TYPE = "p",
) -> None:
    """Compute lattice thermal conductivity via Phono3py BTE."""
    params = _make_params(
        structure_hash=structure_hash,
        fixture_id=fixture_id,
        material_id=material_id,
        candidate_id=candidate_id,
        campaign_id=campaign_id,
        temperature_K=temperature,
        q_mesh=q_mesh,
        carrier_type=carrier_type,
    )
    env = Phono3pyAnharmonicBTEAdapter().compute(params)
    _print_envelope(env.model_dump(mode="json"))


@app.command("hiphive-fit")
def cmd_hiphive_fit(
    structure_hash: _STRUCTURE_HASH = "sha256:none",
    fixture_id: _FIXTURE_ID = None,
    material_id: _MATERIAL_ID = None,
    candidate_id: _CANDIDATE_ID = "candidate:l1-5-cli",
    campaign_id: _CAMPAIGN_ID = "campaign:l1-5-cli",
    temperature: _TEMPERATURE = 300.0,
    q_mesh: _Q_MESH = "6,6,6",
    carrier_type: _CARRIER_TYPE = "p",
) -> None:
    """Fit force constants from MLIP-MD displacement-force data (HiPhive)."""
    params = _make_params(
        structure_hash=structure_hash,
        fixture_id=fixture_id,
        material_id=material_id,
        candidate_id=candidate_id,
        campaign_id=campaign_id,
        temperature_K=temperature,
        q_mesh=q_mesh,
        carrier_type=carrier_type,
    )
    env = HiPhiveForceConstantFitAdapter().compute(params)
    _print_envelope(env.model_dump(mode="json"))


@app.command("boltztrap2-transport")
def cmd_boltztrap2(
    structure_hash: _STRUCTURE_HASH = "sha256:none",
    fixture_id: _FIXTURE_ID = None,
    material_id: _MATERIAL_ID = None,
    candidate_id: _CANDIDATE_ID = "candidate:l1-5-cli",
    campaign_id: _CAMPAIGN_ID = "campaign:l1-5-cli",
    temperature: _TEMPERATURE = 300.0,
    q_mesh: _Q_MESH = "6,6,6",
    carrier_type: _CARRIER_TYPE = "p",
) -> None:
    """Compute electronic transport via BoltzTraP2 rigid-band approximation."""
    params = _make_params(
        structure_hash=structure_hash,
        fixture_id=fixture_id,
        material_id=material_id,
        candidate_id=candidate_id,
        campaign_id=campaign_id,
        temperature_K=temperature,
        q_mesh=q_mesh,
        carrier_type=carrier_type,
    )
    env = BoltzTraP2RigidBandTransportAdapter().compute(params)
    _print_envelope(env.model_dump(mode="json"))


@app.command("amset-transport")
def cmd_amset(
    structure_hash: _STRUCTURE_HASH = "sha256:none",
    fixture_id: _FIXTURE_ID = None,
    material_id: _MATERIAL_ID = None,
    candidate_id: _CANDIDATE_ID = "candidate:l1-5-cli",
    campaign_id: _CAMPAIGN_ID = "campaign:l1-5-cli",
    temperature: _TEMPERATURE = 300.0,
    q_mesh: _Q_MESH = "6,6,6",
    carrier_type: _CARRIER_TYPE = "p",
) -> None:
    """Compute electronic transport via AMSET scattering mechanisms."""
    params = _make_params(
        structure_hash=structure_hash,
        fixture_id=fixture_id,
        material_id=material_id,
        candidate_id=candidate_id,
        campaign_id=campaign_id,
        temperature_K=temperature,
        q_mesh=q_mesh,
        carrier_type=carrier_type,
    )
    env = AmsetScatteringTransportAdapter().compute(params)
    _print_envelope(env.model_dump(mode="json"))


@app.command("zt-assemble")
def cmd_zt_assemble(
    structure_hash: _STRUCTURE_HASH = "sha256:none",
    fixture_id: _FIXTURE_ID = None,
    material_id: _MATERIAL_ID = None,
    candidate_id: _CANDIDATE_ID = "candidate:l1-5-cli",
    campaign_id: _CAMPAIGN_ID = "campaign:l1-5-cli",
    temperature: _TEMPERATURE = 300.0,
    q_mesh: _Q_MESH = "6,6,6",
    carrier_type: _CARRIER_TYPE = "p",
) -> None:
    """Assemble the full thermoelectric ZT chain (Phono3py + BoltzTraP2 + AMSET)."""
    params = _make_params(
        structure_hash=structure_hash,
        fixture_id=fixture_id,
        material_id=material_id,
        candidate_id=candidate_id,
        campaign_id=campaign_id,
        temperature_K=temperature,
        q_mesh=q_mesh,
        carrier_type=carrier_type,
    )
    env = run_zt_assembly(params)
    _print_envelope(env.model_dump(mode="json"))


@app.command("serve")
def cmd_serve(
    host: str = typer.Option("127.0.0.1", help="Host to bind to."),
    port: int = typer.Option(8004, help="Port to bind to."),
    reload: bool = typer.Option(False, help="Enable auto-reload (dev only)."),
) -> None:
    """Start the L1.5 phonon service via uvicorn."""
    try:
        import uvicorn
    except ImportError:
        console.print("[red]uvicorn is not installed. Run: pip install uvicorn[/red]")
        raise typer.Exit(1)

    console.print(
        f"[green]Starting {L15_SERVICE_NAME} v{L15_SERVICE_VERSION} "
        f"on http://{host}:{port}[/green]"
    )
    uvicorn.run(
        "zer0pa_materials.services.l1_5_service:l15_app",
        host=host,
        port=port,
        reload=reload,
    )
