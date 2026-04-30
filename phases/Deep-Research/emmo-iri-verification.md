# EMMO IRI Verification Table

**Boundary**: Research infrastructure for in silico materials science discovery. Outputs are research artifacts. No regulatory certification claims. No clinical or human-subject use. ITAR / weapons applications are out of scope (Meta UMA Acceptable Use Policy and operator policy).

**Verified against**: EMMO 1.0.3 (released January 2025). Base IRI `https://w3id.org/emmo#`. Modules checked: `disciplines/materials.ttl`, `disciplines/chemistry.ttl`, `disciplines/manufacturing.ttl`, `disciplines/computerscience.ttl`, `foundation/mereocausality.ttl`, `perspectives/semiotics.ttl`, `perspectives/reductionistic.ttl`, `emmo-repo/OIE-Ontologies/models.ttl`, `emmo-repo/domain-characterisation-methodology/chameo.ttl`.

**Retrieval date**: 2026-04-30

---

## Term-by-Term Verification

| Term (emmo.py key) | UUID in emmo.py | Status | Confirmed prefLabel | Confirmed Parent(s) | Source Module | Action Required |
|---|---|---|---|---|---|---|
| **Material** | `EMMO_4207e895_8b83_4318_996a_72cfb32acd94` | ✅ CONFIRMED | `"Material"` | EMMO_6e9cb807 (Mesoscopic), EMMO_bc37743c | `disciplines/materials.ttl` | None — IRI correct. Note: emmo.py lists EMMO_2d23bf12 as parent; Substantial is a higher ancestor, not immediate rdfs:subClassOf. Cosmetic only. |
| **Composition** | `EMMO_25aacccd_5d10_4dad_a6d7_4d5e35e18d10` | ❌ NOT CONFIRMED | — | — | Not found in any checked module | Possible stale UUID from pre-1.0 alpha. EMMO chemistry has `ChemicalComposition` at different UUID. Patch candidate: resolve via EMMOntoPy. |
| **Structure** | `EMMO_8aa4afc1_3e57_4afe_84d1_caa0c4dc5a72` | ❌ NOT CONFIRMED | — | — | Not found | materials.ttl has Crystal (`EMMO_0bb3b434`) and MaterialByStructure (`EMMO_f00fb163`). Possible replacements. |
| **Phase** | `EMMO_b35e92d7_7fa0_4661_b6cb_1be7f9d6f6e0` | ❌ NOT CONFIRMED | — | — | Not found | materials.ttl has PhaseOfMatter at `EMMO_668fbd5b_6f1b_405c_9c6b_d6067bd0595a`. Patch candidate. |
| **Property** | `EMMO_b7bcff25_ffc3_474e_9ab5_01b1664bd4ba` | ✅ CONFIRMED | `"Property"` | (superclass of CharacterisationEnvironmentProperty etc.) | `chameo.ttl` | None — IRI correct. |
| **Process** | `EMMO_43e9a05d_98af_41b4_92f6_00f79a09bfce` | ✅ CONFIRMED | `"Process"` | (used as rdfs:subClassOf in OIE-Ontologies/models.ttl and chameo.ttl) | Multiple downstream repos | None — IRI correct. |
| **Model** | `EMMO_5079e106_4f4f_4e98_897a_a4a4d2bbed47` | ❌ NOT CONFIRMED | — | — | Not found | perspectives/semiotics.ttl has Icon/Simulacrum (EMMO_d7788d1a) with skos:altLabel "Model" but different UUID. Investigate emax.ttl. |
| **Simulation** | `EMMO_e97af6ec_4371_4bbc_8936_2c2ace4d2293` | ❌ NOT CONFIRMED | — | — | Not found | Simulation as subClassOf Process expected but UUID unverifiable from public TTL files. Check emax.ttl. |
| **Measurement** | `EMMO_463bcfda_867b_41d8_a96d_a26034775c0d` | ✅ CONFIRMED | `"Measurement"` | superclass of CharacterisationMeasurementProcess | `chameo.ttl` | None — IRI correct. Definition confirmed: "Process of experimentally obtaining one or more values that can reasonably be attributed to a quantity together with any other available relevant information." |
| **Reasoning** | `EMMO_b863702a_4a3c_4d24_b62f_98edcabd4b07` | ❌ NOT CONFIRMED | — | — | Not found | Reasoning as a Process subclass plausible but UUID unverifiable. Check emax.ttl. |
| **Provenance** | `https://schema.zer0pa.ai/materials#Provenance` | N/A (Zer0pa extension) | `"Provenance"` | `http://www.w3.org/ns/prov#Activity` | Not an EMMO term — deliberate Zer0pa extension mapping to PROV-O | None — design decision, not EMMO IRI. |

---

## Summary

- **Confirmed**: Material, Property, Process, Measurement (4/10 EMMO terms)
- **Not confirmed**: Composition, Structure, Phase, Model, Simulation, Reasoning (6/10)
- **Provenance**: Zer0pa extension — correct by design

## Key finding on confirmed terms

The confirmed terms are verified via downstream domain ontologies (chameo.ttl, OIE-Ontologies), not by directly resolving the EMMO base ontology (which requires the full emax.ttl or a running reasoner). The EMMO 1.0.3 base `emmo.ttl` imports subdiscipline modules; the UUIDs confirmed here appear as superclasses in domain extensions maintained by the EMMO community.

## Recommended patches

For the 6 unconfirmed terms, the lead agent should run:

```python
from emmontopy import get_ontology
onto = get_ontology("https://w3id.org/emmo").load()
for cls in onto.classes():
    print(cls.iri, cls.prefLabel)
```

Or query each IRI directly:
```
curl -L "https://w3id.org/emmo#EMMO_25aacccd_5d10_4dad_a6d7_4d5e35e18d10"
```

If any UUID returns 404, replace with the candidate UUID identified above and update `src/zer0pa_materials/ontology/emmo.py`.

## EMMO version note

EMMO 1.0.3 (2025-01-20) is the current stable release. The base IRI `https://w3id.org/emmo#` is unchanged since 1.0.0 (February 2024). Module renames in 1.0.3 (mereocausality→foundation, emmo-full→emax) do not affect the UUID-based IRIs themselves.
