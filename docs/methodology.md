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

The leaderboard displays scores as `point [CI low, CI high]`. As of v0.1.6 the sample composition is:

- v0.1.3 author-curated: N=10 per CORE pair (all 8 CORE pairs)
- v0.1.4 rileykim ml-curated: +8 en-ja, +7 en-zh
- v0.1.5 FLORES certified-translator: +10 per CORE pair (all 8 CORE pairs)
- **v0.1.6 rileykim extension**: 3 docs each for 8 NEW pairs (en-ru, en-ko, en-vi, en-id, en-ur, en-uz, en-kk, en-zh-tw)

Per-pair counts: N=20 for the 6 CORE non-overlap pairs, N=28 for en-ja, N=27 for en-zh, and N=3 for each of the 8 EXTENSION pairs. CIs on the EXTENSION pairs are deliberately wide — these are coverage proofs, not benchmark-quality samples. v0.2 will scale all 16 pairs to N≥25 and replace author-curated refs with certified-translator multi-references.

The benchmark distinguishes **CORE pairs** (`ltbench.CORE_LANG_PAIRS`, 8 pairs, suitable for headline LTB-100 reporting) from **EXTENSION pairs** (8 more pairs, suitable for testing per-pair coverage of large multilingual systems but at sample sizes that don't support tight ranking).

### Per-pair MT-quality variance (v0.1.6.2 finding)

The opus-mt vs NLLB-200 head-to-head on the v0.1.6 dataset surfaced a useful methodological signal: **per-pair MT quality is highly uneven**, especially among smaller per-language Marian-family models.

Helsinki-NLP/opus-mt comes in two flavors:
- *Single-target* per-pair models (en-es, en-de, en-fr, en-ru, etc.) — generally Apache-2.0 and competitive
- *Multi-target router* models (en-mul, en-poz, en-trk) — Apache-2.0 but trained over many target languages with a prefix-token interface; quality varies by target

On COMET-Kiwi-22 over the v0.1.6 N=59 dataset:

| Pair | opus-mt | NLLB-200-600M | Δ (NLLB - opus) | Note |
|---|---|---|---|---|
| en-es | 76.07 | 77.19 | +1.12 | comparable |
| en-de | 76.42 | 74.70 | -1.72 | **opus-mt wins** |
| en-fr | 76.53 | 77.16 | +0.63 | comparable |
| en-ar | 79.37 | 79.39 | +0.02 | comparable |
| en-zh | 72.54 | 73.66 | +1.12 | comparable |
| en-ru | 53.19 | 50.28 | -2.91 | **opus-mt wins** |
| en-ja | 36.94 | 78.09 | +41.15 | opus-mt collapses (Bible-uedin trained) |
| en-ms | 28.36 | 71.92 | +43.56 | poz-router weak on Standard Malay |
| en-ko | 15.83 | 55.75 | +39.92 | TC-big surprisingly weak |
| en-vi | 40.12 | 68.10 | +27.99 | |
| en-id | 47.70 | 70.06 | +22.35 | |
| en-ur | 42.48 | 78.30 | +35.81 | |
| en-kk | 42.37 | 76.98 | +34.61 | |
| en-uz | 1.24 | 1.36 | +0.13 | both broken; likely ref-quality issue |
| en-zh-tw | 38.53 | 43.52 | +4.99 | both struggle on Traditional Han |
| en-th | 61.27 | 75.99 | +14.72 | mul-router weak |

Implications for downstream consumers:
- **European-market products** can ship opus-mt as the open-source MT default (Apache-2.0, performance within ~3 points of NLLB on en-es/-de/-fr/-ar/-zh/-ru)
- **Asian-market products** need NLLB-200 (CC-BY-NC-4.0, research-only) or a paid commercial API; opus-mt's per-language models on those pairs are below the noise floor
- **The benchmark is doing its job**: it surfaces these per-pair quality gaps that single-number macro-averages would have hidden

This is the kind of finding LTB is designed to enable. Future v0.2 work should investigate whether per-language fine-tuned alternatives (e.g. `staka/fugumt-en-ja`, language-specific Marian variants) close the gap on the weak pairs.

### Weight choice (v0.1.1 empirical ablation)

The 50/30/20 weighting of (chrF, IoU, τ) in the LTB-100 composite is not arbitrary — it was empirically validated post-hoc against three alternatives: (40, 40, 20) balanced, (60, 20, 20) text-heavy, and (33, 33, 33) uniform.

System rankings under all four weight schemes are **identical** (Kendall τ_norm = 1.0 between every pair of rankings), as computed by [`scripts/weight_ablation.py`](../scripts/weight_ablation.py). This means weight choice does not change leaderboard ordering on the four v0.1.1 systems. The 50/30/20 weights remain in production because they communicate the intended emphasis (text quality > layout > reading order) without being arbitrary in their effect.

If a future system enters the leaderboard with chrF / IoU / τ in different relative magnitudes than current systems, the ablation should be re-run; if τ_norm drops below 0.95, the weights are doing real work and the methodology should validate them against human judgment.

### Why this comparison is fair: DeepL Text API vs NLLB (v0.1.1)

A reviewer might object that DeepL's *commercial product* (DeepL Documents) handles document context internally, whereas our runner sends each region to DeepL's Text API separately, stripping context. This would be unfair if we were comparing DeepL Documents to NLLB.

We are not. The `deepl-text-oracle` runner uses DeepL's **Text API**, which is designed to be called per-string. The NLLB runner is similarly called per-region. Both systems receive the same per-region inputs, with the same ground-truth bounding boxes as a free oracle. The comparison is structurally symmetric.

A separate `deepl-documents` runner (operating on PDFs end-to-end) is on the v0.2 roadmap. It will be reported as a distinct row from `deepl-text-oracle` because the inputs differ.

### Remaining open methodology issues (v0.1.1)

This methodology has known limitations beyond what v0.1.1 fixes. See [`methodology-roadmap.md`](methodology-roadmap.md) for the full critique-to-status table, but in brief:

- chrF as the text metric has known weaknesses (paraphrase-blindness, adequacy-blindness). COMET-Kiwi-22 is supported (`ltbench score --text-metric comet-kiwi`); v0.2 will make it the leaderboard default.
- Reference quality is mixed by doc, fully transparent in each annotation's `provenance.grade` field:
  - docs 001–010: **author-curated** (single translation, native-speaker non-professional level)
  - docs 011–025: **ml-curated** (rileykim/multilingual-document, Apache-2.0)
  - **docs 026–035: certified-translator** (FLORES-200, CC-BY-SA-4.0)
  v0.2 will extend certified-translator coverage to all docs and add 2-reference multi-ref scoring.
- No human evaluation correlation has been computed. v0.2 will add ~50 DA judgments to validate the automatic metric.
- Sample size is N=20 for the 6 non-overlap pairs (10 author + 10 FLORES), N=28 for en-ja, N=27 for en-zh. v0.2 will scale to N≥25 author-curated per pair *and* keep the FLORES + rileykim expansions.

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
