"""Rebuild the static leaderboard from result JSON files."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from ltbench import LANG_PAIRS, __version__
from ltbench.schemas import LeaderboardRow, SubmissionResult

_TEMPLATE_DIR = Path(__file__).parent / "templates"


def _load_results(results_dir: Path) -> list[SubmissionResult]:
    results: list[SubmissionResult] = []
    for path in sorted(results_dir.glob("*.json")):
        if path.name.endswith(".local.json"):
            continue
        try:
            with path.open("r", encoding="utf-8") as f:
                results.append(SubmissionResult.model_validate(json.load(f)))
        except Exception as e:
            print(f"[warn] could not load {path}: {e}")
    return results


def _rank(results: list[SubmissionResult]) -> list[LeaderboardRow]:
    sorted_results = sorted(results, key=lambda r: r.overall_ltb_100, reverse=True)
    total_pairs = len(LANG_PAIRS)
    rows: list[LeaderboardRow] = []
    for i, r in enumerate(sorted_results, start=1):
        # Coverage = number of language pairs with at least one scored document
        covered = sum(1 for p in r.per_lang_pair if p.n_docs > 0)
        coverage = f"{covered}/{total_pairs}"
        rows.append(
            LeaderboardRow(
                rank=i,
                system_name=r.system.system_name,
                system_version=r.system.system_version,
                ltb_100=r.overall_ltb_100,
                ltb_100_ci_low=r.overall_ltb_100_ci_low,
                ltb_100_ci_high=r.overall_ltb_100_ci_high,
                chrf=r.overall_chrf,
                layout_iou=r.overall_layout_iou,
                reading_order_tau=r.overall_reading_order_tau,
                median_runtime_s=r.system.median_per_doc_runtime_seconds,
                cost_usd=r.system.cost_usd,
                hardware=r.system.hardware,
                submitter=r.system.submitter,
                verified=False,
                coverage=coverage,
                system_type=r.system.system_type,
                parser_failures=r.system.parser_failures,
            )
        )
    return rows


def _split_by_type(rows: list[LeaderboardRow]) -> tuple[list[LeaderboardRow], list[LeaderboardRow]]:
    """Separate end-to-end systems from oracle-layout (upper bound) systems.

    v0.1.1: the leaderboard previously mixed both, which misleadingly presented
    oracle-layout text-quality ceilings as if they were realistic end-to-end
    measurements. Oracle systems are kept on the leaderboard but in a separate
    'reference / ceiling' table.
    """
    end_to_end = [r for r in rows if r.system_type == "end-to-end"]
    oracle = [r for r in rows if r.system_type == "oracle-layout"]
    # Re-rank within each group
    for new_rank, row in enumerate(end_to_end, start=1):
        row.rank = new_rank
    for new_rank, row in enumerate(oracle, start=1):
        row.rank = new_rank
    return end_to_end, oracle


def _format_row_row(r: LeaderboardRow) -> str:
    runtime = f"{r.median_runtime_s:.2f}" if r.median_runtime_s is not None else "—"
    cost = f"${r.cost_usd:.4f}" if r.cost_usd is not None else "—"
    if r.ltb_100_ci_low or r.ltb_100_ci_high:
        ltb_str = f"{r.ltb_100:.2f} [{r.ltb_100_ci_low:.1f}, {r.ltb_100_ci_high:.1f}]"
    else:
        ltb_str = f"{r.ltb_100:.2f}"
    return (
        f"| {r.rank} | {r.system_name} v{r.system_version} | {ltb_str} | "
        f"{r.chrf:.2f} | {r.layout_iou:.4f} | {r.reading_order_tau:.4f} | "
        f"{r.coverage} | {runtime} | {cost} | {r.hardware or '—'} |"
    )


def _render_markdown(rows: list[LeaderboardRow], generated_at: str) -> str:
    end_to_end, oracle = _split_by_type(rows)
    n_caveat = (
        "**Caveat — v0.1 sample size.** All scores are computed on N=5 documents per "
        "language pair. Reported LTB-100 cell shows `point [95% CI low, CI high]` "
        "via 1000-resample percentile bootstrap. The CI on N=5 is *wide* — small "
        "differences between systems are not statistically significant. v0.2 will "
        "scale the dataset to N≥25 per pair."
    )
    lines = [
        "# LayoutTranslateBench Leaderboard",
        "",
        f"_Generated {generated_at} from LayoutTranslateBench v{__version__}._",
        "",
        n_caveat,
        "",
        "## End-to-end systems",
        "",
        "*These runners produce their own bounding boxes. This is the realistic real-world score.*",
        "",
        "| Rank | System | LTB-100 [95% CI] | chrF | Layout IoU | Reading-order τ | Coverage | Median runtime (s/doc) | Cost (USD) | Hardware |",
        "|---:|:---|:---|---:|---:|---:|:---:|---:|---:|:---|",
    ]
    if not end_to_end:
        lines.append("| — | _no end-to-end submissions yet_ | — | — | — | — | — | — | — | — |")
    for r in end_to_end:
        lines.append(_format_row_row(r))

    lines += [
        "",
        "## Oracle-layout reference (text-quality ceilings)",
        "",
        "*These runners are given **ground-truth bounding boxes** as predictions and only "
        "translate the text. They are upper bounds on text-quality, **not** realistic "
        "end-to-end measurements of the underlying products. Use for comparing translation "
        "quality in isolation from layout-extraction quality.*",
        "",
        "| Rank | System | LTB-100 [95% CI] | chrF | Layout IoU | Reading-order τ | Coverage | Median runtime (s/doc) | Cost (USD) | Hardware |",
        "|---:|:---|:---|---:|---:|---:|:---:|---:|---:|:---|",
    ]
    if not oracle:
        lines.append("| — | _no oracle-layout submissions yet_ | — | — | — | — | — | — | — | — |")
    for r in oracle:
        lines.append(_format_row_row(r))

    lines += [
        "",
        "See [BENCHMARK.md](BENCHMARK.md) for the spec and [docs/submission.md](docs/submission.md) to submit.",
        "",
    ]
    return "\n".join(lines)


def build_leaderboard(
    results_dir: Path,
    output_dir: Path,
    leaderboard_md: Path | None = None,
) -> int:
    """Build leaderboard HTML + (optional) Markdown mirror. Returns row count."""
    results = _load_results(results_dir)
    rows = _rank(results)
    end_to_end, oracle = _split_by_type(rows)
    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    output_dir.mkdir(parents=True, exist_ok=True)
    env = Environment(
        loader=FileSystemLoader(_TEMPLATE_DIR),
        autoescape=select_autoescape(["html"]),
    )
    template = env.get_template("index.html.j2")
    html = template.render(
        rows=rows,
        end_to_end=end_to_end,
        oracle=oracle,
        generated_at=generated_at,
        version=__version__,
    )
    (output_dir / "index.html").write_text(html, encoding="utf-8")

    if leaderboard_md is not None:
        leaderboard_md.write_text(_render_markdown(rows, generated_at), encoding="utf-8")

    return len(rows)
