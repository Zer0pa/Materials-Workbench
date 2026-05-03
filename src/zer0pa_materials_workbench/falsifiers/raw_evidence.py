"""Shared recompute helpers — Wave D falsifier hardening.

Boundary
--------
Research infrastructure for in silico materials science discovery. Outputs are
research artifacts. No regulatory certification claims. No clinical or
human-subject use. ITAR / weapons applications are out of scope (Meta UMA
Acceptable Use Policy and operator policy).

Purpose
-------

The Wave D audit caught a systemic falsifier weakness: many gates TRUST FIELDS
in an envelope (``output.energy_disagreement_meV_per_atom``,
``output.novelty_status``, ``audit.source_manifest_refs`` …) instead of
RECOMPUTING the value from raw evidence. RESISTANCE.md ``fp-shapematch``
manifests at the falsifier layer as "shape-match as identity-match": a buggy
or malicious adapter can paint the right field shape on the wrong number and
the gate waves it through.

This module is the SHARED RAW-EVIDENCE PRIMITIVE. Hardened falsifiers in
``l2_falsifiers``, ``l3_falsifiers``, ``l5_falsifiers``, ``l6_falsifiers``,
``ionic_falsifiers`` and ``phase0_falsifiers`` import the helpers below and
recompute the load-bearing scalar / hash / reference / chain from the raw
inputs they have access to (per-model predictions, raw CIF text, the
sources.jsonl ledger, the on-disk artifact bytes).

Every helper is:

* PURE — no I/O except for explicit ``Path`` reads where the caller
  asked us to read a file.
* DETERMINISTIC — given the same inputs, returns the same result.
* SCHEMA-AWARE — accepts the wire-level envelope dict shape produced by
  the production adapters, falls back gracefully when fields are absent.

The helpers do NOT raise on missing fields by themselves; they return
``None`` (or an empty list / set / dict) and let the caller emit the
appropriate ``FalsifierItem`` with status ``blocked``. Adversarial tests
in ``tests/unit/falsifiers/test_recompute_*.py`` show that the OLD
"trust the field" gate would accept a forged envelope while the NEW
recompute gate catches it.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from zer0pa_materials_workbench.envelope.hashing import (
    cif_hash_from_text,
    structure_hash,
)

__all__ = [
    "ARRHENIUS_KB_EV_PER_K",
    "DEFAULT_DISAGREEMENT_TOLERANCE_MEV",
    "DEFAULT_FORCE_TOLERANCE_EV_PER_A",
    "extract_per_model_predictions",
    "find_audit_row_by_event_hash",
    "find_ionic_back_edge_target",
    "find_source_manifest_row",
    "implied_arrhenius_barrier_eV",
    "iter_audit_rows",
    "recompute_artifact_sha256",
    "recompute_l2_disagreement",
    "recompute_structure_hash_from_envelope",
]


# ---------------------------------------------------------------------------
# Tolerances
# ---------------------------------------------------------------------------

# Recompute tolerance: the claimed disagreement scalar may differ from the
# recomputed value only by a small numerical-precision smudge. 0.5 meV/atom
# is well below the 25 meV/atom routing threshold and well above
# IEEE-754 double rounding noise on a 5-digit physical quantity.
DEFAULT_DISAGREEMENT_TOLERANCE_MEV: float = 0.5
DEFAULT_FORCE_TOLERANCE_EV_PER_A: float = 0.005

# Boltzmann constant in eV/K — used by the Arrhenius implied-barrier
# helper (Wave D ionic gate 5).
ARRHENIUS_KB_EV_PER_K: float = 8.617333262e-5  # CODATA 2018


# ---------------------------------------------------------------------------
# (1) L2 disagreement recompute
# ---------------------------------------------------------------------------


def extract_per_model_predictions(
    envelope: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Return the raw per-model prediction list from an L2 envelope.

    The L2 envelope schema records per-model predictions under
    ``output.predictions`` (canonical) or ``output.per_model_predictions``
    (alias used in some adapter-side records). This helper accepts both
    and returns a list of dicts, each carrying at least
    ``{model, energy_eV_per_atom, force_rmse_eV_per_Ang}``.

    Returns an empty list when the envelope is missing the predictions
    field — callers must treat this as ``status="blocked"``.
    """
    output = envelope.get("output") or {}
    if not isinstance(output, Mapping):
        return []
    preds = output.get("predictions")
    if preds is None:
        preds = output.get("per_model_predictions")
    if not isinstance(preds, list):
        return []
    return [p for p in preds if isinstance(p, Mapping)]


