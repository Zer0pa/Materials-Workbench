# Deep Research Phase Report

**Boundary**: Research infrastructure for in silico materials science discovery. Outputs are research artifacts. No regulatory certification claims. No clinical or human-subject use. ITAR / weapons applications are out of scope (Meta UMA Acceptable Use Policy and operator policy).

**Retrieval date**: 2026-04-30  
**Agent**: deep-research subagent (Claude Sonnet 4.6)  
**Sources written to**: `audit/runtime/sources.jsonl`

---

## Verification 1 — EMMO IRI Verification

**Verdict**: PARTIALLY VERIFIED — 4/10 EMMO terms confirmed; 6 unconfirmed (stale or unresolvable UUIDs)

| Term | UUID | Status | Evidence |
|---|---|---|---|
| Material | EMMO_4207e895 | ✅ Confirmed | `disciplines/materials.ttl` EMMO 1.0.3 — prefLabel="Material" |
| Composition | EMMO_25aacccd | ❌ Blocked | Not in any checked module; possible pre-1.0 alpha UUID |
| Structure | EMMO_8aa4afc1 | ❌ Blocked | Not found; Crystal=EMMO_0bb3b434 exists as candidate |
| Phase | EMMO_b35e92d7 | ❌ Blocked | Not found; PhaseOfMatter=EMMO_668fbd5b exists as candidate |
| Property | EMMO_b7bcff25 | ✅ Confirmed | `chameo.ttl` — superclass of characterisation properties |
| Process | EMMO_43e9a05d | ✅ Confirmed | `OIE-Ontologies/models.ttl`, `chameo.ttl` — rdfs:subClassOf target |
| Model | EMMO_5079e106 | ❌ Blocked | Not found; Icon/Simulacrum (EMMO_d7788d1a) has altLabel "Model" |
| Simulation | EMMO_e97af6ec | ❌ Blocked | Not found in any checked module |
| Measurement | EMMO_463bcfda | ✅ Confirmed | `chameo.ttl` — superclass of CharacterisationMeasurementProcess |
| Reasoning | EMMO_b863702a | ❌ Blocked | Not found in any checked module |

**Evidence URLs**:
- https://github.com/emmo-repo/EMMO (EMMO 1.0.3 repository)
- https://raw.githubusercontent.com/emmo-repo/EMMO/master/disciplines/materials.ttl
- https://raw.githubusercontent.com/emmo-repo/domain-characterisation-methodology/main/chameo.ttl
- https://github.com/emmo-repo/OIE-Ontologies/blob/main/models.ttl

**Decision impact**: The 4 confirmed terms (Material, Property, Process, Measurement) are safe. The 6 unconfirmed terms are annotation-only in the A1 KG — they do not affect runtime correctness. Recommend resolving via EMMOntoPy in Wave 4c. Detailed table at `phases/Deep-Research/emmo-iri-verification.md`.

**source_manifest_ids**: `src:emmo:material`, `src:emmo:composition`, `src:emmo:structure`, `src:emmo:phase`, `src:emmo:property`, `src:emmo:process`, `src:emmo:model`, `src:emmo:simulation`, `src:emmo:measurement`, `src:emmo:reasoning`

**Patches for lead agent**:
- `src/zer0pa_materials_workbench/ontology/emmo.py` → Composition parent note (EMMO_25aacccd): mark as `note="UUID unverified against EMMO 1.0.3; resolve via EMMOntoPy before Wave 5 export"` for the 6 blocked terms.

---

## Verification 2 — LLZO Materials Project IDs

**Verdict**: CORRECTION REQUIRED — mp-942733 is TETRAGONAL, not cubic

