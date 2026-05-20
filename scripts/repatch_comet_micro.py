"""Re-compute overall_ltb_100 + CI on existing *.comet.json results using the
v0.1.6 micro-aggregation (per-doc bootstrap mean instead of macro per-pair mean).

Avoids re-running COMET-Kiwi (which takes ~30-60 min per system) by reading the
existing per_doc[*].ltb_100 values and bootstrapping them in-place.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from ltbench.metrics.bootstrap import bootstrap_ci


def main() -> int:
    results_dir = Path("results")
    for path in sorted(results_dir.glob("*.comet.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        per_doc = payload.get("per_doc", [])
        # Honor exclude_parser_failures: skip docs with parser_failure=True for
        # the aggregation if the same logic was applied at score time. We can't
        # tell from the file alone; assume not.
        scoring_pool = [d["ltb_100"] for d in per_doc]
        if not scoring_pool:
            print(f"  {path.name}: no per-doc scores, skipping")
            continue
        point, ci_low, ci_high = bootstrap_ci(scoring_pool)
        old_point = payload.get("overall_ltb_100", 0.0)
        old_ci = (payload.get("overall_ltb_100_ci_low", 0.0), payload.get("overall_ltb_100_ci_high", 0.0))
        payload["overall_ltb_100"] = point
        payload["overall_ltb_100_ci_low"] = ci_low
        payload["overall_ltb_100_ci_high"] = ci_high
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(
            f"  {path.name}: point {old_point:.2f} -> {point:.2f}; "
            f"CI {old_ci[0]:.2f}-{old_ci[1]:.2f} -> {ci_low:.2f}-{ci_high:.2f}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
