# Runpod Cutover Runbook

> **Boundary**: Research infrastructure for in silico materials science discovery.
> Outputs are research artifacts. No regulatory certification claims.
> No clinical or human-subject use. ITAR / weapons applications are out of scope
> (Meta UMA Acceptable Use Policy and operator policy).

This runbook is the operator guide for promoting the Zer0pa Materials pipeline
from `runpod_mock` to `runpod_rest` — the real GPU backend on Runpod.
The cutover is a **config-flag-only swap**: no architecture changes to
adapters, services, or falsifiers are required.

---

## Prerequisites

Before starting, confirm:

1. Wave 5c parity tests pass: `.venv/bin/python -m pytest tests/parity -v`
2. Foundation tests still pass: `.venv/bin/python -m pytest tests -q`
3. Git status is clean on `main` (no uncommitted state).
4. You have a Runpod.io account with sufficient credits for an A100 pod.
5. You have a Hugging Face account in a verified organization (required for UMA).

---

## Step 1 — Clone the repo on the Runpod machine

SSH into the Runpod pod and run:

```bash
git clone https://github.com/Zer0pa/Materials .
cd Materials
```

Do NOT install GPU/Docker dependencies on your local machine.

---

## Step 2 — Install GPU/Docker dependencies (Runpod only)

```bash
# Python 3.13 venv
python3.13 -m venv .venv
source .venv/bin/activate

# Core + GPU extras (only on Runpod)
pip install -e ".[gpu]"

# Verify GPU visibility
python -c "import torch; print(torch.cuda.device_count(), 'GPU(s) visible')"
```

> **Note**: The `[gpu]` extra includes: `torch`, `cupy`, `qe`, `cp2k-python`,
> `pyscf[gpu]`, `deepmd-kit`, `mace-torch`, `pennylane-lightning-gpu`,
> `phonopy`, `phono3py`, `boltztrappy2`, `amset`, `espei`, `fenicsx`,
> `openfoam`. These are NOT installed locally.

---

## Step 3 — Set backend flags

Copy the template and edit:

```bash
cp .env.example .env.runpod
nano .env.runpod  # or use your preferred editor
```

Set every `*_BACKEND` variable to `runpod_rest`:

```dotenv
MATERIALS_MODE=runpod_rest
ARTIFACT_BACKEND=runpod_rest
KG_BACKEND=runpod_rest
PHASE0_LLM_PROVIDER=runpod_rest
PHASE0_EXTRACTION_BACKEND=runpod_rest
PHASE0_DATABASE_BACKEND=runpod_rest
L6_GENERATOR_BACKEND=runpod_rest
MATERIALS_L1_BACKEND=runpod_rest
IONIC_TRANSPORT_BACKEND=runpod_rest
L15_FORCE_BACKEND=runpod_rest
L15_BAND_BACKEND=runpod_rest
L15_TRANSPORT_BACKEND=runpod_rest
L2_BACKEND=runpod_rest
L3_CALPHAD_PROVIDER=runpod_rest
L3_TDB_FIT_PROVIDER=runpod_rest
L3_MLIP_PRIOR_PROVIDER=runpod_rest
L4_SOLVER=runpod_rest
L5_EXECUTION_MODE=runpod_rest
L5_BACKEND=runpod_rest
L7_ORCHESTRATOR_BACKEND=runpod_rest

# Runpod connectivity
RUNPOD_BASE_URL=https://api.runpod.io/v2/<your-endpoint-id>
RUNPOD_API_TOKEN=<your-runpod-api-token>

# UMA (required for L2 UMA backend)
UMA_HF_ORG=<your-hf-organization-slug>
UMA_HF_TOKEN=<your-hf-read-token>
```

Copy to active .env:

```bash
cp .env.runpod .env
```

---

## Step 4 — Run the precheck

```bash
zer0pa-materials runpod precheck
```

All 7 preconditions must show `PASS`. If any show `BLOCKED`, resolve the
issue and re-run. Common blockers:

| Blocker | Fix |
|---------|-----|
| `RUNPOD_BASE_URL` missing | Set it in `.env` |
| `UMA_HF_ORG` missing | See §UMA-specific AUP verification below |
| `MATERIALS_MODE` wrong | Set `MATERIALS_MODE=runpod_rest` in `.env` |

