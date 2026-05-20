"""Adapter: rileykim/multilingual-document -> LTB Annotation format.

Schema (verified against the actual dataset):
  image_id    : str
  lang_pair   : str (en-id, en-ja, en-kk, en-ko, en-ru, en-ur, en-uz, en-vi,
                     en-zh-cn, en-zh-tw)
  target_lang : str
  cls         : str ('document' — sole value, not category)
  ocr         : list[ {box: [x1,y1,x2,y2], text} ]            raw OCR segments
  merge_ocr   : list[ {box: [x1,y1,x2,y2],
                       src_lang, src_text, tgt_lang, tgt_text} ]  ← used here
  image       : PIL.Image

License: Apache 2.0 (per dataset card). Per-doc license recorded in manifest.

Strategy:
  - Group rows by image_id to collect translations across all lang_pairs
    available for the same physical document
  - Filter by LTB-relevant pair set (LTB_PAIR_MAP keys)
  - For each kept image_id, pick ONE representative row to derive bboxes/source
    text (any of its rows have identical merge_ocr boxes/source — the only
    difference between rows is the target translation), then attach references
    from all available pairs
  - Save image to data/rileykim_derived/sources/doc_NNN.png
  - Save annotation to data/rileykim_derived/annotations/doc_NNN.json
  - Update top-level data/manifest.json with new entries
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from collections.abc import Iterator
from pathlib import Path

from datasets import load_dataset

REPO_ID = "rileykim/multilingual-document"

# Map rileykim's lang_pair codes -> LTB-compatible pair codes.
# en-ja and en-zh-cn (mapped to LTB's en-zh) overlap with LTB v0.1.3 directly.
# The rest are net-new pairs we'll declare as v0.1.4 extension pairs.
LTB_PAIR_MAP = {
    "en-ja": "en-ja",
    "en-zh-cn": "en-zh",  # treat Simplified Chinese as LTB's en-zh
    # net-new pairs (v0.1.4 extension):
    "en-id": "en-id",
    "en-ko": "en-ko",
    "en-ru": "en-ru",
    "en-vi": "en-vi",
    "en-ur": "en-ur",
    "en-uz": "en-uz",
    "en-kk": "en-kk",
    "en-zh-tw": "en-zh-tw",
}


def xyxy_to_xywh(bbox: list[float]) -> list[int]:
    x1, y1, x2, y2 = bbox
    return [int(round(x1)), int(round(y1)), int(round(max(0, x2 - x1))), int(round(max(0, y2 - y1)))]


def build_regions_from_merge_ocr(merge_ocr: list[dict]) -> list[dict]:
    """Build LTB regions from a single row's merge_ocr field. Translations attached later."""
    regions: list[dict] = []
    for idx, seg in enumerate(merge_ocr):
        box = seg.get("box")
        src_text = (seg.get("src_text") or "").strip()
        if not box or not src_text:
            continue
        regions.append(
            {
                "region_id": f"r{idx + 1}",
                "bbox": xyxy_to_xywh(box),
                "text": src_text,
                "reading_order": idx,
                "layout_class": "paragraph",
                "style": {"font_family": "serif", "size_hint": 13},
                "references": {},  # populated by merge step below
            }
        )
    return regions


def merge_translations_into_regions(
    regions: list[dict], per_pair_merge_ocr: dict[str, list[dict]]
) -> None:
    """For each LTB pair we have, attach the matching segment's tgt_text to the region.

    Matches by region index. All rows for the same image_id share the same
    merge_ocr structure (verified empirically in inspect step).
    """
    for ltb_pair, merge_ocr in per_pair_merge_ocr.items():
        for idx, region in enumerate(regions):
            if idx >= len(merge_ocr):
                continue
            tgt = (merge_ocr[idx].get("tgt_text") or "").strip()
            if tgt:
                region["references"][ltb_pair] = tgt


