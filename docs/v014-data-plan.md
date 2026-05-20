# v0.1.4 Dataset Expansion — rileykim/multilingual-document Integration

**Status:** Shipped. 15 documents (doc_011–doc_025) ingested.
**Outcome:** LTB expanded from 10 → 25 docs; en-ja n=18, en-zh n=17 (other 6 pairs remain at n=10).

## Candidate datasets considered

| Dataset | License | Layout/bbox? | Translations? | Pair coverage | Outcome |
|---|---|---|---|---|---|
| `rileykim/multilingual-document` | **Apache-2.0** | **Yes (`merge_ocr` xyxy)** | Yes (10 pairs) | en-ja + en-zh-cn overlap with LTB | **Adopted (Tier A)** |
| `facebook/flores` (FLORES-200) | CC-BY-SA-4.0 | No (sentence-only) | Yes, professional translators | 8/8 of LTB pairs | **Tier B** — quality oracle, license-segregated |
| DocHPLT (2025) | TBD | Document-level | Yes | TBD | **Tier C** — investigate later |
| `EUR-Lex` parallel corpus | EU Open Data | No | Yes, certified | EU only | Tier D |

## Decision tree

```
Run scripts/inspect_rileykim.py
├── Has bboxes + >= 4 of our 8 pairs + CC-BY or CC0
│     → Tier A path: write adapter, ingest 20-30 docs as v0.1.4
├── Has translations but no bboxes
│     → Tier B-prime path: use as text source, render synthetic
│       LTB pages via scripts/render_samples.py
└── Wrong shape / restrictive license
      → Fall back to FLORES-200 (Tier B)
          → Compose synthetic LTB pages from FLORES sentences
          → Keep FLORES-derived docs in data/flores_derived/
            with own LICENSE file (CC-BY-SA-4.0)
          → Do NOT mix into main annotations/ directory
            (avoids share-alike contamination of CC-BY-4.0 LTB core)
```

## Fitness criteria (rileykim spike)

A rileykim row is **directly usable** if:
1. License is CC-BY-4.0, CC-BY-SA-4.0, CC0, or Apache-2.0 (we can attribute)
2. Bbox info per text region is present (or derivable from OCR output)
3. At least 4 of our 8 target language pairs are represented (en-es, en-de, en-zh, en-ar, en-ja, en-fr, en-th, en-ms)
4. Document category is recognizable (legal/medical/business/etc.) for category-balanced sampling

A rileykim row is **partially usable** (text-only, render pipeline) if:
- License OK + translations present, but bboxes absent
- We then use scripts/render_samples.py to synthesize a layout

A rileykim row is **rejected** if:
- License is non-commercial or restrictive
- No translations to any of our 8 pairs

## License segregation strategy

LTB's core annotations are **CC-BY-4.0**. To avoid share-alike contamination:
- Any **CC-BY-SA-4.0**-derived documents (e.g. FLORES) live in `data/<source>_derived/` with their own LICENSE file
- `data/manifest.json` records the license per entry; downstream users must respect per-document license
- A `provenance` field will be added to each annotation in v0.1.4: `{"source": "author-curated" | "rileykim" | "flores-200" | ...}`

## Quality grading

| Source | Quality grade (per docs/methodology.md) |
|---|---|
| Author-curated (v0.1, v0.1.3) | Comparable to competent native-speaker non-professional |
| rileykim (v0.1.4 candidate) | TBD — depends on stated provenance |
| FLORES-200 (v0.1.4 fallback) | **Industry-grade** (professional translators) — would be the first certified-quality references in LTB |
| Certified-translator (v0.2 target) | Industry-grade |

If FLORES integrates cleanly, **we can claim v0.1.4 has partial industry-grade references** (the FLORES-derived subset) without waiting for the v0.2 €10–25k budget. This would be a meaningful credibility upgrade for the benchmark.

## What was actually shipped

- [x] Ran `scripts/inspect_rileykim.py` + `inspect_rileykim_stream.py` + `inspect_rileykim_groups.py` — schema verified
- [x] Ran `scripts/import_rileykim.py` (streaming-mode adapter, en-ja batch)
- [x] Ran `scripts/import_rileykim_parquet.py` (direct-parquet adapter, en-zh-cn batch — faster since en-zh-cn lives at the end of the 27-shard stream)
- [x] Added `Provenance` model + `ocr-document` Category + `ReferenceGrade` Literal to `ltbench/schemas.py`
- [x] Updated `ltbench/cli.py` `verify` to permit partial reference coverage for non-author-curated docs
- [x] Updated `ltbench/cli.py` `score` to drop (doc, pair) combinations without references (was double-counting at chrF≈0)
- [x] Added `tests/test_v014.py` with 7 regression tests for partial-coverage scoring
- [x] Re-scored identity baseline on N=25 → `results/identity-baseline-v014.json`
- [x] Updated `data/README.md` and `docs/methodology.md` with v0.1.4 provenance table

## Key implementation findings

- Each rileykim image_id appears in exactly ONE lang_pair — no image is paired with multiple targets. So we cannot get multi-pair coverage from a single rileykim doc; this is the structural reason v0.1.4 docs are "partial coverage."
- The test split (1k rows) has a parquet schema bug that breaks `load_dataset(repo)` in non-streaming mode; streaming-mode and direct-parquet-on-cache both work.
- Rows are physically grouped by lang_pair in the parquet shards, so en-zh-cn lives near the end of the stream. Direct-parquet read of shards 24–26 in reverse hit en-zh-cn in seconds; streaming from the start took minutes.

## Deferred to future versions

- **FLORES-200 integration** — `scripts/inspect_flores.py` exists; not used yet. Would give certified-translator quality across all 8 LTB pairs but with CC-BY-SA-4.0 license segregation requirement.
- **Extending `LangPair` Literal** — rileykim has 8 net-new pairs (en-ru, en-ko, en-vi, en-id, en-ur, en-uz, en-kk, en-zh-tw). Not adopted in v0.1.4 to avoid widening blast radius. v0.1.5 candidate.
- **DocHPLT (2025) document-level translations** — investigate as additional source.
