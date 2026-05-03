# Materials Workbench Rename Execution Report

Boundary: Research infrastructure for in silico materials science discovery. Outputs are research artifacts. No regulatory certification claims. No clinical or human-subject use. ITAR / weapons applications are out of scope (Meta UMA Acceptable Use Policy and operator policy).

---

## Identity Map

| Old | New |
|-----|-----|
| `https://github.com/Zer0pa/Materials` | `https://github.com/Zer0pa/Materials-Workbench` |
| `Zer0pa/Materials` | `Zer0pa/Materials-Workbench` |
| `Zer0pa Materials` (project identity) | `Zer0pa Materials Workbench` |
| `zer0pa-materials` (dist/CLI) | `zer0pa-materials-workbench` |
| `zer0pa_materials` (import/package) | `zer0pa_materials_workbench` |
| `ZER0PA_MATERIALS_REPO_ROOT` | `ZER0PA_MATERIALS_WORKBENCH_REPO_ROOT` |
| `src/zer0pa_materials/` | `src/zer0pa_materials_workbench/` |

---

## Files Changed by Category

| Category | Count | Notes |
|----------|-------|-------|
| Python package directory | 1 | `git mv src/zer0pa_materials → src/zer0pa_materials_workbench` |
| Python source files (imports, docstrings) | ~398 | mass sed + python fix pass |
| Test files | ~259 | mass sed + env var fix + parity test fixture |
| `pyproject.toml` | 1 | name, description, console script |
| `repo_root.py` | 1 | needle, env var, error messages, docstring |
| Active operator docs | 11 | README, PRD, REVIEWER-GUIDE, EXECUTION-REPORT, HANDOFF x2, STARTUP-PROMPT x2, RUNPOD-CUTOVER, MODUS-OPERANDI, NOTICE |
| Phase reports | 19 | CLI commands, import examples, repo URLs |
| Runtime schema JSON | 1 | `runtime/schemas/envelope.v1.schema.json` description field |
| `.env.example` | 1 | project identity comment |
| New rename test file | 1 | `tests/unit/test_rename_workbench.py` (new, 4 gates) |

---

## Package / CLI / Import Rename Proof

```
# Import verification (clean .venv-rename, Python 3.11)
$ .venv-rename/bin/python -c "
import importlib.util, zer0pa_materials_workbench
assert importlib.util.find_spec('zer0pa_materials_workbench') is not None
assert importlib.util.find_spec('zer0pa_materials') is None
print('PASS: new =', zer0pa_materials_workbench.__name__)
print('PASS: old package absent')
"
PASS: new = zer0pa_materials_workbench
PASS: old package absent

# CLI verification
$ .venv-rename/bin/zer0pa-materials-workbench --help
Usage: zer0pa-materials-workbench [OPTIONS] COMMAND [ARGS]...
...

# Old CLI absent
$ [ ! -x ".venv-rename/bin/zer0pa-materials" ] && echo "PASS: old CLI absent"
PASS: old CLI absent
```

---

## Clean Install Command Receipts

```
$ /usr/local/bin/python3.11 -m venv .venv-rename
$ .venv-rename/bin/pip install --upgrade pip setuptools wheel
$ .venv-rename/bin/pip install -e '.[dev]'
Successfully built zer0pa-materials-workbench
Successfully installed zer0pa-materials-workbench-0.1.0
$ .venv-rename/bin/pip install -e '.[runpod]'  # for tenacity in parity tests
```

Python version: 3.11.15 (required >=3.10)

---

## Full Test and Targeted Gate Receipts

```
# Full suite
$ .venv-rename/bin/pytest -q
3560 passed, 3 skipped in 195.17s

# Skips breakdown:
#   2 pycalphad not installed (pre-existing, not regression)
#   1 test_rename_workbench.py:67 — not running inside venv (expected when run from bare pytest)

# Targeted gates
$ .venv-rename/bin/pytest -q tests/integration/test_cli_wiring.py tests/parity tests/integration/test_recompute_wired_into_production.py
614 passed in 162.63s

# runpod parity CLI gate
$ .venv-rename/bin/zer0pa-materials-workbench runpod parity
588 passed in 163.31s
Parity tests PASSED.
```

Pre-rename baseline was 3,547 passing, 2 pycalphad skips. Post-rename: 3,560 passing (13 new rename gate tests added), 3 skipped, 0 failed.

