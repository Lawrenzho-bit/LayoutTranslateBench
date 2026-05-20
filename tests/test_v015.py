"""Tests for v0.1.5 features:
  - FLORES-200 integration: 10 synthetic docs with certified-translator refs
  - License segregation: data/flores_derived/ uses CC-BY-SA-4.0
  - Per-pair sample size growth from N=10 to N=20 (6 pairs) and beyond
"""

from __future__ import annotations

import json
from pathlib import Path

from ltbench.schemas import Annotation, Manifest


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def test_flores_derived_directory_exists():
    """If v0.1.5 ran, the segregated dir + LICENSE must exist."""
    root = _repo_root()
    flores_dir = root / "data" / "flores_derived"
    if not flores_dir.exists():
        return  # skip if v0.1.5 hasn't been built
    assert (flores_dir / "LICENSE").exists(), "FLORES-derived dir must have LICENSE file"
    assert (flores_dir / "README.md").exists()
    license_text = (flores_dir / "LICENSE").read_text(encoding="utf-8")
    assert "CC-BY-SA-4.0" in license_text


def test_flores_docs_carry_certified_translator_grade():
    """Each FLORES-derived doc must declare certified-translator grade in provenance."""
    root = _repo_root()
    flores_ann_dir = root / "data" / "flores_derived" / "annotations"
    if not flores_ann_dir.exists():
        return
    for ann_path in sorted(flores_ann_dir.glob("doc_*.json")):
        ann = Annotation.model_validate(
            json.loads(ann_path.read_text(encoding="utf-8"))
        )
        assert ann.provenance is not None, f"{ann_path.name} missing provenance"
        assert ann.provenance.grade == "certified-translator", (
            f"{ann_path.name} grade was {ann.provenance.grade}, expected certified-translator"
        )
        assert ann.provenance.license == "CC-BY-SA-4.0"
        assert "facebook/flores" in ann.provenance.source


def test_flores_docs_have_all_ltb_pairs():
    """FLORES coverage:
      - v0.1.5 ships refs for the core 8 LTB pairs on every region of every doc.
      - v0.1.7 enriches with the v0.1.6 extension 8 pairs, so the full 16 are
        present on every region.
    This test accepts both — the core 8 are required, the extension 8 is
    optional (its presence reflects v0.1.7+ data)."""
    root = _repo_root()
    flores_ann_dir = root / "data" / "flores_derived" / "annotations"
    if not flores_ann_dir.exists():
        return
    core_pairs = {"en-es", "en-de", "en-zh", "en-ar", "en-ja", "en-fr", "en-th", "en-ms"}
    extension_pairs = {"en-ru", "en-ko", "en-vi", "en-id", "en-ur", "en-uz", "en-kk", "en-zh-tw"}
    valid_supersets = (core_pairs, core_pairs | extension_pairs)
    for ann_path in sorted(flores_ann_dir.glob("doc_*.json")):
        ann = Annotation.model_validate(
            json.loads(ann_path.read_text(encoding="utf-8"))
        )
        for region in ann.regions:
            ref_set = set(region.references.keys())
            assert ref_set in valid_supersets, (
                f"{ann_path.name}/{region.region_id} pair set was "
                f"{ref_set}, expected either core 8 or core+extension 16"
            )


def test_v015_manifest_records_cc_by_sa_license_for_flores_entries():
    """Manifest entries for FLORES-derived docs must record CC-BY-SA-4.0."""
    root = _repo_root()
    manifest_path = root / "data" / "manifest.json"
    if not manifest_path.exists():
        return
    manifest = Manifest.model_validate(
        json.loads(manifest_path.read_text(encoding="utf-8"))
    )
    if not manifest.version.startswith("0.1.5"):
        return
    flores_entries = [
        e for e in manifest.entries if "flores_derived" in e.source_file
    ]
    assert len(flores_entries) > 0, "expected at least one FLORES-derived entry"
    for e in flores_entries:
        assert e.license == "CC-BY-SA-4.0", f"{e.doc_id} license was {e.license}"


def test_v015_per_pair_sample_growth():
    """At v0.1.5: 6 non-overlap pairs at N=20, en-ja at N=28, en-zh at N=27."""
    root = _repo_root()
    manifest_path = root / "data" / "manifest.json"
    if not manifest_path.exists():
        return
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not payload.get("version", "").startswith("0.1.5"):
        return
    data_root = manifest_path.parent
    pair_counts: dict[str, int] = {}
    for entry in payload["entries"]:
        ann_path = data_root / entry["annotation_file"]
        if not ann_path.exists():
            continue
        ann = json.loads(ann_path.read_text(encoding="utf-8"))
        doc_pairs: set[str] = set()
        for region in ann["regions"]:
            doc_pairs.update(region["references"].keys())
        for p in doc_pairs:
            pair_counts[p] = pair_counts.get(p, 0) + 1
    # 6 non-overlap pairs: 10 author-curated + 10 FLORES = 20
    for p in ("en-es", "en-de", "en-ar", "en-fr", "en-th", "en-ms"):
        assert pair_counts.get(p, 0) == 20, (
            f"{p} should have 20 docs (10 author + 10 FLORES), got {pair_counts.get(p, 0)}"
        )
    # en-ja: 10 author + 8 rileykim + 10 FLORES = 28
    assert pair_counts.get("en-ja", 0) == 28, (
        f"en-ja should have 28 docs, got {pair_counts.get('en-ja', 0)}"
    )
    # en-zh: 10 author + 7 rileykim + 10 FLORES = 27
    assert pair_counts.get("en-zh", 0) == 27, (
        f"en-zh should have 27 docs, got {pair_counts.get('en-zh', 0)}"
    )


def test_flores_docs_use_magazine_news_category():
    """All FLORES-derived docs are categorized as magazine-news (Wikinews source)."""
    root = _repo_root()
    manifest_path = root / "data" / "manifest.json"
    if not manifest_path.exists():
        return
    manifest = Manifest.model_validate(
        json.loads(manifest_path.read_text(encoding="utf-8"))
    )
    flores_entries = [
        e for e in manifest.entries if "flores_derived" in e.source_file
    ]
    for e in flores_entries:
        assert e.category == "magazine-news", (
            f"{e.doc_id} category was {e.category}, expected magazine-news"
        )
