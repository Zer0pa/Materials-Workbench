"""Adversarial tests: ionic back-edge resolution (Wave D hardened gate 4).

Boundary
--------
Research infrastructure for in silico materials science discovery. Outputs are
research artifacts. No regulatory certification claims. No clinical or
human-subject use. ITAR / weapons applications are out of scope (Meta UMA
Acceptable Use Policy and operator policy).

Discipline
----------
The OLD ``requires_ionic_transport_service`` accepts any envelope whose
``back_edges`` list contains an entry with ``layer == "ionic"`` (or whose
``input_refs`` mention the IonicTransportService). It does NOT verify
that the back-edge's ``audit_record_id`` resolves in the live audit log.

A buggy adapter can synthesise ``back_edges = [{"layer": "ionic",
"audit_record_id": "audit:fake"}]`` with no corresponding row in
``events.jsonl``. The old gate passes; the new
``verify_ionic_service_back_edge`` resolves the back-edge and fails when
nothing matches.
"""

from __future__ import annotations

from zer0pa_materials.falsifiers.ionic_falsifiers import (
    requires_ionic_transport_service,
    verify_ionic_service_back_edge,
)


# ---------------------------------------------------------------------------
# Fixtures: envelopes claiming ionic conductivity
# ---------------------------------------------------------------------------


def _envelope_claiming_ionic_conductivity(
    *,
    sigma_S_per_cm: float = 5e-3,
    back_edges: list[dict] | None = None,
) -> dict:
    return {
        "layer": "L2",
        "candidate_id": "candidate:test/ionic-back-edge",
        "input_refs": ["service:ionic-transport-service:v1"],
        "output": {
            "nernst_einstein_conductivity_S_per_cm": sigma_S_per_cm,
        },
        "back_edges": back_edges if back_edges is not None else [],
    }


def _events_log_with(*event_payloads: dict) -> list[dict]:
    """Return an in-memory shape compatible with iter_audit_rows.

    Each entry is a dict that already looks like a payload.
    """
    return list(event_payloads)


# ---------------------------------------------------------------------------
# Test 1: forged back-edge — points at audit_record_id that does not resolve
# ---------------------------------------------------------------------------


class TestForgedIonicBackEdge:
    def _envelope(self) -> dict:
        return _envelope_claiming_ionic_conductivity(
            sigma_S_per_cm=5e-3,
            back_edges=[
                {"layer": "ionic", "audit_record_id": "audit:fake/forged"},
            ],
        )

    def test_old_gate_accepts_forged_envelope(self):
        env = self._envelope()
        # The old gate sees the IonicTransportService input_ref; that
        # alone is enough for the original "passes" verdict. This
        # documents the weakness even when both signals are present:
        # neither one resolves to a live audit row.
        item = requires_ionic_transport_service(env)
        assert item.status == "pass", (
            "old gate trusts the input_ref + ionic back-edge field; "
            "this is the weakness Wave D fixes"
        )

    def test_new_gate_fails_when_back_edge_does_not_resolve(self):
        env = self._envelope()
        # Empty audit log — no audit row matches "audit:fake/forged".
        audit_log = _events_log_with()
        item = verify_ionic_service_back_edge(env, audit_log)
        assert item.status == "fail"
        assert any(
            "audit:fake/forged" == aid
            for aid in item.actual.get("unresolved_audit_record_ids", [])
        )

    def test_new_gate_passes_when_back_edge_resolves(self):
        env = self._envelope()
        # Audit log now has the matching row, plus an adapter name that
        # marks it as ionic-layer.
        audit_log = _events_log_with(
            {
                "audit_record_id": "audit:fake/forged",
                "layer": "ionic",
                "tool_adapter": {"name": "IonicNebAdapter"},
            }
        )
        item = verify_ionic_service_back_edge(env, audit_log)
        assert item.status == "pass"


# ---------------------------------------------------------------------------
# Test 2: no back-edges at all — old gate may accept (input_refs only),
#         new gate fails
# ---------------------------------------------------------------------------


class TestNoBackEdges:
    def test_new_gate_fails_with_no_back_edges(self):
        env = _envelope_claiming_ionic_conductivity(back_edges=[])
        audit_log = _events_log_with()
        item = verify_ionic_service_back_edge(env, audit_log)
        assert item.status == "fail"


# ---------------------------------------------------------------------------
# Test 3: back-edge resolves but the row is from a non-ionic adapter
# ---------------------------------------------------------------------------


class TestNonIonicTargetAdapter:
    """Back-edge resolves but the row was produced by a non-ionic adapter.

    A buggy back-edge could point at, e.g., a phonon (L1.5) row whose
    ``layer = "L1.5"`` was repurposed as "ionic evidence". The hardened
    gate must reject this.
    """

    def test_new_gate_fails_when_target_is_not_ionic(self):
        env = _envelope_claiming_ionic_conductivity(
            back_edges=[
                {"layer": "ionic", "audit_record_id": "audit:phonon/run"},
            ]
        )
        audit_log = _events_log_with(
            {
                "audit_record_id": "audit:phonon/run",
                "layer": "L1.5",  # NOT ionic
                "tool_adapter": {"name": "Phonopy3Adapter"},
            }
        )
        item = verify_ionic_service_back_edge(env, audit_log)
        assert item.status == "fail"


# ---------------------------------------------------------------------------
# Test 4: no claim → gate is no-op (vacuous pass)
# ---------------------------------------------------------------------------


class TestNoClaimNoOp:
    def test_envelope_without_claim_passes_trivially(self):
        env = {
            "layer": "L2",
            "candidate_id": "candidate:test/no-claim",
            "input_refs": [],
            "output": {},  # no ionic_conductivity claim
            "back_edges": [],
        }
        audit_log = _events_log_with()
        item = verify_ionic_service_back_edge(env, audit_log)
        assert item.status == "pass"
