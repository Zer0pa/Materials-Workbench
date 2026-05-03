"""End-to-end test of the 16-case falsification wave (Wave 6).

Boundary
--------
Research infrastructure for in silico materials science discovery. Outputs
are research artifacts. No regulatory certification claims. No clinical or
human-subject use. ITAR / weapons applications are out of scope (Meta UMA
Acceptable Use Policy and operator policy).

The wave is adversarial. The asserts below verify:

1. Every case fires its PRD-mandated target falsifier with status="fail".
2. The audit hash chain validates after every case AND at the wave end.
3. No case fires undocumented spurious extras (allowed co-fires live in
   ``COFIRES`` in ``wave_runner.py`` and are explained there).
4. Every case writes the expected ``falsifiers.jsonl`` row and a Decision
   row to ``decisions.jsonl``.
5. Campaign state is uncorrupted: a case running after a previous case's
   failure path still works correctly (this is implicit in the run_all
   ordering — if it weren't true, later cases would observe stale state).
6. The wave-report markdown structure is renderable and complete.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from zer0pa_materials_workbench.audit.kg import MaterialsKG
from zer0pa_materials_workbench.audit.log import AuditLog
from zer0pa_materials_workbench.boundary import RESEARCH_BOUNDARY
from zer0pa_materials_workbench.falsifiers.wave_report import generate_falsification_wave_report
from zer0pa_materials_workbench.falsifiers.wave_runner import (
    COFIRES,
    DEFAULT_CASES,
    WAVE_CASE_ORDER,
    FalsificationWaveResult,
    FalsificationWaveRunner,
)

# ---------------------------------------------------------------------------
# Fixture paths
# ---------------------------------------------------------------------------


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES_ROOT = REPO_ROOT / "fixtures" / "negatives"


# ---------------------------------------------------------------------------
# Wave-level fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="class")
def wave_setup(tmp_path_factory: pytest.TempPathFactory):
    """Run the full wave once and reuse the results across the class.

    Using ``scope="class"`` saves ~16 redundant wave executions per test
    class. The wave is deterministic, so reusing the result is safe.
    """
    tmp = tmp_path_factory.mktemp("wave6")
    audit_log = AuditLog(tmp / "audit")
    kg = MaterialsKG(tmp / "kg.sqlite")
    runner = FalsificationWaveRunner(audit_log=audit_log, kg=kg)
    result = runner.run_all(FIXTURES_ROOT)
    return {
        "tmp": tmp,
        "audit_log": audit_log,
        "kg": kg,
        "runner": runner,
        "result": result,
    }


# ---------------------------------------------------------------------------
# Coverage / completeness
# ---------------------------------------------------------------------------


class TestWaveCoverage:
    """Every PRD-mandated case is present and runs."""

    def test_default_cases_count_is_16(self) -> None:
        assert len(DEFAULT_CASES) == 16, (
            f"PRD §Falsification wave mandates 15 deliberate failures plus the L3 "
            f"quarantine breach negative fixture (16 total). Got {len(DEFAULT_CASES)}."
        )

    def test_wave_case_order_matches_default_cases(self) -> None:
        assert WAVE_CASE_ORDER == tuple(c.name for c in DEFAULT_CASES)

    def test_every_case_has_either_fixture_or_synth(self) -> None:
        for case in DEFAULT_CASES:
            assert (case.fixture_dir is not None) ^ (case.synthesizer is not None), (
                f"case {case.name!r} must have exactly one of fixture_dir / synthesizer"
            )

    def test_every_named_fixture_exists(self) -> None:
        for case in DEFAULT_CASES:
            if case.fixture_dir:
                fixture_path = FIXTURES_ROOT / case.fixture_dir
                assert fixture_path.exists(), (
                    f"case {case.name!r} references missing fixture dir {fixture_path}"
                )

    def test_unique_target_falsifiers(self) -> None:
        """Each case targets a distinct falsifier name (no two cases own
        the same target). This is a discipline check: the wave's case
        list should map 1:1 to PRD-mandated gates."""
        targets = [c.target_falsifier for c in DEFAULT_CASES]
        assert len(targets) == len(set(targets)), (
            f"Duplicate target falsifiers in DEFAULT_CASES: {targets}"
        )


# ---------------------------------------------------------------------------
# End-to-end wave run
# ---------------------------------------------------------------------------


class TestFullWaveRun:
    """The 16-case wave fires every gate correctly."""

    def test_wave_runs_to_completion(self, wave_setup: dict) -> None:
        result = wave_setup["result"]
        assert isinstance(result, FalsificationWaveResult)
        assert len(result.case_results) == 16

    def test_no_runner_errors(self, wave_setup: dict) -> None:
        """No case should fail to dispatch (different from a missed gate)."""
        result = wave_setup["result"]
        errors = [
            (cr.case.name, cr.error)
            for cr in result.case_results
            if cr.error is not None
        ]
        assert not errors, f"Runner errors: {errors}"

    def test_every_case_fires_its_target(self, wave_setup: dict) -> None:
        result = wave_setup["result"]
        missed = [
            cr.case.name
            for cr in result.case_results
            if not cr.target_fired
        ]
        assert not missed, (
            "These cases failed to fire their PRD-mandated target falsifier — "
            f"these are real bugs in the layer gates: {missed}"
        )

    def test_no_undocumented_spurious_extras(self, wave_setup: dict) -> None:
        result = wave_setup["result"]
        spurious = []
        for cr in result.case_results:
            if cr.spurious_extra_count > 0:
                extras = [
                    item.name
                    for item in cr.triggered_falsifiers
                    if item.status == "fail"
                    and item.name != cr.case.target_falsifier
                    and item.name not in COFIRES.get(cr.case.name, set())
                ]
                spurious.append((cr.case.name, extras))
        assert not spurious, (
            "Cases triggered undocumented co-fires. Either the negative fixture "
            "has unintended side effects, or these belong in COFIRES with a "
            f"rationale: {spurious}"
        )

    def test_all_cases_correct_verdict(self, wave_setup: dict) -> None:
        result = wave_setup["result"]
        verdicts = {cr.case.name: cr.verdict for cr in result.case_results}
        non_correct = {n: v for n, v in verdicts.items() if v != "correct"}
        assert not non_correct, (
            f"Cases with non-'correct' verdict: {non_correct}. "
            "Each case must fire ONLY its target with status=fail and a clean "
            "audit hash chain."
        )


# ---------------------------------------------------------------------------
# Audit log persistence
# ---------------------------------------------------------------------------


class TestAuditPersistence:
    """The wave writes a falsifiers.jsonl row per fired falsifier and a
    decision row per case. The hash chain validates."""

    def test_falsifiers_jsonl_row_count_matches_triggers(
        self, wave_setup: dict
    ) -> None:
        result = wave_setup["result"]
        total_triggered = sum(
            len(cr.triggered_falsifiers) for cr in result.case_results
        )
        # Wave F5: the runner also writes one row per gate in the post-PRD
        # recompute sweep (typically 7 rows).
        sweep_rows = (
            len(result.recompute_sweep.gate_results)
            if result.recompute_sweep is not None
            else 0
        )
        # Every triggered FalsifierItem becomes a row regardless of status —
        # the runner records pass/fail items so chain has full history.
        assert (
            result.total_falsifier_rows_written == total_triggered + sweep_rows
        ), (
            f"Expected {total_triggered + sweep_rows} falsifier rows "
            f"(triggers={total_triggered}, sweep={sweep_rows}); got "
            f"{result.total_falsifier_rows_written}."
        )

    def test_one_decision_row_per_case(self, wave_setup: dict) -> None:
        result = wave_setup["result"]
        assert result.total_decision_rows_written == len(result.case_results)

    def test_falsifier_chain_validates(self, wave_setup: dict) -> None:
        log: AuditLog = wave_setup["audit_log"]
        chain = log.validate_chain("falsifiers")
        assert chain.ok, (
            f"falsifiers.jsonl chain broke: {chain.errors[:8]}"
        )

    def test_decision_chain_validates(self, wave_setup: dict) -> None:
        log: AuditLog = wave_setup["audit_log"]
        chain = log.validate_chain("decisions")
        assert chain.ok, (
            f"decisions.jsonl chain broke: {chain.errors[:8]}"
        )

    def test_chain_validates_at_wave_end(self, wave_setup: dict) -> None:
        result = wave_setup["result"]
        assert result.chain_validation_ok, (
            f"Post-wave chain validation failed: {result.chain_errors[:8]}"
        )

    def test_every_falsifier_row_carries_boundary(self, wave_setup: dict) -> None:
        log: AuditLog = wave_setup["audit_log"]
        for row in log.iter_rows("falsifiers"):
            payload = row.payload
            assert payload.get("research_boundary") == RESEARCH_BOUNDARY, (
                f"Row missing or wrong boundary: {row.event_hash}"
            )

    def test_every_decision_row_carries_boundary(self, wave_setup: dict) -> None:
        log: AuditLog = wave_setup["audit_log"]
        for row in log.iter_rows("decisions"):
            payload = row.payload
            assert payload.get("research_boundary") == RESEARCH_BOUNDARY


# ---------------------------------------------------------------------------
# KG side effects
# ---------------------------------------------------------------------------


class TestKGSideEffects:
    """The wave writes a Falsifier KG node per case (16 in total)."""

    def test_kg_falsifier_node_count(self, wave_setup: dict) -> None:
        result = wave_setup["result"]
        assert result.kg_node_count_after == len(DEFAULT_CASES), (
            f"Expected {len(DEFAULT_CASES)} Falsifier nodes in KG; "
            f"got {result.kg_node_count_after}."
        )


# ---------------------------------------------------------------------------
# Campaign state non-corruption
# ---------------------------------------------------------------------------


class TestCampaignStateUncorrupted:
    """Subsequent cases are not affected by a prior case's failure path."""

    def test_later_cases_still_run_after_earlier_failures(
        self, wave_setup: dict
    ) -> None:
        result = wave_setup["result"]
        # The cases run in WAVE_CASE_ORDER. We've asserted they all reach
        # the "correct" verdict; if any later case had been corrupted by
        # earlier state, it would have errored or missed. Re-assert
        # explicitly on the order so a future regression points to which
        # case got out of order.
        for idx, cr in enumerate(result.case_results):
            assert cr.case.name == WAVE_CASE_ORDER[idx]
            assert cr.error is None
            assert cr.target_fired

    def test_repeat_run_yields_identical_verdicts(
        self, tmp_path: Path
    ) -> None:
        """Re-run on a fresh temp dir — verdicts must match exactly. This
        proves the wave is deterministic and case order does not change
        attribution."""
        run_a_log = AuditLog(tmp_path / "a")
        run_a_kg = MaterialsKG(tmp_path / "a.sqlite")
        run_a = FalsificationWaveRunner(run_a_log, run_a_kg)
        a = run_a.run_all(FIXTURES_ROOT)

        run_b_log = AuditLog(tmp_path / "b")
        run_b_kg = MaterialsKG(tmp_path / "b.sqlite")
        run_b = FalsificationWaveRunner(run_b_log, run_b_kg)
        b = run_b.run_all(FIXTURES_ROOT)

        verdicts_a = [cr.verdict for cr in a.case_results]
        verdicts_b = [cr.verdict for cr in b.case_results]
        assert verdicts_a == verdicts_b, (
            f"Wave verdicts differ across runs: A={verdicts_a}, B={verdicts_b}"
        )


