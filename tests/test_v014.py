"""Tests for v0.1.4 features:
  - Provenance schema (annotation-level metadata for external-source docs)
  - ocr-document category for heterogeneous external-source documents
  - Partial reference coverage permitted for non-author-curated docs
"""

from __future__ import annotations

import json
from pathlib import Path

from ltbench.schemas import (
    Annotation,
    Manifest,
    ManifestEntry,
    Provenance,
    Region,
    StyleHint,
)


def _make_region(pair: str, text_src: str = "Hello", text_tgt: str = "Hola") -> Region:
    return Region(
        region_id="r1",
        bbox=(0.0, 0.0, 100.0, 50.0),
        text=text_src,
        reading_order=0,
        layout_class="paragraph",
        style=StyleHint(),
        references={pair: text_tgt},
    )


def test_provenance_round_trip():
    p = Provenance(
        source="rileykim/multilingual-document",
        source_image_id="patimt_00001",
        license="Apache-2.0",
        grade="ml-curated",
        notes="test",
    )
    payload = p.model_dump()
    p2 = Provenance.model_validate(payload)
    assert p2.source == "rileykim/multilingual-document"
    assert p2.grade == "ml-curated"
    assert p2.source_image_id == "patimt_00001"


def test_annotation_without_provenance_still_valid():
    """v0.1, v0.1.3 author-curated docs have no provenance block — must still parse."""
    ann = Annotation(
        doc_id="doc_001",
        page_size=(800, 1100),
        regions=[_make_region("en-es")],
    )
    assert ann.provenance is None


def test_annotation_with_provenance_parses():
    """v0.1.4 docs from external sources record provenance."""
    payload = {
        "doc_id": "doc_011",
        "page_size": [1600, 2024],
        "provenance": {
            "source": "rileykim/multilingual-document",
            "source_image_id": "patimt_00000",
            "license": "Apache-2.0",
            "grade": "ml-curated",
        },
        "regions": [
            {
                "region_id": "r1",
                "bbox": [10, 10, 100, 50],
                "text": "hello",
                "reading_order": 0,
                "layout_class": "paragraph",
                "style": {"font_family": "serif", "size_hint": 13},
                "references": {"en-ja": "こんにちは"},
            }
        ],
    }
    ann = Annotation.model_validate(payload)
    assert ann.provenance is not None
    assert ann.provenance.grade == "ml-curated"
    assert ann.regions[0].references == {"en-ja": "こんにちは"}


def test_annotation_partial_reference_coverage_allowed():
    """v0.1.4 docs from external sources may carry references for only one pair."""
    ann = Annotation(
        doc_id="doc_011",
        page_size=(800, 1100),
        regions=[_make_region("en-ja", "Patent", "特許")],
        provenance=Provenance(
            source="rileykim/multilingual-document",
            license="Apache-2.0",
            grade="ml-curated",
        ),
    )
    # Should not raise — schema doesn't require all 8 pairs in references.
    assert set(ann.regions[0].references.keys()) == {"en-ja"}


def test_ocr_document_category_in_manifest():
    """v0.1.4 adds 'ocr-document' as a valid Category literal."""
    entry = ManifestEntry(
        doc_id="doc_011",
        category="ocr-document",
        source_file="rileykim_derived/sources/doc_011.png",
        annotation_file="rileykim_derived/annotations/doc_011.json",
        page_size=(1600, 2024),
        license="Apache-2.0",
        source_url="https://huggingface.co/datasets/rileykim/multilingual-document",
    )
    assert entry.category == "ocr-document"


def test_real_v014_manifest_parses_if_present():
    """The actual data/manifest.json after v0.1.4 ingest should round-trip."""
    manifest_path = Path(__file__).resolve().parent.parent / "data" / "manifest.json"
    if not manifest_path.exists():
        return  # skip in environments without the dataset
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest = Manifest.model_validate(payload)
    # If a v0.1.4 ingest already ran, version should be >= 0.1.4
    assert manifest.version.startswith("0.1")
    # Every entry should have an annotation file that parses
    data_root = manifest_path.parent
    for entry in manifest.entries:
        ann_path = data_root / entry.annotation_file
        if not ann_path.exists():
            continue
        Annotation.model_validate(json.loads(ann_path.read_text(encoding="utf-8")))


def test_real_v014_per_pair_doc_counts():
    """If v0.1.4 ran, partial-coverage docs should give expected per-pair counts."""
    manifest_path = Path(__file__).resolve().parent.parent / "data" / "manifest.json"
    if not manifest_path.exists():
        return
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not payload.get("version", "").startswith("0.1.4"):
        return
    data_root = manifest_path.parent
    pair_counts: dict[str, int] = {}
    for entry in payload["entries"]:
        ann_path = data_root / entry["annotation_file"]
        if not ann_path.exists():
            continue
        ann = json.loads(ann_path.read_text(encoding="utf-8"))
        doc_pairs = set()
        for region in ann["regions"]:
            for pair in region["references"]:
                doc_pairs.add(pair)
        for p in doc_pairs:
            pair_counts[p] = pair_counts.get(p, 0) + 1
    # All 6 non-overlap pairs should have at least 10 docs (the v0.1.3 author-curated set)
    for p in ("en-es", "en-de", "en-ar", "en-fr", "en-th", "en-ms"):
        assert pair_counts.get(p, 0) >= 10, f"{p} should have >= 10 docs, got {pair_counts.get(p, 0)}"
    # en-ja and en-zh should be > 10 (author + rileykim expansion)
    assert pair_counts.get("en-ja", 0) > 10
    assert pair_counts.get("en-zh", 0) > 10
