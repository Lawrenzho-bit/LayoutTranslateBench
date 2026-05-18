# LayoutTranslateBench — Scoring Methodology

LayoutTranslateBench scores a document translation system on three primary axes — text quality, layout fidelity, and reading-order preservation — and combines them into a single composite score, **LTB-100** (range 0–100, higher is better). This document specifies each metric and the aggregation rules.

## At a glance

For each (system, language pair, document) triple, the system produces a list of *predicted regions*, each with a `region_id`, a bounding box, the translated text, and a reading-order index. The benchmark matches predicted regions to ground-truth regions, scores each match, aggregates per document, then averages across documents and language pairs.

## Metric 1 — Text quality (chrF)

We use **chrF₂** — character-level F-score with β=2, over character n-grams 1..6. This is the WMT-standard chrF variant.

For each ground-truth region with reference translation _r_ and matched predicted text _h_:

```
chrF₂(h, r) = mean over n∈{1..6} of F₂(char-n-grams(h), char-n-grams(r))
            where F₂(P, R) = 5·P·R / (4·P + R)
```

chrF₂ is robust to morphological variation and tokenization differences across languages, which matters for the five LTB language pairs (`en-es`, `en-de`, `en-zh`, `en-ar`, `en-ja` — three of which use non-Latin scripts).

Per-document chrF is the **area-weighted** mean of region chrF scores: regions covering more page area contribute proportionally more, so a title or large body paragraph counts for more than a tiny stamp.

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
- Documents with <2 matched regions score τ_norm = 1.0 (no order to violate) if any regions matched, else 0.0.
- Documents with all unique reading-order indices use standard Kendall τ; ties (rare in well-curated annotations) use τ-b.

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
LTB-100 (v0.1) = 100 × ( 0.50 × chrF/100 + 0.30 × IoU + 0.20 × τ_norm )
```

Weights are intentionally biased toward text quality (50%) — translation correctness remains the dominant signal. They will rebalance in v0.2 when visual fidelity (LPIPS) and OCR round-trip metrics are added.

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
