"""PhaseForgePlus MLIP→CALPHAD prior adapter (PRD §L3, Brief #2 Gap C).

PhaseForgePlus (2025) is an open-source MLIP-to-CALPHAD pipeline that
bridges machine-learning interatomic potentials into CALPHAD parameter
fitting. PRD §L3 declares it the gated prior for ESPEI's MCMC: DFT/MLIP
energies → PhaseForgePlus prior → ESPEI posterior → pycalphad equilibrium.

Repository: ``dogusariturk/PhaseForgePlus``
Brief #1/#2: A/MIT license claimed. **License must be verified before
authority use** (PRD §Open Questions For Overnight Executor #1).

Default posture
---------------

Per PRD: "PhaseForgePlus/PhaseForge maturity and license must be verified
before authority use." Until the lead agent confirms the live MIT license,
the GitHub repo's current activity, and pinned a release tag, this adapter
emits a :class:`BlockedSourceManifest` with ``blocker_reason="license_unverified"``
and falls back to a deterministic synthetic prior.

The synthetic prior is shaped so ESPEI's MCMC consumes it as a Gaussian
on the CALPHAD parameter vector. The mean is centred near a Cu-Mg-style
binary excess interaction; the covariance is loose so the synthetic prior
does not overconstrain the posterior.

Once license is verified
------------------------

Operator calls :meth:`enable_with_verified_license`:

>>> adapter = PhaseForgePlusMlipPriorAdapter()
>>> adapter.enable_with_verified_license(
...     license_proof_uri="https://github.com/dogusariturk/PhaseForgePlus/blob/main/LICENSE",
...     license_spdx="MIT",
...     verified_at="2026-04-30T12:00:00Z",
... )

After enabling, the adapter still emits a synthetic prior (real MLIP
backend lives behind ``L3_MLIP_PRIOR_PROVIDER=phaseforgeplus_local``);
the change is that ``blocker_reason`` no longer applies and the envelope's
``tool_adapter.backend`` becomes ``"phaseforgeplus_local_pending"``.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import struct
from typing import Any

from zer0pa_materials_workbench.adapters.l3.base import L3CalphadAdapter, L3CalphadRequest
from zer0pa_materials_workbench.audit.sources import BlockedSourceManifest
from zer0pa_materials_workbench.boundary import RESEARCH_BOUNDARY
from zer0pa_materials_workbench.envelope.hashing import sha256_of

__all__ = [
    "PhaseForgePlusMlipPriorAdapter",
]


# Synthetic prior shape — Gaussian on a 4-parameter CALPHAD vector.
# The four parameters mirror the names in espei_fit._SYNTHETIC_PARAM_NAMES so
# the prior and posterior are commensurable. The covariance is intentionally
# wider than the posterior covariance so the prior is "weak" relative to data.
_SYNTHETIC_PRIOR_MEAN: list[float] = [-35000.0, 5.0, -10000.0, 0.0]
_SYNTHETIC_PRIOR_COV_DIAG: list[float] = [
    1000.0**2,
    2.0**2,
    2000.0**2,
    1.0**2,
]


def _hash_seeded_prior(seed_hash: str) -> tuple[list[float], list[float]]:
    """Generate a deterministic prior from a seed hash."""
    hex_body = seed_hash.split(":", 1)[-1]
    # Small structured perturbation so different candidates get different priors,
    # but kept small relative to the variance so the prior is still weak.
    perturbations: list[float] = []
    for i in range(4):
        chunk = hex_body[i * 8 : (i + 1) * 8]
        if len(chunk) < 8:
            chunk = hashlib.sha256((seed_hash + str(i)).encode()).hexdigest()[:8]
        raw = struct.unpack(">I", bytes.fromhex(chunk))[0]
        # Map [0, 2^32) to [-1, 1] then scale by sqrt(diag) / 10 — small.
        perturb = -1.0 + (raw / (2**32)) * 2.0
        perturbations.append(perturb)
    perturbed_mean = [
        _SYNTHETIC_PRIOR_MEAN[i] + perturbations[i] * (_SYNTHETIC_PRIOR_COV_DIAG[i] ** 0.5) / 10.0
        for i in range(4)
    ]
    return perturbed_mean, list(_SYNTHETIC_PRIOR_COV_DIAG)


class PhaseForgePlusMlipPriorAdapter(L3CalphadAdapter):
    """PhaseForgePlus MLIP→CALPHAD prior adapter — DEFAULT-BLOCKED.

    The adapter is gated behind a license-verification step. Until the lead
    agent confirms the PhaseForgePlus repository's MIT license and current
    maturity (PRD §Open Questions For Overnight Executor #1), the adapter
    emits a :class:`BlockedSourceManifest` and serves a synthetic prior so
    downstream ESPEI/pycalphad still has a numerically-valid input.

    Attributes
    ----------
    enabled:
        ``False`` until :meth:`enable_with_verified_license` succeeds.
    license_proof_uri:
        URI of the license proof (set via :meth:`enable_with_verified_license`).
    license_spdx:
        SPDX expression for the verified license (e.g. "MIT").
    verified_at:
        ISO-8601 timestamp of when verification occurred.
    """

    NAME = "PhaseForgePlusMlipPriorAdapter"
    VERSION = "0.1.0"
    REPO = "dogusariturk/PhaseForgePlus"

    def __init__(self) -> None:
        self.enabled: bool = False
        self.license_proof_uri: str | None = None
        self.license_spdx: str | None = None
        self.verified_at: str | None = None

    # -------------------------------------------------- gating

    def enable_with_verified_license(
        self,
        license_proof_uri: str,
        license_spdx: str,
        verified_at: str | None = None,
    ) -> None:
        """Enable the adapter after live license verification (PRD §L3).

        Parameters
        ----------
        license_proof_uri:
            URI of the license proof (e.g., the LICENSE file in the live repo).
        license_spdx:
            SPDX expression of the verified license, e.g. ``"MIT"``.
        verified_at:
            ISO-8601 UTC timestamp of when verification occurred. Defaults
            to ``now()`` if omitted.
        """
        if not license_proof_uri.strip():
            raise ValueError("license_proof_uri must be a non-empty string")
        if not license_spdx.strip():
            raise ValueError("license_spdx must be a non-empty string")
        if verified_at is None:
            verified_at = _dt.datetime.now(tz=_dt.timezone.utc).isoformat(
                timespec="microseconds"
            )
        self.license_proof_uri = license_proof_uri
        self.license_spdx = license_spdx
        self.verified_at = verified_at
        self.enabled = True

    # -------------------------------------------------- run

    def run(
        self,
        request: L3CalphadRequest,
    ) -> dict[str, Any]:
        """Run the MLIP-prior adapter and return a wire-level envelope.

        In the default (blocked) state, the envelope's ``tool_adapter.backend``
        is ``"stub"`` and ``output.espei_diagnostics`` records that the
        adapter served a synthetic prior under license-block.
        """
        seed_hash = (request.tdb_path or request.candidate_id or request.run_id) + ":pfp"
        seed_input_hash = "sha256:" + hashlib.sha256(seed_hash.encode()).hexdigest()

        prior_mean, prior_cov_diag = _hash_seeded_prior(seed_input_hash)

        backend = "phaseforgeplus_local_pending" if self.enabled else "stub"
        engine = (
            f"phaseforgeplus-license-verified-{self.license_spdx}"
            if self.enabled
            else "phaseforgeplus-blocked-license-unverified"
        )

        # The output schema is L3CalphadOutput. We populate the
        # phase_fraction_posterior and equilibrium_phases with placeholder
        # values that match what an actual MLIP→CALPHAD prior would emit —
        # the prior is over CALPHAD parameters, not phase fractions, so we
        # encode the prior in espei_diagnostics under "prior_mean"/"prior_cov".
        output: dict[str, Any] = {
            "tdb_ref": (
                f"file://{request.tdb_path}"
                if request.tdb_path
                else f"synthetic:prior:{seed_input_hash[:24]}"
            ),
            # No equilibrium computed at the prior step.
            "equilibrium_phases": [],
            "phase_fraction_posterior": {},
            "espei_diagnostics": {
                "ran": False,
                "reason": "prior_only_call",
                "prior_mean": prior_mean,
                "prior_cov_diag": prior_cov_diag,
                "param_names": ["L0_LIQUID", "L1_LIQUID", "L0_FCC", "L1_FCC"],
                "license_status": (
                    "verified" if self.enabled else "unverified_blocked"
                ),
                "license_spdx": self.license_spdx,
                "license_proof_uri": self.license_proof_uri,
                "verified_at": self.verified_at,
            },
            "fixture_phase_boundary_drift_K": None,
            "phase_set_jaccard_distance": None,
            "phase_fraction_js_divergence": None,
        }
        out_hash = "sha256:" + sha256_of(output).split("sha256:", 1)[1]

        envelope: dict[str, Any] = {
            "research_boundary": RESEARCH_BOUNDARY,
            "contract_version": "zer0pa.materials.layer-envelope.v1",
            "layer": "L3",
            "run_id": request.run_id,
            "candidate_id": request.candidate_id,
            "campaign_id": request.campaign_id,
            "tool_adapter": {
                "name": self.NAME,
                "version": self.VERSION,
                "backend": backend,
                "engine": engine,
            },
            "output": output,
            "confidence": {
                # Confidence is low until license is verified; even after
                # verification, prior alone is not high-confidence — only the
                # posterior is.
                "score": 0.4 if self.enabled else 0.2,
                "band": "low",
                "basis": [
                    f"backend={backend}",
                    f"license_status={'verified' if self.enabled else 'blocked'}",
                ],
            },
            "disagreement": {"metrics": []},
            "falsifier": {
                "status": "blocked" if not self.enabled else "pass",
                "items": [],
            },
            "audit": {
                "audit_record_id": f"audit:{request.run_id}/phaseforgeplus-prior",
                "input_hash": seed_input_hash,
                "output_hash": out_hash,
                "source_manifest_refs": ["src:phaseforgeplus:library"],
            },
            "rights": {
                "rights_claim_id": request.rights_claim_id,
                "reuse_scope": "tenant_only",
            },
            "back_edges": [],
            "_phaseforgeplus_meta": {
                "enabled": self.enabled,
                "repo": self.REPO,
                "license_spdx": self.license_spdx,
                "verified_at": self.verified_at,
            },
        }
        return envelope

    # -------------------------------------------------- blocked_manifests

    def blocked_manifests(self) -> list[dict[str, Any]]:
        """Return BlockedSourceManifest unless license is verified."""
        if self.enabled:
            return []
        m = BlockedSourceManifest(
            source_manifest_id="src:phaseforgeplus:library",
            attempted_locator=f"https://github.com/{self.REPO}",
            blocker_reason="license_unverified",
            blocker_detail=(
                "PhaseForgePlus license has not been live-verified. "
                "PRD §L3 + §Open Questions: 'PhaseForgePlus/PhaseForge maturity "
                "and license must be verified before authority use.' Brief #2 "
                "claims A/MIT but live verification is the lead agent's "
                "responsibility before the adapter is enabled. While blocked, "
                "the adapter serves a deterministic synthetic prior so "
                "downstream ESPEI/pycalphad still has a numerically-valid input."
            ),
            retry_strategy=(
                "Lead agent: visit https://github.com/dogusariturk/PhaseForgePlus, "
                "confirm MIT (or current) LICENSE file, pin a release tag, "
                "and call enable_with_verified_license(license_proof_uri=..., "
                "license_spdx='MIT', verified_at='<iso-utc>') on the adapter."
            ),
        )
        return [m.model_dump(mode="json")]
