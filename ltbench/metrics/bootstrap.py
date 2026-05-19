"""Bootstrap confidence intervals for per-pair / per-system LTB-100 scores.

Addresses a methodology issue in v0.1: N=5 documents per language pair is
statistically thin; a 7-point gap between two systems on N=5 is well within
sampling noise. Bootstrap percentile CIs make the uncertainty visible.

Uses a fixed seed so CIs are deterministic given the same input scores. The
default 1000 resamples is conservative; reduce via the n_resamples argument
for faster CI computation in tests.
"""

from __future__ import annotations

import random
from statistics import mean


def bootstrap_ci(
    per_doc_scores: list[float],
    n_resamples: int = 1000,
    alpha: float = 0.05,
    seed: int = 42,
) -> tuple[float, float, float]:
    """Return (point_estimate, ci_low, ci_high) via percentile bootstrap.

    Args:
        per_doc_scores: scores for each document in a single language pair.
        n_resamples: number of bootstrap samples (default 1000).
        alpha: 1 - confidence level. Default 0.05 → 95% CI.
        seed: RNG seed for reproducibility.

    Returns:
        Tuple of (mean of input scores, lower CI bound, upper CI bound).

    Notes:
        For len < 2 returns (mean, mean, mean) — no usable CI on a singleton.
        For len = 2 the CI is wide but well-defined.
    """
    if not per_doc_scores:
        return 0.0, 0.0, 0.0
    point = mean(per_doc_scores)
    if len(per_doc_scores) < 2:
        return point, point, point

    rng = random.Random(seed)
    n = len(per_doc_scores)
    sample_means: list[float] = []
    for _ in range(n_resamples):
        sample = [per_doc_scores[rng.randrange(n)] for _ in range(n)]
        sample_means.append(sum(sample) / n)
    sample_means.sort()

    low_idx = int(n_resamples * (alpha / 2))
    high_idx = int(n_resamples * (1 - alpha / 2)) - 1
    low_idx = max(0, min(low_idx, n_resamples - 1))
    high_idx = max(0, min(high_idx, n_resamples - 1))

    return point, sample_means[low_idx], sample_means[high_idx]
