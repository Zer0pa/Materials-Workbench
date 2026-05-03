# Materials Workbench Clean Rename PRD

Boundary: Research infrastructure for in silico materials science discovery. Outputs are research artifacts. No regulatory certification claims. No clinical or human-subject use. ITAR / weapons applications are out of scope (Meta UMA Acceptable Use Policy and operator policy).

## Executive Mandate

Rename the current `Zer0pa/Materials` repository and codebase to **Materials Workbench** cleanly, before broader pre-public use. This is not a cosmetic README edit. This is a repository, package, CLI, module, import, test, documentation, and GitHub identity migration.

The next agent has zero prior context. This document is the source of truth. Do not infer a smaller task. Do not stop after renaming the GitHub repository. Do not stop after a README pass. Do not keep compatibility shims unless this PRD explicitly permits one. Do not declare success while stale import paths or stale commands remain in source, tests, current docs, or packaging metadata.

The operator has approved the new name: **Materials Workbench**.

## Why This Rename Exists

The system is not a static "materials" repo. It is a research workbench for in silico materials discovery: a CPU-side control plane plus Runpod/H100 cutover path for layer adapters, audit trails, falsifiers, evidence packets, and campaign-grade provenance across DFT, phonon/transport, MLIP, CALPHAD, phase-field, continuum, generative, and orchestration layers.

"Materials Workbench" is the approved descriptive name because it is broad enough for the L1-L7 pipeline, does not imply a finished commercial product, and does not overclaim real GPU-backed discovery completion.

## Non-Negotiable Outcome

At completion, a fresh clone of the renamed GitHub repository must install, import, run the CLI, and pass the verification suite under the new identity:

- GitHub repository: `https://github.com/Zer0pa/Materials-Workbench`
- Human display name: `Zer0pa Materials Workbench`
- Short product/workstream name: `Materials Workbench`
- Python distribution name: `zer0pa-materials-workbench`
- Python import package: `zer0pa_materials_workbench`
- Console command: `zer0pa-materials-workbench`
- Repo-root environment variable: `ZER0PA_MATERIALS_WORKBENCH_REPO_ROOT`

The old active identities must be gone from current source, tests, package metadata, and current operator docs:

- `https://github.com/Zer0pa/Materials`
- `Zer0pa/Materials`
- `Zer0pa Materials` when used as the project/workstream identity
- `zer0pa-materials` when used as package or CLI identity
- `zer0pa_materials` when used as import/module identity
- `ZER0PA_MATERIALS_REPO_ROOT`

Historical immutable audit records are exempt only where changing them would corrupt a hash chain or falsification evidence. Every exemption must be listed in the final execution report with the file path, reason, and proof that it is immutable historical evidence rather than live documentation or code.

## Current Known Surface

The repository currently contains a large Python package under `src/zer0pa_materials/`, with approximately 398 source files and approximately 259 Python test files. The current `pyproject.toml` declares:

```toml
[project]
name = "zer0pa-materials"
description = "Zer0pa Materials - research infrastructure for in silico materials science discovery"

[project.scripts]
zer0pa-materials = "zer0pa_materials.cli:app"
```

The current repo-root resolver in `src/zer0pa_materials/repo_root.py` searches for `name = "zer0pa-materials"` and supports `ZER0PA_MATERIALS_REPO_ROOT`. That must be changed to the new distribution name and environment variable.

The current docs include old clone URLs, old CLI commands, and old import examples in `README.md`, `REVIEWER-GUIDE.md`, `EXECUTION-REPORT.md`, `docs/RUNPOD-CUTOVER.md`, `PRD.md`, `HANDOFF-TO-ORCHESTRATOR.md`, `HANDOFF-TO-OVERNIGHT-EXECUTOR.md`, `ORCHESTRATOR-STARTUP-PROMPT.md`, and `OVERNIGHT-EXECUTOR-STARTUP-PROMPT.md`. All active docs must be renamed.

## Hard Boundary

Every artifact you produce or edit must preserve this exact boundary text where a boundary block is present or newly added:

