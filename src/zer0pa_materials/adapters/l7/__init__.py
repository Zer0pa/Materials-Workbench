"""L7 orchestration adapters.

Public surface:

* :class:`L7Adapter` — abstract base for every L7 adapter.
* :func:`make_l7_envelope` — envelope construction helper.
* :class:`PrefectCampaignAdapter` — campaign lifecycle (lifecycle, retries,
  cancellation, deployment metadata).
* :class:`ParslFanoutAdapter` — fan-out across processes.
* :class:`AiiDAProvenanceAdapter` — materials workflow provenance.
* :class:`Atomate2WorkflowAdapter` — workflow templates.
* :class:`LangGraphReasonerAdapter` — reasoner state graph.
* :class:`BoTorchAcquisitionAdapter` — multi-fidelity acquisition.
* :class:`AlabOSProtocolCompilerStub` — recipe-only protocol compiler.
* :exc:`ForbiddenAcquisitionError`, :exc:`AlabosExecutableInRecipeOnlyError`.
"""

from zer0pa_materials.adapters.l7.aiida_provenance import AiiDAProvenanceAdapter
from zer0pa_materials.adapters.l7.alabos_protocol import (
    AlabosExecutableInRecipeOnlyError,
    AlabOSProtocolCandidate,
    AlabOSProtocolCompilerStub,
)
from zer0pa_materials.adapters.l7.atomate2_workflow import Atomate2WorkflowAdapter
from zer0pa_materials.adapters.l7.base import (
    L7Adapter,
    L7CampaignParams,
    make_l7_envelope,
    rollup_falsifier_status,
)
from zer0pa_materials.adapters.l7.botorch_acquisition import (
    BoTorchAcquisitionAdapter,
    ForbiddenAcquisitionError,
)
from zer0pa_materials.adapters.l7.langgraph_reasoner import LangGraphReasonerAdapter
from zer0pa_materials.adapters.l7.parsl_fanout import ParslFanoutAdapter
from zer0pa_materials.adapters.l7.prefect_campaign import PrefectCampaignAdapter

__all__ = [
    "L7Adapter",
    "L7CampaignParams",
    "make_l7_envelope",
    "rollup_falsifier_status",
    "PrefectCampaignAdapter",
    "ParslFanoutAdapter",
    "AiiDAProvenanceAdapter",
    "Atomate2WorkflowAdapter",
    "LangGraphReasonerAdapter",
    "BoTorchAcquisitionAdapter",
    "ForbiddenAcquisitionError",
    "AlabOSProtocolCandidate",
    "AlabOSProtocolCompilerStub",
    "AlabosExecutableInRecipeOnlyError",
]
