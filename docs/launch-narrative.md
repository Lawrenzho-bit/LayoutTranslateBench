# LayoutTranslateBench v0.1 — Findings

This document records what we measured in v0.1 of the LayoutTranslateBench dataset. It is intentionally written as research — observations and numbers, not recommendations. Methodology lives in [`BENCHMARK.md`](../BENCHMARK.md) and [`docs/methodology.md`](methodology.md); raw scores live under [`results/`](../results/).

## TL;DR

On the v0.1 sample dataset (5 documents × 8 language pairs), four systems were scored:

| Rank | System | LTB-100 | chrF | Layout IoU | Reading-order τ | Coverage |
|---:|:---|---:|---:|---:|---:|:---:|
| 1 | deepl-text-oracle | 84.52 | 69.04 | 1.000 | 1.000 | 6/8 |
| 2 | nllb-text-oracle | 77.58 | 55.17 | 1.000 | 1.000 | **8/8** |
| 3 | identity-baseline | 63.71 | 27.41 | 1.000 | 1.000 | 8/8 |
| 4 | qwen3-vl-2b-instruct | 20.83 | 4.28 | 0.040 | 0.875 | 8/8 |

All four runs cost $0 (DeepL free tier, the rest CPU-local). Total wall-clock to reproduce all four rows: approximately 3 hours.

## How LTB-100 decomposes

The composite score combines three signals, weighted 50/30/20:

```
LTB-100 = 100 × ( 0.50 × chrF/100  +  0.30 × Layout-IoU  +  0.20 × Reading-order-τ )
```

| Metric | Range | What it captures |
|---|---|---|
| chrF (text quality) | 0–100 | Character-level F-score against reference translations |
| Layout IoU | 0–1 | Mean IoU of predicted text-region bounding boxes vs ground truth |
| Reading-order Kendall τ | 0–1 | Normalised order correlation between source and predicted regions |

The composite is biased toward text quality (50%) but the other 50% is layout — a system that translates well and places text poorly does not get full credit.

## Observation 1 — open-weight MT vs commercial MT, oracle layout

When both systems are given oracle bounding boxes (predicted bboxes = ground truth) and asked only to translate, the gap between commercial DeepL and open-source NLLB-200-distilled-600M is smaller than common assumption:

| Pair | DeepL | NLLB-200 | Δ |
|---|---:|---:|---:|
| en-es | 91.23 | 87.15 | −4.1 |
| en-de | 88.46 | 82.32 | −6.1 |
| en-zh | 71.16 | **72.01** | **+0.9** |
| en-ar | 87.11 | 77.97 | −9.1 |
| en-ja | 79.59 | 66.89 | −12.7 |
| en-fr | 89.59 | 81.26 | −8.3 |
| en-th | — | 74.22 | DeepL n=0 |
| en-ms | — | 78.85 | DeepL n=0 |

On en-zh, NLLB-200 scores higher than DeepL on this sample. On the other shared pairs, the average gap is roughly 7 LTB-100 points. The largest gap (en-ja, 12.7 points) and the smallest (en-zh, −0.9) bracket the chrF spread of this small sample.

## Observation 2 — DeepL coverage on en-th and en-ms

DeepL's Text API supports the following target languages as of v0.1 of this benchmark: AR, BG, CS, DA, DE, EL, EN, ES, ET, FI, FR, HU, ID, IT, JA, KO, LT, LV, NB, NL, PL, PT, RO, RU, SK, SL, SV, TR, UK, ZH (source: DeepL API documentation, retrieved 2026-05-18). The pairs **en-th** (Thai) and **en-ms** (Bahasa Melayu) are not in this list. Both pairs are supported by NLLB-200 and were scored on the LTB v0.1 sample.

## Observation 3 — zero-shot VLM bbox grounding on documents

A popular open-weight 2B vision-language model (Qwen3-VL-2B-Instruct) was scored end-to-end (no oracle layout): the model was given the source image and prompted to output both translated text and bounding boxes per region.

