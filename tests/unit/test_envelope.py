"""Unit tests for the Universal Layer Envelope (PRD §Architecture Invariant)."""

from __future__ import annotations

import copy

import pytest
from pydantic import ValidationError

from zer0pa_materials.boundary import RESEARCH_BOUNDARY, BoundaryError
from zer0pa_materials.envelope import (
    AuditBlock,
    BackEdge,
    ConfidenceBlock,
    DisagreementBlock,
    DisagreementMetric,
    ENVELOPE_KEY_ORDER,
    Envelope,
    FalsifierBlock,
    FalsifierItem,
    L1QuantumVqeOutput,
    RightsBlock,
    ToolAdapter,
    sha256_of,
)


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------


def _good_audit() -> AuditBlock:
    return AuditBlock(
        audit_record_id="audit:test-001",
        input_hash=sha256_of({"x": 1}),
        output_hash=sha256_of({"y": 2}),
        source_manifest_refs=[],
    )


def _good_rights() -> RightsBlock:
    return RightsBlock(rights_claim_id="rights:test", reuse_scope="tenant_only")


def _good_tool() -> ToolAdapter:
    return ToolAdapter(
        name="StubAdapter", version="0.1.0", backend="stub", engine="StubEngine"
    )


def _build_envelope(**overrides) -> Envelope:
    base = dict(
        research_boundary=RESEARCH_BOUNDARY,
        run_id="run:test-001",
        campaign_id="campaign:test",
        candidate_id="candidate:test",
        layer="L1",
        tool_adapter=_good_tool(),
        input_refs=[],
        output={},
        confidence=ConfidenceBlock(),
        disagreement=DisagreementBlock(),
        falsifier=FalsifierBlock(),
        audit=_good_audit(),
        rights=_good_rights(),
        back_edges=[],
    )
    base.update(overrides)
    return Envelope(**base)


# ----------------------------------------------------------------------------
# Round-trip
# ----------------------------------------------------------------------------


def test_envelope_round_trip_via_canonical_dict():
    env = _build_envelope()
    d = env.canonical_dict()
    rebuilt = Envelope.model_validate(d)
    assert rebuilt.model_dump(mode="json") == env.model_dump(mode="json")


def test_envelope_round_trip_via_json():
    env = _build_envelope()
    raw = env.model_dump_json()
    rebuilt = Envelope.model_validate_json(raw)
    assert rebuilt.canonical_bytes() == env.canonical_bytes()


def test_envelope_canonical_dict_uses_specified_key_order():
    env = _build_envelope()
    d = env.canonical_dict()
    actual_order = list(d.keys())
    # The first len(ENVELOPE_KEY_ORDER) keys must match exactly.
    assert actual_order[: len(ENVELOPE_KEY_ORDER)] == list(ENVELOPE_KEY_ORDER)


def test_envelope_contract_version_literal():
    env = _build_envelope()
    assert env.contract_version == "zer0pa.materials.layer-envelope.v1"


# ----------------------------------------------------------------------------
# Boundary enforcement
# ----------------------------------------------------------------------------


def test_envelope_rejects_missing_boundary():
    with pytest.raises(ValidationError):
        _build_envelope(research_boundary="this is not the canonical block")


def test_envelope_rejects_truncated_boundary():
    truncated = RESEARCH_BOUNDARY[:-10]
    with pytest.raises(ValidationError):
        _build_envelope(research_boundary=truncated)


def test_envelope_validator_rejects_forbidden_phrase_in_output():
    """A forbidden phrase anywhere in output triggers boundary failure.

    Pydantic wraps the underlying ``BoundaryError`` into a ``ValidationError``
    at model_validate time. We assert on the wrapping ``ValidationError`` and
    on the inner message so a regression in the boundary message string is
    caught.
    """
    with pytest.raises(ValidationError) as ei:
        _build_envelope(output={"description": "FDA-approved replacement therapy"})
    assert "FDA-approved" in str(ei.value)
    assert "Boundary violation" in str(ei.value)


