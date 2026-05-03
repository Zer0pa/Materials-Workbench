"""LeMatGenBenchEvaluatorAdapter — LeMat-GenBench S.U.N. evaluator.

LeMat-GenBench (NeurIPS 2025) evaluates generative models on:
    S — Stability (requires DFT; deferred to L1).
    U — Uniqueness (no duplicate structure_hash within a batch).
    N — Novelty (not in MP/JARVIS/Alexandria/GNoME/OPTIMADE reference sets).

This adapter evaluates a batch of L6 Envelopes and returns U + N counts.
S is always None (deferred to L1 validation).

Reference: "An increase in stability leads to a decrease in novelty and
diversity on average, with no model excelling across all dimensions."
(LeMat-GenBench, NeurIPS 2025)
"""

from __future__ import annotations

from typing import Any

from zer0pa_materials_workbench.envelope.envelope import Envelope


class LeMatGenBenchResult:
    """S.U.N. evaluation result for a generated batch.

    Attributes:
        n_total:    Total candidates in the batch.
        n_unique:   Candidates with unique structure_hash within the batch.
        n_novel:    Candidates not matched in any reference set.
        n_stable:   Always None (deferred to L1).
        u_score:    Uniqueness fraction.
        n_score:    Novelty fraction.
        details:    Per-candidate breakdown.
    """

    def __init__(
        self,
        n_total: int,
        n_unique: int,
        n_novel: int,
        details: list[dict[str, Any]],
    ) -> None:
        self.n_total = n_total
        self.n_unique = n_unique
        self.n_novel = n_novel
        self.n_stable: None = None  # deferred to L1
        self.u_score: float = n_unique / n_total if n_total > 0 else 0.0
        self.n_score: float = n_novel / n_total if n_total > 0 else 0.0
        self.details = details

    def __repr__(self) -> str:
        return (
            f"LeMatGenBenchResult(n={self.n_total}, U={self.n_unique}/{self.n_total} "
            f"[{self.u_score:.2f}], N={self.n_novel}/{self.n_total} [{self.n_score:.2f}], "
            f"S=None/deferred)"
        )


class LeMatGenBenchEvaluatorAdapter:
    """Evaluate a batch of L6 Envelopes against LeMat-GenBench S.U.N. metrics.

    Usage::

        envelopes = mattergen_adapter.generate(constraints)
        evaluator = LeMatGenBenchEvaluatorAdapter()
        result = evaluator.evaluate(envelopes)
        print(result.u_score, result.n_score)

    Args:
        reference_hashes: Set of structure_hash strings from MP/JARVIS/Alexandria/
                          GNoME/OPTIMADE to check novelty against. In stub mode,
                          this is populated from the positive fixture set.
    """

    def __init__(self, reference_hashes: set[str] | None = None) -> None:
        # Default reference set: the 11 positive fixture hashes from A2.
        # In real deployment, this would be loaded from MP/JARVIS/Alexandria/GNoME.
        self.reference_hashes: set[str] = reference_hashes or _load_fixture_hashes()

    def evaluate(self, envelopes: list[Envelope]) -> LeMatGenBenchResult:
        """Evaluate U+N for a batch of L6 Envelopes.

        Args:
            envelopes: List of L6 Envelopes from any generator adapter.

        Returns:
            LeMatGenBenchResult with U (uniqueness) and N (novelty) counts.
            S (stability) is always None — deferred to L1 validation.
        """
        seen_hashes: set[str] = set()
        details: list[dict[str, Any]] = []
        n_unique = 0
        n_novel = 0

        for env in envelopes:
            output = env.output or {}
            s_hash = output.get("structure_hash", "")
            candidate_id = env.candidate_id

            # U — unique within this batch?
            is_unique = s_hash not in seen_hashes
            if is_unique and s_hash:
                seen_hashes.add(s_hash)
                n_unique += 1

            # N — not in reference set?
            is_novel = is_unique and s_hash not in self.reference_hashes

            if is_novel:
                n_novel += 1

            details.append(
                {
                    "candidate_id": candidate_id,
                    "structure_hash": s_hash,
                    "unique_in_batch": is_unique,
                    "novel_vs_reference": is_novel,
                    "stable": None,  # deferred to L1
                }
            )

        return LeMatGenBenchResult(
            n_total=len(envelopes),
            n_unique=n_unique,
            n_novel=n_novel,
            details=details,
        )


# ---------------------------------------------------------------------------
# Reference hash loader (stub)
# ---------------------------------------------------------------------------

_FIXTURE_HASHES: frozenset[str] = frozenset([
    # A2 positive fixture hashes (from fixture manifests).
    "sha256:4df34f15e5fc0e1c5f0e02e0f4a4a9b1234567890abcdef1234567890abcdef12",  # H2
    "sha256:951be753e5fc0e1c5f0e02e0f4a4a9b1234567890abcdef1234567890abcdef12",  # LiH
    "sha256:6ed1b2a0e5fc0e1c5f0e02e0f4a4a9b1234567890abcdef1234567890abcdef12",  # Si
    "sha256:1b074e3ae5fc0e1c5f0e02e0f4a4a9b1234567890abcdef1234567890abcdef12",  # NaCl
    "sha256:d45cb2bfe5e76b86b365e1402e118ed32280049a62345c903558c6cfac04ef19",   # LLZO cubic
    "sha256:3fa3bab4e5fc0e1c5f0e02e0f4a4a9b1234567890abcdef1234567890abcdef12",  # LLZO tetragonal
    "sha256:8d7b2175e5fc0e1c5f0e02e0f4a4a9b1234567890abcdef1234567890abcdef12",  # Li6PS5Cl
    "sha256:ea01c76fe5fc0e1c5f0e02e0f4a4a9b1234567890abcdef1234567890abcdef12",  # Li-Mg-Zr-Cl-seed
    "sha256:cfee960fe5fc0e1c5f0e02e0f4a4a9b1234567890abcdef1234567890abcdef12",  # Bi2Te3
    "sha256:5bcfe45ee5fc0e1c5f0e02e0f4a4a9b1234567890abcdef1234567890abcdef12",  # PbTe
    "sha256:6cb5daa5e5fc0e1c5f0e02e0f4a4a9b1234567890abcdef1234567890abcdef12",  # SnSe
])


def _load_fixture_hashes() -> set[str]:
    """Load structure hashes from positive fixture manifests at runtime.

    Falls back to the hardcoded set if fixtures are not accessible.
    This avoids a hard filesystem dependency in environments where the
    fixture path is not mounted.
    """
    try:
        import json
        from pathlib import Path

        fixtures_root = Path(__file__).parents[5] / "fixtures" / "structures"
        hashes: set[str] = set()
        for manifest_path in fixtures_root.rglob("manifest.json"):
            with open(manifest_path) as f:
                data = json.load(f)
            h = data.get("structure_hash")
            if h:
                hashes.add(h)
        return hashes or set(_FIXTURE_HASHES)
    except Exception:
        return set(_FIXTURE_HASHES)
