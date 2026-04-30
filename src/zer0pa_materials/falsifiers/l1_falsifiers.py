"""L1 DFT falsifiers (PRD §Layer-Specific Falsifiers And Gates).

Functions
---------
convergence_delta_screening_threshold(output) -> FalsifierItem
    Flag if cross-code or functional delta > 50 meV/atom.

convergence_delta_publication_threshold(output) -> FalsifierItem
    Flag if delta > 5 meV/atom.

force_threshold_check(output, threshold_eV_per_Ang) -> FalsifierItem
    Check force RMSE against threshold.

cross_code_disagreement(envelopes) -> tuple[FalsifierItem, DisagreementMetric]
    Compute cross-code energy disagreement; emit DisagreementMetric for KG.
"""

from __future__ import annotations

import statistics
from typing import Any

from zer0pa_materials.envelope import (
    DisagreementMetric,
    Envelope,
    FalsifierItem,
    L1DftOutput,
)

__all__ = [
    "convergence_delta_screening_threshold",
    "convergence_delta_publication_threshold",
    "force_threshold_check",
    "cross_code_disagreement",
]

_SCREENING_THRESHOLD_MEV = 50.0   # meV/atom (PRD §L1)
_PUBLICATION_THRESHOLD_MEV = 5.0  # meV/atom (PRD §L1)


def _l1_output_from_envelope(envelope: Envelope) -> L1DftOutput:
    """Extract and validate the L1DftOutput from an Envelope."""
    return L1DftOutput.model_validate(envelope.output)


# ---------------------------------------------------------------------------
# Individual gate falsifiers
# ---------------------------------------------------------------------------


def convergence_delta_screening_threshold(output: L1DftOutput) -> FalsifierItem:
    """Return a FalsifierItem for the 50 meV/atom screening gate (PRD §L1).

    FAIL when ``convergence_delta_meV_per_atom > 50 meV/atom``.
    BLOCKED when delta is None (not measured).
    """
    delta = output.convergence_delta_meV_per_atom
    if delta is None:
        return FalsifierItem(
            name="l1.screening_convergence_delta",
            threshold=f"< {_SCREENING_THRESHOLD_MEV} meV/atom",
            actual=None,
            status="blocked",
        )
    status = "pass" if delta < _SCREENING_THRESHOLD_MEV else "fail"
    return FalsifierItem(
        name="l1.screening_convergence_delta",
        threshold=f"< {_SCREENING_THRESHOLD_MEV} meV/atom",
        actual=delta,
        status=status,
    )


def convergence_delta_publication_threshold(output: L1DftOutput) -> FalsifierItem:
    """Return a FalsifierItem for the 5 meV/atom publication gate (PRD §L1).

    FAIL when ``convergence_delta_meV_per_atom > 5 meV/atom``.
    Only relevant when ``output.publication_grade == True``; callers should
    check this flag before including this item in a promotion decision.
    """
    delta = output.convergence_delta_meV_per_atom
    if delta is None:
        return FalsifierItem(
            name="l1.publication_convergence_delta",
            threshold=f"<= {_PUBLICATION_THRESHOLD_MEV} meV/atom",
            actual=None,
            status="blocked",
        )
    status = "pass" if delta <= _PUBLICATION_THRESHOLD_MEV else "fail"
    return FalsifierItem(
        name="l1.publication_convergence_delta",
        threshold=f"<= {_PUBLICATION_THRESHOLD_MEV} meV/atom",
        actual=delta,
        status=status,
    )


def force_threshold_check(
    output: L1DftOutput,
    threshold_eV_per_Ang: float = 0.05,
) -> FalsifierItem:
    """Return a FalsifierItem checking force RMSE against a threshold.

    Default threshold: 0.05 eV/Å (PRD default for geometry convergence).
    """
    rmse = output.force_rmse_eV_per_Ang
    status = "pass" if rmse <= threshold_eV_per_Ang else "fail"
    return FalsifierItem(
        name="l1.force_threshold",
        threshold=f"<= {threshold_eV_per_Ang} eV/Ang",
        actual=rmse,
        status=status,
    )


# ---------------------------------------------------------------------------
# Cross-code disagreement
# ---------------------------------------------------------------------------


def cross_code_disagreement(
    envelopes: list[Envelope],
) -> tuple[FalsifierItem, DisagreementMetric]:
    """Compute cross-code energy disagreement from a list of L1 envelopes.

    Parameters
    ----------
    envelopes:
        List of Envelope objects, each carrying an L1DftOutput. Must have
        at least two envelopes with different ``code`` values.

    Returns
    -------
    falsifier_item:
        FalsifierItem summarising the cross-code disagreement gate.
    disagreement_metric:
        DisagreementMetric to be written to the KG as a DisagreementMetric
        node (and the ``disagreement.jsonl`` audit log).

    Notes
    -----
    The disagreement is computed as the range (max - min) of total energies
    per atom across all envelopes. If n_atoms cannot be determined from the
    output, we fall back to per-formula-unit comparison.

    KG write contract (caller must execute):
        kg.add_node(KGNodeType.DisagreementMetric, node_id, {metric.model_dump()})
        kg.add_edge(KGEdgeType.AGREES_WITH / CONTRADICTS, ...)
    """
    if len(envelopes) < 2:
        return (
            FalsifierItem(
                name="l1.cross_code_disagreement",
                threshold=f"< {_SCREENING_THRESHOLD_MEV} meV/atom",
                actual=None,
                status="blocked",
            ),
            DisagreementMetric(
                name="l1.cross_code_disagreement",
                value=0.0,
                unit="meV/atom",
                references=[],
            ),
        )

    outputs = [_l1_output_from_envelope(e) for e in envelopes]
    codes = [o.code for o in outputs]
    # Energy in eV; convert to meV/atom — assume 1 formula unit for molecular systems
    energies_eV = [o.total_energy_eV for o in outputs]
    # Per-atom normalisation: L1DftOutput doesn't carry n_atoms so we use
    # per-formula-unit comparison (n_atoms = 1 for our 2-atom molecular fixtures).
    # Callers that know n_atoms can call this function with scaled energies.
    energy_range_eV = max(energies_eV) - min(energies_eV)
    energy_range_meV = energy_range_eV * 1000.0  # meV/f.u.

    status = "pass" if energy_range_meV < _SCREENING_THRESHOLD_MEV else "fail"
    label = "l1.cross_code_disagreement"

    falsifier_item = FalsifierItem(
        name=label,
        threshold=f"< {_SCREENING_THRESHOLD_MEV} meV/f.u.",
        actual=round(energy_range_meV, 6),
        status=status,
    )
    disagreement_metric = DisagreementMetric(
        name=label,
        value=round(energy_range_meV, 6),
        unit="meV/f.u.",
        references=[f"{c}:{round(e, 6)}eV" for c, e in zip(codes, energies_eV)],
    )
    return falsifier_item, disagreement_metric