**Critical finding**: The Materials Project entry **mp-942733 is Li7La3Zr2O12 TETRAGONAL (I4_1/acd, space group #142)**, not cubic. Both legacy.materialsproject.org and next-gen.materialsproject.org confirm this explicitly in their page titles: "mp-942733: Li7La3Zr2O12 (tetragonal, I4_1/acd, 142)".

The cubic LLZO manifest (`fixtures/structures/LLZO/cubic/manifest.json`) lists `mp-942733` as its MP source — this is incorrect. The tetragonal manifest (`fixtures/structures/LLZO/tetragonal/manifest.json`) lists `mp-942790` — this could not be independently confirmed (API requires key, no public page found).

**Possible correct assignment**:
- mp-942733 → tetragonal LLZO (Ia1/acd #142) ← should be in tetragonal manifest
- mp-942790 → unknown; may be cubic LLZO (Ia-3d #230) or another entry

**Evidence URLs**:
- https://legacy.materialsproject.org/materials/mp-942733/ — title: "Li7La3Zr2O12 (tetragonal, I4_1/acd, 142)"
- https://next-gen.materialsproject.org/materials/mp-942733 — same
- https://www.osti.gov/biblio/1313215 — confirms mp-942733 tetragonal I4_1/acd

**Primary literature DOIs** (both verified):
- Murugan et al. 2007 cubic LLZO: `10.1002/anie.200701144` — Angew. Chem. Int. Ed. 46(41), 7778. First cubic LLZO synthesis, RT conductivity ~3×10⁻⁴ S/cm, activation energy 0.3 eV.
- Awaka et al. 2009 tetragonal LLZO: `10.1016/j.jssc.2009.05.020` — J. Solid State Chem. 182(8), 2046. Space group I41/acd; a=13.134 Å, c=12.663 Å.

**BibTeX**:
```bibtex
@article{murugan2007llzo,
  author  = {Murugan, Ramasubramanian and Thangadurai, Venkataraman and Weppner, Werner},
  title   = {Fast Lithium Ion Conduction in Garnet-Type Li7La3Zr2O12},
  journal = {Angewandte Chemie International Edition},
  year    = {2007},
  volume  = {46},
  number  = {41},
  pages   = {7778--7781},
  doi     = {10.1002/anie.200701144}
}

@article{awaka2009llzo,
  author  = {Awaka, Junji and Kijima, Norihito and Hayakawa, Hiroshi and Akimoto, Junji},
  title   = {Synthesis and structure analysis of tetragonal {Li7La3Zr2O12} with the garnet-related type structure},
  journal = {Journal of Solid State Chemistry},
  year    = {2009},
  volume  = {182},
  number  = {8},
  pages   = {2046--2052},
  doi     = {10.1016/j.jssc.2009.05.020}
}
```

**source_manifest_ids**: `src:mp:llzo-cubic-mp942733` (blocked), `src:mp:llzo-tetragonal-mp942790` (blocked), `src:paper:llzo-murugan-2007`, `src:paper:llzo-awaka-2009`

**Patch for lead agent** (REQUIRED — this blocks correctness of fixture metadata):
```
fixtures/structures/LLZO/cubic/manifest.json
  CHANGE: sources[2].locator from "mp-942733" to "[PENDING — verify correct cubic MP ID]"
  ADD note: "mp-942733 is tetragonal. Cubic LLZO (Ia-3d #230) MP ID pending MP API verification."

fixtures/structures/LLZO/tetragonal/manifest.json
  ADD note: "mp-942733 confirmed tetragonal (I4_1/acd #142) — if mp-942790 is not tetragonal, swap citation."
```

---

## Verification 3 — Bi2Te3 ZT Review Citation

**Verdict**: VERIFIED as legitimate, but NOT the most authoritative source; recommend supplementing

**Finding**: DOI `10.1088/2515-7639/acc550` resolves to: Pecunia, V.; Silva, S.R.P.; Phillips, J.D.; et al. "Roadmap on energy harvesting materials." J. Phys.: Mater. 2023, 6(4), 042501. This is a multi-technology roadmap (photovoltaics, piezoelectric, triboelectric, thermoelectric, RF). Thermoelectrics are covered in Section 5; Bi2Te3 appears as the benchmark material. The DOI is valid and the journal (IOP Publishing, Journal of Physics: Materials) is legitimate.

**More authoritative sources identified**:

1. **Snyder & Toberer 2008** — the canonical thermoelectric review:
   - DOI: `10.1038/nmat2090`
   - Snyder, G.J.; Toberer, E.S. "Complex thermoelectric materials." Nature Materials 2008, 7(2), 105–114.
   - Directly discusses Bi2Te3 as the room-temperature TE benchmark, ZT theory, phonon engineering.

2. **Poudel et al. 2008** — primary Bi2Te3 ZT experimental:
   - DOI: `10.1126/science.1156446`
   - Poudel, B. et al. "High-thermoelectric performance of nanostructured bismuth antimony telluride bulk alloys." Science 2008, 320(5876), 634–638.
   - Peak ZT=1.4 at 100°C in nanocrystalline BiSbTe.

**BibTeX**:
```bibtex
@article{snyder2008thermoelectric,
  author  = {Snyder, G. Jeffrey and Toberer, Eric S.},
  title   = {Complex thermoelectric materials},
  journal = {Nature Materials},
  year    = {2008},
  volume  = {7},
  pages   = {105--114},
  doi     = {10.1038/nmat2090}
}

@article{poudel2008nanostructured,
  author  = {Poudel, Bed and Hao, Qing and Ma, Yi and Lan, Yucheng and Minnich, Austin and Yu, Bo and Yan, Xiao and Wang, Dezhi and Muto, Andrew and Vashaee, Daryoosh and Chen, Xiaoyuan and Liu, Junming and Dresselhaus, Mildred S. and Chen, Gang and Ren, Zhifeng},
  title   = {High-thermoelectric performance of nanostructured bismuth antimony telluride bulk alloys},
  journal = {Science},
  year    = {2008},
  volume  = {320},
  number  = {5876},
  pages   = {634--638},
  doi     = {10.1126/science.1156446}
}
```

**source_manifest_ids**: `src:paper:bi2te3-zt-roadmap-2023`, `src:paper:bi2te3-snyder-2008`, `src:paper:bi2te3-poudel-2008`

**Patch for lead agent** (cosmetic citation upgrade):
```
fixtures/structures/Bi2Te3/manifest.json
  ADD source: {"type": "paper", "locator": "10.1038/nmat2090", "license": "operator-cited"}
  CONSIDER ADDING: {"type": "paper", "locator": "10.1126/science.1156446", "license": "operator-cited"}
  NOTE on existing: 10.1088/2515-7639/acc550 is valid but is a multi-tech roadmap, not a Bi2Te3-specific review.
```

---

## Verification 4 — PhaseForgePlus License + Maturity

**Verdict**: MATURITY VERIFIED, LICENSE UNVERIFIED — remain default-blocked

**Maturity findings**:
- Latest release: v0.1.0 (2025-11-04)
- Last commit: 2026-04-26 (Dependabot ruff bump) — **actively maintained**
- pip-installable: yes — `pip install phaseforgeplus` documented in Quick Start
- pyproject.toml present: yes
- ESPEI integration: **confirmed** — `espei` is a core dependency in pyproject.toml (sourced from `github.com/cjkunselman18/ESPEI.git@Gradient-based_update` — a custom gradient-based optimization branch, not standard MCMC ESPEI)
- pycalphad>=0.11.0 required

**License findings**:
- pyproject.toml: **no license field**
- README: **no license section or badge**
- LICENSE file at `/blob/main/LICENSE`: **404**
- Described as "fully open-source" in documentation but SPDX identifier not confirmed
- Brief #2 claimed MIT — **CANNOT BE VERIFIED** from public sources

**Decision**: Keep default-blocked. The license unverification is a genuine gap, not overcaution. The Brief #2 MIT claim may be correct but cannot be confirmed from the repository.

**source_manifest_ids**: `src:repo:phaseforgeplus-license` (blocked), `src:repo:phaseforgeplus-metadata`

**Action for lead agent**: Contact maintainer (dogusariturk) to confirm license, or check PyPI page for `phaseforgeplus` which may display license metadata.

---

## Verification 5 — UMA License + AUP Confirmation

**Verdict**: VERIFIED WITH CORRECTION — library is MIT (not Apache-2.0); weights FAIR Chemistry License v1 confirmed

### fairchem library license

**CORRECTION**: Brief #2 Issue 1 stated the library is **Apache-2.0**. The actual license is **MIT**.

Evidence:
- `https://raw.githubusercontent.com/facebookresearch/fairchem/main/LICENSE.md` verbatim: "MIT License / Copyright (c) Meta, Inc. and its affiliates."
- `fair-chem.github.io/install`: "The software in this repo is licensed under an MIT license unless otherwise specified."

### UMA weights license (FAIR Chemistry License v1)

All terms confirmed from HuggingFace model card `facebook/UMA` (last updated 2025-05-14):

**Geographic restrictions** (verbatim):
> "UMA is available via HuggingFace globally, except in comprehensively sanctioned jurisdictions, and in China, Russia, and Belarus."

South Africa: **unrestricted** (not mentioned as restricted).

**AUP prohibited uses** (Section 2, verbatim):
> "Military, warfare, nuclear industries or applications, espionage, use for materials or activities that are subject to the International Traffic Arms Regulations (ITAR) maintained by the United States Department of State"
> "Guns and illegal weapons (including weapon development)"

**Output/derivative works ownership** (verbatim):
> "Subject to Meta's ownership of Materials and derivatives made by or for Meta, with respect to any derivative works and modifications of the Materials that are made by you, as between you and Meta, you are and will be the owner of such derivative works and modifications."

**Warranty disclaimer** (verbatim):
> "THE MATERIALS AND ANY OUTPUT AND RESULTS THEREFROM ARE PROVIDED ON AN 'AS IS' BASIS, WITHOUT WARRANTIES OF ANY KIND"

### LAMBench UMA exclusion

UMA was excluded from LAMBench because the model is **not accessible in China** — the authors' institutions are China-based, so the geographic restriction in FAIR Chemistry License v1 prevented access. This is a geographic-access consequence of the license, not a blanket licensing incompatibility.

**source_manifest_ids**: `src:license:fairchem-library-mit`, `src:license:uma-weights-fair-chemistry-v1`, `src:paper:lambench-uma-exclusion`

**Patches for lead agent**:
```
Any file referencing "Apache-2.0" for fairchem library:
  CHANGE to "MIT"
  Example: if adapters/l2_mlip/uma.py or source-briefs/Brief-2.md has "Apache-2.0" for library license → correct to "MIT"
```

---

## Verification 6 — DPA-3.1-3M License + LAMBench Position

**Verdict**: VERIFIED — all claims in Brief #2 Gap B confirmed with one precision refinement

| Claim | Status |
|---|---|
| DeePMD-kit library = LGPL-3.0 | ✅ CONFIRMED |
| DPA-3.1-3M weights = CC-BY-4.0 | ✅ CONFIRMED |
| LAMBench rank #1 overall | ✅ CONFIRMED |
| UMA excluded from LAMBench "due to licensing" | ⚠️ IMPRECISE — mechanism is geographic access block (China), which is a consequence of FAIR Chemistry License v1 geo-restriction |

**Evidence**:
- DeePMD-kit LGPL-3.0: `docs.deepmodeling.com/projects/deepmd/en/v3.0.3/license.html`
- DPA-3.1-3M weights CC-BY-4.0: `huggingface.co/deepmodelingcommunity/DPA` — model card metadata
- LAMBench rank 1: arXiv:2504.19578 (published npj Computational Materials DOI: 10.1038/s41524-025-01929-3). DPA-3.1-3M: M̄ᶠᶠᵐ=0.175, M̄ᵖᶜᵐ=0.322 — lowest generalizability error of all 10 benchmarked models. Rank 1 in Molecules and Catalysis domains.

**BibTeX**:
```bibtex
@article{peng2025lambench,
  author  = {Peng, Anyang and Cai, Chun and Guo, Mingyu and Zhang, Duo and Zhang, Chengqian and Jiang, Wanrun and Wang, Yinan and Loew, Antoine and Wu, Chengkun and E, Weinan and Zhang, Linfeng and Wang, Han},
  title   = {{LAMBench}: a benchmark for large atomistic models},
  journal = {npj Computational Materials},
  year    = {2025},
  doi     = {10.1038/s41524-025-01929-3}
}
```

**source_manifest_ids**: `src:license:deepmd-kit-lgpl3`, `src:license:dpa3-weights-cc-by-4`, `src:paper:lambench-dpa3-rank1`

**No patches required.** Brief #2 Gap B is substantively correct.

---

## Opportunistic Finds

### Gap E — FNO/DeepONet Phase Field Paper with Repo

Peivaste, I.; Makradi, A.; Belouettar, S. "Teaching Artificial Intelligence to Perform Rapid, Resolution-Invariant Grain Growth Modeling via Fourier Neural Operator." Accepted: Computer Methods in Applied Mechanics and Engineering, 2025. arXiv: 2503.14568.

- GitHub: https://github.com/Iman-Peivaste/PF-FNO (open-source, Python)
- Key result: FNO surrogate replaces phase-field solver for grain growth; ~400× speedup at 128×128 grid; resolution-invariant (one model generalises to unseen grid sizes)
- Direct relevance to Brief #2 Issue 3 (PINNs-MPF → FNO/DeepONet redirect) — provides a concrete citable repo for L4 neural-operator advisory mode

**source_manifest_id**: `src:paper:fno-grain-growth-2025`

**Action for lead agent**: Cite in L4 phase-field adapter documentation. No code integration needed; `advisory=True` gate already implemented.

### Gap G — PennyLane + PySCF Integration Tutorial

PennyLane official demo: "Using PennyLane with PySCF and OpenFermion." URL: https://pennylane.ai/qml/demos/tutorial_qchem_external. Published 2023-01-02; last updated 2026-04-17.

- Shows PennyLane + PySCF for Hamiltonian construction, molecular integrals, and VQE
- Note: does NOT cover Qiskit Nature directly
- Separate: `qiskit-nature-pyscf` package (github.com/qiskit-community/qiskit-nature-pyscf) integrates Qiskit Nature + PySCF
- A single unified PennyLane + Qiskit Nature + PySCF three-way tutorial was not found

**source_manifest_id**: `src:doc:pennylane-pyscf-tutorial`

**Action for lead agent**: Update Wave 3A.2 documentation notes. The three-way integration exists but as two separate demos/packages, not a single unified tutorial. Handover note claiming it was "not delivered" should note the PennyLane-PySCF demo IS the closest official resource.

---

## Audit Log Summary

**Total SourceManifest entries written**: 14  
**Total BlockedSourceManifest entries written**: 10

| source_manifest_id | Type | Status |
|---|---|---|
| src:emmo:material | SourceManifest | Confirmed |
| src:emmo:composition | BlockedSourceManifest | Blocked |
| src:emmo:structure | BlockedSourceManifest | Blocked |
| src:emmo:phase | BlockedSourceManifest | Blocked |
| src:emmo:property | SourceManifest | Confirmed |
| src:emmo:process | SourceManifest | Confirmed |
| src:emmo:model | BlockedSourceManifest | Blocked |
| src:emmo:simulation | BlockedSourceManifest | Blocked |
| src:emmo:measurement | SourceManifest | Confirmed |
| src:emmo:reasoning | BlockedSourceManifest | Blocked |
| src:mp:llzo-cubic-mp942733 | BlockedSourceManifest | **CRITICAL** — mp-942733 is tetragonal, not cubic |
| src:mp:llzo-tetragonal-mp942790 | BlockedSourceManifest | Blocked — mp-942790 unverifiable |
| src:paper:llzo-murugan-2007 | SourceManifest | Confirmed |
| src:paper:llzo-awaka-2009 | SourceManifest | Confirmed |
| src:paper:bi2te3-zt-roadmap-2023 | SourceManifest | Confirmed (but not most authoritative) |
| src:paper:bi2te3-snyder-2008 | SourceManifest | Confirmed — recommended addition |
| src:paper:bi2te3-poudel-2008 | SourceManifest | Confirmed — recommended addition |
| src:repo:phaseforgeplus-license | BlockedSourceManifest | Blocked — license unverified |
| src:repo:phaseforgeplus-metadata | SourceManifest | Confirmed — maturity/ESPEI/pip |
| src:license:fairchem-library-mit | SourceManifest | **CORRECTION** — MIT not Apache-2.0 |
| src:license:uma-weights-fair-chemistry-v1 | SourceManifest | Confirmed |
| src:paper:lambench-uma-exclusion | SourceManifest | Confirmed |
| src:license:deepmd-kit-lgpl3 | SourceManifest | Confirmed |
| src:license:dpa3-weights-cc-by-4 | SourceManifest | Confirmed |
| src:paper:lambench-dpa3-rank1 | SourceManifest | Confirmed |
| src:paper:fno-grain-growth-2025 | SourceManifest | Opportunistic — Gap E |
| src:doc:pennylane-pyscf-tutorial | SourceManifest | Opportunistic — Gap G |

**Total entries**: 27 (17 SourceManifest + 10 BlockedSourceManifest)

---

## Patches the Lead Agent Should Apply

### BLOCKING — Fixture Metadata Error

**File**: `fixtures/structures/LLZO/cubic/manifest.json`  
**Problem**: `sources[2].locator = "mp-942733"` is wrong — mp-942733 is tetragonal LLZO.  
**Action**: Remove or flag mp-942733 from cubic manifest. Identify correct cubic LLZO MP ID (use MP API with key, search for Li7La3Zr2O12 space group Ia-3d #230).

### CORRECTION — License Documentation

**Files**: Any source-briefs, adapter comments, or documentation referencing fairchem library as "Apache-2.0"  
**Change**: fairchem library license is **MIT**, not Apache-2.0.  
**Impact**: Non-blocking (MIT is more permissive) but audit accuracy requires correction.

### COSMETIC — Bi2Te3 Citations

**File**: `fixtures/structures/Bi2Te3/manifest.json`  
**Action**: Add `10.1038/nmat2090` (Snyder & Toberer 2008) as a recommended authoritative review. Optionally add `10.1126/science.1156446` (Poudel 2008).

### NON-BLOCKING — EMMO UUID Verification

**File**: `src/zer0pa_materials_workbench/ontology/emmo.py`  
**Action**: Add note to the 6 unverified terms (Composition, Structure, Phase, Model, Simulation, Reasoning) that their UUIDs are pending Wave 4c EMMOntoPy verification. No IRI change required yet.

---

## Downstream Blockers vs. Cosmetic Fixes

| Issue | Severity | Blocks Downstream? |
|---|---|---|
| mp-942733 listed as cubic LLZO fixture source | **HIGH** | Blocks any run claiming MP ID provenance for cubic LLZO fixture |
| mp-942790 for tetragonal unverified | MEDIUM | Blocks MP ID provenance for tetragonal LLZO fixture |
| 6 EMMO UUIDs unverified | LOW | Does not block runtime; annotation-only |
| fairchem library Apache-2.0 → MIT correction | LOW | Does not block runtime; audit accuracy only |
| PhaseForgePlus license unverified | MEDIUM | Correctly default-blocked; do not unblock |
| Bi2Te3 citation upgrade | LOW | Cosmetic only |
| LAMBench UMA exclusion reason imprecision | LOW | Cosmetic only |