def recompute_l2_disagreement(
    envelope: Mapping[str, Any],
) -> tuple[float | None, float | None]:
    """Recompute (energy_disagreement_meV_per_atom, force_rmse_disagreement_eV_per_A).

    The recompute is "what would the canonical L2 ensemble runner have
    written into the envelope, given the per-model predictions that are
    actually in the envelope?" It uses the SAME formula as
    :class:`zer0pa_materials_workbench.adapters.l2.ensemble.L2EnsembleRunner.run`:

        energy_disagreement_meV = abs(E_DPA - E_MACE) * 1000
        force_rmse_disagreement_eV/A = abs(F_DPA - F_MACE)

    DPA and MACE are identified by the ``model`` field substring match
    (``"DPA"`` and ``"MACE"`` respectively). If two predictions match the
    same family, the first one is used; if neither family appears, returns
    ``(None, None)`` to signal blocked recompute.

    Optional models (UMA, SevenNet, etc.) are recorded but do NOT enter
    the disagreement computation — that is the canonical PRD invariant
    "DPA + MACE are the mandatory pair".

    Returns
    -------
    (energy_disagreement_meV_per_atom, force_rmse_disagreement_eV_per_A)
        A tuple of recomputed scalars. Either or both can be ``None`` if
        the necessary fields are missing.
    """
    preds = extract_per_model_predictions(envelope)
    if not preds:
        return (None, None)

    dpa = next((p for p in preds if "DPA" in str(p.get("model", ""))), None)
    mace = next((p for p in preds if "MACE" in str(p.get("model", ""))), None)
    if dpa is None or mace is None:
        return (None, None)

    e_dpa = dpa.get("energy_eV_per_atom")
    e_mace = mace.get("energy_eV_per_atom")
    f_dpa = dpa.get("force_rmse_eV_per_Ang")
    f_mace = mace.get("force_rmse_eV_per_Ang")

    energy_meV = (
        abs(float(e_dpa) - float(e_mace)) * 1000.0
        if (e_dpa is not None and e_mace is not None)
        else None
    )
    force_eV_A = (
        abs(float(f_dpa) - float(f_mace))
        if (f_dpa is not None and f_mace is not None)
        else None
    )
    return (energy_meV, force_eV_A)


# ---------------------------------------------------------------------------
# (2) Structure hash recompute (used by L6 novelty re-dedupe)
# ---------------------------------------------------------------------------


def recompute_structure_hash_from_envelope(
    envelope: Mapping[str, Any],
) -> str | None:
    """Recompute structure_hash from the envelope's raw CIF / structure dict.

    Looks for, in order:
      1. ``envelope.output.cif_text`` — parses with the canonical minimal
         CIF parser then hashes via :func:`structure_hash`.
      2. ``envelope.output.structure`` — a structure dict with
         ``lattice_vectors``, ``species``, ``fractional_coords``.
      3. ``envelope.output.lattice_vectors`` + ``species`` +
         ``fractional_coords`` directly (legacy shape).

    Returns ``None`` if none of those is present, or if a parse fails.

    The recomputed hash uses the canonical tolerances from
    :func:`zer0pa_materials_workbench.envelope.hashing.structure_hash`. A claim
    field ``output.structure_hash`` is NEVER trusted — that is the whole
    point of Wave D.
    """
    output = envelope.get("output") or {}
    if not isinstance(output, Mapping):
        return None

    cif_text = output.get("cif_text")
    if isinstance(cif_text, str) and cif_text.strip():
        try:
            return cif_hash_from_text(cif_text)
        except Exception:
            return None

    structure = output.get("structure")
    if isinstance(structure, Mapping) and {
        "lattice_vectors",
        "species",
        "fractional_coords",
    } <= set(structure.keys()):
        try:
            return structure_hash(dict(structure))
        except Exception:
            return None

    if {"lattice_vectors", "species", "fractional_coords"} <= set(output.keys()):
        try:
            return structure_hash(
                {
                    "lattice_vectors": output["lattice_vectors"],
                    "species": output["species"],
                    "fractional_coords": output["fractional_coords"],
                }
            )
        except Exception:
            return None

    return None


# ---------------------------------------------------------------------------
# (3) Artifact sha256 recompute (used by L5 sidecar gate)
# ---------------------------------------------------------------------------


