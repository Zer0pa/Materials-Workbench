"""L4 falsifiers (PRD §L4 falsifier gates).

PRD-mandated gates:
    cahn_hilliard_mass_drift            < 1e-3 on tiny fixture
    allen_cahn_bounds_violation         < 1e-4
    spparks_potts_energy_monotonic      T=0 energy non-increasing across dumps
    plug-swap from stub to another L4 backend changes backend, not schema
    neural_operator_advisory_gate       advisory=False requires both subgates pass
    microsim_subprocess_isolation       MICROSIM must run subprocess (GPL-3 quarantine)

Each falsifier accepts an envelope dict (wire-level, as emitted by an L4
adapter) and returns a ``FalsifierItem`` row. The ``plug_swap_schema_invariance``
falsifier accepts two envelopes (backend A, backend B).

Conventions:
    - All falsifier names start with ``l4.``.
    - ``actual`` carries the measured numeric value when available; for
      structural checks (e.g. plug-swap) ``actual`` carries a small dict.
    - Status mapping:
          pass         — gate cleared
          fail         — gate violated
          blocked      — required signal missing (cannot evaluate)
          inconclusive — reserved (currently unused at L4)
"""

from __future__ import annotations

from typing import Any

from zer0pa_materials_workbench.envelope.falsifier import FalsifierItem, FalsifierStatus

# ---------------------------------------------------------------------------
# Threshold constants (PRD §L4)
# ---------------------------------------------------------------------------

CH_MASS_DRIFT_THRESHOLD = 1e-3
AC_BOUNDS_THRESHOLD = 1e-4
NEURAL_OP_QOI_THRESHOLD = 0.10  # < 10% relative QoI error


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_output(envelope: dict[str, Any]) -> dict[str, Any]:
    out = envelope.get("output")
    if not isinstance(out, dict):
        raise ValueError(f"envelope.output is missing or not a dict; got {type(out)}")
    return out


def _get_meta(envelope: dict[str, Any], key: str = "_l4_meta") -> dict[str, Any]:
    return envelope.get(key, {}) if isinstance(envelope.get(key), dict) else {}


# ---------------------------------------------------------------------------
# l4.cahn_hilliard_mass_drift
# ---------------------------------------------------------------------------


def cahn_hilliard_mass_drift(
    envelope: dict[str, Any],
    threshold: float = CH_MASS_DRIFT_THRESHOLD,
) -> FalsifierItem:
    """Fail if Cahn-Hilliard mass drift is >= threshold (default 1e-3).

    Reads ``output.cahn_hilliard_mass_drift``. If missing, status is
    ``blocked``. The PRD-mandated threshold is 1e-3 on the tiny fixture.
    """
    try:
        output = _get_output(envelope)
    except ValueError:
        return FalsifierItem(
            name="l4.cahn_hilliard_mass_drift",
            threshold=f"< {threshold}",
            actual=None,
            status="blocked",
        )
    drift = output.get("cahn_hilliard_mass_drift")
    if drift is None:
        return FalsifierItem(
            name="l4.cahn_hilliard_mass_drift",
            threshold=f"< {threshold}",
            actual=None,
            status="blocked",
        )
    status: FalsifierStatus = "pass" if drift < threshold else "fail"
    return FalsifierItem(
        name="l4.cahn_hilliard_mass_drift",
        threshold=f"< {threshold}",
        actual=drift,
        status=status,
    )


# ---------------------------------------------------------------------------
# l4.allen_cahn_bounds_violation
# ---------------------------------------------------------------------------


def allen_cahn_bounds_violation(
    envelope: dict[str, Any],
    threshold: float = AC_BOUNDS_THRESHOLD,
) -> FalsifierItem:
    """Fail if Allen-Cahn bounds violation is >= threshold (default 1e-4).

    Reads ``output.allen_cahn_bounds_violation``.
    """
    try:
        output = _get_output(envelope)
    except ValueError:
        return FalsifierItem(
            name="l4.allen_cahn_bounds_violation",
            threshold=f"< {threshold}",
            actual=None,
            status="blocked",
        )
    bv = output.get("allen_cahn_bounds_violation")
    if bv is None:
        return FalsifierItem(
            name="l4.allen_cahn_bounds_violation",
            threshold=f"< {threshold}",
            actual=None,
            status="blocked",
        )
    status: FalsifierStatus = "pass" if bv < threshold else "fail"
    return FalsifierItem(
        name="l4.allen_cahn_bounds_violation",
        threshold=f"< {threshold}",
        actual=bv,
        status=status,
    )