def test_envelope_allows_in_silico_phrase():
    """The 'in silico' allow-listed fragment must NOT trip the boundary detector."""
    env = _build_envelope(output={"description": "in silico screening of candidates"})
    assert "in silico" in env.output["description"]


def test_envelope_allows_therapeutic_candidate_phrase():
    env = _build_envelope(output={"description": "therapeutic candidate identified"})
    assert env.output["description"]


def test_envelope_directly_raises_boundary_error_when_called_via_dict_walker():
    """The module-level ``assert_boundary`` raises BoundaryError directly; only
    the pydantic validator wraps it as a ValidationError."""
    from zer0pa_materials.boundary import assert_boundary
    with pytest.raises(BoundaryError):
        assert_boundary(
            {
                "research_boundary": RESEARCH_BOUNDARY,
                "claims": "FDA-approved candidate",
            }
        )


# ----------------------------------------------------------------------------
# Hash format
# ----------------------------------------------------------------------------


def test_envelope_rejects_malformed_input_hash():
    bad_audit = {
        "audit_record_id": "audit:test-001",
        "input_hash": "not-a-sha256",
        "output_hash": sha256_of({"y": 2}),
        "source_manifest_refs": [],
    }
    with pytest.raises(ValidationError):
        _build_envelope(audit=bad_audit)


def test_envelope_rejects_malformed_output_hash():
    bad_audit = {
        "audit_record_id": "audit:test-001",
        "input_hash": sha256_of({"x": 1}),
        "output_hash": "sha256:tooshort",
        "source_manifest_refs": [],
    }
    with pytest.raises(ValidationError):
        _build_envelope(audit=bad_audit)


def test_envelope_rejects_uppercase_hex_in_hash():
    bad_audit = {
        "audit_record_id": "audit:test-001",
        "input_hash": "sha256:" + "A" * 64,
        "output_hash": sha256_of({"y": 2}),
        "source_manifest_refs": [],
    }
    with pytest.raises(ValidationError):
        _build_envelope(audit=bad_audit)


# ----------------------------------------------------------------------------
# URN ID validators
# ----------------------------------------------------------------------------


def test_envelope_rejects_run_id_without_prefix():
    with pytest.raises(ValidationError):
        _build_envelope(run_id="my-run-001")


def test_envelope_rejects_campaign_id_with_wrong_prefix():
    with pytest.raises(ValidationError):
        _build_envelope(campaign_id="run:not-a-campaign")


def test_envelope_rejects_candidate_id_empty_after_prefix():
    with pytest.raises(ValidationError):
        _build_envelope(candidate_id="candidate:")


def test_envelope_rejects_audit_record_id_with_run_prefix():
    bad_audit = AuditBlock(
        audit_record_id="audit:bad",
        input_hash=sha256_of({"x": 1}),
        output_hash=sha256_of({"y": 2}),
    )
    bad_audit_dict = bad_audit.model_dump()
    bad_audit_dict["audit_record_id"] = "run:audit-not-allowed"
    with pytest.raises(ValidationError):
        _build_envelope(audit=bad_audit_dict)


def test_envelope_rejects_rights_claim_id_with_wrong_prefix():
    bad_rights = {"rights_claim_id": "audit:wrong", "reuse_scope": "tenant_only"}
    with pytest.raises(ValidationError):
        _build_envelope(rights=bad_rights)


# ----------------------------------------------------------------------------
# Layer literal
# ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "layer",
    ["phase0", "L1", "L1.5", "ionic", "L2", "L3", "L4", "L5", "L6", "L7"],
)
def test_envelope_accepts_every_layer_literal(layer: str):
    env = _build_envelope(layer=layer)
    assert env.layer == layer


def test_envelope_rejects_unknown_layer():
    with pytest.raises(ValidationError):
        _build_envelope(layer="L42")


# ----------------------------------------------------------------------------
# Backend literal
# ----------------------------------------------------------------------------


@pytest.mark.parametrize("backend", ["stub", "local_cpu", "runpod_mock", "runpod_rest"])
def test_envelope_accepts_every_backend_literal(backend: str):
    tool = {"name": "X", "version": "1", "backend": backend, "engine": "Eng"}
    env = _build_envelope(tool_adapter=tool)
    assert env.tool_adapter.backend == backend


