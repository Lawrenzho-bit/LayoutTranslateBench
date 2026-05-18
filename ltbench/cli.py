"""`ltbench` command-line interface.

Commands:
    ltbench verify                 — validate the dataset manifest + annotation files
    ltbench score                  — score a submission, write a result JSON
    ltbench leaderboard            — regenerate the static leaderboard from results/
    ltbench run-baseline           — run the identity baseline against the dataset
    ltbench info                   — print weights, lang pairs, version
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ltbench import LANG_PAIRS, LTB_WEIGHTS_V01, __version__
from ltbench.dataset import load_annotation, load_manifest, load_submission
from ltbench.metrics import score_submission
from ltbench.runners import IdentityRunner
from ltbench.schemas import DocumentSubmission

app = typer.Typer(
    name="ltbench",
    help="LayoutTranslateBench — benchmark for document translation with layout preservation",
    add_completion=False,
    no_args_is_help=True,
)
console = Console()


def _project_root() -> Path:
    """Return the directory the CLI was invoked from."""
    return Path.cwd()


@app.command()
def info() -> None:
    """Print benchmark version, language pairs, and metric weights."""
    table = Table(title=f"LayoutTranslateBench v{__version__}")
    table.add_column("Setting", style="bold cyan")
    table.add_column("Value")
    table.add_row("Language pairs", ", ".join(LANG_PAIRS))
    weights_str = ", ".join(f"{k}={v}" for k, v in LTB_WEIGHTS_V01.items())
    table.add_row("LTB-100 weights (v0.1)", weights_str)
    table.add_row(
        "Composite",
        "LTB-100 = 100 * (0.50 * chrF/100 + 0.30 * IoU + 0.20 * tau)",
    )
    console.print(table)


@app.command()
def verify(
    manifest: Path = typer.Option(
        Path("data/manifest.json"),
        help="Path to the dataset manifest JSON.",
    ),
    data_root: Path = typer.Option(Path("data"), help="Root of the data directory."),
) -> None:
    """Validate the dataset: manifest entries, annotation file existence, schema."""
    try:
        m = load_manifest(manifest)
    except Exception as e:
        console.print(f"[red]Manifest load failed:[/red] {e}")
        raise typer.Exit(code=2) from e

    console.print(
        Panel.fit(
            f"[bold]{m.benchmark}[/bold] v{m.version}\n"
            f"{len(m.entries)} document entries in {manifest}",
            border_style="green",
        )
    )

    errors: list[str] = []
    for entry in m.entries:
        ann_path = data_root / entry.annotation_file
        if not ann_path.exists():
            errors.append(f"missing annotation: {entry.doc_id} -> {ann_path}")
            continue
        try:
            ann = load_annotation(ann_path)
        except Exception as e:
            errors.append(f"annotation invalid: {entry.doc_id}: {e}")
            continue
        if ann.doc_id != entry.doc_id:
            errors.append(
                f"doc_id mismatch: manifest={entry.doc_id}, annotation={ann.doc_id}"
            )
        for region in ann.regions:
            missing = [lp for lp in LANG_PAIRS if lp not in region.references]
            if missing:
                errors.append(
                    f"{entry.doc_id}/{region.region_id}: missing references {missing}"
                )

    if errors:
        console.print(f"[red]{len(errors)} error(s):[/red]")
        for e in errors[:30]:
            console.print(f"  - {e}")
        if len(errors) > 30:
            console.print(f"  ... and {len(errors) - 30} more")
        raise typer.Exit(code=1)
    console.print("[green]OK[/green] — dataset integrity verified.")


@app.command()
def score(
    submission: Path = typer.Option(..., help="Path to submission directory."),
    manifest: Path = typer.Option(Path("data/manifest.json")),
    data_root: Path = typer.Option(Path("data")),
    output: Optional[Path] = typer.Option(
        None,
        help="Where to write the result JSON. Default: results/<system-name>.json",
    ),
) -> None:
    """Score a submission against the dataset; write a result JSON."""
    m = load_manifest(manifest)
    annotations = {
        entry.doc_id: load_annotation(data_root / entry.annotation_file)
        for entry in m.entries
    }

    system, per_pair = load_submission(submission)

    # Build per-pair (annotation, submission) tuples; warn on doc_id mismatches
    per_pair_data: dict[str, list[tuple]] = {}
    skipped = 0
    for lang_pair, docs in per_pair.items():
        paired: list[tuple] = []
        for doc_sub in docs:
            ann = annotations.get(doc_sub.doc_id)
            if ann is None:
                skipped += 1
                continue
            paired.append((ann, doc_sub))
        per_pair_data[lang_pair] = paired

    if skipped:
        console.print(
            f"[yellow]Warning:[/yellow] skipped {skipped} submissions with unknown doc_id"
        )

    result = score_submission(system, per_pair_data)  # type: ignore[arg-type]

    out_path = output or Path("results") / f"{system.system_name}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(result.model_dump(), f, indent=2, ensure_ascii=False)

    # Pretty summary
    summary = Table(title=f"{system.system_name} v{system.system_version}")
    summary.add_column("Metric", style="bold cyan")
    summary.add_column("Score", justify="right")
    summary.add_row("Overall LTB-100", f"{result.overall_ltb_100:.2f}")
    summary.add_row("Overall chrF", f"{result.overall_chrf:.2f}")
    summary.add_row("Overall Layout IoU", f"{result.overall_layout_iou:.4f}")
    summary.add_row("Overall Reading-order tau", f"{result.overall_reading_order_tau:.4f}")
    console.print(summary)

    pair_table = Table(title="Per language pair")
    pair_table.add_column("Pair")
    pair_table.add_column("n", justify="right")
    pair_table.add_column("LTB-100", justify="right")
    pair_table.add_column("chrF", justify="right")
    pair_table.add_column("IoU", justify="right")
    pair_table.add_column("tau", justify="right")
    for p in result.per_lang_pair:
        pair_table.add_row(
            p.lang_pair,
            str(p.n_docs),
            f"{p.ltb_100:.2f}",
            f"{p.chrf:.2f}",
            f"{p.layout_iou:.4f}",
            f"{p.reading_order_tau:.4f}",
        )
    console.print(pair_table)
    console.print(f"[green]Result written:[/green] {out_path}")


@app.command()
def leaderboard(
    results_dir: Path = typer.Option(Path("results"), help="Directory of result JSONs."),
    output_dir: Path = typer.Option(
        Path("leaderboard"),
        help="Where to write the static leaderboard HTML.",
    ),
    leaderboard_md: Path = typer.Option(
        Path("LEADERBOARD.md"),
        help="Where to write the Markdown mirror of the leaderboard.",
    ),
) -> None:
    """Rebuild the static leaderboard from results/."""
    from ltbench.leaderboard.build import build_leaderboard

    n = build_leaderboard(results_dir, output_dir, leaderboard_md)
    console.print(
        f"[green]Built leaderboard from {n} result(s)[/green] -> {output_dir / 'index.html'}"
    )


@app.command(name="run-baseline")
def run_baseline(
    manifest: Path = typer.Option(Path("data/manifest.json")),
    data_root: Path = typer.Option(Path("data")),
    submission_dir: Path = typer.Option(Path("submissions/identity-baseline")),
) -> None:
    """Run the identity baseline against the dataset and write a submission."""
    m = load_manifest(manifest)
    runner = IdentityRunner()
    submission_dir.mkdir(parents=True, exist_ok=True)

    # Write system manifest
    sys_manifest_path = submission_dir / "manifest.json"
    with sys_manifest_path.open("w", encoding="utf-8") as f:
        json.dump(runner.system_manifest().model_dump(), f, indent=2)

    # One JSONL per language pair
    n_written = 0
    for lang_pair in LANG_PAIRS:
        path = submission_dir / f"{lang_pair}.jsonl"
        with path.open("w", encoding="utf-8") as f:
            for entry in m.entries:
                ann = load_annotation(data_root / entry.annotation_file)
                sub: DocumentSubmission = runner.translate(ann, lang_pair)  # type: ignore[arg-type]
                f.write(sub.model_dump_json() + "\n")
                n_written += 1
    console.print(
        f"[green]Wrote {n_written} document submissions[/green] to {submission_dir}"
    )


def main() -> None:
    try:
        app()
    except KeyboardInterrupt:
        console.print("[yellow]Interrupted.[/yellow]")
        sys.exit(130)


if __name__ == "__main__":
    main()
