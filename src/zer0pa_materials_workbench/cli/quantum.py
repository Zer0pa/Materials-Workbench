"""Quantum VQE CLI commands (``zer0pa-materials-workbench quantum ...``).

Commands
--------
run-vqe-h2    — run VQE on H2 (PennyLane or stub)
run-vqe-lih   — run VQE on LiH (PennyLane or stub)
healthz       — print quantum adapter status

Usage:
    zer0pa-materials-workbench quantum run-vqe-h2
    zer0pa-materials-workbench quantum run-vqe-lih
"""

from __future__ import annotations

import json
from pathlib import Path

import typer

app = typer.Typer(name="quantum", help="Quantum VQE adapter commands.")


@app.command("run-vqe-h2")
def run_vqe_h2(
    bond_ang: float = typer.Option(0.74, help="H-H bond length in Å"),
    campaign_id: str = typer.Option("campaign:vqe-cli-h2"),
    candidate_id: str = typer.Option("candidate:vqe-cli-h2"),
    output_json: Path | None = typer.Option(None, help="Write envelope JSON to file"),
) -> None:
    """Run VQE on H2 and print the envelope."""
    from zer0pa_materials_workbench.adapters.quantum.pennylane_vqe import PennyLaneVqeSolver

    solver = PennyLaneVqeSolver()
    envelope = solver.solve_h2(bond_ang, campaign_id, candidate_id)
    env_dict = envelope.model_dump(mode="json")
    out = json.dumps(env_dict, indent=2)
    if output_json:
        output_json.write_text(out)
        typer.echo(f"Envelope written to {output_json}")
    else:
        typer.echo(out)
    mode = "real PennyLane" if solver.pennylane_available else "stub"
    output = env_dict["output"]
    delta = abs(output["ground_state_energy_Ha"] - output["classical_reference_Ha"])
    typer.echo(f"# Backend: {mode} | delta = {delta:.6f} Ha", err=True)


@app.command("run-vqe-lih")
def run_vqe_lih(
    bond_ang: float = typer.Option(1.5949, help="Li-H bond length in Å"),
    campaign_id: str = typer.Option("campaign:vqe-cli-lih"),
    candidate_id: str = typer.Option("candidate:vqe-cli-lih"),
    output_json: Path | None = typer.Option(None, help="Write envelope JSON to file"),
) -> None:
    """Run VQE on LiH and print the envelope."""
    from zer0pa_materials_workbench.adapters.quantum.pennylane_vqe import PennyLaneVqeSolver

    solver = PennyLaneVqeSolver()
    envelope = solver.solve_lih(bond_ang, campaign_id, candidate_id)
    env_dict = envelope.model_dump(mode="json")
    out = json.dumps(env_dict, indent=2)
    if output_json:
        output_json.write_text(out)
        typer.echo(f"Envelope written to {output_json}")
    else:
        typer.echo(out)
    mode = "real PennyLane" if solver.pennylane_available else "stub"
    output = env_dict["output"]
    delta = abs(output["ground_state_energy_Ha"] - output["classical_reference_Ha"])
    typer.echo(f"# Backend: {mode} | delta = {delta:.6f} Ha", err=True)


@app.command("healthz")
def healthz() -> None:
    """Print quantum adapter status."""
    import importlib.util

    pennylane_ok = importlib.util.find_spec("pennylane") is not None
    pyscf_ok = importlib.util.find_spec("pyscf") is not None
    qiskit_ok = importlib.util.find_spec("qiskit_nature") is not None
    typer.echo(f"PennyLane available:     {pennylane_ok}")
    typer.echo(f"PySCF available:         {pyscf_ok}")
    typer.echo(f"Qiskit Nature available: {qiskit_ok}")
    typer.echo("L1-VQE slot:   active (PennyLane or stub)")
    typer.echo("L4-QAOA slot:  parked")
    typer.echo("L7-QAA slot:   parked")
    typer.echo("Quantum adapter layer: OK")
