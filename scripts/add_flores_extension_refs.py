"""Enrich existing FLORES-derived docs with v0.1.6 extension-pair references.

The v0.1.5 composer (`scripts/compose_flores_docs.py`) only emitted refs for
the core 8 LTB pairs. FLORES-200 supports every v0.1.6 extension pair too —
this script back-fills those refs into doc_026 through doc_035 by:

  1. Loading `eng_Latn.devtest` (1012 source sentences)
  2. For each region's English `text`, finding the matching sentence index
  3. Looking up the parallel-aligned translation in each extension-pair
     FLORES file at that index
  4. Adding to the region's `references` dict

The annotation `provenance.grade` remains 'certified-translator' since the
new refs come from the same FLORES-200 source — NLLB project's professional
translators.

Effect on per-pair coverage (post-v0.1.6.4):

  | Pair | Before | After |
  |---|---|---|
  | en-ru | 0 | 10 |
  | en-ko | 3 (ml-curated) | 13 (3 ml + 10 certified) |
  | en-vi | 3 | 13 |
  | en-id | 3 | 13 |
  | en-ur | 3 | 13 |
  | en-uz | 3 | 13 |
  | en-kk | 3 | 13 |
  | en-zh-tw | 3 | 13 |

Run from repo root:

    python scripts/add_flores_extension_refs.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# v0.1.6 extension pairs only — core 8 are already covered.
EXTENSION_LTB_TO_FLORES = {
    "en-ru": "rus_Cyrl",
    "en-ko": "kor_Hang",
    "en-vi": "vie_Latn",
    "en-id": "ind_Latn",
    "en-ur": "urd_Arab",
    "en-uz": "uzn_Latn",  # Northern Uzbek (Latin script, post-2018 reform)
    "en-kk": "kaz_Cyrl",
    "en-zh-tw": "zho_Hant",
}

FLORES_DIR = Path(".flores-tmp/flores200_dataset")
ANN_DIR = Path("data/flores_derived/annotations")


def load_devtest(basename: str) -> list[str]:
    """Load 1012 sentences from one FLORES devtest file."""
    path = FLORES_DIR / "devtest" / f"{basename}.devtest"
    return path.read_text(encoding="utf-8").splitlines()


def main() -> int:
    if not FLORES_DIR.exists():
        print(f"ERROR: FLORES dataset not found at {FLORES_DIR}.")
        print("Download flores200_dataset.tar.gz into .flores-tmp/ first.")
        return 2

    # Source language: index map of English sentence -> sentence index
    eng_sentences = load_devtest("eng_Latn")
    eng_to_idx: dict[str, int] = {}
    for i, s in enumerate(eng_sentences):
        # Multiple identical sentences are rare; keep first occurrence
        eng_to_idx.setdefault(s, i)

    # Pre-load all extension-pair files
    pair_sentences: dict[str, list[str]] = {}
    for ltb_pair, flores_file in EXTENSION_LTB_TO_FLORES.items():
        pair_sentences[ltb_pair] = load_devtest(flores_file)

    n_docs_updated = 0
    n_regions_enriched = 0
    n_regions_unmatched = 0

    for ann_path in sorted(ANN_DIR.glob("doc_*.json")):
        ann = json.loads(ann_path.read_text(encoding="utf-8"))
        doc_id = ann["doc_id"]
        doc_changed = False
        for region in ann["regions"]:
            text = region.get("text", "").strip()
            if not text:
                continue
            idx = eng_to_idx.get(text)
            if idx is None:
                n_regions_unmatched += 1
                continue
            references = region.setdefault("references", {})
            for ltb_pair, sentences in pair_sentences.items():
                if ltb_pair in references:
                    # Skip if already present (idempotent)
                    continue
                translation = sentences[idx].strip()
                if translation:
                    references[ltb_pair] = translation
                    n_regions_enriched += 1
                    doc_changed = True
        if doc_changed:
            # Refresh provenance note: explicitly call out 16-pair coverage
            prov = ann.setdefault("provenance", {})
            notes = prov.get("notes", "") or ""
            marker = " [v0.1.7: enriched with 8 v0.1.6 extension-pair refs from FLORES-200]"
            if marker.strip() not in notes:
                prov["notes"] = (notes + marker).strip()
            ann_path.write_text(
                json.dumps(ann, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            n_docs_updated += 1
            print(f"  enriched {doc_id}")

    print(
        f"\nDone. Updated {n_docs_updated} docs / added "
        f"{n_regions_enriched} region refs / {n_regions_unmatched} unmatched."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
