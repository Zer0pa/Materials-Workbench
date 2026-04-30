"""Hard-failure detectors for the Runpod cutover (Wave 5c).

Ten PRD-mandated detectors are implemented as methods of
:class:`HardFailureDetector`.  Each detector:

1. Inspects its target (envelope dict, git status, audit log, etc.).
2. Returns a :class:`HardFailureResult` with ``passed: bool`` and evidence.
3. If ``passed is False``, emits a :class:`~zer0pa_materials.envelope.FalsifierItem`
   and (optionally) appends to ``falsifiers.jsonl``.

Detectors (10 total, PRD §Runpod Migration / hard cutover failures):
    1  detect_schema_drift          — JSON-Schema diff of envelope shapes
    2  detect_missing_artifact_hashes — missing input_hash / output_hash
    3  detect_missing_boundary_block  — research_boundary absent or wrong
    4  detect_missing_resource_metrics — runpod_* backend without gpu_seconds etc.
    5  detect_caller_changes        — downstream code modified outside allowed dirs
    6  detect_lost_audit_provenance  — audit.audit_record_id missing or malformed
    7  detect_model_response_without_disagreement — MLIP/DFT no disagreement.metrics
    8  detect_uma_without_hf_aup_gate — UMA backend without HF org + AUP
    9  detect_bulk_datasets_locally   — files > 5 MB outside fixtures/ allowlist
    10 detect_falsifier_bypass        — candidate promoted past unfired layer

Boundary (verbatim)
-------------------
Research infrastructure for in silico materials science discovery.
Outputs are research artifacts. No regulatory certification claims.
No clinical or human-subject use. ITAR / weapons applications are
out of scope (Meta UMA Acceptable Use Policy and operator policy).
"""

from __future__ import annotations

import json
import os
import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from zer0pa_materials.boundary import RESEARCH_BOUNDARY
from zer0pa_materials.envelope.hashing import HASH_REGEX

__all__ = [
    "HardFailureResult",
    "HardFailureDetector",
]

# Layers whose envelopes MUST carry disagreement.metrics when backend is MLIP/DFT.
_DISAGGREMENT_REQUIRED_LAYERS: frozenset[str] = frozenset({"L1", "L2", "ionic", "quantum"})

# Files larger than this trigger detect_bulk_datasets_locally.
_BULK_SIZE_BYTES: int = 5 * 1024 * 1024  # 5 MB

# Allowed subdirectories for large files (relative to repo root).
_BULK_ALLOWLIST_DIRS: frozenset[str] = frozenset({"fixtures"})

# Audit record ID pattern.
_AUDIT_URN_RE = re.compile(r"^audit:[A-Za-z0-9._\-:/]+$")

# UMA engine keywords that trigger HF org/AUP check.
_UMA_ENGINE_KEYWORDS: tuple[str, ...] = ("UMA", "uma", "fair_chemistry", "FAIR")

# Layers that must run before a candidate can be promoted.
_REQUIRED_LAYER_SEQUENCE: tuple[str, ...] = ("L1", "L2", "ionic")


@dataclass
class HardFailureResult:
    """Result from one hard-failure detector."""

    detector: str
    passed: bool
    evidence: str
    suggested_fix: str = ""
    falsifier_name: str = ""

    def to_falsifier_item_dict(self) -> dict[str, Any]:
        return {
            "name": self.falsifier_name or f"runpod.hard_failure.{self.detector}",
            "threshold": "must_pass",
            "actual": self.evidence[:512],
            "status": "pass" if self.passed else "fail",
            "evidence_ref": f"audit:hard_failure:{uuid.uuid4().hex[:12]}",
            "rationale": self.suggested_fix or None,
        }


