# LayoutTranslateBench Leaderboard

_Generated 2026-05-19T09:05:00+00:00 from LayoutTranslateBench v0.1.0._

**Caveat — v0.1 sample size.** All scores are computed on N=5 documents per language pair. Reported LTB-100 cell shows `point [95% CI low, CI high]` via 1000-resample percentile bootstrap. The CI on N=5 is *wide* — small differences between systems are not statistically significant. v0.2 will scale the dataset to N≥25 per pair.

## End-to-end systems

*These runners produce their own bounding boxes. This is the realistic real-world score.*

| Rank | System | LTB-100 [95% CI] | chrF | Layout IoU | Reading-order τ | Coverage | Median runtime (s/doc) | Cost (USD) | Hardware |
|---:|:---|:---|---:|---:|---:|:---:|---:|---:|:---|
| 1 | identity-baseline v0.1.0 | 51.32 [50.7, 52.1] | 2.65 | 1.0000 | 1.0000 | 8/8 | — | — | cpu |
| 2 | qwen3-vl-2b-instruct v0.1.0 | 16.35 [14.0, 18.6] | 2.60 | 0.0395 | 0.6935 | 8/8 | 184.90 | $0.0000 | cpu |

## Oracle-layout reference (text-quality ceilings)

*These runners are given **ground-truth bounding boxes** as predictions and only translate the text. They are upper bounds on text-quality, **not** realistic end-to-end measurements of the underlying products. Use for comparing translation quality in isolation from layout-extraction quality.*

| Rank | System | LTB-100 [95% CI] | chrF | Layout IoU | Reading-order τ | Coverage | Median runtime (s/doc) | Cost (USD) | Hardware |
|---:|:---|:---|---:|---:|---:|:---:|---:|---:|:---|
| 1 | deepl-text-oracle v0.1.0 | 78.20 [75.2, 81.7] | 56.40 | 1.0000 | 1.0000 | 6/8 | 0.40 | $0.0000 | api |
| 2 | nllb-text-oracle-nllb-200-distilled-600m v0.1.0 | 72.13 [69.2, 75.0] | 44.25 | 1.0000 | 1.0000 | 8/8 | 11.70 | $0.0000 | cpu |

See [BENCHMARK.md](BENCHMARK.md) for the spec and [docs/submission.md](docs/submission.md) to submit.