Research infrastructure for in silico materials science discovery. Outputs are research artifacts. No regulatory certification claims. No clinical or human-subject use. ITAR / weapons applications are out of scope (Meta UMA Acceptable Use Policy and operator policy).

Do not weaken this boundary. Do not convert the workbench into a product/service claim. Do not imply regulatory certification, clinical use, human-subject inference, weapons/ITAR use, or completed H100 scientific discovery.

## Scope

### In Scope

1. Rename GitHub repository from `Materials` to `Materials-Workbench`.
2. Update local git remote to the renamed repository URL.
3. Update README front door to the new name while preserving the Lab Front Door first-ten spine.
4. Update all active agent docs, handoffs, startup prompts, reports, and runbooks.
5. Update `pyproject.toml` distribution metadata and console script.
6. Rename the Python package directory from `src/zer0pa_materials/` to `src/zer0pa_materials_workbench/`.
7. Update all source imports, tests, docstrings, service launch commands, CLI examples, type references, and package references.
8. Remove stale generated package metadata such as tracked `src/zer0pa_materials.egg-info/`; regenerate only through install/build tools.
9. Update repo-root resolver names, function names where identity-specific, error messages, and tests.
10. Run the full verification suite in a clean install environment.
11. Commit, push, and remote-verify GitHub main.
12. Produce a final rename execution report with command receipts and SHA receipts.

### Out of Scope

1. Do not change repository visibility.
2. Do not broaden the scientific pipeline or add new H100 functionality.
3. Do not provision Runpod or consume H100 time for this rename.
4. Do not rewrite architecture for style reasons.
5. Do not change the approved scientific boundary.
6. Do not rename generic domain concepts such as "materials science", "materials discovery", `MaterialsConfig`, or `MaterialsKG` unless they are being used specifically as stale project identity.
7. Do not mutate immutable audit hash-chain records to make `rg` output prettier.
8. Do not collapse the anti-demo/non-claim posture into marketing language.

## Rename Map

Use this map consistently.

| Current | New | Required? | Notes |
| --- | --- | --- | --- |
| `Zer0pa/Materials` | `Zer0pa/Materials-Workbench` | Yes | GitHub owner/repo identity |
| `https://github.com/Zer0pa/Materials` | `https://github.com/Zer0pa/Materials-Workbench` | Yes | Include `.git` variants |
| `Zer0pa Materials` | `Zer0pa Materials Workbench` | Yes when project identity | Do not rewrite generic scientific phrases blindly |
| `Materials` repo/project title | `Materials Workbench` | Yes when project identity | Keep "materials" when it means the domain |
| `zer0pa-materials` | `zer0pa-materials-workbench` | Yes for dist/CLI/install | Do not change verified external org strings unless confirmed |
| `zer0pa_materials` | `zer0pa_materials_workbench` | Yes for imports/package/module docs | Old import must fail in clean env |
| `ZER0PA_MATERIALS_REPO_ROOT` | `ZER0PA_MATERIALS_WORKBENCH_REPO_ROOT` | Yes | Backward env shim is forbidden |
| `_materials-repo` | avoid in docs | Yes for docs | Local folder names are not canonical |

## Allowed Exceptions

The old identity may remain only in the following cases:

1. Immutable historical audit JSONL records where changing text would invalidate stored `event_hash` or `prev_hash`.
2. Git history.
3. Local virtualenvs, caches, `.pytest_cache`, build artifacts, or untracked files that are excluded from git.
4. A verified external organization or account string such as an existing Hugging Face organization if and only if changing it would make the code inaccurate. If preserved, document the verification result and reason in the execution report.
5. Historical prose that explicitly says "formerly `Zer0pa/Materials`" in the final rename report only.

No other exceptions are allowed.

## Forbidden Half-States

The following are failure states:

1. GitHub repo renamed but Python package still imports as `zer0pa_materials`.
2. Python package renamed but console command remains `zer0pa-materials`.
3. Tests updated by adding alias imports rather than changing imports.
4. `pyproject.toml` says `zer0pa-materials-workbench` but `repo_root.py` still searches for `zer0pa-materials`.
5. README title changed but runbooks still instruct `git clone https://github.com/Zer0pa/Materials`.
6. New package works only because stale editable install metadata remains in the local venv.
7. Full suite passes because tests still import the old module alias.
8. `runpod` docs point to old CLI commands.
9. A compatibility shim package `zer0pa_materials` exists without explicit operator approval. There is no approval in this PRD.
10. A status note is written claiming completion before a clean install and full suite pass.

