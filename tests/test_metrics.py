"""Tests for ltbench metric implementations."""

from __future__ import annotations

import pytest

from ltbench.metrics.composite import ltb_100
from ltbench.metrics.layout import bbox_iou, match_regions
from ltbench.metrics.reading_order import normalized_kendall_tau
from ltbench.metrics.text import chrf
from ltbench.schemas import PredictedRegion, Region, StyleHint


# ---------- chrF ----------


def test_chrf_identical_is_100():
    assert chrf("hello world", "hello world") == 100.0


def test_chrf_empty_pair():
    assert chrf("", "") == 100.0


def test_chrf_disjoint_low():
    # Pure-Latin vs pure-CJK: chrF should be 0 (no character overlap)
    assert chrf("abc", "中文") == 0.0


def test_chrf_partial_overlap():
    s = chrf("the quick brown fox", "the quick red fox")
    assert 50.0 < s < 100.0


def test_chrf_in_range():
    s = chrf("translated text", "different translation")
    assert 0.0 <= s <= 100.0


# ---------- bbox_iou ----------


def test_iou_identical_is_one():
    assert bbox_iou((10, 10, 100, 50), (10, 10, 100, 50)) == 1.0


def test_iou_disjoint_is_zero():
    assert bbox_iou((0, 0, 10, 10), (100, 100, 10, 10)) == 0.0


def test_iou_partial_overlap():
    # Two 10x10 boxes overlapping in a 5x10 region: inter=50, union=150 -> 1/3
    iou = bbox_iou((0, 0, 10, 10), (5, 0, 10, 10))
    assert abs(iou - 1 / 3) < 1e-9


def test_iou_contained():
    # 10x10 inside 20x20: inter=100, union=400 -> 0.25
    iou = bbox_iou((5, 5, 10, 10), (0, 0, 20, 20))
    assert abs(iou - 0.25) < 1e-9


# ---------- reading order ----------


def test_tau_perfect_order():
    assert normalized_kendall_tau([0, 1, 2, 3], [0, 1, 2, 3]) == 1.0


def test_tau_reversed():
    assert normalized_kendall_tau([0, 1, 2, 3], [3, 2, 1, 0]) == 0.0


def test_tau_single_element():
    assert normalized_kendall_tau([0], [0]) == 1.0


def test_tau_one_swap():
    # Swap last two: 5 concordant, 1 discordant out of 6 → tau = 4/6, normalized = 5/6
    score = normalized_kendall_tau([0, 1, 2, 3], [0, 1, 3, 2])
    assert 0.5 < score < 1.0


# ---------- composite ----------


def test_ltb100_perfect():
    assert ltb_100(100.0, 1.0, 1.0) == 100.0


def test_ltb100_zero():
    assert ltb_100(0.0, 0.0, 0.0) == 0.0


def test_ltb100_layout_only():
    # All layout, no text: 30 + 20 = 50
    assert ltb_100(0.0, 1.0, 1.0) == 50.0


def test_ltb100_text_only():
    # All text, no layout: 50
    assert ltb_100(100.0, 0.0, 0.0) == 50.0


# ---------- region matching ----------


def _mk_region(rid: str, bbox, ref_text: str = "x"):
    return Region(
        region_id=rid,
        bbox=bbox,
        text="src",
        reading_order=0,
        style=StyleHint(),
        references={
            "en-es": ref_text,
            "en-de": ref_text,
            "en-zh": ref_text,
            "en-ar": ref_text,
            "en-ja": ref_text,
        },
    )


def _mk_pred(rid: str, bbox, text: str = "x"):
    return PredictedRegion(region_id=rid, bbox=bbox, text=text, reading_order=0)


def test_match_exact_id():
    gt = [_mk_region("r1", (0, 0, 100, 100)), _mk_region("r2", (0, 200, 100, 100))]
    pr = [_mk_pred("r1", (10, 10, 100, 100)), _mk_pred("r2", (5, 200, 100, 100))]
    m = match_regions(gt, pr)
    assert m == {"r1": "r1", "r2": "r2"}


def test_match_greedy_iou():
    # Predictions have different ids but overlap ground truth
    gt = [_mk_region("g1", (0, 0, 100, 100))]
    pr = [_mk_pred("p_xyz", (10, 10, 100, 100))]
    m = match_regions(gt, pr)
    assert m == {"g1": "p_xyz"}


def test_match_unmatched_below_threshold():
    gt = [_mk_region("g1", (0, 0, 100, 100))]
    pr = [_mk_pred("p_xyz", (500, 500, 100, 100))]  # disjoint
    m = match_regions(gt, pr)
    assert m == {"g1": None}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
