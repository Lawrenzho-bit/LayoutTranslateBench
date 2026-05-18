"""Text quality: character-level chrF (Popović 2015).

Pure-Python implementation, no external NLP dependencies.

chrF is a character-level F-score combining character n-gram precision and recall
across n in 1..N (default 6). F-beta with beta=2 (chrF2) is the standard.
"""

from __future__ import annotations

from collections import Counter


def _char_ngrams(text: str, n: int) -> Counter[str]:
    if not text or n <= 0 or len(text) < n:
        return Counter()
    return Counter(text[i : i + n] for i in range(len(text) - n + 1))


def _ngram_f(hyp: Counter[str], ref: Counter[str], beta: float) -> float:
    """F-beta over one n-gram order."""
    if not hyp and not ref:
        return 1.0
    if not hyp or not ref:
        return 0.0
    overlap = sum((hyp & ref).values())
    hyp_total = sum(hyp.values())
    ref_total = sum(ref.values())
    if overlap == 0:
        return 0.0
    p = overlap / hyp_total
    r = overlap / ref_total
    if p == 0 or r == 0:
        return 0.0
    beta_sq = beta * beta
    return (1 + beta_sq) * p * r / (beta_sq * p + r)


def chrf(hypothesis: str, reference: str, n: int = 6, beta: float = 2.0) -> float:
    """Compute chrF (character F-beta) score in [0, 100].

    Args:
        hypothesis: the predicted translation
        reference: the reference (gold) translation
        n: max n-gram order (default 6)
        beta: F-beta weight (default 2 = chrF2, the WMT-standard variant)

    Returns:
        chrF score in [0, 100]. Identical strings score 100; disjoint strings score 0.
    """
    if hypothesis == reference:
        return 100.0
    if not hypothesis and not reference:
        return 100.0
    if not hypothesis or not reference:
        return 0.0

    scores: list[float] = []
    for k in range(1, n + 1):
        h = _char_ngrams(hypothesis, k)
        r = _char_ngrams(reference, k)
        # Skip orders where both are empty (rare; only for very short strings)
        if not h and not r:
            continue
        scores.append(_ngram_f(h, r, beta))

    if not scores:
        return 0.0
    return 100.0 * sum(scores) / len(scores)
