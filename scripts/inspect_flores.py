"""Inspect FLORES-200 HF dataset for LTB fallback suitability.

FLORES-200 (facebook/flores) is sentence-level only, no bboxes/layout — but it
is professional-translator quality across 200 languages including all 8 of our
LTB pairs. Use case: provide certified gold-reference sentences that we then
manually compose into LTB-format synthetic documents (one rendered page per
small group of sentences).

This script just verifies our 8 language codes are present and dumps sample
translations so we can decide on a composition strategy.
"""

from __future__ import annotations

import sys

from datasets import load_dataset

# FLORES-200 language codes (FLORES uses BCP-47-ish codes)
# Mapping LTB en-XX target lang codes -> FLORES-200 codes
LTB_TO_FLORES = {
    "en": "eng_Latn",
    "es": "spa_Latn",
    "de": "deu_Latn",
    "zh": "zho_Hans",
    "ar": "arb_Arab",
    "ja": "jpn_Jpan",
    "fr": "fra_Latn",
    "th": "tha_Thai",
    "ms": "zsm_Latn",
}


def main() -> int:
    print("== Loading facebook/flores (devtest split) ==")
    print("  Strategy: load English + one target at a time, check overlap")

    samples = {}
    for lang_short, flores_code in LTB_TO_FLORES.items():
        try:
            # FLORES-200 schema: load by lang code, single 'sentence' column
            ds = load_dataset("facebook/flores", flores_code, split="devtest")
        except Exception as exc:
            print(f"  FAIL {lang_short} ({flores_code}): {exc}")
            continue
        samples[lang_short] = {
            "code": flores_code,
            "n_rows": len(ds),
            "fields": list(ds.features.keys()),
            "sample_0": ds[0],
            "sample_500": ds[500] if len(ds) > 500 else None,
        }
        print(f"  OK {lang_short} ({flores_code}): {len(ds)} rows, fields={list(ds.features.keys())}")

    print(f"\n== Sample row 0 across all langs ==")
    if "en" in samples:
        en_text = samples["en"]["sample_0"].get("sentence", "<no sentence field>")
        print(f"  EN: {en_text!r}")
        for lang_short, info in samples.items():
            if lang_short == "en":
                continue
            target = info["sample_0"].get("sentence", "<no sentence field>")
            print(f"  {lang_short.upper()}: {target!r}")

    print(f"\n== Coverage summary ==")
    print(f"  LTB pairs covered: {len([k for k in samples if k != 'en'])} / 8")
    print(f"  Missing: {[k for k in LTB_TO_FLORES if k not in samples]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