---

## Step 5 — Run the sentinel campaign

```bash
zer0pa-materials runpod sentinel --backend runpod_rest
```

This runs LLZO, Li6PS5Cl, Li-Mg-Zr-Cl, and Bi2Te3 through every GPU-bound
layer. The sentinel report is written to
`phases/Runpod-cutover/sentinel-report.md`.

Expected duration: ~45-90 minutes for a full run (A100 × all 9 layers × 4 seeds).

---

## Step 6 — Verify parity

```bash
zer0pa-materials runpod parity
```

This runs `tests/parity/` against both the `runpod_mock` baseline and the
just-completed `runpod_rest` sentinel. Every parity test must pass:

| Check | Invariant |
|-------|-----------|
| Schema shape | Same top-level and nested key sets |
| input_hash | Identical for the same input payload |
| Boundary block | Verbatim in every envelope |
| Resource metrics | `gpu_seconds`, `vram_mb`, `wallclock_seconds` present |
| Disagreement | L1/L2/ionic/quantum carry at least one metric |

If parity fails:
1. Check the sentinel report for which layer/seed failed.
2. Run the hard-failure detectors: `zer0pa-materials runpod hard-failures`.
3. Check `phases/Runpod-cutover/parity-result.txt` for detail.

---

## Step 7 — Confirm no downstream code changed

```bash
git diff HEAD --name-only
```

