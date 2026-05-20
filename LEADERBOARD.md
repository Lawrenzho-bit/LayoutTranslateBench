# LayoutTranslateBench Leaderboard

_Generated 2026-05-20T07:44:05+00:00 from LayoutTranslateBench v0.1.0._

**Sample size — v0.1.5.** Per-pair counts: N=20 for en-es/en-de/en-ar/en-fr/en-th/en-ms (10 author-curated + 10 FLORES-200), N=28 for en-ja (+8 rileykim), N=27 for en-zh (+7 rileykim). LTB-100 cell shows `point [95% CI low, CI high]` via 1000-resample percentile bootstrap. CIs at N=20 are roughly √2× tighter than v0.1.3's N=10.

**Metric.** Two parallel leaderboards are shown — **chrF** (character-level F-score, fast, deterministic, paraphrase-blind) and **COMET-Kiwi-22** (reference-free neural MT quality estimation, slower but more correlated with human judgment). System rankings can differ between metrics, especially for systems that paraphrase well.

---

# Leaderboard A — chrF

## End-to-end systems (chrF)

*These runners produce their own bounding boxes. This is the realistic real-world score.*

| Rank | System | LTB-100 [95% CI] | chrF | Layout IoU | Reading-order τ | Coverage | Median runtime (s/doc) | Cost (USD) | Hardware |
|---:|:---|:---|---:|---:|---:|:---:|---:|---:|:---|
| 1 | identity-baseline v0.1.0 | 50.54 [50.3, 50.8] | 1.08 | 1.0000 | 1.0000 | 16/16 | — | — | cpu |
| 2 | qwen3-vl-2b-instruct v0.1.0 | 16.35 [14.0, 18.6] | 2.60 | 0.0395 | 0.6935 | 8/16 | 184.90 | $0.0000 | cpu |

## Oracle-layout reference (chrF)

*Given **ground-truth bounding boxes** as predictions; only the text is translated. These are upper bounds on text-quality, **not** realistic end-to-end measurements.*

| Rank | System | LTB-100 [95% CI] | chrF | Layout IoU | Reading-order τ | Coverage | Median runtime (s/doc) | Cost (USD) | Hardware |
|---:|:---|:---|---:|---:|---:|:---:|---:|---:|:---|
| 1 | deepl-text-oracle v0.1.0 | 78.20 [75.2, 81.7] | 56.40 | 1.0000 | 1.0000 | 6/16 | 0.40 | $0.0000 | api |
| 2 | nllb-text-oracle-nllb-200-distilled-600m v0.1.0 | 75.82 [73.7, 76.4] | 51.63 | 1.0000 | 1.0000 | 8/16 | — | — | cpu |

---

# Leaderboard B — COMET-Kiwi-22

*COMET-Kiwi is reference-free; the per-region chrF column shown above is replaced by the COMET-Kiwi score (also in [0, 100], higher = better).*

## End-to-end systems (COMET-Kiwi)

*These runners produce their own bounding boxes. This is the realistic real-world score.*

| Rank | System | LTB-100 [95% CI] | COMET-Kiwi | Layout IoU | Reading-order τ | Coverage | Median runtime (s/doc) | Cost (USD) | Hardware |
|---:|:---|:---|---:|---:|---:|:---:|---:|---:|:---|
| 1 | identity-baseline v0.1.0 | 50.58 [50.4, 50.9] | 1.16 | 1.0000 | 1.0000 | 8/16 | — | — | cpu |
| 2 | qwen3-vl-2b-instruct v0.1.0 | 22.79 [18.6, 27.1] | 15.46 | 0.0395 | 0.6935 | 8/16 | 184.90 | $0.0000 | cpu |

## Oracle-layout reference (COMET-Kiwi)

*Given **ground-truth bounding boxes** as predictions; only the text is translated. These are upper bounds on text-quality, **not** realistic end-to-end measurements.*

| Rank | System | LTB-100 [95% CI] | COMET-Kiwi | Layout IoU | Reading-order τ | Coverage | Median runtime (s/doc) | Cost (USD) | Hardware |
|---:|:---|:---|---:|---:|---:|:---:|---:|---:|:---|
| 1 | nllb-text-oracle-nllb-200-distilled-600m v0.1.0 | 88.01 [87.0, 88.9] | 76.01 | 1.0000 | 1.0000 | 8/16 | — | — | cpu |
| 2 | deepl-text-oracle v0.1.0 | 84.89 [81.4, 88.0] | 69.77 | 1.0000 | 1.0000 | 6/16 | 0.40 | $0.0000 | api |

---

See [BENCHMARK.md](BENCHMARK.md) for the spec and [docs/submission.md](docs/submission.md) to submit.
