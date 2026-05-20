"""End-to-end leaderboard refresh on the v0.1.5 dataset (N=35).

Scores all 4 known systems against the current manifest:
  - identity-baseline       (N=35 — submissions refreshed)
  - nllb-text-oracle        (N=35 — submissions refreshed)
  - qwen3-vl-2b-instruct    (N=5  — old submissions, kept for comparability)
  - deepl-text-oracle       (N=5  — old submissions, no API key to refresh)

Each system gets scored twice:
  1. With chrF (default text metric)        -> results/<system>.json
  2. With COMET-Kiwi-22 (where supported)   -> results/<system>.comet.json

After all scoring, rebuilds the static leaderboard.

Run with the COMET-enabled venv:
  .comet-env/Scripts/python.exe scripts/refresh_leaderboard_v015.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SYSTEMS = [
    "identity-baseline",
    "nllb-text-oracle",
    "qwen3-vl-2b-instruct",
    "deepl-text-oracle",
]


def run(cmd: list[str]) -> int:
    print(f"$ {' '.join(cmd)}")
    proc = subprocess.run(cmd, check=False)
    return proc.returncode


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    print(f"Repo root: {repo_root}")
    py = sys.executable
    failures: list[str] = []

    for system in SYSTEMS:
        submission_dir = repo_root / "submissions" / system
        if not submission_dir.exists():
            print(f"  skip {system}: no submissions/")
            continue

        # chrF scoring (always works)
        out_chrf = repo_root / "results" / f"{system}.json"
        rc = run(
            [
                py,
                "-m",
                "ltbench.cli",
                "score",
                "--submission",
                str(submission_dir),
                "--output",
                str(out_chrf),
            ]
        )
        if rc != 0:
            failures.append(f"chrF {system}")

        # COMET-Kiwi scoring (heavier; requires comet)
        out_comet = repo_root / "results" / f"{system}.comet.json"
        rc = run(
            [
                py,
                "-m",
                "ltbench.cli",
                "score",
                "--submission",
                str(submission_dir),
                "--output",
                str(out_comet),
                "--text-metric",
                "comet-kiwi",
            ]
        )
        if rc != 0:
            failures.append(f"comet {system}")

    # Rebuild leaderboard from results/ - prefer COMET if both exist
    # (the leaderboard build code picks the appropriate result file)
    print("\nRebuilding leaderboard...")
    rc = run([py, "-m", "ltbench.cli", "leaderboard"])
    if rc != 0:
        failures.append("leaderboard")

    if failures:
        print(f"\nFAILURES: {failures}")
        return 1
    print("\nDone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
