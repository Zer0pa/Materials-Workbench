"""OptimadeFederatedQueryAdapter — OPTIMADE v1.3 federated structure query.

Backend selection via MaterialsConfig.PHASE0_DATABASE_BACKEND:
    "optimade_mock" (default)  — returns canned hits matching positive fixtures.
    "optimade_live"            — real OPTIMADE v1.3 HTTP query via httpx
                                 (parked; enabled when config flag is set).

Every call emits a SourceManifest (mock) or triggers a live fetch.
No network calls in the stub backend — all data is read from fixture manifests.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from zer0pa_materials_workbench.adapters.phase0.base import Phase0Adapter, _run_id
from zer0pa_materials_workbench.audit.sources import SourceManifest
from zer0pa_materials_workbench.envelope.config import MaterialsConfig
from zer0pa_materials_workbench.envelope.hashing import sha256_of

# Path to the fixture structures directory (relative to the repo root).
_FIXTURES_STRUCTURES = Path(__file__).parents[4] / "fixtures" / "structures"

# Canned OPTIMADE v1.3 response entries that mirror the positive fixtures.
_STUB_HITS: list[dict[str, Any]] = [
    {
        "id": "mp-942733",
        "type": "structures",
        "attributes": {
            "chemical_formula_reduced": "La3Li7O12Zr2",
            "nsites": 24,
            "elements": ["La", "Li", "O", "Zr"],
            "lattice_vectors": [[12.971, 0.0, 0.0], [0.0, 12.971, 0.0], [0.0, 0.0, 12.971]],
            "structure_features": [],
            "last_modified": "2024-01-01T00:00:00Z",
        },
        "relationships": {},
    },
    {
        "id": "mp-985582",
        "type": "structures",
        "attributes": {
            "chemical_formula_reduced": "Cl5Li6PS",
            "nsites": 13,
            "elements": ["Cl", "Li", "P", "S"],
            "lattice_vectors": [[9.85, 0.0, 0.0], [0.0, 9.85, 0.0], [0.0, 0.0, 9.85]],
            "structure_features": [],
            "last_modified": "2024-01-01T00:00:00Z",
        },
        "relationships": {},
    },
]


class OptimadeFederatedQueryAdapter(Phase0Adapter):
    """OPTIMADE v1.3 federated query adapter.

    Args:
        config: MaterialsConfig instance (reads PHASE0_DATABASE_BACKEND).
        base_url: OPTIMADE endpoint (used by real backend only).
    """

    adapter_name = "optimade_federated_query"
    OPTIMADE_VERSION = "1.3"

    def __init__(
        self,
        config: MaterialsConfig | None = None,
        base_url: str = "https://optimade.materialsproject.org",
    ) -> None:
        super().__init__(config)
        self.base_url = base_url
        self._last_manifest: SourceManifest | None = None

    def _execute(self, input: dict[str, Any]) -> dict[str, Any]:
        backend = getattr(self.config, "PHASE0_DATABASE_BACKEND", "optimade_mock")
        if backend == "optimade_live":
            return self._query_real(input)
        return self._query_stub(input)

    def _query_stub(self, input: dict[str, Any]) -> dict[str, Any]:
        """Return canned OPTIMADE hits for the queried element(s)."""
        elements = input.get("elements", [])
        filter_str = input.get("filter", "")
        query_id = uuid.uuid4().hex[:12]
        run_id = _run_id()

        # Filter stub hits by element if provided.
        hits = _STUB_HITS
        if elements:
            hits = [
                h for h in _STUB_HITS
                if any(el in h["attributes"]["elements"] for el in elements)
            ]

        input_payload = {"elements": elements, "filter": filter_str, "backend": "optimade_mock"}
        output_payload = {
            "extracted_properties": [],
            "units_normalised": True,
            "contradictions_blocking": [],
            "optimade_hits": hits,
            "query_filter": filter_str or f"elements HAS ANY '{','.join(elements)}'",
            "optimade_version": self.OPTIMADE_VERSION,
            "hit_count": len(hits),
        }

        input_hash = sha256_of(input_payload)
        output_hash = sha256_of(output_payload)

        # Emit SourceManifest.
        self._last_manifest = self._make_source_manifest(
            source_id=f"optimade:stub:{query_id}",
            source_type="api",
            locator=f"{self.base_url}/v1/structures",
            license_spdx="CC-BY-4.0",
            summary=f"OPTIMADE v{self.OPTIMADE_VERSION} stub query elements={elements}; {len(hits)} hits",
            content_hash=output_hash,
            query_params=input_payload,
        )

        return self._build_envelope(
            run_id=run_id,
            input_hash=input_hash,
            output_hash=output_hash,
            output=output_payload,
            tool_adapter_name="OptimadeFederatedQueryAdapter/stub",
            backend="stub",
            input_data=input_payload,
        )

    def _query_real(self, input: dict[str, Any]) -> dict[str, Any]:  # pragma: no cover
        """Real OPTIMADE v1.3 query via httpx.

        Parked behind PHASE0_DATABASE_BACKEND=optimade_live.
        Not called in any unit test — the stub covers the contract.
        """
        raise NotImplementedError(
            "optimade_live backend is parked. "
            "Set PHASE0_DATABASE_BACKEND=optimade_mock for stub mode."
        )

    def get_last_manifest(self) -> SourceManifest | None:
        """Return the SourceManifest produced by the most recent query."""
        return self._last_manifest
