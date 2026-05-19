"""Composite LTB-100 score and per-document / per-submission aggregation."""

from __future__ import annotations

from datetime import datetime, timezone
from statistics import mean

from ltbench import LANG_PAIRS, LTB_WEIGHTS_V01
from ltbench.metrics.bootstrap import bootstrap_ci
from ltbench.metrics.language import chrf_with_lang_check
from ltbench.metrics.layout import bbox_iou, match_regions
from ltbench.metrics.reading_order import coverage_aware_tau
from ltbench.schemas import (
    Annotation,
    DocumentScore,
    DocumentSubmission,
    LangPair,
    LangPairScore,
    RegionScore,
    SubmissionResult,
    SystemManifest,
)


def ltb_100(chrf_score: float, layout_iou: float, reading_order_tau: float) -> float:
    """Combine the three primary metrics into the LTB-100 composite (v0.1).

    chrf_score is in [0, 100]; the other two are in [0, 1].
    """
    w = LTB_WEIGHTS_V01
    return 100.0 * (
        w["chrf"] * (chrf_score / 100.0)
        + w["layout_iou"] * layout_iou
        + w["reading_order_tau"] * reading_order_tau
    )


def _area(bbox: tuple[float, float, float, float]) -> float:
    return max(0.0, bbox[2]) * max(0.0, bbox[3])


def _is_parser_fallback(submission: DocumentSubmission) -> bool:
    """Detect the parser-fallback shape: a single region with empty text.

    Runners that can't parse their model's output return a 1-region empty
    placeholder so scoring still runs. This function identifies that shape so
    the scorer can flag the document for the --exclude-parser-failures path.
    """
    if len(submission.regions) != 1:
        return False
    only = submission.regions[0]
    return not only.text.strip()


def score_document(
    annotation: Annotation,
    submission: DocumentSubmission,
    lang_pair: LangPair,
) -> DocumentScore:
    """Score one document for one (system, language pair).

    Matches predicted regions to ground-truth regions (exact id then greedy IoU),
    computes per-region chrF + IoU (area-weighted), and a single Kendall-tau on
    matched regions' reading orders.
    """
    mapping = match_regions(annotation.regions, submission.regions)
    pred_by_id = {r.region_id: r for r in submission.regions}
    region_scores: list[RegionScore] = []

    total_area = sum(_area(r.bbox) for r in annotation.regions) or 1.0
    weighted_chrf = 0.0
    weighted_iou = 0.0
    matched_source_orders: list[int] = []
    matched_pred_orders: list[int] = []

    for gt_region in annotation.regions:
        pid = mapping.get(gt_region.region_id)
        ref_text = gt_region.references.get(lang_pair, "")
        weight = _area(gt_region.bbox) / total_area

        if pid is None:
            region_scores.append(
                RegionScore(
                    region_id=gt_region.region_id,
                    chrf=0.0,
                    layout_iou=0.0,
                    matched=False,
                )
            )
            continue

        pred_region = pred_by_id[pid]
        # v0.1.1: chrF is gated by language detection. Predictions in the wrong
        # language are scored 0 regardless of character overlap.
        rchrf = chrf_with_lang_check(pred_region.text, ref_text, lang_pair)
        riou = bbox_iou(gt_region.bbox, pred_region.bbox)
        region_scores.append(
            RegionScore(
                region_id=gt_region.region_id,
                chrf=rchrf,
                layout_iou=riou,
                matched=True,
            )
        )
        weighted_chrf += weight * rchrf
        weighted_iou += weight * riou
        matched_source_orders.append(gt_region.reading_order)
        matched_pred_orders.append(pred_region.reading_order)

    # v0.1.1: coverage-aware tau penalises partial-coverage predictions
    # (e.g. a model returning 1 region out of 7 no longer gets tau=1.0).
    tau = coverage_aware_tau(
        matched_source_orders, matched_pred_orders, n_gt_regions=len(annotation.regions)
    )

    return DocumentScore(
        doc_id=annotation.doc_id,
        lang_pair=lang_pair,
        chrf=weighted_chrf,
        layout_iou=weighted_iou,
        reading_order_tau=tau,
        ltb_100=ltb_100(weighted_chrf, weighted_iou, tau),
        region_scores=region_scores,
        parser_failure=_is_parser_fallback(submission),
    )


