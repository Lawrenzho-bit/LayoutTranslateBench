# LayoutTranslateBench (LTB) — Specification v0.1

LayoutTranslateBench is a public benchmark for **document translation with layout preservation**. It measures whether a translation system produces output that is simultaneously (a) linguistically correct, (b) visually faithful to the source page, and (c) preserves the original reading order of text regions.

Today's translation tools either translate **plain text** (DeepL, Google Translate text mode), or translate **document files but degrade layout** (DeepL Documents, Google Translate documents, ChatGPT vision). LTB is the first benchmark that scores layout fidelity and reading order as first-class signals alongside translation quality.

## Quick facts

- **Name:** LayoutTranslateBench (LTB)
- **Version:** 0.1
- **Documents:** 200 (target) — 10 categories × 20 documents
- **Language pairs:** 8 — `en-es`, `en-de`, `en-zh`, `en-ar`, `en-ja`, `en-fr`, `en-th`, `en-ms`
- **License:** Code Apache-2.0, dataset CC-BY-4.0 (per-doc license recorded in manifest)
- **Composite score:** LTB-100 (range 0–100, higher is better)
- **Submission format:** One JSONL per (system × language pair); see `docs/submission.md`
- **Leaderboard:** `leaderboard/index.html` (regenerated on every accepted submission)

## What LTB measures

Each document in LTB is annotated with text regions. A region is a polygon (or axis-aligned bounding box) containing a contiguous run of text in a single logical block — a heading, a paragraph, a table cell, a stamp, a signature line. Every region carries:

- The original source text
- A reference translation for each of the 5 target languages, produced by a certified translator
- Style hints: font family class (serif / sans / mono / handwritten), size hint, color, background
- A reading-order index (0-based, document-global)
- A layout class (e.g. `single-column`, `two-column`, `form-field`, `table-cell`, `caption`, `header`, `footer`)

A submission for one (system, language pair) is a JSONL of predicted regions: for each source region, the system declares the translated text it produced AND the bounding box where it placed that text in the rendered output. This dual reporting is what lets LTB score both translation and layout simultaneously.

## The five primary metrics

| Metric | Range | What it captures |
|---|---|---|
| **chrF (text quality)** | 0–100 | Character-level F-score against reference translation, per region, weighted by region area |
| **Layout IoU** | 0–1 | Mean IoU of predicted region bboxes against ground-truth bboxes |
| **Reading-order τ** | 0–1 | Normalized Kendall tau between source reading order and predicted reading order |
| **OCR round-trip** *(v0.2)* | 0–1 | OCR the rendered output, compare text to predicted text — catches silent text loss |
| **Visual fidelity** *(v0.2)* | 0–1 | LPIPS on non-text regions — catches destroyed figures, charts, stamps |

Per-region scores are aggregated to a per-document score, then averaged across all documents in the language pair, then across all language pairs.

## The LTB-100 composite

The composite score is a weighted linear combination of normalized metrics:

```
LTB-100 (v0.1) = 100 × (0.50 × chrF/100 + 0.30 × IoU + 0.20 × τ)
LTB-100 (v0.2) = 100 × (0.40 × chrF/100 + 0.25 × IoU + 0.15 × τ + 0.10 × OCR + 0.10 × LPIPS)
```

LTB-100 v0.1 is intentionally biased toward text quality (50%) because translation correctness remains the dominant signal; future versions will rebalance as the field matures.

## Why not just OCR + translate + paste?

This pipeline — what most current tools do — fails on at least four axes that LTB scores explicitly:

1. **Text expansion / contraction.** English → German averages 30% longer; English → Chinese averages 30–50% shorter. Naive pipelines overflow boxes, leave white gaps, or wrap awkwardly. LTB's layout IoU penalizes both.
2. **Reading order collapse.** Multi-column documents, sidebars, footnotes — OCR pipelines frequently flatten reading order. The reading-order τ metric exposes this.
3. **Font / style loss.** A passport that was set in a specific font becomes Helvetica. Visual fidelity (v0.2) catches this.
4. **RTL flips.** English → Arabic requires mirroring of layout. Current tools handle this inconsistently. The composite penalizes failures.

## Document categories (target distribution)

| Category | n | Why it's hard |
|---|---|---|
| Birth / marriage / academic certificates | 20 | Stamps, seals, official fonts, RTL on Arabic source variants |
| Government forms (filled scans) | 20 | Mixed printed + handwritten + checkboxes |
| Legal contract pages | 20 | Long compound terms, multi-column footnotes, defined-term capitalization |
| Scientific paper pages (two-column) | 20 | Equations, captions, citations |
| Slide deck pages | 20 | Mixed visual + text, bullets, callouts |
| Receipts / invoices | 20 | Tabular, abbreviations, currency formatting |
| Business letters | 20 | Letterheads, signatures, addresses |
| Magazine / news pages | 20 | Complex grids, pull-quotes, captions |
| Bank statements / tabular forms | 20 | Dense tables, alignment-sensitive |
| Handwritten or mixed-media | 20 | The hard tier; tests OCR + translate jointly |

## Language pairs and why these eight

- **en→es** — highest-volume Latin pair; immigration, education, e-commerce
- **en→de** — text expansion stress test (~30% longer); DACH market
- **en→zh** — script change + contraction stress test (~30–50% shorter)
- **en→ar** — RTL stress test; mirrors layout; ligature-heavy
- **en→ja** — mixed scripts (kanji + kana + Latin); optional vertical text
- **en→fr** — France launch market; sworn-translation industry baseline; well-supported by commercial systems
- **en→th** — Thai script; **DeepL does not support this pair** — exposes a commercial coverage gap relevant to the Southeast Asia market
- **en→ms** — Bahasa Melayu; **DeepL does not support this pair** — ASEAN hub adjacency to Indonesian (270M speakers)

The inclusion of `en→th` and `en→ms` is deliberate: both are commercially valuable language pairs that current state-of-the-art document-translation APIs (DeepL Documents, etc.) simply do not cover, making them a structural product opportunity that the benchmark surfaces empirically.

Future versions may add `zh-en`, `es-en`, `de-en` (reverse), and additional pairs (`hi`, `pt-br`, `ko`, `vi`, `id`).

## Reproducibility

Every submission must include:

- `manifest_version` — the LTB dataset version evaluated against
- `system_name`, `system_version`, `model_id_or_url` if applicable
- `runner_config` — temperature, prompts, post-processing steps
- `total_runtime_seconds` and `per_doc_runtime_seconds` median
- `hardware` — CPU/GPU model
- `cost_usd` if a paid API was used

Without these, scores are accepted but flagged "unverified" on the leaderboard.

## Submission lifecycle

1. Clone the repo, install `ltbench`.
2. Run your system on `data/manifest.json` and produce JSONL files per language pair.
3. Run `ltbench score --submission submissions/<your-system>/`.
4. Open a PR with the result JSON. Maintainers re-score on a held-out split before promoting to the leaderboard.
5. Held-out split rotates every 90 days to prevent benchmark overfit.

## How to cite

```bibtex
@misc{ltbench2026,
  title  = {LayoutTranslateBench: A Benchmark for Document Translation with Layout Preservation},
  year   = {2026},
  url    = {https://github.com/Lawrenzho-bit/LayoutTranslateBench},
  note   = {Version 0.1}
}
```

See `docs/methodology.md` for full scoring details, `docs/submission.md` for how to submit, `docs/faq.md` for common questions.
