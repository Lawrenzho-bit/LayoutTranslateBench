"""Layout fidelity: axis-aligned bounding-box IoU and greedy region matching."""

from __future__ import annotations

from ltbench.schemas import BBox, PredictedRegion, Region


def bbox_iou(a: BBox, b: BBox) -> float:
    """Intersection-over-Union for two axis-aligned bboxes (x, y, w, h)."""
    ax1, ay1, aw, ah = a
    bx1, by1, bw, bh = b
    ax2, ay2 = ax1 + aw, ay1 + ah
    bx2, by2 = bx1 + bw, by1 + bh

    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0:
        return 0.0

    union = aw * ah + bw * bh - inter
    if union <= 0:
        return 0.0
    return inter / union


def match_regions(
    gt: list[Region],
    pred: list[PredictedRegion],
    min_iou: float = 0.1,
) -> dict[str, str | None]:
    """Match predicted regions to ground-truth regions.

    Strategy:
        1. Exact region_id match, honored only when the boxes also overlap
           (IoU >= min_iou).
        2. Greedy match remaining by max IoU, threshold `min_iou`.

    Returns a dict mapping ground-truth region_id -> predicted region_id (or None).
    """
    gt_by_id = {r.region_id: r for r in gt}
    pred_by_id = {r.region_id: r for r in pred}

    matched_gt: set[str] = set()
    matched_pred: set[str] = set()
    mapping: dict[str, str | None] = {gid: None for gid in gt_by_id}

    # Phase 1: exact region_id match, honored only when the boxes also overlap.
    # Oracle runners copy GT region_ids *and* GT boxes, so this IoU check passes
    # trivially (IoU = 1.0). End-to-end runners may emit ids that coincidentally
    # collide with the GT `r1, r2, ...` namespace; gating on IoU keeps the scorer
    # from honoring a spurious id match between non-overlapping regions and lets
    # those fall through to Phase 2 greedy IoU matching.
    for gid in list(gt_by_id):
        if gid in pred_by_id and bbox_iou(gt_by_id[gid].bbox, pred_by_id[gid].bbox) >= min_iou:
            mapping[gid] = gid
            matched_gt.add(gid)
            matched_pred.add(gid)

    # Phase 2: greedy IoU match for remaining
    remaining_gt = [g for g in gt if g.region_id not in matched_gt]
    remaining_pred = [p for p in pred if p.region_id not in matched_pred]

    pairs: list[tuple[float, str, str]] = []
    for g in remaining_gt:
        for p in remaining_pred:
            iou = bbox_iou(g.bbox, p.bbox)
            if iou >= min_iou:
                pairs.append((iou, g.region_id, p.region_id))

    pairs.sort(reverse=True, key=lambda t: t[0])
    for _, gid, pid in pairs:
        if gid in matched_gt or pid in matched_pred:
            continue
        mapping[gid] = pid
        matched_gt.add(gid)
        matched_pred.add(pid)

    return mapping
