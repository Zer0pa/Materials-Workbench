"""Rights claims and reuse-scope enforcement (PRD §Data Sovereignty).

This module implements the canonical rights table from the PRD. Three contract
modes (``strict_sovereign``, ``shared_advantage``, ``open_science``) cross-cut
the per-data-class ownership table:

================================  =================  =================  =====================================
Data class                        Default ownership   Default scope     Notes
================================  =================  =================  =====================================
customer_input                    customer            tenant_only        chemistry, specs, constraints
raw_simulation_output             customer            tenant_only        DFT/MLIP/CALPHAD on customer chemistry
mlip_finetune                     customer            tenant_only        checkpoints trained on customer data
calphad_posterior                 customer            tenant_only        TDBs/posteriors fitted from customer
audit_schema                      zer0pa              open_science       schema and software (Zer0pa-owned)
audit_event_content               customer            tenant_only        confidential; redacted hash proofs
public_kg                         public              open_science       per source license
cross_customer_corpus             public              open_science       no use by default; opt-in only
================================  =================  =================  =====================================

The ``shared_advantage`` mode allows ``shared_learning`` reuse for the
``mlip_finetune`` and ``calphad_posterior`` classes (anonymized priors),
provided the customer has signed the explicit opt-in.

The ``open_science`` mode allows ``open_science`` reuse for any data class
the customer has agreed to publish. Agreed public artifacts only.

The function :func:`assert_rights_for` enforces the table at runtime: if an
envelope's ``rights.reuse_scope`` does not match the rights claim's
``reuse_scope`` for that data class, ``RightsViolationError`` is raised.

This is the gate the falsification wave's "private tuple reuse outside
``reuse_scope``" test exercises.
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

__all__ = [
    "RIGHTS_CLAIM_ID_RE",
    "RIGHTS_TABLE",
    "ContractMode",
    "DataClass",
    "Ownership",
    "RedactionPolicy",
    "ReuseScope",
    "RightsClaim",
    "RightsViolationError",
    "assert_rights_for",
    "default_reuse_scope_for",
    "is_reuse_scope_compatible",
]


# ----------------------------------------------------------------------------
# Type aliases
# ----------------------------------------------------------------------------

DataClass = Literal[
    "customer_input",
    "raw_simulation_output",
    "mlip_finetune",
    "calphad_posterior",
    "audit_schema",
    "audit_event_content",
    "public_kg",
    "cross_customer_corpus",
]
Ownership = Literal["customer", "zer0pa", "public", "split"]
ReuseScope = Literal["tenant_only", "shared_learning", "open_science"]
ContractMode = Literal["strict_sovereign", "shared_advantage", "open_science"]
RedactionPolicy = Literal["none", "hash_commit", "aggregate_only", "full"]


RIGHTS_CLAIM_ID_RE = re.compile(r"^rights:[A-Za-z0-9._\-:/]+$")


# ----------------------------------------------------------------------------
# The canonical rights table (PRD §Data Sovereignty)
# ----------------------------------------------------------------------------


class _RightsTableEntry(BaseModel):
    """One row of the canonical rights table."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    data_class: DataClass
    default_ownership: Ownership
    default_reuse_scope: ReuseScope
    # Set of reuse scopes that are *legal* for this data class regardless
    # of contract mode. The table below sometimes widens this set under
    # specific contract modes — see :func:`is_reuse_scope_compatible`.
    base_allowed_scopes: tuple[ReuseScope, ...]
    # Notes for the operator audit.
    notes: str