def aggregate_lang_pair(doc_scores: list[DocumentScore], lang_pair: LangPair) -> LangPairScore:
    pair_scores = [d for d in doc_scores if d.lang_pair == lang_pair]
    if not pair_scores:
        return LangPairScore(
            lang_pair=lang_pair,
            n_docs=0,
            chrf=0.0,
            layout_iou=0.0,
            reading_order_tau=0.0,
            ltb_100=0.0,
            ltb_100_ci_low=0.0,
            ltb_100_ci_high=0.0,
        )
    # v0.1.1: bootstrap CI on LTB-100 across the per-document scores in this pair.
    # On N=5 (the v0.1 sample size) this CI is wide — that is the point.
    _, ci_low, ci_high = bootstrap_ci([d.ltb_100 for d in pair_scores])
    return LangPairScore(
        lang_pair=lang_pair,
        n_docs=len(pair_scores),
        chrf=mean(d.chrf for d in pair_scores),
        layout_iou=mean(d.layout_iou for d in pair_scores),
        reading_order_tau=mean(d.reading_order_tau for d in pair_scores),
        ltb_100=mean(d.ltb_100 for d in pair_scores),
        ltb_100_ci_low=ci_low,
        ltb_100_ci_high=ci_high,
    )


def score_submission(
    system: SystemManifest,
    per_pair_data: dict[LangPair, list[tuple[Annotation, DocumentSubmission]]],
    exclude_parser_failures: bool = False,
) -> SubmissionResult:
    """Compose the full SubmissionResult from raw (annotation, submission) pairs.

    Args:
        system: metadata about the submitting system.
        per_pair_data: mapping from language pair to list of (annotation, submission) tuples.
        exclude_parser_failures: when True, documents whose submission triggered
            the runner's parser-fallback (1-region empty placeholder) are dropped
            from per-pair and overall aggregation. Per-document scores still
            include them with parser_failure=True so the count remains visible.
    """
    per_doc: list[DocumentScore] = []
    for lang_pair, items in per_pair_data.items():
        for annotation, submission in items:
            per_doc.append(score_document(annotation, submission, lang_pair))

    if exclude_parser_failures:
        scoring_pool = [d for d in per_doc if not d.parser_failure]
    else:
        scoring_pool = per_doc

    per_lang_pair = [aggregate_lang_pair(scoring_pool, lp) for lp in LANG_PAIRS]
    # Overall = mean across language pairs that have at least one doc scored
    populated = [lps for lps in per_lang_pair if lps.n_docs > 0]
    if populated:
        overall_chrf = mean(lps.chrf for lps in populated)
        overall_iou = mean(lps.layout_iou for lps in populated)
        overall_tau = mean(lps.reading_order_tau for lps in populated)
        overall_ltb = mean(lps.ltb_100 for lps in populated)
        # v0.1.1: overall CI = bootstrap on per-document LTB-100 across ALL
        # covered pairs (not the mean of per-pair CIs — that would understate
        # variance).
        _, overall_ci_low, overall_ci_high = bootstrap_ci([d.ltb_100 for d in scoring_pool])
    else:
        overall_chrf = overall_iou = overall_tau = overall_ltb = 0.0
        overall_ci_low = overall_ci_high = 0.0

    return SubmissionResult(
        system=system,
        weights=dict(LTB_WEIGHTS_V01),
        overall_ltb_100=overall_ltb,
        overall_ltb_100_ci_low=overall_ci_low,
        overall_ltb_100_ci_high=overall_ci_high,
        overall_chrf=overall_chrf,
        overall_layout_iou=overall_iou,
        overall_reading_order_tau=overall_tau,
        per_lang_pair=per_lang_pair,
        per_doc=per_doc,
        scored_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )
