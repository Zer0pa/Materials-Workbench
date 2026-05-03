"""Phase 0 — literature / knowledge mining adapters.

Adapters:
    OptimadeFederatedQueryAdapter    OPTIMADE v1.3 federated structure query.
    LangGraphExtractionWorkflow      LangGraph + GPT-4.1 Mini property extraction.
    RobocrystallographerStructureNarrator  Structure-to-text description.
    MaterialsBertNerAdapter          Gated NER (license gate: BlockedSourceManifest).

All adapters:
    - inherit from Phase0Adapter (common base in base.py)
    - call assert_boundary on every emitted Envelope
    - consult MaterialsConfig for backend selection
    - emit SourceManifest or BlockedSourceManifest per query
"""

from zer0pa_materials_workbench.adapters.phase0.base import Phase0Adapter
from zer0pa_materials_workbench.adapters.phase0.langgraph_extraction import LangGraphExtractionWorkflow
from zer0pa_materials_workbench.adapters.phase0.materialsbert import MaterialsBertNerAdapter
from zer0pa_materials_workbench.adapters.phase0.optimade import OptimadeFederatedQueryAdapter
from zer0pa_materials_workbench.adapters.phase0.robocrys import RobocrystallographerStructureNarrator

__all__ = [
    "LangGraphExtractionWorkflow",
    "MaterialsBertNerAdapter",
    "OptimadeFederatedQueryAdapter",
    "Phase0Adapter",
    "RobocrystallographerStructureNarrator",
]
