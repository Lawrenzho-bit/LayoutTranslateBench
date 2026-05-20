# LayoutTranslateBench — Methodology Roadmap

This document tracks methodology critiques against LTB and their status. The benchmark is a research artifact; methodology is expected to improve with each release. This file is the public, honest record of what's been fixed and what remains.

## Status as of v0.1.7

| # | Critique | Status | Notes |
|---|---|:---:|---|
| 1 | Sample size N=5 statistically meaningless | ✅ Largely fixed (v0.1.7) | Core 8: N=20 (en-es/de/ar/fr/th/ms), N=27 (en-zh), N=28 (en-ja). Extension 8 (v0.1.7): N=10 for en-ru (certified-only); N=13 each for en-ko/vi/id/ur/uz/kk/zh-tw (10 certified-FLORES + 3 ml-curated rileykim). Industry-grade FLORES-200 refs back every pair. |
| 2 | Identity baseline = chrF Latin-bleed artifact | ✅ Fixed (v0.1.1) | Language-detection gate ([methodology.md](methodology.md#language-detection-penalty-v011)) |
| 3 | chrF wrong text metric (paraphrase / adequacy blind) | ✅ Fixed (v0.1.2 round-2) | COMET-Kiwi-22 ships as a second leaderboard, run on all systems. See [docs/comet-setup.md](comet-setup.md). |
| 4 | Oracle vs end-to-end conflation in headline scores | ✅ Fixed (v0.1.1) | Separate leaderboard tables |
| 5 | DeepL doc-context unfairness | ✅ Clarified (v0.1.1) | Both DeepL Text API and NLLB are per-region; this is a fair comparison. DeepL Documents (with context) is a v0.2 runner. |
| 6 | Composite weights 50/30/20 unvalidated | ✅ Empirically defended (v0.1.1) | Weight ablation script shows ranking stable (τ_norm = 1.0) across (50/30/20), (40/40/20), (60/20/20), (33/33/33). See [results/weight_ablation.json](../results/weight_ablation.json). |
| 7 | Kendall τ partial-coverage hole | ✅ Fixed (v0.1.1) | Coverage-aware τ ([methodology.md](methodology.md#coverage-aware-%CF%84-v011)) |
| 8 | Single author-curated reference | ⚠️ Partially addressed (v0.1.5 + v0.1.7) | FLORES-200 adds industry-grade refs alongside the author-curated set; v0.1.7 extends FLORES coverage to all 16 LTB pairs. Still single-ref per region — multi-ref scoring deferred to v0.2. |
| 9 | Qwen-VL parser/model conflation | ✅ Fixed (v0.1.2) | `--exclude-parser-failures` flag on `ltbench score`. With-failures = 16.35; restricted = 18.67. |
| 10 | No human evaluation correlation | ⚠️ Infrastructure shipped (v0.1.2) | `ltbench.human_eval` module + `ltbench export-eval-prompts` + `ltbench correlate-human` CLI commands. Collecting judgments still requires paid raters (v0.2). |
| 11 | Reference corruption on mined refs (rileykim) | ✅ Fixed (v0.1.6.4) | Script-validation gate at ingest + post-hoc `scripts/validate_extension_refs.py`. Refs whose tgt-text script doesn't match the expected target-language script are dropped. Surfaced en-ru rileykim rows were Chinese-tgt-text — en-ru dropped to N=0. |
| 12 | Open-source MT licensing (NLLB CC-BY-NC) | ✅ Fixed (v0.1.6.2) | Helsinki-NLP/opus-mt runner ships commercial-safe MT at 16/16 coverage (Apache-2.0 / CC-BY-4.0). |
| 13 | Per-pair quality variance for open MT | ✅ Documented (v0.1.6.3) | opus-mt is competitive with NLLB on European pairs, dramatically weaker on Asian / Central Asian. Per-pair gaps recorded in [methodology.md](methodology.md). |

Nine critiques fully fixed (#1, #2, #3, #4, #6, #7, #9, #11, #12), one clarified (#5), two mitigated (#8, #10-data, #10-infrastructure shipped), one documented (#13). No critiques remain truly open at v0.1.6.4 — v0.2 work (#8 multi-ref, #10 human eval, plus visual-fidelity / OCR round-trip metrics) is funded scope, not methodology debt.

## What blocks the remaining items

| Item | What's needed | Cost | Effort |
|---|---|---|---|
| #8 Multi-reference + certified translators | 2–3 certified translators producing 1 reference each for 200 docs × 16 pairs | ~€20k–50k | Calendar weeks |
| #10 Human evaluation (data) | 5 raters × ~50 DA judgments × 4–5 systems = ~1000 judgments | ~€2k–5k via Mechanical Turk / Prolific, or €5k–10k via certified translators | Calendar weeks |
| Extension pair coverage to N≥10 | Curate / certify additional refs on en-ru, en-ko, en-vi, en-id, en-ur, en-uz, en-kk, en-zh-tw (currently N≤3 each, N=0 en-ru) | ~€8k–15k | Calendar weeks |
| Visual fidelity (v0.2) | LPIPS implementation on non-text regions of rendered output | $0 | ~1 week engineering |
| OCR round-trip (v0.2) | Tesseract / PaddleOCR on rendered output, compare to predicted text | $0 | ~1 week engineering |

## Sequencing

**v0.1.2 shipped:**
- ✅ **Parser-failure-excluded scoring** — `--exclude-parser-failures` flag on `ltbench score`. Restricts aggregation to documents whose submission did NOT trigger the runner's parser fallback (1-region empty placeholder). Per-doc scores still include them with `parser_failure=True` so the count is visible. Demonstrated on Qwen-VL: with-failures = 16.35, without = 18.67.
- ✅ **Human-evaluation infrastructure** — `ltbench.human_eval` module + `ltbench export-eval-prompts` (export CSV for raters) + `ltbench correlate-human` (compute Kendall τ / Pearson r between human DA and automatic LTB-100) + judgment JSONL schema. v0.1.2 ships the scaffolding; collecting actual judgments still requires paid raters (v0.2).
- ✅ **COMET-Kiwi-22 integration** — initially deferred in v0.1.2 round 1 due to a numpy version conflict on Windows; resolved in round 2 with the `.comet-env` workflow. All 4 systems scored on both chrF and COMET-Kiwi; both leaderboards published.

**v0.1.3 shipped:** Dataset doubled to N=10 (5 new English-source real-world-template docs).

**v0.1.4 shipped:** rileykim/multilingual-document ML-curated expansion (10 → 25 docs, +8 en-ja, +7 en-zh).

**v0.1.5 shipped:** FLORES-200 industry-grade reference expansion — N=20 on core 8 (10 author-curated + 10 FLORES-200), N=27/28 on en-zh/en-ja.

**v0.1.5.1 shipped:** NLLB-200-distilled-600M + identity-baseline re-scored on the full N=35 corpus with chrF + COMET-Kiwi.

**v0.1.6 shipped:** `LangPair` extended from 8 to 16 (added en-ru, en-ko, en-vi, en-id, en-ur, en-uz, en-kk, en-zh-tw); NLLB runner covers all 16; language-detection gate gets script rules for non-Latin extension pairs; `CORE_LANG_PAIRS` frozen at the v0.1 core 8.

**v0.1.6.1 shipped:** NLLB extension rerun + macro/micro aggregation consistency fix.

**v0.1.6.2 shipped:** Helsinki-NLP/opus-mt runner — 14 models, 16/16 coverage, commercial-safe (Apache-2.0 / CC-BY-4.0). Ship-able where NLLB-200's CC-BY-NC-4.0 is not.

**v0.1.6.3 shipped:** Methodology note documenting opus-mt vs NLLB per-pair quality variance (competitive on European pairs, dramatically weaker on Asian / Central Asian).

**v0.1.6.4 shipped:** fugumt en-ja swap (replaced opus-mt-en-jap with staka/fugumt-en-ja); ingest-time and post-hoc script validation drops rileykim refs whose `tgt_text` script doesn't match expected. After cleanup, en-ru has N=0; other extension pairs retain ≥1.

**v0.1.7 shipped:** FLORES-200 extension-pair refs (`scripts/add_flores_extension_refs.py`) back-fill the 10 FLORES-derived docs (doc_026–doc_035) with certified-translator refs for all 8 v0.1.6 extension pairs. Closes the en-ru gap (0 → 10 docs) and upgrades the 7 surviving extension pairs from ml-curated rileykim refs to a mix of certified-FLORES + ml-curated-rileykim (13 docs each). Now every LTB pair has at least 10 certified-translator-grade reference documents. NOTE: leaderboard scores remain at v0.1.6 numbers until systems are re-run against the new refs — that's a separate scoring milestone.

**v0.2 (next, requires budget):**
- Extension pair coverage to N≥10 each (certified or industry-grade refs)
- Multi-reference scoring (2 references per doc on the core 8, certified-translator quality)
- COMET-Kiwi as the primary metric (chrF retained as secondary)
- DA / SQM human evaluation on 50 doc-pair outputs across 4+ systems
- LPIPS visual-fidelity metric (10% weight) + OCR round-trip metric (10% weight)
- Held-out split rotation (20% private, refreshed quarterly)

## Why this is published openly

A benchmark whose methodology weaknesses are not publicly tracked is harder to trust. By writing this file we accept that:

- Readers will use this list to argue against specific findings. That's correct — they should.
- Reviewers will use it as a checklist when scoring future submissions.
- Contributors can pick an open item and propose a PR addressing it.

If you have a proposed fix for any open critique, open an issue tagged `methodology` with a concrete proposal before opening a PR — methodology changes need discussion before code.