## Agent Operating Model

The lead agent owns the rename. Subagents may accelerate the work, but they do not lower the acceptance standard.

If the execution environment supports subagents, use them only with explicit, non-overlapping scopes:

1. **Source/package rename worker:** owns `src/`, import paths, `pyproject.toml`, and package metadata.
2. **Test rename worker:** owns `tests/` and rename-specific tests.
3. **Docs/runbook worker:** owns README, runbooks, handoffs, startup prompts, phase reports used as proof anchors, and clone/CLI/import examples.
4. **Falsification verifier:** read-only until all patches land; runs stale identity scans, clean-install checks, targeted gates, and attempts to find old-name leaks.

Rules for subagents:

- A worker must not edit files outside its assigned scope.
- A worker must not create compatibility shims.
- A worker must not mark success because its own slice passes; only the lead can declare completion after the global gates.
- The lead must inspect and integrate every worker change.
- If subagents are not available, the lead executes every scope directly. Lack of subagents is not a blocker and is not an excuse for a partial rename.
- Re-read this PRD before each acceptance gate. Treat the PRD as the stateful memory, not the chat context.

## Required Execution Sequence

Follow this order. Do not reorder unless a command is impossible, and document any deviation in the final execution report.

### 1. Clone Or Fetch Canonical Main

If no local checkout exists:

```bash
git clone https://github.com/Zer0pa/Materials.git Materials-Workbench-rename
cd Materials-Workbench-rename
```

If a local checkout exists:

```bash
git fetch origin
git checkout main
git pull --ff-only origin main
git status --short --branch
```

The worktree must be clean before edits. If it is not clean, inspect the changes. Do not revert user changes. Commit only your own rename work.

### 2. Create A Rename Branch Locally

Use a branch for safety until the full verification gate passes:

```bash
git checkout -b rename/materials-workbench
```

If the repository policy allows direct main pushes and the branch is fully verified, merge/push according to the push section below. If branch protection requires a PR, open one after verification.

### 3. Inventory The Old Identity Before Editing

Run:

```bash
rg -n "Zer0pa Materials|Zer0pa/Materials|https://github.com/Zer0pa/Materials|zer0pa-materials|zer0pa_materials|ZER0PA_MATERIALS_REPO_ROOT|_materials-repo" \
  --glob '!.git/**' \
  --glob '!.venv/**' \
  --glob '!**/__pycache__/**' \
  --glob '!.pytest_cache/**' \
  .
```

Save the output to the final report summary as "pre-rename identity inventory". Do not paste every line into the report; summarize counts by category.

### 4. Rename The Python Package Directory

Use `git mv`, not copy/delete:

```bash
git mv src/zer0pa_materials src/zer0pa_materials_workbench
```

If `src/zer0pa_materials.egg-info/` is tracked, remove it:

```bash
git rm -r src/zer0pa_materials.egg-info
```

Add or confirm `.gitignore` excludes generated metadata:

```gitignore
*.egg-info/
build/
dist/
```

Do not create a `src/zer0pa_materials/` compatibility package.

### 5. Update Python Imports And Module References

Update every source and test import:

```text
from zer0pa_materials... -> from zer0pa_materials_workbench...
import zer0pa_materials... -> import zer0pa_materials_workbench...
zer0pa_materials. -> zer0pa_materials_workbench.
```

Also update:

- module docstrings
- Sphinx/autodoc references
- FastAPI service launch examples
- `uvicorn zer0pa_materials...` examples
- error messages that name the active package
- test fixture paths that construct `src/zer0pa_materials`
- code comments that tell operators what to import

Do not rename classes like `MaterialsConfig`, `MaterialsKG`, or strings where "materials" is the scientific domain rather than the old project identity.

### 6. Update Packaging And CLI

Edit `pyproject.toml`:

