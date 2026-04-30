"""CLI surface for the IonicTransportService.

Subcommands:

* ``zer0pa-materials ionic neb --fixture-id <ID>`` — print NEB envelope.
* ``zer0pa-materials ionic md-diffusion --fixture-id <ID>`` — MLIP-MD envelope.
* ``zer0pa-materials ionic aimd-diffusion --fixture-id <ID>`` — AIMD envelope.
* ``zer0pa-materials ionic arrhenius-fit --temperatures-K 300,400,500 --conductivities-S-per-cm 1e-3,5e-3,1e-2`` — fit Ea.
* ``zer0pa-materials ionic electrochemical-window --fixture-id <ID>``
* ``zer0pa-materials ionic interface-stability --fixture-id <ID>``
* ``zer0pa-materials ionic full-battery-evidence --fixture-id <ID>`` — bundle.
* ``zer0pa-materials ionic promote-battery-candidate --fixture-id <ID> --candidate-id <ID>`` — decision.
* ``zer0pa-materials ionic serve`` — start the FastAPI service via uvicorn.

The ionic CLI is intentionally thin — every command serialises the
adapter or service result to canonical JSON so the operator can pipe
the output into the audit log without touching the Python interface.
"""

from __future__ import annotations

import json
from typing import Annotated, Optional

import orjson
import typer
from rich.console import Console

from zer0pa_materials.adapters.ionic.aimd import AimdDiffusionAdapter
from zer0pa_materials.adapters.ionic.arrhenius import (
    ArrheniusFitAdapter,
    ArrheniusFitParams,
)
from zer0pa_materials.adapters.ionic.base import IonicJobParams
from zer0pa_materials.adapters.ionic.electrochemical_window import (
    ElectrochemicalWindowAdapter,
)
from zer0pa_materials.adapters.ionic.interface_stability import (
    InterfaceStabilityAdapter,
)
from zer0pa_materials.adapters.ionic.mlip_md import MlipMdDiffusionAdapter
from zer0pa_materials.adapters.ionic.neb import NebMigrationBarrierAdapter
from zer0pa_materials.services.ionic_transport_service import (
    IONIC_SERVICE_NAME,
    IONIC_SERVICE_VERSION,
    promote_battery_candidate,
    run_full_battery_evidence,
)

