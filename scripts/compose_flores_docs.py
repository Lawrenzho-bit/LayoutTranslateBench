"""Compose synthetic LTB documents from FLORES-200 devtest sentences.

FLORES-200 is a sentence-level parallel corpus with 1012 devtest sentences per
language, professionally translated. Sentences are grouped by source article
in metadata_devtest.tsv (the URL column). We exploit that grouping: consecutive
sentences from the same Wikinews article naturally form a coherent document.

Strategy per doc:
  1. Pick a Wikinews article with >= 5 consecutive sentences
  2. Take the first 5-7 sentences as LTB regions
  3. Layout: single column, top-down, first sentence as title-style,
     remaining as paragraph-style
  4. References: pull the parallel-aligned translation from each of the 8
     FLORES files for our LTB target langs
  5. Render PNG via the existing render_annotation utility

License segregation: outputs land in data/flores_derived/ with a CC-BY-SA-4.0
LICENSE file. The LTB core (data/annotations/, data/sources/) remains
CC-BY-4.0; per-doc license is recorded in manifest entries.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

# Reuse the existing renderer
sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_samples import render_annotation  # noqa: E402

# Map LTB pair codes -> FLORES-200 language file basenames
# v0.1.7: extended from 8 to 16 pairs so every FLORES doc carries
# certified-translator refs for the full LTB pair set.
LTB_TO_FLORES_FILE = {
    "en": "eng_Latn",
    # Core 8
    "en-es": "spa_Latn",
    "en-de": "deu_Latn",
    "en-zh": "zho_Hans",
    "en-ar": "arb_Arab",
    "en-ja": "jpn_Jpan",
    "en-fr": "fra_Latn",
    "en-th": "tha_Thai",
    "en-ms": "zsm_Latn",
    # v0.1.6 extension 8
    "en-ru": "rus_Cyrl",
    "en-ko": "kor_Hang",
    "en-vi": "vie_Latn",
    "en-id": "ind_Latn",
    "en-ur": "urd_Arab",
    "en-uz": "uzn_Latn",  # Northern Uzbek (Latin script, post-2018 reform)
    "en-kk": "kaz_Cyrl",
    "en-zh-tw": "zho_Hant",
}


def load_devtest(flores_dir: Path, file_basename: str) -> list[str]:
    """Load 1012 sentences from one FLORES devtest file."""
    path = flores_dir / "devtest" / f"{file_basename}.devtest"
    return path.read_text(encoding="utf-8").splitlines()


def load_metadata(flores_dir: Path) -> list[dict]:
    """Load metadata_devtest.tsv — one row per sentence index 0..1011."""
    path = flores_dir / "metadata_devtest.tsv"
    rows: list[dict] = []
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            rows.append(row)
    return rows


def group_by_article(metadata: list[dict]) -> list[tuple[str, list[int]]]:
    """Return [(url, [sentence_index, ...]), ...] in metadata order.

    Consecutive rows sharing the same URL form one article. We preserve order.
    """
    groups: list[tuple[str, list[int]]] = []
    current_url: str | None = None
    current_indices: list[int] = []
    for idx, row in enumerate(metadata):
        url = row.get("URL") or row.get("url") or ""
        if url != current_url:
            if current_url is not None and current_indices:
                groups.append((current_url, current_indices))
            current_url = url
            current_indices = []
        current_indices.append(idx)
    if current_url is not None and current_indices:
        groups.append((current_url, current_indices))
    return groups


def compose_doc(
    doc_id: str,
    article_url: str,
    topic: str,
    sentence_indices: list[int],
    eng_sentences: list[str],
    translations_per_pair: dict[str, list[str]],
    *,
    page_width: int = 800,
    page_height: int = 1100,
    margin_x: int = 50,
    margin_y_top: int = 60,
    title_size: int = 22,
    body_size: int = 14,
    title_height: int = 70,
    body_line_height: int = 140,
) -> dict:
    """Build an LTB Annotation dict for one synthetic FLORES-derived doc.

    First sentence becomes the title region; subsequent sentences become
    paragraph regions stacked vertically.
    """
    regions: list[dict] = []
    available_width = page_width - 2 * margin_x

    # Title region (first sentence)
    title_idx = sentence_indices[0]
    title_text = eng_sentences[title_idx]
    title_refs = {
        pair: translations_per_pair[pair][title_idx]
        for pair in translations_per_pair
    }
    regions.append(
        {
            "region_id": "r1",
            "bbox": [margin_x, margin_y_top, available_width, title_height],
            "text": title_text,
            "reading_order": 0,
            "layout_class": "title",
            "style": {"font_family": "serif", "size_hint": title_size, "bold": True},
            "references": title_refs,
        }
    )

    # Body regions (subsequent sentences)
    y_cursor = margin_y_top + title_height + 20
    for i, sentence_idx in enumerate(sentence_indices[1:], start=2):
        if y_cursor + body_line_height > page_height - margin_y_top:
            break  # would overflow
        body_text = eng_sentences[sentence_idx]
        body_refs = {
            pair: translations_per_pair[pair][sentence_idx]
            for pair in translations_per_pair
        }
        regions.append(
            {
                "region_id": f"r{i}",
                "bbox": [margin_x, y_cursor, available_width, body_line_height - 20],
                "text": body_text,
                "reading_order": i - 1,
                "layout_class": "paragraph",
                "style": {"font_family": "serif", "size_hint": body_size},
                "references": body_refs,
            }
        )
        y_cursor += body_line_height

    annotation = {
        "doc_id": doc_id,
        "page_size": [page_width, page_height],
        "provenance": {
            "source": "facebook/flores-200",
            "source_image_id": article_url,
            "license": "CC-BY-SA-4.0",
            "grade": "certified-translator",
            "notes": (
                "Reference translations are from FLORES-200 (Wikinews / Wikipedia "
                "source sentences, professionally translated). License is "
                "CC-BY-SA-4.0 (share-alike) — this annotation must be redistributed "
                f"under CC-BY-SA-4.0. Article topic: {topic!r}."
            ),
        },
        "regions": regions,
    }
    return annotation


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--flores-dir",
        type=Path,
        default=Path(".flores-tmp/flores200_dataset"),
        help="Path to extracted FLORES-200 dataset directory",
    )
    parser.add_argument("--max-docs", type=int, default=10)
    parser.add_argument("--start-doc-id", type=int, default=26)
    parser.add_argument("--min-sentences-per-article", type=int, default=5)
    parser.add_argument("--max-sentences-per-doc", type=int, default=6)
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--subdir", type=str, default="flores_derived")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not args.flores_dir.exists():
        print(f"FLORES dir not found: {args.flores_dir}")
        print(
            "Download via: curl -sL -o flores200_dataset.tar.gz "
            "https://dl.fbaipublicfiles.com/nllb/flores200_dataset.tar.gz "
            "&& tar xzf flores200_dataset.tar.gz"
        )
        return 2

    derived_dir = args.data_dir / args.subdir
    src_dir = derived_dir / "sources"
    ann_dir = derived_dir / "annotations"
    if not args.dry_run:
        src_dir.mkdir(parents=True, exist_ok=True)
        ann_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading FLORES devtest sentences for 9 languages...")
    sentences_by_short: dict[str, list[str]] = {}
    for short, basename in LTB_TO_FLORES_FILE.items():
        sentences = load_devtest(args.flores_dir, basename)
        print(f"  {short:6s} ({basename}): {len(sentences)} sentences")
        sentences_by_short[short] = sentences

    eng_sentences = sentences_by_short["en"]
    translations_per_pair = {
        pair: sentences_by_short[pair]
        for pair in LTB_TO_FLORES_FILE
        if pair != "en"
    }
    assert len(translations_per_pair) == 8, "expected 8 LTB pairs in translations"

    print(f"\nLoading metadata...")
    metadata = load_metadata(args.flores_dir)
    print(f"  {len(metadata)} metadata rows")

    print(f"Grouping by article URL...")
    groups = group_by_article(metadata)
    print(f"  {len(groups)} distinct articles")

    eligible = [
        (url, indices) for url, indices in groups if len(indices) >= args.min_sentences_per_article
    ]
    print(f"  {len(eligible)} articles with >= {args.min_sentences_per_article} sentences")

    # Take the first N eligible articles
    chosen = eligible[: args.max_docs]
    print(f"\nGenerating {len(chosen)} docs...")

    new_manifest_entries: list[dict] = []
    next_id = args.start_doc_id
    for article_url, sentence_indices in chosen:
        # Cap sentence count per doc
        capped_indices = sentence_indices[: args.max_sentences_per_doc]
        topic = metadata[sentence_indices[0]].get("topic", "").strip()
        doc_id = f"doc_{next_id:03d}"

        annotation = compose_doc(
            doc_id=doc_id,
            article_url=article_url,
            topic=topic,
            sentence_indices=capped_indices,
            eng_sentences=eng_sentences,
            translations_per_pair=translations_per_pair,
        )

        ann_path = ann_dir / f"{doc_id}.json"
        src_path = src_dir / f"{doc_id}.png"

        if not args.dry_run:
            ann_path.write_text(
                json.dumps(annotation, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            # Render the PNG
            render_annotation(ann_path, src_path)

        print(
            f"  + {doc_id} ({len(annotation['regions'])} regions, topic={topic!r:50s}, "
            f"url={article_url[:60]})"
        )

        new_manifest_entries.append(
            {
                "doc_id": doc_id,
                "category": "magazine-news",  # FLORES sources are Wikinews/Wikipedia
                "source_file": f"{args.subdir}/sources/{doc_id}.png",
                "annotation_file": f"{args.subdir}/annotations/{doc_id}.json",
                "page_size": [800, 1100],
                "license": "CC-BY-SA-4.0",
                "source_url": "https://github.com/facebookresearch/flores",
            }
        )

        next_id += 1

    print(f"\nGenerated {len(new_manifest_entries)} docs.")

    if not args.dry_run and new_manifest_entries:
        manifest_path = args.data_dir / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["entries"].extend(new_manifest_entries)
        manifest["version"] = "0.1.5"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"Updated {manifest_path} (version -> 0.1.5)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
