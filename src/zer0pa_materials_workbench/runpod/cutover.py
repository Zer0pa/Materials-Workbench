"""Runpod cutover orchestrator (Wave 5c).

:class:`RunpodCutover` implements the seven-step PRD-mandated cutover
procedure.  It does NOT flip any backend — it gates, documents, and records
every step with Decision rows in the audit log.

Cutover procedure (PRD §Runpod Migration):
    1. Provision Runpod machine and clone https://github.com/Zer0pa/Materials.
    2. Install GPU/Docker dependencies only on the Runpod machine.
    3. Set backend URLs and config flags.
    4. Run sentinel campaign (LLZO, Li6PS5Cl, Li-Mg-Zr-Cl, Bi2Te3).
    5. Compare schema shape, artifact manifests, hashes, audit events,
       disagreement records, and candidate IDs against runpod_mock.
    6. Confirm no downstream code changed.
    7. Promote backend from mock to real only after parity passes.

Boundary (verbatim)
-------------------
Research infrastructure for in silico materials science discovery.
Outputs are research artifacts. No regulatory certification claims.
No clinical or human-subject use. ITAR / weapons applications are
out of scope (Meta UMA Acceptable Use Policy and operator policy).
"""

from __future__ import annotations

import datetime as _dt
import json
import subprocess
import sys
import uuid
from dataclasses import dataclass, field
from typing import Any

from zer0pa_materials_workbench.boundary import RESEARCH_BOUNDARY
from zer0pa_materials_workbench.envelope.config import MaterialsConfig
from zer0pa_materials_workbench.repo_root import audit_root, phase_dir, repo_root
from zer0pa_materials_workbench.runpod.hard_failures import HardFailureDetector
from zer0pa_materials_workbench.runpod.mock_backends import (
    RUNPOD_MOCK_LAYERS,
    build_runpod_mock_envelope,
)
from zer0pa_materials_workbench.runpod.rest_client import (
    RunpodCredentialsError,
    RunpodRestClient,
)

__all__ = [
    "CutoverPrecheckReport",
    "ParityReport",
    "PromotionReport",
    "RunpodCutover",
    "SentinelCampaignReport",
]

# Sentinel seeds per PRD §Runpod Migration step 4.
SENTINEL_SEEDS: tuple[dict[str, Any], ...] = (
    {
        "name": "LLZO_cubic",
        "chemical_system": "Li-La-Zr-O",
        "target_conductivity_S_per_cm": 1e-3,
        "fixture_id": "llzo_cubic",
    },
    {
        "name": "Li6PS5Cl",
        "chemical_system": "Li-P-S-Cl",
        "target_conductivity_S_per_cm": 5e-4,
        "fixture_id": "li6ps5cl",
    },
    {
        "name": "Li_Mg_Zr_Cl_seed",
        "chemical_system": "Li-Mg-Zr-Cl",
        "target_conductivity_S_per_cm": 2e-3,
        "fixture_id": "li_mg_zr_cl_seed",
    },
    {
        "name": "Bi2Te3_thermoelectric",
        "chemical_system": "Bi-Te",
        "target_ZT": 1.0,
        "fixture_id": "bi2te3",
    },
)


@dataclass
class CutoverPrecheckReport:
    """Result of :meth:`RunpodCutover.precheck`.

    Attributes:
        passed: True only when all 7 preconditions pass.
        blockers: Config-level blockers from ``validate_for_runpod_cutover()``.
        preconditions: Dict mapping precondition name → bool.
        evidence: Human-readable evidence for each precondition.
        boundary: Verbatim boundary block.
    """

    passed: bool
    blockers: list[str]
    preconditions: dict[str, bool]
    evidence: dict[str, str]
    boundary: str = RESEARCH_BOUNDARY

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_type": "CutoverPrecheckReport",
            "boundary": self.boundary,
            "passed": self.passed,
            "blockers": self.blockers,
            "preconditions": self.preconditions,
            "evidence": self.evidence,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


@dataclass
class SentinelCampaignReport:
    """Result of :meth:`RunpodCutover.run_sentinel_campaign`.

    Each seed produces one envelope per GPU-bound layer.
    """

    seed_results: dict[str, dict[str, Any]]  # seed_name -> layer -> envelope dict
    layers_run: list[str]
    seeds_run: list[str]
    backend: str
    started_at: str
    completed_at: str
    boundary: str = RESEARCH_BOUNDARY

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_type": "SentinelCampaignReport",
            "boundary": self.boundary,
            "backend": self.backend,
            "seeds_run": self.seeds_run,
            "layers_run": self.layers_run,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "seed_results": self.seed_results,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


