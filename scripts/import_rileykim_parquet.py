"""Faster rileykim importer: reads cached parquet files directly.

Use this when streaming is slow (e.g. en-zh-cn rows live near the end of the
27-shard dataset). Walks shards in REVERSE order so we hit en-zh-tw / en-zh-cn
quickly.

Usage:
  python scripts/import_rileykim_parquet.py --target-pair en-zh-cn --max-docs 7 --start-doc-id 19
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path

import pyarrow.parquet as pq
from PIL import Image

REPO_ID = "rileykim/multilingual-document"
CACHE_ROOT = Path(
    "C:/Users/asus/.cache/huggingface/hub/datasets--rileykim--multilingual-document/snapshots"
)

LTB_PAIR_MAP = {
    # Direct overlaps with LTB v0.1.5 (core 8 pairs)
    "en-ja": "en-ja",
    "en-zh-cn": "en-zh",
    # v0.1.6 extension pairs
    "en-ru": "en-ru",
    "en-ko": "en-ko",
    "en-vi": "en-vi",
    "en-id": "en-id",
    "en-ur": "en-ur",
    "en-uz": "en-uz",
    "en-kk": "en-kk",
    "en-zh-tw": "en-zh-tw",
}


def find_train_parquet_shards() -> list[Path]:
    """Locate all train-*.parquet files in cache, in shard-index order."""
    shards: list[Path] = []
    for snapshot_dir in CACHE_ROOT.iterdir():
        data_dir = snapshot_dir / "data"
        if not data_dir.is_dir():
            continue
        shards.extend(sorted(data_dir.glob("train-*.parquet")))
        break
    return shards


def xyxy_to_xywh(bbox: list[float]) -> list[int]:
    x1, y1, x2, y2 = bbox
    return [
        int(round(x1)),
        int(round(y1)),
        int(round(max(0, x2 - x1))),
        int(round(max(0, y2 - y1))),
    ]


# v0.1.6.4: ingest-time script validation. Skip ref additions whose tgt_text
# script does not match the expected script for the LTB target language.
# Mirrors scripts/validate_extension_refs.py.
_EXPECTED_SCRIPT_AT_INGEST = {
    "en-es": "latin", "en-de": "latin", "en-fr": "latin", "en-vi": "latin",
    "en-id": "latin", "en-ms": "latin", "en-uz": "latin",
    "en-zh": "han", "en-zh-tw": "han",
    "en-ru": "cyrillic", "en-kk": "cyrillic",
    "en-ar": "arabic", "en-ur": "arabic",
    "en-ko": "hangul",
    "en-th": "thai",
    "en-ja": "japanese",
}


def _char_script_at_ingest(cp: int) -> str | None:
    if cp < 256 and chr(cp).isalpha():
        return "latin"
    if 0x0400 <= cp <= 0x04FF:
        return "cyrillic"
    if 0xAC00 <= cp <= 0xD7AF or 0x1100 <= cp <= 0x11FF or 0x3130 <= cp <= 0x318F:
        return "hangul"
    if 0x0600 <= cp <= 0x06FF or 0x0750 <= cp <= 0x077F or 0xFB50 <= cp <= 0xFDFF or 0xFE70 <= cp <= 0xFEFF:
        return "arabic"
    if 0x4E00 <= cp <= 0x9FFF or 0x3400 <= cp <= 0x4DBF:
        return "han"
    if 0x3040 <= cp <= 0x309F or 0x30A0 <= cp <= 0x30FF:
        return "japanese"
    if 0x0E00 <= cp <= 0x0E7F:
        return "thai"
    return None


def _script_matches(text: str, expected: str, min_fraction: float = 0.5) -> bool:
    n_alpha = 0
    n_match = 0
    for ch in text:
        script = _char_script_at_ingest(ord(ch))
        if script is None:
            continue
        n_alpha += 1
        if expected == "japanese" and script in ("japanese", "han"):
            n_match += 1
        elif script == expected:
            n_match += 1
    if n_alpha == 0:
        return True  # fail-open on no alpha
    return (n_match / n_alpha) >= min_fraction


def build_regions_from_merge_ocr(merge_ocr_arr, ltb_pair: str | None = None) -> list[dict]:
    """Build LTB regions from rileykim merge_ocr entries.

    v0.1.6.4: when ltb_pair is provided, validate each tgt_text against the
    expected script for that pair and skip refs that fail validation. This
    catches rileykim's labeling bugs (e.g. en-ru rows with Chinese tgt_text).
    """
    expected_script = _EXPECTED_SCRIPT_AT_INGEST.get(ltb_pair) if ltb_pair else None
    n_filtered = 0
    regions: list[dict] = []
    for idx, seg in enumerate(merge_ocr_arr):
        box = list(seg["box"])
        src_text = (seg.get("src_text") or "").strip()
        tgt_text = (seg.get("tgt_text") or "").strip()
        if not box or not src_text:
            continue
        region = {
            "region_id": f"r{idx + 1}",
            "bbox": xyxy_to_xywh(box),
            "text": src_text,
            "reading_order": idx,
            "layout_class": "paragraph",
            "style": {"font_family": "serif", "size_hint": 13},
            "references": {},
        }
        if tgt_text:
            # Validate script before attaching
            if expected_script is None or _script_matches(tgt_text, expected_script):
                region["_tgt_text"] = tgt_text
            else:
                n_filtered += 1
        regions.append(region)
    if n_filtered:
        print(f"    (script-filter dropped {n_filtered} region refs for pair={ltb_pair})")
    return regions


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-pair", required=True, help="rileykim pair code, e.g. en-zh-cn")
    parser.add_argument("--max-docs", type=int, default=10)
    parser.add_argument("--start-doc-id", type=int, default=11)
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--subdir", type=str, default="rileykim_derived")
    parser.add_argument("--max-image-width", type=int, default=1600)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--shard-order",
        choices=["forward", "reverse"],
        default="reverse",
        help="Reverse hits en-zh-cn/en-zh-tw earlier",
    )
    args = parser.parse_args()

    ltb_pair = LTB_PAIR_MAP.get(args.target_pair)
    if ltb_pair is None:
        print(f"target-pair {args.target_pair} has no LTB mapping; aborting.")
        return 2

    derived_dir = args.data_dir / args.subdir
    src_dir = derived_dir / "sources"
    ann_dir = derived_dir / "annotations"
    if not args.dry_run:
        src_dir.mkdir(parents=True, exist_ok=True)
        ann_dir.mkdir(parents=True, exist_ok=True)

    shards = find_train_parquet_shards()
    if args.shard_order == "reverse":
        shards = list(reversed(shards))
    print(f"Scanning {len(shards)} shards (order={args.shard_order})...")

    kept = 0
    next_id = args.start_doc_id
    new_manifest_entries: list[dict] = []

    for shard in shards:
        if kept >= args.max_docs:
            break
        print(f"  shard: {shard.name}")
        table = pq.read_table(shard)
        cols = table.column_names
        # convert to row-oriented iteration via to_pylist (decodes images lazily)
        rows = table.to_pylist()
        for row in rows:
            if kept >= args.max_docs:
                break
            if row.get("lang_pair") != args.target_pair:
                continue

            merge_ocr = row.get("merge_ocr") or []
            regions = build_regions_from_merge_ocr(merge_ocr, ltb_pair=ltb_pair)
            if not regions:
                continue
            # Attach translations under the LTB pair
            for region in regions:
                tgt = region.pop("_tgt_text", None)
                if tgt:
                    region["references"][ltb_pair] = tgt

            # Decode image bytes -> PIL
            img_obj = row.get("image")
            if isinstance(img_obj, dict) and "bytes" in img_obj:
                img = Image.open(io.BytesIO(img_obj["bytes"]))
            elif isinstance(img_obj, (bytes, bytearray)):
                img = Image.open(io.BytesIO(img_obj))
            else:
                # If decoded earlier
                img = img_obj
            if img is None:
                continue
            w, h = img.size

            # Downsample if wide
            if w > args.max_image_width:
                ratio = args.max_image_width / w
                new_w = args.max_image_width
                new_h = int(h * ratio)
                img = img.resize((new_w, new_h))
                for region in regions:
                    bx, by, bw, bh = region["bbox"]
                    region["bbox"] = [
                        int(round(bx * ratio)),
                        int(round(by * ratio)),
                        int(round(bw * ratio)),
                        int(round(bh * ratio)),
                    ]
                w, h = new_w, new_h

            doc_id = f"doc_{next_id:03d}"
            annotation = {
                "doc_id": doc_id,
                "page_size": [w, h],
                "provenance": {
                    "source": REPO_ID,
                    "source_image_id": row.get("image_id"),
                    "license": "Apache-2.0",
                    "grade": "ml-curated",
                    "notes": (
                        "Reference translations are from rileykim/multilingual-document; "
                        "quality is ml-curated (not certified-translator). Treat as "
                        "v0.1.4 expansion data."
                    ),
                },
                "regions": regions,
            }

            if not args.dry_run:
                if img.mode != "RGB":
                    img = img.convert("RGB")
                img.save(src_dir / f"{doc_id}.png")
                (ann_dir / f"{doc_id}.json").write_text(
                    json.dumps(annotation, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                print(
                    f"  + {doc_id} (img_id={row.get('image_id')}, "
                    f"pair={args.target_pair}->{ltb_pair}, regions={len(regions)}, size={w}x{h})"
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

    print(f"\nIngested {kept} docs from {args.target_pair}.")

    if not args.dry_run and new_manifest_entries:
        manifest_path = args.data_dir / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["entries"].extend(new_manifest_entries)
        # Use the highest version we've ever set as a floor (don't downgrade)
        prev_version = manifest.get("version", "0.1.0")
        target_version = "0.1.6"
        manifest["version"] = max(prev_version, target_version)
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"Updated {manifest_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
