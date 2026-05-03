"""Tests for rights claims and reuse-scope enforcement (A1 §Data Sovereignty)."""

from __future__ import annotations

import pytest

from zer0pa_materials_workbench.audit.rights import (
    RIGHTS_TABLE,
    RightsClaim,
    RightsViolationError,
    assert_rights_for,
    default_reuse_scope_for,
    is_reuse_scope_compatible,
)

# ----------------------------------------------------------------------------
# Rights table integrity
# ----------------------------------------------------------------------------


def test_rights_table_covers_all_eight_data_classes():
    expected = {
        "customer_input",
        "raw_simulation_output",
        "mlip_finetune",
        "calphad_posterior",
        "audit_schema",
        "audit_event_content",
        "public_kg",
        "cross_customer_corpus",
    }
    assert set(RIGHTS_TABLE.keys()) == expected


def test_rights_table_defaults_match_prd():
    """Default reuse scopes should match the PRD §Data Sovereignty table."""
    assert RIGHTS_TABLE["customer_input"].default_reuse_scope == "tenant_only"
    assert RIGHTS_TABLE["raw_simulation_output"].default_reuse_scope == "tenant_only"
    assert RIGHTS_TABLE["mlip_finetune"].default_reuse_scope == "tenant_only"
    assert RIGHTS_TABLE["calphad_posterior"].default_reuse_scope == "tenant_only"
    assert RIGHTS_TABLE["audit_schema"].default_reuse_scope == "open_science"
    assert RIGHTS_TABLE["audit_event_content"].default_reuse_scope == "tenant_only"
    assert RIGHTS_TABLE["public_kg"].default_reuse_scope == "open_science"
    # Cross-customer corpus default is tenant_only because PRD says
    # "no use by default; explicit opt-in only".
    assert RIGHTS_TABLE["cross_customer_corpus"].default_reuse_scope == "tenant_only"


# ----------------------------------------------------------------------------
# is_reuse_scope_compatible
# ----------------------------------------------------------------------------


def test_strict_sovereign_blocks_shared_learning_for_customer_input():
    assert not is_reuse_scope_compatible(
        "customer_input", "shared_learning", "strict_sovereign"
    )


def test_strict_sovereign_blocks_open_science_for_raw_simulation_output():
    assert not is_reuse_scope_compatible(
        "raw_simulation_output", "open_science", "strict_sovereign"
    )


def test_shared_advantage_widens_mlip_finetune():
    """Under shared_advantage, MLIP finetune may be shared_learning."""
    assert is_reuse_scope_compatible(
        "mlip_finetune", "shared_learning", "shared_advantage"
    )


def test_shared_advantage_does_not_open_customer_input():
    """customer_input remains tenant_only even under shared_advantage."""
    assert not is_reuse_scope_compatible(
        "customer_input", "shared_learning", "shared_advantage"
    )


def test_open_science_widens_raw_simulation_output():
    """Under open_science (with customer agreement), raw outputs may go open."""
    assert is_reuse_scope_compatible(
        "raw_simulation_output", "open_science", "open_science"
    )


def test_audit_event_content_remains_tenant_under_open_science():
    """Audit event content is not auto-widened by open_science contract mode.

    The customer must use a redaction policy on the rights claim.
    """
    assert not is_reuse_scope_compatible(
        "audit_event_content", "open_science", "open_science"
    )


# ----------------------------------------------------------------------------
# default_reuse_scope_for
# ----------------------------------------------------------------------------


def test_default_reuse_scope_for_strict_returns_table_default():
    assert default_reuse_scope_for("mlip_finetune", "strict_sovereign") == "tenant_only"
    assert default_reuse_scope_for("public_kg", "strict_sovereign") == "open_science"


def test_default_reuse_scope_for_shared_advantage_widens():
    assert default_reuse_scope_for("mlip_finetune", "shared_advantage") == "shared_learning"


def test_default_reuse_scope_for_open_science():
    assert default_reuse_scope_for("raw_simulation_output", "open_science") == "open_science"


# ----------------------------------------------------------------------------
# RightsClaim model
# ----------------------------------------------------------------------------


def test_rights_claim_round_trip():
    rc = RightsClaim(
        rights_claim_id="rights:campaign:battery:v1",
        tenant="acme-batteries",
        data_class="customer_input",
        ownership="customer",
        reuse_scope="tenant_only",
        contract_mode="strict_sovereign",
        rationale="Customer chemistry; not shared.",
    )
    raw = rc.model_dump_json()
    rc2 = RightsClaim.model_validate_json(raw)
    assert rc2.rights_claim_id == rc.rights_claim_id
    assert rc2.redaction_policy == "none"


def test_rights_claim_rejects_bad_id():
    with pytest.raises(ValueError, match="rights_claim_id must match"):
        RightsClaim(
            rights_claim_id="bad",
            tenant="x",
            data_class="customer_input",
            ownership="customer",
            reuse_scope="tenant_only",
            contract_mode="strict_sovereign",
            rationale="x",
        )


def test_rights_claim_rejects_invalid_data_class():
    with pytest.raises(ValueError):
        RightsClaim(
            rights_claim_id="rights:test",
            tenant="x",
            data_class="not-a-class",  # type: ignore[arg-type]
            ownership="customer",
            reuse_scope="tenant_only",
            contract_mode="strict_sovereign",
            rationale="x",
        )


# ----------------------------------------------------------------------------
# assert_rights_for — the falsification gate
# ----------------------------------------------------------------------------


