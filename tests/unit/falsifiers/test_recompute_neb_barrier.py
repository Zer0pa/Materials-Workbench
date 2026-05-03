"""Adversarial tests: NEB barrier range / Arrhenius consistency
(Wave D hardened gate 5).

Boundary
--------
Research infrastructure for in silico materials science discovery. Outputs are
research artifacts. No regulatory certification claims. No clinical or
human-subject use. ITAR / weapons applications are out of scope (Meta UMA
Acceptable Use Policy and operator policy).

Discipline
----------
The PRE-WAVE-D ionic falsifier set had no plausibility band check on the
migration barrier. An adapter could emit ``migration_barrier_eV = 5.0``
(nonsense for any battery material) and the candidate would still pass
through to L7 promotion as long as σ and the Arrhenius R² were
adapter-supplied.

The new ``neb_barrier_range_check`` enforces:

* Literature band: barrier in ``[0.05, 3.0]`` eV. Outside this it's
  almost always a NEB integrator bug.
* Arrhenius consistency: when ``sigma >= 1e-3 S/cm`` (the PRD MVP
  threshold), the implied barrier at 300 K with a typical superionic
  prefactor lives in ``[0.20, 0.45]`` eV. A claimed barrier outside
  this band, while sigma is above the threshold, is internally
  inconsistent.
"""

from __future__ import annotations

import pytest

from zer0pa_materials_workbench.falsifiers.ionic_falsifiers import (
    ARRHENIUS_BARRIER_BAND_AT_1E_3_EV,
    MAX_PLAUSIBLE_BARRIER_EV,
    MIN_PLAUSIBLE_BARRIER_EV,
    neb_barrier_range_check,
)
from zer0pa_materials_workbench.falsifiers.raw_evidence import implied_arrhenius_barrier_eV

# ---------------------------------------------------------------------------
# Old shape — there was no equivalent gate before Wave D.
#
# We document the absence: any envelope with ``output.migration_barrier_eV``
# present, regardless of value, was acceptable to the prior ionic
# falsifier set. The test below pins this fact as a regression-safety
# invariant.
# ---------------------------------------------------------------------------


def _envelope(
    barrier_eV: float | None,
    sigma_S_per_cm: float | None = None,
) -> dict:
    output: dict = {}
    if barrier_eV is not None:
        output["migration_barrier_eV"] = barrier_eV
    if sigma_S_per_cm is not None:
        output["nernst_einstein_conductivity_S_per_cm"] = sigma_S_per_cm
    return {"layer": "ionic", "output": output}


# ---------------------------------------------------------------------------
# Test 1: barrier above literature upper band
# ---------------------------------------------------------------------------


class TestBarrierAboveBand:
    def test_5eV_barrier_fails(self):
        env = _envelope(barrier_eV=5.0)
        item = neb_barrier_range_check(env)
        assert item.status == "fail"
        assert "barrier_outside_literature_band" in (item.rationale or "")
        # Pre-Wave-D: no equivalent gate; this is a brand-new check.

    def test_3eV_just_above_passes(self):
        # 3.0 is the upper bound (inclusive); 3.0 + epsilon fails.
        env = _envelope(barrier_eV=MAX_PLAUSIBLE_BARRIER_EV + 0.001)
        item = neb_barrier_range_check(env)
        assert item.status == "fail"


# ---------------------------------------------------------------------------
# Test 2: barrier below literature lower band
# ---------------------------------------------------------------------------


class TestBarrierBelowBand:
    def test_0_01eV_barrier_fails(self):
        env = _envelope(barrier_eV=0.01)
        item = neb_barrier_range_check(env)
        assert item.status == "fail"
        assert "barrier_outside_literature_band" in (item.rationale or "")

    def test_0_05eV_minimum_passes(self):
        # Exact boundary value passes (closed interval).
        env = _envelope(barrier_eV=MIN_PLAUSIBLE_BARRIER_EV)
        item = neb_barrier_range_check(env)
        # Could be pass; sigma not present so Arrhenius check skipped.
        assert item.status == "pass"


# ---------------------------------------------------------------------------
# Test 3: Arrhenius inconsistency — barrier outside the implied band
#         when sigma >= 1e-3 S/cm
# ---------------------------------------------------------------------------


class TestArrheniusInconsistent:
    """Claimed sigma=1e-3 S/cm (battery MVP) but barrier=0.6 eV.

    The implied barrier from Arrhenius at 300 K with sigma_0=1e3 S/cm is
    ~0.36 eV — well within the [0.20, 0.45] band. A claim of 0.6 eV
    while sigma=1e-3 is internally inconsistent.
    """

    def test_0_6eV_barrier_with_sigma_1e_minus_3_fails(self):
        env = _envelope(barrier_eV=0.6, sigma_S_per_cm=1e-3)
        item = neb_barrier_range_check(env)
        assert item.status == "fail"
        assert item.rationale == "arrhenius_inconsistent"
        # Evidence shows the implied barrier band and the implied value.
        actual = item.actual
        assert actual["sigma_S_per_cm"] == pytest.approx(1e-3)
        assert actual["barrier_eV"] == pytest.approx(0.6)
        assert actual["expected_band"] == list(ARRHENIUS_BARRIER_BAND_AT_1E_3_EV)
        # Implied barrier is recorded as a diagnostic.
        implied = actual.get("implied_barrier_eV_from_sigma")
        assert implied is not None
        assert 0.30 < implied < 0.40

    def test_arrhenius_helper_returns_band(self):
        # Cross-check the implied helper directly.
        implied = implied_arrhenius_barrier_eV(1e-3)
        lo, hi = ARRHENIUS_BARRIER_BAND_AT_1E_3_EV
        assert lo < implied < hi

    def test_0_15eV_barrier_with_sigma_1e_minus_3_fails(self):
        # Below the implied band, also flagged.
        env = _envelope(barrier_eV=0.15, sigma_S_per_cm=1e-3)
        item = neb_barrier_range_check(env)
        assert item.status == "fail"


# ---------------------------------------------------------------------------
# Test 4: clean barrier in the band, sigma either absent or aligned
# ---------------------------------------------------------------------------


class TestCleanBarrier:
    def test_0_25eV_barrier_alone_passes(self):
        env = _envelope(barrier_eV=0.25)
        item = neb_barrier_range_check(env)
        assert item.status == "pass"

    def test_0_30eV_barrier_with_sigma_1e_minus_3_passes(self):
        env = _envelope(barrier_eV=0.30, sigma_S_per_cm=1e-3)
        item = neb_barrier_range_check(env)
        assert item.status == "pass"

    def test_2eV_barrier_with_low_sigma_passes(self):
        # A high barrier (2 eV) with a low conductivity (1e-9 S/cm) is
        # internally consistent: a poor conductor with a real high
        # barrier. The Arrhenius check only fires for sigma >= 1e-3.
        env = _envelope(barrier_eV=2.0, sigma_S_per_cm=1e-9)
        item = neb_barrier_range_check(env)
        assert item.status == "pass"


# ---------------------------------------------------------------------------
# Test 5: missing barrier — gate is no-op
# ---------------------------------------------------------------------------


class TestNoBarrierNoOp:
    def test_no_barrier_pass_trivially(self):
        env = _envelope(barrier_eV=None)
        item = neb_barrier_range_check(env)
        assert item.status == "pass"
        assert "not triggered" in (item.rationale or "").lower()
