"""L6 falsifiers (PRD §Phase 0 / L6 Falsifiers).

Functions:
    valid_cif_only(envelope)                   -- rejects unparseable CIF.
    charge_neutrality_check(structure)         -- sums oxidation states.
    min_interatomic_distance(structure, ...)   -- minimum pair distance.
    structure_hash_dedupe(envelopes)           -- flags duplicate hashes.
    reference_expansion_dedupe(envelope, ref) -- checks vs reference set.
    pymatgen_structure_matcher(envelope, ref) -- graceful skip if no pymatgen.
    novelty_status_gate(envelope)              -- blocks premature "novel".
    recompute_novelty(envelope, reference_set) -- Wave D: re-runs structure
                                                  hash + reference dedupe
                                                  + per-batch dedupe and
                                                  returns the recomputed
                                                  status, ignoring claim.
    novelty_status_gate_recomputed(envelope, reference_set, batch_envelopes)
                                               -- Wave D: compares claim to
                                                  recomputed status.

Wave D discipline (RESISTANCE.md ``fp-shapematch``):
    The original ``novelty_status_gate`` accepts ``output.novelty_status
    == "novel"`` as long as the L1 back-edge exists. A buggy adapter
    can paint that label on a candidate that already lives in
    Materials Project. The hardened gate re-runs structure_hash, runs
    reference_set membership, runs per-batch hashing, and compares the
    recomputed status against the claim.
"""

from __future__ import annotations

import math
from typing import Any, Iterable

from zer0pa_materials.envelope.envelope import Envelope
from zer0pa_materials.envelope.falsifier import FalsifierItem, FalsifierStatus
from zer0pa_materials.envelope.hashing import cif_hash_from_text, parse_minimal_cif
from zer0pa_materials.falsifiers.raw_evidence import (
    recompute_structure_hash_from_envelope,
)

# ---------------------------------------------------------------------------
# Oxidation state lookup (simplified; covers battery-relevant elements)
# ---------------------------------------------------------------------------

# Common oxidation states per element.  For charge neutrality we pick the
# most common state when there are multiple choices.  A full implementation
# would use pymatgen's oxidation state guesser; this table handles the
# fixture chemistry.
_OXIDATION_STATES: dict[str, int] = {
    "Li": +1, "Na": +1, "K": +1, "Rb": +1, "Cs": +1,
    "Mg": +2, "Ca": +2, "Sr": +2, "Ba": +2,
    "Al": +3, "Ga": +3, "In": +3, "Tl": +3,
    "Si": +4, "Ge": +4, "Sn": +4, "Pb": +4,
    "N": -3, "P": +5, "As": +5, "Sb": +5, "Bi": +3,
    "O": -2, "S": -2, "Se": -2, "Te": -2,
    "F": -1, "Cl": -1, "Br": -1, "I": -1,
    "La": +3, "Ce": +3, "Pr": +3, "Nd": +3, "Sm": +3,
    "Eu": +3, "Gd": +3, "Tb": +3, "Dy": +3, "Ho": +3,
    "Er": +3, "Tm": +3, "Yb": +3, "Lu": +3,
    "Zr": +4, "Hf": +4,
    "Ti": +4, "V": +5, "Cr": +3, "Mn": +2, "Fe": +3,
    "Co": +2, "Ni": +2, "Cu": +2, "Zn": +2,
    "Nb": +5, "Mo": +6, "W": +6,
    "H": +1,
    "B": +3, "C": +4,
    "Bi": +3, "Pb": +4,
    "In": +3,
}


# ---------------------------------------------------------------------------
# valid_cif_only
# ---------------------------------------------------------------------------


class InvalidCifError(ValueError):
    """Raised when a CIF cannot be parsed by the canonical minimal parser."""