@dataclass
class ParityReport:
    """Result of :meth:`RunpodCutover.compare_to_mock`.

    Attributes:
        passed: True if all parity checks pass.
        schema_drifts: Layer -> list of drift paths.
        hash_mismatches: Layer -> list of mismatched hash fields.
        boundary_failures: Seeds/layers where boundary block was wrong.
        resource_metric_failures: Seeds/layers where metrics were missing.
        disagreement_failures: Seeds/layers where disagreement metrics absent.
        mock_envelope_in_rest_report: Seeds/layers where the sentinel
            report claimed ``backend="runpod_rest"`` but a cell envelope
            carried ``tool_adapter.backend == "runpod_mock"`` (or any
            non-rest label).  This is the deception the user audit caught
            in Wave F: a relabelled mock under a runpod_rest report.  Any
            non-empty list HARD-FAILS parity.
        boundary: Verbatim boundary block.
    """

    passed: bool
    schema_drifts: dict[str, list[str]]
    hash_mismatches: dict[str, list[str]]
    boundary_failures: list[str]
    resource_metric_failures: list[str]
    disagreement_failures: list[str]
    mock_envelope_in_rest_report: list[str] = field(default_factory=list)
    boundary: str = RESEARCH_BOUNDARY

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_type": "ParityReport",
            "boundary": self.boundary,
            "passed": self.passed,
            "schema_drifts": self.schema_drifts,
            "hash_mismatches": self.hash_mismatches,
            "boundary_failures": self.boundary_failures,
            "resource_metric_failures": self.resource_metric_failures,
            "disagreement_failures": self.disagreement_failures,
            "mock_envelope_in_rest_report": self.mock_envelope_in_rest_report,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


@dataclass
class PromotionReport:
    """Result of :meth:`RunpodCutover.promote_backend`.

    Attributes:
        layer: Layer that was promoted.
        from_backend: Previous backend value.
        to_backend: New backend value.
        blocked: True if promotion was blocked by an outstanding parity failure.
        reason: Why promotion was blocked (if applicable).
        decision_id: Audit decision URN.
        boundary: Verbatim boundary block.
    """

    layer: str
    from_backend: str
    to_backend: str
    blocked: bool
    reason: str
    decision_id: str
    boundary: str = RESEARCH_BOUNDARY

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_type": "PromotionReport",
            "boundary": self.boundary,
            "layer": self.layer,
            "from_backend": self.from_backend,
            "to_backend": self.to_backend,
            "blocked": self.blocked,
            "reason": self.reason,
            "decision_id": self.decision_id,
        }


