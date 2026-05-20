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
    """Load all canonical *.json results. Snapshots go in results/snapshots/."""
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


def _load_results_split_by_metric(
    results_dir: Path,
) -> tuple[list[SubmissionResult], list[SubmissionResult]]:
    """Return (chrF results, COMET-Kiwi results) using filename convention.

    Convention: <system>.json is the chrF scoring; <system>.comet.json is the
    COMET-Kiwi scoring. Snapshots in results/snapshots/ are ignored.
    """
    chrf_results: list[SubmissionResult] = []
    comet_results: list[SubmissionResult] = []
    for path in sorted(results_dir.glob("*.json")):
        if path.name.endswith(".local.json"):
            continue
        try:
            with path.open("r", encoding="utf-8") as f:
                result = SubmissionResult.model_validate(json.load(f))
        except Exception as e:
            print(f"[warn] could not load {path}: {e}")
            continue
        if path.name.endswith(".comet.json"):
            comet_results.append(result)
        else:
            chrf_results.append(result)
    return chrf_results, comet_results


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


def _render_section(
    rows: list[LeaderboardRow],
    *,
    metric_label: str,
    metric_col_header: str,
) -> list[str]:
    """Render the two-tier table (end-to-end + oracle-layout) for a single metric."""
    end_to_end, oracle = _split_by_type(rows)
    lines: list[str] = [
        f"## End-to-end systems ({metric_label})",
        "",
        "*These runners produce their own bounding boxes. This is the realistic real-world score.*",
        "",
        f"| Rank | System | LTB-100 [95% CI] | {metric_col_header} | Layout IoU | Reading-order τ | Coverage | Median runtime (s/doc) | Cost (USD) | Hardware |",
        "|---:|:---|:---|---:|---:|---:|:---:|---:|---:|:---|",
    ]
    if not end_to_end:
        lines.append("| — | _no end-to-end submissions yet_ | — | — | — | — | — | — | — | — |")
    for r in end_to_end:
        lines.append(_format_row_row(r))

    lines += [
        "",
        f"## Oracle-layout reference ({metric_label})",
        "",
        "*Given **ground-truth bounding boxes** as predictions; only the text is translated. "
        "These are upper bounds on text-quality, **not** realistic end-to-end measurements.*",
        "",
        f"| Rank | System | LTB-100 [95% CI] | {metric_col_header} | Layout IoU | Reading-order τ | Coverage | Median runtime (s/doc) | Cost (USD) | Hardware |",
        "|---:|:---|:---|---:|---:|---:|:---:|---:|---:|:---|",
    ]
    if not oracle:
        lines.append("| — | _no oracle-layout submissions yet_ | — | — | — | — | — | — | — | — |")
    for r in oracle:
        lines.append(_format_row_row(r))

    return lines


def _render_markdown(
    chrf_rows: list[LeaderboardRow],
    comet_rows: list[LeaderboardRow],
    generated_at: str,
) -> str:
    n_caveat = (
        "**Sample size — v0.1.5.** Per-pair counts: N=20 for en-es/en-de/en-ar/en-fr/en-th/en-ms "
        "(10 author-curated + 10 FLORES-200), N=28 for en-ja (+8 rileykim), N=27 for en-zh "
        "(+7 rileykim). LTB-100 cell shows `point [95% CI low, CI high]` via 1000-resample "
        "percentile bootstrap. CIs at N=20 are roughly √2× tighter than v0.1.3's N=10."
    )
    metric_caveat = (
        "**Metric.** Two parallel leaderboards are shown — **chrF** (character-level F-score, "
        "fast, deterministic, paraphrase-blind) and **COMET-Kiwi-22** (reference-free neural "
        "MT quality estimation, slower but more correlated with human judgment). System "
        "rankings can differ between metrics, especially for systems that paraphrase well."
    )
    lines = [
        "# LayoutTranslateBench Leaderboard",
        "",
        f"_Generated {generated_at} from LayoutTranslateBench v{__version__}._",
        "",
        n_caveat,
        "",
        metric_caveat,
        "",
        "---",
        "",
        "# Leaderboard A — chrF",
        "",
    ]
    lines.extend(_render_section(chrf_rows, metric_label="chrF", metric_col_header="chrF"))

    lines += [
        "",
        "---",
        "",
        "# Leaderboard B — COMET-Kiwi-22",
        "",
        "*COMET-Kiwi is reference-free; the per-region chrF column shown above is replaced by "
        "the COMET-Kiwi score (also in [0, 100], higher = better).*",
        "",
    ]
    lines.extend(_render_section(comet_rows, metric_label="COMET-Kiwi", metric_col_header="COMET-Kiwi"))

    lines += [
        "",
        "---",
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
    chrf_results, comet_results = _load_results_split_by_metric(results_dir)
    chrf_rows = _rank(chrf_results)
    comet_rows = _rank(comet_results)
    chrf_e2e, chrf_oracle = _split_by_type(chrf_rows)
    comet_e2e, comet_oracle = _split_by_type(comet_rows)
    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    output_dir.mkdir(parents=True, exist_ok=True)
    env = Environment(
        loader=FileSystemLoader(_TEMPLATE_DIR),
        autoescape=select_autoescape(["html"]),
    )
    template = env.get_template("index.html.j2")
    html = template.render(
        # Backwards-compatible names: end_to_end / oracle default to the chrF view
        rows=chrf_rows + comet_rows,
        end_to_end=chrf_e2e,
        oracle=chrf_oracle,
        chrf_end_to_end=chrf_e2e,
        chrf_oracle=chrf_oracle,
        comet_end_to_end=comet_e2e,
        comet_oracle=comet_oracle,
        generated_at=generated_at,
        version=__version__,
    )
    (output_dir / "index.html").write_text(html, encoding="utf-8")

    if leaderboard_md is not None:
        leaderboard_md.write_text(
            _render_markdown(chrf_rows, comet_rows, generated_at), encoding="utf-8"
        )

    return len(chrf_rows) + len(comet_rows)
