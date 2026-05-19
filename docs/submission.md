# LayoutTranslateBench — How to Submit

A submission to LayoutTranslateBench (LTB) is a directory containing one `manifest.json` (system metadata) and one JSONL file per language pair (`en-es.jsonl`, `en-de.jsonl`, `en-zh.jsonl`, `en-ar.jsonl`, `en-ja.jsonl`). Each line of each JSONL is one translated document, with predicted text regions and bounding boxes.

## Quickstart

```bash
# 1. Install
pip install -e .

# 2. Verify the dataset is intact
ltbench verify

# 3. Produce an identity-baseline submission as a reference
ltbench run-baseline

# 4. Score your submission
ltbench score --submission submissions/<your-system>

# 5. Rebuild the leaderboard from the results/ directory
ltbench leaderboard
```

## Directory layout

```
submissions/<your-system-name>/
├── manifest.json     # SystemManifest — required
├── en-es.jsonl       # one DocumentSubmission per line — required
├── en-de.jsonl
├── en-zh.jsonl
├── en-ar.jsonl
└── en-ja.jsonl
```

Partial submissions are accepted (e.g., only `en-es.jsonl`); the unscored pairs are simply omitted from the overall score, and the leaderboard flags the submission as partial.

## `manifest.json` schema

See [`ltbench/schemas.py`](../ltbench/schemas.py) — `SystemManifest`. Example:

```json
{
  "system_name": "deepl-doc",
  "system_version": "2026-04-01",
  "manifest_version": "0.1",
  "model_id_or_url": "https://www.deepl.com/docs-api",
  "runner_config": {"formality": "default", "preserve_formatting": true},
  "hardware": "DeepL Cloud",
  "total_runtime_seconds": 142.5,
  "median_per_doc_runtime_seconds": 5.3,
  "cost_usd": 0.42,
  "submitter": "Jane Doe <jane@example.org>",
  "notes": "Used DeepL Document API. Reading order extracted post-hoc by sorting by bbox y-coordinate."
}
```

## JSONL line schema

Each line in `<lang-pair>.jsonl` is a `DocumentSubmission`:

```json
{
  "doc_id": "doc_001",
  "regions": [
    {
      "region_id": "r1",
      "bbox": [200, 60, 400, 60],
      "text": "Certificado de Nacimiento",
      "reading_order": 0
    }
  ],
  "output_file": "outputs/doc_001.es.pdf",
  "runtime_seconds": 4.8
}
```

- `region_id` should match the ground-truth region id when known. The scorer falls back to greedy IoU matching otherwise.
- `bbox` is `(x, y, width, height)` in pixels relative to the source page. Use the bbox where your system actually placed the translated text.
- `reading_order` is the position of this region in your system's reading order (0-based, document-global).
- `output_file` (optional, recommended) is a path to the rendered output document. Required for v0.2 visual-fidelity scoring.

## Submission lifecycle

1. Submitter runs their system on the public split, produces a submission directory, runs `ltbench score` locally, and opens a pull request with their `submissions/<name>/` and `results/<name>.json`.
2. Maintainers verify the submission is well-formed, then re-score against the **held-out split** (not present in the public manifest).
3. If held-out-split scores match within tolerance, the submission is promoted to the leaderboard and flagged "verified".
4. Submissions that fail re-scoring (e.g. obvious split overfit) are rejected with a public explanation.

## What "good faith" looks like

- Submit a single system per PR — not five variants.
- Disclose any LTB documents you used as part of model development.
- Report a single primary configuration on the leaderboard; report sweeps in `notes` or a linked write-up.

## Reproducibility

The leaderboard prefers submissions with full reproducibility metadata: hardware, runtime, cost, and a `runner_config` that lets a third party re-run your system. Closed/proprietary systems are accepted but scored as "unverified" — the leaderboard distinguishes them visually.

## Open-source runners welcome

`ltbench/runners/` is the place to drop a public adapter. PRs adding adapters for new translation systems are welcome — the runner pattern means the same adapter can be used by anyone to re-score the system without re-implementing the integration.

## Oracle-layout runners

Some runners — like the bundled `deepl-text-oracle` — translate only the text and **copy the ground-truth bboxes verbatim** as predicted bboxes. This is intentional:

- It measures the *upper bound on text quality* for a given translation system, isolated from layout-extraction failure.
- It exposes the gap between a hypothetical "perfect-layout commercial MT" and real end-to-end systems.
- It is **not** a fair comparison to a true end-to-end runner that has to extract its own bboxes — and the leaderboard flags oracle-layout systems so readers don't confuse them.

If you submit a new oracle-layout runner, set `"oracle_layout": true` in your `runner_config` and explain the choice in `notes`. Run-time and cost still belong in the manifest as usual.

## Built-in runners

| Runner | CLI | Extras to install | What it measures |
|---|---|---|---|
| Identity baseline | `ltbench run-baseline` | (none) | Trivial lower bound — returns source text in source boxes |
| Qwen-VL family | `ltbench run-qwen-vl` | `pip install -e ".[runners-qwen]"` | End-to-end zero-shot VLM (Qwen3-VL by default). Heavy install. |
| DeepL Text + oracle layout | `ltbench run-deepl` | `pip install -e ".[runners-deepl]"` | Text-quality upper bound. Requires `DEEPL_API_KEY`. |
