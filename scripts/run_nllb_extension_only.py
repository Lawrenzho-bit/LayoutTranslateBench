"""Run NLLB-200 on just the 24 v0.1.6 extension docs.

The general run-nllb CLI command iterates every (doc, pair) combination. For
the v0.1.6 extension pairs, only 3 docs per pair carry references — running
the full 8 × 59 = 472 combinations wastes compute on 448 docs that the scorer
would drop anyway.

This script directly iterates the 24 rileykim-extension docs and translates
each one for its single target pair. Result: ONE NLLB model load + 24
translations + 8 jsonl append operations.

Run from repo root with the COMET-enabled venv that has transformers+torch:
    .comet-env/Scripts/python.exe scripts/run_nllb_extension_only.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from ltbench.runners.nllb_text import NllbTextRunner
from ltbench.schemas import Annotation, DocumentSubmission


# (pair, doc_id) targets — 24 total. Mirrors the import order in
# scripts/import_rileykim_extension.py.
TARGETS: list[tuple[str, str]] = [
    ("en-ru", "doc_036"),
    ("en-ru", "doc_037"),
    ("en-ru", "doc_038"),
    ("en-ko", "doc_039"),
    ("en-ko", "doc_040"),
    ("en-ko", "doc_041"),
    ("en-vi", "doc_042"),
    ("en-vi", "doc_043"),
    ("en-vi", "doc_044"),
    ("en-id", "doc_045"),
    ("en-id", "doc_046"),
    ("en-id", "doc_047"),
    ("en-ur", "doc_048"),
    ("en-ur", "doc_049"),
    ("en-ur", "doc_050"),
    ("en-uz", "doc_051"),
    ("en-uz", "doc_052"),
    ("en-uz", "doc_053"),
    ("en-kk", "doc_054"),
    ("en-kk", "doc_055"),
    ("en-kk", "doc_056"),
    ("en-zh-tw", "doc_057"),
    ("en-zh-tw", "doc_058"),
    ("en-zh-tw", "doc_059"),
]


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    data_root = repo_root / "data"
    submission_dir = repo_root / "submissions" / "nllb-text-oracle"
    submission_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading NLLB-200 ...")
    runner = NllbTextRunner()
    runner._ensure_loaded()
    print(f"Loaded on {runner._actual_device}.")

    # Group targets by pair so we append once per jsonl
    by_pair: dict[str, list[str]] = {}
    for pair, doc_id in TARGETS:
        by_pair.setdefault(pair, []).append(doc_id)

    n_written = 0
    for pair, doc_ids in by_pair.items():
        path = submission_dir / f"{pair}.jsonl"
        # Append mode — preserve any existing submissions for this pair
        with path.open("a", encoding="utf-8") as f:
            for doc_id in doc_ids:
                ann_path = (
                    data_root / "rileykim_derived" / "annotations" / f"{doc_id}.json"
                )
                if not ann_path.exists():
                    print(f"  MISSING: {ann_path}")
                    continue
                ann = Annotation.model_validate(
                    json.loads(ann_path.read_text(encoding="utf-8"))
                )
                sub: DocumentSubmission = runner.translate(ann, pair)  # type: ignore[arg-type]
                f.write(sub.model_dump_json() + "\n")
                n_written += 1
                rt = (
                    f" ({sub.runtime_seconds:.1f}s)"
                    if sub.runtime_seconds is not None
                    else ""
                )
                print(
                    f"  + {pair} / {doc_id} -> {len(sub.regions)} regions{rt}"
                )

    runner.close()
    print(f"\nWrote {n_written} extension-pair submissions to {submission_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