class RunpodCutover:
    """Runpod cutover orchestrator.

    All methods write :class:`Decision` rows to ``decisions.jsonl`` via the
    audit log.  This class does NOT flip backends — it gates and documents the
    flip, which the operator performs manually after all gates pass.

    Args:
        config: ``MaterialsConfig`` instance.  If None, loads from env.
        audit_dir: Path to the runtime audit directory.  If None, uses
            config.runtime_paths()["audit_dir"].
    """

    def __init__(
        self,
        config: MaterialsConfig | None = None,
        audit_dir: str | None = None,
    ) -> None:
        self.config = config or MaterialsConfig()
        self._audit_dir = audit_dir
        self._detector = HardFailureDetector()
        self._decisions: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Step 1: Precheck
    # ------------------------------------------------------------------

    def precheck(self, *, fast: bool = False, persist: bool = True) -> CutoverPrecheckReport:
        """Run cutover preconditions afresh; record evidence and persist a JSONL report.

        Wave C rewrite: the prior implementation hardcoded P5/P6/P7 to
        ``True`` with the literal evidence string ``"Assumed pass"`` — a
        smoking-gun pattern this rewrite eliminates.  Each precondition
        below either runs a concrete subprocess and captures its real
        output, or records an ``unable to run: <reason>`` evidence string
        with ``passed=false``.  No precondition is allowed to claim
        ``passed=true`` without producing direct evidence.

        Preconditions:
            P1. ``RUNPOD_BASE_URL`` + ``RUNPOD_API_TOKEN`` set; if both
                are present we additionally call ``RunpodRestClient.healthz("L1")``
                and record the boolean.
            P2. UMA HF gate: ``UMA_HF_ORG`` + ``UMA_HF_TOKEN`` set AND
                ``phases/UMA-license/manifest.json`` exists with an
                ``aup_accepted_at`` field.  Wave D will produce that
                manifest; until it lands, P2 records "manifest pending".
            P3. ``MATERIALS_MODE`` is one of ``runpod_mock`` / ``runpod_rest``.
            P4. ``validate_for_runpod_cutover()`` returns no blockers
                (always True when ``MATERIALS_MODE == "runpod_mock"``).
            P5. ``pytest tests/unit/adapters`` returncode == 0.
            P6. ``pytest tests/integration`` returncode == 0.
            P7. ``pytest tests/parity`` returncode == 0.
            P8. ``pytest tests/integration/test_full_falsification_wave.py``
                returncode == 0.

        Args:
            fast: When True, skip P5–P8 (the subprocess-pytest checks).
                Operators use ``fast=True`` to verify connectivity quickly
                without waiting on the full unit/parity suite.  Default
                is False (run everything).
            persist: When True (default), append the report as a single
                JSONL row to ``audit_root() / "precheck.jsonl"``.

        Returns:
            :class:`CutoverPrecheckReport` with ``passed`` True only when
            every recorded precondition is True.
        """
        cfg = self.config
        blockers = cfg.validate_for_runpod_cutover()

        preconditions: dict[str, bool] = {}
        evidence: dict[str, str] = {}

        # ---- P1: Runpod connectivity -------------------------------------
        p1_creds_ok = bool(cfg.RUNPOD_BASE_URL and cfg.RUNPOD_API_TOKEN)
        p1_evidence_lines = [
            f"RUNPOD_BASE_URL={'set' if cfg.RUNPOD_BASE_URL else 'MISSING'}",
            f"RUNPOD_API_TOKEN={'set' if cfg.RUNPOD_API_TOKEN else 'MISSING'}",
        ]
        healthz_ok: bool | None = None
        if p1_creds_ok:
            try:
                client = RunpodRestClient(
                    base_url=cfg.RUNPOD_BASE_URL,
                    api_token=cfg.RUNPOD_API_TOKEN,
                )
                healthz_ok = client.healthz("L1")
                p1_evidence_lines.append(
                    f"healthz(L1) returncode={'2xx' if healthz_ok else 'non-2xx-or-error'}"
                )
            except RunpodCredentialsError as exc:
                healthz_ok = False
                p1_evidence_lines.append(f"client construction failed: {exc}")
            except Exception as exc:
                healthz_ok = False
                p1_evidence_lines.append(f"healthz call raised: {type(exc).__name__}: {exc}")
        else:
            p1_evidence_lines.append(
                "healthz check skipped (credentials missing — would need both env vars)."
            )

        # P1 passes when creds are present AND healthz returns 2xx; in
        # mock mode (no creds expected) we only need to record evidence
        # of *what* is missing, and P1 is False so the operator sees it.
        p1 = bool(p1_creds_ok and healthz_ok)
        preconditions["runpod_connectivity"] = p1
        evidence["runpod_connectivity"] = "; ".join(p1_evidence_lines)

        # ---- P2: UMA HF gate ---------------------------------------------
        p2_env_ok = bool(cfg.UMA_HF_ORG and cfg.UMA_HF_TOKEN)
        p2_manifest_ok, p2_manifest_evidence = _check_uma_manifest()
        p2 = p2_env_ok and p2_manifest_ok
        preconditions["uma_hf_aup_gate"] = p2
        evidence["uma_hf_aup_gate"] = (
            f"UMA_HF_ORG={'set' if cfg.UMA_HF_ORG else 'MISSING'}; "
            f"UMA_HF_TOKEN={'set' if cfg.UMA_HF_TOKEN else 'MISSING'}; "
            f"manifest: {p2_manifest_evidence}"
        )

        # ---- P3: MATERIALS_MODE acceptable -------------------------------
        p3 = cfg.MATERIALS_MODE in ("runpod_mock", "runpod_rest")
        preconditions["materials_mode_acceptable"] = p3
        evidence["materials_mode_acceptable"] = (
            f"MATERIALS_MODE={cfg.MATERIALS_MODE!r} "
            f"(must be runpod_mock or runpod_rest)"
        )

        # ---- P4: No config blockers --------------------------------------
        # In runpod_mock mode the layer-flag blockers do not apply (parity
        # tests run under runpod_mock by design).  In runpod_rest mode
        # every blocker is a hard fail.
        p4 = len(blockers) == 0 or cfg.MATERIALS_MODE == "runpod_mock"
        preconditions["no_config_blockers"] = p4
        evidence["no_config_blockers"] = (
            f"validate_for_runpod_cutover() returned {len(blockers)} blocker(s): "
            f"{blockers[:5]}{'...' if len(blockers) > 5 else ''}"
            if blockers else "validate_for_runpod_cutover() returned no blockers."
        )

        # ---- P5/P6/P7/P8: subprocess-pytest checks -----------------------
        if fast:
            for key, label in (
                ("local_stub_tests_pass", "tests/unit/adapters"),
                ("local_cpu_tests_pass", "tests/integration"),
                ("runpod_mock_tests_pass", "tests/parity"),
                ("falsification_wave_fires", "tests/integration/test_full_falsification_wave.py"),
            ):
                preconditions[key] = False
                evidence[key] = (
                    f"skipped (fast=True; precheck did not invoke pytest on {label})"
                )
        else:
            p5_ok, p5_evidence = _run_pytest_subprocess(
                ["tests/unit/adapters", "-q", "--tb=no", "-x"],
                label="tests/unit/adapters",
            )
            preconditions["local_stub_tests_pass"] = p5_ok
            evidence["local_stub_tests_pass"] = p5_evidence

            p6_ok, p6_evidence = _run_pytest_subprocess(
                ["tests/integration", "-q", "--tb=no", "-x",
                 "--ignore=tests/integration/test_full_falsification_wave.py"],
                label="tests/integration",
            )
            preconditions["local_cpu_tests_pass"] = p6_ok
            evidence["local_cpu_tests_pass"] = p6_evidence

            p7_ok, p7_evidence = _run_pytest_subprocess(
                ["tests/parity", "-q", "--tb=no", "-x"],
                label="tests/parity",
            )
            preconditions["runpod_mock_tests_pass"] = p7_ok
            evidence["runpod_mock_tests_pass"] = p7_evidence

            p8_ok, p8_evidence = _run_pytest_subprocess(
                ["tests/integration/test_full_falsification_wave.py", "-q", "--tb=no"],
                label="tests/integration/test_full_falsification_wave.py",
            )
            preconditions["falsification_wave_fires"] = p8_ok
            evidence["falsification_wave_fires"] = p8_evidence

        # ---- assemble + persist ------------------------------------------
        all_passed = all(preconditions.values())
        report = CutoverPrecheckReport(
            passed=all_passed,
            blockers=blockers,
            preconditions=preconditions,
            evidence=evidence,
        )
        self._record_decision(
            decision_id=f"decision:precheck:{uuid.uuid4().hex[:12]}",
            action="precheck",
            outcome="pass" if all_passed else "blocked",
            rationale=(
                f"Precheck (fast={fast}): "
                f"{sum(preconditions.values())}/{len(preconditions)} conditions met. "
                f"Blockers: {blockers or 'none'}"
            ),
        )
        if persist:
            try:
                _append_precheck_jsonl(report, fast=fast)
            except Exception as exc:
                # Persistence failure is not a precheck failure but it must
                # leave a trail — record it as a decision row.
                self._record_decision(
                    decision_id=f"decision:precheck_persist:{uuid.uuid4().hex[:12]}",
                    action="precheck_persist",
                    outcome="failed",
                    rationale=f"Could not write precheck.jsonl: {type(exc).__name__}: {exc}",
                )
        return report

    # ------------------------------------------------------------------
    # Step 2: Provision (stub — documents what would be done)
    # ------------------------------------------------------------------

    def provision_runpod_machine(self, spec: dict[str, Any] | None = None) -> dict[str, Any]:
        """Document the Runpod machine provisioning steps (stub).

        This method does NOT actually provision a machine.  It returns a dict
        describing the steps the operator must take manually on the Runpod
        machine.  See ``docs/RUNPOD-CUTOVER.md`` for the full runbook.

        Args:
            spec: Optional spec dict with ``gpu_type``, ``disk_gb``, etc.

        Returns:
            A dict with the provisioning steps.
        """
        s = spec or {}
        steps = [
            "1. Log in to Runpod.io and create a pod with the requested GPU spec.",
            f"   GPU type: {s.get('gpu_type', 'A100-80GB')}",
            f"   Disk: {s.get('disk_gb', 200)} GB",
            "2. SSH into the pod and clone: git clone https://github.com/Zer0pa/Materials .",
            "3. Install GPU dependencies: pip install -e '.[gpu]' (NOT on local machine).",
            "4. Copy .env.runpod to .env and set backend flags (see docs/RUNPOD-CUTOVER.md).",
            "5. Set MATERIALS_MODE=runpod_rest in the pod environment.",
            "6. Run: zer0pa-materials runpod precheck",
            "7. Run: zer0pa-materials runpod sentinel",
            "8. Run: zer0pa-materials runpod parity",
            "9. If parity passes: zer0pa-materials runpod cutover-runbook",
        ]
        result = {
            "action": "provision_runpod_machine",
            "status": "stub",
            "note": "This is a documentation stub. No machine was provisioned.",
            "steps": steps,
            "spec": s,
            "boundary": RESEARCH_BOUNDARY,
        }
        self._record_decision(
            decision_id=f"decision:provision:{uuid.uuid4().hex[:12]}",
            action="provision_runpod_machine",
            outcome="stub",
            rationale="Provisioning documented; operator must execute manually on Runpod.",
        )
        return result

    # ------------------------------------------------------------------
    # Step 3: Set backend flags
    # ------------------------------------------------------------------

    def set_backend_flags(self, flags: dict[str, str]) -> dict[str, Any]:
        """Document backend flag changes (does not write to .env).

        In production the operator sets these flags in the pod's .env file or
        as environment variables.  This method records the intent for audit.

        Args:
            flags: Dict of env-var-name → value pairs to apply.

        Returns:
            A dict summarising the flag changes.
        """
        result = {
            "action": "set_backend_flags",
            "flags_to_set": flags,
            "note": (
                "Set these env vars in .env or export them before running the sentinel. "
                "This method records intent for audit but does not write to disk."
            ),
            "boundary": RESEARCH_BOUNDARY,
        }
        self._record_decision(
            decision_id=f"decision:set_flags:{uuid.uuid4().hex[:12]}",
            action="set_backend_flags",
            outcome="recorded",
            rationale=f"Backend flags to set: {list(flags.keys())}",
        )
        return result

    # ------------------------------------------------------------------
    # Step 4: Run sentinel campaign
    # ------------------------------------------------------------------

    def run_sentinel_campaign(
        self,
        backend: str = "runpod_mock",
        seeds: tuple[dict[str, Any], ...] = SENTINEL_SEEDS,
    ) -> SentinelCampaignReport:
        """Run the sentinel campaign on all GPU-bound layers.

        Routing semantics (honest-block invariant):

        * ``backend="runpod_mock"``: every seed × layer cell is generated via
          :func:`build_runpod_mock_envelope`.  Envelopes carry
          ``tool_adapter.backend == "runpod_mock"``.

        * ``backend="runpod_rest"``: every seed × layer cell is dispatched
          through :class:`RunpodDispatcher`.  When credentials are valid the
          dispatcher invokes the real REST client and records
          ``tool_adapter.backend == "runpod_rest"``.  When credentials are
          MISSING the cell records a structured failure (NOT a mock relabelled
          as ``runpod_rest``) and a :class:`BlockedSourceManifest` is emitted
          via the dispatcher.  This is the failure the user's audit demanded.

        Args:
            backend: ``"runpod_mock"`` (default) or ``"runpod_rest"``.
            seeds: Sentinel seed dicts.

        Returns:
            :class:`SentinelCampaignReport`.
        """
        started_at = _now_iso()
        seed_results: dict[str, dict[str, Any]] = {}

        # When the operator asks for ``runpod_rest`` we route through the
        # dispatcher so credential gates and BlockedSourceManifest emission
        # match the production cutover path.  We construct the dispatcher
        # lazily (it pulls in tenacity, which lives in the [runpod] extra).
        dispatcher: Any = None
        rest_credentials_blocker: str | None = None
        if backend == "runpod_rest":
            try:
                from zer0pa_materials_workbench.runpod.dispatcher import RunpodDispatcher
                dispatcher = RunpodDispatcher(self.config)
            except Exception as exc:
                rest_credentials_blocker = (
                    f"failed to construct dispatcher: {type(exc).__name__}: {exc}"
                )
            else:
                creds_ok, missing = dispatcher.credentials_ok()
                if not creds_ok:
                    rest_credentials_blocker = (
                        "RunpodCredentialsError — required environment variables "
                        f"missing: {', '.join(missing)}.  "
                        "Honest-block: NO mock fallback under runpod_rest label."
                    )

        for seed in seeds:
            seed_name = seed["name"]
            seed_results[seed_name] = {}
            for layer in RUNPOD_MOCK_LAYERS:
                if backend == "runpod_rest":
                    # Honest-block: when creds are absent, every cell records a
                    # blocked failure.  We do NOT silently emit a mock-shaped
                    # envelope and label it runpod_rest.
                    if rest_credentials_blocker is not None:
                        seed_results[seed_name][layer] = {
                            "blocked": True,
                            "backend_requested": "runpod_rest",
                            "layer": layer,
                            "seed": seed_name,
                            "blocker": rest_credentials_blocker,
                            "remediation": (
                                "Set RUNPOD_BASE_URL and RUNPOD_API_TOKEN; "
                                "see docs/RUNPOD-CUTOVER.md."
                            ),
                        }
                        continue
                    # Credentials present: route through the dispatcher (REST call).
                    try:
                        endpoint = _layer_default_endpoint(layer)
                        rest_response = dispatcher.dispatch(
                            layer=layer,
                            endpoint=endpoint,
                            payload={**seed, "layer": layer},
                        )
                        seed_results[seed_name][layer] = rest_response
                    except Exception as exc:
                        seed_results[seed_name][layer] = {
                            "error": (
                                f"runpod_rest dispatch raised "
                                f"{type(exc).__name__}: {exc}"
                            ),
                            "layer": layer,
                            "seed": seed_name,
                            "backend_requested": "runpod_rest",
                        }
                    continue

                # backend == "runpod_mock" (or anything else not yet supported).
                input_payload = {**seed, "layer": layer, "backend": "runpod_mock"}
                try:
                    env_dict = build_runpod_mock_envelope(
                        layer=layer,
                        input_payload=input_payload,
                        output_payload=_minimal_layer_output(layer, seed),
                    )
                    seed_results[seed_name][layer] = env_dict
                except Exception as exc:
                    seed_results[seed_name][layer] = {
                        "error": str(exc),
                        "layer": layer,
                        "seed": seed_name,
                    }

        completed_at = _now_iso()
        report = SentinelCampaignReport(
            seed_results=seed_results,
            layers_run=list(RUNPOD_MOCK_LAYERS),
            seeds_run=[s["name"] for s in seeds],
            backend=backend,
            started_at=started_at,
            completed_at=completed_at,
        )

        if backend == "runpod_rest" and rest_credentials_blocker is not None:
            outcome = "blocked_no_credentials"
            rationale = (
                f"Sentinel campaign blocked at construction: {rest_credentials_blocker}. "
                "All seed × layer cells recorded the blocker; no envelopes generated."
            )
        else:
            outcome = "completed"
            rationale = (
                f"Sentinel campaign completed: {len(seeds)} seeds × "
                f"{len(RUNPOD_MOCK_LAYERS)} layers = "
                f"{len(seeds) * len(RUNPOD_MOCK_LAYERS)} cells; backend={backend}."
            )

        self._record_decision(
            decision_id=f"decision:sentinel:{uuid.uuid4().hex[:12]}",
            action="run_sentinel_campaign",
            outcome=outcome,
            rationale=rationale,
        )
        return report

    # ------------------------------------------------------------------
    # Step 5: Compare to mock
    # ------------------------------------------------------------------

    def compare_to_mock(
        self,
        sentinel_report: SentinelCampaignReport,
        mock_baseline: SentinelCampaignReport | None = None,
    ) -> ParityReport:
        """Deep-diff sentinel results against the runpod_mock baseline.

        If ``mock_baseline`` is None, re-runs the sentinel with ``runpod_mock``
        backend and uses that as the baseline.

        Args:
            sentinel_report: The runpod_rest sentinel report.
            mock_baseline: A pre-computed mock baseline report.  If None, one
                is generated automatically.

        Returns:
            :class:`ParityReport`.
        """
        if mock_baseline is None:
            mock_baseline = self.run_sentinel_campaign(backend="runpod_mock")

        schema_drifts: dict[str, list[str]] = {}
        hash_mismatches: dict[str, list[str]] = {}
        boundary_failures: list[str] = []
        resource_metric_failures: list[str] = []
        disagreement_failures: list[str] = []
        mock_in_rest_report: list[str] = []

        # Hard-reject (Wave F.4): any cell labelled ``runpod_mock`` (or any
        # non-rest backend) inside a sentinel_report whose top-level
        # ``backend`` field claims ``runpod_rest`` is the deception the user
        # audit caught.  Surface every such cell.
        sentinel_claims_rest = sentinel_report.backend == "runpod_rest"

        for seed_name, layer_envs in sentinel_report.seed_results.items():
            baseline_seed = mock_baseline.seed_results.get(seed_name, {})
            for layer, env in layer_envs.items():
                baseline_env = baseline_seed.get(layer, {})
                key = f"{seed_name}/{layer}"

                # Mock-in-rest deception check runs FIRST so the failure is
                # visible even when the cell otherwise looks fine.
                if sentinel_claims_rest and isinstance(env, dict):
                    cell_backend = env.get("tool_adapter", {}).get("backend")
                    cell_blocked = env.get("blocked") is True
                    # Honest-block cells (blocked=true) are correct; only
                    # cells that appear to be successful envelopes but
                    # carry a non-rest backend label leak the deception.
                    if (
                        not cell_blocked
                        and cell_backend is not None
                        and cell_backend != "runpod_rest"
                    ):
                        mock_in_rest_report.append(
                            f"{key}: tool_adapter.backend={cell_backend!r} "
                            f"in a runpod_rest sentinel report"
                        )

                if not isinstance(env, dict) or "error" in env:
                    schema_drifts[key] = [f"sentinel envelope error: {env.get('error', '?')}"]
                    continue

                # Schema drift.
                drift_result = self._detector.detect_schema_drift(baseline_env, env)
                if not drift_result.passed:
                    schema_drifts[key] = [drift_result.evidence]

                # Hash mismatches.
                sentinel_hashes = {
                    "input_hash": env.get("audit", {}).get("input_hash"),
                    "output_hash": env.get("audit", {}).get("output_hash"),
                }
                baseline_hashes = {
                    "input_hash": baseline_env.get("audit", {}).get("input_hash"),
                    "output_hash": baseline_env.get("audit", {}).get("output_hash"),
                }
                mm = [k for k, v in sentinel_hashes.items() if v != baseline_hashes.get(k)]
                if mm:
                    hash_mismatches[key] = mm

                # Boundary.
                bb = self._detector.detect_missing_boundary_block(env)
                if not bb.passed:
                    boundary_failures.append(key)

                # Resource metrics.
                rm = self._detector.detect_missing_resource_metrics(env)
                if not rm.passed:
                    resource_metric_failures.append(key)

                # Disagreement.
                dg = self._detector.detect_model_response_without_disagreement(env)
                if not dg.passed:
                    disagreement_failures.append(key)

        all_passed = (
            not schema_drifts
            and not hash_mismatches
            and not boundary_failures
            and not resource_metric_failures
            and not disagreement_failures
            and not mock_in_rest_report
        )

        report = ParityReport(
            passed=all_passed,
            schema_drifts=schema_drifts,
            hash_mismatches=hash_mismatches,
            boundary_failures=boundary_failures,
            resource_metric_failures=resource_metric_failures,
            disagreement_failures=disagreement_failures,
            mock_envelope_in_rest_report=mock_in_rest_report,
        )
        self._record_decision(
            decision_id=f"decision:parity:{uuid.uuid4().hex[:12]}",
            action="compare_to_mock",
            outcome="pass" if all_passed else "fail",
            rationale=(
                f"Parity: schema_drifts={len(schema_drifts)}, "
                f"hash_mismatches={len(hash_mismatches)}, "
                f"boundary_failures={len(boundary_failures)}, "
                f"resource_failures={len(resource_metric_failures)}, "
                f"disagreement_failures={len(disagreement_failures)}, "
                f"mock_in_rest_report={len(mock_in_rest_report)} "
                "(hard-fail when non-zero — Wave F.4)."
            ),
        )
        return report

    # ------------------------------------------------------------------
    # Step 7: Promote backend
    # ------------------------------------------------------------------

    def promote_backend(
        self,
        layer: str,
        from_backend: str,
        to_backend: str,
        parity_report: ParityReport | None = None,
    ) -> PromotionReport:
        """Gate the backend promotion for a single layer.

        Promotion is BLOCKED if:
        - ``parity_report`` is not None and ``parity_report.passed is False``.
        - ``to_backend`` is not ``"runpod_rest"``.
        - ``from_backend`` is not ``"runpod_mock"``.

        Args:
            layer: The layer to promote.
            from_backend: Must be ``"runpod_mock"``.
            to_backend: Must be ``"runpod_rest"``.
            parity_report: Completed parity report; if None promotion is
                pessimistically blocked.

        Returns:
            :class:`PromotionReport`.
        """
        decision_id = f"decision:promote:{uuid.uuid4().hex[:12]}"

        # Gate 1: backend transition must be mock → rest.
        if from_backend != "runpod_mock" or to_backend != "runpod_rest":
            reason = (
                f"Promotion gate: from_backend must be 'runpod_mock' and "
                f"to_backend must be 'runpod_rest'. Got {from_backend!r} → {to_backend!r}."
            )
            self._record_decision(decision_id, "promote_backend", "blocked", reason)
            return PromotionReport(
                layer=layer, from_backend=from_backend, to_backend=to_backend,
                blocked=True, reason=reason, decision_id=decision_id,
            )

        # Gate 2: parity must pass.
        if parity_report is None:
            reason = "Promotion gate: no parity report provided. Run compare_to_mock() first."
            self._record_decision(decision_id, "promote_backend", "blocked", reason)
            return PromotionReport(
                layer=layer, from_backend=from_backend, to_backend=to_backend,
                blocked=True, reason=reason, decision_id=decision_id,
            )
        if not parity_report.passed:
            failures = []
            if parity_report.schema_drifts:
                failures.append(f"schema_drifts={len(parity_report.schema_drifts)}")
            if parity_report.hash_mismatches:
                failures.append(f"hash_mismatches={len(parity_report.hash_mismatches)}")
            if parity_report.boundary_failures:
                failures.append(f"boundary_failures={len(parity_report.boundary_failures)}")
            reason = f"Promotion gate: parity FAILED. Failures: {', '.join(failures)}."
            self._record_decision(decision_id, "promote_backend", "blocked", reason)
            return PromotionReport(
                layer=layer, from_backend=from_backend, to_backend=to_backend,
                blocked=True, reason=reason, decision_id=decision_id,
            )

        reason = (
            f"Parity passed. Layer {layer!r} cleared for promotion "
            f"from {from_backend!r} to {to_backend!r}. "
            "Operator must update .env and restart the pipeline."
        )
        self._record_decision(decision_id, "promote_backend", "approved", reason)
        return PromotionReport(
            layer=layer, from_backend=from_backend, to_backend=to_backend,
            blocked=False, reason=reason, decision_id=decision_id,
        )

    # ------------------------------------------------------------------
    # Rollback
    # ------------------------------------------------------------------

    def rollback(self, checkpoint_id: str) -> dict[str, Any]:
        """Document the rollback procedure for a given checkpoint.

        This method does NOT modify any files.  It records the intent in the
        decision log and returns instructions for the operator.

        Args:
            checkpoint_id: A decision URN from a previous cutover step.

        Returns:
            A dict with rollback instructions.
        """
        decision_id = f"decision:rollback:{uuid.uuid4().hex[:12]}"
        result = {
            "action": "rollback",
            "checkpoint_id": checkpoint_id,
            "instructions": [
                "1. SSH into the Runpod pod.",
                "2. In .env: set MATERIALS_MODE=runpod_mock (or local_cpu).",
                "3. Restore all *_BACKEND flags to their pre-cutover values.",
                "4. Re-run: zer0pa-materials runpod precheck",
                "5. Notify the lead agent with the checkpoint_id.",
            ],
            "boundary": RESEARCH_BOUNDARY,
            "decision_id": decision_id,
        }
        self._record_decision(
            decision_id=decision_id,
            action="rollback",
            outcome="initiated",
            rationale=f"Rollback to checkpoint {checkpoint_id!r} requested.",
        )
        return result

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def get_decisions(self) -> list[dict[str, Any]]:
        """Return all Decision rows recorded by this orchestrator instance."""
        return list(self._decisions)

    def _record_decision(
        self,
        decision_id: str,
        action: str,
        outcome: str,
        rationale: str,
    ) -> None:
        row = {
            "decision_id": decision_id,
            "timestamp": _now_iso(),
            "action": action,
            "outcome": outcome,
            "rationale": rationale,
            "boundary": RESEARCH_BOUNDARY,
        }
        self._decisions.append(row)


