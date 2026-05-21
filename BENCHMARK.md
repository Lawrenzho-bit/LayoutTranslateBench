# LayoutTranslateBench (LTB) — Specification v0.1

LayoutTranslateBench is a public benchmark for **document translation with layout preservation**. It measures whether a translation system produces output that is simultaneously (a) linguistically correct, (b) visually faithful to the source page, and (c) preserves the original reading order of text regions.

Today's translation tools either translate **plain text** (DeepL, Google Translate text mode), or translate **document files but degrade layout** (DeepL Documents, Google Translate documents, ChatGPT vision). LTB is the first benchmark that scores layout fidelity and reading order as first-class signals alongside translation quality.

## Quick facts

- **Name:** LayoutTranslateBench (LTB)
- **Spec version:** 0.1 | **Dataset version:** 0.1.7
- **Documents:** 59 (v0.1.7) — scaling to 200+ in v0.2
- **Language pairs:** 16 — `en-es`, `en-de`, `en-zh`, `en-ar`, `en-ja`, `en-fr`, `en-th`, `en-ms` (core 8) + `en-ru`, `en-ko`, `en-vi`, `en-id`, `en-ur`, `en-uz`, `en-kk`, `en-zh-tw` (v0.1.6 extension); all 16 covered at v0.1.7
- **License:** Code Apache-2.0; dataset CC-BY-4.0 (author-curated + rileykim-derived) / CC-BY-SA-4.0 (FLORES-derived). Per-doc licenses in `data/manifest.json`.
- **Composite score:** LTB-100 (range 0–100, higher is better)
- **Submission format:** One JSONL per (system × language pair); see `docs/submission.md`
- **Leaderboard:** `leaderboard/index.html` (regenerated on every accepted submission)

## What LTB measures

Each document in LTB is annotated with text regions. A region is a polygon (or axis-aligned bounding box) containing a contiguous run of text in a single logical block — a heading, a paragraph, a table cell, a stamp, a signature line. Every region carries:

- The original source text
- A reference translation for each covered target language pair, produced by a certified translator or via FLORES-200 certified-translator parallel data
- Style hints: font family class (serif / sans / mono / handwritten), size hint, color, background
- A reading-order index (0-based, document-global)
- A layout class (e.g. `single-column`, `two-column`, `form-field`, `table-cell`, `caption`, `header`, `footer`)

A submission for one (system, language pair) is a JSONL of predicted regions: for each source region, the system declares the translated text it produced AND the bounding box where it placed that text in the rendered output. This dual reporting is what lets LTB score both translation and layout simultaneously.

## The primary metrics

| Metric | Range | What it captures |
|---|---|---|
| **chrF (text quality)** | 0–100 | Character-level F-score against reference translation, per region, weighted by region area |
| **Layout IoU** | 0–1 | Mean IoU of predicted region bboxes against ground-truth bboxes |
| **Reading-order τ** | 0–1 | Normalized Kendall tau between source reading order and predicted reading order |
| **COMET-Kiwi-22** *(optional)* | 0–100 | Reference-free neural QE (Unbabel); substitutes for chrF in a parallel leaderboard |
| **OCR round-trip** *(v0.2)* | 0–1 | OCR the rendered output, compare text to predicted text — catches silent text loss |
| **Visual fidelity** *(v0.2)* | 0–1 | LPIPS on non-text regions — catches destroyed figures, charts, stamps |

Per-region scores are aggregated to a per-document score, then averaged across all documents in the language pair, then averaged across all language pairs (macro-average).

## The LTB-100 composite

The composite score is a weighted linear combination of normalized metrics:

```
LTB-100 (v0.1.x) = 100 × (0.50 × chrF/100 + 0.30 × IoU + 0.20 × τ)
LTB-100 (v0.2)   = 100 × (0.40 × chrF/100 + 0.25 × IoU + 0.15 × τ + 0.10 × OCR + 0.10 × LPIPS)
```

LTB-100 v0.1.x is intentionally biased toward text quality (50%) because translation correctness remains the dominant signal; future versions will rebalance as the field matures.

**v0.1.1 methodology corrections** (vs v0.1, applied to all four metrics above):

- **chrF includes a language-detection penalty.** Predictions confidently not in the target language score 0 chrF for that region (fixes Latin-character-bleed-through which inflated the identity baseline in v0.1).
- **τ is coverage-aware.** `τ_final = τ_norm × min(1.0, n_matched / n_gt_regions)` — single-region fallback predictions no longer get free τ=1.0 credit.
- **All LTB-100 scores ship with bootstrap 95% CIs** (1000 resamples, seed 42).
- **End-to-end and oracle-layout systems are segregated on the leaderboard.** Oracle systems are text-quality upper bounds, not realistic measurements.

