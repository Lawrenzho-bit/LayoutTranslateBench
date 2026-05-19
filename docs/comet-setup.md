# COMET-Kiwi-22 Setup (Optional Text Metric)

LTB v0.1.2 ships COMET-Kiwi-22 as an **optional** text metric (`--text-metric comet-kiwi`). chrF₂ remains the default because COMET requires a clean Python environment.

## Why it's optional

`unbabel-comet` (the COMET-Kiwi package) requires `scipy + numpy ≥ 2.x`. Many development environments pin `numpy < 2` for `opencv-contrib-python` or other ML packages, which makes installing COMET into the main `ltbench` environment fail at scipy-import time.

The fix is a **dedicated virtual environment** for COMET-based runs.

## One-time setup

```bash
# From the repo root:
python -m venv .comet-env

# Activate the venv:
.comet-env\Scripts\activate          # Windows (PowerShell or cmd)
source .comet-env/bin/activate       # macOS / Linux

# Install COMET + ltbench inside the venv:
pip install unbabel-comet
pip install -e .
```

The venv directory is gitignored. ~3 GB on disk after install (torch + pytorch-lightning + COMET model weights).

## Running with COMET-Kiwi

From inside the activated `.comet-env`:

```bash
ltbench score \
  --submission submissions/deepl-text-oracle \
  --text-metric comet-kiwi \
  --output results/deepl-text-oracle.comet.json
```

The first invocation downloads `Unbabel/wmt22-cometkiwi-da` (~600 MB) to the HuggingFace cache. Subsequent runs load from cache.

Approximate runtime on CPU (4 systems × 8 lang-pairs × 5 docs × ~7 regions = ~1120 region calls):

| Stage | Cost |
|---|---|
| Model download (first-time only) | 1–5 min |
| Per-region inference (batched per doc) | 5–20 sec/doc |
| Full 4-system re-score | 30–90 min |

GPU inference is ~10–50× faster; pass `LTB_COMET_DEVICE=cuda` if you have one.

## Result file changes

The result JSON's `overall_chrf` and `per_lang_pair[*].chrf` fields now hold the COMET-Kiwi score (still in [0, 100], so the LTB-100 composite formula is unchanged). The `weights` field is unchanged.

To distinguish chrF-scored and COMET-scored runs, name the output file accordingly (`<system>.json` vs `<system>.comet.json`) and rebuild the leaderboard against the appropriate result set.

## When to use which metric

| Use chrF (default) | Use COMET-Kiwi |
|---|---|
| Quick iteration / CI / unit tests | Pre-launch sanity-check on rankings |
| No GPU available, want <1 sec/region | Have GPU or willing to wait |
| Reproducibility on CPU-only machines | Higher human-judgment correlation |
| All v0.1.1 leaderboard rows | A separate `*.comet.json` set of result files |

chrF is *the* metric for the v0.1.1 leaderboard until COMET-scored runs are available for *every* submission — otherwise the leaderboard would mix metrics on the same axis.

## Verifying setup

Inside the activated venv:

```bash
python -c "
from ltbench.metrics.comet import score_one
print(score_one('Certificate of Birth', 'Certificado de Nacimiento'))
"
```

A first-time run prints model-download progress, then a float in `[0, 100]` (typically 70–95 for a competent translation). Subsequent runs skip the download.

## Limitations

- **First-load overhead.** Model loading takes ~30–60 sec; bake this into your timing.
- **Per-pair quality varies.** COMET-Kiwi-22 is trained mostly on WMT data; low-resource pairs (en-th, en-ms) have less training signal than en-de or en-es.
- **No GPU on Windows by default.** Pytorch CUDA on Windows needs a specific torch install. If you have an NVIDIA GPU and want speedup, follow the [torch Windows-CUDA install](https://pytorch.org/get-started/locally/) instructions inside `.comet-env`.

## Roadmap

v0.2 will ship a Docker image that bundles `unbabel-comet` and the LTB scoring pipeline in one container, eliminating the dual-venv workflow. Until then, this guide is the supported path.