def iter_grouped_by_image_id(
    streaming_ds, max_distinct_ids: int
) -> Iterator[tuple[str, list[dict]]]:
    """Yield (image_id, [row, row, ...]) by walking the streaming dataset.

    Note: streaming dataset rows for the same image_id are typically contiguous
    (sorted by lang_pair), so we buffer and flush on transition. If the order
    isn't guaranteed contiguous we still produce correct groups, just with
    extra memory.
    """
    buckets: dict[str, list[dict]] = defaultdict(list)
    seen_ids = 0
    for row in streaming_ds:
        img_id = row["image_id"]
        buckets[img_id].append(row)
        if len(buckets) >= max_distinct_ids + 200:
            # Flush oldest fully-formed groups by keeping only the most recent ids
            # (this heuristic relies on contiguity; safe to skip if memory is fine)
            pass
    seen_ids = len(buckets)
    for img_id, rows in buckets.items():
        yield img_id, rows
        seen_ids -= 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-docs", type=int, default=20, help="Number of new docs to ingest")
    parser.add_argument(
        "--target-pairs",
        type=str,
        default="en-ja,en-zh-cn",
        help=(
            "Comma-separated rileykim pair codes to keep (any-of). "
            "Default = the 2 pairs that overlap with LTB v0.1.3 (en-ja, en-zh-cn->en-zh). "
            "Adding others (en-ru, en-ko, en-vi, en-id, en-ur, en-uz, en-kk, en-zh-tw) "
            "would require extending the LangPair Literal in ltbench/schemas.py."
        ),
    )
    parser.add_argument("--start-doc-id", type=int, default=11, help="Starting numeric suffix")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data"),
        help="LTB data dir (must contain manifest.json)",
    )
    parser.add_argument(
        "--subdir",
        type=str,
        default="rileykim_derived",
        help="Subdir under data/ for rileykim-derived sources+annotations",
    )
    parser.add_argument("--max-image-width", type=int, default=1600, help="Downsample images wider than this")
    parser.add_argument("--dry-run", action="store_true", help="Don't write any files")
    args = parser.parse_args()

    target_pairs = {p.strip() for p in args.target_pairs.split(",") if p.strip()}
    print(f"Target rileykim pairs: {sorted(target_pairs)}")

    # Prepare output dirs
    derived_dir = args.data_dir / args.subdir
    src_dir = derived_dir / "sources"
    ann_dir = derived_dir / "annotations"
    if not args.dry_run:
        src_dir.mkdir(parents=True, exist_ok=True)
        ann_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading rileykim streaming train split...")
    ds = load_dataset(REPO_ID, split="train", streaming=True)
    ds = ds.filter(lambda r: r["lang_pair"] in target_pairs)

    # Group by image_id (streaming-friendly; flush opportunistically)
    print(f"Grouping rows by image_id (target docs: {args.max_docs})...")
    groups: dict[str, list[dict]] = defaultdict(list)
    for row in ds:
        img_id = row["image_id"]
        groups[img_id].append(row)
        if len(groups) >= args.max_docs * 3:
            # We have enough candidates — stop scanning
            break
    print(f"  Collected {len(groups)} candidate image_ids")

    # Sort image_ids by number of pairs we got (highest first), then by id
    sorted_groups = sorted(
        groups.items(),
        key=lambda kv: (-len({r["lang_pair"] for r in kv[1]}), kv[0]),
    )

    kept = 0
    next_id = args.start_doc_id
    new_manifest_entries: list[dict] = []

    for img_id, rows in sorted_groups:
        if kept >= args.max_docs:
            break

        # Build per-pair merge_ocr dict
        per_pair_merge: dict[str, list[dict]] = {}
        rep_row = None
        for row in rows:
            rileykim_pair = row["lang_pair"]
            ltb_pair = LTB_PAIR_MAP.get(rileykim_pair)
            if ltb_pair is None:
                continue
            per_pair_merge[ltb_pair] = row["merge_ocr"]
            if rep_row is None:
                rep_row = row

        if rep_row is None or not per_pair_merge:
            continue

        regions = build_regions_from_merge_ocr(rep_row["merge_ocr"])
        if not regions:
            continue
        merge_translations_into_regions(regions, per_pair_merge)

        doc_id = f"doc_{next_id:03d}"
        image = rep_row["image"]
        w, h = image.size
        # Downsample if needed
        if w > args.max_image_width:
            ratio = args.max_image_width / w
            new_w = args.max_image_width
            new_h = int(h * ratio)
            image = image.resize((new_w, new_h))
            # Also rescale bboxes
            for region in regions:
                bx, by, bw, bh = region["bbox"]
                region["bbox"] = [
                    int(round(bx * ratio)),
                    int(round(by * ratio)),
                    int(round(bw * ratio)),
                    int(round(bh * ratio)),
                ]
            w, h = new_w, new_h

        annotation = {
            "doc_id": doc_id,
            "page_size": [w, h],
            "provenance": {
                "source": REPO_ID,
                "source_image_id": img_id,
                "license": "Apache-2.0",
                "grade": "ml-curated",
                "notes": "Reference translations are from rileykim/multilingual-document; quality is ML-curated (not certified-translator). Treat as v0.1.4 expansion data.",
            },
            "regions": regions,
        }

        if not args.dry_run:
            (ann_dir / f"{doc_id}.json").write_text(
                json.dumps(annotation, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            image.save(src_dir / f"{doc_id}.png")
            print(
                f"  + {doc_id} (img_id={img_id}, pairs={sorted(per_pair_merge.keys())}, "
                f"regions={len(regions)}, size={w}x{h})"
            )
        else:
            print(
                f"  [dry] {doc_id} (img_id={img_id}, pairs={sorted(per_pair_merge.keys())}, "
                f"regions={len(regions)}, size={w}x{h})"
            )

        new_manifest_entries.append(
            {
                "doc_id": doc_id,
                "category": "ocr-document",
                "source_file": f"{args.subdir}/sources/{doc_id}.png",
                "annotation_file": f"{args.subdir}/annotations/{doc_id}.json",
                "page_size": [w, h],
                "license": "Apache-2.0",
                "source_url": f"https://huggingface.co/datasets/{REPO_ID}",
            }
        )

        kept += 1
        next_id += 1

    print(f"\nIngested {kept} docs.")

    if not args.dry_run and new_manifest_entries:
        manifest_path = args.data_dir / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["entries"].extend(new_manifest_entries)
        manifest["version"] = "0.1.4"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"Updated {manifest_path} (version -> 0.1.4)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
