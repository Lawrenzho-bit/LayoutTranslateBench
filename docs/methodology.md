# LayoutTranslateBench — Scoring Methodology

LayoutTranslateBench scores a document translation system on three primary axes — text quality, layout fidelity, and reading-order preservation — and combines them into a single composite score, **LTB-100** (range 0–100, higher is better). This document specifies each metric and the aggregation rules.

> **v0.1.1 methodology update (May 2026):** four post-release methodology corrections were applied to address peer review:
> - **chrF now includes a language-detection penalty** (text in the wrong language scores 0 chrF for that region)
> - **Kendall τ is coverage-aware** (penalises partial-coverage predictions to prevent τ=1.0 free credit on single-region fallback)
> - **Bootstrap 95% CIs** are reported on all LTB-100 scores (1000 percentile resamples, fixed seed)
> - **End-to-end and oracle-layout systems are segregated on the leaderboard** (oracle-layout = predicted bboxes copied from ground truth; these are text-quality upper bounds, not realistic measurements)
>
> See the relevant sections below for specifics. v0.1 result files remain readable; missing CI / system-type fields default to 0 / "end-to-end" for backwards compatibility.

## At a glance

For each (system, language pair, document) triple, the system produces a list of *predicted regions*, each with a `region_id`, a bounding box, the translated text, and a reading-order index. The benchmark matches predicted regions to ground-truth regions, scores each match, aggregates per document, then averages across documents and language pairs.

## Metric 1 — Text quality (chrF)

We use **chrF₂** — character-level F-score with β=2, over character n-grams 1..6. This is the WMT-standard chrF variant.

For each ground-truth region with reference translation _r_ and matched predicted text _h_:

```
chrF₂(h, r) = mean over n∈{1..6} of F₂(char-n-grams(h), char-n-grams(r))
            where F₂(P, R) = 5·P·R / (4·P + R)
```

chrF₂ is robust to morphological variation and tokenization differences across languages, which matters for the eight LTB v0.1 language pairs (`en-es`, `en-de`, `en-zh`, `en-ar`, `en-ja`, `en-fr`, `en-th`, `en-ms` — four of which use non-Latin scripts).

Per-document chrF is the **area-weighted** mean of region chrF scores: regions covering more page area contribute proportionally more, so a title or large body paragraph counts for more than a tiny stamp.

### Language-detection penalty (v0.1.1)

chrF as a metric rewards character n-gram overlap *regardless of whether the output is in the target language*. v0.1 of LTB exposed this as an artifact: the identity baseline (which returns English text) scored chrF ≈ 25 on Latin-script targets via shared Latin characters, proper-noun copying ("Maria Garcia Lopez"), and verbatim numbers/dates.

v0.1.1 introduces a **language-detection gate**: before computing chrF for a region, the predicted text is checked against the target language. If the prediction is confidently *not* in the target language, chrF is forced to **0** for that region.

The check has two layers:

1. **Script-based pre-filter** (non-Latin targets only). For `en-zh`, `en-ja`, `en-ar`, `en-th`, we count the fraction of alphabetic characters in the prediction that fall in the target's Unicode script block (CJK Unified Ideographs for `zh`, Hiragana+Katakana+Han for `ja`, Arabic block for `ar`, Thai block for `th`). If ≥50% are in the target script, accept. If <50%, reject. This is more robust than statistical detectors on short strings.
2. **langdetect** (`langdetect` Python package) for Latin-script targets (`en-es`, `en-de`, `en-fr`, `en-ms`) where script alone is insufficient.

The gate is *permissive*:
- Short strings (<4 alphabetic characters), numbers, currency, and pure punctuation pass without check.
- Detection failures fail open (the prediction gets the benefit of the doubt).
- For `en-ms`, both `ms` (Malay) and `id` (Indonesian) are accepted because they are mutually intelligible and langdetect cannot reliably distinguish them on short strings.

This means the penalty only fires on **confidently wrong-language predictions** (e.g. submitting English text for a Spanish target). It does not penalise paraphrase variation or technical terminology that legitimately remains in the source language.

## Metric 2 — Layout IoU

For each matched region pair `(g, p)` we compute axis-aligned bounding-box IoU:

```
IoU(g, p) = area(g ∩ p) / area(g ∪ p)
```

Per-document layout IoU is the area-weighted mean over all ground-truth regions (unmatched regions count as IoU=0). This rewards systems that place translated text in the same regions of the page as the source.

## Metric 3 — Reading-order Kendall τ

For each document, after region matching, we extract two parallel sequences:

- Ground-truth reading orders of matched regions, in document order
- Predicted reading orders of those same regions

We compute **Kendall τ-b** between these sequences (handles ties), then normalize to [0, 1]:

```
τ_norm = (τ + 1) / 2
```