def _now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat()


# Pytest subprocess timeout: 120 s matches the wave-C spec.  We expose it as
# a module constant so tests can monkey-patch it down for unit-test speed.
_PYTEST_SUBPROCESS_TIMEOUT_S: float = 120.0


def _run_pytest_subprocess(
    args: list[str],
    *,
    label: str,
    timeout_s: float | None = None,
) -> tuple[bool, str]:
    """Run ``pytest <args>`` from the repo root and return ``(passed, evidence)``.

    The evidence string contains ``returncode=<n>``, the last line of
    ``stdout`` (so the operator sees something like
    ``"3404 passed, 2 skipped"``), and a truncated ``stderr`` snippet on
    non-zero return codes.

    No exception escapes: a subprocess timeout, missing pytest binary, or
    any other ``OSError`` is converted into ``passed=False`` with concrete
    evidence describing the failure.  This is the property tested by
    ``test_precheck_executes.py``.
    """
    timeout = timeout_s if timeout_s is not None else _PYTEST_SUBPROCESS_TIMEOUT_S
    try:
        cwd = repo_root()
    except Exception as exc:
        return False, f"unable to resolve repo_root(): {type(exc).__name__}: {exc}"

    cmd = [sys.executable, "-m", "pytest", *args]
    try:
        result = subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return False, (
            f"pytest {label} timed out after {timeout}s; returncode=N/A; "
            "evidence=subprocess.TimeoutExpired"
        )
    except FileNotFoundError as exc:
        return False, f"pytest not available on PYTHONPATH: {exc}"
    except OSError as exc:
        return False, f"pytest invocation OSError: {type(exc).__name__}: {exc}"

    stdout_text = (result.stdout or b"").decode("utf-8", errors="replace")
    stderr_text = (result.stderr or b"").decode("utf-8", errors="replace")
    last_line = ""
    if stdout_text:
        for line in reversed(stdout_text.splitlines()):
            line_stripped = line.strip()
            if line_stripped:
                last_line = line_stripped
                break
    evidence = (
        f"pytest {label} returncode={result.returncode}; "
        f"last stdout line: {last_line or '<empty>'}"
    )
    if result.returncode != 0 and stderr_text:
        # Trim the stderr to the last 200 chars to keep the evidence size
        # bounded; the full output is reachable via the persisted JSONL.
        evidence += f"; stderr tail: {stderr_text.strip()[-200:]!r}"
    return (result.returncode == 0), evidence


