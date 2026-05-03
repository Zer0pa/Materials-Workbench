"""Falsification wave: plain qExpectedImprovement default is forbidden."""

from __future__ import annotations

import pytest

from zer0pa_materials_workbench.adapters.l7 import (
    BoTorchAcquisitionAdapter,
    ForbiddenAcquisitionError,
)
from zer0pa_materials_workbench.falsifiers.l7_falsifiers import (
    botorch_acquisition_function_allowed,
)


def test_select_acquisition_raises_for_qei_without_opt_in():
    adapter = BoTorchAcquisitionAdapter(allow_legacy_qei=False)
    with pytest.raises(ForbiddenAcquisitionError):
        adapter.select_acquisition(False, requested="qExpectedImprovement")


def test_falsifier_fails_on_qei_envelope():
    """Synthesise an L7 envelope with acquisition='qExpectedImprovement' → falsifier fails."""
    env_dict = {
        "research_boundary": "_ignored_",
        "audit": {"audit_record_id": "audit:test:x"},
        "output": {"acquisition": "qExpectedImprovement"},
        "falsifier": {
            "items": [
                {
                    "name": "l7.botorch_acquisition_function_allowed",
                    "actual": {
                        "acquisition_function": "qExpectedImprovement",
                        "allow_legacy_qei": False,
                    },
                    "status": "fail",
                    "threshold": "x",
                }
            ]
        },
        "disagreement": {"metrics": []},
    }
    item = botorch_acquisition_function_allowed(env_dict, allow_legacy_qei=False)
    assert item.status == "fail"


def test_falsifier_passes_when_opt_in():
    env_dict = {
        "research_boundary": "_ignored_",
        "audit": {"audit_record_id": "audit:test:x"},
        "output": {"acquisition": "qExpectedImprovement"},
        "falsifier": {
            "items": [
                {
                    "name": "l7.botorch_acquisition_function_allowed",
                    "actual": {
                        "acquisition_function": "qExpectedImprovement",
                        "allow_legacy_qei": True,
                    },
                    "status": "pass",
                    "threshold": "x",
                }
            ]
        },
        "disagreement": {"metrics": []},
    }
    item = botorch_acquisition_function_allowed(env_dict, allow_legacy_qei=True)
    assert item.status == "pass"
