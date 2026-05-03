"""Shared fixtures for plug-swap tests — Wave 5b.

Research infrastructure for in silico materials science discovery.
Outputs are research artifacts. No regulatory certification claims.
No clinical or human-subject use. ITAR / weapons applications are
out of scope (Meta UMA Acceptable Use Policy and operator policy).

This conftest provides:

1. ``plug_swap_registry`` — a session-scoped SwapRegistry populated with
   (layer, adapter_a, adapter_b, golden_seed, call_fn) for every layer.

2. ``plug_swap_harness`` — a session-scoped PlugSwapHarness backed by the
   registry above.

These fixtures are available to all tests under ``tests/plug_swap/`` without
modifying any existing per-layer test files.

Layer adapter pairs registered
-------------------------------
| Layer   | Adapter A                        | Adapter B                       |
|---------|----------------------------------|---------------------------------|
| phase0  | OptimadeFederatedQueryAdapter    | LangGraphExtractionWorkflow     |
| L1      | PyScfMolecularSolver             | QuantumEspressoAiiDASolver      |
| quantum | PennyLaneVqeSolver               | QiskitNatureVqeSolver           |
| L2      | DeepmdDpaCalculatorAdapter       | MaceMpCalculatorAdapter         |
| ionic   | NebMigrationBarrierAdapter       | MlipMdDiffusionAdapter          |
| L1.5    | PhonopyHarmonicAdapter           | Phono3pyAnharmonicBTEAdapter    |
| L3      | PyCalphadEquilibriumAdapter      | EspeiBayesianFitAdapter         |
| L4      | PrismsPfAdapter                  | MoosePhaseFieldAdapter          |
| L5      | FEniCSxContinuumAdapter          | DealIIStructuralAdapter         |
| L6      | MatterGenGeneratorAdapter        | DiffCspGeneratorAdapter         |
| L7      | PrefectCampaignAdapter           | LangGraphReasonerAdapter        |

Note on L7 (LangGraphReasonerAdapter)
--------------------------------------
The LangGraph reasoner adapter's primary public method is ``step()`` (which
returns a ``ReasonerState``), not ``run()``.  For the plug-swap invariant we
wrap it via :class:`PrefectCampaignAdapter.run()` for A and use the
PrefectCampaignAdapter.run() shape for both to keep the envelope type
consistent.  The harness's ``call_fn`` for L7 uses ``adapter.run()`` on both.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from zer0pa_materials_workbench.adapters.ionic.base import IonicJobParams
from zer0pa_materials_workbench.adapters.ionic.mlip_md import MlipMdDiffusionAdapter

# ionic
from zer0pa_materials_workbench.adapters.ionic.neb import NebMigrationBarrierAdapter
from zer0pa_materials_workbench.adapters.l1.base import L1JobParams

# L1
from zer0pa_materials_workbench.adapters.l1.pyscf import PyScfMolecularSolver
from zer0pa_materials_workbench.adapters.l1.qe_aiida import QuantumEspressoAiiDASolver
from zer0pa_materials_workbench.adapters.l1_5.base import L15JobParams
from zer0pa_materials_workbench.adapters.l1_5.phono3py_bte import Phono3pyAnharmonicBTEAdapter

# L1.5
from zer0pa_materials_workbench.adapters.l1_5.phonopy_harmonic import PhonopyHarmonicAdapter
from zer0pa_materials_workbench.adapters.l2.base import L2PredictRequest

# L2
from zer0pa_materials_workbench.adapters.l2.deepmd_dpa import DeepmdDpaCalculatorAdapter
from zer0pa_materials_workbench.adapters.l2.mace_mp import MaceMpCalculatorAdapter
from zer0pa_materials_workbench.adapters.l3.base import L3CalphadRequest
from zer0pa_materials_workbench.adapters.l3.espei_fit import EspeiBayesianFitAdapter

# L3
from zer0pa_materials_workbench.adapters.l3.pycalphad_equilibrium import PyCalphadEquilibriumAdapter
from zer0pa_materials_workbench.adapters.l4.base import L4PredictRequest
from zer0pa_materials_workbench.adapters.l4.contracts import (
    PhaseFieldDomain,
    PhaseFieldMaterial,
    PhaseFieldMesh,
    PhaseFieldRunSpec,
)
from zer0pa_materials_workbench.adapters.l4.moose import MoosePhaseFieldAdapter

# L4
from zer0pa_materials_workbench.adapters.l4.prisms_pf import PrismsPfAdapter
from zer0pa_materials_workbench.adapters.l5.base import L5ContinuumRequest
from zer0pa_materials_workbench.adapters.l5.dealii import DealIIStructuralAdapter

# L5
from zer0pa_materials_workbench.adapters.l5.fenicsx import FEniCSxContinuumAdapter
from zer0pa_materials_workbench.adapters.l6.diffcsp import DiffCspGeneratorAdapter

# L6
from zer0pa_materials_workbench.adapters.l6.mattergen import MatterGenGeneratorAdapter
from zer0pa_materials_workbench.adapters.l7.base import L7CampaignParams
from zer0pa_materials_workbench.adapters.l7.langgraph_reasoner import LangGraphReasonerAdapter

# L7
from zer0pa_materials_workbench.adapters.l7.prefect_campaign import PrefectCampaignAdapter
from zer0pa_materials_workbench.adapters.phase0.langgraph_extraction import LangGraphExtractionWorkflow

# ---------------------------------------------------------------------------
# Layer-specific imports
# ---------------------------------------------------------------------------
# phase0
from zer0pa_materials_workbench.adapters.phase0.optimade import OptimadeFederatedQueryAdapter

# quantum
from zer0pa_materials_workbench.adapters.quantum.pennylane_vqe import PennyLaneVqeSolver
from zer0pa_materials_workbench.adapters.quantum.qiskit_nature_vqe import QiskitNatureVqeSolver
from zer0pa_materials_workbench.envelope import cif_hash_from_text
from zer0pa_materials_workbench.plugswap import GLOBAL_REGISTRY, PlugSwapHarness, SwapRegistry

# ---------------------------------------------------------------------------
# Golden seed constants
# ---------------------------------------------------------------------------

_FIXTURES_DIR = Path(__file__).parents[2] / "fixtures" / "structures"

_H2_CIF = (_FIXTURES_DIR / "H2" / "structure.cif").read_text()
_H2_HASH = cif_hash_from_text(_H2_CIF)

_LLZO_HASH = "sha256:d45cb2bfe5e76b86b365e1402e118ed32280049a62345c903558c6cfac04ef19"
_LI6PS5CL_HASH = "sha256:8d7b217550c751a08bd6bc85d74a166ff0b4966266552d254ca53527607c40bc"

_TDB_PATH = str(Path(__file__).parents[2] / "fixtures" / "tdb" / "Cu-Mg-toy.tdb")

_L4_SPEC = PhaseFieldRunSpec(
    equation="cahn_hilliard",
    domain=PhaseFieldDomain(dimension=2, extents=[10.0, 10.0], units="nm"),
    mesh=PhaseFieldMesh(nodes=[16, 16]),
    materials=[PhaseFieldMaterial(phase_name="alpha", initial_fraction=0.5)],
    time_steps=10,
    dt=0.01,
    n_dumps=6,
)

# ---------------------------------------------------------------------------
# Per-layer call_fn helpers
# ---------------------------------------------------------------------------

# phase0 — adapter.query(dict) -> Envelope
def _phase0_call(adapter, seed):
    return adapter.query(seed)

# L1 — adapter.submit_job(cif, params) -> Envelope
def _l1_call(adapter, seed):
    cif, params = seed
    return adapter.submit_job(cif, params)

# quantum — adapter.solve_h2() -> Envelope (seed ignored; H2 is canonical)
def _quantum_call(adapter, seed):
    return adapter.solve_h2()

# L2 — adapter.predict(structure, request) -> dict -> Envelope
def _l2_call(adapter, seed):
    from zer0pa_materials_workbench.envelope.envelope import Envelope as _Env
    structure, request = seed
    result = adapter.predict(structure, request)
    clean = {k: v for k, v in result.items() if not k.startswith("_")}
    return _Env.model_validate(clean)

# ionic — adapter.compute(params) -> Envelope
def _ionic_call(adapter, seed):
    return adapter.compute(seed)

# L1.5 — adapter.compute(params) -> Envelope
def _l15_call(adapter, seed):
    return adapter.compute(seed)

# L3 — adapter.run(request) -> dict -> Envelope
def _l3_call(adapter, seed):
    from zer0pa_materials_workbench.envelope.envelope import Envelope as _Env
    result = adapter.run(seed)
    clean = {k: v for k, v in result.items() if not k.startswith("_")}
    return _Env.model_validate(clean)

# L4 — adapter.run(spec, request) -> dict -> Envelope
def _l4_call(adapter, seed):
    from zer0pa_materials_workbench.envelope.envelope import Envelope as _Env
    spec, request = seed
    result = adapter.run(spec, request)
    clean = {k: v for k, v in result.items() if not k.startswith("_")}
    return _Env.model_validate(clean)

# L5 — adapter.run(request) -> dict -> Envelope
def _l5_call(adapter, seed):
    from zer0pa_materials_workbench.envelope.envelope import Envelope as _Env
    result = adapter.run(seed)
    clean = {k: v for k, v in result.items() if not k.startswith("_")}
    return _Env.model_validate(clean)

# L6 — adapter.generate(seed_dict) -> list[Envelope]; take first
def _l6_call(adapter, seed):
    envs = adapter.generate(seed)
    return envs[0]

# L7 — adapter.execute(params) -> Envelope
def _l7_call(adapter, seed):
    return adapter.execute(seed)


# ---------------------------------------------------------------------------
# Golden seed factories (zero-argument callables)
# ---------------------------------------------------------------------------

def _phase0_seed():
    return {"chemical_formula": "La3Li7O12Zr2", "elements": ["La", "Li", "O", "Zr"]}

def _l1_seed():
    params = L1JobParams(
        structure_cif=_H2_CIF,
        structure_hash=_H2_HASH,
        campaign_id="campaign:plugswap-conftest-l1",
        candidate_id="candidate:plugswap-h2",
    )
    return (_H2_CIF, params)

def _quantum_seed():
    return {"molecule": "H2", "bond_length_ang": 0.74, "basis": "sto-3g"}

def _l2_seed():
    structure = {
        "lattice_vectors": [[3.84, 0.0, 0.0], [0.0, 3.84, 0.0], [0.0, 0.0, 3.84]],
        "species": ["Si", "Si"],
        "fractional_coords": [[0.0, 0.0, 0.0], [0.5, 0.5, 0.5]],
    }
    request = L2PredictRequest(
        run_id="run:plugswap/l2/si",
        candidate_id="candidate:Si:plugswap",
        campaign_id="campaign:plugswap/l2",
        rights_claim_id="rights:plugswap/l2",
    )
    return (structure, request)

def _ionic_seed():
    return IonicJobParams(
        structure_hash=_LLZO_HASH,
        campaign_id="campaign:plugswap/ionic",
        candidate_id="candidate:LLZO:cubic",
        run_id="run:plugswap/ionic/llzo",
    )

def _l15_seed():
    return L15JobParams(
        structure_hash=_LLZO_HASH,
        fixture_id="fixture:LLZO:plugswap",
        material_id="LLZO",
        campaign_id="campaign:plugswap/l15",
        candidate_id="candidate:LLZO:plugswap",
    )

def _l3_seed():
    return L3CalphadRequest(
        run_id="run:plugswap/l3/cu-mg",
        candidate_id="candidate:Cu-Mg:plugswap",
        campaign_id="campaign:plugswap/l3",
        rights_claim_id="rights:plugswap/l3",
        tdb_path=_TDB_PATH,
    )

def _l4_seed():
    request = L4PredictRequest(
        run_id="run:plugswap/l4/001",
        candidate_id="candidate:plugswap/l4",
        campaign_id="campaign:plugswap/l4",
        rights_claim_id="rights:plugswap/l4",
    )
    return (_L4_SPEC, request)

def _l5_seed():
    return L5ContinuumRequest(
        run_id="run:plugswap/l5/001",
        candidate_id="candidate:plugswap/l5",
        campaign_id="campaign:plugswap/l5",
        rights_claim_id="rights:plugswap/l5",
    )

def _l6_seed():
    return {}

def _l7_seed():
    return L7CampaignParams(
        campaign_id="campaign:plugswap/l7",
        candidate_id="candidate:plugswap/l7",
        objective="maximize_ionic_conductivity",
        n_candidates=1,
        fidelity="L2_stub",
    )


# ---------------------------------------------------------------------------
# Populate GLOBAL_REGISTRY once per session
# ---------------------------------------------------------------------------

def _populate_global_registry(registry: SwapRegistry) -> None:
    """Register all 11 layers in the provided registry."""
    registry.register_layer(
        layer="phase0",
        adapter_factory_a=OptimadeFederatedQueryAdapter,
        adapter_factory_b=LangGraphExtractionWorkflow,
        golden_seed_fn=_phase0_seed,
        call_fn=_phase0_call,
        adapter_a_name="OptimadeFederatedQueryAdapter",
        adapter_b_name="LangGraphExtractionWorkflow",
    )
    registry.register_layer(
        layer="L1",
        adapter_factory_a=PyScfMolecularSolver,
        adapter_factory_b=QuantumEspressoAiiDASolver,
        golden_seed_fn=_l1_seed,
        call_fn=_l1_call,
        adapter_a_name="PyScfMolecularSolver",
        adapter_b_name="QuantumEspressoAiiDASolver",
    )
    registry.register_layer(
        layer="quantum",
        adapter_factory_a=PennyLaneVqeSolver,
        adapter_factory_b=QiskitNatureVqeSolver,
        golden_seed_fn=_quantum_seed,
        call_fn=_quantum_call,
        adapter_a_name="PennyLaneVqeSolver",
        adapter_b_name="QiskitNatureVqeSolver",
    )
    registry.register_layer(
        layer="L2",
        adapter_factory_a=DeepmdDpaCalculatorAdapter,
        adapter_factory_b=MaceMpCalculatorAdapter,
        golden_seed_fn=_l2_seed,
        call_fn=_l2_call,
        adapter_a_name="DeepmdDpaCalculatorAdapter",
        adapter_b_name="MaceMpCalculatorAdapter",
    )
    registry.register_layer(
        layer="ionic",
        adapter_factory_a=NebMigrationBarrierAdapter,
        adapter_factory_b=MlipMdDiffusionAdapter,
        golden_seed_fn=_ionic_seed,
        call_fn=_ionic_call,
        adapter_a_name="NebMigrationBarrierAdapter",
        adapter_b_name="MlipMdDiffusionAdapter",
    )
    registry.register_layer(
        layer="L1.5",
        adapter_factory_a=PhonopyHarmonicAdapter,
        adapter_factory_b=Phono3pyAnharmonicBTEAdapter,
        golden_seed_fn=_l15_seed,
        call_fn=_l15_call,
        adapter_a_name="PhonopyHarmonicAdapter",
        adapter_b_name="Phono3pyAnharmonicBTEAdapter",
    )
    registry.register_layer(
        layer="L3",
        adapter_factory_a=PyCalphadEquilibriumAdapter,
        adapter_factory_b=EspeiBayesianFitAdapter,
        golden_seed_fn=_l3_seed,
        call_fn=_l3_call,
        adapter_a_name="PyCalphadEquilibriumAdapter",
        adapter_b_name="EspeiBayesianFitAdapter",
    )
    registry.register_layer(
        layer="L4",
        adapter_factory_a=PrismsPfAdapter,
        adapter_factory_b=MoosePhaseFieldAdapter,
        golden_seed_fn=_l4_seed,
        call_fn=_l4_call,
        adapter_a_name="PrismsPfAdapter",
        adapter_b_name="MoosePhaseFieldAdapter",
    )
    registry.register_layer(
        layer="L5",
        adapter_factory_a=FEniCSxContinuumAdapter,
        adapter_factory_b=DealIIStructuralAdapter,
        golden_seed_fn=_l5_seed,
        call_fn=_l5_call,
        adapter_a_name="FEniCSxContinuumAdapter",
        adapter_b_name="DealIIStructuralAdapter",
    )
    registry.register_layer(
        layer="L6",
        adapter_factory_a=lambda: MatterGenGeneratorAdapter(n_candidates=1),
        adapter_factory_b=lambda: DiffCspGeneratorAdapter(n_candidates=1),
        golden_seed_fn=_l6_seed,
        call_fn=_l6_call,
        adapter_a_name="MatterGenGeneratorAdapter",
        adapter_b_name="DiffCspGeneratorAdapter",
    )
    registry.register_layer(
        layer="L7",
        adapter_factory_a=PrefectCampaignAdapter,
        adapter_factory_b=LangGraphReasonerAdapter,
        golden_seed_fn=_l7_seed,
        call_fn=_l7_call,
        adapter_a_name="PrefectCampaignAdapter",
        adapter_b_name="LangGraphReasonerAdapter",
    )


# Populate the module-level singleton on import.
_populate_global_registry(GLOBAL_REGISTRY)


# ---------------------------------------------------------------------------
# Pytest fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def plug_swap_registry() -> SwapRegistry:
    """Session-scoped SwapRegistry with all 11 layers registered."""
    registry = SwapRegistry()
    _populate_global_registry(registry)
    return registry


@pytest.fixture(scope="session")
def plug_swap_harness(plug_swap_registry: SwapRegistry) -> PlugSwapHarness:
    """Session-scoped PlugSwapHarness backed by plug_swap_registry."""
    return PlugSwapHarness(registry=plug_swap_registry)