RIGHTS_TABLE: dict[DataClass, _RightsTableEntry] = {
    "customer_input": _RightsTableEntry(
        data_class="customer_input",
        default_ownership="customer",
        default_reuse_scope="tenant_only",
        base_allowed_scopes=("tenant_only",),
        notes="Chemistry, specs, constraints. Processing only during campaign.",
    ),
    "raw_simulation_output": _RightsTableEntry(
        data_class="raw_simulation_output",
        default_ownership="customer",
        default_reuse_scope="tenant_only",
        base_allowed_scopes=("tenant_only",),
        notes="DFT/phonon/MLIP/CALPHAD outputs from customer chemistry.",
    ),
    "mlip_finetune": _RightsTableEntry(
        data_class="mlip_finetune",
        default_ownership="customer",
        default_reuse_scope="tenant_only",
        # Under shared_advantage, anonymised reuse is allowed.
        base_allowed_scopes=("tenant_only",),
        notes="Checkpoints trained on customer data; adapter code remains Zer0pa.",
    ),
    "calphad_posterior": _RightsTableEntry(
        data_class="calphad_posterior",
        default_ownership="customer",
        default_reuse_scope="tenant_only",
        base_allowed_scopes=("tenant_only",),
        notes="TDBs/posteriors fitted from customer data; generic priors remain Zer0pa.",
    ),
    "audit_schema": _RightsTableEntry(
        data_class="audit_schema",
        default_ownership="zer0pa",
        default_reuse_scope="open_science",
        base_allowed_scopes=("open_science", "shared_learning", "tenant_only"),
        notes="Audit log schema and software; Zer0pa-owned, full reuse.",
    ),
    "audit_event_content": _RightsTableEntry(
        data_class="audit_event_content",
        default_ownership="customer",
        default_reuse_scope="tenant_only",
        base_allowed_scopes=("tenant_only",),
        notes="Audit event content for customer campaign; redacted hash-chain proof.",
    ),
    "public_kg": _RightsTableEntry(
        data_class="public_kg",
        default_ownership="public",
        default_reuse_scope="open_science",
        base_allowed_scopes=("open_science", "shared_learning", "tenant_only"),
        notes="Public literature/database KG; reuse with attribution per source license.",
    ),
    "cross_customer_corpus": _RightsTableEntry(
        data_class="cross_customer_corpus",
        default_ownership="public",
        # No use by default — explicit opt-in only.
        default_reuse_scope="tenant_only",
        base_allowed_scopes=("tenant_only",),
        notes="Cross-customer training corpus; no use by default; opt-in only.",
    ),
}


# Per (data_class, contract_mode) widening of the allowed scope set.
# Default base allowed scopes apply if no widening row matches.
_CONTRACT_MODE_WIDENINGS: dict[tuple[DataClass, ContractMode], tuple[ReuseScope, ...]] = {
    # Shared advantage allows anonymised posterior reuse.
    ("mlip_finetune", "shared_advantage"): ("tenant_only", "shared_learning"),
    ("calphad_posterior", "shared_advantage"): ("tenant_only", "shared_learning"),
    ("cross_customer_corpus", "shared_advantage"): ("tenant_only", "shared_learning"),
    # Open science allows full open reuse for those classes that the
    # customer has agreed to publish (the rights claim is the agreement).
    ("raw_simulation_output", "open_science"): ("tenant_only", "shared_learning", "open_science"),
    ("mlip_finetune", "open_science"): ("tenant_only", "shared_learning", "open_science"),
    ("calphad_posterior", "open_science"): ("tenant_only", "shared_learning", "open_science"),
    ("cross_customer_corpus", "open_science"): ("tenant_only", "shared_learning", "open_science"),
    # audit_event_content under open_science still requires per-event redaction.
    # We do NOT widen audit_event_content here; the customer must use the
    # appropriate redaction_policy on the rights claim.
}


def default_reuse_scope_for(
    data_class: DataClass,
    contract_mode: ContractMode = "strict_sovereign",
) -> ReuseScope:
    """Return the default reuse scope for a data class under a contract mode."""
    if contract_mode == "strict_sovereign":
        return RIGHTS_TABLE[data_class].default_reuse_scope
    # For shared_advantage / open_science, the default still tracks
    # ``default_reuse_scope`` unless this widening explicitly overrides.
    widened = _CONTRACT_MODE_WIDENINGS.get((data_class, contract_mode))
    if widened is None:
        return RIGHTS_TABLE[data_class].default_reuse_scope
    # Pick the most-permissive widened scope.
    if "open_science" in widened:
        return "open_science"
    if "shared_learning" in widened:
        return "shared_learning"
    return "tenant_only"


def is_reuse_scope_compatible(
    data_class: DataClass,
    requested_scope: ReuseScope,
    contract_mode: ContractMode,
) -> bool:
    """Return True if ``requested_scope`` is allowed for ``data_class`` under ``contract_mode``."""
    base = set(RIGHTS_TABLE[data_class].base_allowed_scopes)
    widened = _CONTRACT_MODE_WIDENINGS.get((data_class, contract_mode))
    if widened is not None:
        base |= set(widened)
    return requested_scope in base


# ----------------------------------------------------------------------------
# RightsClaim model
# ----------------------------------------------------------------------------


