"""MVP Evidence Packet CLI subcommands (Wave 5a).

Registered as ``zer0pa-materials packets <subcommand>``.

Subcommands:
    packets healthz
    packets list-fixtures
    packets assemble battery <fixture-key> [--interface-mode ...]
    packets assemble thermoelectric <fixture-key>
    packets validate <packet-path>
    packets export-ro-crate <packet-path> <out-dir>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from zer0pa_materials_workbench.packets.battery_packet import (
    BATTERY_FIXTURE_SPECS,
    assemble_battery_packet,
)
from zer0pa_materials_workbench.packets.evidence_packet import EvidencePacket
from zer0pa_materials_workbench.packets.ro_crate_export import (
    export_packet_to_ro_crate,
)
from zer0pa_materials_workbench.packets.thermoelectric_packet import (
    THERMOELECTRIC_FIXTURE_SPECS,
    assemble_thermoelectric_packet,
)
from zer0pa_materials_workbench.packets.validators import validate_evidence_packet

packets_app = typer.Typer(
    name="packets",
    help="MVP Evidence Packet generator (PRD §Final Output Required #9 + #10).",
    no_args_is_help=True,
)
console = Console()


# ----------------------------------------------------------------------------
# packets healthz / list-fixtures
# ----------------------------------------------------------------------------


@packets_app.command("healthz")
def healthz() -> None:
    """Print service identity / version."""
    typer.echo(
        json.dumps(
            {
                "status": "ok",
                "service": "MvpEvidencePacketService",
                "version": "0.1.0",
                "battery_fixtures": sorted(BATTERY_FIXTURE_SPECS.keys()),
                "thermoelectric_fixtures": sorted(THERMOELECTRIC_FIXTURE_SPECS.keys()),
            },
            indent=2,
            sort_keys=True,
        )
    )


@packets_app.command("list-fixtures")
def list_fixtures(
    objective: Annotated[
        str,
        typer.Option(help="battery | thermoelectric | both"),
    ] = "both",
) -> None:
    """List available fixture identifiers."""
    out: dict[str, list[str]] = {}
    if objective in ("battery", "both"):
        out["battery"] = sorted(BATTERY_FIXTURE_SPECS.keys())
    if objective in ("thermoelectric", "both"):
        out["thermoelectric"] = sorted(THERMOELECTRIC_FIXTURE_SPECS.keys())
    typer.echo(json.dumps(out, indent=2, sort_keys=True))


# ----------------------------------------------------------------------------
# packets assemble battery / thermoelectric
# ----------------------------------------------------------------------------


assemble_app = typer.Typer(
    name="assemble",
    help="Assemble an evidence packet for a fixture.",
    no_args_is_help=True,
)
packets_app.add_typer(assemble_app, name="assemble")


@assemble_app.command("battery")
def assemble_battery(
    fixture_key: Annotated[str, typer.Argument(help="LLZO|Li6PS5Cl|Li-Mg-Zr-Cl-seed")],
    interface_mode: Annotated[
        str, typer.Option(help="li_metal|cathode_facing|coating_interlayer")
    ] = "li_metal",
    candidate_id: Annotated[str | None, typer.Option(help="Override candidate URN")] = None,
    campaign_id: Annotated[str | None, typer.Option(help="Override campaign URN")] = None,
    out_path: Annotated[
        str | None, typer.Option(help="If set, write packet JSON to this file.")
    ] = None,
) -> None:
    """Assemble a battery primary packet."""
    if fixture_key not in BATTERY_FIXTURE_SPECS:
        raise typer.BadParameter(
            f"unknown fixture {fixture_key!r}; valid: {sorted(BATTERY_FIXTURE_SPECS)}"
        )
    packet = assemble_battery_packet(
        fixture_key,
        interface_mode=interface_mode,
        candidate_id=candidate_id,
        campaign_id=campaign_id,
    )
    payload = packet.model_dump(mode="json")
    if out_path:
        Path(out_path).write_text(
            json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
        )
        console.print(f"[green]wrote packet[/green] {out_path}")
    else:
        typer.echo(json.dumps(payload, indent=2, sort_keys=True))
    console.print(
        f"packet_id={packet.packet_id} decision={packet.promotion_decision}"
    )


@assemble_app.command("thermoelectric")
def assemble_thermoelectric(
    fixture_key: Annotated[str, typer.Argument(help="Si|Bi2Te3|PbTe|SnSe")],
    candidate_id: Annotated[str | None, typer.Option(help="Override candidate URN")] = None,
    campaign_id: Annotated[str | None, typer.Option(help="Override campaign URN")] = None,
    out_path: Annotated[
        str | None, typer.Option(help="If set, write packet JSON to this file.")
    ] = None,
) -> None:
    """Assemble a thermoelectric sidecar packet."""
    if fixture_key not in THERMOELECTRIC_FIXTURE_SPECS:
        raise typer.BadParameter(
            f"unknown fixture {fixture_key!r}; valid: {sorted(THERMOELECTRIC_FIXTURE_SPECS)}"
        )
    packet = assemble_thermoelectric_packet(
        fixture_key,
        candidate_id=candidate_id,
        campaign_id=campaign_id,
    )
    payload = packet.model_dump(mode="json")
    if out_path:
        Path(out_path).write_text(
            json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
        )
        console.print(f"[green]wrote packet[/green] {out_path}")
    else:
        typer.echo(json.dumps(payload, indent=2, sort_keys=True))
    console.print(
        f"packet_id={packet.packet_id} decision={packet.promotion_decision}"
    )


# ----------------------------------------------------------------------------
# packets validate
# ----------------------------------------------------------------------------


@packets_app.command("validate")
def validate(
    packet_path: Annotated[
        str, typer.Argument(help="Path to a packet JSON file.")
    ],
) -> None:
    """Run the packet validators on the file at ``packet_path``."""
    path = Path(packet_path)
    if not path.exists():
        raise typer.BadParameter(f"file not found: {packet_path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    try:
        packet = EvidencePacket.model_validate(payload)
    except Exception as exc:
        console.print(f"[red]invalid packet:[/red] {exc}")
        sys.exit(2)
    report = validate_evidence_packet(packet)
    typer.echo(json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True))
    if report.overall_status != "pass":
        sys.exit(1)


# ----------------------------------------------------------------------------
# packets export-ro-crate
# ----------------------------------------------------------------------------


@packets_app.command("export-ro-crate")
def export_ro_crate(
    packet_path: Annotated[
        str, typer.Argument(help="Path to a packet JSON file.")
    ],
    out_dir: Annotated[
        str, typer.Argument(help="Output directory for the RO-Crate.")
    ],
) -> None:
    """Write the packet's RO-Crate to ``out_dir``."""
    path = Path(packet_path)
    if not path.exists():
        raise typer.BadParameter(f"file not found: {packet_path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    packet = EvidencePacket.model_validate(payload)
    bundle = export_packet_to_ro_crate(packet, out_dir)
    typer.echo(
        json.dumps(
            {
                "crate_root": str(bundle.crate_root),
                "metadata_path": str(bundle.metadata_path),
                "packet_path": str(bundle.packet_path),
                "section_count": len(bundle.section_paths),
                "entry_count": len(bundle.entries),
            },
            indent=2,
            sort_keys=True,
        )
    )