app = typer.Typer(
    name="ionic",
    help="IonicTransportService — battery MVP evidence engine.",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()


def _params_from_kwargs(
    *,
    structure_hash: str,
    fixture_id: str | None,
    candidate_id: str,
    campaign_id: str,
    temperature_K: float,
    li_carrier_concentration_per_cm3: float,
    haven_ratio: float,
    interface_mode: str,
    cathode_chemistry: str,
) -> IonicJobParams:
    return IonicJobParams(
        structure_hash=structure_hash,
        fixture_id=fixture_id,
        candidate_id=candidate_id,
        campaign_id=campaign_id,
        temperature_K=temperature_K,
        li_carrier_concentration_per_cm3=li_carrier_concentration_per_cm3,
        haven_ratio=haven_ratio,
        interface_mode=interface_mode,
        cathode_chemistry=cathode_chemistry,
    )


def _print_json(data: dict) -> None:
    typer.echo(json.dumps(data, indent=2, sort_keys=True))


_StructureHashOpt = Annotated[
    str,
    typer.Option(
        "--structure-hash",
        help="sha256:<hex> of the canonicalised structure (or 'sha256:none').",
    ),
]
_FixtureIdOpt = Annotated[
    Optional[str],
    typer.Option("--fixture-id", help="Stable fixture identifier."),
]
_CandidateIdOpt = Annotated[
    str,
    typer.Option("--candidate-id", help="URN candidate id."),
]
_CampaignIdOpt = Annotated[
    str,
    typer.Option("--campaign-id", help="URN campaign id."),
]
_TemperatureKOpt = Annotated[
    float,
    typer.Option("--temperature-K", help="Temperature in K (default 300)."),
]
_LiCarrierOpt = Annotated[
    float,
    typer.Option(
        "--li-carrier-concentration-per-cm3",
        help="Li carrier number density in /cm³.",
    ),
]
_HavenRatioOpt = Annotated[
    float,
    typer.Option("--haven-ratio", help="Haven ratio (default 1.0)."),
]
_InterfaceModeOpt = Annotated[
    str,
    typer.Option(
        "--interface-mode",
        help="li_metal | cathode_facing | coating_interlayer.",
    ),
]
_CathodeOpt = Annotated[
    str,
    typer.Option("--cathode-chemistry", help="Cathode placeholder (e.g. 'NMC811')."),
]


@app.command("neb")
def cli_neb(
    structure_hash: _StructureHashOpt = "sha256:d45cb2bfe5e76b86b365e1402e118ed32280049a62345c903558c6cfac04ef19",
    fixture_id: _FixtureIdOpt = None,
    candidate_id: _CandidateIdOpt = "candidate:ionic-default",
    campaign_id: _CampaignIdOpt = "campaign:ionic-default",
    temperature_K: _TemperatureKOpt = 300.0,
    li_carrier_concentration_per_cm3: _LiCarrierOpt = 2.0e22,
    haven_ratio: _HavenRatioOpt = 1.0,
    interface_mode: _InterfaceModeOpt = "li_metal",
    cathode_chemistry: _CathodeOpt = "NMC811",
    path_id: Annotated[
        Optional[str], typer.Option("--path-id", help="Optional NEB path id.")
    ] = None,
) -> None:
    """Run the NEB migration-barrier adapter (CPU-first stub)."""
    params = _params_from_kwargs(
        structure_hash=structure_hash,
        fixture_id=fixture_id,
        candidate_id=candidate_id,
        campaign_id=campaign_id,
        temperature_K=temperature_K,
        li_carrier_concentration_per_cm3=li_carrier_concentration_per_cm3,
        haven_ratio=haven_ratio,
        interface_mode=interface_mode,
        cathode_chemistry=cathode_chemistry,
    )
    if path_id is not None:
        params = IonicJobParams(**{**params.model_dump(), "path_id": path_id})
    env = NebMigrationBarrierAdapter().compute(params)
    _print_json(env.canonical_dict())


@app.command("md-diffusion")
def cli_md_diffusion(
    structure_hash: _StructureHashOpt = "sha256:d45cb2bfe5e76b86b365e1402e118ed32280049a62345c903558c6cfac04ef19",
    fixture_id: _FixtureIdOpt = None,
    candidate_id: _CandidateIdOpt = "candidate:ionic-default",
    campaign_id: _CampaignIdOpt = "campaign:ionic-default",
    temperature_K: _TemperatureKOpt = 300.0,
    li_carrier_concentration_per_cm3: _LiCarrierOpt = 2.0e22,
    haven_ratio: _HavenRatioOpt = 1.0,
    interface_mode: _InterfaceModeOpt = "li_metal",
    cathode_chemistry: _CathodeOpt = "NMC811",
) -> None:
    """Run the MLIP-MD diffusion adapter (CPU-first stub)."""
    params = _params_from_kwargs(
        structure_hash=structure_hash,
        fixture_id=fixture_id,
        candidate_id=candidate_id,
        campaign_id=campaign_id,
        temperature_K=temperature_K,
        li_carrier_concentration_per_cm3=li_carrier_concentration_per_cm3,
        haven_ratio=haven_ratio,
        interface_mode=interface_mode,
        cathode_chemistry=cathode_chemistry,
    )
    env = MlipMdDiffusionAdapter().compute(params)
    _print_json(env.canonical_dict())


@app.command("aimd-diffusion")
def cli_aimd_diffusion(
    structure_hash: _StructureHashOpt = "sha256:d45cb2bfe5e76b86b365e1402e118ed32280049a62345c903558c6cfac04ef19",
    fixture_id: _FixtureIdOpt = None,
    candidate_id: _CandidateIdOpt = "candidate:ionic-default",
    campaign_id: _CampaignIdOpt = "campaign:ionic-default",
    temperature_K: _TemperatureKOpt = 300.0,
    li_carrier_concentration_per_cm3: _LiCarrierOpt = 2.0e22,
    haven_ratio: _HavenRatioOpt = 1.0,
    interface_mode: _InterfaceModeOpt = "li_metal",
    cathode_chemistry: _CathodeOpt = "NMC811",
) -> None:
    """Run the AIMD diffusion adapter (CPU-first stub)."""
    params = _params_from_kwargs(
        structure_hash=structure_hash,
        fixture_id=fixture_id,
        candidate_id=candidate_id,
        campaign_id=campaign_id,
        temperature_K=temperature_K,
        li_carrier_concentration_per_cm3=li_carrier_concentration_per_cm3,
        haven_ratio=haven_ratio,
        interface_mode=interface_mode,
        cathode_chemistry=cathode_chemistry,
    )
    env = AimdDiffusionAdapter().compute(params)
    _print_json(env.canonical_dict())


@app.command("arrhenius-fit")
def cli_arrhenius_fit(
    temperatures_K: Annotated[
        str,
        typer.Option(
            "--temperatures-K",
            help="Comma-separated temperatures (K), e.g. '300,400,500'.",
        ),
    ],
    conductivities_S_per_cm: Annotated[
        str,
        typer.Option(
            "--conductivities-S-per-cm",
            help="Comma-separated conductivities (S/cm), e.g. '1e-3,5e-3,1e-2'.",
        ),
    ],
    candidate_id: _CandidateIdOpt = "candidate:ionic-default",
    campaign_id: _CampaignIdOpt = "campaign:ionic-default",
    fixture_id: _FixtureIdOpt = None,
) -> None:
    """Fit ln(σ·T) vs 1/T to extract activation energy."""
    Ts = [float(x) for x in temperatures_K.split(",")]
    Ss = [float(x) for x in conductivities_S_per_cm.split(",")]
    params = ArrheniusFitParams(
        temperatures_K=Ts,
        conductivities_S_per_cm=Ss,
        candidate_id=candidate_id,
        campaign_id=campaign_id,
        fixture_id=fixture_id,
    )
    env = ArrheniusFitAdapter().compute_from_params(params)
    _print_json(env.canonical_dict())


@app.command("electrochemical-window")
def cli_electrochemical_window(
    structure_hash: _StructureHashOpt = "sha256:d45cb2bfe5e76b86b365e1402e118ed32280049a62345c903558c6cfac04ef19",
    fixture_id: _FixtureIdOpt = None,
    candidate_id: _CandidateIdOpt = "candidate:ionic-default",
    campaign_id: _CampaignIdOpt = "campaign:ionic-default",
    cathode_chemistry: _CathodeOpt = "NMC811",
) -> None:
    """Run the electrochemical-window adapter (CPU-first stub)."""
    params = IonicJobParams(
        structure_hash=structure_hash,
        fixture_id=fixture_id,
        candidate_id=candidate_id,
        campaign_id=campaign_id,
        cathode_chemistry=cathode_chemistry,
    )
    env = ElectrochemicalWindowAdapter().compute(params)
    _print_json(env.canonical_dict())


@app.command("interface-stability")
def cli_interface_stability(
    structure_hash: _StructureHashOpt = "sha256:d45cb2bfe5e76b86b365e1402e118ed32280049a62345c903558c6cfac04ef19",
    fixture_id: _FixtureIdOpt = None,
    candidate_id: _CandidateIdOpt = "candidate:ionic-default",
    campaign_id: _CampaignIdOpt = "campaign:ionic-default",
    interface_mode: _InterfaceModeOpt = "li_metal",
    cathode_chemistry: _CathodeOpt = "NMC811",
) -> None:
    """Run the interface-stability adapter (CPU-first stub)."""
    params = IonicJobParams(
        structure_hash=structure_hash,
        fixture_id=fixture_id,
        candidate_id=candidate_id,
        campaign_id=campaign_id,
        interface_mode=interface_mode,
        cathode_chemistry=cathode_chemistry,
    )
    env = InterfaceStabilityAdapter().compute(params)
    _print_json(env.canonical_dict())


@app.command("full-battery-evidence")
def cli_full_battery_evidence(
    structure_hash: _StructureHashOpt = "sha256:d45cb2bfe5e76b86b365e1402e118ed32280049a62345c903558c6cfac04ef19",
    fixture_id: _FixtureIdOpt = None,
    candidate_id: _CandidateIdOpt = "candidate:ionic-default",
    campaign_id: _CampaignIdOpt = "campaign:ionic-default",
    temperature_K: _TemperatureKOpt = 300.0,
    li_carrier_concentration_per_cm3: _LiCarrierOpt = 2.0e22,
    haven_ratio: _HavenRatioOpt = 1.0,
    interface_mode: _InterfaceModeOpt = "li_metal",
    cathode_chemistry: _CathodeOpt = "NMC811",
) -> None:
    """Run the full battery evidence chain (six envelopes + two summary falsifiers)."""
    params = _params_from_kwargs(
        structure_hash=structure_hash,
        fixture_id=fixture_id,
        candidate_id=candidate_id,
        campaign_id=campaign_id,
        temperature_K=temperature_K,
        li_carrier_concentration_per_cm3=li_carrier_concentration_per_cm3,
        haven_ratio=haven_ratio,
        interface_mode=interface_mode,
        cathode_chemistry=cathode_chemistry,
    )
    bundle = run_full_battery_evidence(params)
    _print_json(bundle.model_dump(mode="json"))


@app.command("promote-battery-candidate")
def cli_promote(
    structure_hash: _StructureHashOpt = "sha256:d45cb2bfe5e76b86b365e1402e118ed32280049a62345c903558c6cfac04ef19",
    fixture_id: _FixtureIdOpt = None,
    candidate_id: _CandidateIdOpt = "candidate:ionic-default",
    campaign_id: _CampaignIdOpt = "campaign:ionic-default",
    temperature_K: _TemperatureKOpt = 300.0,
    li_carrier_concentration_per_cm3: _LiCarrierOpt = 2.0e22,
    haven_ratio: _HavenRatioOpt = 1.0,
    interface_mode: _InterfaceModeOpt = "li_metal",
    cathode_chemistry: _CathodeOpt = "NMC811",
) -> None:
    """Run the battery promotion gate."""
    params = _params_from_kwargs(
        structure_hash=structure_hash,
        fixture_id=fixture_id,
        candidate_id=candidate_id,
        campaign_id=campaign_id,
        temperature_K=temperature_K,
        li_carrier_concentration_per_cm3=li_carrier_concentration_per_cm3,
        haven_ratio=haven_ratio,
        interface_mode=interface_mode,
        cathode_chemistry=cathode_chemistry,
    )
    decision = promote_battery_candidate(candidate_id, params=params)
    _print_json(decision.model_dump(mode="json"))


@app.command("serve")
def cli_serve(
    host: Annotated[str, typer.Option("--host", help="Bind host.")] = "127.0.0.1",
    port: Annotated[int, typer.Option("--port", help="Bind port.")] = 8051,
) -> None:
    """Start the IonicTransportService FastAPI app via uvicorn."""
    import uvicorn

    console.print(
        f"[green]Starting {IONIC_SERVICE_NAME} v{IONIC_SERVICE_VERSION} "
        f"on {host}:{port}[/green]"
    )
    uvicorn.run(
        "zer0pa_materials.services.ionic_transport_service:ionic_app",
        host=host,
        port=port,
        log_level="info",
    )
