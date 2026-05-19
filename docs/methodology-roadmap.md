# LayoutTranslateBench — Methodology Roadmap

This document tracks methodology critiques against LTB and their status. The benchmark is a research artifact; methodology is expected to improve with each release. This file is the public, honest record of what's been fixed and what remains.

## Status as of v0.1.1

| # | Critique | Status | Notes |
|---|---|:---:|---|
| 1 | Sample size N=5 statistically meaningless | ⚠️ Mitigated | Bootstrap 95% CIs report uncertainty; true fix requires N≥25 per pair (v0.2) |
| 2 | Identity baseline = chrF Latin-bleed artifact | ✅ Fixed | Language-detection gate ([methodology.md](methodology.md#language-detection-penalty-v011)) |
| 3 | chrF wrong text metric (paraphrase / adequacy blind) | ❌ Open | Need COMET-Kiwi-22 (see below) |
| 4 | Oracle vs end-to-end conflation in headline scores | ✅ Fixed | Separate leaderboard tables |
| 5 | DeepL doc-context unfairness | ✅ Clarified | Both DeepL Text API and NLLB are per-region; this is a fair comparison. DeepL Documents (with context) is a v0.2 runner. |
| 6 | Composite weights 50/30/20 unvalidated | ✅ Fixed (empirically) | Weight ablation script shows ranking stable (τ_norm = 1.0) across (50/30/20), (40/40/20), (60/20/20), (33/33/33). See [results/weight_ablation.json](../results/weight_ablation.json). |
| 7 | Kendall τ partial-coverage hole | ✅ Fixed | Coverage-aware τ ([methodology.md](methodology.md#coverage-aware-%CF%84-v011)) |
| 8 | Single author-curated reference | ❌ Open | Need certified-translator multi-reference (v0.2) |
| 9 | Qwen-VL parser/model conflation | ⚠️ Partial | `parser_failures` column displayed on leaderboard. Full fix = restrict scoring to successfully-parsed docs (v0.1.2). |
| 10 | No human evaluation correlation | ❌ Open | Need paid rater DA/SQM judgments (v0.2) |

Three critiques shipped fully fixed (#2, #4, #7), two clarified or empirically defended (#5, #6), two mitigated (#1, #9), three remain open (#3, #8, #10).

## What blocks the remaining items

| Item | What's needed | Cost | Effort |
|---|---|---|---|
| #3 COMET-Kiwi-22 | Pip install `unbabel-comet`; download 600M model; re-score 4 systems | $0 (CPU-feasible) | ~2 hrs engineering + ~30 min compute |
| #8 Multi-reference + certified translators | 2–3 certified translators producing 1 reference each for 200 docs × 8 pairs | ~€10k–25k | Calendar weeks |
| #10 Human evaluation | 5 raters × ~50 DA judgments × 4 systems = 1000 judgments | ~€2k–5k via Mechanical Turk / Prolific, or €5k–10k via certified translators | Calendar weeks |
| #9 Parser-failure-excluded scoring | CLI flag + new column on leaderboard | $0 | ~1 hr engineering |
| #1 N≥25 per pair | Curate +20 documents per category, write annotations + references | ~€5k–15k (translators) | Calendar weeks |

## Sequencing

**v0.1.2 (this month, no budget):**
- COMET-Kiwi-22 as optional metric — adds `--text-metric comet-kiwi` flag to `ltbench score`. Reports alongside chrF. Doesn't replace chrF in the production composite yet.
- Parser-failure-excluded scoring — `--exclude-parser-failures` flag on `ltbench score`. New column on the leaderboard alongside the headline score.

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