def recompute_artifact_sha256(path: str | Path) -> str | None:
    """Read the on-disk artifact bytes and return a fresh ``sha256:<hex>``.

    Returns ``None`` if the path does not exist or cannot be read. The
    caller treats ``None`` as "artifact missing" — a deliberate failure
    mode for the L5 hardened gate (a forged envelope can claim an
    artifact URI that points to nothing).
    """
    p = Path(path)
    if not p.is_file():
        return None
    try:
        data = p.read_bytes()
    except OSError:
        return None
    return "sha256:" + hashlib.sha256(data).hexdigest()


# ---------------------------------------------------------------------------
# (4) Audit-log lookup helpers (used by source-manifest, ionic back-edge,
#     L3 sovereign block-enforcement gates)
# ---------------------------------------------------------------------------


def iter_audit_rows(
    audit_log: Any,
    category: str,
) -> Iterable[Mapping[str, Any]]:
    """Yield decoded payloads from an audit-log category.

    Accepts either:

    * a ``zer0pa_materials_workbench.audit.log.AuditLog`` instance (calls
      ``iter_rows`` and yields the payload dicts), or
    * a plain ``list`` / ``tuple`` of dicts (yielded directly — used by
      the unit tests that pass an in-memory ledger fixture), or
    * an iterable of payload dicts.

    Unknown shapes yield nothing.
    """
    # AuditLog has iter_rows(category) -> Iterator[AuditRow]
    if hasattr(audit_log, "iter_rows"):
        try:
            for row in audit_log.iter_rows(category):
                payload = getattr(row, "payload", None)
                if isinstance(payload, Mapping):
                    yield payload
        except Exception:
            return
        return

    # Plain iterable: yield Mapping items.
    if isinstance(audit_log, (list, tuple)):
        for entry in audit_log:
            if isinstance(entry, Mapping):
                if "payload" in entry and isinstance(entry["payload"], Mapping):
                    yield entry["payload"]
                else:
                    yield entry
        return

    # Anything else: best-effort iteration.
    try:
        for entry in audit_log:
            if isinstance(entry, Mapping):
                if "payload" in entry and isinstance(entry["payload"], Mapping):
                    yield entry["payload"]
                else:
                    yield entry
    except TypeError:
        return


def find_audit_row_by_event_hash(
    audit_log: Any,
    category: str,
    event_hash: str,
) -> Mapping[str, Any] | None:
    """Return the audit row whose top-level event_hash matches.

    Walks the rows in ``category`` and returns the first row whose
    ``event_hash`` equals the supplied value. Returns ``None`` if no
    match.

    Accepts the same audit-log shapes as :func:`iter_audit_rows` plus,
    additionally, a list of full row-dicts (with chain wrappers) so
    callers can search by the chain-level event_hash. This is the
    intended use for the ionic back-edge gate.
    """
    if hasattr(audit_log, "iter_rows"):
        try:
            for row in audit_log.iter_rows(category):
                row_eh = getattr(row, "event_hash", None)
                if row_eh == event_hash:
                    return row.model_dump(mode="json") if hasattr(row, "model_dump") else dict(row)
        except Exception:
            return None
        return None

    if isinstance(audit_log, (list, tuple)):
        for entry in audit_log:
            if isinstance(entry, Mapping) and entry.get("event_hash") == event_hash:
                return entry
        return None
    return None


def find_audit_row_by_audit_record_id(
    audit_log: Any,
    category: str,
    audit_record_id: str,
) -> Mapping[str, Any] | None:
    """Return the audit row whose payload['audit_record_id'] matches.

    Walks the rows in ``category`` and returns the first row whose
    payload contains ``audit_record_id == <given>``. Returns ``None`` if
    no match. Use this to resolve a back-edge ``audit_record_id`` to its
    actual recorded event.
    """
    for payload in iter_audit_rows(audit_log, category):
        if payload.get("audit_record_id") == audit_record_id:
            return payload
        # Some payloads nest the id inside a sub-dict.
        for sub_key in ("envelope", "audit"):
            sub = payload.get(sub_key)
            if isinstance(sub, Mapping) and sub.get("audit_record_id") == audit_record_id:
                return payload
    return None


def find_source_manifest_row(
    audit_log: Any,
    source_manifest_id: str,
) -> Mapping[str, Any] | None:
    """Return the sources.jsonl payload matching ``source_manifest_id``.

    Walks ``sources.jsonl`` and returns the first row whose payload
    has ``source_manifest_id == <given>``. Returns ``None`` if no
    match. The Wave D source-manifest linkage gate uses this to verify
    that an envelope's claimed ``source_manifest_refs`` actually exist.
    """
    for payload in iter_audit_rows(audit_log, "sources"):
        if payload.get("source_manifest_id") == source_manifest_id:
            return payload
    return None