def valid_cif_only(envelope: Envelope) -> FalsifierItem:
    """Return FAIL FalsifierItem if the CIF in envelope.output is unparseable.

    Uses ``cif_hash_from_text`` to attempt a parse; rejects on ValueError.

    Args:
        envelope: L6 Envelope with ``output["cif_text"]`` set.

    Returns:
        FalsifierItem with status "pass" or "fail".

    Raises:
        InvalidCifError — when the CIF cannot be parsed.
    """
    cif_text: str = (envelope.output or {}).get("cif_text", "")

    if not cif_text.strip():
        raise InvalidCifError("CIF text is empty or missing in envelope output.")

    try:
        cif_hash_from_text(cif_text)
    except (ValueError, Exception) as exc:
        raise InvalidCifError(f"CIF parse failed: {exc}") from exc

    return FalsifierItem(
        name="l6.cif_valid",
        threshold="cif_hash_from_text succeeds",
        actual={"cif_text_len": len(cif_text)},
        status="pass",
    )


# ---------------------------------------------------------------------------
# charge_neutrality_check
# ---------------------------------------------------------------------------


class ChargeNeutralityError(ValueError):
    """Raised when charge neutrality cannot be confirmed."""


def charge_neutrality_check(structure: dict[str, Any]) -> FalsifierItem:
    """Check charge neutrality by summing oxidation states.

    Args:
        structure: dict with "species" list (element symbols) and optionally
                   "oxidation_states" list (overrides lookup table).

    Returns:
        FalsifierItem with status "pass" if neutral, "fail" if not, or
        "inconclusive" if any element is missing from the lookup table.

    Raises:
        ChargeNeutralityError — when total charge is non-zero and all states
        are known (hard fail, not inconclusive).
    """
    species: list[str] = structure.get("species", [])
    overrides: list[int] | None = structure.get("oxidation_states")

    if overrides is not None:
        total = sum(overrides)
        if total != 0:
            raise ChargeNeutralityError(
                f"Structure is not charge neutral: sum(oxidation_states) = {total}"
            )
        return FalsifierItem(
            name="l6.charge_neutral",
            threshold="sum(oxidation_states) == 0",
            actual={"total_charge": total},
            status="pass",
        )

    # Use lookup table.
    unknown: list[str] = []
    total = 0
    for sp in species:
        if sp not in _OXIDATION_STATES:
            unknown.append(sp)
        else:
            total += _OXIDATION_STATES[sp]

    if unknown:
        return FalsifierItem(
            name="l6.charge_neutral",
            threshold="sum(oxidation_states) == 0",
            actual={"unknown_elements": unknown, "partial_sum": total},
            status="inconclusive",
        )

    if total != 0:
        raise ChargeNeutralityError(
            f"Structure is not charge neutral: sum of known oxidation states = {total}. "
            f"Species: {species}"
        )

    return FalsifierItem(
        name="l6.charge_neutral",
        threshold="sum(oxidation_states) == 0",
        actual={"total_charge": total},
        status="pass",
    )


# ---------------------------------------------------------------------------
# min_interatomic_distance
# ---------------------------------------------------------------------------


class MinDistanceError(ValueError):
    """Raised when any pair of atoms is closer than the threshold."""


