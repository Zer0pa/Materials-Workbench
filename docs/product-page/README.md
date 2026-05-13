# Materials Workbench — Product Page

Cell-for-cell replica of the locked ZPE product-page prototype, populated for the **Materials** lane.

- **Lane:** Materials · slot 07 · portfolio `insilico`
- **Headline carried from landing-rd-v3:** *"Materials you can falsify."*
- **Status:** GO (FPO §A.218; STATUS: GO).
- **Voice:** realistic-ambition — CPU control plane is real today; H100 evidence campaign is the next campaign, not the current claim.
- **Hero diagram (#2):** operator-supplied asset pending; pure black placeholder of correct dimensions held in place per FPO §C.4.

## Truth basis

- FPO Dispatch Brief — Product Page Wave — 2026-05-09 §A line 218–234 (`Materials — materials (slot 07) — STATUS: GO`).
- Repo §B.1 line 747 — `KEEP carried headline`.
- Website §C.0–§C.1 universal practitioner layer.
- Landing-rd-v3 carry-over: hero headline, accent span, lane-cat (`MATERIALS · CONTROL PLANE`).
- README at this repo HEAD; `.gpd/STATE.md` for live posture.

## Artifacts

| File | Purpose |
|---|---|
| `index.html` | Locked-prototype replica with lane-owned cells populated. Pretext-driven static page. |
| `_render.mjs` | Playwright render script — produces five screenshots + audit JSON at 1440px and 414px viewports. |
| `audit.json` | Render-time audit: Pretext state, console-error trace, five-metric audit, non-live-green count, stale-label sweep, external-blank-cell list. |

## Screenshots

Rendered PNG screenshots are not committed to this repo (large binaries). They live on Hugging Face at:

**`Zer0pa/Materials-Workbench` (dataset · public)** — receipts/product-page/

Re-render locally with:

```bash
cd docs/product-page
node _render.mjs
```

(Requires Playwright; the script's `executablePath` points at a local Chrome install — adjust for your environment.)

## Lane-owned cells

| Cell | Source of truth |
|---|---|
| 00 Hero (headline, sublabel, body) | FPO §A.220, §A.222; landing-rd-v3 carry-over |
| 01 GAP | FPO §A.224 (CURRENT TECH bound — "GPU-first, audit-second") |
| 02 MARKETS | Lab ethos — market sizing not quoted on research-infrastructure lanes (Repo Protocol §13) |
| 03 VALUE | §A defensible metric: `23/23` falsifier shots fired correctly, 0 misses |
| 04 INSIGHT | FPO §A.223 |
| 05.0 CURRENT TECH | FPO §A.224 |
| 05.1 OUR TECH | FPO §A.225 + README "What We Prove" |
| 05.2 BENCHMARKS | FPO §A.226 + README "Key Metrics" |
| 06 MEASUREMENT | FPO §A.227 |
| 06.1 COMPARATIVE PERFORMANCE | FPO §A.228 |
| 07.1–07.5 KEY METRICS | FPO §A.229 (`null` on 07.5 per FPO §0.3 — no GPU-backed `runpod_rest` artefact yet) |
| 08 DETERMINISM | FPO §A.230 |
| 08.1 WHAT DETERMINISTIC MEANS | FPO §A.231 |
| 08.2 FIDELITY GAP | FPO §A.232 (verbatim non-claim) |
| 09 POSSIBILITY | Lab-anchored question from the falsifier-first wedge |
| 09.1 AMBITION | Recompute discipline as portable primitive |
| 09.2 LIVE PROBE | The 588 Runpod-sim parity surface |
| 09.3 LIVE WORKSTREAM | Pre-H100 cutover gate list |
| 09.4 BATTERY WEDGE | LLZO, Li6PS5Cl, Li-Mg-Zr-Cl seed (FPO §A `00 Hero body bound`) |
| 09.5 THERMOELECTRIC SIDECAR | Bi2Te3, PbTe, SnSe (same source) |
| 09.6 REPLICABLE THIRD-PARTY AUDIT | Falsifier registry as public surface |
| 09.7 PRE-GPU TRIAGE | H100 budget conservation (40–250 hours per `.gpd/STATE.md`) |
| 09.8 FALSIFIER REGISTRY AS PRIMITIVE | 23-falsifier registry layer-implementation-independent |

## Vocabulary discipline

No `BLOCKED` / `FAIL` / `INTERNAL` / `NOT READY` / `PRIVATE_ONLY` / `could` / `might` / `revolutionary` / `seamless` / `holistic` / founder language / campaign prose.

## What this page does not claim

Discovery. H100-backed evidence. Material hits. UMA / HuggingFace / Materials Project / PhaseForgePlus / EMMO closure. See cell 08.2.