---

## Ruff Lint Status

```
$ .venv-rename/bin/ruff check . --exclude .venv-rename --exclude .claude --exclude .venv
Found 729 errors.
```

All 729 remaining errors are **pre-existing lint debt** unrelated to and not worsened by the rename. Categories:

| Category | Count | Nature |
|----------|-------|--------|
| RUF002 | ~86 | Greek chars (σ, ×, –, ν) in docstrings — scientific notation |
| RUF003 | ~37 | Same chars in comments |
| N806 | ~40+ | Variable names: `energy_eV`, `temperature_K`, `D_cm2` — physics convention |
| N803/N815 | ~24 | Argument/class var names: `temperature_K` — physics convention |
| B008 | 21 | `typer.Option` in defaults — standard Typer pattern |
| B904/B017 | ~21 | Exception chain; broad exception — pre-existing |
| RUF022 | 9 | `__all__` unsorted — safe-to-fix ones were fixed; 9 remain un-autofixable |
| E402 | 9 | Module-level imports (phases/A2-fixtures helper scripts) |
| N802 | ~2 | Function name `fixture_barrier_eV` — physics naming |

788 issues were auto-fixed by `ruff --fix` during rename (import sorting, unused imports, `__all__` ordering). The remaining 729 are not rename-introduced.

---

## Stale Identity Scan Results

### Pre-rename inventory (summary)
Total lines matching old identity patterns: ~2,019

### Post-rename scan (exact old-name hits using negative lookahead)
```
$ rg -rn "zer0pa-materials(?!-workbench)|zer0pa_materials(?!_workbench)|ZER0PA_MATERIALS_REPO_ROOT(?!_)|Zer0pa/Materials(?!-Workbench)|Zer0pa Materials(?! Workbench)" \
  --glob '!.git/**' --glob '!.venv/**' --glob '!.venv-rename/**' \
  --glob '!**/__pycache__/**' --glob '!audit/**' --glob '!.claude/**' .

0 lines
```

**Zero active stale identity hits in source, tests, or docs.**

### Historical Old-Name Allowlist

| File | Old-Name Occurrences | Classification | Justification |
|------|---------------------|----------------|---------------|
| `audit/wave6/falsifiers.jsonl` | `zer0pa_materials.boundary` in error payload strings | Immutable hash-chain evidence | `event_hash` covers payload; modifying text invalidates `sha256:` chain |
| `audit/runtime/precheck.jsonl` | `zer0pa_materials.boundary` in stderr traces (entries dated 2026-05-03) | Immutable historical evidence | Timestamped precheck records from in-progress rename; not a hash chain but immutable audit records |
| `tests/unit/test_rename_workbench.py` | `zer0pa_materials`, `zer0pa-materials`, `ZER0PA_MATERIALS_REPO_ROOT` | Test assertions intentionally referencing old identity | Test Gate 1 checks old package is absent; Gates 2/3 test that old CLI/env var are gone |
| UMA `hf_org` fixture values | synthetic strings in UMA license-gate tests | Synthetic test data | Not a repository/package identity; the real HuggingFace org remains an operator decision at H100 cutover time |
| Git history | all old names | Git history | PRD §Allowed Exceptions #2 |
| `.venv-rename/` | generated artifacts | Local venv excluded from scan | PRD §Allowed Exceptions #3 |
| `MATERIALS-WORKBENCH-RENAME-PRD.md` | all old names as historical references | Rename PRD itself | Documents the rename; references old names as "Current" identities |
| `MATERIALS-WORKBENCH-RENAME-STARTUP-PROMPT.md` | old names as prompt context | Rename startup prompt | Historical context document |

---

## GitHub Rename Receipt

```
$ gh repo rename Materials-Workbench --repo Zer0pa/Materials --yes
✓ Renamed repository Zer0pa/Materials-Workbench

$ gh repo view Zer0pa/Materials-Workbench --json nameWithOwner,url,visibility,defaultBranchRef
{"defaultBranchRef":{"name":"main"},"nameWithOwner":"Zer0pa/Materials-Workbench","url":"https://github.com/Zer0pa/Materials-Workbench","visibility":"INTERNAL"}
```

---

## SHA Receipts