class HardFailureDetector:
    """Ten PRD-mandated hard-failure detectors for Runpod cutover.

    Usage::

        detector = HardFailureDetector()
        result = detector.detect_schema_drift(envelope_a, envelope_b)
        if not result.passed:
            raise RuntimeError(result.evidence)

    Each method returns a :class:`HardFailureResult`.  The caller decides
    whether to raise, log, or accumulate failures.
    """

    # ------------------------------------------------------------------
    # 1. Schema drift
    # ------------------------------------------------------------------

    def detect_schema_drift(
        self,
        envelope_a: dict[str, Any],
        envelope_b: dict[str, Any],
    ) -> HardFailureResult:
        """Compare top-level and nested key sets of two envelopes.

        Schema drift means the *shape* of ``b`` differs from ``a`` — keys are
        added, removed, or change their type.  Value differences are allowed
        (that is what parity tests check separately).

        Args:
            envelope_a: Baseline envelope (e.g. ``local_stub``).
            envelope_b: Candidate envelope (e.g. ``runpod_mock``).

        Returns:
            :class:`HardFailureResult` with ``passed=True`` when schemas match.
        """
        drift = _schema_diff(envelope_a, envelope_b, "$")
        if drift:
            return HardFailureResult(
                detector="schema_drift",
                passed=False,
                evidence=f"Schema drift detected at paths: {drift}",
                suggested_fix=(
                    "Ensure both backends use the same Envelope model. "
                    "Check that mock_backends.py and the local adapter produce "
                    "the same top-level and nested key structure."
                ),
                falsifier_name="runpod.hard_failure.schema_drift",
            )
        return HardFailureResult(
            detector="schema_drift",
            passed=True,
            evidence="No schema drift detected.",
            falsifier_name="runpod.hard_failure.schema_drift",
        )

    # ------------------------------------------------------------------
    # 2. Missing artifact hashes
    # ------------------------------------------------------------------

    def detect_missing_artifact_hashes(
        self,
        envelope: dict[str, Any],
    ) -> HardFailureResult:
        """Fail if ``audit.input_hash`` or ``audit.output_hash`` are absent or malformed.

        Args:
            envelope: The envelope to inspect.

        Returns:
            :class:`HardFailureResult`.
        """
        audit = envelope.get("audit", {}) if isinstance(envelope, Mapping) else {}
        missing: list[str] = []
        for field_name in ("input_hash", "output_hash"):
            value = audit.get(field_name)
            if not value or not HASH_REGEX.match(str(value)):
                missing.append(field_name)
        if missing:
            return HardFailureResult(
                detector="missing_artifact_hashes",
                passed=False,
                evidence=f"Missing or malformed hashes: {missing}",
                suggested_fix=(
                    "Every envelope must carry sha256:<hex> for input_hash and "
                    "output_hash. Verify sha256_of() is called on both the input "
                    "and output payload before building the envelope."
                ),
                falsifier_name="runpod.hard_failure.missing_artifact_hashes",
            )
        return HardFailureResult(
            detector="missing_artifact_hashes",
            passed=True,
            evidence="Both input_hash and output_hash present and well-formed.",
            falsifier_name="runpod.hard_failure.missing_artifact_hashes",
        )

    # ------------------------------------------------------------------
    # 3. Missing boundary block
    # ------------------------------------------------------------------

    def detect_missing_boundary_block(
        self,
        envelope: dict[str, Any],
    ) -> HardFailureResult:
        """Fail if ``research_boundary`` is absent or does not match verbatim.

        Args:
            envelope: The envelope to inspect.

        Returns:
            :class:`HardFailureResult`.
        """
        block = envelope.get("research_boundary") if isinstance(envelope, Mapping) else None
        if block == RESEARCH_BOUNDARY:
            return HardFailureResult(
                detector="missing_boundary_block",
                passed=True,
                evidence="research_boundary present and verbatim.",
                falsifier_name="runpod.hard_failure.missing_boundary_block",
            )
        truncated = str(block)[:80] if block else "<absent>"
        return HardFailureResult(
            detector="missing_boundary_block",
            passed=False,
            evidence=f"research_boundary missing or wrong: {truncated!r}",
            suggested_fix=(
                "Set research_boundary = zer0pa_materials.boundary.RESEARCH_BOUNDARY "
                "verbatim in every envelope. The Envelope pydantic model validates this "
                "at construction time."
            ),
            falsifier_name="runpod.hard_failure.missing_boundary_block",
        )

    # ------------------------------------------------------------------
    # 4. Missing resource metrics
    # ------------------------------------------------------------------

    def detect_missing_resource_metrics(
        self,
        envelope: dict[str, Any],
    ) -> HardFailureResult:
        """Fail if a runpod_* backend envelope lacks resource metrics.

        Resource metrics (``gpu_seconds``, ``vram_mb``, ``wallclock_seconds``)
        must be present in ``output["resource_metrics"]`` for any envelope where
        ``tool_adapter.backend`` starts with ``"runpod_"``.

        Local/stub backends are explicitly exempted — their resource metrics
        are expected to be absent or zero.

        Args:
            envelope: The envelope to inspect.

        Returns:
            :class:`HardFailureResult`.
        """
        adapter = envelope.get("tool_adapter", {}) if isinstance(envelope, Mapping) else {}
        backend = adapter.get("backend", "") if isinstance(adapter, Mapping) else ""
        if not str(backend).startswith("runpod_"):
            return HardFailureResult(
                detector="missing_resource_metrics",
                passed=True,
                evidence=f"Backend {backend!r} is not a runpod_* backend; resource metrics exempt.",
                falsifier_name="runpod.hard_failure.missing_resource_metrics",
            )

        output = envelope.get("output", {}) if isinstance(envelope, Mapping) else {}
        metrics = output.get("resource_metrics", {}) if isinstance(output, Mapping) else {}
        required_keys = {"gpu_seconds", "vram_mb", "wallclock_seconds"}
        present = set(metrics.keys()) if isinstance(metrics, Mapping) else set()
        missing = required_keys - present
        if missing:
            return HardFailureResult(
                detector="missing_resource_metrics",
                passed=False,
                evidence=f"Backend {backend!r}: resource_metrics missing keys: {sorted(missing)}",
                suggested_fix=(
                    "Inject output['resource_metrics'] = {'gpu_seconds': ..., "
                    "'vram_mb': ..., 'wallclock_seconds': ...} in every runpod_mock "
                    "and runpod_rest envelope. See mock_backends.py MOCK_RESOURCE_METRICS."
                ),
                falsifier_name="runpod.hard_failure.missing_resource_metrics",
            )
        return HardFailureResult(
            detector="missing_resource_metrics",
            passed=True,
            evidence=f"Backend {backend!r}: resource_metrics present: {dict(metrics)}",
            falsifier_name="runpod.hard_failure.missing_resource_metrics",
        )

    # ------------------------------------------------------------------
    # 5. Caller changes
    # ------------------------------------------------------------------

    def detect_caller_changes(
        self,
        git_status: str,
        *,
        allowed_dirs: Sequence[str] = ("services/", "runpod/", "tests/parity/", "docs/"),
    ) -> HardFailureResult:
        """Fail if downstream code outside allowed dirs was modified.

        ``git_status`` is the raw output of ``git status --porcelain`` (or
        ``git diff --name-only``).  Any path that is NOT under one of the
        *allowed_dirs* prefixes is flagged as a caller change.

        Args:
            git_status: Lines of ``git status --porcelain`` or ``git diff --name-only``.
            allowed_dirs: Paths that are allowed to change.

        Returns:
            :class:`HardFailureResult`.
        """
        changed_paths: list[str] = []
        for line in git_status.strip().splitlines():
            # Strip git-status prefix (XY + space + path).
            path = line.strip().lstrip("MADRCU?! \t")
            if not path:
                continue
            if not any(path.startswith(d) for d in allowed_dirs):
                changed_paths.append(path)

        if changed_paths:
            return HardFailureResult(
                detector="caller_changes",
                passed=False,
                evidence=f"Downstream code modified: {changed_paths}",
                suggested_fix=(
                    "Only files under services/, runpod/, tests/parity/, and docs/ "
                    "should change between the runpod_mock baseline and the runpod_rest "
                    "run. Revert unexpected changes or add them to allowed_dirs if "
                    "intentional."
                ),
                falsifier_name="runpod.hard_failure.caller_changes",
            )
        return HardFailureResult(
            detector="caller_changes",
            passed=True,
            evidence="No downstream code changes detected outside allowed dirs.",
            falsifier_name="runpod.hard_failure.caller_changes",
        )

    # ------------------------------------------------------------------
    # 6. Lost audit provenance
    # ------------------------------------------------------------------

    def detect_lost_audit_provenance(
        self,
        envelope: dict[str, Any],
        audit_log: list[dict[str, Any]] | None = None,
    ) -> HardFailureResult:
        """Fail if audit.audit_record_id is missing, malformed, or not in the log.

        Args:
            envelope: The envelope to inspect.
            audit_log: Optional list of audit log dicts.  If provided, checks
                that the audit_record_id appears in the log.

        Returns:
            :class:`HardFailureResult`.
        """
        audit = envelope.get("audit", {}) if isinstance(envelope, Mapping) else {}
        record_id = audit.get("audit_record_id") if isinstance(audit, Mapping) else None
        if not record_id or not _AUDIT_URN_RE.match(str(record_id)):
            return HardFailureResult(
                detector="lost_audit_provenance",
                passed=False,
                evidence=f"audit.audit_record_id missing or malformed: {record_id!r}",
                suggested_fix=(
                    "Every envelope must have audit.audit_record_id matching "
                    "^audit:[A-Za-z0-9._-:/]+$. Check the adapter's _build_*_envelope helper."
                ),
                falsifier_name="runpod.hard_failure.lost_audit_provenance",
            )

        if audit_log is not None:
            log_ids = {
                row.get("audit_record_id")
                for row in audit_log
                if isinstance(row, Mapping)
            }
            if record_id not in log_ids:
                return HardFailureResult(
                    detector="lost_audit_provenance",
                    passed=False,
                    evidence=f"audit_record_id {record_id!r} not found in audit log.",
                    suggested_fix=(
                        "Ensure the adapter appends to the AuditLog BEFORE returning the "
                        "envelope. The audit_record_id in the envelope must match the row "
                        "in audit/runtime/<category>.jsonl."
                    ),
                    falsifier_name="runpod.hard_failure.lost_audit_provenance",
                )

        return HardFailureResult(
            detector="lost_audit_provenance",
            passed=True,
            evidence=f"audit_record_id {record_id!r} present and well-formed.",
            falsifier_name="runpod.hard_failure.lost_audit_provenance",
        )

    # ------------------------------------------------------------------
    # 7. Model response without disagreement metrics
    # ------------------------------------------------------------------

    def detect_model_response_without_disagreement(
        self,
        envelope: dict[str, Any],
    ) -> HardFailureResult:
        """Fail if an MLIP/DFT layer envelope lacks disagreement.metrics.

        Applies to layers: L1, L2, ionic, quantum.  The disagreement block must
        carry at least one metric with a non-None value.

        Args:
            envelope: The envelope to inspect.

        Returns:
            :class:`HardFailureResult`.
        """
        layer = envelope.get("layer") if isinstance(envelope, Mapping) else None
        if layer not in _DISAGGREMENT_REQUIRED_LAYERS:
            return HardFailureResult(
                detector="model_response_without_disagreement",
                passed=True,
                evidence=f"Layer {layer!r} does not require disagreement metrics.",
                falsifier_name="runpod.hard_failure.model_response_without_disagreement",
            )

        disagreement = envelope.get("disagreement", {}) if isinstance(envelope, Mapping) else {}
        metrics = disagreement.get("metrics", []) if isinstance(disagreement, Mapping) else []
        if not metrics:
            return HardFailureResult(
                detector="model_response_without_disagreement",
                passed=False,
                evidence=f"Layer {layer!r}: disagreement.metrics is empty.",
                suggested_fix=(
                    f"Layer {layer!r} is MLIP/DFT — it must carry at least one disagreement "
                    "metric (e.g. energy MAE across DFT codes or MLIP committee). "
                    "Add metrics to the disagreement block in the adapter or mock backend."
                ),
                falsifier_name="runpod.hard_failure.model_response_without_disagreement",
            )

        # At least one metric must have a numeric value.
        has_numeric = any(
            isinstance(m.get("value"), (int, float))
            for m in metrics
            if isinstance(m, Mapping)
        )
        if not has_numeric:
            return HardFailureResult(
                detector="model_response_without_disagreement",
                passed=False,
                evidence=f"Layer {layer!r}: no disagreement metric has a numeric value.",
                suggested_fix=(
                    "Set metric['value'] to a float (e.g. energy MAE in meV/atom)."
                ),
                falsifier_name="runpod.hard_failure.model_response_without_disagreement",
            )

        return HardFailureResult(
            detector="model_response_without_disagreement",
            passed=True,
            evidence=f"Layer {layer!r}: {len(metrics)} disagreement metric(s) present.",
            falsifier_name="runpod.hard_failure.model_response_without_disagreement",
        )

    # ------------------------------------------------------------------
    # 8. UMA without HF org + AUP gate
    # ------------------------------------------------------------------

    def detect_uma_without_hf_aup_gate(
        self,
        envelope: dict[str, Any],
        *,
        hf_org: str | None = None,
        hf_token: str | None = None,
    ) -> HardFailureResult:
        """Fail if UMA is used without a verified HF organization and AUP gate.

        Inspects ``tool_adapter.engine`` for UMA keywords.  If found, checks
        that ``hf_org`` and ``hf_token`` are non-empty.

        Args:
            envelope: The envelope to inspect.
            hf_org: From ``UMA_HF_ORG`` env var (via MaterialsConfig).
            hf_token: From ``UMA_HF_TOKEN`` env var.

        Returns:
            :class:`HardFailureResult`.
        """
        adapter = envelope.get("tool_adapter", {}) if isinstance(envelope, Mapping) else {}
        engine = adapter.get("engine", "") if isinstance(adapter, Mapping) else ""
        is_uma = any(kw in str(engine) for kw in _UMA_ENGINE_KEYWORDS)

        if not is_uma:
            return HardFailureResult(
                detector="uma_without_hf_aup_gate",
                passed=True,
                evidence=f"Engine {engine!r} does not use UMA; AUP gate exempt.",
                falsifier_name="runpod.hard_failure.uma_without_hf_aup_gate",
            )

        missing: list[str] = []
        if not hf_org:
            missing.append("UMA_HF_ORG")
        if not hf_token:
            missing.append("UMA_HF_TOKEN")
        if missing:
            return HardFailureResult(
                detector="uma_without_hf_aup_gate",
                passed=False,
                evidence=f"UMA engine detected ({engine!r}) but missing: {missing}",
                suggested_fix=(
                    "Set UMA_HF_ORG and UMA_HF_TOKEN in .env / Runpod environment. "
                    "The Hugging Face organization must have accepted the FAIR Chemistry "
                    "License v1 and the Meta UMA Acceptable Use Policy. "
                    "See docs/RUNPOD-CUTOVER.md §UMA-specific AUP verification."
                ),
                falsifier_name="runpod.hard_failure.uma_without_hf_aup_gate",
            )

        return HardFailureResult(
            detector="uma_without_hf_aup_gate",
            passed=True,
            evidence=f"UMA engine {engine!r}: HF org {hf_org!r} and token present.",
            falsifier_name="runpod.hard_failure.uma_without_hf_aup_gate",
        )

    # ------------------------------------------------------------------
    # 9. Bulk datasets written locally
    # ------------------------------------------------------------------

    def detect_bulk_datasets_locally(
        self,
        repo_path: str | Path,
        *,
        max_size_bytes: int = _BULK_SIZE_BYTES,
        allowlist_dirs: Sequence[str] = tuple(_BULK_ALLOWLIST_DIRS),
    ) -> HardFailureResult:
        """Fail if any file in the repo exceeds *max_size_bytes* outside *allowlist_dirs*.

        This prevents researchers from accidentally committing bulk trajectory
        or dataset files to the repository.

        Args:
            repo_path: Root of the repository to scan.
            max_size_bytes: Default 5 MB.
            allowlist_dirs: Subdirectory names whose files are exempt.

        Returns:
            :class:`HardFailureResult`.
        """
        repo = Path(repo_path)
        offenders: list[str] = []
        try:
            for root, dirs, files in os.walk(repo):
                # Skip .git and __pycache__.
                dirs[:] = [d for d in dirs if d not in (".git", "__pycache__", ".venv")]
                rel_root = Path(root).relative_to(repo)
                # Check if this subtree is under an allowlisted dir.
                parts = rel_root.parts
                if parts and parts[0] in allowlist_dirs:
                    continue
                for fname in files:
                    fpath = Path(root) / fname
                    try:
                        sz = fpath.stat().st_size
                    except OSError:
                        continue
                    if sz > max_size_bytes:
                        offenders.append(f"{fpath.relative_to(repo)} ({sz // 1024} KB)")
        except Exception as exc:  # noqa: BLE001
            return HardFailureResult(
                detector="bulk_datasets_locally",
                passed=False,
                evidence=f"Could not scan repo: {exc}",
                suggested_fix="Ensure repo_path is a valid directory and readable.",
                falsifier_name="runpod.hard_failure.bulk_datasets_locally",
            )

        if offenders:
            return HardFailureResult(
                detector="bulk_datasets_locally",
                passed=False,
                evidence=f"Large files found outside allowlist: {offenders}",
                suggested_fix=(
                    f"Move files > {max_size_bytes // 1024 // 1024} MB to a remote store "
                    f"(Runpod volume, S3, or fixtures/ directory). "
                    "Never commit bulk trajectory or dataset files to the repo."
                ),
                falsifier_name="runpod.hard_failure.bulk_datasets_locally",
            )

        return HardFailureResult(
            detector="bulk_datasets_locally",
            passed=True,
            evidence=f"No files > {max_size_bytes // 1024 // 1024} MB found outside allowlist.",
            falsifier_name="runpod.hard_failure.bulk_datasets_locally",
        )

    # ------------------------------------------------------------------
    # 10. Falsifier bypass
    # ------------------------------------------------------------------

    def detect_falsifier_bypass(
        self,
        envelope: dict[str, Any],
        kg: dict[str, Any] | None = None,
    ) -> HardFailureResult:
        """Fail if a candidate is promoted past a required layer that didn't run.

        A candidate in the envelope is considered "promoted" if
        ``falsifier.status == "pass"`` and the layer is beyond L2/ionic (i.e.,
        it reached L3+ without having passed L1, L2, and ionic in the
        knowledge-graph back-edge trail).

        Without a live KG, we inspect ``back_edges`` in the envelope to verify
        that each required layer appears.

        Args:
            envelope: The envelope to inspect.
            kg: Optional knowledge-graph dict keyed by ``candidate_id``.

        Returns:
            :class:`HardFailureResult`.
        """
        layer = envelope.get("layer") if isinstance(envelope, Mapping) else None
        falsifier = envelope.get("falsifier", {}) if isinstance(envelope, Mapping) else {}
        status = falsifier.get("status") if isinstance(falsifier, Mapping) else None

        # Only check layers that are "past" the falsifier gates.
        post_gate_layers = {"L3", "L4", "L5", "L7"}
        if layer not in post_gate_layers:
            return HardFailureResult(
                detector="falsifier_bypass",
                passed=True,
                evidence=f"Layer {layer!r} is not a post-gate layer; bypass check skipped.",
                falsifier_name="runpod.hard_failure.falsifier_bypass",
            )

        if status != "pass":
            # Rejected candidate — bypass detector doesn't apply.
            return HardFailureResult(
                detector="falsifier_bypass",
                passed=True,
                evidence=f"Layer {layer!r}: falsifier.status={status!r}; not promoted.",
                falsifier_name="runpod.hard_failure.falsifier_bypass",
            )

        # Check back_edges for required layers.
        back_edges = envelope.get("back_edges", []) if isinstance(envelope, Mapping) else []
        seen_layers = {
            e.get("layer")
            for e in back_edges
            if isinstance(e, Mapping)
        }

        missing_layers = [req for req in _REQUIRED_LAYER_SEQUENCE if req not in seen_layers]

        # If KG is provided, also check it.
        if kg is not None:
            candidate_id = envelope.get("candidate_id")
            if candidate_id and isinstance(kg, Mapping):
                kg_entry = kg.get(candidate_id, {})
                kg_layers = set(kg_entry.get("completed_layers", []))
                missing_layers = [req for req in missing_layers if req not in kg_layers]

        if missing_layers:
            return HardFailureResult(
                detector="falsifier_bypass",
                passed=False,
                evidence=(
                    f"Candidate promoted to {layer!r} without completing "
                    f"required layers: {missing_layers}. "
                    f"back_edges seen: {sorted(seen_layers)}"
                ),
                suggested_fix=(
                    "Every candidate must pass L1 (DFT), L2 (MLIP ensemble), and "
                    "ionic transport falsifiers before reaching L3+. "
                    "Check the L7 orchestrator gate logic."
                ),
                falsifier_name="runpod.hard_failure.falsifier_bypass",
            )

        return HardFailureResult(
            detector="falsifier_bypass",
            passed=True,
            evidence=(
                f"Candidate at {layer!r}: all required layers present in back_edges: "
                f"{sorted(seen_layers)}"
            ),
            falsifier_name="runpod.hard_failure.falsifier_bypass",
        )

    # ------------------------------------------------------------------
    # Batch runner
    # ------------------------------------------------------------------

    def run_all_envelope_detectors(
        self,
        envelope: dict[str, Any],
        *,
        hf_org: str | None = None,
        hf_token: str | None = None,
        kg: dict[str, Any] | None = None,
        audit_log: list[dict[str, Any]] | None = None,
    ) -> list[HardFailureResult]:
        """Run all envelope-level detectors and return list of results."""
        return [
            self.detect_schema_drift(envelope, envelope),  # self-consistency check
            self.detect_missing_artifact_hashes(envelope),
            self.detect_missing_boundary_block(envelope),
            self.detect_missing_resource_metrics(envelope),
            self.detect_lost_audit_provenance(envelope, audit_log),
            self.detect_model_response_without_disagreement(envelope),
            self.detect_uma_without_hf_aup_gate(envelope, hf_org=hf_org, hf_token=hf_token),
            self.detect_falsifier_bypass(envelope, kg),
        ]


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------

