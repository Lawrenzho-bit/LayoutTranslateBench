"""`ltbench` command-line interface.

Commands:
    ltbench verify                 — validate the dataset manifest + annotation files
    ltbench score                  — score a submission, write a result JSON
    ltbench leaderboard            — regenerate the static leaderboard from results/
    ltbench run-baseline           — run the identity baseline against the dataset
    ltbench run-qwen-vl            — run a local Qwen-VL model against the dataset
    ltbench run-deepl              — run the DeepL Text API runner (oracle layout)
    ltbench run-florence-nllb      — run the Florence-2 + NLLB-200 pipeline (end-to-end)
    ltbench run-nllb               — run the NLLB-200 Text runner (oracle layout)
    ltbench render                 — render annotation JSONs to PNG source images
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
        # v0.1.4: partial reference coverage is permitted for docs imported from
        # external sources (ml-curated / certified-translator). Author-curated
        # docs still require references in all 8 LTB pairs as a quality contract.
        grade = ann.provenance.grade if ann.provenance else "author-curated"
        require_full_coverage = grade == "author-curated"
        for region in ann.regions:
            missing = [lp for lp in LANG_PAIRS if lp not in region.references]
            if missing and require_full_coverage:
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
    exclude_parser_failures: bool = typer.Option(
        False,
        "--exclude-parser-failures",
        help="Drop documents that triggered the runner's parser fallback "
        "(1-region empty placeholder) from per-pair and overall aggregation. "
        "Useful for separating model quality from prompt/parser quality "
        "(v0.1.2 methodology fix #9).",
    ),
    text_metric: str = typer.Option(
        "chrf",
        "--text-metric",
        help="Text-quality metric for the chrF position in LTB-100. "
        "'chrf' (default) is the v0.1.1 chrF₂ with language-detection gate. "
        "'comet-kiwi' substitutes COMET-Kiwi-22 (reference-free neural QE, "
        "Unbabel) — requires `unbabel-comet` installed. See "
        "ltbench/metrics/comet.py for setup instructions.",
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
    # v0.1.4: filter out (doc, pair) combinations where the annotation has no
    # reference text in that pair. This is necessary because v0.1.4 introduces
    # partial-coverage docs (rileykim-derived) that cover only one LTB pair.
    per_pair_data: dict[str, list[tuple]] = {}
    skipped = 0
    skipped_no_ref = 0
    for lang_pair, docs in per_pair.items():
        paired: list[tuple] = []
        for doc_sub in docs:
            ann = annotations.get(doc_sub.doc_id)
            if ann is None:
                skipped += 1
                continue
            # Drop if annotation has no reference for this pair (partial coverage)
            has_ref = any(lang_pair in r.references for r in ann.regions)
            if not has_ref:
                skipped_no_ref += 1
                continue
            paired.append((ann, doc_sub))
        per_pair_data[lang_pair] = paired

    if skipped:
        console.print(
            f"[yellow]Warning:[/yellow] skipped {skipped} submissions with unknown doc_id"
        )
    if skipped_no_ref:
        console.print(
            f"[yellow]Note:[/yellow] dropped {skipped_no_ref} (doc, pair) pairs lacking references "
            f"(expected for v0.1.4 partial-coverage docs)"
        )

    result = score_submission(  # type: ignore[arg-type]
        system,
        per_pair_data,
        exclude_parser_failures=exclude_parser_failures,
        text_metric=text_metric,
    )

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


@app.command(name="render")
def render(
    manifest: Path = typer.Option(Path("data/manifest.json")),
    data_root: Path = typer.Option(Path("data")),
) -> None:
    """Render annotation JSONs into PNG source images under data/sources/."""
    try:
        from scripts.render_samples import render_all
    except ImportError:
        # Fall back to running the script directly from the project root
        import importlib.util

        script = Path(__file__).parent.parent / "scripts" / "render_samples.py"
        spec = importlib.util.spec_from_file_location("render_samples", script)
        if spec is None or spec.loader is None:
            console.print("[red]Could not locate scripts/render_samples.py[/red]")
            raise typer.Exit(code=2)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        render_all = mod.render_all  # type: ignore[attr-defined]

    count = 0
    for path in render_all(manifest_path=manifest, data_root=data_root):
        console.print(f"  [green]rendered[/green]  {path}")
        count += 1
    console.print(f"[green]{count} PNG(s) written.[/green]")


@app.command(name="run-qwen-vl")
def run_qwen_vl(
    manifest: Path = typer.Option(Path("data/manifest.json")),
    data_root: Path = typer.Option(Path("data")),
    submission_dir: Path = typer.Option(Path("submissions/qwen-vl")),
    model_id: Optional[str] = typer.Option(
        None,
        help="HuggingFace model id. Defaults to Qwen/Qwen3-VL-2B-Instruct or $LTB_QWEN_MODEL_ID.",
    ),
    device: Optional[str] = typer.Option(None, help="cuda | cpu (auto if unset)"),
    dtype: str = typer.Option("auto", help="auto | fp16 | bf16 | fp32"),
    max_new_tokens: int = typer.Option(2048),
    lang_pairs: Optional[str] = typer.Option(
        None,
        help="Comma-separated subset of language pairs (default: all). "
        "Example: --lang-pairs en-es,en-de",
    ),
    docs: Optional[str] = typer.Option(
        None,
        help="Comma-separated subset of doc_ids (default: all). Example: --docs doc_001,doc_002",
    ),
) -> None:
    """Run a local Qwen-VL model against the dataset and write a submission.

    Requires the heavy extras: pip install -e ".[runners-qwen]"
    """
    from ltbench.runners import get_qwen_vl_runner

    m = load_manifest(manifest)
    runner = get_qwen_vl_runner(
        model_id=model_id,
        device=device,
        dtype=dtype,
        max_new_tokens=max_new_tokens,
        data_root=data_root,
    )

    selected_pairs = list(LANG_PAIRS)
    if lang_pairs:
        wanted = {p.strip() for p in lang_pairs.split(",") if p.strip()}
        selected_pairs = [p for p in LANG_PAIRS if p in wanted]
        if not selected_pairs:
            console.print(f"[red]No valid language pairs in --lang-pairs {lang_pairs}[/red]")
            raise typer.Exit(code=2)

    selected_entries = list(m.entries)
    if docs:
        wanted_docs = {d.strip() for d in docs.split(",") if d.strip()}
        selected_entries = [e for e in m.entries if e.doc_id in wanted_docs]
        if not selected_entries:
            console.print(f"[red]No matching doc_ids in --docs {docs}[/red]")
            raise typer.Exit(code=2)

    submission_dir.mkdir(parents=True, exist_ok=True)

    console.print(f"[cyan]Loading model[/cyan] {runner.model_id} ...")
    runner._ensure_loaded()  # warm load so the first translate doesn't dominate the timer
    console.print(f"[green]Model loaded on {runner._actual_device}.[/green]")

    sys_manifest_path = submission_dir / "manifest.json"
    with sys_manifest_path.open("w", encoding="utf-8") as f:
        json.dump(runner.system_manifest().model_dump(), f, indent=2)

    total = len(selected_pairs) * len(selected_entries)
    n_written = 0
    runtime_total = 0.0
    for lang_pair in selected_pairs:
        path = submission_dir / f"{lang_pair}.jsonl"
        with path.open("w", encoding="utf-8") as f:
            for entry in selected_entries:
                ann = load_annotation(data_root / entry.annotation_file)
                console.print(
                    f"  [dim]({n_written + 1}/{total})[/dim] {lang_pair} / {entry.doc_id}",
                    end="",
                )
                sub: DocumentSubmission = runner.translate(ann, lang_pair)  # type: ignore[arg-type]
                f.write(sub.model_dump_json() + "\n")
                n_written += 1
                runtime_total += sub.runtime_seconds or 0.0
                rt = f" ({sub.runtime_seconds:.1f}s)" if sub.runtime_seconds is not None else ""
                console.print(f" [green]->[/green] {len(sub.regions)} regions{rt}")
    console.print(
        f"[green]Wrote {n_written} submissions[/green] to {submission_dir}"
        f" (total {runtime_total:.1f}s)"
    )


@app.command(name="run-deepl")
def run_deepl(
    manifest: Path = typer.Option(Path("data/manifest.json")),
    data_root: Path = typer.Option(Path("data")),
    submission_dir: Path = typer.Option(Path("submissions/deepl-text-oracle")),
    api_key: Optional[str] = typer.Option(
        None,
        help="DeepL API key. If unset, reads DEEPL_API_KEY env var.",
    ),
    pro: bool = typer.Option(False, help="Use Pro endpoint instead of free-tier."),
    formality: Optional[str] = typer.Option(
        None,
        help="DeepL formality option (default / more / less). Only some target languages support it.",
    ),
    lang_pairs: Optional[str] = typer.Option(
        None, help="Comma-separated subset of language pairs. Example: --lang-pairs en-es,en-de"
    ),
    docs: Optional[str] = typer.Option(
        None, help="Comma-separated subset of doc_ids. Example: --docs doc_001,doc_002"
    ),
) -> None:
    """Run the DeepL Text API runner (oracle-layout baseline).

    Requires: pip install -e ".[runners-deepl]"

    This is an oracle-layout runner: ground-truth bboxes are copied as predictions.
    It measures DeepL's *text* quality assuming perfect layout extraction.
    """
    from ltbench.runners import get_deepl_text_runner

    m = load_manifest(manifest)
    runner = get_deepl_text_runner(api_key=api_key, free_tier=not pro, formality=formality)

    selected_pairs = list(LANG_PAIRS)
    if lang_pairs:
        wanted = {p.strip() for p in lang_pairs.split(",") if p.strip()}
        selected_pairs = [p for p in LANG_PAIRS if p in wanted]
        if not selected_pairs:
            console.print(f"[red]No valid language pairs in --lang-pairs {lang_pairs}[/red]")
            raise typer.Exit(code=2)

    selected_entries = list(m.entries)
    if docs:
        wanted_docs = {d.strip() for d in docs.split(",") if d.strip()}
        selected_entries = [e for e in m.entries if e.doc_id in wanted_docs]
        if not selected_entries:
            console.print(f"[red]No matching doc_ids in --docs {docs}[/red]")
            raise typer.Exit(code=2)

    submission_dir.mkdir(parents=True, exist_ok=True)
    sys_manifest_path = submission_dir / "manifest.json"
    with sys_manifest_path.open("w", encoding="utf-8") as f:
        json.dump(runner.system_manifest().model_dump(), f, indent=2)

    from ltbench.runners.deepl_text import UnsupportedLanguageError

    total = len(selected_pairs) * len(selected_entries)
    n_written = 0
    skipped_unsupported: list[str] = []
    runtime_total = 0.0
    for lang_pair in selected_pairs:
        # Skip language pairs DeepL doesn't support; record the gap so the
        # submission shows them as n=0 on the leaderboard.
        if not runner.supports(lang_pair):
            skipped_unsupported.append(lang_pair)
            console.print(
                f"  [yellow]skip[/yellow] {lang_pair}: not supported by DeepL"
            )
            continue

        path = submission_dir / f"{lang_pair}.jsonl"
        with path.open("w", encoding="utf-8") as f:
            for entry in selected_entries:
                ann = load_annotation(data_root / entry.annotation_file)
                console.print(
                    f"  [dim]({n_written + 1}/{total})[/dim] {lang_pair} / {entry.doc_id}",
                    end="",
                )
                try:
                    sub: DocumentSubmission = runner.translate(ann, lang_pair)  # type: ignore[arg-type]
                except UnsupportedLanguageError:
                    console.print(" [yellow]skip[/yellow]")
                    continue
                f.write(sub.model_dump_json() + "\n")
                n_written += 1
                runtime_total += sub.runtime_seconds or 0.0
                rt = f" ({sub.runtime_seconds:.2f}s)" if sub.runtime_seconds is not None else ""
                console.print(f" [green]->[/green] {len(sub.regions)} regions{rt}")

    runner.close()

    if skipped_unsupported:
        console.print(
            f"[yellow]Note:[/yellow] DeepL did not support: "
            f"{', '.join(skipped_unsupported)}. These pairs will appear as n=0 "
            f"on the leaderboard — that's a real DeepL coverage gap, not a bug."
        )
    console.print(
        f"[green]Wrote {n_written} submissions[/green] to {submission_dir}"
        f" (total {runtime_total:.1f}s)"
    )


@app.command(name="run-florence-nllb")
def run_florence_nllb(
    manifest: Path = typer.Option(Path("data/manifest.json")),
    data_root: Path = typer.Option(Path("data")),
    submission_dir: Path = typer.Option(Path("submissions/florence-nllb")),
    florence_model: Optional[str] = typer.Option(
        None, help="HuggingFace id. Default: microsoft/Florence-2-base"
    ),
    nllb_model: Optional[str] = typer.Option(
        None, help="HuggingFace id. Default: facebook/nllb-200-distilled-600M"
    ),
    device: Optional[str] = typer.Option(None, help="cuda | cpu (auto if unset)"),
    lang_pairs: Optional[str] = typer.Option(
        None, help="Comma-separated subset of language pairs."
    ),
    docs: Optional[str] = typer.Option(
        None, help="Comma-separated subset of doc_ids."
    ),
) -> None:
    """Run the Florence-2 + NLLB-200 end-to-end pipeline.

    Florence-2 extracts text + bboxes; NLLB-200 translates each region.
    Bboxes come from the model (not the GT) — this is a true end-to-end runner.

    Requires: pip install -e ".[runners-florence-nllb]"
    """
    from ltbench.runners import get_florence_nllb_runner

    m = load_manifest(manifest)
    runner = get_florence_nllb_runner(
        florence_model=florence_model,
        nllb_model=nllb_model,
        device=device,
        data_root=data_root,
    )

    selected_pairs = list(LANG_PAIRS)
    if lang_pairs:
        wanted = {p.strip() for p in lang_pairs.split(",") if p.strip()}
        selected_pairs = [p for p in LANG_PAIRS if p in wanted]
        if not selected_pairs:
            console.print(f"[red]No valid language pairs in --lang-pairs {lang_pairs}[/red]")
            raise typer.Exit(code=2)

    selected_entries = list(m.entries)
    if docs:
        wanted_docs = {d.strip() for d in docs.split(",") if d.strip()}
        selected_entries = [e for e in m.entries if e.doc_id in wanted_docs]
        if not selected_entries:
            console.print(f"[red]No matching doc_ids in --docs {docs}[/red]")
            raise typer.Exit(code=2)

    submission_dir.mkdir(parents=True, exist_ok=True)

    console.print(
        f"[cyan]Loading[/cyan] {runner.florence_model} + {runner.nllb_model} ..."
    )
    runner._ensure_loaded()
    console.print(f"[green]Loaded on {runner._actual_device}.[/green]")

    sys_manifest_path = submission_dir / "manifest.json"
    with sys_manifest_path.open("w", encoding="utf-8") as f:
        json.dump(runner.system_manifest().model_dump(), f, indent=2)

    total = len(selected_pairs) * len(selected_entries)
    n_written = 0
    runtime_total = 0.0
    for lang_pair in selected_pairs:
        path = submission_dir / f"{lang_pair}.jsonl"
        with path.open("w", encoding="utf-8") as f:
            for entry in selected_entries:
                ann = load_annotation(data_root / entry.annotation_file)
                console.print(
                    f"  [dim]({n_written + 1}/{total})[/dim] {lang_pair} / {entry.doc_id}",
                    end="",
                )
                sub: DocumentSubmission = runner.translate(ann, lang_pair)  # type: ignore[arg-type]
                f.write(sub.model_dump_json() + "\n")
                n_written += 1
                runtime_total += sub.runtime_seconds or 0.0
                rt = (
                    f" ({sub.runtime_seconds:.1f}s)" if sub.runtime_seconds is not None else ""
                )
                console.print(f" [green]->[/green] {len(sub.regions)} regions{rt}")

    runner.close()
    console.print(
        f"[green]Wrote {n_written} submissions[/green] to {submission_dir}"
        f" (total {runtime_total:.1f}s)"
    )


@app.command(name="run-nllb")
def run_nllb(
    manifest: Path = typer.Option(Path("data/manifest.json")),
    data_root: Path = typer.Option(Path("data")),
    submission_dir: Path = typer.Option(Path("submissions/nllb-text-oracle")),
    nllb_model: Optional[str] = typer.Option(
        None, help="HuggingFace id. Default: facebook/nllb-200-distilled-600M"
    ),
    device: Optional[str] = typer.Option(None, help="cuda | cpu (auto if unset)"),
    num_beams: int = typer.Option(4),
    batch_size: int = typer.Option(8),
    lang_pairs: Optional[str] = typer.Option(None),
    docs: Optional[str] = typer.Option(None),
) -> None:
    """Run the NLLB-200 Text runner (oracle layout, open-source MT).

    Requires: pip install -e ".[runners-nllb]"
    """
    from ltbench.runners import get_nllb_text_runner

    m = load_manifest(manifest)
    runner = get_nllb_text_runner(
        nllb_model=nllb_model, device=device, num_beams=num_beams, batch_size=batch_size
    )

    selected_pairs = list(LANG_PAIRS)
    if lang_pairs:
        wanted = {p.strip() for p in lang_pairs.split(",") if p.strip()}
        selected_pairs = [p for p in LANG_PAIRS if p in wanted]
        if not selected_pairs:
            console.print(f"[red]No valid language pairs in --lang-pairs {lang_pairs}[/red]")
            raise typer.Exit(code=2)

    selected_entries = list(m.entries)
    if docs:
        wanted_docs = {d.strip() for d in docs.split(",") if d.strip()}
        selected_entries = [e for e in m.entries if e.doc_id in wanted_docs]
        if not selected_entries:
            console.print(f"[red]No matching doc_ids in --docs {docs}[/red]")
            raise typer.Exit(code=2)

    submission_dir.mkdir(parents=True, exist_ok=True)
    console.print(f"[cyan]Loading[/cyan] {runner.nllb_model} ...")
    runner._ensure_loaded()
    console.print(f"[green]Loaded on {runner._actual_device}.[/green]")

    sys_manifest_path = submission_dir / "manifest.json"
    with sys_manifest_path.open("w", encoding="utf-8") as f:
        json.dump(runner.system_manifest().model_dump(), f, indent=2)

    total = len(selected_pairs) * len(selected_entries)
    n_written = 0
    runtime_total = 0.0
    for lang_pair in selected_pairs:
        path = submission_dir / f"{lang_pair}.jsonl"
        with path.open("w", encoding="utf-8") as f:
            for entry in selected_entries:
                ann = load_annotation(data_root / entry.annotation_file)
                console.print(
                    f"  [dim]({n_written + 1}/{total})[/dim] {lang_pair} / {entry.doc_id}",
                    end="",
                )
                sub: DocumentSubmission = runner.translate(ann, lang_pair)  # type: ignore[arg-type]
                f.write(sub.model_dump_json() + "\n")
                n_written += 1
                runtime_total += sub.runtime_seconds or 0.0
                rt = (
                    f" ({sub.runtime_seconds:.1f}s)" if sub.runtime_seconds is not None else ""
                )
                console.print(f" [green]->[/green] {len(sub.regions)} regions{rt}")

    runner.close()
    console.print(
        f"[green]Wrote {n_written} submissions[/green] to {submission_dir}"
        f" (total {runtime_total:.1f}s)"
    )


@app.command(name="export-eval-prompts")
def export_eval_prompts(
    submissions: list[str] = typer.Option(
        ..., "--submission", "-s", help="One or more submission names (under submissions/)."
    ),
    manifest: Path = typer.Option(Path("data/manifest.json")),
    data_root: Path = typer.Option(Path("data")),
    output: Path = typer.Option(Path("eval/da_prompts.csv")),
    lang_pairs: Optional[str] = typer.Option(None, help="Filter to specific pairs."),
) -> None:
    """Export a CSV of rows for human raters to score (Direct Assessment 0–100).

    One row per (system, doc, region) — including the source text, the
    predicted translation, and the reference. Raters fill in `da_score`
    (and optional `notes`) per row, then `ltbench import-judgments` ingests
    the completed CSV. v0.1.2 methodology fix #10 infrastructure.
    """
    import csv

    m = load_manifest(manifest)
    annotations = {
        entry.doc_id: load_annotation(data_root / entry.annotation_file) for entry in m.entries
    }

    selected_pairs = list(LANG_PAIRS)
    if lang_pairs:
        wanted = {p.strip() for p in lang_pairs.split(",") if p.strip()}
        selected_pairs = [p for p in LANG_PAIRS if p in wanted]

    output.parent.mkdir(parents=True, exist_ok=True)
    n_rows = 0
    with output.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "judgment_id",
                "system_name",
                "doc_id",
                "lang_pair",
                "region_id",
                "source_text",
                "predicted_text",
                "reference_text",
                "da_score",  # blank — for rater to fill in 0–100
                "notes",  # blank — optional
            ]
        )
        for sub_name in submissions:
            sub_dir = Path("submissions") / sub_name
            if not sub_dir.exists():
                console.print(f"[yellow]Warn:[/yellow] {sub_dir} does not exist; skipping")
                continue
            for lang_pair in selected_pairs:
                jsonl_path = sub_dir / f"{lang_pair}.jsonl"
                if not jsonl_path.exists():
                    continue
                with jsonl_path.open("r", encoding="utf-8") as jf:
                    for line in jf:
                        line = line.strip()
                        if not line:
                            continue
                        sub = json.loads(line)
                        doc_id = sub["doc_id"]
                        ann = annotations.get(doc_id)
                        if ann is None:
                            continue
                        gt_by_id = {r.region_id: r for r in ann.regions}
                        for pred_region in sub["regions"]:
                            gt = gt_by_id.get(pred_region["region_id"])
                            if gt is None:
                                continue
                            ref_text = gt.references.get(lang_pair, "")
                            writer.writerow(
                                [
                                    f"{sub_name}-{doc_id}-{lang_pair}-{pred_region['region_id']}",
                                    sub_name,
                                    doc_id,
                                    lang_pair,
                                    pred_region["region_id"],
                                    gt.text,
                                    pred_region.get("text", ""),
                                    ref_text,
                                    "",  # da_score
                                    "",  # notes
                                ]
                            )
                            n_rows += 1
    console.print(f"[green]Wrote {n_rows} eval prompts[/green] -> {output}")
    console.print(
        "[dim]Raters: fill in da_score (0-100, Direct Assessment scale) and optional notes.[/dim]"
    )


@app.command(name="correlate-human")
def correlate_human(
    judgments_dir: Path = typer.Option(Path("data/human_judgments")),
    results_dir: Path = typer.Option(Path("results")),
    output: Optional[Path] = typer.Option(None, help="Optional JSON output path."),
) -> None:
    """Compute correlation between human DA scores and automatic LTB-100.

    Reads all judgments under data/human_judgments/*/*.jsonl, aggregates by
    cell, joins with per-document scores in results/*.json, and reports
    Kendall τ + Pearson r per system.

    No-op (prints a guidance message) if no judgments are found. v0.1.2
    methodology fix #10 infrastructure.
    """
    from ltbench.human_eval import (
        aggregate_per_cell,
        extract_automatic_doc_scores_from_result,
        kendall_tau_human_vs_auto,
        load_judgments,
    )

    judgments = load_judgments(judgments_dir)
    if not judgments:
        console.print(
            "[yellow]No human judgments found at "
            f"{judgments_dir}.[/yellow]\n\n"
            "Workflow:\n"
            "  1. Run 'ltbench export-eval-prompts -s <system_name>' to export a CSV\n"
            "  2. Have raters fill in da_score (0-100) per row\n"
            "  3. Save completed JSONLs at "
            f"{judgments_dir}/<rater_id>/<system>-<lang_pair>.jsonl\n"
            "  4. Re-run this command."
        )
        raise typer.Exit(code=0)

    human_per_cell = aggregate_per_cell(judgments)
    console.print(f"[cyan]Loaded[/cyan] {len(judgments)} judgments across "
                  f"{len(human_per_cell)} unique cells")

    # Build automatic scores per system, then correlate per system
    summary: dict[str, dict] = {}
    for result_path in sorted(results_dir.glob("*.json")):
        if result_path.name.endswith(".local.json"):
            continue
        with result_path.open("r", encoding="utf-8") as f:
            r = json.load(f)
        auto_scores = extract_automatic_doc_scores_from_result(r)
        if not auto_scores:
            continue
        system_name = r["system"]["system_name"]
        # Restrict to this system's judgments
        sys_human = {k: v for k, v in human_per_cell.items() if k[0] == system_name}
        if not sys_human:
            continue
        corr = kendall_tau_human_vs_auto(sys_human, auto_scores)
        summary[system_name] = corr
        console.print(
            f"  [bold]{system_name}[/bold]: n={corr['n_pairs']} cells, "
            f"τ_norm={corr['kendall_tau_norm']:.4f}, r={corr['pearson_r']:.4f}"
        )

    if not summary:
        console.print("[yellow]No overlap between human judgments and automatic scores.[/yellow]")
        raise typer.Exit(code=0)

    if output is None:
        output = results_dir / "human_correlation.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    console.print(f"[green]Wrote correlation summary[/green] -> {output}")


def main() -> None:
    try:
        app()
    except KeyboardInterrupt:
        console.print("[yellow]Interrupted.[/yellow]")
        sys.exit(130)


if __name__ == "__main__":
    main()
