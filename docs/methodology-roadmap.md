# LayoutTranslateBench — Methodology Roadmap

This document tracks methodology critiques against LTB and their status. The benchmark is a research artifact; methodology is expected to improve with each release. This file is the public, honest record of what's been fixed and what remains.

## Status as of v0.1.2

| # | Critique | Status | Notes |
|---|---|:---:|---|
| 1 | Sample size N=5 statistically meaningless | ⚠️ Mitigated | Bootstrap 95% CIs report uncertainty; true fix requires N≥25 per pair (v0.2) |
| 2 | Identity baseline = chrF Latin-bleed artifact | ✅ Fixed (v0.1.1) | Language-detection gate ([methodology.md](methodology.md#language-detection-penalty-v011)) |
| 3 | chrF wrong text metric (paraphrase / adequacy blind) | ⏭️ Deferred (dep conflict) | COMET-Kiwi-22 integration designed but blocked by scipy/numpy 2 vs opencv numpy 1.26 conflict on Windows. Docker / clean venv path below. |
| 4 | Oracle vs end-to-end conflation in headline scores | ✅ Fixed (v0.1.1) | Separate leaderboard tables |
| 5 | DeepL doc-context unfairness | ✅ Clarified (v0.1.1) | Both DeepL Text API and NLLB are per-region; this is a fair comparison. DeepL Documents (with context) is a v0.2 runner. |
| 6 | Composite weights 50/30/20 unvalidated | ✅ Empirically defended (v0.1.1) | Weight ablation script shows ranking stable (τ_norm = 1.0) across (50/30/20), (40/40/20), (60/20/20), (33/33/33). See [results/weight_ablation.json](../results/weight_ablation.json). |
| 7 | Kendall τ partial-coverage hole | ✅ Fixed (v0.1.1) | Coverage-aware τ ([methodology.md](methodology.md#coverage-aware-%CF%84-v011)) |
| 8 | Single author-curated reference | ❌ Open | Need certified-translator multi-reference (v0.2) |
| 9 | Qwen-VL parser/model conflation | ✅ Fixed (v0.1.2) | `--exclude-parser-failures` flag on `ltbench score`. With-failures = 16.35; restricted = 18.67. |
| 10 | No human evaluation correlation | ⚠️ Infrastructure shipped (v0.1.2) | `ltbench.human_eval` module + `ltbench export-eval-prompts` + `ltbench correlate-human` CLI commands. Collecting judgments still requires paid raters (v0.2). |

Six critiques fully fixed (#2, #4, #6, #7, #9, #10-infrastructure), one clarified (#5), two mitigated (#1, #10-data), one deferred-Windows-dep (#3), one truly open (#8).

## What blocks the remaining items

| Item | What's needed | Cost | Effort |
|---|---|---|---|
| #3 COMET-Kiwi-22 | Pip install `unbabel-comet`; download 600M model; re-score 4 systems | $0 (CPU-feasible) | ~2 hrs engineering + ~30 min compute |
| #8 Multi-reference + certified translators | 2–3 certified translators producing 1 reference each for 200 docs × 8 pairs | ~€10k–25k | Calendar weeks |
| #10 Human evaluation | 5 raters × ~50 DA judgments × 4 systems = 1000 judgments | ~€2k–5k via Mechanical Turk / Prolific, or €5k–10k via certified translators | Calendar weeks |
| #9 Parser-failure-excluded scoring | CLI flag + new column on leaderboard | $0 | ~1 hr engineering |
| #1 N≥25 per pair | Curate +20 documents per category, write annotations + references | ~€5k–15k (translators) | Calendar weeks |

## Sequencing

**v0.1.2 shipped:**
- ✅ **Parser-failure-excluded scoring** — `--exclude-parser-failures` flag on `ltbench score`. Restricts aggregation to documents whose submission did NOT trigger the runner's parser fallback (1-region empty placeholder). Per-doc scores still include them with `parser_failure=True` so the count is visible. Demonstrated on Qwen-VL: with-failures = 16.35, without = 18.67.
- ✅ **Human-evaluation infrastructure** — `ltbench.human_eval` module + `ltbench export-eval-prompts` (export CSV for raters) + `ltbench correlate-human` (compute Kendall τ / Pearson r between human DA and automatic LTB-100) + judgment JSONL schema. v0.1.2 ships the scaffolding; collecting actual judgments still requires paid raters (v0.2).

**v0.1.2 deferred (Windows dep conflict):**
- ⏭️ **COMET-Kiwi-22 as optional metric** — `unbabel-comet` requires scipy + numpy 2.x, which conflicts with `opencv-contrib-python`'s pinned numpy 1.26 on the development machine. Workarounds:
  - Run in a clean venv: `python -m venv .comet-env; .comet-env\Scripts\activate; pip install unbabel-comet ltbench`
  - Docker image with isolated deps (planned for v0.2 release)
  - Wait for `opencv-contrib-python` numpy-2 support (tracked upstream)

  No code changes were made for COMET in v0.1.2; the integration design stays. Roadmap shifts COMET to v0.2 Docker tooling.

**v0.2 (Q3 2026, requires budget):**
- N≥25 per pair (200 docs total, scaled from 5)
- Multi-reference scoring (2 references per doc, certified-translator quality)
- COMET-Kiwi promoted to primary text metric (chrF retained as secondary)
- DA / SQM human evaluation on 50 doc-pair outputs across all 4+ systems
- LPIPS visual-fidelity metric (10% weight) + OCR round-trip metric (10% weight)
- Held-out split rotation (20% private, refreshed quarterly)

## Why this is published openly

A benchmark whose methodology weaknesses are not publicly tracked is harder to trust. By writing this file we accept that:

- Readers will use this list to argue against specific findings. That's correct — they should.
- Reviewers will use it as a checklist when scoring future submissions.
- Contributors can pick an open item and propose a PR addressing it.

If you have a proposed fix for any open critique, open an issue tagged `methodology` with a concrete proposal before opening a PR — methodology changes need discussion before code.