# ---------------------------------------------------------------------------
# Report rendering
# ---------------------------------------------------------------------------


class TestReportRendering:
    """The wave_report markdown is renderable and well-structured."""

    def test_report_includes_boundary_block(self, wave_setup: dict) -> None:
        result = wave_setup["result"]
        md = generate_falsification_wave_report(result)
        assert RESEARCH_BOUNDARY in md

    def test_report_includes_aggregate_table(self, wave_setup: dict) -> None:
        result = wave_setup["result"]
        md = generate_falsification_wave_report(result)
        assert "## Aggregate" in md
        assert "Cases run" in md
        assert "Fired correctly" in md

    def test_report_inverted_semantics_callout(self, wave_setup: dict) -> None:
        """The report MUST explain the inverted-semantics caveat."""
        result = wave_setup["result"]
        md = generate_falsification_wave_report(result)
        assert "inverted" in md.lower()
        assert "adversarial" in md.lower()

    def test_report_lists_every_case(self, wave_setup: dict) -> None:
        result = wave_setup["result"]
        md = generate_falsification_wave_report(result)
        for case in DEFAULT_CASES:
            assert case.name in md, f"case {case.name!r} missing from report"
            assert case.target_falsifier in md, (
                f"target falsifier {case.target_falsifier!r} for case "
                f"{case.name!r} missing from report"
            )

    def test_report_markdown_renders(self, wave_setup: dict, tmp_path: Path) -> None:
        result = wave_setup["result"]
        md = generate_falsification_wave_report(result)
        target = tmp_path / "FALSIFICATION-WAVE-REPORT.md"
        target.write_text(md, encoding="utf-8")
        # Re-read and ensure no encoding loss.
        re_read = target.read_text(encoding="utf-8")
        assert re_read == md
        assert len(md) > 1500  # header + boundary + 16-row table is bulky


# ---------------------------------------------------------------------------
# Per-case sanity (one test per PRD-mandated case to give nice failure
# attribution if a single gate regresses).
# ---------------------------------------------------------------------------


class TestPerCaseSanity:
    @pytest.mark.parametrize(
        "case_name",
        [c.name for c in DEFAULT_CASES],
        ids=[c.name for c in DEFAULT_CASES],
    )
    def test_case_fires_target(self, wave_setup: dict, case_name: str) -> None:
        result: FalsificationWaveResult = wave_setup["result"]
        cr = next(c for c in result.case_results if c.case.name == case_name)
        assert cr.error is None, f"runner error for {case_name}: {cr.error}"
        assert cr.target_fired, (
            f"case {case_name} did not fire its target "
            f"{cr.case.target_falsifier}; got triggers: "
            f"{[(it.name, it.status) for it in cr.triggered_falsifiers]}"
        )