```toml
[project]
name = "zer0pa-materials-workbench"
description = "Zer0pa Materials Workbench - research infrastructure for in silico materials science discovery"

[project.scripts]
zer0pa-materials-workbench = "zer0pa_materials_workbench.cli:app"
```

Update package metadata references everywhere else:

- README install commands
- reviewer guide commands
- Runpod cutover docs
- execution report commands
- startup prompts
- tests that invoke the CLI command
- Typer/CLI help tests

Old command `zer0pa-materials` must not remain as an active command or documented command. Do not keep a console-script alias.

### 7. Update Repo Root Resolver

In the renamed `src/zer0pa_materials_workbench/repo_root.py`:

- `_PYPROJECT_NEEDLE` must be `name = "zer0pa-materials-workbench"`.
- Environment variable must be `ZER0PA_MATERIALS_WORKBENCH_REPO_ROOT`.
- Exception names and messages must say `zer0pa-materials-workbench` or `Materials Workbench`.
- Helper function names may remain generic where possible; identity-specific names should be updated.
- Add or update tests proving:
  - repo root is found by walking from module path;
  - new env var works;
  - old env var does not silently work;
  - old distribution needle does not identify the repo.

### 8. Update README Front Door

Keep the Lab Front Door first-ten spine exactly:

1. `## What This Is`
2. `## Pipeline Mechanics`
3. `## Key Metrics`
4. `## Repo Identity`
5. `## Readiness`
6. `## What We Prove`
7. `## What We Don't Claim`
8. `## Verification Status`
9. `## Proof Anchors`
10. `## Repo Shape`

Requirements:

- Title must be `# Zer0pa Materials Workbench`.
- Lead must be <=30 words.
- Exactly four Key Metrics data rows.
- At most six Proof Anchors.
- Every Proof Anchor path must resolve on GitHub main after push.
- Readiness must say the workbench is ready to start H100 completion, not that scientific completion is achieved.
- Boundary must appear verbatim near the top.
- Keep the anti-demo/no-mock/no-first-green posture.
- Repository URL must be `https://github.com/Zer0pa/Materials-Workbench`.
- CLI examples must use `zer0pa-materials-workbench`.
- Execution surface must use `src/zer0pa_materials_workbench/`.

### 9. Update Active Agent Docs And Runbooks

Update all active human/agent-facing docs:

- `PRD.md`
- `README.md`
- `REVIEWER-GUIDE.md`
- `EXECUTION-REPORT.md`
- `docs/RUNPOD-CUTOVER.md`
- `HANDOFF-TO-ORCHESTRATOR.md`
- `HANDOFF-TO-OVERNIGHT-EXECUTOR.md`
- `ORCHESTRATOR-STARTUP-PROMPT.md`
- `OVERNIGHT-EXECUTOR-STARTUP-PROMPT.md`
- any phase report that serves as an active proof anchor or operator runbook

Rules:

- Update clone URLs.
- Update package/CLI names.
- Update import examples.
- Update source-tree paths.
- Preserve boundary text.
- Preserve blockers and non-claims.
- Do not rewrite historical scientific conclusions unless the old project name is the only thing being changed.

### 10. Update Tests

All tests must import `zer0pa_materials_workbench`. No test may import the old package.

Required test additions or updates:

1. A package import smoke test:

```python
import importlib.util


def test_new_package_imports_and_old_package_is_absent() -> None:
    assert importlib.util.find_spec("zer0pa_materials_workbench") is not None
    assert importlib.util.find_spec("zer0pa_materials") is None
```

2. A CLI wiring test that uses the new command name in subprocess or Typer runner context.
3. A repo-root resolver test for `ZER0PA_MATERIALS_WORKBENCH_REPO_ROOT`.
4. A stale identity scan test or verification script that fails if active source/docs contain forbidden old identity strings outside the explicit allowlist.

### 11. Handle Historical Audit Logs Correctly

Do not mechanically edit committed hash-chain JSONL under `audit/` if the old name appears inside a hashed payload. That can invalidate evidence.

Instead:

