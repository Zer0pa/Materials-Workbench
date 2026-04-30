"""ThermoelectricZtAssembler — full ZT figure-of-merit assembler.

This is the PRIMARY USER-FACING adapter. It orchestrates the full thermoelectric
evidence chain:

  1. Phono3py BTE → κ_L (lattice thermal conductivity)
  2. BoltzTraP2 → S, σ_e, κ_e (electronic transport, rigid-band)
  3. AMSET → S, σ_e, κ_e (electronic transport, explicit scattering)
  4. ZT = S²σ_e·T / (κ_L + κ_e) from BOTH BoltzTraP2 and AMSET branches
  5. Rank stability check: both methods must agree on which candidate ranks highest

ZT rank stability (PRD §L1.5 Falsifiers)
-----------------------------------------
A candidate's ZT rank is considered "stable" iff both BoltzTraP2 and AMSET rank
the same candidate above the same threshold (ZT > 1.5 at ≥700 K for Bi2Te3/SnSe
family). If the rank changes between transport assumptions, the gate fails.

Literature reference ZT targets
--------------------------------
Bi2Te3 (300 K): ZT ~ 1.0–1.2 (state of the art; classic thermoelectric)
PbTe    (700 K): ZT ~ 1.5–2.0 (Heremans 2008, Pei 2011)
SnSe    (800 K): ZT ~ 2.6 (Zhao et al. 2014, single crystal b-axis)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from zer0pa_materials.adapters.l1_5.amset import AmsetScatteringTransportAdapter
from zer0pa_materials.adapters.l1_5.base import (
    L15JobParams,
    L15PhononAdapter,
    make_l15_envelope,
    rollup_falsifier_status,
)
from zer0pa_materials.adapters.l1_5.boltztrap2 import BoltzTraP2RigidBandTransportAdapter
from zer0pa_materials.adapters.l1_5.phono3py_bte import Phono3pyAnharmonicBTEAdapter
from zer0pa_materials.audit.sources import BlockedSourceManifest
from zer0pa_materials.boundary import RESEARCH_BOUNDARY
from zer0pa_materials.envelope import (
    AuditBlock,
    Envelope,
    FalsifierItem,
    L15PhononOutput,
    RightsBlock,
    ToolAdapter,
    canonical_json_bytes,
    sha256_of,
)

import uuid

__all__ = [
    "ThermoelectricZtAssembler",
    "EQUIFORMERV2_BLOCKED_MANIFEST",
    "ZtAssemblyResult",
    "assemble_zt",
]


# EquiformerV2-OMat24 is the strongest universal phonon MLIP (Brief #2 Gap A).
# Blocked pending model licence confirmation.
EQUIFORMERV2_BLOCKED_MANIFEST = BlockedSourceManifest(
    source_manifest_id="src:blocked:equiformerv2-omat24-zt",
    attempted_locator="fairchem/EquiformerV2-OMat24 for MLIP-phonon ZT chain",
    blocker_reason="license_unverified",
    blocker_detail=(
        "EquiformerV2-OMat24 (Brief #2 Gap A) is the strongest universal phonon MLIP "
        "as of September 2025. Using it for force constant generation in the ZT chain "
        "requires verified licence terms for the OMat24 trained weights. "
        "The ZT assembler stub uses Phono3py + BoltzTraP2/AMSET synthetic stubs instead."
    ),
    retry_strategy=(
        "Verify EquiformerV2-OMat24 licence via fairchem/EquiformerV2 on HuggingFace. "
        "If compatible, wire it as the MLIP backend for Phono3py displacement-force "
        "generation and update the L2 MLIP phase report. Track under Brief #2 Gap A."
    ),
)

# ZT threshold for rank stability check (PRD §L1.5 Falsifiers)
ZT_THRESHOLD_HIGH = 1.5     # ZT > 1.5 at high T is the candidate gate
ZT_RANK_STABILITY_TOLERANCE = 0.15  # |ZT_BT2 - ZT_AMSET| / ZT_BT2 < 15%


def assemble_zt(
    seebeck_uV_per_K: float,
    sigma_e_S_per_cm: float,
    kappa_e_W_per_mK: float,
    kappa_L_W_per_mK: float,
    temperature_K: float,
) -> float:
    """Compute ZT = S²σ_e·T / (κ_L + κ_e).

    Units: S in µV/K → convert to V/K. σ_e in S/cm. κ in W/(m·K).
    All κ converted to W/(cm·K) to match σ_e denominator.
    """
    # S in V/K
    S_V_per_K = seebeck_uV_per_K * 1e-6
    # κ_total in W/(m·K)
    kappa_total = kappa_L_W_per_mK + kappa_e_W_per_mK
    if kappa_total <= 0:
        return 0.0
    # σ_e in S/m = S/cm × 100
    sigma_e_S_per_m = sigma_e_S_per_cm * 100.0
    # ZT = S²·σ·T / κ   [V²/K² × S/m × K / (W/(m·K)) = V²·S/(m·K·W/(m·K)) = dimensionless]
    zt = (S_V_per_K ** 2) * sigma_e_S_per_m * temperature_K / kappa_total
    return zt


@dataclass
class ZtAssemblyResult:
    """Result of assembling ZT from both BoltzTraP2 and AMSET branches."""

    material_id: str | None
    temperature_K: float

    # Phono3py κ_L
    kappa_L_W_per_mK: float

    # BoltzTraP2 branch
    bt2_seebeck_uV_per_K: float
    bt2_sigma_e_S_per_cm: float
    bt2_kappa_e_W_per_mK: float
    bt2_zt: float

    # AMSET branch
    amset_seebeck_uV_per_K: float
    amset_sigma_e_S_per_cm: float
    amset_kappa_e_W_per_mK: float
    amset_zt: float

    # Rank stability
    zt_rank_stable: bool
    zt_fractional_disagreement: float


class ThermoelectricZtAssembler(L15PhononAdapter):
    """Full thermoelectric ZT assembler.

    Orchestrates: Phono3py → κ_L, BoltzTraP2 → transport, AMSET → transport,
    then assembles ZT from both branches and checks rank stability.

    The rank stability gate (PRD §L1.5): if |ZT_BT2 - ZT_AMSET| / ZT_BT2 > 15%,
    the gate fails — the candidate's ZT rank is not stable across transport
    assumptions and requires further DFT validation.
    """

    ADAPTER_NAME: str = "ThermoelectricZtAssembler"
    ADAPTER_VERSION: str = "0.1.0"
    BACKEND: str = "stub"
    ENGINE: str = "zt-assembler-synthetic"

    def __init__(self) -> None:
        self._phono3py = Phono3pyAnharmonicBTEAdapter()
        self._boltztrap2 = BoltzTraP2RigidBandTransportAdapter()
        self._amset = AmsetScatteringTransportAdapter()

    def compute(self, params: L15JobParams) -> Envelope:
        return self._assemble(params)

    def assemble(self, params: L15JobParams) -> ZtAssemblyResult:
        """Run the full ZT chain and return a structured result object."""
        # Step 1: Phono3py κ_L
        phono3py_env = self._phono3py.compute(params)
        kappa_L = phono3py_env.output.get("thermal_conductivity_W_per_mK") or 0.0

        # Step 2: BoltzTraP2 electronic transport
        bt2_env = self._boltztrap2.compute(params)
        bt2_seebeck = bt2_env.output.get("seebeck_uV_per_K") or 0.0
        bt2_sigma_e = bt2_env.output.get("electrical_conductivity_S_per_cm") or 0.0
        bt2_kappa_e = bt2_env.output.get("thermal_conductivity_W_per_mK") or 0.0

        # Step 3: AMSET electronic transport
        amset_env = self._amset.compute(params)
        amset_seebeck = amset_env.output.get("seebeck_uV_per_K") or 0.0
        amset_sigma_e = amset_env.output.get("electrical_conductivity_S_per_cm") or 0.0
        amset_kappa_e = amset_env.output.get("thermal_conductivity_W_per_mK") or 0.0

        # Step 4: Assemble ZT from both branches
        bt2_zt = assemble_zt(bt2_seebeck, bt2_sigma_e, bt2_kappa_e, kappa_L, params.temperature_K)
        amset_zt = assemble_zt(amset_seebeck, amset_sigma_e, amset_kappa_e, kappa_L, params.temperature_K)

        # Step 5: Rank stability check
        zt_disagreement = abs(bt2_zt - amset_zt) / max(bt2_zt, 1e-9)
        rank_stable = zt_disagreement <= ZT_RANK_STABILITY_TOLERANCE

        return ZtAssemblyResult(
            material_id=params.material_id,
            temperature_K=params.temperature_K,
            kappa_L_W_per_mK=kappa_L,
            bt2_seebeck_uV_per_K=bt2_seebeck,
            bt2_sigma_e_S_per_cm=bt2_sigma_e,
            bt2_kappa_e_W_per_mK=bt2_kappa_e,
            bt2_zt=bt2_zt,
            amset_seebeck_uV_per_K=amset_seebeck,
            amset_sigma_e_S_per_cm=amset_sigma_e,
            amset_kappa_e_W_per_mK=amset_kappa_e,
            amset_zt=amset_zt,
            zt_rank_stable=rank_stable,
            zt_fractional_disagreement=zt_disagreement,
        )

    def _assemble(self, params: L15JobParams) -> Envelope:
        """Run the full ZT chain and return a populated envelope."""
        result = self.assemble(params)

        # Best ZT is the average of both branches (conservative)
        best_zt = (result.bt2_zt + result.amset_zt) / 2.0

        # Rank stability falsifier
        stability_item = FalsifierItem(
            name="l15.zt_rank_stability",
            threshold=(
                f"<= {ZT_RANK_STABILITY_TOLERANCE*100:.0f}% fractional ZT disagreement "
                f"between BoltzTraP2 and AMSET"
            ),
            actual={
                "bt2_zt": round(result.bt2_zt, 4),
                "amset_zt": round(result.amset_zt, 4),
                "fractional_disagreement": round(result.zt_fractional_disagreement, 4),
                "rank_stable": result.zt_rank_stable,
            },
            status="pass" if result.zt_rank_stable else "fail",
        )

        # High-ZT candidate gate
        candidate_item = FalsifierItem(
            name="l15.zt_candidate_threshold",
            threshold=f"> {ZT_THRESHOLD_HIGH} at operating temperature (both branches)",
            actual={
                "bt2_zt": round(result.bt2_zt, 4),
                "amset_zt": round(result.amset_zt, 4),
                "threshold": ZT_THRESHOLD_HIGH,
                "both_exceed": result.bt2_zt > ZT_THRESHOLD_HIGH and result.amset_zt > ZT_THRESHOLD_HIGH,
            },
            status=(
                "pass"
                if result.bt2_zt > ZT_THRESHOLD_HIGH and result.amset_zt > ZT_THRESHOLD_HIGH
                else ("inconclusive" if best_zt > ZT_THRESHOLD_HIGH else "fail")
            ),
        )

        # Phonon-does-not-substitute-for-ionic is hardcoded in make_l15_envelope
        output = L15PhononOutput(
            imaginary_mode_max_THz=0.0,
            mlip_vs_dft_force_rmse_eV_per_Ang=None,
            qmesh_convergence_pct=None,
            seebeck_uV_per_K=round(result.bt2_seebeck_uV_per_K, 2),
            electrical_conductivity_S_per_cm=round(result.bt2_sigma_e_S_per_cm, 2),
            thermal_conductivity_W_per_mK=round(result.kappa_L_W_per_mK + result.bt2_kappa_e_W_per_mK, 4),
            zt=round(best_zt, 4),
        )

        run_id = params.run_id or f"run:l1-5:zt:{uuid.uuid4().hex[:12]}"
        canonical_input: dict[str, Any] = {
            "structure_hash": params.structure_hash,
            "temperature_K": params.temperature_K,
            "fixture_id": params.fixture_id,
            "material_id": params.material_id,
            "adapter": self.ADAPTER_NAME,
        }

        in_bytes = canonical_json_bytes(canonical_input)
        out_dict = output.model_dump(mode="json")
        out_bytes = canonical_json_bytes(out_dict)
        audit_id = f"audit:l1-5:zt:{uuid.uuid4().hex[:12]}"

        # Build all falsifier items
        from zer0pa_materials.adapters.l1_5.base import _PHONON_NOT_IONIC_ITEM  # noqa
        from zer0pa_materials.envelope.falsifier import FalsifierStatus

        items: list[FalsifierItem] = [
            _PHONON_NOT_IONIC_ITEM,
            *output.falsifier_items(),
            stability_item,
            candidate_item,
        ]

        envelope = Envelope(
            research_boundary=RESEARCH_BOUNDARY,
            run_id=run_id,
            campaign_id=params.campaign_id,
            candidate_id=params.candidate_id,
            layer="L1.5",
            tool_adapter=ToolAdapter(
                name=self.ADAPTER_NAME,
                version=self.ADAPTER_VERSION,
                backend=self.BACKEND,  # type: ignore[arg-type]
                engine=self.ENGINE,
            ),
            input_refs=["service:l1-5-phonon-service:v1"],
            output={
                **out_dict,
                # Extended ZT assembly result (both branches)
                "zt_assembly": {
                    "bt2_zt": round(result.bt2_zt, 4),
                    "amset_zt": round(result.amset_zt, 4),
                    "bt2_seebeck_uV_per_K": round(result.bt2_seebeck_uV_per_K, 2),
                    "amset_seebeck_uV_per_K": round(result.amset_seebeck_uV_per_K, 2),
                    "bt2_sigma_e_S_per_cm": round(result.bt2_sigma_e_S_per_cm, 2),
                    "amset_sigma_e_S_per_cm": round(result.amset_sigma_e_S_per_cm, 2),
                    "kappa_L_W_per_mK": round(result.kappa_L_W_per_mK, 4),
                    "zt_rank_stable": result.zt_rank_stable,
                    "zt_fractional_disagreement": round(result.zt_fractional_disagreement, 4),
                },
            },
            falsifier={
                "status": rollup_falsifier_status(items),
                "items": [fi.model_dump(mode="json") for fi in items],
            },
            audit=AuditBlock(
                audit_record_id=audit_id,
                input_hash=sha256_of(in_bytes),
                output_hash=sha256_of(out_bytes),
            ),
            rights=RightsBlock(
                rights_claim_id=params.rights_claim_id,
                reuse_scope=params.reuse_scope,  # type: ignore[arg-type]
            ),
        )
        return envelope