def _envelope_rights(rights_claim_id: str, scope: str) -> dict:
    return {"rights_claim_id": rights_claim_id, "reuse_scope": scope}


def test_assert_rights_passes_when_envelope_matches_claim():
    rc = RightsClaim(
        rights_claim_id="rights:claim:1",
        tenant="acme",
        data_class="customer_input",
        ownership="customer",
        reuse_scope="tenant_only",
        contract_mode="strict_sovereign",
        rationale="x",
    )
    env = _envelope_rights("rights:claim:1", "tenant_only")
    # Should not raise.
    assert_rights_for(env, rc)


def test_assert_rights_rejects_id_mismatch():
    rc = RightsClaim(
        rights_claim_id="rights:claim:A",
        tenant="acme",
        data_class="customer_input",
        ownership="customer",
        reuse_scope="tenant_only",
        contract_mode="strict_sovereign",
        rationale="x",
    )
    env = _envelope_rights("rights:claim:B", "tenant_only")
    with pytest.raises(RightsViolationError, match="does not match"):
        assert_rights_for(env, rc)


def test_assert_rights_rejects_scope_mismatch():
    """Envelope claims open_science but rights claim is tenant_only — must reject."""
    rc = RightsClaim(
        rights_claim_id="rights:claim:1",
        tenant="acme",
        data_class="customer_input",
        ownership="customer",
        reuse_scope="tenant_only",
        contract_mode="strict_sovereign",
        rationale="x",
    )
    env = _envelope_rights("rights:claim:1", "open_science")
    with pytest.raises(RightsViolationError, match="does not match"):
        assert_rights_for(env, rc)


def test_assert_rights_rejects_invalid_claim_under_contract_mode():
    """A claim itself can be invalid: customer_input with shared_learning under
    strict_sovereign is illegal regardless of envelope."""
    # We have to bypass model validation since reuse_scope is a Literal —
    # construct a "valid" model and let assert_rights_for catch the table
    # violation.
    rc = RightsClaim(
        rights_claim_id="rights:bad-claim",
        tenant="acme",
        data_class="customer_input",
        ownership="customer",
        reuse_scope="shared_learning",  # Not allowed for customer_input
        contract_mode="strict_sovereign",
        rationale="invalid by construction",
    )
    env = _envelope_rights("rights:bad-claim", "shared_learning")
    with pytest.raises(RightsViolationError, match="not allowed"):
        assert_rights_for(env, rc)


# ----------------------------------------------------------------------------
# Per PRD §Data Sovereignty: four contract-mode × data-class violations
# ----------------------------------------------------------------------------

# These four cover the cardinal violations the falsification wave exercises.


@pytest.mark.parametrize(
    "data_class, claim_scope, contract_mode",
    [
        # 1. customer_input promoted to shared_learning under strict_sovereign
        ("customer_input", "shared_learning", "strict_sovereign"),
        # 2. raw_simulation_output promoted to open_science under strict_sovereign
        ("raw_simulation_output", "open_science", "strict_sovereign"),
        # 3. mlip_finetune promoted to open_science under shared_advantage
        #    (only widening shared_learning is allowed)
        ("mlip_finetune", "open_science", "shared_advantage"),
        # 4. cross_customer_corpus promoted to open_science under
        #    strict_sovereign (only opt-in shared_advantage widens it)
        ("cross_customer_corpus", "open_science", "strict_sovereign"),
    ],
)
def test_four_canonical_violations_blocked(data_class, claim_scope, contract_mode):
    rc = RightsClaim(
        rights_claim_id="rights:violation-test",
        tenant="acme",
        data_class=data_class,
        ownership="customer",
        reuse_scope=claim_scope,
        contract_mode=contract_mode,
        rationale="violation test",
    )
    env = _envelope_rights("rights:violation-test", claim_scope)
    with pytest.raises(RightsViolationError):
        assert_rights_for(env, rc)


def test_tenant_only_tuple_cannot_be_promoted_to_open_science():
    """Falsification-wave gate: 'private tuple reuse outside reuse_scope'."""
    rc = RightsClaim(
        rights_claim_id="rights:tenant-tuple",
        tenant="acme",
        data_class="raw_simulation_output",
        ownership="customer",
        reuse_scope="tenant_only",
        contract_mode="strict_sovereign",
        rationale="tenant-only customer simulation",
    )
    env = _envelope_rights("rights:tenant-tuple", "open_science")
    with pytest.raises(RightsViolationError):
        assert_rights_for(env, rc)


def test_assert_rights_accepts_envelope_dict_or_object():
    """Helper accepts both pydantic-like and plain-dict envelopes."""
    rc = RightsClaim(
        rights_claim_id="rights:claim:1",
        tenant="acme",
        data_class="customer_input",
        ownership="customer",
        reuse_scope="tenant_only",
        contract_mode="strict_sovereign",
        rationale="x",
    )

    class FakeRights:
        rights_claim_id = "rights:claim:1"
        reuse_scope = "tenant_only"

    assert_rights_for(FakeRights(), rc)
    assert_rights_for({"rights_claim_id": "rights:claim:1", "reuse_scope": "tenant_only"}, rc)


def test_assert_rights_rejects_non_rights_input():
    rc = RightsClaim(
        rights_claim_id="rights:test",
        tenant="acme",
        data_class="customer_input",
        ownership="customer",
        reuse_scope="tenant_only",
        contract_mode="strict_sovereign",
        rationale="x",
    )
    with pytest.raises(TypeError, match="RightsBlock-like or a dict"):
        assert_rights_for(123, rc)  # type: ignore[arg-type]
