# Plug-Swap Acceptance Report

> **Boundary**: Research infrastructure for in silico materials science discovery. Outputs are research artifacts. No regulatory certification claims. No clinical or human-subject use. ITAR / weapons applications are out of scope (Meta UMA Acceptable Use Policy and operator policy).

> **Budget**: register + verify leg < 5.0s per layer.
> Assumption: adapter authoring time (human-bounded, 1–8 h) is not timed.

| Layer | Adapter A | Adapter B | Schema | Audit | Disagreement | Falsifier | Wallclock | Budget |
|---|---|---|---|---|---|---|---|---|
| phase0 | OptimadeFederatedQueryAdapter | LangGraphExtractionWorkflow | OK | OK | OK | OK | 0.017s | YES |
| L1 | PyScfMolecularSolver | QuantumEspressoAiiDASolver | OK | OK | OK | OK | 0.005s | YES |
| quantum | PennyLaneVqeSolver | QiskitNatureVqeSolver | OK | OK | OK | OK | 0.009s | YES |
| L2 | DeepmdDpaCalculatorAdapter | MaceMpCalculatorAdapter | OK | OK | OK | OK | 0.004s | YES |
| ionic | NebMigrationBarrierAdapter | MlipMdDiffusionAdapter | OK | OK | OK | OK | 0.041s | YES |
| L1.5 | PhonopyHarmonicAdapter | Phono3pyAnharmonicBTEAdapter | OK | OK | OK | OK | 0.006s | YES |
| L3 | PyCalphadEquilibriumAdapter | EspeiBayesianFitAdapter | OK | OK | OK | OK | 0.153s | YES |
| L4 | PrismsPfAdapter | MoosePhaseFieldAdapter | OK | OK | OK | OK | 0.009s | YES |
| L5 | FEniCSxContinuumAdapter | DealIIStructuralAdapter | OK | OK | OK | OK | 0.004s | YES |
| L6 | MatterGenGeneratorAdapter | DiffCspGeneratorAdapter | OK | OK | OK | OK | 0.016s | YES |
| L7 | PrefectCampaignAdapter | LangGraphReasonerAdapter | OK | OK | OK | OK | 0.006s | YES |

## Legend
- **OK** — verdict `pass`
- **WARN** — verdict `inconclusive` (informational; not a hard failure)
- **FAIL** — verdict `fail` (hard failure — see individual boundary tests)
- **Budget** — register + verify leg < 5 seconds (YES / NO)
