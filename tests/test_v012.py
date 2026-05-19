"""Tests for v0.1.2 features:
  - --exclude-parser-failures flag on ltbench score
  - Parser-fallback detection on submission shape
  - Human-evaluation infrastructure (schema + correlation)
"""

from __future__ import annotations

from ltbench.human_eval import (
    HumanJudgment,
    aggregate_per_cell,
    kendall_tau_human_vs_auto,
)
from ltbench.metrics.composite import _is_parser_fallback
from ltbench.schemas import DocumentSubmission, PredictedRegion


def test_parser_fallback_detected_on_single_empty_region():
    sub = DocumentSubmission(
        doc_id="doc_001",
        regions=[
            PredictedRegion(region_id="r0", bbox=(0.0, 0.0, 1.0, 1.0), text="", reading_order=0)
        ],
    )
    assert _is_parser_fallback(sub) is True


def test_parser_fallback_not_detected_on_single_nonempty_region():
    sub = DocumentSubmission(
        doc_id="doc_001",
        regions=[
            PredictedRegion(
                region_id="r0", bbox=(0.0, 0.0, 100.0, 50.0), text="real text", reading_order=0
            )
        ],
    )
    assert _is_parser_fallback(sub) is False


def test_parser_fallback_not_detected_on_multiple_regions():
    sub = DocumentSubmission(
        doc_id="doc_001",
        regions=[
            PredictedRegion(region_id="r0", bbox=(0.0, 0.0, 100.0, 50.0), text="x", reading_order=0),
            PredictedRegion(region_id="r1", bbox=(0.0, 50.0, 100.0, 50.0), text="y", reading_order=1),
        ],
    )
    assert _is_parser_fallback(sub) is False


# ---------- Human-evaluation infrastructure ----------


def _make_judgment(system: str, doc: str, lang_pair: str, region: str | None, da: float) -> HumanJudgment:
    return HumanJudgment(
        judgment_id=f"{system}-{doc}-{region}-{lang_pair}",
        rater_id="test-rater",
        system_name=system,
        doc_id=doc,
        lang_pair=lang_pair,  # type: ignore[arg-type]
        region_id=region,
        da_score=da,
        timestamp="2026-05-19T12:00:00Z",
    )


def test_aggregate_per_cell_averages_raters():
    judgments = [
        _make_judgment("sys-a", "doc_001", "en-es", "r0", 80.0),
        _make_judgment("sys-a", "doc_001", "en-es", "r0", 70.0),
        _make_judgment("sys-a", "doc_001", "en-es", "r1", 90.0),
    ]
    agg = aggregate_per_cell(judgments)
    assert agg[("sys-a", "doc_001", "en-es", "r0")] == 75.0
    assert agg[("sys-a", "doc_001", "en-es", "r1")] == 90.0


def test_aggregate_per_cell_doc_level():
    judgments = [
        _make_judgment("sys-a", "doc_001", "en-es", None, 85.0),
    ]
    agg = aggregate_per_cell(judgments)
    assert agg[("sys-a", "doc_001", "en-es", "doc")] == 85.0


def test_correlation_perfect_agreement():
    human = {
        ("sys-a", "doc_001", "en-es", "doc"): 90.0,
        ("sys-a", "doc_002", "en-es", "doc"): 70.0,
        ("sys-a", "doc_003", "en-es", "doc"): 50.0,
    }
    auto = {
        ("sys-a", "doc_001", "en-es", "doc"): 80.0,
        ("sys-a", "doc_002", "en-es", "doc"): 60.0,
        ("sys-a", "doc_003", "en-es", "doc"): 40.0,
    }
    corr = kendall_tau_human_vs_auto(human, auto)
    assert corr["n_pairs"] == 3
    assert corr["kendall_tau_norm"] == 1.0  # perfect rank agreement
    assert corr["pearson_r"] > 0.99  # perfect linear


def test_correlation_no_overlap():
    human = {("sys-a", "doc_001", "en-es", "doc"): 90.0}
    auto = {("sys-b", "doc_002", "en-es", "doc"): 80.0}  # different system + doc
    corr = kendall_tau_human_vs_auto(human, auto)
    assert corr["n_pairs"] == 0
    assert corr["kendall_tau_norm"] == 0.0


def test_correlation_anti_agreement():
    # Reversed rank ordering — tau should be 0 (normalised from -1)
    human = {
        ("sys", "doc_001", "en-es", "doc"): 90.0,
        ("sys", "doc_002", "en-es", "doc"): 80.0,
        ("sys", "doc_003", "en-es", "doc"): 70.0,
    }
    auto = {
        ("sys", "doc_001", "en-es", "doc"): 10.0,
        ("sys", "doc_002", "en-es", "doc"): 20.0,
        ("sys", "doc_003", "en-es", "doc"): 30.0,
    }
    corr = kendall_tau_human_vs_auto(human, auto)
    assert corr["kendall_tau_norm"] == 0.0  # perfectly reversed
    assert corr["pearson_r"] < -0.99
