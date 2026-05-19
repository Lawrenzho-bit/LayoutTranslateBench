"""Reading-order preservation: normalized Kendall tau in [0, 1]."""

from __future__ import annotations


def _kendall_tau_b(a: list[int], b: list[int]) -> float:
    """Kendall tau-b correlation in [-1, 1]. O(n^2). Pure stdlib."""
    n = len(a)
    if n != len(b):
        raise ValueError(f"reading-order sequences must be same length, got {n} vs {len(b)}")
    if n < 2:
        return 1.0

    concordant = 0
    discordant = 0
    ties_a = 0
    ties_b = 0

    for i in range(n - 1):
        for j in range(i + 1, n):
            da = a[i] - a[j]
            db = b[i] - b[j]
            if da == 0 and db == 0:
                ties_a += 1
                ties_b += 1
            elif da == 0:
                ties_a += 1
            elif db == 0:
                ties_b += 1
            elif (da > 0) == (db > 0):
                concordant += 1
            else:
                discordant += 1

    total = n * (n - 1) / 2
    denom_a = (total - ties_a) * (total - ties_b)
    if denom_a <= 0:
        return 1.0 if concordant >= discordant else -1.0
    return (concordant - discordant) / (denom_a**0.5)


def normalized_kendall_tau(source_order: list[int], predicted_order: list[int]) -> float:
    """Kendall tau normalized to [0, 1].

    1.0 = perfectly preserved order. 0.5 = random. 0.0 = reversed order.

    Args:
        source_order: reading-order indices from the ground-truth annotation,
            in the order that matched predicted regions appear.
        predicted_order: predicted reading-order indices, in the same alignment.

    Returns:
        Normalized tau in [0, 1].
    """
    if len(source_order) != len(predicted_order):
        raise ValueError("sequences must be same length")
    if len(source_order) < 2:
        return 1.0
    tau = _kendall_tau_b(source_order, predicted_order)
    return (tau + 1.0) / 2.0


def coverage_aware_tau(
    source_order: list[int],
    predicted_order: list[int],
    n_gt_regions: int,
) -> float:
    """Coverage-aware Kendall tau.

    Addresses a v0.1 methodology issue: a system returning only 1 region out of
    7 ground-truth regions gets normalized_kendall_tau = 1.0 (trivially "in
    order" since there's only one). This artificially inflates the reading-
    order score for partial-coverage runs.

    Solution: scale by coverage ratio. A system matching n_matched regions out
    of n_gt_regions multiplies its base tau by (n_matched / n_gt_regions).

        coverage_aware_tau = base_tau × min(1.0, n_matched / n_gt_regions)

    Args:
        source_order: matched ground-truth reading-order indices.
        predicted_order: matched predicted reading-order indices.
        n_gt_regions: total ground-truth region count for this document.

    Returns:
        Coverage-aware tau in [0, 1].
    """
    if n_gt_regions <= 0:
        return 0.0
    n_matched = len(source_order)
    base_tau: float
    if n_matched < 2:
        base_tau = 1.0 if n_matched == 1 else 0.0
    else:
        base_tau = normalized_kendall_tau(source_order, predicted_order)
    coverage = min(1.0, n_matched / n_gt_regions)
    return base_tau * coverage