def _check_uma_manifest() -> tuple[bool, str]:
    """Verify ``phases/UMA-license/manifest.json`` via the Wave D verifier.

    Wave F.6 hardening: this used to do a shape-only check (file exists,
    JSON parses, ``aup_accepted_at`` non-empty) — which trivially passed
    the committed *starter* manifest with placeholder values.  The user
    audit caught the deception.

    The hardened path delegates to
    :func:`zer0pa_materials_workbench.falsifiers.uma_manifest.verify_uma_manifest`
    which:

    * Schema-validates against :class:`UmaAupLicenseManifest` (rejects
      placeholder strings, missing fields, wrong literal values).
    * Recomputes the manifest hash and rejects tampering.
    * Confirms the jurisdiction is not in
      :data:`RESTRICTED_JURISDICTIONS`.
    * Confirms ``geographic_jurisdiction_verified_against_aup`` and
      ``derivative_works_ownership_acknowledged`` are both ``True``.
    * Confirms ``library_license_spdx == "MIT"`` and
      ``weights_license == "FAIR-Chemistry-License-v1"``.

    The committed starter manifest at ``phases/UMA-license/manifest.json``
    is intentionally a failing-state placeholder (per Wave D), so the
    starter MUST cause this check to fail.  Operators copy
    ``manifest.template.json`` and fill the placeholders to produce a
    passing manifest; the precheck then gives a green P2.
    """
    from zer0pa_materials_workbench.falsifiers.uma_manifest import verify_uma_manifest

    try:
        manifest_path = phase_dir("UMA-license") / "manifest.json"
    except Exception as exc:
        return False, f"phase_dir() failed: {type(exc).__name__}: {exc}"
    if not manifest_path.is_file():
        return False, (
            f"manifest at {manifest_path} not present; "
            "copy phases/UMA-license/manifest.template.json to manifest.json "
            "and fill the placeholders before enabling UMA"
        )

    item = verify_uma_manifest(manifest_path)
    passed = item.status == "pass"
    if passed:
        return True, (
            f"manifest at {manifest_path} verified by "
            f"verify_uma_manifest (status=pass, threshold={item.threshold!r})"
        )

    # Surface the concrete failure reason — the verifier's rationale plus
    # the actual fields it inspected — so the operator can pinpoint the gap.
    return False, (
        f"verify_uma_manifest({manifest_path}) returned "
        f"status={item.status!r}; rationale={item.rationale!r}"
    )


