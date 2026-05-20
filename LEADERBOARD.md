# LayoutTranslateBench Leaderboard

_Generated 2026-05-20T16:15:08+00:00 from LayoutTranslateBench v0.1.0._

**Sample size — v0.1.6.** Core 8 pairs: N=20 for en-es/en-de/en-ar/en-fr/en-th/en-ms, N=28 for en-ja, N=27 for en-zh. Extension 8 pairs (v0.1.6): N=3 each for en-ko/en-vi/en-id/en-ur/en-uz/en-kk/en-zh-tw; N=0 for en-ru (rileykim labeling bug removed all refs at v0.1.6.4 script-validation). LTB-100 cell shows `point [95% CI low, CI high]` via 1000-resample percentile bootstrap. Coverage column shows pairs with ≥1 scored doc.

**Metric.** Two parallel leaderboards are shown — **chrF** (character-level F-score, fast, deterministic, paraphrase-blind) and **COMET-Kiwi-22** (reference-free neural MT quality estimation, slower but more correlated with human judgment). System rankings can differ between metrics, especially for systems that paraphrase well.

---

# Leaderboard A — chrF

## End-to-end systems (chrF)

*These runners produce their own bounding boxes. This is the realistic real-world score.*

| Rank | System | LTB-100 [95% CI] | chrF | Layout IoU | Reading-order τ | Coverage | Median runtime (s/doc) | Cost (USD) | Hardware |
|---:|:---|:---|---:|---:|---:|:---:|---:|---:|:---|
| 1 | identity-baseline v0.1.0 | 50.53 [50.3, 50.8] | 1.12 | 1.0000 | 1.0000 | 15/16 | — | — | cpu |
| 2 | qwen3-vl-2b-instruct v0.1.0 | 16.35 [14.0, 18.6] | 2.60 | 0.0395 | 0.6935 | 8/16 | 184.90 | $0.0000 | cpu |

## Oracle-layout reference (chrF)

*Given **ground-truth bounding boxes** as predictions; only the text is translated. These are upper bounds on text-quality, **not** realistic end-to-end measurements.*

| Rank | System | LTB-100 [95% CI] | chrF | Layout IoU | Reading-order τ | Coverage | Median runtime (s/doc) | Cost (USD) | Hardware |
|---:|:---|:---|---:|---:|---:|:---:|---:|---:|:---|
| 1 | deepl-text-oracle v0.1.0 | 78.20 [75.2, 81.7] | 56.40 | 1.0000 | 1.0000 | 6/16 | 0.40 | $0.0000 | api |
| 2 | nllb-text-oracle-nllb-200-distilled-600m v0.1.0 | 74.02 [72.7, 75.4] | 42.87 | 1.0000 | 1.0000 | 15/16 | — | — | cpu |
| 3 | opus-mt-text-oracle v0.1.0 | 69.16 [67.6, 70.9] | 30.95 | 1.0000 | 1.0000 | 15/16 | — | — | cpu |

---

# Leaderboard B — COMET-Kiwi-22

*COMET-Kiwi is reference-free; the per-region chrF column shown above is replaced by the COMET-Kiwi score (also in [0, 100], higher = better).*

## End-to-end systems (COMET-Kiwi)

*These runners produce their own bounding boxes. This is the realistic real-world score.*

| Rank | System | LTB-100 [95% CI] | COMET-Kiwi | Layout IoU | Reading-order τ | Coverage | Median runtime (s/doc) | Cost (USD) | Hardware |
|---:|:---|:---|---:|---:|---:|:---:|---:|---:|:---|
| 1 | identity-baseline v0.1.0 | 50.66 [50.4, 51.0] | 1.70 | 1.0000 | 1.0000 | 15/16 | — | — | cpu |
| 2 | qwen3-vl-2b-instruct v0.1.0 | 22.79 [18.6, 27.1] | 15.46 | 0.0395 | 0.6935 | 8/16 | 184.90 | $0.0000 | cpu |

## Oracle-layout reference (COMET-Kiwi)

*Given **ground-truth bounding boxes** as predictions; only the text is translated. These are upper bounds on text-quality, **not** realistic end-to-end measurements.*

| Rank | System | LTB-100 [95% CI] | COMET-Kiwi | Layout IoU | Reading-order τ | Coverage | Median runtime (s/doc) | Cost (USD) | Hardware |
|---:|:---|:---|---:|---:|---:|:---:|---:|---:|:---|
| 1 | nllb-text-oracle-nllb-200-distilled-600m v0.1.0 | 86.95 [85.8, 88.0] | 66.81 | 1.0000 | 1.0000 | 15/16 | — | — | cpu |
| 2 | deepl-text-oracle v0.1.0 | 84.89 [81.4, 88.0] | 69.77 | 1.0000 | 1.0000 | 6/16 | 0.40 | $0.0000 | api |
| 3 | opus-mt-text-oracle v0.1.0 | 80.46 [78.9, 82.1] | 49.77 | 1.0000 | 1.0000 | 15/16 | — | — | cpu |

---

See [BENCHMARK.md](BENCHMARK.md) for the spec and [docs/submission.md](docs/submission.md) to submit.
