"""L1 DFT CLI commands (``zer0pa-materials-workbench l1 ...``).

Commands
--------
run-pyscf    — run PySCF on a fixture CIF (H2 or LiH)
dry-run-qe   — emit a QE input file without running QE
dry-run-cp2k — emit a CP2K input file without running CP2K
dry-run-abinit — emit an ABINIT input file without running ABINIT
healthz      — print L1 adapter status

Usage (after ``pip install -e .``):
    zer0pa-materials-workbench l1 run-pyscf --cif fixtures/structures/H2/structure.cif
    zer0pa-materials-workbench l1 dry-run-qe --cif fixtures/structures/Si/structure.cif
"""

from __future__ import annotations

import json
from pathlib import Path

import typer

from zer0pa_materials_workbench.adapters.l1.base import L1JobParams
from zer0pa_materials_workbench.adapters.l1.pyscf import PyScfMolecularSolver
from zer0pa_materials_workbench.envelope import cif_hash_from_text

app = typer.Typer(name="l1", help="L1 DFT adapter commands.")


@app.command("run-pyscf")
def run_pyscf(
    cif: Path = typer.Option(..., help="Path to structure.cif"),
    functional: str = typer.Option("PBE", help="XC functional"),
    campaign_id: str = typer.Option("campaign:l1-cli"),
    candidate_id: str = typer.Option("candidate:l1-cli"),
    output_json: Path | None = typer.Option(None, help="Write envelope JSON to file"),
) -> None:
    """Run PySCF (real or stub) on a CIF and print the envelope."""
    cif_text = cif.read_text()
    cif_hash = cif_hash_from_text(cif_text)
    solver = PyScfMolecularSolver()
    params = L1JobParams(
        structure_cif=cif_text,
        structure_hash=cif_hash,
        functional=functional,
        campaign_id=campaign_id,
        candidate_id=candidate_id,
    )
    envelope = solver.submit_job(cif_text, params)
    env_dict = envelope.model_dump(mode="json")
    out = json.dumps(env_dict, indent=2)
    if output_json:
        output_json.write_text(out)
        typer.echo(f"Envelope written to {output_json}")
    else:
        typer.echo(out)
    mode = "real PySCF" if solver.pyscf_available else "stub"
    typer.echo(f"# Backend: {mode}", err=True)


@app.command("dry-run-qe")
def dry_run_qe(
    cif: Path = typer.Option(..., help="Path to structure.cif"),
    output_file: Path | None = typer.Option(None, help="Write QE input to file"),
) -> None:
    """Emit a Quantum ESPRESSO input file (dry-run only — no QE execution)."""
    from zer0pa_materials_workbench.adapters.l1.qe_aiida import QuantumEspressoAiiDASolver

    cif_text = cif.read_text()
    cif_hash = cif_hash_from_text(cif_text)
    solver = QuantumEspressoAiiDASolver()
    params = L1JobParams(structure_cif=cif_text, structure_hash=cif_hash)
    solver._compute_output(cif_text, params)
    qe_input = getattr(solver, "_last_qe_input", "")
    if output_file:
        output_file.write_text(qe_input)
        typer.echo(f"QE input written to {output_file}")
    else:
        typer.echo(qe_input)


@app.command("dry-run-cp2k")
def dry_run_cp2k(
    cif: Path = typer.Option(..., help="Path to structure.cif"),
    output_file: Path | None = typer.Option(None, help="Write CP2K input to file"),
) -> None:
    """Emit a CP2K input file (dry-run only)."""
    from zer0pa_materials_workbench.adapters.l1.cp2k_aiida import Cp2kAiiDASolver

    cif_text = cif.read_text()
    cif_hash = cif_hash_from_text(cif_text)
    solver = Cp2kAiiDASolver()
    params = L1JobParams(structure_cif=cif_text, structure_hash=cif_hash)
    solver._compute_output(cif_text, params)
    cp2k_input = getattr(solver, "_last_cp2k_input", "")
    if output_file:
        output_file.write_text(cp2k_input)
        typer.echo(f"CP2K input written to {output_file}")
    else:
        typer.echo(cp2k_input)


@app.command("dry-run-abinit")
def dry_run_abinit(
    cif: Path = typer.Option(..., help="Path to structure.cif"),
    output_file: Path | None = typer.Option(None, help="Write ABINIT input to file"),
) -> None:
    """Emit an ABINIT input file (dry-run only)."""
    from zer0pa_materials_workbench.adapters.l1.abinit_aiida import AbinitAiiDASolver

    cif_text = cif.read_text()
    cif_hash = cif_hash_from_text(cif_text)
    solver = AbinitAiiDASolver()
    params = L1JobParams(structure_cif=cif_text, structure_hash=cif_hash)
    solver._compute_output(cif_text, params)
    abinit_input = getattr(solver, "_last_abinit_input", "")
    if output_file:
        output_file.write_text(abinit_input)
        typer.echo(f"ABINIT input written to {output_file}")
    else:
        typer.echo(abinit_input)


@app.command("healthz")
def healthz() -> None:
    """Print L1 adapter status and available backends."""
    import importlib.util

    pyscf_ok = importlib.util.find_spec("pyscf") is not None
    typer.echo(f"PySCF available:  {pyscf_ok}")
    typer.echo("QE:               dry-run/parse-only (real: parked)")
    typer.echo("CP2K:             dry-run/parse-only (real: parked)")
    typer.echo("ABINIT:           dry-run/parse-only (real: parked)")
    typer.echo("L1 adapter layer: OK")