Only files under `services/`, `runpod/`, `tests/parity/`, and `docs/`
should differ from the `runpod_mock` baseline. Any other changes are a
**hard failure** (detector #5: `detect_caller_changes`).

---

## Step 8 — Promote backend from mock to real

```bash
zer0pa-materials runpod precheck  # re-verify
```

If precheck passes with `MATERIALS_MODE=runpod_rest`, the cutover is complete.
No additional command is needed — the `.env` file already has the real flags.

Record the promotion decision:

```bash
python -c "
from zer0pa_materials.runpod.cutover import RunpodCutover, ParityReport
c = RunpodCutover()
r = c.promote_backend('all', 'runpod_mock', 'runpod_rest',
    parity_report=ParityReport(passed=True, schema_drifts={}, hash_mismatches={},
        boundary_failures=[], resource_metric_failures=[], disagreement_failures=[]))
print(r.decision_id, r.reason)
"
```

---

## Rollback procedure

If any step fails after cutover, roll back immediately:

```bash
# On the Runpod pod:
nano .env
# Set MATERIALS_MODE=runpod_mock (or local_cpu)
# Restore all *_BACKEND flags to their pre-cutover values

# Verify
zer0pa-materials runpod precheck

# Notify the lead agent with the checkpoint decision_id
```

Rollback via API:

```bash
python -c "
from zer0pa_materials.runpod.cutover import RunpodCutover
c = RunpodCutover()
result = c.rollback('decision:promote:<your-checkpoint-id>')
print(result['instructions'])
"
```

---

## The 10 hard-failure detectors

Run all detectors:

```bash
zer0pa-materials runpod hard-failures
```

| # | Detector | What triggers it | Fix |
|---|----------|-----------------|-----|
| 1 | `schema_drift` | Top-level or nested key set changed between baseline and candidate | Ensure both backends produce the same Envelope schema |
| 2 | `missing_artifact_hashes` | `input_hash` or `output_hash` absent or not `sha256:<hex>` | Verify `sha256_of()` is called on both payloads |
| 3 | `missing_boundary_block` | `research_boundary` absent or not verbatim | Set `RESEARCH_BOUNDARY` in every adapter |
| 4 | `missing_resource_metrics` | `runpod_*` backend lacks `gpu_seconds`, `vram_mb`, `wallclock_seconds` | Inject `output["resource_metrics"]` in every runpod adapter |
| 5 | `caller_changes` | Code outside `services/`, `runpod/`, `tests/parity/`, `docs/` was modified | Revert unexpected changes before cutover |
| 6 | `lost_audit_provenance` | `audit.audit_record_id` absent, malformed, or not in `audit/runtime/*.jsonl` | Check adapter `_build_*_envelope` and `AuditLog.append_event` |
| 7 | `model_response_without_disagreement` | L1/L2/ionic/quantum envelope has empty `disagreement.metrics` | Add committee energy MAE / force MAE to adapter |
| 8 | `uma_without_hf_aup_gate` | UMA engine detected but `UMA_HF_ORG`/`UMA_HF_TOKEN` not set | See §UMA-specific AUP verification |
| 9 | `bulk_datasets_locally` | File > 5 MB found outside `fixtures/` | Move to Runpod volume or remote store |
| 10 | `falsifier_bypass` | Candidate promoted to L3+ without L1/L2/ionic back-edges | Check L7 gate logic |

---

## UMA-specific HF org + AUP verification

UMA (Universal Model for Atoms, FAIR Chemistry License v1) requires:

1. **Organization membership**: Join the `fair-chemistry` organization on
   Hugging Face: https://huggingface.co/fair-chemistry
2. **License acceptance**: Accept the FAIR Chemistry License v1 and the Meta
   UMA Acceptable Use Policy (AUP) at: https://huggingface.co/facebook/UMA
3. **Set credentials**:
   ```dotenv
   UMA_HF_ORG=fair-chemistry
   UMA_HF_TOKEN=hf_<your-read-token>
   ```
4. **Verify**:
   ```bash
   zer0pa-materials runpod hard-failures --layer L2
   # Detector 8 must show PASS
   ```
5. **Scope**: UMA is used only for L2 MLIP at scale. It is NOT used for
   ITAR / weapons applications (hard-blocked by AUP and operator policy).

> **Boundary reminder**: UMA use is strictly limited to in silico materials
> science research. Regulatory, clinical, ITAR, and weapons applications are
> out of scope and will trigger hard failures.

---

## Environment variable reference

All backend flags, their default values, and their `runpod_rest` targets:

| Flag | Default | Runpod-rest value |
|------|---------|------------------|
| `MATERIALS_MODE` | `local_cpu` | `runpod_rest` |
| `ARTIFACT_BACKEND` | `local_manifest` | `runpod_rest` |
| `KG_BACKEND` | `sqlite_stub` | `runpod_rest` |
| `PHASE0_LLM_PROVIDER` | `stub` | `runpod_rest` |
| `PHASE0_EXTRACTION_BACKEND` | `local_stub` | `runpod_rest` |
| `PHASE0_DATABASE_BACKEND` | `optimade_mock` | `runpod_rest` |
| `L6_GENERATOR_BACKEND` | `stub` | `runpod_rest` |
| `MATERIALS_L1_BACKEND` | `local_cpu` | `runpod_rest` |
| `IONIC_TRANSPORT_BACKEND` | `stub` | `runpod_rest` |
| `L15_FORCE_BACKEND` | `mock` | `runpod_rest` |
| `L15_BAND_BACKEND` | `mock` | `runpod_rest` |
| `L15_TRANSPORT_BACKEND` | `local_cpu` | `runpod_rest` |
| `L2_BACKEND` | `local_stub` | `runpod_rest` |
| `L3_CALPHAD_PROVIDER` | `pycalphad_cpu` | `runpod_rest` |
| `L3_TDB_FIT_PROVIDER` | `espei_cpu` | `runpod_rest` |
| `L3_MLIP_PRIOR_PROVIDER` | `phaseforgeplus_stub` | `runpod_rest` |
| `L4_SOLVER` | `stub` | `runpod_rest` |
| `L5_EXECUTION_MODE` | `local_stub` | `runpod_rest` |
| `L5_BACKEND` | `fenicsx` | `runpod_rest` |
| `L7_ORCHESTRATOR_BACKEND` | `local_prefect` | `runpod_rest` |
| `RUNPOD_BASE_URL` | `None` | Your pod endpoint URL |
| `RUNPOD_API_TOKEN` | `None` | Your Runpod API token |
| `UMA_HF_ORG` | `None` | `fair-chemistry` |
| `UMA_HF_TOKEN` | `None` | Your HF read token |

---

*Generated by Wave 5c — Runpod migration scaffold + parity tests.*
*Boundary block applies to all outputs produced by this pipeline.*
