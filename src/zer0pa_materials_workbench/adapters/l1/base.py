"""L1DftAdapter — abstract base class for all L1 DFT adapters (PRD §L1).

Every concrete solver (PySCF, QE, CP2K, ABINIT) subclasses this and implements:

    submit_job(structure, params) -> Envelope[L1DftOutput]
    parse_output(raw_text)        -> L1DftOutput
    validate_convergence(output, threshold_meV_per_atom) -> FalsifierItem

The envelope carries ``tool_adapter.backend`` set to the concrete backend
string. Dry-run / stub adapters set ``backend="stub"``; real-run adapters
set ``backend="runpod_rest"``.

``L1JobParams`` is the canonical input struct so test fixtures can be
constructed without touching the wire interface.
"""

from __future__ import annotations

import abc
import datetime
import uuid

from pydantic import BaseModel, ConfigDict, Field

from zer0pa_materials_workbench.boundary import RESEARCH_BOUNDARY
from zer0pa_materials_workbench.envelope import (
    AuditBlock,
    Envelope,
    FalsifierItem,
    FalsifierStatus,
    L1DftOutput,
    RightsBlock,
    ToolAdapter,
    canonical_json_bytes,
    sha256_of,
)

__all__ = ["L1DftAdapter", "L1JobParams"]


class L1JobParams(BaseModel):
    """Canonical input parameters for an L1 DFT job."""

    model_config = ConfigDict(extra="allow")

    structure_cif: str = Field(..., description="CIF text of the input structure.")
    structure_hash: str = Field(..., description="sha256: hash of the canonicalised structure.")
    functional: str = Field(default="PBE", description="XC functional / theory level.")
    kpoint_mesh: list[int] = Field(
        default_factory=lambda: [1, 1, 1],
        description="K-point mesh; length 3.",
    )
    basis_set: str | None = Field(default=None, description="Basis set / PP identifier.")
    cutoff_Ry: float | None = Field(default=None, description="Plane-wave cutoff in Ry.")
    max_scf_cycles: int = Field(default=200, ge=1)
    convergence_threshold: float = Field(default=1e-6, gt=0.0)
    campaign_id: str = Field(default="campaign:l1-default")
    candidate_id: str = Field(default="candidate:l1-default")
    run_id: str | None = Field(default=None, description="If None, auto-generated.")


def _make_envelope(
    output: L1DftOutput,
    params: L1JobParams,
    adapter_name: str,
    adapter_version: str,
    backend: str,
    engine: str,
) -> Envelope:
    """Helper: wrap an L1DftOutput in a fully populated Envelope."""
    run_id = params.run_id or f"run:l1:{uuid.uuid4().hex[:12]}"
    out_dict = output.model_dump(mode="json")
    in_bytes = canonical_json_bytes({"structure_hash": params.structure_hash, "functional": params.functional})
    out_bytes = canonical_json_bytes(out_dict)
    audit_id = f"audit:l1:{uuid.uuid4().hex[:12]}"
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()

    return Envelope(
        research_boundary=RESEARCH_BOUNDARY,
        run_id=run_id,
        campaign_id=params.campaign_id,
        candidate_id=params.candidate_id,
        layer="L1",
        tool_adapter=ToolAdapter(
            name=adapter_name,
            version=adapter_version,
            backend=backend,  # type: ignore[arg-type]
            engine=engine,
        ),
        output=out_dict,
        falsifier={
            "status": _rollup_status(output.falsifier_items()),
            "items": [fi.model_dump(mode="json") for fi in output.falsifier_items()],
        },
        audit=AuditBlock(
            audit_record_id=audit_id,
            input_hash=sha256_of(in_bytes),
            output_hash=sha256_of(out_bytes),
        ),
        rights=RightsBlock(
            rights_claim_id="rights:l1:default",
            reuse_scope="tenant_only",
        ),
    )


def _rollup_status(items: list[FalsifierItem]) -> FalsifierStatus:
    if any(fi.status == "fail" for fi in items):
        return "fail"
    if any(fi.status == "blocked" for fi in items):
        return "blocked"
    return "pass"


class L1DftAdapter(abc.ABC):
    """Abstract base for L1 DFT adapters.

    Subclasses MUST implement ``parse_output``. The ``submit_job`` default
    wraps ``parse_output`` with envelope construction; real adapters may
    override ``submit_job`` to fire remote jobs before calling ``parse_output``.
    """

    ADAPTER_NAME: str = "L1DftAdapter"
    ADAPTER_VERSION: str = "0.1.0"
    BACKEND: str = "stub"
    ENGINE: str = "unknown"

    # ------------------------------------------------------------------
    # Core interface
    # ------------------------------------------------------------------

    @abc.abstractmethod
    def parse_output(self, raw_text: str) -> L1DftOutput:
        """Parse raw tool output (stdout / output file) into an L1DftOutput."""

    def submit_job(self, structure_cif: str, params: L1JobParams) -> Envelope:
        """Run the job (or dry-run) and return a fully wrapped Envelope.

        The default implementation calls ``_compute_output`` (which subclasses
        override) then wraps the result. Real adapters that fire remote jobs
        should override ``submit_job`` entirely.
        """
        output = self._compute_output(structure_cif, params)
        return _make_envelope(
            output=output,
            params=params,
            adapter_name=self.ADAPTER_NAME,
            adapter_version=self.ADAPTER_VERSION,
            backend=self.BACKEND,
            engine=self.ENGINE,
        )

    def _compute_output(self, structure_cif: str, params: L1JobParams) -> L1DftOutput:
        """Override in subclass to compute the L1DftOutput before wrapping."""
        raise NotImplementedError(
            f"{type(self).__name__} must implement _compute_output or override submit_job."
        )

    def validate_convergence(
        self,
        output: L1DftOutput,
        threshold_meV_per_atom: float = 50.0,
    ) -> FalsifierItem:
        """Return a FalsifierItem for the convergence delta gate.

        Parameters
        ----------
        output:
            The L1DftOutput to check.
        threshold_meV_per_atom:
            Screening threshold (default 50 meV/atom). Pass 5.0 for
            publication grade.
        """
        delta = output.convergence_delta_meV_per_atom
        if delta is None:
            return FalsifierItem(
                name="l1.convergence_delta",
                threshold=f"<= {threshold_meV_per_atom} meV/atom",
                actual=None,
                status="blocked",
            )
        return FalsifierItem(
            name="l1.convergence_delta",
            threshold=f"<= {threshold_meV_per_atom} meV/atom",
            actual=delta,
            status="pass" if delta <= threshold_meV_per_atom else "fail",
        )
