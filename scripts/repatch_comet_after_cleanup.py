"""Re-aggregate COMET result files after v0.1.6.4 ref cleanup.

After `validate_extension_refs.py --fix` drops region refs that fail script
validation, some docs no longer have any reference for a given pair. Those
(doc, pair) tuples should be filtered out of the per-pair and overall
aggregation, even though COMET-Kiwi (being reference-free) doesn't need the
ref to compute the per-region score itself.

This script:
  1. Loads each *.comet.json
  2. Loads current annotations to determine which (doc, pair) tuples still
     have at least one region ref for that pair
  3. Filters per_doc entries accordingly
  4. Recomputes per_lang_pair aggregates + overall LTB-100 + CI

Does NOT re-run COMET-Kiwi on the actual model — uses the existing per-doc
scores from disk. Only the aggregation is recomputed.

Note: For opus-mt specifically, the en-ja submissions changed (fugumt swap),
so per_doc en-ja scores in opus-mt-text-oracle.comet.json are STALE and need
a fresh COMET run. That's a separate concern — run COMET on opus-mt en-ja
to refresh, then this script handles the aggregation.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from statistics import mean

from ltbench.metrics.bootstrap import bootstrap_ci


def load_annotation_pair_coverage(manifest_path: Path) -> dict[tuple[str, str], bool]:
    """Return {(doc_id, lang_pair): True} for every (doc, pair) that has at
    least one region ref for that pair in the current annotation file."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    data_root = manifest_path.parent
    coverage: dict[tuple[str, str], bool] = {}
    for entry in manifest["entries"]:
        ann_path = data_root / entry["annotation_file"]
        if not ann_path.exists():
            continue
        ann = json.loads(ann_path.read_text(encoding="utf-8"))
        for region in ann["regions"]:
            for pair in region["references"]:
                coverage[(entry["doc_id"], pair)] = True
    return coverage


def main() -> int:
    results_dir = Path("results")
    manifest_path = Path("data/manifest.json")
    coverage = load_annotation_pair_coverage(manifest_path)

    # Standard LTB pair list
    from ltbench import LANG_PAIRS

    for path in sorted(results_dir.glob("*.comet.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        per_doc = payload.get("per_doc", [])

        # Filter per-doc by current coverage
        filtered_per_doc = [
            d
            for d in per_doc
            if (d["doc_id"], d["lang_pair"]) in coverage
        ]
        n_dropped = len(per_doc) - len(filtered_per_doc)

        # Recompute per_lang_pair
        per_pair: dict[str, list[dict]] = {}
        for d in filtered_per_doc:
            per_pair.setdefault(d["lang_pair"], []).append(d)

        new_per_lang_pair = []
        for lp in LANG_PAIRS:
            docs = per_pair.get(lp, [])
            n = len(docs)
            if n == 0:
                new_per_lang_pair.append(
                    {
                        "lang_pair": lp,
                        "n_docs": 0,
                        "chrf": 0.0,
                        "layout_iou": 0.0,
                        "reading_order_tau": 0.0,
                        "ltb_100": 0.0,
                        "ltb_100_ci_low": 0.0,
                        "ltb_100_ci_high": 0.0,
                    }
                )
                continue
            chrf = mean(d["chrf"] for d in docs)
            iou = mean(d["layout_iou"] for d in docs)
            tau = mean(d["reading_order_tau"] for d in docs)
            ltb_scores = [d["ltb_100"] for d in docs]
            ltb_point, ci_low, ci_high = bootstrap_ci(ltb_scores)
            new_per_lang_pair.append(
                {
                    "lang_pair": lp,
                    "n_docs": n,
                    "chrf": chrf,
                    "layout_iou": iou,
                    "reading_order_tau": tau,
                    "ltb_100": ltb_point,
                    "ltb_100_ci_low": ci_low,
                    "ltb_100_ci_high": ci_high,
                }
            )

        # Recompute overall using v0.1.6.1 micro-aggregation
        populated = [p for p in new_per_lang_pair if p["n_docs"] > 0]
        if populated:
            overall_chrf = mean(p["chrf"] for p in populated)
            overall_iou = mean(p["layout_iou"] for p in populated)
            overall_tau = mean(p["reading_order_tau"] for p in populated)
            all_scores = [d["ltb_100"] for d in filtered_per_doc]
            overall_ltb, ci_low, ci_high = bootstrap_ci(all_scores)
        else:
            overall_chrf = overall_iou = overall_tau = overall_ltb = 0.0
            ci_low = ci_high = 0.0

        old_point = payload.get("overall_ltb_100", 0.0)
        payload["per_doc"] = filtered_per_doc
        payload["per_lang_pair"] = new_per_lang_pair
        payload["overall_ltb_100"] = overall_ltb
        payload["overall_ltb_100_ci_low"] = ci_low
        payload["overall_ltb_100_ci_high"] = ci_high
        payload["overall_chrf"] = overall_chrf
        payload["overall_layout_iou"] = overall_iou
        payload["overall_reading_order_tau"] = overall_tau

        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(
            f"  {path.name}: dropped {n_dropped} per-doc entries, "
            f"LTB-100 {old_point:.2f} -> {overall_ltb:.2f}"
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
