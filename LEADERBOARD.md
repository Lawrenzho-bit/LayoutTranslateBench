# LayoutTranslateBench Leaderboard

_Generated 2026-05-22T05:01:52+00:00 from LayoutTranslateBench v0.1.7.2._

**Sample size — v0.1.7.** Core 8 pairs: N=20 for en-es/en-de/en-ar/en-fr/en-th/en-ms, N=28 for en-ja, N=27 for en-zh. Extension 8 pairs (v0.1.7): N=10 for en-ru (FLORES-200 only; rileykim refs removed at v0.1.6.4), N=13 for en-ko/en-vi/en-id/en-ur/en-uz/en-kk/en-zh-tw (3 rileykim + 10 FLORES). All 16 pairs now covered. LTB-100 cell shows `point [95% CI low, CI high]` via 1000-resample percentile bootstrap (seed 42). Coverage column shows pairs with ≥1 scored doc.

**Metric.** Two parallel leaderboards are shown — **chrF** (character-level F-score, fast, deterministic, paraphrase-blind) and **COMET-Kiwi-22** (reference-free neural MT quality estimation, slower but more correlated with human judgment). System rankings can differ between metrics, especially for systems that paraphrase well.

---

# Leaderboard A — chrF

## End-to-end systems (chrF)

*These runners produce their own bounding boxes. This is the realistic real-world score.*

| Rank | System | LTB-100 [95% CI] | chrF | Layout IoU | Reading-order τ | Coverage | Median runtime (s/doc) | Cost (USD) | Hardware |
|---:|:---|:---|---:|---:|---:|:---:|---:|---:|:---|
| 1 | identity-baseline v0.1.0 | 50.38 [50.2, 50.6] | 0.62 | 1.0000 | 1.0000 | 16/16 | — | — | cpu |
| 2 | florence-nllb v0.1.0 | 39.79 [36.6, 42.9] | 37.93 | 0.1541 | 0.8104 | 8/16 | — | — | cpu |
| 3 | qwen3-vl-2b-instruct v0.1.0 | 14.82 [12.1, 17.4] | 5.13 | 0.1084 | 0.4504 | 8/16 | 184.90 | $0.0000 | cpu |

## Oracle-layout reference (chrF)

*Given **ground-truth bounding boxes** as predictions; only the text is translated. These are upper bounds on text-quality, **not** realistic end-to-end measurements.*

| Rank | System | LTB-100 [95% CI] | chrF | Layout IoU | Reading-order τ | Coverage | Median runtime (s/doc) | Cost (USD) | Hardware |
|---:|:---|:---|---:|---:|---:|:---:|---:|---:|:---|
| 1 | deepl-text-oracle v0.1.0 | 78.20 [75.2, 81.7] | 56.40 | 1.0000 | 1.0000 | 6/16 | 0.40 | $0.0000 | api |
| 2 | nllb-text-oracle v0.1.0 | 73.71 [72.5, 74.9] | 47.61 | 1.0000 | 1.0000 | 16/16 | — | — | cpu |
| 3 | opus-mt-text-oracle v0.1.0 | 68.60 [67.1, 70.0] | 37.26 | 1.0000 | 1.0000 | 16/16 | — | — | cpu |

---

# Leaderboard B — COMET-Kiwi-22

*COMET-Kiwi is reference-free; the per-region chrF column shown above is replaced by the COMET-Kiwi score (also in [0, 100], higher = better).*

## End-to-end systems (COMET-Kiwi)

*These runners produce their own bounding boxes. This is the realistic real-world score.*

| Rank | System | LTB-100 [95% CI] | COMET-Kiwi | Layout IoU | Reading-order τ | Coverage | Median runtime (s/doc) | Cost (USD) | Hardware |
|---:|:---|:---|---:|---:|---:|:---:|---:|---:|:---|
| 1 | identity-baseline v0.1.0 | 50.47 [50.3, 50.7] | 0.81 | 1.0000 | 1.0000 | 16/16 | — | — | cpu |
| 2 | florence-nllb v0.1.0 | 48.11 [44.1, 51.7] | 54.56 | 0.1541 | 0.8104 | 8/16 | — | — | cpu |
| 3 | qwen3-vl-2b-instruct v0.1.0 | 18.43 [14.6, 22.3] | 12.33 | 0.1084 | 0.4504 | 8/16 | 184.90 | $0.0000 | cpu |

## Oracle-layout reference (COMET-Kiwi)

*Given **ground-truth bounding boxes** as predictions; only the text is translated. These are upper bounds on text-quality, **not** realistic end-to-end measurements.*

| Rank | System | LTB-100 [95% CI] | COMET-Kiwi | Layout IoU | Reading-order τ | Coverage | Median runtime (s/doc) | Cost (USD) | Hardware |
|---:|:---|:---|---:|---:|---:|:---:|---:|---:|:---|
| 1 | nllb-text-oracle v0.1.0 | 86.51 [85.3, 87.7] | 72.15 | 1.0000 | 1.0000 | 16/16 | — | — | cpu |
| 2 | deepl-text-oracle v0.1.0 | 84.89 [81.4, 88.0] | 69.77 | 1.0000 | 1.0000 | 6/16 | 0.40 | $0.0000 | api |
| 3 | opus-mt-text-oracle v0.1.0 | 79.35 [77.9, 80.8] | 57.36 | 1.0000 | 1.0000 | 16/16 | — | — | cpu |

---

See [BENCHMARK.md](BENCHMARK.md) for the spec and [docs/submission.md](docs/submission.md) to submit.
