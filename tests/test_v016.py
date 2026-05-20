"""Tests for v0.1.6 features:
  - LangPair Literal extended from 8 to 16 pairs
  - CORE_LANG_PAIRS subset to avoid retroactive coverage breakage on
    author-curated and certified-translator docs
  - rileykim adapter updated for all 10 source pairs
  - NLLB runner code map covers all 16 LTB pairs (NLLB-200 supports all 200)
  - Language-detection gate has rules for the 8 new pairs
"""

from __future__ import annotations

import json
from pathlib import Path

from ltbench import CORE_LANG_PAIRS, LANG_PAIRS
from ltbench.metrics.language import is_target_language
from ltbench.runners.nllb_text import _LANG_PAIR_TO_NLLB
from ltbench.schemas import LangPair


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def test_lang_pairs_count():
    """v0.1.6 declares 16 supported pairs."""
    assert len(LANG_PAIRS) == 16


def test_core_lang_pairs_unchanged():
    """The CORE_LANG_PAIRS subset is exactly the v0.1 core 8 — author docs
    are required to cover this set, not the extended one."""
    assert CORE_LANG_PAIRS == (
        "en-es",
        "en-de",
        "en-zh",
        "en-ar",
        "en-ja",
        "en-fr",
        "en-th",
        "en-ms",
    )


def test_extension_pairs_present():
    """All 8 extension pairs must be in LANG_PAIRS."""
    extension = {"en-ru", "en-ko", "en-vi", "en-id", "en-ur", "en-uz", "en-kk", "en-zh-tw"}
    assert extension.issubset(set(LANG_PAIRS))


def test_nllb_runner_supports_all_16_pairs():
    """NLLB-200 supports all 200+ languages — the runner's code map must
    cover every LTB pair, including the v0.1.6 extension."""
    for pair in LANG_PAIRS:
        assert pair in _LANG_PAIR_TO_NLLB, f"NLLB code missing for {pair}"


def test_language_detection_recognizes_extension_pairs_via_script():
    """For non-Latin extension pairs (en-ru, en-ko, en-ur, en-zh-tw, en-kk),
    a sample target-script string should pass the language gate; a clearly
    English string should fail."""
    cases = [
        # (pair, target-script sample, expected pass?)
        ("en-ru", "Привет мир, это тестовый текст на русском языке.", True),
        ("en-ru", "Hello world, this is a long English sentence.", False),
        ("en-ko", "안녕하세요 이것은 한국어 테스트 문장입니다.", True),
        ("en-ko", "Hello world, this is a long English sentence.", False),
        ("en-ur", "یہ ایک اردو زبان میں ٹیسٹ جملہ ہے۔", True),
        ("en-zh-tw", "這是一個用繁體中文寫成的測試句子。", True),
        ("en-kk", "Бұл қазақ тіліндегі сынақ сөйлем.", True),
    ]
    for pair, text, expected in cases:
        result = is_target_language(text, pair)
        assert result == expected, (
            f"{pair}: is_target_language({text!r}) -> {result}, expected {expected}"
        )


def test_language_detection_latin_extension_pairs_fail_open_on_short():
    """For Latin-script extension pairs (en-vi, en-id, en-uz), short strings
    pass the gate (fail-open behavior). This is by design — short strings
    are unreliable for langdetect."""
    cases = ["en-vi", "en-id", "en-uz"]
    for pair in cases:
        # Empty + short clean text should pass (fail open)
        assert is_target_language("", pair) is True
        assert is_target_language("abc", pair) is True


def test_rileykim_extension_docs_have_provenance():
    """If v0.1.6 ingest ran, the new docs (doc_036–doc_059) must declare
    ml-curated provenance from rileykim."""
    from ltbench.schemas import Annotation

    rileykim_ann = _repo_root() / "data" / "rileykim_derived" / "annotations"
    if not rileykim_ann.exists():
        return
    extension_docs = []
    for path in sorted(rileykim_ann.glob("doc_*.json")):
        doc_num = int(path.stem.split("_")[1])
        if doc_num >= 36:
            extension_docs.append(path)
    if not extension_docs:
        return
    for path in extension_docs:
        ann = Annotation.model_validate(
            json.loads(path.read_text(encoding="utf-8"))
        )
        assert ann.provenance is not None
        assert ann.provenance.grade == "ml-curated"
        assert ann.provenance.license == "Apache-2.0"


def test_real_v016_manifest_per_pair_counts():
    """At v0.1.6 with rileykim extension and v0.1.6.4 script-validation cleanup,
    per-pair coverage shifts: en-ru has 0 docs after cleanup (the rileykim
    en-ru rows had Chinese-script refs); other extension pairs retain >= 1
    doc each. Core 8 pairs retain their v0.1.5 targets."""
    manifest_path = _repo_root() / "data" / "manifest.json"
    if not manifest_path.exists():
        return
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not payload.get("version", "").startswith("0.1.6"):
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
    # v0.1.6.4: en-ru lost all 3 docs after script-validation removed the
    # mislabeled rileykim refs. Other extension pairs retain partial coverage.
    # Allow >=0 for en-ru, >=1 for others.
    surviving_extension_pairs = ("en-ko", "en-vi", "en-id", "en-ur", "en-uz", "en-kk", "en-zh-tw")
    for pair in surviving_extension_pairs:
        assert pair_counts.get(pair, 0) >= 1, (
            f"{pair} should have >= 1 doc after v0.1.6.4 cleanup, got {pair_counts.get(pair, 0)}"
        )
    # en-ru is expected to be zero after cleanup
    assert pair_counts.get("en-ru", 0) == 0, (
        f"en-ru should be 0 after v0.1.6.4 cleanup (rileykim refs were all "
        f"Chinese), got {pair_counts.get('en-ru', 0)}"
    )
    # Core 8 pairs should still meet v0.1.5 targets (20 for non-overlap, 27+ for ja/zh)
    for pair in ("en-es", "en-de", "en-ar", "en-fr", "en-th", "en-ms"):
        assert pair_counts.get(pair, 0) >= 20
    assert pair_counts.get("en-ja", 0) >= 28
    assert pair_counts.get("en-zh", 0) >= 27