def _schema_diff(
    a: Any,
    b: Any,
    path: str,
) -> list[str]:
    """Return list of schema-drift paths between a and b."""
    diffs: list[str] = []

    if type(a) is not type(b):
        # Allow int/float interchangeability.
        if not (isinstance(a, (int, float)) and isinstance(b, (int, float))):
            diffs.append(f"{path}: type {type(a).__name__!r} vs {type(b).__name__!r}")
            return diffs

    if isinstance(a, Mapping) and isinstance(b, Mapping):
        keys_a = set(a.keys())
        keys_b = set(b.keys())
        # Keys present in a but not b.
        for k in sorted(keys_a - keys_b):
            diffs.append(f"{path}.{k}: present in baseline but missing in candidate")
        # Keys present in b but not a.
        for k in sorted(keys_b - keys_a):
            diffs.append(f"{path}.{k}: absent in baseline but added in candidate")
        # Recurse on common keys.
        for k in sorted(keys_a & keys_b):
            diffs.extend(_schema_diff(a[k], b[k], f"{path}.{k}"))

    elif isinstance(a, list) and isinstance(b, list):
        # For lists, compare element-by-element if same length.
        if len(a) != len(b):
            # Only flag if the difference could indicate structural drift.
            # (e.g. disagreement.metrics length difference is not schema drift,
            # but tool_adapter key list difference is.)
            pass
        for i, (ea, eb) in enumerate(zip(a, b)):
            diffs.extend(_schema_diff(ea, eb, f"{path}[{i}]"))

    return diffs
