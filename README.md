# LayoutTranslateBench

**The first public benchmark for document translation that scores layout fidelity and reading order alongside translation quality.**

Today's translation tools either translate plain text well (DeepL, Google Translate) or translate documents while destroying their layout (DeepL Documents, Google Translate documents, ChatGPT vision). LayoutTranslateBench (LTB) is the first benchmark that measures both at once — so the next generation of layout-preserving translation tools has a single, objective number to optimize.

## TL;DR

- **200 documents** across 10 categories, 5 language pairs (`en-es`, `en-de`, `en-zh`, `en-ar`, `en-ja`)
- **Single composite score** — LTB-100 — combining text quality (chrF), layout IoU, and reading-order Kendall τ
- **Open code (Apache-2.0)** and **open dataset (CC-BY-4.0)**
- **Leaderboard** updated on every accepted submission, with held-out split rotated quarterly
- **Reproducibility-first** — every submission records runtime, cost, hardware, and config

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
# Verify the included sample dataset
ltbench verify

# Score the identity baseline (returns source text unchanged) on the sample
ltbench score --submission submissions/identity-baseline --output results/identity-baseline.json

# Rebuild the leaderboard HTML
ltbench leaderboard
```

## Repository layout

```
document-parser/
├── BENCHMARK.md              # The spec — the citeable artifact
├── LEADERBOARD.md            # Current results (mirror of leaderboard/index.html)
├── llms.txt                  # GEO root file for LLM crawlers
├── ltbench/                  # Python package
│   ├── schemas.py            # Pydantic models for manifest, annotation, submission
│   ├── metrics/              # chrF, layout IoU, reading-order Kendall τ, composite
│   ├── runners/              # System adapters (identity, deepl, google, qwen, ...)
│   ├── dataset/              # Manifest loader and validator
│   ├── leaderboard/          # Static HTML generator
│   └── cli.py                # ltbench command
├── data/
│   ├── manifest.json         # The 200-doc index (v0.1 ships 5 samples)
│   └── annotations/          # Per-doc ground-truth JSON files
├── submissions/              # System submissions (one subdir per system)
├── results/                  # Scored result JSONs (input to leaderboard)
├── leaderboard/              # Generated static site
└── docs/                     # Methodology, submission guide, FAQ, citation
```

## How the metrics compose

```
LTB-100 (v0.1) = 100 × ( 0.50 × chrF/100  +  0.30 × IoU  +  0.20 × Kendall-τ )
```

- **chrF** — character-level F-score (F₂, n-grams 1..6) of predicted vs reference translation, per region, area-weighted
- **Layout IoU** — mean intersection-over-union of predicted vs ground-truth bounding boxes
- **Kendall τ** — normalized to [0, 1], measures how well the system preserves source reading order

Full details in [docs/methodology.md](docs/methodology.md).

## Submit a system

1. Run your system over `data/manifest.json` to produce one JSONL per language pair.
2. Put them in `submissions/<your-system-name>/`.
3. `ltbench score --submission submissions/<your-system-name>` produces a result JSON.
4. Open a PR with the JSON. We re-score against the held-out split and update the leaderboard.

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
- **Dataset** — CC-BY-4.0 ([DATASET_LICENSE](DATASET_LICENSE)); individual document licenses recorded per entry in `data/manifest.json`

## Citation

See [docs/citation.md](docs/citation.md). The short form:

```bibtex
@misc{ltbench2026,
  title = {LayoutTranslateBench: A Benchmark for Document Translation with Layout Preservation},
  year  = {2026},
  url   = {https://github.com/Lawrenzho-bit/LayoutTranslateBench}
}
```
