"""L6 — Generative Discovery adapters.

Adapters:
    MatterGenGeneratorAdapter      Diffusion CSP stub (perturbed LLZO fixtures).
    DiffCspGeneratorAdapter        DiffCSP stub.
    CrystaLlmCifGeneratorAdapter   CrystaLLM stub.
    LeMatGenBenchEvaluatorAdapter  LeMat-GenBench S.U.N. evaluator (U+N only).

All adapters:
    - inherit from L6GeneratorAdapter (common base in base.py)
    - call assert_boundary on every emitted Envelope
    - emit BlockedSourceManifest (license_unverified) for real backends
    - novelty_status defaults to "pending" until falsifiers pass
"""

from zer0pa_materials.adapters.l6.base import L6GeneratorAdapter
from zer0pa_materials.adapters.l6.crystallm import CrystaLlmCifGeneratorAdapter
from zer0pa_materials.adapters.l6.diffcsp import DiffCspGeneratorAdapter
from zer0pa_materials.adapters.l6.lematgen_eval import LeMatGenBenchEvaluatorAdapter
from zer0pa_materials.adapters.l6.mattergen import MatterGenGeneratorAdapter

__all__ = [
    "L6GeneratorAdapter",
    "MatterGenGeneratorAdapter",
    "DiffCspGeneratorAdapter",
    "CrystaLlmCifGeneratorAdapter",
    "LeMatGenBenchEvaluatorAdapter",
]