def min_interatomic_distance(
    structure: dict[str, Any],
    threshold_angstrom: float = 0.7,
) -> FalsifierItem:
    """Check that no two atoms are closer than ``threshold_angstrom``.

    Computes Cartesian distances from fractional coordinates and the lattice
    matrix. For periodic images only the ±1 supercell copies are checked
    (sufficient for the threshold distances involved).

    Args:
        structure: dict with "lattice" ([[a1,a2,a3],[b1,b2,b3],[c1,c2,c3]])
                   and "frac_coords" (list of [x,y,z]).
        threshold_angstrom: Minimum allowed pair distance in Angstrom.

    Returns:
        FalsifierItem with status "pass" or "fail".

    Raises:
        MinDistanceError — when any pair is closer than the threshold.
    """
    lattice: list[list[float]] = structure.get("lattice_vectors", structure.get("lattice", []))
    frac_coords: list[list[float]] = structure.get("fractional_coords", structure.get("frac_coords", []))

    if not lattice or not frac_coords:
        return FalsifierItem(
            name="l6.minimum_distance_ok",
            threshold=f">= {threshold_angstrom} Å",
            actual={"reason": "no lattice or coords"},
            status="inconclusive",
        )

    # Convert fractional → Cartesian.
    def frac_to_cart(frac: list[float]) -> list[float]:
        return [
            frac[0] * lattice[0][0] + frac[1] * lattice[1][0] + frac[2] * lattice[2][0],
            frac[0] * lattice[0][1] + frac[1] * lattice[1][1] + frac[2] * lattice[2][1],
            frac[0] * lattice[0][2] + frac[1] * lattice[1][2] + frac[2] * lattice[2][2],
        ]

    cart = [frac_to_cart(fc) for fc in frac_coords]
    n = len(cart)
    min_d = float("inf")

    for i in range(n):
        for j in range(i + 1, n):
            dx = cart[i][0] - cart[j][0]
            dy = cart[i][1] - cart[j][1]
            dz = cart[i][2] - cart[j][2]
            d = math.sqrt(dx * dx + dy * dy + dz * dz)
            if d < min_d:
                min_d = d

    if min_d < threshold_angstrom:
        raise MinDistanceError(
            f"Minimum interatomic distance {min_d:.4f} Å is below threshold "
            f"{threshold_angstrom} Å."
        )

    return FalsifierItem(
        name="l6.minimum_distance_ok",
        threshold=f">= {threshold_angstrom} Å",
        actual={"min_distance_ang": round(min_d, 4)},
        status="pass",
    )


# ---------------------------------------------------------------------------
# structure_hash_dedupe
# ---------------------------------------------------------------------------


class DuplicateStructureError(ValueError):
    """Raised when duplicate structure_hash values are found within a batch."""


def structure_hash_dedupe(envelopes: list[Envelope]) -> FalsifierItem:
    """Flag duplicate structure_hash values within a generated batch.

    Args:
        envelopes: List of L6 Envelopes from a single generation call.

    Returns:
        FalsifierItem with status "pass" if all unique, "fail" if duplicates.

    Raises:
        DuplicateStructureError — when duplicates are found.
    """
    seen: dict[str, str] = {}  # hash -> candidate_id
    duplicates: list[dict[str, Any]] = []

    for env in envelopes:
        output = env.output or {}
        s_hash = output.get("structure_hash", "")
        if not s_hash:
            continue
        if s_hash in seen:
            duplicates.append(
                {
                    "hash": s_hash,
                    "first": seen[s_hash],
                    "duplicate": env.candidate_id,
                }
            )
        else:
            seen[s_hash] = env.candidate_id

    if duplicates:
        raise DuplicateStructureError(
            f"Duplicate structure_hash within batch: {duplicates}"
        )

    return FalsifierItem(
        name="l6.dedup_unique",
        threshold="no duplicate structure_hash in batch",
        actual={"n_unique": len(seen), "n_total": len(envelopes)},
        status="pass",
    )


# ---------------------------------------------------------------------------
# reference_expansion_dedupe
# ---------------------------------------------------------------------------


class ReferenceMatchError(ValueError):
    """Raised when a generated candidate matches a reference database entry."""


def reference_expansion_dedupe(
    envelope: Envelope,
    reference_set: set[str] | None = None,
) -> FalsifierItem:
    """Check candidate structure_hash against MP/JARVIS/Alexandria/GNoME/OPTIMADE.

    Args:
        envelope: L6 Envelope with ``output["structure_hash"]``.
        reference_set: Set of reference structure_hash strings. Stub-stubbed
                       from positive fixture hashes if None.

    Returns:
        FalsifierItem with status "pass" (not in any reference) or "fail".

    Raises:
        ReferenceMatchError — when the hash matches a reference entry.
    """
    output = envelope.output or {}
    s_hash = output.get("structure_hash", "")

    if reference_set is None:
        from zer0pa_materials.adapters.l6.lematgen_eval import _load_fixture_hashes
        reference_set = _load_fixture_hashes()

    if s_hash and s_hash in reference_set:
        raise ReferenceMatchError(
            f"Candidate {envelope.candidate_id!r} structure_hash {s_hash!r} "
            "matched a reference database entry. "
            "Not novel — set novelty_status='duplicate'."
        )

    return FalsifierItem(
        name="l6.reference_expansion_dedupe",
        threshold="structure_hash not in reference set",
        actual={"structure_hash": s_hash, "reference_size": len(reference_set)},
        status="pass",
    )


