"""AimdDiffusionAdapter — AIMD diffusion / conductivity adapter.

Higher-fidelity counterpart to :class:`MlipMdDiffusionAdapter`. Real
AIMD requires gradient-true DFT energy/forces at every MD step which is
prohibitively expensive on CPU; the real backend lives behind a
:class:`BlockedSourceManifest`.

Stub mode shares the synthetic-trace generator with the MLIP-MD adapter
but uses the ``method_seed="aimd"`` value, which adds a ~8% systematic
bias toward lower D so the cross-method disagreement falsifier
``mlip_aimd_diffusion_disagreement`` exercises a non-zero gap on every
fixture.
"""

from __future__ import annotations

from typing import Any

from zer0pa_materials.adapters.ionic.base import (
    IonicJobParams,
    IonicTransportAdapter,
)
from zer0pa_materials.adapters.ionic.mlip_md import (
    fit_diffusion_blocks,
    synthetic_msd_trace,
)
from zer0pa_materials.adapters.ionic.nernst_einstein import (
    nernst_einstein_conductivity,
)
from zer0pa_materials.audit.sources import BlockedSourceManifest
from zer0pa_materials.envelope import (
    Envelope,
    FalsifierItem,
    IonicTransportOutput,
)

__all__ = ["AimdDiffusionAdapter", "AIMD_BLOCKED_MANIFEST"]


AIMD_BLOCKED_MANIFEST: BlockedSourceManifest = BlockedSourceManifest(
    source_manifest_id="src:blocked:aimd-real-backend",
    attempted_locator="real-AIMD-via-VASP-or-CP2K-or-QE",
    blocker_reason="unavailable_credentials",
    blocker_detail=(
        "Real AIMD requires DFT gradient calls at every MD step (typical "
        "10000-50000 steps at 600 K), which is impractical without "
        "Runpod GPU access AND a verified L1 DFT backend. Both are "
        "parked behind the L1 source manifest and the Runpod cutover "
        "gate. Stub returns deterministic literature-calibrated D with "
        "an AIMD-method bias relative to the MLIP-MD stub."
    ),
    retry_strategy=(
        "Wire the real AIMD backend after L1 publishes a CINEB/AIMD-"
        "capable solver and the Runpod cutover gate is green. Run AIMD "
        "only for highest-promise candidates because of GPU cost."
    ),
)


class AimdDiffusionAdapter(IonicTransportAdapter):
    """AIMD diffusion / conductivity adapter (CPU-first stub).

    Same shape as :class:`MlipMdDiffusionAdapter` but with the AIMD
    method seed so the cross-method disagreement falsifier produces a
    real (small) gap on every fixture.
    """

    ADAPTER_NAME = "AimdDiffusionAdapter"
    ADAPTER_VERSION = "0.1.0"
    BACKEND = "stub"
    ENGINE = "aimd-stub-v1"
    METHOD_SEED = "aimd"

    def compute(self, params: IonicJobParams) -> Envelope:
        dt_ps = params.md_trajectory_length_ps / max(params.n_md_steps, 1)
        times, msd = synthetic_msd_trace(
            structure_hash=params.structure_hash,
            fixture_id=params.fixture_id,
            n_steps=params.n_md_steps,
            dt_ps=dt_ps,
            method_seed=self.METHOD_SEED,
        )
        block = fit_diffusion_blocks(times, msd, n_blocks=4)
        D_cm2 = block.D_mean_cm2_per_s
        sigma = nernst_einstein_conductivity(
            diffusion_cm2_per_s=D_cm2,
            carrier_concentration_per_cm3=params.li_carrier_concentration_per_cm3,
            temperature_K=params.temperature_K,
            charge_number=1,
            haven_ratio=params.haven_ratio,
        )
        msd_final_A2 = msd[-1] if msd else 0.0
        # AIMD is more authoritative when it runs but slower; stub
        # confidence reflects the method's nominal authority.
        is_known = params.fixture_id is not None
        confidence = 0.85 if is_known else 0.50

        output = IonicTransportOutput(
            msd_A2=msd_final_A2,
            diffusion_coefficient_cm2_per_s=D_cm2,
            nernst_einstein_conductivity_S_per_cm=sigma,
            interface_stability="unknown",
            defect_disorder_assumptions=[
                f"haven_ratio={params.haven_ratio}",
                f"carrier_density_per_cm3={params.li_carrier_concentration_per_cm3}",
                f"D_uncertainty_dex={block.D_uncertainty_dex:.4f}",
                "stub: synthetic AIMD trace; ~8% systematic bias vs MLIP-MD stub",
            ],
            confidence=confidence,
        )
        ci_lo = nernst_einstein_conductivity(
            diffusion_cm2_per_s=block.lo_cm2_per_s,
            carrier_concentration_per_cm3=params.li_carrier_concentration_per_cm3,
            temperature_K=params.temperature_K,
            haven_ratio=params.haven_ratio,
        )
        ci_hi = nernst_einstein_conductivity(
            diffusion_cm2_per_s=block.hi_cm2_per_s,
            carrier_concentration_per_cm3=params.li_carrier_concentration_per_cm3,
            temperature_K=params.temperature_K,
            haven_ratio=params.haven_ratio,
        )
        ci_item = FalsifierItem(
            name="ionic.rt_conductivity_credible_interval",
            threshold=">= 1e-3 S/cm in CI",
            actual={
                "mean_S_per_cm": sigma,
                "lo_S_per_cm": ci_lo,
                "hi_S_per_cm": ci_hi,
                "uncertainty_dex": block.D_uncertainty_dex,
                "method": "aimd",
            },
            status="pass" if ci_hi >= 1e-3 else "fail",
            rationale="AIMD block-stdev uncertainty propagated through Nernst-Einstein.",
        )
        extra_input: dict[str, Any] = {
            "method_seed": self.METHOD_SEED,
            "n_md_steps": params.n_md_steps,
            "trajectory_length_ps": params.md_trajectory_length_ps,
        }
        return self.make_envelope(
            output, params, extra_falsifier_items=[ci_item], extra_input=extra_input
        )
