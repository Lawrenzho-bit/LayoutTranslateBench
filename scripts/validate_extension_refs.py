"""Validate v0.1.6 extension pair references for script-mismatch corruption.

The rileykim/multilingual-document dataset has a labeling bug where some rows
tagged `lang_pair="en-ru"` (or other extension pairs) actually carry tgt_text
in a completely different script (Simplified Chinese, for example). This
silently corrupts the LTB scoring for those pairs.

This script:
  1. Iterates annotations doc_036 through doc_059 (the v0.1.6 extension docs)
  2. For each annotation, detects the dominant script of its references in
     the declared target pair
  3. Flags refs whose script does NOT match the expected script for the pair
  4. With --fix, REMOVES the bad refs from the annotation file (the doc still
     exists for layout-fidelity testing, but won't score for that pair)

Usage:
    python scripts/validate_extension_refs.py            # report only
    python scripts/validate_extension_refs.py --fix      # remove bad refs
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Expected scripts per target pair. Dominant-script-fraction is computed
# against alphabetic chars only; any pair whose ref scores < FRACTION_OK on
# the expected script is flagged.
EXPECTED_SCRIPT = {
    "en-ru": "cyrillic",
    "en-ko": "hangul",
    "en-vi": "latin",
    "en-id": "latin",
    "en-ur": "arabic",
    "en-uz": "latin",  # post-2018 reform
    "en-kk": "cyrillic",
    "en-zh-tw": "han",
    # core 8 (sanity check; should never trip)
    "en-es": "latin",
    "en-de": "latin",
    "en-fr": "latin",
    "en-ms": "latin",
    "en-th": "thai",
    "en-zh": "han",
    "en-ja": "japanese",  # Hiragana/Katakana/Han
    "en-ar": "arabic",
}

FRACTION_OK = 0.5  # at least half of alpha chars must be in the expected script


def _char_script(cp: int) -> str | None:
    if cp < 256 and chr(cp).isalpha():
        return "latin"
    if 0x0400 <= cp <= 0x04FF:
        return "cyrillic"
    if 0xAC00 <= cp <= 0xD7AF or 0x1100 <= cp <= 0x11FF or 0x3130 <= cp <= 0x318F:
        return "hangul"
    if (
        0x0600 <= cp <= 0x06FF
        or 0x0750 <= cp <= 0x077F
        or 0x08A0 <= cp <= 0x08FF
        or 0xFB50 <= cp <= 0xFDFF
        or 0xFE70 <= cp <= 0xFEFF
    ):
        return "arabic"
    if 0x4E00 <= cp <= 0x9FFF or 0x3400 <= cp <= 0x4DBF:
        return "han"
    if 0x3040 <= cp <= 0x309F or 0x30A0 <= cp <= 0x30FF or 0xFF66 <= cp <= 0xFF9F:
        return "japanese"
    if 0x0E00 <= cp <= 0x0E7F:
        return "thai"
    return None


def script_fraction(text: str, expected: str) -> float:
    """Fraction of alphabetic chars in `text` that match `expected` script."""
    counts: dict[str, int] = {}
    n_alpha = 0
    for ch in text:
        script = _char_script(ord(ch))
        if script is None:
            continue
        # 'japanese' is "Hiragana+Katakana+Han"; 'han' overlaps; treat them
        # as compatible
        n_alpha += 1
        if expected == "japanese" and script in ("han", "japanese"):
            counts[expected] = counts.get(expected, 0) + 1
        elif script == expected:
            counts[expected] = counts.get(expected, 0) + 1
        else:
            counts[script] = counts.get(script, 0) + 1
    if n_alpha == 0:
        return 1.0  # fail-open on no-alpha
    return counts.get(expected, 0) / n_alpha


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fix", action="store_true", help="Remove bad refs in place")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data/rileykim_derived/annotations"),
        help="Directory of rileykim-derived annotations",
    )
    args = parser.parse_args()

    # Region-level validation: drop individual region refs whose script
    # doesn't match the expected target for the pair.
    bad_regions: list[tuple[str, str, str, float]] = []
    for ann_path in sorted(args.data_dir.glob("doc_*.json")):
        ann = json.loads(ann_path.read_text(encoding="utf-8"))
        doc_id = ann["doc_id"]
        # Each rileykim ann has a single-pair references dict.
        ref_pairs: set[str] = set()
        for region in ann["regions"]:
            ref_pairs.update(region["references"].keys())
        for pair in sorted(ref_pairs):
            expected = EXPECTED_SCRIPT.get(pair)
            if expected is None:
                continue
            n_dropped = 0
            for region in ann["regions"]:
                ref = region["references"].get(pair, "")
                if not ref:
                    continue
                frac = script_fraction(ref, expected)
                if frac < FRACTION_OK:
                    bad_regions.append((doc_id, region["region_id"], pair, frac))
                    n_dropped += 1
                    if args.fix:
                        del region["references"][pair]
            if n_dropped:
                print(
                    f"  {doc_id}  pair={pair:8s}  expected={expected:10s}  "
                    f"dropped {n_dropped}/{len(ann['regions'])} region refs"
                )
                if args.fix:
                    prov = ann.setdefault("provenance", {})
                    notes = prov.get("notes", "") or ""
                    marker = (
                        f" [v0.1.6.4: dropped {n_dropped} {pair} region refs "
                        f"due to script mismatch]"
                    )
                    if marker.strip() not in notes:
                        prov["notes"] = (notes + marker).strip()

        if args.fix:
            ann_path.write_text(
                json.dumps(ann, ensure_ascii=False, indent=2), encoding="utf-8"
            )

    print(f"\nBAD: {len(bad_regions)} region refs with script mismatch:")
    if args.fix:
        print(f"Fixed in place — dropped from annotations.")
    else:
        print(f"Dry-run only. Re-run with --fix to drop the bad refs.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
