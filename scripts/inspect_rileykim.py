"""Inspect rileykim/multilingual-document HF dataset for LTB suitability.

Goal: determine if we can adapt it into LTB v0.1.4 expansion.

Outputs a structured report:
- License
- Total rows, splits
- Schema (field names + types)
- Language pair coverage vs LTB's 8 pairs
- Sample row (text + structure)
- Bbox availability
- Category distribution
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

from datasets import load_dataset

LTB_PAIRS = {"en-es", "en-de", "en-zh", "en-ar", "en-ja", "en-fr", "en-th", "en-ms"}


def main() -> int:
    repo_id = "rileykim/multilingual-document"
    print(f"== Loading {repo_id} ==")
    try:
        ds = load_dataset(repo_id)
    except Exception as exc:
        print(f"FAIL load_dataset: {exc}")
        return 1

    print(f"\n== Splits ==")
    for split_name, split in ds.items():
        print(f"  {split_name}: {len(split)} rows")

    # Use first split (usually 'train')
    first_split_name = next(iter(ds))
    split = ds[first_split_name]

    print(f"\n== Schema ({first_split_name}) ==")
    for field, ftype in split.features.items():
        print(f"  {field}: {ftype}")

    print(f"\n== Sample row 0 ==")
    sample = split[0]
    for k, v in sample.items():
        if isinstance(v, (str, bytes)):
            preview = (v[:200] + "...") if len(v) > 200 else v
            print(f"  {k}: {preview!r}")
        elif isinstance(v, (list, dict)):
            preview = json.dumps(v, ensure_ascii=False, default=str)[:400]
            print(f"  {k}: {preview}")
        else:
            print(f"  {k}: {v!r} ({type(v).__name__})")

    # Try to find language-pair fields
    print(f"\n== Field name scan for language-pair signals ==")
    field_names = list(split.features.keys())
    pair_like = [f for f in field_names if any(p in f.lower() for p in ["lang", "trans", "en_", "_en", "es", "de", "zh", "ar", "ja", "fr", "th", "ms"])]
    for f in pair_like:
        print(f"  candidate: {f}")

    # If there's a 'language' or 'lang' or 'target' column, distribute
    for candidate in ["language", "lang", "target_language", "target_lang", "translation"]:
        if candidate in split.features:
            print(f"\n== Distribution of {candidate} (top 30) ==")
            try:
                vals = split[candidate]
                if isinstance(vals[0], dict):
                    # translation field — dict per row
                    keys = list(vals[0].keys())
                    print(f"  translation dict keys: {keys}")
                else:
                    c = Counter(vals)
                    for v, n in c.most_common(30):
                        print(f"  {v}: {n}")
            except Exception as exc:
                print(f"  scan failed: {exc}")

    # Category / document type distribution
    for candidate in ["category", "doc_type", "document_type", "type", "domain"]:
        if candidate in split.features:
            print(f"\n== Distribution of {candidate} ==")
            try:
                c = Counter(split[candidate])
                for v, n in c.most_common():
                    print(f"  {v}: {n}")
            except Exception as exc:
                print(f"  scan failed: {exc}")

    # Bbox availability
    print(f"\n== Bbox check ==")
    for candidate in ["bbox", "bboxes", "regions", "layout", "boxes"]:
        if candidate in split.features:
            print(f"  has '{candidate}' field: {split.features[candidate]}")

    print(f"\n== Done ==")
    return 0


if __name__ == "__main__":
    sys.exit(main())
