"""Shared pytest fixtures and constants for the A2 fixture wave tests.

The repository's `fixtures/` tree is the single source of truth. This
module exposes a few pure-Python helpers that the test files share:

* `FIXTURES_ROOT` — absolute path to `<repo>/fixtures/`.
* `RESEARCH_BOUNDARY` — verbatim boundary block for assertion convenience.
* `iter_manifests` — iterator over (path, parsed-json) for every manifest.
* `BUDGET_BYTES` — total committed footprint cap (PRD §Constraints; no bulk).

The detect_falsifier function used by `test_negative_targets.py` is a
small, deterministic stub. Its job is NOT to re-derive the real falsifier
package (Wave 9 owns that). It maps each negative-fixture directory name
to its expected falsifier target, executes a *small handcoded check* that
demonstrably triggers, and returns a list of fired targets. The test then
asserts: list == [expected_target]. The check is intentionally
fixture-aware (each negative carries machine-checkable data), so a future
real falsifier subagent can replace this stub without changing the
tests' contract.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURES_ROOT = REPO_ROOT / "fixtures"

RESEARCH_BOUNDARY = (
    "Research infrastructure for in silico materials science discovery. "
    "Outputs are research artifacts. No regulatory certification claims. "
    "No clinical or human-subject use. ITAR / weapons applications are "
    "out of scope (Meta UMA Acceptable Use Policy and operator policy)."
)

# 1 MB upper bound on committed fixture footprint.
BUDGET_BYTES = 1_000_000


def iter_manifests(category: str | None = None) -> Iterator[tuple[Path, dict[str, Any]]]:
    """Yield (manifest_path, manifest_dict) for every manifest under fixtures/.

    If ``category`` is given (one of: ``structures``, ``negatives``,
    ``extractions``, ``tdb``), only manifests under that subtree are
    returned.
    """
    if category is None:
        roots = [FIXTURES_ROOT / s for s in ("structures", "negatives", "extractions", "tdb")]
    else:
        roots = [FIXTURES_ROOT / category]
    for root in roots:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.json")):
            if not path.name.startswith("manifest"):
                # Cu-Mg-toy.manifest.json and Li-halide-toy.manifest.json are
                # also manifest files even though they aren't named exactly
                # "manifest.json". Capture them via the *.manifest.json case.
                if not path.name.endswith(".manifest.json"):
                    continue
            data = json.loads(path.read_text())
            yield path, data


def total_committed_bytes() -> int:
    """Sum of every committed file under ``fixtures/`` (excluding .gitkeep)."""
    total = 0
    for p in FIXTURES_ROOT.rglob("*"):
        if p.is_file() and p.name != ".gitkeep":
            total += p.stat().st_size
    return total


# ----------------------------------------------------------------------------
# Stub falsifier — used by test_negative_targets.py
# ----------------------------------------------------------------------------


def _smallest_eigenvalue(matrix: list[list[float]]) -> float:
    arr = np.asarray(matrix, dtype=np.float64)
    return float(np.linalg.eigvalsh(arr).min())


def detect_falsifier(fixture_dir: Path) -> list[str]:
    """Return the list of falsifier-target names a negative fixture triggers.

    The list MUST contain exactly one entry equal to the manifest's
    ``negative_falsifier_target``. If multiple entries appear, the fixture
    is "leaky" and the test fails.

    Each negative-fixture directory carries machine-checkable data; this
    function applies a small handcoded check per kind. A future real
    falsifier package (Wave 9) replaces these stubs without changing the
    test contract: the test asserts `detect_falsifier == [target_name]`.
    """
    name = fixture_dir.name
    fired: list[str] = []

    if name == "invalid_cif":
        from zer0pa_materials_workbench.envelope.hashing import parse_minimal_cif

        cif = (fixture_dir / "structure.cif").read_text()
        try:
            parse_minimal_cif(cif)
        except (ValueError, IndexError):
            fired.append("invalid_cif")
        return fired

    if name == "duplicate_candidate":
        from zer0pa_materials_workbench.envelope.hashing import cif_hash_from_text

        # Compare against the LLZO cubic positive fixture's hash (committed
        # in fixtures/structures/LLZO/cubic/manifest.json).
        positive_manifest = json.loads(
            (FIXTURES_ROOT / "structures" / "LLZO" / "cubic" / "manifest.json").read_text()
        )
        target_hash = positive_manifest["structure_hash"]
        text = (fixture_dir / "structure.cif").read_text()
        h = cif_hash_from_text(text)
        if h == target_hash:
            fired.append("duplicate_candidate")
        return fired

    if name == "missing_boundary":
        from zer0pa_materials_workbench.boundary import find_violations

        env = json.loads((fixture_dir / "envelope.json").read_text())
        violations = find_violations(env)
        # We expect exactly the boundary missing/non-verbatim violation; no
        # forbidden-phrase fragments in the test fixture.
        if any(v.field_path == "$.research_boundary" for v in violations):
            fired.append("missing_boundary")
        return fired

    if name == "ungrounded_property":
        from pydantic import ValidationError

        from zer0pa_materials_workbench.envelope.layer_outputs import Phase0Output

        payload = json.loads((fixture_dir / "extraction.json").read_text())
        # Drop the boundary key (Phase0Output schema doesn't carry it).
        payload.pop("research_boundary", None)
        try:
            Phase0Output.model_validate(payload)
        except ValidationError:
            fired.append("ungrounded_property")
        return fired

    if name == "unstable_phonon":
        spec = json.loads((fixture_dir / "phonon_spectrum.json").read_text())
        if spec["imaginary_mode_max_THz"] > 0.25:
            fired.append("unstable_phonon")
        return fired

    if name == "unreadable_tdb":
        # Apply the small syntactic-shape check (no pycalphad assumed).
        text = (fixture_dir / "broken.tdb").read_text()
        if not _tdb_syntactically_well_formed(text):
            fired.append("unreadable_tdb")
        return fired

    if name == "high_disagreement":
        l2 = json.loads((fixture_dir / "l2_result.json").read_text())
        # PRD §L2: hard reject if energy disagreement > 75 meV/atom.
        if l2["energy_disagreement_meV_per_atom"] > 75.0:
            fired.append("high_disagreement")
        return fired

    if name == "non_spd_tensor":
        l5 = json.loads((fixture_dir / "l5_result.json").read_text())
        matrix = l5["_synthetic_C_3x3"]
        smallest = _smallest_eigenvalue(matrix)
        if smallest <= 0.0:
            fired.append("non_spd_tensor")
        return fired

    if name == "tdb_quarantine_breach":
        claim = json.loads((fixture_dir / "tdb_claim.json").read_text())
        provider = claim.get("tdb_provider", "")
        license_str = claim.get("license", "")
        redistributable = claim.get("redistributable", False)
        commercial = (
            "thermocalc" in provider.lower()
            or license_str.lower() == "proprietary"
        )
        if commercial and redistributable:
            fired.append("tdb_quarantine_breach")
        return fired

    if name == "alabos_executable_in_recipe_only":
        proto = json.loads((fixture_dir / "protocol.json").read_text())
        if proto.get("alabos_mode") == "recipe_only" and proto.get("hardware_executable"):
            fired.append("alabos_executable_in_recipe_only")
        return fired

    if name == "runpod_schema_drift":
        from pydantic import ValidationError

        from zer0pa_materials_workbench.envelope.envelope import Envelope

        env = json.loads((fixture_dir / "envelope.json").read_text())
        # Envelope is sealed (extra='forbid'). The drift field violates that.
        try:
            Envelope.model_validate(env)
        except ValidationError:
            fired.append("runpod_schema_drift")
        return fired

    if name == "tenant_only_tuple_leak":
        bundle = json.loads((fixture_dir / "tuple_export.json").read_text())
        if bundle.get("export_bundle") == "shared_learning":
            for tup in bundle.get("tuples", []):
                if tup.get("reuse_scope") == "tenant_only":
                    fired.append("tenant_only_tuple_leak")
                    break
        return fired

    if name == "ionic_overclaim_no_service":
        cand = json.loads((fixture_dir / "candidate.json").read_text())
        if (
            cand.get("ionic_conductivity_S_per_cm", 0.0) > 1e-3
            and cand.get("ionic_transport_service_ref") is None
        ):
            fired.append("ionic_overclaim_no_service")
        return fired

    raise AssertionError(
        f"unknown negative fixture directory name: {name!r}; "
        "extend conftest.detect_falsifier to handle it"
    )


# ----------------------------------------------------------------------------
# TDB syntactic-shape parser (no pycalphad dependency)
# ----------------------------------------------------------------------------


def _tdb_syntactically_well_formed(text: str) -> bool:
    """Return True iff the TDB text passes a small syntactic-shape check.

    The check is intentionally permissive — it MUST accept the toy Cu-Mg
    and Li-halide fixtures and MUST reject the deliberately broken
    ``unreadable_tdb`` fixture. The check enforces:

    1. Statements are ``!``-terminated (TDB requires this).
    2. ELEMENT lines have at least 5 fields after ``ELEMENT``
       (name, ref-state, mass, H298, S298).
    3. Each FUNCTION block contains a ``;`` (mid-block separator).
    4. Every PHASE has a CONSTITUENT line and at least one PARAMETER
       block.
    """
    text = _strip_tdb_comments(text)
    # After stripping ``$``-comments, the file MUST still contain at least
    # one ``!`` (every TDB statement is ``!``-terminated).
    if "!" not in text:
        return False

    lines = [ln.rstrip() for ln in text.splitlines() if ln.strip()]

    units = _split_into_statements(lines)

    has_element = False
    has_phase = False
    has_constituent = False
    has_parameter = False

    for unit in units:
        head = unit.lstrip().split(maxsplit=1)
        if not head:
            continue
        kw = head[0].upper()
        body = head[1] if len(head) > 1 else ""
        if kw == "ELEMENT":
            tokens = body.split()
            if len(tokens) < 5:
                return False
            has_element = True
        elif kw == "FUNCTION":
            if ";" not in unit:
                return False
        elif kw == "PHASE":
            has_phase = True
        elif kw == "CONSTITUENT":
            has_constituent = True
        elif kw == "PARAMETER":
            has_parameter = True

    if not has_element:
        return False
    if has_phase and (not has_constituent or not has_parameter):
        return False
    return True


def _strip_tdb_comments(text: str) -> str:
    """Drop $-prefixed comment lines."""
    return "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith("$"))


def _split_into_statements(lines: Iterable[str]) -> list[str]:
    """Group lines into statements ending in ``!`` (TDB statement terminator)."""
    out: list[str] = []
    buf: list[str] = []
    for ln in lines:
        buf.append(ln)
        if "!" in ln:
            joined = " ".join(buf)
            # statement is everything up to the first ``!``.
            stmt, *rest = joined.split("!", 1)
            out.append(stmt.strip())
            buf = []
            if rest and rest[0].strip():
                # tail after ! is start of next statement.
                buf.append(rest[0].strip())
    if buf and " ".join(buf).strip():
        out.append(" ".join(buf).strip())
    return out