def _append_precheck_jsonl(report: CutoverPrecheckReport, *, fast: bool) -> None:
    """Append one line to ``audit_root() / precheck.jsonl`` describing this run."""
    target = audit_root() / "precheck.jsonl"
    target.parent.mkdir(parents=True, exist_ok=True)
    row: dict[str, Any] = {
        "report_type": "CutoverPrecheckReport",
        "boundary": RESEARCH_BOUNDARY,
        "recorded_at": _now_iso(),
        "fast": fast,
        "passed": report.passed,
        "blockers": report.blockers,
        "preconditions": report.preconditions,
        "evidence": report.evidence,
    }
    with target.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, sort_keys=True) + "\n")


def _layer_default_endpoint(layer: str) -> str:
    """Default endpoint per layer for the sentinel campaign's REST routing.

    The mapping mirrors the per-layer FastAPI service surfaces.  These are
    the canonical "smoke" endpoints — production callers can override.
    """
    return {
        "L1": "dft/jobs",
        "L2": "predict",
        "ionic": "neb",
        "L1.5": "phonopy-harmonic",
        "L3": "equilibrium",
        "L4": "runs",
        "L5": "continuum-runs",
        "L6": "generate",
        "quantum": "vqe/jobs",
        "L7": "campaigns",
    }.get(layer, "smoke")