def test_envelope_rejects_unknown_backend():
    tool = {"name": "X", "version": "1", "backend": "kubernetes", "engine": "Eng"}
    with pytest.raises(ValidationError):
        _build_envelope(tool_adapter=tool)


# ----------------------------------------------------------------------------
# Determinism
# ----------------------------------------------------------------------------


def test_envelope_canonical_bytes_is_deterministic_across_calls():
    env = _build_envelope()
    a = env.canonical_bytes()
    b = env.canonical_bytes()
    assert a == b


def test_envelope_canonical_bytes_independent_of_input_dict_order():
    """If we build the envelope from a dict whose key order is shuffled,
    the canonical_bytes must match a fresh-build envelope with the same data.
    """
    env_a = _build_envelope()
    env_b_dict = env_a.canonical_dict()
    # Reverse the top-level dict order; pydantic re-validates and should produce
    # the same canonical_bytes back.
    shuffled = dict(reversed(list(env_b_dict.items())))
    env_b = Envelope.model_validate(shuffled)
    assert env_a.canonical_bytes() == env_b.canonical_bytes()


def test_envelope_canonical_bytes_changes_when_payload_changes():
    env_a = _build_envelope()
    env_b = _build_envelope(input_refs=["s3://different"])
    assert env_a.canonical_bytes() != env_b.canonical_bytes()


# ----------------------------------------------------------------------------
# Falsifier integration
# ----------------------------------------------------------------------------


def test_envelope_with_falsifier_items_round_trip():
    items = [
        FalsifierItem(
            name="l1.h2_vqe_vs_fci",
            threshold="<= 1e-3 Ha",
            actual=2.8e-4,
            status="pass",
        )
    ]
    block = FalsifierBlock(status="pass", items=items)
    env = _build_envelope(falsifier=block)
    rebuilt = Envelope.model_validate_json(env.model_dump_json())
    assert rebuilt.falsifier.items[0].name == "l1.h2_vqe_vs_fci"
    assert rebuilt.falsifier.status == "pass"


def test_envelope_with_back_edges():
    edges = [
        BackEdge(layer="L6", audit_record_id="audit:l6-source-001"),
        BackEdge(layer="L1", audit_record_id="audit:l1-validation-001", relation="USED"),
    ]
    env = _build_envelope(back_edges=edges)
    rebuilt = Envelope.model_validate_json(env.model_dump_json())
    assert len(rebuilt.back_edges) == 2
    assert rebuilt.back_edges[0].relation == "DERIVED_FROM"
    assert rebuilt.back_edges[1].relation == "USED"


# ----------------------------------------------------------------------------
# Disagreement metrics
# ----------------------------------------------------------------------------


def test_envelope_disagreement_metrics_round_trip():
    metrics = [
        DisagreementMetric(name="dpa_vs_mace_energy", value=12.5, unit="meV/atom"),
        DisagreementMetric(name="qe_vs_pyscf_energy", value=2.1, unit="meV/atom"),
    ]
    block = DisagreementBlock(metrics=metrics)
    env = _build_envelope(disagreement=block)
    rebuilt = Envelope.model_validate_json(env.model_dump_json())
    assert len(rebuilt.disagreement.metrics) == 2
    assert rebuilt.disagreement.metrics[0].name == "dpa_vs_mace_energy"


# ----------------------------------------------------------------------------
# Boundary block in nested artifacts
# ----------------------------------------------------------------------------


def test_envelope_includes_research_boundary_verbatim_in_canonical_dict():
    env = _build_envelope()
    d = env.canonical_dict()
    assert d["research_boundary"] == RESEARCH_BOUNDARY


def test_envelope_extra_fields_rejected():
    """The envelope is sealed (extra='forbid')."""
    base = _build_envelope().model_dump(mode="json")
    base["sneaky_extra_field"] = "hello"
    with pytest.raises(ValidationError):
        Envelope.model_validate(base)