class RightsClaim(BaseModel):
    """A rights claim attached to an envelope or KG node.

    Each rights claim must be self-consistent against :data:`RIGHTS_TABLE`
    AND against the contract mode declared by the customer. The claim is
    immutable once written to the audit ledger; supersession is via the
    :class:`zer0pa_materials_workbench.audit.decisions.Decision` mechanism.
    """

    model_config = ConfigDict(extra="forbid")

    rights_claim_id: str = Field(..., description="URN starting with 'rights:'.")
    tenant: str = Field(
        ..., min_length=1, description="Tenant identifier: 'Zer0pa', '<customer>', 'public'."
    )
    data_class: DataClass
    ownership: Ownership
    reuse_scope: ReuseScope
    contract_mode: ContractMode
    redaction_policy: RedactionPolicy = Field(default="none")
    rationale: str = Field(
        ..., min_length=1, description="Short explanation tying claim to PRD policy."
    )

    @field_validator("rights_claim_id")
    @classmethod
    def _v_id(cls, v: str) -> str:
        if not RIGHTS_CLAIM_ID_RE.match(v):
            raise ValueError(
                f"rights_claim_id must match {RIGHTS_CLAIM_ID_RE.pattern!r}; got {v!r}"
            )
        return v


# ----------------------------------------------------------------------------
# Enforcement
# ----------------------------------------------------------------------------


class RightsViolationError(ValueError):
    """Raised when an envelope's reuse scope conflicts with its rights claim.

    The falsification wave's "private tuple reuse outside ``reuse_scope``"
    test deliberately constructs an envelope with a tenant_only data class
    promoted to open_science; this error must fire.
    """

    def __init__(
        self,
        message: str,
        *,
        rights_claim_id: str | None = None,
        envelope_scope: str | None = None,
        data_class: str | None = None,
    ):
        self.rights_claim_id = rights_claim_id
        self.envelope_scope = envelope_scope
        self.data_class = data_class
        super().__init__(message)


def assert_rights_for(envelope_rights, rights_claim: RightsClaim) -> None:
    """Assert that the envelope's rights are compatible with the rights claim.

    Raises :class:`RightsViolationError` on a mismatch. The function accepts
    either a :class:`zer0pa_materials_workbench.envelope.RightsBlock` or a plain dict
    with ``rights_claim_id`` and ``reuse_scope`` keys, so we don't import-cycle
    the envelope module from here.
    """
    if hasattr(envelope_rights, "rights_claim_id"):
        env_id = envelope_rights.rights_claim_id
        env_scope = envelope_rights.reuse_scope
    elif isinstance(envelope_rights, dict):
        env_id = envelope_rights.get("rights_claim_id")
        env_scope = envelope_rights.get("reuse_scope")
    else:
        raise TypeError(
            "envelope_rights must be RightsBlock-like or a dict with rights_claim_id+reuse_scope"
        )

    if env_id != rights_claim.rights_claim_id:
        raise RightsViolationError(
            f"envelope.rights.rights_claim_id ({env_id!r}) does not match "
            f"the rights claim being asserted ({rights_claim.rights_claim_id!r})",
            rights_claim_id=rights_claim.rights_claim_id,
            envelope_scope=env_scope,
            data_class=rights_claim.data_class,
        )

    # 1. The claim's own scope must be valid under its contract mode.
    if not is_reuse_scope_compatible(
        rights_claim.data_class, rights_claim.reuse_scope, rights_claim.contract_mode
    ):
        raise RightsViolationError(
            f"rights claim {rights_claim.rights_claim_id} has scope "
            f"{rights_claim.reuse_scope!r} which is not allowed for data class "
            f"{rights_claim.data_class!r} under contract mode {rights_claim.contract_mode!r}",
            rights_claim_id=rights_claim.rights_claim_id,
            envelope_scope=env_scope,
            data_class=rights_claim.data_class,
        )

    # 2. The envelope's scope must match (no widening at envelope time).
    if env_scope != rights_claim.reuse_scope:
        raise RightsViolationError(
            f"envelope.rights.reuse_scope ({env_scope!r}) does not match "
            f"rights_claim.reuse_scope ({rights_claim.reuse_scope!r}) for data class "
            f"{rights_claim.data_class!r}",
            rights_claim_id=rights_claim.rights_claim_id,
            envelope_scope=env_scope,
            data_class=rights_claim.data_class,
        )