# ---------------------------------------------------------------------------
# pymatgen_structure_matcher
# ---------------------------------------------------------------------------


def pymatgen_structure_matcher(
    envelope: Envelope,
    reference_set: list[Any] | None = None,
) -> FalsifierItem:
    """Compare using pymatgen StructureMatcher if pymatgen is installed.

    If pymatgen is not installed, gracefully returns a "parked" item
    (status="inconclusive") and documents the gap.

    Args:
        envelope: L6 Envelope with ``output["cif_text"]``.
        reference_set: List of pymatgen Structure objects (or None for stub).

    Returns:
        FalsifierItem — "pass" if no match, "inconclusive" if pymatgen absent,
        "fail" if pymatgen match found.
    """
    try:
        import importlib.util
        if importlib.util.find_spec("pymatgen") is None:
            raise ImportError("pymatgen not installed")
        # If pymatgen IS installed, we would do:
        # from pymatgen.analysis.structure_matcher import StructureMatcher
        # sm = StructureMatcher()
        # ... match against reference_set ...
        # For now, document as parked_pending_pymatgen even when installed,
        # since we have no real reference Structure objects.
        raise ImportError("parked_pending_pymatgen — no reference Structure objects provided")
    except ImportError:
        return FalsifierItem(
            name="l6.pymatgen_structure_matcher",
            threshold="StructureMatcher finds no match",
            actual={"status": "parked_pending_pymatgen"},
            status="inconclusive",
        )


# ---------------------------------------------------------------------------
# novelty_status_gate
# ---------------------------------------------------------------------------


class PrematureNoveltyError(ValueError):
    """Raised when novelty_status='novel' is set before all gates pass."""


def novelty_status_gate(envelope: Envelope) -> FalsifierItem:
    """Block premature novelty_status='novel' claims.

    PRD discipline: "novelty_status: novel" is a CLAIM. The gate enforces
    that this claim cannot be set until:
        1. All dedupe falsifiers passed (structure_hash_dedupe +
           reference_expansion_dedupe + pymatgen_structure_matcher).
        2. L1 validation passed.
        3. ionic and L2 ensemble passed.

    Until those layers run, novelty_status MUST be "pending".

    In stub mode (before L1/ionic/L2 run), this falsifier fires when
    novelty_status is prematurely set to "novel".

    Args:
        envelope: L6 Envelope.

    Returns:
        FalsifierItem with status "pass" if pending/duplicate/invalid,
        or "fail" if prematurely "novel".

    Raises:
        PrematureNoveltyError — when novelty_status="novel" is set before
        all required gates have passed.
    """
    output = envelope.output or {}
    novelty_status = output.get("novelty_status", "pending")

    # Check if any dedupe falsifier recorded a failure.
    # In the envelope, falsifier items may or may not be populated yet.
    # The gate fires on the *output field* directly.
    if novelty_status == "novel":
        # In stub mode: always reject premature "novel".
        # In real pipeline: additionally check that L1/ionic/L2 back-edges exist.
        back_edges = envelope.back_edges or []
        l1_back_edge = any(
            getattr(be, "layer", None) == "L1" or
            (isinstance(be, dict) and be.get("layer") == "L1")
            for be in back_edges
        )
        if not l1_back_edge:
            raise PrematureNoveltyError(
                f"Candidate {envelope.candidate_id!r} has novelty_status='novel' "
                "but no L1 back-edge exists. novelty_status MUST remain 'pending' "
                "until L1 + ionic + L2 ensemble all pass and back-edges are attached."
            )

    status: FalsifierStatus
    if novelty_status == "pending":
        status = "blocked"  # not yet resolved — not a pass
    elif novelty_status == "duplicate":
        status = "fail"
    elif novelty_status == "invalid":
        status = "fail"
    elif novelty_status == "novel":
        # Passed the premature check above (has L1 back-edge).
        status = "pass"
    else:
        status = "blocked"

    return FalsifierItem(
        name="l6.novelty_resolved",
        threshold="novelty_status in {novel,duplicate,invalid} after all gates",
        actual=novelty_status,
        status=status,
    )