def _minimal_layer_output(layer: str, seed: dict[str, Any]) -> dict[str, Any]:
    """Return a minimal output payload for the given layer and seed."""
    base = {"seed_name": seed.get("name", "unknown"), "layer": layer}
    layer_specific: dict[str, dict[str, Any]] = {
        "L6": {"novelty_status": "pending", "cif_valid": True, "generator": "MatterGen/runpod_mock"},
        "L1": {"energy_per_atom_eV": -6.12, "bandgap_eV": 3.84, "converged": True},
        "quantum": {"ground_state_energy_Ha": -1.8, "vqe_iterations": 250, "converged": True},
        "L2": {"energy_per_atom_eV": -6.10, "routing_decision": "promote", "committee_size": 3},
        "ionic": {"neb_barrier_eV": 0.22, "sigma_S_per_cm": 8.4e-4, "promotion_decision": "promote"},
        "L1.5": {"ZT_300K": 0.82, "kappa_L_W_per_mK": 1.4, "phonon_stable": True},
        "L3": {"phase_boundary_K": 1050.0, "activity_Li": 0.92, "fit_converged": True},
        "L4": {"phase_field_converged": True, "grain_size_um": 3.2, "porosity": 0.02},
        "L5": {"von_mises_stress_MPa": 148.0, "displacement_max_um": 0.34, "converged": True},
    }
    return {**base, **layer_specific.get(layer, {})}
