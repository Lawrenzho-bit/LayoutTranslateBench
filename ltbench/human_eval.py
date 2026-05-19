"""Human-evaluation infrastructure for LayoutTranslateBench.

Address methodology critique #10 (No human evaluation, no inter-annotator
agreement). This module defines the schema and aggregation rules for human
Direct Assessment (DA) judgments and provides correlation against automatic
LTB-100 scores.

v0.1.2 ships the **infrastructure only** — no judgments are bundled in the
repo, because collecting them requires paid annotators or volunteers. The
intended workflow:

  1. Run `ltbench score` on systems of interest; produce result JSONs.
  2. Use `ltbench export-eval-prompts` (CLI command in cli.py) to export a
     CSV of (system, doc, region, source_text, predicted_text, reference)
     rows for raters to score 0–100 DA.
  3. Raters fill in `da_score` (and optional `notes`) per row.
  4. Import judgments back via `ltbench import-judgments`.
  5. Run `ltbench correlate` to compute Kendall τ and Pearson r between
     automatic LTB-100 and aggregated human DA.

Storage layout:
  data/human_judgments/{rater_id}/{system_name}-{lang_pair}.jsonl

Each line is one HumanJudgment (Pydantic model below).
"""

from __future__ import annotations

from pathlib import Path
from statistics import mean

from pydantic import BaseModel, Field

from ltbench.schemas import LangPair


class HumanJudgment(BaseModel):
    """One human Direct Assessment (DA) judgment of one (system, doc, region)
    prediction.

    DA scores follow WMT convention: 0–100 scale where:
      0–25  = nonsense / unrelated to source
      26–50 = some content preserved but with major errors
      51–75 = mostly correct, minor errors
      76–100 = excellent, indistinguishable from professional translation
    """

    judgment_id: str
    rater_id: str
    system_name: str
    doc_id: str
    lang_pair: LangPair
    region_id: str | None = None  # None = whole-document judgment
    da_score: float = Field(ge=0.0, le=100.0)
    notes: str | None = None
    timestamp: str  # ISO-8601


def load_judgments(judgments_dir: Path) -> list[HumanJudgment]:
    """Load every .jsonl under judgments_dir/* into a flat list."""
    judgments: list[HumanJudgment] = []
    if not judgments_dir.exists():
        return judgments
    for jsonl in judgments_dir.rglob("*.jsonl"):
        with jsonl.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                judgments.append(HumanJudgment.model_validate_json(line))
    return judgments


def aggregate_per_cell(judgments: list[HumanJudgment]) -> dict[tuple[str, str, str, str], float]:
    """Average DA scores across raters for each (system, doc, lang_pair, region) cell.

    Returns a mapping from (system_name, doc_id, lang_pair, region_id_or_"doc")
    to mean DA score. region_id is "doc" when the judgment was on the whole
    document (region_id field was None on the input).
    """
    bucketed: dict[tuple[str, str, str, str], list[float]] = {}
    for j in judgments:
        key = (j.system_name, j.doc_id, j.lang_pair, j.region_id or "doc")
        bucketed.setdefault(key, []).append(j.da_score)
    return {k: mean(v) for k, v in bucketed.items()}


def kendall_tau_human_vs_auto(
    human_aggregated: dict[tuple[str, str, str, str], float],
    automatic_scores: dict[tuple[str, str, str, str], float],
) -> dict[str, float | int]:
    """Compute correlation between human DA and automatic per-region scores.

    Args:
        human_aggregated: output of aggregate_per_cell()
        automatic_scores: per-region scores from result JSONs, keyed the same
            way (system_name, doc_id, lang_pair, region_id). For whole-document
            scores use region_id="doc".

    Returns:
        {
            "n_pairs": number of overlapping cells,
            "kendall_tau_norm": [0, 1],
            "pearson_r": [-1, 1],
            "human_mean": mean human DA,
            "auto_mean": mean automatic,
        }

    Returns n_pairs=0 with NaN-equivalent (0.0) correlations if there is no
    overlap between human and automatic cells.
    """
    from ltbench.metrics.reading_order import _kendall_tau_b  # type: ignore[attr-defined]

    common_keys = sorted(set(human_aggregated) & set(automatic_scores))
    if len(common_keys) < 2:
        return {
            "n_pairs": len(common_keys),
            "kendall_tau_norm": 0.0,
            "pearson_r": 0.0,
            "human_mean": 0.0,
            "auto_mean": 0.0,
        }

    h = [human_aggregated[k] for k in common_keys]
    a = [automatic_scores[k] for k in common_keys]

    # Convert to ranks for Kendall τ
    def _ranks(values: list[float]) -> list[int]:
        sorted_idx = sorted(range(len(values)), key=lambda i: values[i])
        ranks = [0] * len(values)
        for rank, idx in enumerate(sorted_idx):
            ranks[idx] = rank
        return ranks

    tau = _kendall_tau_b(_ranks(h), _ranks(a))
    tau_norm = (tau + 1.0) / 2.0

    # Pearson r
    n = len(h)
    mean_h = sum(h) / n
    mean_a = sum(a) / n
    cov = sum((h[i] - mean_h) * (a[i] - mean_a) for i in range(n))
    var_h = sum((h[i] - mean_h) ** 2 for i in range(n))
    var_a = sum((a[i] - mean_a) ** 2 for i in range(n))
    pearson = cov / ((var_h * var_a) ** 0.5) if var_h > 0 and var_a > 0 else 0.0

    return {
        "n_pairs": n,
        "kendall_tau_norm": tau_norm,
        "pearson_r": pearson,
        "human_mean": mean_h,
        "auto_mean": mean_a,
    }


def extract_automatic_doc_scores_from_result(result_json: dict) -> dict[tuple[str, str, str, str], float]:
    """Pull per-document LTB-100 scores from a result.json into the cell-mapping
    format that pairs with human DA judgments at whole-document granularity."""
    system_name = result_json["system"]["system_name"]
    out: dict[tuple[str, str, str, str], float] = {}
    for d in result_json["per_doc"]:
        key = (system_name, d["doc_id"], d["lang_pair"], "doc")
        out[key] = d["ltb_100"]
    return out
