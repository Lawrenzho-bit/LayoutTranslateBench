# LayoutTranslateBench — FAQ

## What is LayoutTranslateBench?

LayoutTranslateBench (LTB) is the first public benchmark for document translation that scores layout fidelity and reading order alongside translation quality. A submission is judged on whether the translated output reads the same way the source did, looks visually similar, and is linguistically correct — combined into a single LTB-100 score in the range 0–100.

## Why is this needed when WMT and chrF already exist?

WMT shared tasks evaluate *text*-only translation. They do not score whether the translated document preserves the source layout, reading order, or visual style. Modern users translate PDFs, scans, contracts, certificates, and slide decks — and the current tools degrade layout severely on anything beyond plain text. LTB is the first benchmark that measures this directly.

## How is LTB-100 computed?

LTB-100 (v0.1) = 100 × (0.50 × chrF/100 + 0.30 × Layout IoU + 0.20 × Reading-order Kendall τ). Higher is better. Full details in [methodology.md](methodology.md).

## What language pairs are supported?

Five pairs in v0.1: `en-es` (Spanish), `en-de` (German), `en-zh` (Chinese), `en-ar` (Arabic, RTL), `en-ja` (Japanese, mixed scripts). These were chosen to stress different layout effects: text expansion (German), contraction (Chinese), bidirectional flipping (Arabic), and script mixing (Japanese). v0.2 will add reverse directions and additional pairs.

## How big is the dataset?

The full target is 200 documents (10 categories × 20 documents). v0.1 ships 5 documents as a smoke-test sample with synthesized layouts and certified-style references. The full 200-document release is in human-translation curation and rolls out in batches.

## Why a 5-doc sample first?

To let translation system builders and researchers test the scoring pipeline end-to-end before the full dataset lands. The sample exercises every category of metric (chrF, IoU, Kendall τ, composite, aggregation) on real region structures with real references.

## What's a "good" LTB-100 score?

For reference points on the v0.1 sample (5 docs):
- **Identity baseline** (returns source unchanged): high IoU and τ, near-zero chrF — typically LTB-100 around 50 (it gets all the layout credit and none of the translation credit).
- **Plain-text-only translator** (DeepL text mode, manually placed): high chrF, but layout often degrades on multi-column documents.
- **Good document translator** target: LTB-100 > 80 across all language pairs.
- **Ceiling** (human-translated reference rendered to PDF): LTB-100 close to 100.

The held-out split prevents publishing a system tuned to the public split.

## Why not use bilingual visual metrics like DocBLEU?

DocBLEU and similar bilingual visual metrics conflate text quality and layout into a single per-pixel signal, which makes it hard to diagnose *what* a system is doing wrong. LTB reports text, layout, and order as independent axes plus a composite, so improvements on each axis are visible.

## How does LTB relate to OmniDocBench / socOCRbench / OmniDoc-TokenBench?

| Benchmark | Measures | Doesn't measure |
|---|---|---|
| OmniDocBench | Document parsing / extraction quality (markdown/HTML output) | Translation; layout preservation in a target language |
| socOCRbench | OCR quality across regions, scripts, formats | Translation; layout in target language |
| OmniDoc-TokenBench | VAE reconstruction fidelity on text-rich documents | End-to-end translation evaluation |
| **LayoutTranslateBench** | **Translation × layout × reading order, jointly** | Generative quality, sentence-level fluency in isolation |

They are complementary. A system that scores high on OmniDocBench (good extraction) can still score low on LTB if it then translates badly or destroys layout when re-rendering.

## Can I submit a closed/proprietary system?

Yes. The submission requires the system's outputs, not the model weights. Closed-system submissions are scored normally but flagged "unverified" on the leaderboard. To be flagged "verified", maintainers re-score on the held-out split; closed systems can still be verified if the submitter runs the held-out split themselves under maintainer oversight.

## Can I submit a single language pair?

Yes. Partial submissions are scored on the pairs provided; the overall score is the average over populated language pairs. The leaderboard flags partial submissions visually.

## Is there a paid hosted version?

No. LTB is fully open. The code is Apache-2.0, the dataset is CC-BY-4.0, and the leaderboard is regenerated from a static repository. There are no API gates, no rate limits, no paywall on results.

## Who maintains LayoutTranslateBench?

LTB is maintained by the contributors listed in the repository. Contributions to the dataset (especially documents in underrepresented categories or languages), runner adapters, and methodology improvements are welcome via pull request.

## How can I contribute?

- **Documents** — Submit CC-BY-compatible documents with human translations. See [data/README.md](../data/README.md).
- **Runner adapters** — Drop an adapter in `ltbench/runners/`. See [submission.md](submission.md).
- **Methodology** — Open an issue with a proposed metric or aggregation change; methodology changes are versioned and don't invalidate prior submissions.