# ---------------------------------------------------------------------------
# l4.spparks_potts_energy_monotonic
# ---------------------------------------------------------------------------


def spparks_potts_energy_monotonic(envelope: dict[str, Any]) -> FalsifierItem:
    """Fail if SPPARKS Potts energy is NOT non-increasing across dumps at T=0.

    Reads ``output.spparks_potts_energy_monotonic`` (bool). The envelope's
    ``_l4_meta.energies`` carries the per-dump energies for diagnostics.

    Status mapping:
        - True   -> pass
        - False  -> fail
        - None   -> blocked (not a kMC run, or no T=0 measurement available)
    """
    try:
        output = _get_output(envelope)
    except ValueError:
        return FalsifierItem(
            name="l4.spparks_potts_energy_monotonic",
            threshold="energy_non_increasing == True",
            actual=None,
            status="blocked",
        )
    monotonic = output.get("spparks_potts_energy_monotonic")
    meta = _get_meta(envelope)
    energies = meta.get("energies")
    if monotonic is None:
        return FalsifierItem(
            name="l4.spparks_potts_energy_monotonic",
            threshold="energy_non_increasing == True",
            actual=energies,
            status="blocked",
        )
    status: FalsifierStatus = "pass" if monotonic else "fail"
    return FalsifierItem(
        name="l4.spparks_potts_energy_monotonic",
        threshold="energy_non_increasing == True",
        actual=energies if energies is not None else monotonic,
        status=status,
    )


# ---------------------------------------------------------------------------
# l4.neural_operator_advisory_gate
# ---------------------------------------------------------------------------


def neural_operator_advisory_gate(
    envelope: dict[str, Any],
    qoi_threshold: float = NEURAL_OP_QOI_THRESHOLD,
) -> FalsifierItem:
    """Fail if a neural-operator envelope claims advisory=False without
    BOTH (a) beats_persistence_baseline and (b) qoi_relative_error < 10%.

    PRD §L4 (Brief #2 reframe verbatim): "Neural operator is advisory only
    until it beats persistence baseline AND has < 10% relative QoI error
    on held-out classical trajectories."

    This falsifier is the dual of the contract:
        - advisory=True               -> pass     (gate respected)
        - advisory=False AND both subgates pass  -> pass
        - advisory=False AND any subgate fails   -> FAIL (premature
                                                          advisory-off)
        - non-neural-op envelope (no neural_op_gates)  -> pass (gate not relevant)
    """
    meta = _get_meta(envelope)
    neural_gates = meta.get("neural_op_gates")
    if not isinstance(neural_gates, dict):
        # Non-neural-operator envelope; the gate is not relevant. Pass.
        return FalsifierItem(
            name="l4.neural_operator_advisory_gate",
            threshold=(
                "advisory=False requires beats_persistence AND "
                f"qoi_rel_err < {qoi_threshold}"
            ),
            actual={"adapter_name": meta.get("adapter_name")},
            status="pass",
        )

    advisory = meta.get("advisory")
    beats_persistence = neural_gates.get("beats_persistence_baseline")
    qoi_err = neural_gates.get("qoi_relative_error")
    qoi_passes = qoi_err is not None and qoi_err < qoi_threshold

    if advisory is True:
        # Gate respected — advisory=True regardless of subgate state.
        return FalsifierItem(
            name="l4.neural_operator_advisory_gate",
            threshold=(
                "advisory=False requires beats_persistence AND "
                f"qoi_rel_err < {qoi_threshold}"
            ),
            actual={
                "advisory": True,
                "beats_persistence": beats_persistence,
                "qoi_relative_error": qoi_err,
            },
            status="pass",
        )

    # advisory==False — both subgates must pass
    if beats_persistence is True and qoi_passes:
        return FalsifierItem(
            name="l4.neural_operator_advisory_gate",
            threshold=(
                "advisory=False requires beats_persistence AND "
                f"qoi_rel_err < {qoi_threshold}"
            ),
            actual={
                "advisory": False,
                "beats_persistence": True,
                "qoi_relative_error": qoi_err,
            },
            status="pass",
        )

    # advisory=False but at least one subgate failed: PREMATURE ADVISORY-OFF
    return FalsifierItem(
        name="l4.neural_operator_advisory_gate",
        threshold=(
            "advisory=False requires beats_persistence AND "
            f"qoi_rel_err < {qoi_threshold}"
        ),
        actual={
            "advisory": False,
            "beats_persistence": beats_persistence,
            "qoi_relative_error": qoi_err,
            "qoi_threshold": qoi_threshold,
        },
        status="fail",
    )