| Pair | LTB-100 | chrF | Layout IoU | Reading-order τ |
|---|---:|---:|---:|---:|
| en-es | 20.13 | 5.60 | 0.044 | 0.800 |
| en-de | 19.55 | 4.66 | 0.041 | 0.800 |
| en-zh | 17.85 | 1.62 | 0.035 | 0.800 |
| en-ar | 19.10 | 4.13 | 0.034 | 0.800 |
| en-ja | 22.16 | 1.63 | 0.045 | 1.000 |
| en-fr | 20.02 | 5.88 | 0.036 | 0.800 |
| en-th | 23.16 | 3.97 | 0.039 | 1.000 |
| en-ms | 24.65 | 6.78 | 0.042 | 1.000 |

Overall LTB-100 = 20.83. Layout IoU averages 0.040 across pairs (vs 1.000 for oracle-layout runners), which dominates the composite. Reading order is mostly preserved (mean τ = 0.875). The translation per region is competent on average; the bounding boxes are not.

### Why vision-language models struggle with document bbox grounding

This is an architectural observation, not a quality judgement of the model. Four contributing factors:

1. **Image tokens are coarse.** A vision encoder reduces a typical full-page document (≈ 880k pixels) to 256–1024 patch tokens. Each token covers 850–3,400 source pixels. Pixel-precise bounding boxes are not recoverable at this granularity through a text-decoder.
2. **Coordinates are predicted as text, not regressed.** The model emits coordinate strings character-by-character via autoregressive decoding. There is no spatial inductive bias — no convolutional detection head, no anchor boxes, no IoU loss.
3. **Document layouts are out-of-distribution.** Public VLM pretraining is dominated by natural images, captions, VQA, and free-form OCR. The "identify every text region with pixel-precise bbox + translation" task is rare in pretraining data.
4. **Output coordinate conventions vary.** Qwen-VL family models sometimes emit coordinates normalised to 1000-unit space, sometimes to the model's internal vision resolution. Without explicit rescaling, the output can be off by a constant factor.

The runner in [`ltbench/runners/qwen_vl.py`](../ltbench/runners/qwen_vl.py) implements bbox normalisation that accepts both `(x, y, w, h)` and `(x1, y1, x2, y2)` formats; the residual IoU error after that conversion is what is reported.

## Limitations of v0.1

- **Sample size.** 5 documents × 8 pairs = 40 doc-pair combinations per system. Numbers are indicative; significance testing requires more documents.
- **Author-curated references.** v0.1 references were produced by the project authors with reasonable care, not by certified human translators. v0.2 will replace them.
- **Single VLM size class.** Only Qwen3-VL-2B was scored. Larger Qwen3-VL variants (4B, 8B) and grounding-tuned models (e.g. Florence-2) may score very differently and are deferred to v0.2.
- **Visual fidelity not yet scored.** LPIPS / SSIM on non-text regions and OCR round-trip are documented as v0.2 metrics in [`BENCHMARK.md`](../BENCHMARK.md).
- **One reference per pair.** Multiple-reference scoring is a future option for noisier targets.

## One-paragraph summary

> On LayoutTranslateBench v0.1 — a public, reproducible benchmark for document translation that scores layout fidelity and reading order alongside translation quality — four systems were scored on a 5-document × 8-language-pair sample. Open-source NLLB-200-distilled-600M scored 77.58 LTB-100 across all 8 pairs; commercial DeepL scored 84.52 across the 6 pairs it supports (en-th and en-ms are not in DeepL's supported set). An identity baseline (source text returned unchanged) scored 63.71. A 2B zero-shot vision-language model (Qwen3-VL-2B-Instruct) scored 20.83 end-to-end, with the composite drop attributable primarily to bounding-box predictions (mean IoU 0.040 vs the oracle 1.000). All scores reproduce at zero cost from the repository.

For methodology, reproduction steps, or submitting a new system, see [`BENCHMARK.md`](../BENCHMARK.md), [`docs/methodology.md`](methodology.md), and [`docs/submission.md`](submission.md).
