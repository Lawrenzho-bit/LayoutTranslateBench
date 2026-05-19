"""Single-document smoke test for the Florence-2 + NLLB-200 pipeline.

Loads both models, runs on (doc_001, en-es), and prints timings + first
extracted/translated regions. Used to validate the pipeline works end-to-end
before kicking off the full 8-pair benchmark run.

Run from repo root:
    python scripts/smoke_florence_nllb.py
"""

from __future__ import annotations

import time
from pathlib import Path

from ltbench.dataset import load_annotation, load_manifest
from ltbench.runners.florence_nllb import FlorenceNllbRunner


def main() -> int:
    print("== LayoutTranslateBench Florence-2 + NLLB-200 smoke test ==", flush=True)
    runner = FlorenceNllbRunner(data_root=Path("data"))
    print(f"Models: {runner.florence_model} + {runner.nllb_model}", flush=True)

    t0 = time.time()
    runner._ensure_loaded()
    print(f"Loaded in {time.time() - t0:.1f}s on {runner._actual_device}.", flush=True)

    manifest = load_manifest(Path("data/manifest.json"))
    entry = manifest.entries[0]
    annotation = load_annotation(Path("data") / entry.annotation_file)
    print(
        f"Pipeline on {entry.doc_id} ({entry.category}) -> en-es ...",
        flush=True,
    )

    t0 = time.time()
    submission = runner.translate(annotation, "en-es")
    t_infer = time.time() - t0
    print(
        f"Inference took {t_infer:.1f}s; got {len(submission.regions)} regions.",
        flush=True,
    )

    print("\nFirst 4 predicted regions:", flush=True)
    for r in submission.regions[:4]:
        bbox_str = f"({r.bbox[0]:.0f},{r.bbox[1]:.0f},{r.bbox[2]:.0f},{r.bbox[3]:.0f})"
        print(f"  {r.region_id} bbox={bbox_str} text={r.text[:60]!r}", flush=True)

    print(
        f"\nEstimated full 8-pair x 5-doc run: {t_infer * 40:.0f}s "
        f"= {t_infer * 40 / 60:.1f} min.",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