# ---------------------------------------------------------------------------
# l4.plug_swap_schema_invariance
# ---------------------------------------------------------------------------


def plug_swap_schema_invariance(
    envelope_backend_a: dict[str, Any],
    envelope_backend_b: dict[str, Any],
) -> FalsifierItem:
    """Fail if two envelopes from different L4 backends differ in schema.

    PRD §L4: "plug-swap from stub to another L4 backend changes backend,
    NOT schema."

    What counts as a schema difference (FAIL):
        - The envelopes do not have the same set of top-level keys
          (back_edges and adapter_info differences are ALLOWED at the
          tool_adapter and audit blocks because those legitimately differ
          per backend).
        - The ``output`` dicts have different sets of keys.
        - The ``layer`` literal differs.
        - The ``contract_version`` differs.

    What is ALLOWED to differ (NOT a failure):
        - Numerical values inside output / disagreement
        - tool_adapter.name / engine / backend
        - audit.audit_record_id / source_manifest_refs
        - confidence values
        - back_edges
    """
    a = envelope_backend_a
    b = envelope_backend_b

    # Strip non-schema keys (underscore-prefixed) before comparison
    a_keys = {k for k in a if not k.startswith("_")}
    b_keys = {k for k in b if not k.startswith("_")}

    diffs: list[str] = []
    if a_keys != b_keys:
        diffs.append(f"top-level keys differ: A-only={a_keys - b_keys}, B-only={b_keys - a_keys}")

    a_out = a.get("output", {}) if isinstance(a.get("output"), dict) else {}
    b_out = b.get("output", {}) if isinstance(b.get("output"), dict) else {}
    a_out_keys = set(a_out.keys())
    b_out_keys = set(b_out.keys())
    if a_out_keys != b_out_keys:
        diffs.append(
            f"output keys differ: A-only={a_out_keys - b_out_keys}, B-only={b_out_keys - a_out_keys}"
        )

    if a.get("layer") != b.get("layer"):
        diffs.append(f"layer differs: A={a.get('layer')!r} vs B={b.get('layer')!r}")

    if a.get("contract_version") != b.get("contract_version"):
        diffs.append(
            f"contract_version differs: A={a.get('contract_version')!r} vs B={b.get('contract_version')!r}"
        )

    status: FalsifierStatus = "pass" if not diffs else "fail"
    return FalsifierItem(
        name="l4.plug_swap_schema_invariance",
        threshold="L4 backends emit identical wire-level schema",
        actual={
            "diffs": diffs,
            "backend_a": (a.get("tool_adapter") or {}).get("name"),
            "backend_b": (b.get("tool_adapter") or {}).get("name"),
        },
        status=status,
    )


# ---------------------------------------------------------------------------
# l4.microsim_subprocess_isolation
# ---------------------------------------------------------------------------


def microsim_subprocess_isolation(envelope: dict[str, Any]) -> FalsifierItem:
    """Fail if a MICROSIM envelope was produced in-process (GPL-3 violation).

    PRD §L4: "MICROSIM is treated as GPL-3 subprocess/container until license
    review says otherwise."

    Looks at:
        - ``tool_adapter.engine`` for "MICROSIM"
        - ``_l4_meta.isolation_mode`` (must be "subprocess" or "container")

    Status mapping:
        - non-MICROSIM envelope                    -> pass (gate not relevant)
        - MICROSIM, isolation_mode in {subprocess, container}  -> pass
        - MICROSIM, isolation_mode in {in_process, missing}    -> fail
    """
    tool_adapter = envelope.get("tool_adapter", {})
    engine = tool_adapter.get("engine", "")
    name = tool_adapter.get("name", "")

    is_microsim = (
        "MICROSIM" in engine.upper()
        or "MICROSIM" in name.upper()
    )
    if not is_microsim:
        return FalsifierItem(
            name="l4.microsim_subprocess_isolation",
            threshold="MICROSIM runs require subprocess/container isolation",
            actual={"engine": engine, "is_microsim": False},
            status="pass",
        )

    meta = _get_meta(envelope)
    isolation_mode = meta.get("isolation_mode")
    if isolation_mode in ("subprocess", "container"):
        return FalsifierItem(
            name="l4.microsim_subprocess_isolation",
            threshold="MICROSIM runs require subprocess/container isolation",
            actual={"isolation_mode": isolation_mode, "engine": engine},
            status="pass",
        )
    return FalsifierItem(
        name="l4.microsim_subprocess_isolation",
        threshold="MICROSIM runs require subprocess/container isolation (GPL-3 quarantine)",
        actual={"isolation_mode": isolation_mode, "engine": engine},
        status="fail",
    )
