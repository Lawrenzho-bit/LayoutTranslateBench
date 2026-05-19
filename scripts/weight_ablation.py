"""Composite-weights ablation for LayoutTranslateBench.

Addresses the v0.1.1 open critique that the LTB-100 weights (50% chrF, 30% IoU,
20% τ) are unmotivated. This script re-computes overall LTB-100 for every
scored system under four weight schemes:

  50/30/20 — current production
  40/40/20 — text and layout balanced
  60/20/20 — text-heavy
  33/33/33 — uniform

It then computes Kendall τ between the system rankings under each pair of
weight schemes. If τ ≈ 1.0 across all pairs, the leaderboard ordering is
robust to weight choice. If τ < 0.7 on any pair, the weights are doing
significant work and need empirical validation against human judgment.

Run from repo root:
    python scripts/weight_ablation.py

Outputs to stdout (and optionally `--output results/weight_ablation.json`).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from statistics import mean

from ltbench.metrics.reading_order import _kendall_tau_b  # type: ignore[attr-defined]


WEIGHT_SCHEMES: dict[str, tuple[float, float, float]] = {
    "50/30/20 (production)": (0.50, 0.30, 0.20),
    "40/40/20 (balanced)": (0.40, 0.40, 0.20),
    "60/20/20 (text-heavy)": (0.60, 0.20, 0.20),
    "33/33/33 (uniform)": (1 / 3, 1 / 3, 1 / 3),
}


def _ltb_under_weights(
    per_doc: list[dict], w_chrf: float, w_iou: float, w_tau: float
) -> float:
    """Recompute overall LTB-100 from per-doc scores under custom weights."""
    if not per_doc:
        return 0.0
    return mean(
        100.0
        * (w_chrf * d["chrf"] / 100.0 + w_iou * d["layout_iou"] + w_tau * d["reading_order_tau"])
        for d in per_doc
    )


def _kendall_tau_norm(a: list[int], b: list[int]) -> float:
    """Kendall τ-b normalised to [0, 1] (1.0 = perfect rank agreement)."""
    if len(a) < 2:
        return 1.0
    tau = _kendall_tau_b(a, b)
    return (tau + 1.0) / 2.0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--results-dir", type=Path, default=Path("results"), help="Directory of result JSONs"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional path to write a JSON summary",
    )
    args = parser.parse_args()

    results = []
    for path in sorted(args.results_dir.glob("*.json")):
        if path.name.endswith(".local.json"):
            continue
        with path.open("r", encoding="utf-8") as f:
            r = json.load(f)
        results.append(
            {
                "system_name": r["system"]["system_name"],
                "system_type": r["system"].get("system_type", "end-to-end"),
                "per_doc": r["per_doc"],
            }
        )

    if not results:
        print(f"No result JSONs found in {args.results_dir}", file=sys.stderr)
        return 1

    # Compute LTB-100 for every (system, weight-scheme) cell
    print("\n=== LTB-100 under each weight scheme ===\n")
    header = f"  {'System':<55} | " + " | ".join(f"{k:^20}" for k in WEIGHT_SCHEMES)
    print(header)
    print("  " + "-" * (len(header) - 2))

    cells: dict[str, dict[str, float]] = {}
    for r in results:
        row = {}
        for scheme_name, (wc, wi, wt) in WEIGHT_SCHEMES.items():
            row[scheme_name] = _ltb_under_weights(r["per_doc"], wc, wi, wt)
        cells[r["system_name"]] = row
        cells_str = " | ".join(f"{row[k]:>14.2f}" for k in WEIGHT_SCHEMES)
        print(f"  {r['system_name']:<55} | {cells_str}")

    # Ranking under each scheme
    print("\n=== Rankings (1 = best) ===\n")
    rankings: dict[str, list[str]] = {}
    print(f"  {'Scheme':<25}  {'1st':<45}  {'2nd':<45}  {'3rd':<45}  {'4th':<45}")
    print("  " + "-" * 200)
    for scheme_name in WEIGHT_SCHEMES:
        names_sorted = sorted(
            cells.keys(), key=lambda n: cells[n][scheme_name], reverse=True
        )
        rankings[scheme_name] = names_sorted
        rendered = "  ".join(f"{n:<45}" for n in names_sorted[:4])
        print(f"  {scheme_name:<25}  {rendered}")

    # Pairwise Kendall τ between rankings
    print("\n=== Pairwise rank agreement (Kendall τ_norm, 1.0 = perfect agreement) ===\n")
    scheme_names = list(WEIGHT_SCHEMES)
    print(f"  {'Pair':<55} {'τ_norm':>10}")
    print("  " + "-" * 70)
    tau_results: list[dict] = []
    for i, s1 in enumerate(scheme_names):
        for s2 in scheme_names[i + 1 :]:
            # Convert each system's rank under each scheme into ints
            r1 = {n: i for i, n in enumerate(rankings[s1])}
            r2 = {n: i for i, n in enumerate(rankings[s2])}
            common = list(set(r1) & set(r2))
            seq1 = [r1[n] for n in common]
            seq2 = [r2[n] for n in common]
            tau_norm = _kendall_tau_norm(seq1, seq2)
            tau_results.append({"scheme_1": s1, "scheme_2": s2, "tau_norm": tau_norm})
            print(f"  {s1:<27} vs {s2:<27} {tau_norm:>9.4f}")

    # Verdict
    print("\n=== Verdict ===\n")
    min_tau = min(t["tau_norm"] for t in tau_results)
    if min_tau >= 0.95:
        verdict = (
            f"Rankings are stable across weight schemes (min τ_norm = {min_tau:.4f}). "
            f"The 50/30/20 production weights are not doing methodologically significant work."
        )
    elif min_tau >= 0.75:
        verdict = (
            f"Rankings are mostly stable across weight schemes (min τ_norm = {min_tau:.4f}). "
            f"Some borderline systems may swap rank under different weights — disclose this "
            f"in any cross-system comparison."
        )
    else:
        verdict = (
            f"Rankings are NOT robust to weight choice (min τ_norm = {min_tau:.4f}). "
            f"The 50/30/20 weights are doing significant work — they need empirical "
            f"validation against human judgment before being trusted as 'the' LTB-100."
        )
    print(f"  {verdict}\n")

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("w", encoding="utf-8") as f:
            json.dump(
                {
                    "schemes": dict(WEIGHT_SCHEMES),
                    "cells": cells,
                    "rankings": rankings,
                    "pairwise_tau": tau_results,
                    "min_tau": min_tau,
                    "verdict": verdict,
                },
                f,
                indent=2,
            )
        print(f"  Wrote summary to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
