# Contributing to LayoutTranslateBench

LayoutTranslateBench (LTB) is a public benchmark; contributions are welcome from anyone, no affiliation required. Three classes of contribution are highest-impact in v0.1:

## 1. Documents and annotations

The v0.1 release ships 5 sample documents as a smoke test. The full benchmark targets 200 (10 categories × 20 docs). Contributing a real document requires:

- The source page image or PDF (must be redistributable under CC-BY-4.0 or compatible)
- A clean annotation JSON matching `ltbench.schemas.Annotation`, with:
  - Bounding boxes for every text region
  - Source text (verbatim)
  - **Human-translated** references for all five language pairs (`en-es`, `en-de`, `en-zh`, `en-ar`, `en-ja`)
  - Reading-order index, layout class, style hints

We especially need documents in **handwritten / mixed-media**, **certificates**, **non-Latin source languages**, and **two-column scientific** categories.

To submit a document, open a PR adding the source under `data/sources/` and the annotation under `data/annotations/`, then add a matching entry to `data/manifest.json`. Run `ltbench verify` locally before pushing.

## 2. Runner adapters

A runner wraps a translation system and produces LTB-format submissions. To add one:

1. Create `ltbench/runners/<system>.py` subclassing `Runner` and implementing `translate(annotation, lang_pair) -> DocumentSubmission`.
2. Add a CLI entry-point or a small driver script so anyone can reproduce a submission from your adapter.
3. Open a PR including a sample submission directory under `submissions/<system>/`.

Wanted: DeepL Document API, Google Translate Documents, GPT-5 vision, Claude Sonnet/Haiku vision, Mistral Document OCR, a local Qwen3-VL + VAE pipeline, and a classical OCR + plain-text-MT baseline.

## 3. Methodology improvements

Open an issue with a concrete proposal before submitting code. Examples of welcome proposals:

- Better text quality metrics (BLEURT, COMET-Kiwi without references, MetricX) — must run CPU-friendly
- Improved region matching (Hungarian assignment vs greedy IoU; polygon IoU for skewed regions)
- v0.2 visual fidelity (LPIPS / SSIM) and OCR round-trip implementations
- Held-out split rotation logic

Methodology changes are versioned — adopting a v0.2 weighting does not invalidate v0.1 results; both display side-by-side on the leaderboard with version labels.

## Development workflow

```bash
git clone <repo>
cd document-parser
pip install -e ".[dev]"
pytest
ltbench verify
ltbench run-baseline
ltbench score --submission submissions/identity-baseline
ltbench leaderboard
```

CI runs the same sequence on every PR. Failing CI blocks merge.

## Style and conventions

- Python 3.10+, type hints required for public APIs
- Pydantic v2 for all data shapes
- No heavyweight ML dependencies in the core scoring path (must remain CPU-only)
- New optional dependencies go into `pyproject.toml` extras (e.g. `[visual]`, `[runners]`)
- Tests for any new metric or scoring rule

## Code of conduct

Be respectful. Discuss methodology in issues before opening contentious PRs. Don't submit results scored on the held-out split — re-scoring is the maintainers' job.

## License

By contributing you agree that your contributions are licensed under Apache-2.0 (code) or CC-BY-4.0 (data), matching the repository licenses.