Full details in [`docs/methodology.md`](docs/methodology.md#language-detection-penalty-v011). Open methodology issues and their fix sequencing are tracked in [`docs/methodology-roadmap.md`](docs/methodology-roadmap.md).

## Why not just OCR + translate + paste?

This pipeline — what most current tools do — fails on at least four axes that LTB scores explicitly:

1. **Text expansion / contraction.** English → German averages 30% longer; English → Chinese averages 30–50% shorter. Naive pipelines overflow boxes, leave white gaps, or wrap awkwardly. LTB's layout IoU penalizes both.
2. **Reading order collapse.** Multi-column documents, sidebars, footnotes — OCR pipelines frequently flatten reading order. The reading-order τ metric exposes this.
3. **Font / style loss.** A passport that was set in a specific font becomes Helvetica. Visual fidelity (v0.2) catches this.
4. **RTL flips.** English → Arabic requires mirroring of layout. Current tools handle this inconsistently. The composite penalizes failures.

## Document categories (v0.1.7 actual distribution)

| Category | n (v0.1.7) | Provenance | Notes |
|---|---:|:---:|---|
| ocr-document | 39 | rileykim ML-curated | Real-world scanned docs from multilingual-document dataset; refs ml-curated then script-validated |
| magazine-news | 11 | 1 author + 10 FLORES | Wikinews articles; FLORES-derived refs are certified-translator quality (CC-BY-SA-4.0) |
| scientific-paper | 2 | author | Two-column layout; citations, equations |
| gov-form | 2 | author | Mixed printed + handwritten; checkboxes |
| certificate | 1 | author | Stamps, seals, official fonts |
| receipt-invoice | 1 | author | Tabular; currency formatting |
| business-letter | 1 | author | Letterhead, signatures, addresses |
| handwritten-mixed | 1 | author | Hard tier; mixed printed + handwritten |
| legal-contract | 1 | author | Multi-column footnotes; defined-term capitalization |

**v0.2 target:** 200 docs, rebalanced to ≥15 per category, all author-curated or certified-translator sourced. Current ocr-document dominance (39/59 = 66%) is expected to decrease significantly.

## Language pairs

### Core 8 (v0.1)

- **en→es** — highest-volume Latin pair; immigration, education, e-commerce
- **en→de** — text expansion stress test (~30% longer); DACH market
- **en→zh** — script change + contraction stress test (~30–50% shorter); Simplified Chinese
- **en→ar** — RTL stress test; mirrors layout; ligature-heavy
- **en→ja** — mixed scripts (kanji + kana + Latin); optional vertical text
- **en→fr** — France launch market; sworn-translation industry baseline; well-supported by commercial systems
- **en→th** — Thai script; **DeepL does not support this pair** — exposes a commercial coverage gap relevant to the Southeast Asia market
- **en→ms** — Bahasa Melayu; **DeepL does not support this pair** — ASEAN hub adjacency to Indonesian (270M speakers)

### Extension 8 (v0.1.6)

- **en→ru** — Cyrillic; largest European language by population; high CIS demand
- **en→ko** — Hangul; South Korean tech/media markets
- **en→vi** — Latin script; Vietnam; Southeast Asia expansion
- **en→id** — Latin script; Indonesian (270M speakers); overlaps en→ms audience
- **en→ur** — Arabic-family script; Pakistan; distinct from Modern Standard Arabic
- **en→uz** — Latin script (post-2018 reform); Uzbekistan; Central Asia
- **en→kk** — Cyrillic; Kazakhstan; Central Asia; underserved in commercial MT
- **en→zh-tw** — Traditional Chinese; Taiwan / Hong Kong / diaspora; distinct from Simplified

**Coverage note (v0.1.7):** All 16 pairs now have ≥ 10 reference documents. At v0.1.6.4, `en-ru` dropped to N=0 after script-validation removed rileykim rows where `tgt_text` was Chinese-script. The v0.1.7 FLORES-200 extension restored `en-ru` to N=10 with certified-translator quality.

Future versions may add reverse directions (`zh-en`, `es-en`, `de-en`) and additional pairs (`hi`, `pt-br`, `sw`).

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
4. Open a PR with the result JSON and submission directory.

## How to cite

```bibtex
@misc{ltbench2026,
  title  = {LayoutTranslateBench: A Benchmark for Document Translation with Layout Preservation},
  year   = {2026},
  url    = {https://github.com/Lawrenzho-bit/LayoutTranslateBench},
  note   = {Spec v0.1, Dataset v0.1.7}
}
```

See `docs/methodology.md` for full scoring details, `docs/submission.md` for how to submit, `docs/faq.md` for common questions.