1. Leave immutable audit records unchanged.
2. Add a final execution report section named `Historical Old-Name Allowlist`.
3. For every remaining old-name hit, classify it:
   - immutable hash-chain evidence;
   - external verified organization/account;
   - generated ignored local artifact;
   - forbidden active stale identity.
4. Completion requires zero forbidden active stale identity hits.

### 12. Clean Install Verification

Do not trust the existing virtualenv. Create a fresh environment:

```bash
python3 -m venv .venv-rename
. .venv-rename/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -e '.[dev]'
```

Then verify:

```bash
python - <<'PY'
import importlib.util
import zer0pa_materials_workbench

assert importlib.util.find_spec("zer0pa_materials_workbench") is not None
assert importlib.util.find_spec("zer0pa_materials") is None
print(zer0pa_materials_workbench.__name__)
PY
```

Verify CLI:

```bash
zer0pa-materials-workbench --help
zer0pa-materials-workbench runpod parity
```

The old CLI command must fail in the clean environment:

```bash
if [ -x "$VIRTUAL_ENV/bin/zer0pa-materials" ]; then
  echo "FAIL: old CLI command is still installed inside the clean rename venv"
  exit 1
fi
```

### 13. Full Test And Quality Gates

Run:

```bash
ruff check .
pytest -q
```

Expected baseline before rename was approximately 3,547 passing, 2 pycalphad skips. The exact count may change if you add rename tests, but failures are not acceptable.

Run targeted gates:

```bash
pytest -q tests/integration/test_cli_wiring.py
pytest -q tests/parity
pytest -q tests/integration/test_recompute_wired_into_production.py
zer0pa-materials-workbench runpod parity
```

If `runpod precheck --json` blocks because H100 credentials or endpoints are absent, that is acceptable only if it blocks honestly and the report says credentials/endpoints are missing. It must not silently pass. Do not require H100 for this rename.

### 14. Forbidden Identity Scan Gate

After code/test/doc updates and clean install, run:

```bash
rg -n "Zer0pa Materials|Zer0pa/Materials|https://github.com/Zer0pa/Materials|zer0pa-materials|zer0pa_materials|ZER0PA_MATERIALS_REPO_ROOT|_materials-repo" \
  --glob '!.git/**' \
  --glob '!.venv/**' \
  --glob '!.venv-rename/**' \
  --glob '!**/__pycache__/**' \
  --glob '!.pytest_cache/**' \
  --glob '!build/**' \
  --glob '!dist/**' \
  .
```

Every remaining hit must be either:

- in this PRD or the final rename report as historical reference;
- in immutable audit hash-chain records;
- in verified external identity/account references that must remain accurate;
- in generated ignored artifacts.

If a hit is in source code, tests, active README/runbook/handoff docs, package metadata, CLI examples, or current proof anchors, the rename is incomplete.

### 15. GitHub Repository Rename

After local code passes all gates, rename the GitHub repository:

```bash
gh repo rename Materials-Workbench --repo Zer0pa/Materials --yes
```

If this `gh repo rename` form is unavailable in the installed `gh` version, use the GitHub API equivalent:

```bash
gh api -X PATCH repos/Zer0pa/Materials -f name=Materials-Workbench
```

If `gh` says the repo is already renamed, verify:

```bash
gh repo view Zer0pa/Materials-Workbench --json nameWithOwner,url,visibility,defaultBranchRef
```

Do not change visibility.

Update local remote:

```bash
git remote set-url origin https://github.com/Zer0pa/Materials-Workbench.git
git remote -v
```

Push the verified rename branch or main according to policy.

Preferred direct-main path if branch protection allows it:

```bash
git checkout main
git merge --ff-only rename/materials-workbench || git merge --no-ff rename/materials-workbench
git push origin main
```

If direct main push is blocked, push the branch and open a PR. The PR body must contain the full verification receipts.

### 16. Remote Verification

After push or merge, re-read GitHub main:

```bash
git fetch origin
git rev-parse HEAD
git ls-remote origin refs/heads/main
git rev-parse HEAD:README.md
gh api repos/Zer0pa/Materials-Workbench/contents/README.md --jq '.sha'
gh api repos/Zer0pa/Materials-Workbench/contents/pyproject.toml --jq '.sha'
```

