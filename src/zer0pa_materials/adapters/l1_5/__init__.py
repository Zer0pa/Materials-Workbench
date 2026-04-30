"""L1.5 phonon + thermoelectric transport adapters.

Public surface
--------------

* :class:`L15PhononAdapter` — abstract base for all L1.5 adapters.
* :class:`L15JobParams` — canonical input struct.
* :class:`PhonopyHarmonicAdapter` — harmonic phonon spectrum (Phonopy or synthetic).
* :class:`Phono3pyAnharmonicBTEAdapter` — lattice thermal conductivity via BTE.
* :class:`HiPhiveForceConstantFitAdapter` — force constants from MLIP-MD data.
* :class:`BoltzTraP2RigidBandTransportAdapter` — electronic transport (rigid band).
* :class:`AmsetScatteringTransportAdapter` — electronic transport (scattering mechanisms).
* :class:`ThermoelectricZtAssembler` — full ZT = S²σT / (κ_L + κ_e) assembler.
* BlockedSourceManifest entries — all real backends parked behind L15 gates.

PRD §L1.5: "Phonon does NOT substitute for ionic conductivity."
The ``phonon_does_not_substitute_for_ionic`` falsifier is hardcoded in
every envelope; the L1.5 envelope MUST NEVER claim ionic_conductivity_S_per_cm.
"""

from zer0pa_materials.adapters.l1_5.base import (
    L15JobParams,
    L15PhononAdapter,
    L15_SERVICE_REF,
    make_l15_envelope,
    rollup_falsifier_status,
)
from zer0pa_materials.adapters.l1_5.phonopy_harmonic import (
    PHONOPY_BLOCKED_MANIFEST,
    PhonopyHarmonicAdapter,
)
from zer0pa_materials.adapters.l1_5.phono3py_bte import (
    PHONO3PY_BLOCKED_MANIFEST,
    Phono3pyAnharmonicBTEAdapter,
)
from zer0pa_materials.adapters.l1_5.hiphive_fit import (
    HIPHIVE_BLOCKED_MANIFEST,
    HiPhiveForceConstantFitAdapter,
)
from zer0pa_materials.adapters.l1_5.boltztrap2 import (
    BOLTZTRAP2_BLOCKED_MANIFEST,
    BoltzTraP2RigidBandTransportAdapter,
)
from zer0pa_materials.adapters.l1_5.amset import (
    AMSET_BLOCKED_MANIFEST,
    AmsetScatteringTransportAdapter,
)
from zer0pa_materials.adapters.l1_5.zt_assembler import (
    EQUIFORMERV2_BLOCKED_MANIFEST,
    ThermoelectricZtAssembler,
    ZtAssemblyResult,
)

__all__ = [
    "L15JobParams",
    "L15PhononAdapter",
    "L15_SERVICE_REF",
    "make_l15_envelope",
    "rollup_falsifier_status",
    "PHONOPY_BLOCKED_MANIFEST",
    "PhonopyHarmonicAdapter",
    "PHONO3PY_BLOCKED_MANIFEST",
    "Phono3pyAnharmonicBTEAdapter",
    "HIPHIVE_BLOCKED_MANIFEST",
    "HiPhiveForceConstantFitAdapter",
    "BOLTZTRAP2_BLOCKED_MANIFEST",
    "BoltzTraP2RigidBandTransportAdapter",
    "AMSET_BLOCKED_MANIFEST",
    "AmsetScatteringTransportAdapter",
    "EQUIFORMERV2_BLOCKED_MANIFEST",
    "ThermoelectricZtAssembler",
    "ZtAssemblyResult",
]