Edge cases:
- Documents with all unique reading-order indices use standard Kendall τ; ties (rare in well-curated annotations) use τ-b.

### Coverage-aware τ (v0.1.1)

v0.1 had a partial-coverage bug: a system returning only **one** region out of seven ground-truth regions trivially scored τ_norm = 1.0 (single-element sequences are "in order" by definition). This artificially inflated reading-order scores for parser-failure cases.

v0.1.1 scales τ by **coverage**:

```
τ_final = τ_norm × min(1.0, n_matched / n_gt_regions)
```

where `n_matched` is the number of predicted regions that matched a ground-truth region (via exact id or IoU), and `n_gt_regions` is the total ground-truth region count for the document.

Under this rule, the single-region fallback case scores τ_final = 1.0 × (1/7) ≈ 0.14 instead of 1.0 — properly recognising that the system covered only a small fraction of the document.

## Region matching

A predicted region is matched to a ground-truth region by:

1. **Exact `region_id` match** when both sides supply the same identifier.
2. **Greedy IoU match** for any unmatched regions, with `min_iou = 0.10`. Pairs are sorted descending by IoU and matched without replacement.

Predicted regions that fail to match contribute nothing positive — they neither raise nor lower the document's chrF/IoU directly. However, ground-truth regions with no match contribute zero to chrF and IoU and are excluded from the reading-order sequence.

## Aggregation

```
per-region scores  →  area-weighted mean  →  per-document score
per-document scores →  arithmetic mean   →  per-language-pair score
per-language-pair scores → arithmetic mean across pairs with n_docs > 0 → overall
```

Each language pair is weighted equally in the overall score, regardless of document count. This protects against benchmark drift if more documents are added in some categories than others.

## LTB-100 composite

```
LTB-100 (v0.1.1) = 100 × ( 0.50 × chrF_with_lang_check / 100 + 0.30 × IoU + 0.20 × τ_coverage_aware )
```

Weights are intentionally biased toward text quality (50%) — translation correctness remains the dominant signal. They will rebalance in v0.2 when visual fidelity (LPIPS) and OCR round-trip metrics are added.

### Bootstrap confidence intervals (v0.1.1)

Each LTB-100 score is reported with a **95% bootstrap percentile confidence interval** — 1000 resamples with replacement from the per-document scores, fixed seed (42) for reproducibility.

The leaderboard displays scores as `point [CI low, CI high]`. On the v0.1 sample size (N=5 documents per language pair), these CIs are *wide* — that is the methodologically honest signal that **a 5-point gap between two systems is below the noise floor on this sample**. v0.2 will scale to N≥25 per pair, which should tighten CIs by roughly 2×.

### End-to-end vs oracle-layout systems (v0.1.1)

A runner declares `system_type` in its manifest:

- `end-to-end` — the runner produces its own bounding boxes from the source image. This is the realistic measurement.
- `oracle-layout` — the runner copies ground-truth bounding boxes as predictions and only translates the text. This is a **text-quality upper bound**, not a real-world measurement of the underlying product.

The leaderboard segregates the two. Mixing oracle-layout scores with end-to-end scores misleads readers; for example, "DeepL: 78" looks like a measurement of DeepL's product but is actually a measurement of "DeepL's text quality assuming a perfect layout extractor", which DeepL's product does not provide.

## What v0.2 will add

- **OCR round-trip (10% weight)** — OCR the rendered output document, compute chrF against the system's own declared translated text. Catches text that was claimed in the JSONL but not actually rendered.
- **Visual fidelity / LPIPS (10% weight)** — perceptual similarity of non-text regions between the source page and the rendered output. Catches systems that destroy figures, charts, stamps, or backgrounds during translation.

When v0.2 ships, the weights become:

```
LTB-100 (v0.2) = 100 × ( 0.40·chrF/100 + 0.25·IoU + 0.15·τ + 0.10·OCR + 0.10·LPIPS )
```

Submitted v0.1 results remain valid and are displayed alongside v0.2 results with an explicit version label.

## Held-out split

To prevent benchmark overfit, 20% of documents per category are held out and never published in raw form. Submitters score the public split locally; maintainers re-score the held-out split before promoting a result to the leaderboard. The split rotates every 90 days.

## Reproducibility requirements

Every submission must include a `manifest.json` (see `ltbench.schemas.SystemManifest`) containing:

- `system_name`, `system_version`, `manifest_version` (LTB dataset version)
- `model_id_or_url` (HF id, API endpoint, paper URL, or null for proprietary)
- `runner_config` (any tunable that affects the result: prompt, temperature, post-processing)
- `hardware`, `total_runtime_seconds`, `median_per_doc_runtime_seconds`, `cost_usd`

Submissions missing this metadata are accepted but flagged "unverified" on the leaderboard.
