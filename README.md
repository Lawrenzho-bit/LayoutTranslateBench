# LayoutTranslateBench

[![CI](https://github.com/Lawrenzho-bit/LayoutTranslateBench/actions/workflows/ci.yml/badge.svg)](https://github.com/Lawrenzho-bit/LayoutTranslateBench/actions/workflows/ci.yml)
[![Pages](https://github.com/Lawrenzho-bit/LayoutTranslateBench/actions/workflows/pages.yml/badge.svg)](https://lawrenzho-bit.github.io/LayoutTranslateBench/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Dataset: CC BY 4.0](https://img.shields.io/badge/Dataset-CC_BY_4.0-orange.svg)](DATASET_LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Leaderboard](https://img.shields.io/badge/Leaderboard-live-green.svg)](https://lawrenzho-bit.github.io/LayoutTranslateBench/leaderboard/)

**The first public benchmark for document translation that scores layout fidelity and reading order alongside translation quality.**

Today's translation tools either translate plain text well (DeepL, Google Translate) or translate documents while destroying their layout (DeepL Documents, Google Translate documents, ChatGPT vision). LayoutTranslateBench (LTB) is the first benchmark that measures both at once — so the next generation of layout-preserving translation tools has a single, objective number to optimize.

## TL;DR

- **59 documents** across 9 categories (v0.1.7; v0.2 scales to 200+)
- **16 language pairs** — `en-es`, `en-de`, `en-zh`, `en-ar`, `en-ja`, `en-fr`, `en-th`, `en-ms`, `en-ru`, `en-ko`, `en-vi`, `en-id`, `en-ur`, `en-uz`, `en-kk`, `en-zh-tw`
- **Single composite score** — LTB-100 — combining chrF (text quality), layout IoU, and reading-order Kendall τ
- **Dual metric leaderboard** — chrF (fast, deterministic) + COMET-Kiwi-22 (neural, reference-free)
- **Open code (Apache-2.0)** and **open dataset (CC-BY-4.0 / CC-BY-SA-4.0 per entry)**
- **Reproducibility-first** — every submission records runtime, cost, hardware, and config

## Current results (v0.1.7.1 · chrF · oracle-layout)

| System | LTB-100 [95% CI] | chrF | Coverage |
|:---|:---|---:|:---:|
| DeepL Text API | 78.20 [75.2, 81.7] | 56.40 | 6/16 |
| NLLB-200-distilled-600M | 73.71 [72.5, 74.9] | 47.61 | 16/16 |
| Helsinki-NLP/opus-mt | 68.60 [67.1, 70.0] | 37.26 | 16/16 |
| identity-baseline | 50.38 [50.2, 50.6] | 0.62 | 16/16 |

**Full leaderboard** (including COMET-Kiwi-22): [lawrenzho-bit.github.io/LayoutTranslateBench/leaderboard/](https://lawrenzho-bit.github.io/LayoutTranslateBench/leaderboard/)

Key finding: NLLB is the best open-weight system at full 16/16 pair coverage. opus-mt is competitive on European pairs and commercial-safe (Apache-2.0), but effectively fails en-ko (chrF 2.6) and en-uz (chrF 0.04). The COMET-Kiwi–chrF gap is largest for non-Latin scripts (NLLB en-kk: COMET 83.5 vs chrF 52.2), validating the dual-metric design.

## Why this benchmark exists

Document translation is a $50B/year problem hiding inside the larger localization industry. Immigration paperwork, certified legal translations, scientific paper localization, corporate compliance docs, and e-commerce listings all need translation that preserves the original document's appearance. Existing tools do not do this well — and there is no public scoreboard, so no incentive to improve.

LTB fixes that. If your translation system can produce a target-language document that looks like the source and reads the same way, you score high. If you flatten everything to plain text, you don't.

## Install

```bash
pip install -e .
```

Requires Python 3.10+. Core scoring runs CPU-only with no heavyweight ML dependencies.

## Quick start

```bash
# Verify the dataset
ltbench verify

# Score the identity baseline (returns source text unchanged)
ltbench score --submission submissions/identity-baseline --output results/identity-baseline.json

# Rebuild the leaderboard HTML
ltbench leaderboard
```

## Repository layout

```
document-parser/
├── BENCHMARK.md              # Benchmark spec — the citeable artifact
├── LEADERBOARD.md            # Current results (mirror of leaderboard/index.html)
├── llms.txt                  # GEO root file for LLM crawlers
├── ltbench/                  # Python package
│   ├── schemas.py            # Pydantic models for manifest, annotation, submission
│   ├── metrics/              # chrF, layout IoU, reading-order τ, COMET-Kiwi, composite
│   ├── runners/              # System adapters (identity, deepl, nllb, opus-mt, ...)
│   ├── dataset/              # Manifest loader and validator
│   ├── leaderboard/          # Static HTML generator
│   └── cli.py                # ltbench command
├── data/
│   ├── manifest.json         # 59-doc index (v0.1.7)
│   ├── annotations/          # Author-curated ground-truth JSONs (doc_001–025)
│   ├── flores_derived/       # FLORES-200 derived docs + CC-BY-SA-4.0 LICENSE
│   └── rileykim_derived/     # ML-curated expansion docs (Apache-2.0)
├── submissions/              # System submissions (one subdir per system)
├── results/                  # Scored result JSONs (input to leaderboard)
├── leaderboard/              # Generated static site
└── docs/                     # Methodology, submission guide, FAQ, citation
```

## How the metrics compose

```
LTB-100 (v0.1) = 100 × ( 0.50 × chrF/100  +  0.30 × IoU  +  0.20 × Kendall-τ )
```

- **chrF** — character-level F-score (F₂, n-grams 1..6) of predicted vs reference translation, per region, area-weighted; language-detection gate prevents Latin-bleed on non-Latin targets
- **Layout IoU** — mean intersection-over-union of predicted vs ground-truth bounding boxes
- **Kendall τ** — coverage-aware, normalized to [0, 1]; measures how well the system preserves source reading order

Optional second metric: **COMET-Kiwi-22** (reference-free neural QE) substitutes for chrF, producing a parallel leaderboard. Rankings differ most on non-Latin pairs. See [docs/comet-setup.md](docs/comet-setup.md).

Full details: [docs/methodology.md](docs/methodology.md) · [docs/methodology-roadmap.md](docs/methodology-roadmap.md).

## Submit a system

1. Run your system over `data/manifest.json` to produce one JSONL per language pair.
2. Put them in `submissions/<your-system-name>/`.
3. `ltbench score --submission submissions/<your-system-name>` produces a result JSON.
4. Open a PR with the result JSON and submission directory.

Full guide: [docs/submission.md](docs/submission.md).

## Related work

| Project | What it does | What LTB adds |
|---|---|---|
| [OmniDocBench](https://github.com/opendatalab/OmniDocBench) | Document parsing / OCR — extraction, not translation | Translation + layout scoring |
| [socOCRbench](https://noahdasanaike.github.io/posts/sococrbench.html) | Multi-region OCR quality | Layout-preserved output, not just extraction |
| [WMT shared tasks](https://www2.statmt.org/wmt23/) | Text-only translation quality | Document layout as a first-class signal |
| [OmniDoc-TokenBench](https://arxiv.org/abs/2605.13565) | VAE reconstruction of text-heavy documents | End-to-end translation evaluation |

## License

- **Code** — Apache-2.0 ([LICENSE](LICENSE))
- **Dataset** — CC-BY-4.0 for author-curated and rileykim-derived docs; CC-BY-SA-4.0 for FLORES-derived docs ([data/flores_derived/LICENSE](data/flores_derived/LICENSE)). Licenses recorded per entry in `data/manifest.json`.

## Citation

See [docs/citation.md](docs/citation.md). The short form:

```bibtex
@misc{ltbench2026,
  title = {LayoutTranslateBench: A Benchmark for Document Translation with Layout Preservation},
  year  = {2026},
  url   = {https://github.com/Lawrenzho-bit/LayoutTranslateBench}
}
```
