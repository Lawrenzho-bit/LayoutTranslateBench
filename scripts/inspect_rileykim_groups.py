"""Group analysis: does image_id appear in multiple lang_pairs?

Uses streaming mode because the test split has a parquet schema bug that
breaks the non-streaming code path. We only need the train split anyway.
"""

from __future__ import annotations

import sys
from collections import Counter, defaultdict

from datasets import load_dataset


def main() -> int:
    print("Loading rileykim/multilingual-document train split in streaming mode...")
    ds = load_dataset(
        "rileykim/multilingual-document", split="train", streaming=True
    )

    print("Walking rows to map image_id -> lang_pairs (no image decoding)...")
    id_to_pairs: dict[str, list[str]] = defaultdict(list)
    image_dims: dict[str, tuple[int, int]] = {}
    # Don't pull image bytes; just iterate over the rest.
    ds_slim = ds.remove_columns(["image", "ocr", "merge_ocr"])
    for n, row in enumerate(ds_slim, start=1):
        id_to_pairs[row["image_id"]].append(row["lang_pair"])
        if n % 1000 == 0:
            print(f"  ...{n} rows scanned, {len(id_to_pairs)} distinct image_ids so far")

    total_rows = sum(len(v) for v in id_to_pairs.values())
    print(f"\nTotal rows scanned: {total_rows}")
    print(f"Distinct image_ids: {len(id_to_pairs)}")

    pair_count_dist = Counter(len(v) for v in id_to_pairs.values())
    print(f"\nPairs-per-image distribution:")
    for n_pairs, n_ids in sorted(pair_count_dist.items()):
        print(f"  {n_pairs} lang_pair(s): {n_ids} image_ids")

    # Pair coverage overall
    all_pairs: Counter[str] = Counter()
    for pairs in id_to_pairs.values():
        all_pairs.update(pairs)
    print(f"\nLang pair distribution (all rows):")
    for p, n in all_pairs.most_common():
        print(f"  {p}: {n}")

    # Sample images that span multiple pairs
    multi = [(img_id, pairs) for img_id, pairs in id_to_pairs.items() if len(pairs) > 1]
    print(f"\nImages with >1 lang_pair: {len(multi)}")
    for img_id, pairs in multi[:10]:
        print(f"  {img_id}: {sorted(set(pairs))}")

    # How many distinct image_ids appear in LTB-overlap pairs?
    LTB_OVERLAP = {"en-ja", "en-zh-cn"}
    overlap_ids = {
        img_id
        for img_id, pairs in id_to_pairs.items()
        if any(p in LTB_OVERLAP for p in pairs)
    }
    print(f"\nDistinct image_ids with en-ja or en-zh-cn: {len(overlap_ids)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