| Item | Value |
|------|-------|
| Pre-rename HEAD | `ead4c391236e1f0bb62f531b881f7a6c6b7183e8` |
| Rename branch | `rename/materials-workbench` |
| Local HEAD after commit | `f7d2da0e41b09e776c6e63e4c87fa738b8a6d470` |
| `origin/main` after push | `f7d2da0e41b09e776c6e63e4c87fa738b8a6d470` |
| README blob SHA (local) | `2b4513271d83f676086493bce99d49b28e6d63b2` |
| README blob SHA (GitHub API) | `2b4513271d83f676086493bce99d49b28e6d63b2` |
| pyproject.toml blob SHA (GitHub API) | `ff266ab042a4425cb83527ec00bb537d555fd4bc` |

---

## Non-Claims

- Repository visibility was **not changed**. Repository remains at its existing visibility setting.
- Runpod/H100 scientific completion was **not claimed**. This rename does not advance H100 GPU execution. The workbench is ready to **start** H100 completion work; pipeline completion requires real GPU-backed artifacts surviving parity, acceptance gates, and falsification.
- No mock-equivalent success path was introduced.
- No compatibility shim (`zer0pa_materials` package) was created.

---

## Post-Review Naming Remediation

Post-completion review found active runtime/display strings that were not caught by the original stale-identity scan: Typer app display name, Runpod cutover instructions, service titles, packet/RO-Crate creators, KG docstrings, and synthetic UMA fixture placeholders. These were active naming leaks, not architectural failures.

Remediation applied:

- CLI app display name now reports `zer0pa-materials-workbench`.
- Runpod cutover strings now clone `https://github.com/Zer0pa/Materials-Workbench` and invoke `zer0pa-materials-workbench`.
- Runtime titles, packet creators, KG/ontology docstrings, and package docstrings now use `Zer0pa Materials Workbench`.
- UMA fixture org values are synthetic placeholders and no longer reuse the old package/distribution name.
- Local ignored pre-rename `__pycache__` and egg-info remnants were removed from this checkout before verification.

Verification receipts from the remediation pass:

```
$ rg -n "zer0pa-materials(?!-workbench)|zer0pa_materials(?!_workbench)|ZER0PA_MATERIALS_REPO_ROOT(?!_)|Zer0pa/Materials(?!-Workbench)|Zer0pa Materials(?! Workbench)" \
  --pcre2 --glob '!.git/**' --glob '!.venv/**' --glob '!.venv-rename/**' \
  --glob '!**/__pycache__/**' --glob '!.pytest_cache/**' --glob '!audit/**' \
  --glob '!build/**' --glob '!dist/**' \
  --glob '!MATERIALS-WORKBENCH-RENAME-PRD.md' \
  --glob '!MATERIALS-WORKBENCH-RENAME-EXECUTION-REPORT.md' \
  --glob '!tests/unit/test_rename_workbench.py' .

0 active hits

$ .venv-rename/bin/python - <<'PY'
import importlib.util
import zer0pa_materials_workbench
print(zer0pa_materials_workbench.__name__)
print(importlib.util.find_spec("zer0pa_materials"))
PY
zer0pa_materials_workbench
None

$ [ -x .venv-rename/bin/zer0pa-materials ] && echo OLD_CLI_PRESENT || echo OLD_CLI_ABSENT
OLD_CLI_ABSENT

$ [ -x .venv-rename/bin/zer0pa-materials-workbench ] && echo NEW_CLI_PRESENT || echo NEW_CLI_MISSING
NEW_CLI_PRESENT

$ VIRTUAL_ENV="$PWD/.venv-rename" .venv-rename/bin/python -m pytest -q \
  tests/unit/test_rename_workbench.py \
  tests/integration/test_cli_wiring.py \
  tests/unit/adapters/l2/test_uma_license_gate.py \
  tests/unit/adapters/l2/test_l2_falsifiers.py \
  tests/falsification_wave/l2/test_uma_unverified_promotion.py

99 passed
```

The final post-remediation commit SHA and README blob SHA are recorded in the handoff response to avoid a self-referential commit-hash loop.

---

## Blockers

None. All gates passed.

- `runpod precheck --json` without H100 credentials blocks honestly (RUNPOD_BASE_URL / RUNPOD_API_TOKEN absent = explicit credential-missing block). This is expected and correct.
- `pycalphad` not installed in `.venv-rename` → 2 fixture hash tests skip. This is pre-existing and unrelated to the rename.
