"""Batch-import 3 rileykim docs per v0.1.6 extension pair.

Calls scripts/import_rileykim_parquet.py once per new pair. Each call grows
data/manifest.json by 3 entries; this script chains all 8 calls so the doc_ids
land contiguously (doc_036–doc_059).

Pairs added (in order): en-ru, en-ko, en-vi, en-id, en-ur, en-uz, en-kk, en-zh-tw

Run from repo root:
    python scripts/import_rileykim_extension.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

EXTENSION_PAIRS_ORDER = [
    "en-ru",
    "en-ko",
    "en-vi",
    "en-id",
    "en-ur",
    "en-uz",
    "en-kk",
    "en-zh-tw",
]
DOCS_PER_PAIR = 3
START_DOC_ID = 36


def main() -> int:
    py = sys.executable
    script = Path(__file__).resolve().parent / "import_rileykim_parquet.py"
    next_id = START_DOC_ID

    for pair in EXTENSION_PAIRS_ORDER:
        print(f"\n=== Importing {pair} starting at doc_{next_id:03d} ===")
        proc = subprocess.run(
            [
                py,
                str(script),
                "--target-pair",
                pair,
                "--max-docs",
                str(DOCS_PER_PAIR),
                "--start-doc-id",
                str(next_id),
            ],
            check=False,
        )
        if proc.returncode != 0:
            print(f"FAIL {pair}: exit code {proc.returncode}")
            return proc.returncode
        next_id += DOCS_PER_PAIR

    print("\nAll 8 extension pairs imported.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
