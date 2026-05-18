"""Loaders for manifest, annotation files, and submission JSONL files."""

from __future__ import annotations

import json
from pathlib import Path

from ltbench.schemas import (
    Annotation,
    DocumentSubmission,
    LangPair,
    Manifest,
    SystemManifest,
)


def load_manifest(path: Path | str) -> Manifest:
    path = Path(path)
    with path.open("r", encoding="utf-8") as f:
        return Manifest.model_validate(json.load(f))


def load_annotation(path: Path | str) -> Annotation:
    path = Path(path)
    with path.open("r", encoding="utf-8") as f:
        return Annotation.model_validate(json.load(f))


def load_submission(
    submission_dir: Path | str,
) -> tuple[SystemManifest, dict[LangPair, list[DocumentSubmission]]]:
    """Load a system submission from a directory.

    Expected structure:
        submissions/<system-name>/
            manifest.json       # SystemManifest
            en-es.jsonl         # one DocumentSubmission per line
            en-de.jsonl
            ...
    """
    submission_dir = Path(submission_dir)
    manifest_path = submission_dir / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"missing system manifest: {manifest_path}")
    with manifest_path.open("r", encoding="utf-8") as f:
        system = SystemManifest.model_validate(json.load(f))

    per_pair: dict[LangPair, list[DocumentSubmission]] = {}
    for jsonl in sorted(submission_dir.glob("*.jsonl")):
        lang_pair = jsonl.stem
        if lang_pair not in ("en-es", "en-de", "en-zh", "en-ar", "en-ja"):
            continue
        docs: list[DocumentSubmission] = []
        with jsonl.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                docs.append(DocumentSubmission.model_validate_json(line))
        per_pair[lang_pair] = docs  # type: ignore[index]
    return system, per_pair