Verify every README Proof Anchor resolves on GitHub main. For each anchor:

```bash
gh api repos/Zer0pa/Materials-Workbench/contents/<path> --jq '.sha'
```

Do not declare done until local HEAD, remote `origin/main`, and GitHub API receipts agree.

## Final Execution Report

Create `MATERIALS-WORKBENCH-RENAME-EXECUTION-REPORT.md` at repo root as part of the rename work.

Do not create an impossible self-referential SHA loop. A tracked file cannot know the hash of the commit that contains its own final contents before that commit exists. Therefore:

- the tracked execution report must include all command receipts, test receipts, stale-identity scan results, GitHub rename receipts, and any local/remote SHAs known at the time it is committed;
- the final user-facing handoff must include the final post-push `origin/main` SHA and final GitHub README blob SHA after the last push;
- if a branch/PR is required, the PR body must contain the final verification receipts available for that branch.

It must include:

1. Boundary block verbatim.
2. Old identity and new identity table.
3. Summary of files changed by category.
4. Package/CLI/import rename proof.
5. Clean install command receipts.
6. Full test and targeted gate receipts.
7. Stale identity scan results and allowlist.
8. GitHub rename receipt.
9. Local HEAD SHA at report creation time.
10. `origin/main` or pushed branch SHA at report creation time.
11. README blob SHA from local git at report creation time.
12. README blob SHA from GitHub API after the relevant push/merge when available.
13. Explicit statement that repository visibility was not changed.
14. Explicit statement that Runpod/H100 scientific completion was not claimed.
15. Any blockers if a gate could not run, with exact reason.

Do not write "complete" if any required gate failed.

## Acceptance Gates

All gates must pass.

### Gate A: Identity

- GitHub repo name is `Materials-Workbench`.
- README title is `Zer0pa Materials Workbench`.
- `pyproject.toml` distribution is `zer0pa-materials-workbench`.
- Import package is `zer0pa_materials_workbench`.
- CLI command is `zer0pa-materials-workbench`.
- Old import package is absent in a clean environment.
- Old CLI command is absent in a clean environment.

### Gate B: Source And Tests

- No active source imports `zer0pa_materials`.
- No active test imports `zer0pa_materials`.
- No compatibility shim exists.
- Full `pytest -q` passes.
- `ruff check .` passes or any existing pre-rename lint debt is documented with proof it is unrelated and not worsened. Prefer fixing lint if feasible.

### Gate C: Documentation

- README follows the Lab Front Door first-ten spine.
- Lead is <=30 words.
- Exactly four Key Metrics rows.
- <=6 Proof Anchors.
- Proof Anchor paths resolve on GitHub main.
- Active docs use new repo URL, CLI, and import package.
- Boundary and non-claims are preserved.

### Gate D: Runpod/Cutover Honesty

- Runpod docs use new CLI and repo URL.
- `runpod_rest` is not represented as complete because of this rename.
- Any precheck without H100 credentials blocks honestly.
- No mock-equivalent success path is introduced.

### Gate E: Remote Receipts

- GitHub main is the consuming surface.
- Local HEAD equals `origin/main`.
- GitHub README blob SHA equals local `HEAD:README.md`.
- Final execution report and final handoff together record all SHAs without a self-referential commit-hash loop.

## Estimated Effort

Plan for 6-12 hours. Most work is mechanical, but the test and scan gates are non-optional. The risk is not the text replacement; the risk is stale editable-install state, hidden old imports, broken repo-root detection, old CLI examples, and docs that tell the next H100 agent to clone or run the wrong identity.

## Completion Definition

The task is done only when a different machine can run:

```bash
git clone https://github.com/Zer0pa/Materials-Workbench.git
cd Materials-Workbench
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -e '.[dev]'
python -c "import zer0pa_materials_workbench; print(zer0pa_materials_workbench.__name__)"
zer0pa-materials-workbench --help
pytest -q
zer0pa-materials-workbench runpod parity
```

and the old import/CLI do not exist in that clean environment.

No weaker definition of done is acceptable.
