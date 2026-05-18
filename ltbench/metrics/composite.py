"""Composite LTB-100 score and per-document / per-submission aggregation."""

from __future__ import annotations

from datetime import datetime, timezone
from statistics import mean

from ltbench import LANG_PAIRS, LTB_WEIGHTS_V01
from ltbench.metrics.layout import bbox_iou, match_regions
from ltbench.metrics.reading_order import normalized_kendall_tau
from ltbench.metrics.text import chrf
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
        rchrf = chrf(pred_region.text, ref_text)
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

    if len(matched_source_orders) >= 2:
        tau = normalized_kendall_tau(matched_source_orders, matched_pred_orders)
    else:
        # 1 matched region: order is trivially preserved; 0 matched: full penalty
        tau = 1.0 if matched_source_orders else 0.0

    return DocumentScore(
        doc_id=annotation.doc_id,
        lang_pair=lang_pair,
        chrf=weighted_chrf,
        layout_iou=weighted_iou,
        reading_order_tau=tau,
        ltb_100=ltb_100(weighted_chrf, weighted_iou, tau),
        region_scores=region_scores,
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
        )
    return LangPairScore(
        lang_pair=lang_pair,
        n_docs=len(pair_scores),
        chrf=mean(d.chrf for d in pair_scores),
        layout_iou=mean(d.layout_iou for d in pair_scores),
        reading_order_tau=mean(d.reading_order_tau for d in pair_scores),
        ltb_100=mean(d.ltb_100 for d in pair_scores),
    )


def score_submission(
    system: SystemManifest,
    per_pair_data: dict[LangPair, list[tuple[Annotation, DocumentSubmission]]],
) -> SubmissionResult:
    """Compose the full SubmissionResult from raw (annotation, submission) pairs.

    Args:
        system: metadata about the submitting system.
        per_pair_data: mapping from language pair to list of (annotation, submission) tuples.
    """
    per_doc: list[DocumentScore] = []
    for lang_pair, items in per_pair_data.items():
        for annotation, submission in items:
            per_doc.append(score_document(annotation, submission, lang_pair))

    per_lang_pair = [aggregate_lang_pair(per_doc, lp) for lp in LANG_PAIRS]
    # Overall = mean across language pairs that have at least one doc scored
    populated = [lps for lps in per_lang_pair if lps.n_docs > 0]
    if populated:
        overall_chrf = mean(lps.chrf for lps in populated)
        overall_iou = mean(lps.layout_iou for lps in populated)
        overall_tau = mean(lps.reading_order_tau for lps in populated)
        overall_ltb = mean(lps.ltb_100 for lps in populated)
    else:
        overall_chrf = overall_iou = overall_tau = overall_ltb = 0.0

    return SubmissionResult(
        system=system,
        weights=dict(LTB_WEIGHTS_V01),
        overall_ltb_100=overall_ltb,
        overall_chrf=overall_chrf,
        overall_layout_iou=overall_iou,
        overall_reading_order_tau=overall_tau,
        per_lang_pair=per_lang_pair,
        per_doc=per_doc,
        scored_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )
