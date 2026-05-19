"""Single-document smoke test for the Qwen-VL runner.

Loads the default model and runs one (doc_001, en-es) inference, printing
timings so we can estimate the cost of the full 25-call run before kicking it
off.

Run from repo root:
    python scripts/smoke_qwen_vl.py
"""

from __future__ import annotations

import time
from pathlib import Path

from ltbench.dataset import load_annotation, load_manifest
from ltbench.runners.qwen_vl import QwenVLRunner


def main() -> int:
    print("== LayoutTranslateBench Qwen-VL smoke test ==", flush=True)
    t_start = time.time()

    runner = QwenVLRunner(data_root=Path("data"))
    print(f"Model: {runner.model_id}", flush=True)

    t0 = time.time()
    runner._ensure_loaded()
    t_load = time.time() - t0
    print(f"Model loaded in {t_load:.1f}s on {runner._actual_device}.", flush=True)

    manifest = load_manifest(Path("data/manifest.json"))
    entry = manifest.entries[0]
    annotation = load_annotation(Path("data") / entry.annotation_file)
    print(
        f"Inference on {entry.doc_id} ({entry.category}, "
        f"{len(annotation.regions)} regions) -> en-es ...",
        flush=True,
    )

    t0 = time.time()
    submission = runner.translate(annotation, "en-es")
    t_infer = time.time() - t0
    print(f"Inference took {t_infer:.1f}s; got {len(submission.regions)} regions.", flush=True)

    print("\nFirst 3 predicted regions:", flush=True)
    for r in submission.regions[:3]:
        print(f"  region_id={r.region_id} bbox={r.bbox} text={r.text[:60]!r}", flush=True)

    total = time.time() - t_start
    print(
        f"\nTotal smoke time: {total:.1f}s. "
        f"Estimated full run (model already loaded): {t_infer * 25:.0f}s "
        f"= {t_infer * 25 / 60:.1f} min.",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