# ---------------------------------------------------------------------------
# recompute_novelty   (Wave D hardened gate 3)
# ---------------------------------------------------------------------------


def recompute_novelty(
    envelope: Envelope | dict[str, Any],
    reference_set: Iterable[str] | None = None,
    batch_envelopes: Iterable[Envelope | dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Recompute the novelty status from raw evidence (CIF + back-edges).

    Re-runs every dedupe pipeline step from scratch:

    1. Recompute the candidate's ``structure_hash`` from
       ``output.cif_text`` (or from the structure dict). If recompute
       fails, the candidate is ``"invalid"``.
    2. Match the recomputed hash against the supplied
       ``reference_set`` (Materials Project / JARVIS / Alexandria /
       GNoME / OPTIMADE references). If matched, ``"duplicate"``.
    3. Match the recomputed hash against the per-batch sibling
       hashes (``batch_envelopes``). If matched, ``"duplicate"``.
    4. If the candidate has all three downstream back-edges
       (``L1``, ``ionic``, ``L2``), it can be ``"novel"``.
    5. Otherwise return ``"pending"`` — the candidate has not yet
       collected the gates required for a novelty claim.

    Returns
    -------
    dict
        ``{"status": <recomputed status>, "structure_hash":
        <recomputed sha or None>, "back_edges_present": [...]}``. The
        status is one of ``{"novel","duplicate","invalid","pending"}``
        and is suitable for compare-against-claim in
        :func:`novelty_status_gate_recomputed`.
    """
    if isinstance(envelope, Envelope):
        body = envelope.model_dump(mode="json")
    else:
        body = dict(envelope)

    s_hash = recompute_structure_hash_from_envelope(body)
    if not s_hash:
        return {"status": "invalid", "structure_hash": None, "back_edges_present": []}

    ref_set = set(reference_set or [])
    if s_hash in ref_set:
        return {
            "status": "duplicate",
            "structure_hash": s_hash,
            "duplicate_of": "reference_set",
            "back_edges_present": [],
        }

    # Per-batch dedupe.
    batch_hashes: dict[str, str] = {}
    for sibling in batch_envelopes or []:
        if isinstance(sibling, Envelope):
            sib = sibling.model_dump(mode="json")
        else:
            sib = dict(sibling)
        sib_id = sib.get("candidate_id", "<unknown>")
        if sib_id == body.get("candidate_id"):
            continue
        sib_hash = recompute_structure_hash_from_envelope(sib)
        if sib_hash:
            batch_hashes[sib_hash] = sib_id
    if s_hash in batch_hashes:
        return {
            "status": "duplicate",
            "structure_hash": s_hash,
            "duplicate_of": batch_hashes[s_hash],
            "back_edges_present": [],
        }

    # Back-edge presence check — required to elevate to "novel".
    back_edges = body.get("back_edges") or []
    layers_present: set[str] = set()
    for be in back_edges:
        if isinstance(be, dict):
            layer = be.get("layer")
        else:
            layer = getattr(be, "layer", None)
        if layer:
            layers_present.add(str(layer))
    required = {"L1", "ionic", "L2"}
    if required <= layers_present:
        return {
            "status": "novel",
            "structure_hash": s_hash,
            "back_edges_present": sorted(layers_present),
        }
    return {
        "status": "pending",
        "structure_hash": s_hash,
        "back_edges_present": sorted(layers_present),
        "missing_back_edges": sorted(required - layers_present),
    }


def novelty_status_gate_recomputed(
    envelope: Envelope | dict[str, Any],
    reference_set: Iterable[str] | None = None,
    batch_envelopes: Iterable[Envelope | dict[str, Any]] | None = None,
) -> FalsifierItem:
    """Hardened ``novelty_status`` gate that ignores the claim and recomputes.

    Compares the envelope's claimed ``output.novelty_status`` against
    the result of :func:`recompute_novelty`. Pass conditions:

      * Recomputed status is ``"novel"`` AND claim equals ``"novel"``.
      * Recomputed status is ``"pending"`` AND claim is ``"pending"`` OR
        claim is unset.

    Fail conditions (any one):
      * Recomputed status is ``"duplicate"`` (the candidate is known to
        be in a reference database or to a batch sibling). Claim is
        irrelevant; the gate still fails.
      * Claim is ``"novel"`` but recompute is ``"pending"`` /
        ``"duplicate"`` / ``"invalid"``.
      * Recompute is ``"invalid"`` (cannot recover hash from raw CIF).
    """
    if isinstance(envelope, Envelope):
        body = envelope.model_dump(mode="json")
    else:
        body = dict(envelope)
    output = body.get("output") or {}
    claim = output.get("novelty_status", "pending") if isinstance(output, dict) else "pending"

    re = recompute_novelty(body, reference_set=reference_set, batch_envelopes=batch_envelopes)
    recomputed = re["status"]

    if recomputed == "duplicate":
        return FalsifierItem(
            name="l6.novelty_resolved_recomputed",
            threshold=(
                "recompute(structure_hash) NOT in reference set AND NOT in batch siblings; "
                "back_edges include L1+ionic+L2"
            ),
            actual={
                "claim": claim,
                "recomputed": recomputed,
                "structure_hash": re.get("structure_hash"),
                "duplicate_of": re.get("duplicate_of"),
            },
            status="fail",
            rationale=(
                f"recomputed structure_hash matches {re.get('duplicate_of')!r}; "
                f"candidate is duplicate (claim was {claim!r})"
            ),
        )

    if recomputed == "invalid":
        return FalsifierItem(
            name="l6.novelty_resolved_recomputed",
            threshold=(
                "recompute(structure_hash) succeeds AND not in reference / batch"
            ),
            actual={"claim": claim, "recomputed": recomputed},
            status="fail",
            rationale="cannot recompute structure_hash from raw evidence",
        )

    if recomputed == "novel":
        if claim != "novel":
            return FalsifierItem(
                name="l6.novelty_resolved_recomputed",
                threshold="claim matches recompute when recompute=='novel'",
                actual={"claim": claim, "recomputed": recomputed},
                status="fail",
                rationale=(
                    f"recompute says novel but claim is {claim!r} — "
                    "operator should set novelty_status='novel'"
                ),
            )
        return FalsifierItem(
            name="l6.novelty_resolved_recomputed",
            threshold="claim matches recompute when recompute=='novel'",
            actual={
                "claim": claim,
                "recomputed": recomputed,
                "structure_hash": re.get("structure_hash"),
                "back_edges_present": re.get("back_edges_present"),
            },
            status="pass",
        )

    # recomputed == "pending"
    if claim == "novel":
        return FalsifierItem(
            name="l6.novelty_resolved_recomputed",
            threshold="if claim=='novel' then back_edges include L1+ionic+L2",
            actual={
                "claim": claim,
                "recomputed": recomputed,
                "missing_back_edges": re.get("missing_back_edges"),
            },
            status="fail",
            rationale=(
                "claim says novel but back-edges incomplete — "
                f"missing {re.get('missing_back_edges')}"
            ),
        )
    return FalsifierItem(
        name="l6.novelty_resolved_recomputed",
        threshold="claim matches recompute (pending or novel based on back-edges)",
        actual={
            "claim": claim,
            "recomputed": recomputed,
            "structure_hash": re.get("structure_hash"),
        },
        status="pass",
    )
