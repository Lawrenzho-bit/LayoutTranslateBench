"""Streaming-mode inspection of rileykim/multilingual-document — fast, no full download.

Confirms WebFetch findings about the actual data shape using one row.
"""

from __future__ import annotations

import json
import sys
from collections import Counter

from datasets import load_dataset


def main() -> int:
    print("Loading rileykim/multilingual-document in STREAMING mode (no full download)...")
    ds = load_dataset("rileykim/multilingual-document", split="train", streaming=True)
    print("  loaded.")

    it = iter(ds)
    first = next(it)
    print(f"\n== Top-level field names ==")
    for k, v in first.items():
        t = type(v).__name__
        if isinstance(v, list):
            preview = f"list[{type(v[0]).__name__}] len={len(v)}"
        else:
            sval = str(v)[:80]
            preview = f"{t}={sval!r}"
        print(f"  {k}: {preview}")

    print(f"\n== Row 0 OCR structure ==")
    ocr = first.get("ocr") or []
    if ocr:
        print(f"  ocr[0]: {json.dumps(ocr[0], ensure_ascii=False, default=str)[:300]}")
        print(f"  ocr count: {len(ocr)}")

    print(f"\n== Row 0 merge_ocr structure ==")
    merged = first.get("merge_ocr") or []
    if merged:
        print(f"  merge_ocr[0]: {json.dumps(merged[0], ensure_ascii=False, default=str)[:400]}")
        print(f"  merge_ocr count: {len(merged)}")
        print(f"  merge_ocr[0] keys: {list(merged[0].keys())}")

    print(f"\n== Row 0 metadata ==")
    print(f"  image_id: {first.get('image_id')!r}")
    print(f"  lang_pair: {first.get('lang_pair')!r}")
    print(f"  target_lang: {first.get('target_lang')!r}")
    print(f"  cls: {first.get('cls')!r}")
    img = first.get("image")
    if img is not None:
        print(f"  image: type={type(img).__name__} size={getattr(img, 'size', '?')}")

    # Scan first 100 rows for distribution
    print(f"\n== lang_pair distribution (first 200 rows) ==")
    pair_counts: Counter[str] = Counter()
    pair_counts[first.get("lang_pair", "?")] += 1
    for i, row in enumerate(it):
        if i >= 199:
            break
        pair_counts[row.get("lang_pair", "?")] += 1
    for pair, n in pair_counts.most_common():
        print(f"  {pair}: {n}")

    print("\n== Done (streaming) ==")
    return 0


if __name__ == "__main__":
    sys.exit(main())
