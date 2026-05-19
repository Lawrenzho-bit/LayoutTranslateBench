"""Tests for the leaderboard builder — particularly the Coverage column."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ltbench import LANG_PAIRS
from ltbench.leaderboard.build import _rank, build_leaderboard
from ltbench.schemas import (
    DocumentScore,
    LangPairScore,
    SubmissionResult,
    SystemManifest,
)


def _make_result(
    name: str,
    overall_ltb: float = 60.0,
    covered_pairs: tuple[str, ...] = ("en-es",),
) -> SubmissionResult:
    """Build a minimal SubmissionResult with n_docs > 0 only on covered_pairs."""
    per_pair: list[LangPairScore] = []
    for lp in LANG_PAIRS:
        per_pair.append(
            LangPairScore(
                lang_pair=lp,
                n_docs=5 if lp in covered_pairs else 0,
                chrf=50.0 if lp in covered_pairs else 0.0,
                layout_iou=1.0 if lp in covered_pairs else 0.0,
                reading_order_tau=1.0 if lp in covered_pairs else 0.0,
                ltb_100=overall_ltb if lp in covered_pairs else 0.0,
            )
        )
    return SubmissionResult(
        system=SystemManifest(system_name=name, system_version="0.1.0"),
        weights={"chrf": 0.5, "layout_iou": 0.3, "reading_order_tau": 0.2},
        overall_ltb_100=overall_ltb,
        overall_chrf=50.0,
        overall_layout_iou=1.0,
        overall_reading_order_tau=1.0,
        per_lang_pair=per_pair,
        per_doc=[],
        scored_at="2026-05-19T00:00:00+00:00",
    )


def test_coverage_full():
    """A system covering all language pairs should display total/total."""
    result = _make_result("full-cov-system", overall_ltb=70.0, covered_pairs=LANG_PAIRS)
    rows = _rank([result])
    assert rows[0].coverage == f"{len(LANG_PAIRS)}/{len(LANG_PAIRS)}"


def test_coverage_partial():
    """A system covering 1 of 8 pairs should display 1/8."""
    result = _make_result("partial-cov", overall_ltb=20.0, covered_pairs=("en-es",))
    rows = _rank([result])
    assert rows[0].coverage == f"1/{len(LANG_PAIRS)}"


def test_coverage_six_of_eight():
    """A system like deepl-text-oracle covering 6 of 8 pairs."""
    six = ("en-es", "en-de", "en-zh", "en-ar", "en-ja", "en-fr")
    result = _make_result("deepl-like", overall_ltb=84.0, covered_pairs=six)
    rows = _rank([result])
    assert rows[0].coverage == f"6/{len(LANG_PAIRS)}"


def test_ranking_by_ltb_100():
    """Rows must be ordered by overall_ltb_100 desc, regardless of coverage."""
    r_high_partial = _make_result(
        "high-partial", overall_ltb=80.0, covered_pairs=("en-es",)
    )
    r_low_full = _make_result(
        "low-full", overall_ltb=50.0, covered_pairs=LANG_PAIRS
    )
    rows = _rank([r_low_full, r_high_partial])  # deliberately out of order
    assert rows[0].system_name == "high-partial"
    assert rows[0].rank == 1
    assert rows[1].system_name == "low-full"
    assert rows[1].rank == 2


def test_build_leaderboard_html_contains_coverage(tmp_path: Path):
    """End-to-end: result JSON -> rebuilt HTML -> 'Coverage' header visible."""
    results_dir = tmp_path / "results"
    results_dir.mkdir()
    output_dir = tmp_path / "leaderboard"

    result = _make_result("end-to-end", overall_ltb=75.0, covered_pairs=("en-es", "en-de"))
    (results_dir / "end-to-end.json").write_text(
        json.dumps(result.model_dump()), encoding="utf-8"
    )

    md_path = tmp_path / "LEADERBOARD.md"
    n = build_leaderboard(results_dir, output_dir, md_path)
    assert n == 1

    html = (output_dir / "index.html").read_text(encoding="utf-8")
    assert "Coverage" in html
    assert "2/8" in html  # this system covers 2 pairs out of 8

    md = md_path.read_text(encoding="utf-8")
    assert "Coverage" in md
    assert "2/8" in md


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