def find_ionic_back_edge_target(
    envelope: Mapping[str, Any],
    audit_log: Any,
) -> Mapping[str, Any] | None:
    """Resolve the envelope's ionic back-edge to the recorded event row.

    Returns the audit row payload that the back-edge with ``layer ==
    "ionic"`` points at. Returns ``None`` if:

    * The envelope has no ionic back-edge.
    * The back-edge's ``audit_record_id`` does not resolve in
      ``events.jsonl``.

    The Wave D ionic back-edge gate fails an envelope when this returns
    None despite the envelope claiming an ionic conductivity scalar.
    """
    back_edges = envelope.get("back_edges") or []
    if not isinstance(back_edges, (list, tuple)):
        return None

    for be in back_edges:
        if not isinstance(be, Mapping):
            continue
        if be.get("layer") != "ionic":
            continue
        target_id = be.get("audit_record_id")
        if not target_id:
            continue
        # Search events.jsonl first, fall back to artifacts.jsonl.
        row = find_audit_row_by_audit_record_id(audit_log, "events", target_id)
        if row is None:
            row = find_audit_row_by_audit_record_id(audit_log, "artifacts", target_id)
        if row is not None:
            return row
    return None


# ---------------------------------------------------------------------------
# (5) Arrhenius implied-barrier helper
# ---------------------------------------------------------------------------


def implied_arrhenius_barrier_eV(
    sigma_S_per_cm: float,
    T_K: float = 300.0,
    sigma_0_S_per_cm: float = 1e3,
) -> float:
    """Return the activation barrier implied by an Arrhenius fit.

    Solves :math:`\\sigma = \\sigma_0 \\exp(-E_a / k_B T)` for ``E_a``::

        E_a [eV] = -k_B [eV/K] * T [K] * ln(sigma / sigma_0)

    The reference prefactor ``sigma_0 = 1e3 S/cm`` is the canonical
    superionic-conductor reference (see e.g. Famprikis 2019,
    Bachman 2016 Chem Rev). For typical solid electrolytes with
    ``sigma_0`` in the 1e2 - 1e4 S/cm range and ``sigma`` ~ 1e-3 S/cm at
    300 K, this returns barriers in the [0.20, 0.45] eV range — the
    Wave D ionic gate 5 plausibility band.

    This is a recompute, not a fit: it exists so the falsifier can ask
    "given the conductivity value the envelope is claiming, what is the
    implied barrier? Does it match the migration_barrier_eV the envelope
    is also claiming?"

    Raises ``ValueError`` for non-positive sigma or T.
    """
    if sigma_S_per_cm <= 0.0:
        raise ValueError(f"sigma must be positive; got {sigma_S_per_cm}")
    if T_K <= 0.0:
        raise ValueError(f"T must be positive; got {T_K}")
    if sigma_0_S_per_cm <= 0.0:
        raise ValueError(f"sigma_0 must be positive; got {sigma_0_S_per_cm}")
    return -ARRHENIUS_KB_EV_PER_K * T_K * math.log(sigma_S_per_cm / sigma_0_S_per_cm)


# ---------------------------------------------------------------------------
# (6) Reference structure hash set helper (used by L6 re-dedupe)
# ---------------------------------------------------------------------------


def llzo_cubic_reference_structure() -> dict[str, Any]:
    """Return a minimal LLZO cubic-garnet structure dict for adversarial tests.

    Garnet Li7La3Zr2O12 (cubic Ia-3d) is a paradigmatic battery solid
    electrolyte present in every reference database (Materials Project,
    JARVIS, etc.). The Wave D L6 re-dedupe gate uses its
    :func:`structure_hash` as the canonical "this structure is NOT
    novel" reference. The lattice constant ~12.97 Å is from
    Awaka 2009 (mp-942733).

    Numerical values are chosen to be deterministic and round-trip
    through :func:`structure_hash`. This is a TEST FIXTURE generator,
    not a CIF library: real reference sets come from the L6 adapter.
    """
    return {
        "lattice_vectors": [
            [12.9700, 0.0, 0.0],
            [0.0, 12.9700, 0.0],
            [0.0, 0.0, 12.9700],
        ],
        # Minimal cell — full Ia-3d garnet has 192 atoms; the hash is
        # deterministic over the canonicalised site list, so this small
        # set is sufficient for the adversarial test.
        "species": ["Li", "La", "Zr", "O"],
        "fractional_coords": [
            [0.000, 0.000, 0.000],
            [0.125, 0.000, 0.250],
            [0.000, 0.000, 0.500],
            [0.250, 0.250, 0.250],
        ],
    }
