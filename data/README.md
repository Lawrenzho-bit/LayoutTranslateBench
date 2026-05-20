# LayoutTranslateBench Dataset

This directory holds the LTB dataset: the manifest, ground-truth annotations, and source page images.

## Layout

```
data/
├── manifest.json                      # Index of all documents (one entry per doc_id)
├── annotations/                       # Author-curated annotations (v0.1, v0.1.3)
├── sources/                           # Author-rendered page PNGs (v0.1, v0.1.3)
└── rileykim_derived/                  # v0.1.4 expansion (Apache-2.0 source)
    ├── annotations/                   # Annotations derived from rileykim/multilingual-document
    └── sources/                       # Real-world OCR'd document images (downsampled <=1600px)
```

## Manifest schema

See `ltbench.schemas.Manifest`. Each entry contains a `doc_id`, `category`, paths to the source and annotation files, the page size, a per-document license, and an optional source URL.

## Annotation schema

See `ltbench.schemas.Annotation`. Each annotation lists text regions with bounding boxes, the source text, a reading-order index, layout class, optional style hints, and reference translations for every supported language pair.

## Dataset status by version

### v0.1 — 5 sample documents (initial release)
- doc_001 — Certificate of Birth (certificate)
- doc_002 — Sunny Beans Coffee receipt (receipt-invoice)
- doc_003 — Scientific paper page (scientific-paper)
- doc_004 — Acme Industries business letter (business-letter)
- doc_005 — Q1 planning meeting notes, handwritten style (handwritten-mixed)

### v0.1.3 — 5 additional documents (doubles N)
- doc_006 — USCIS Arrival/Departure record I-94 style (gov-form)
- doc_007 — UK Driving Licence application excerpt (gov-form)
- doc_008 — Clinical Laboratory lipid panel report (scientific-paper, medical sub-class)
- doc_009 — Residential Lease Agreement rent clause (legal-contract)
- doc_010 — Public Health Advisory bilingual government notice (magazine-news, gov-comms sub-class)

All 10 v0.1.3 documents have:
- Source rendered from author-authored text reproducing real-world public-form templates
- Bounding-box annotations across 5–8 text regions per doc
- Reference translations in 8 language pairs (`en-es`, `en-de`, `en-zh`, `en-ar`, `en-ja`, `en-fr`, `en-th`, `en-ms`)

### v0.1.4 — rileykim/multilingual-document expansion (this release)

15 additional documents imported from [`rileykim/multilingual-document`](https://huggingface.co/datasets/rileykim/multilingual-document) (Apache-2.0):
- **8 docs (doc_011–doc_018)** with `en-ja` references
- **7 docs (doc_019–doc_025)** with `en-zh` references (mapped from rileykim's `en-zh-cn`)

These docs differ from v0.1.3 in three ways:
1. **Real-world OCR'd document images** (not author-rendered) — patent documents, ad imagery, multi-column layouts. Stored under `data/rileykim_derived/sources/` at native rileykim resolution (downsampled to ≤1600px wide for repo size).
2. **Real OCR bounding boxes** (not author-drawn rectangles) — `merge_ocr` segments from the source dataset, converted from xyxy to xywh.
3. **Single-pair reference coverage per doc** — each rileykim image was paired with exactly one target language, so doc_011–018 have `en-ja` refs only and doc_019–025 have `en-zh` refs only. They do NOT contain all 8 LTB pairs.

Use case: the v0.1.4 expansion is layout-fidelity / reading-order ground truth on real document images, with reference translations for the two LTB pairs that overlap with rileykim. Use them to stress-test runners on real (not synthetic) document scans. Scoring against rileykim references should be reported with the "ml-curated" provenance caveat — see provenance table below.

### Reference-translation provenance

| Version | Provenance | Quality grade |
|---|---|---|
| v0.1 (docs 001–005) | Author-curated | Comparable to a competent native-speaker non-professional translator |
| v0.1.3 (docs 006–010) | Author-curated, same standard as v0.1 | Same as above |
| **v0.1.4 (docs 011–025)** | **rileykim/multilingual-document, Apache-2.0** | **ml-curated** (ML-system output published as references; lower than author-curated for stylistic fluency, but real-world image source) |
| v0.2 (target Q3 2026) | Certified-translator, 2 references per pair | Industry-grade |

References on docs 001–010 are **not certified-translator outputs**. References on docs 011–025 are **ml-curated** (provenance recorded in each annotation file's `provenance` block). Results computed against them should be reported with the appropriate caveat. v0.2 will introduce certified translations once the dataset-curation budget is secured (~€10–25k; see `docs/methodology-roadmap.md`).

### Why these 5 new docs

The v0.1.3 expansion specifically targets the launch-market verticals identified in the broader project strategy:

| Doc | Vertical | Market relevance |
|---|---|---|
| doc_006 USCIS I-94 | Immigration paperwork | US market entry; also de facto template for many world airports |
| doc_007 UK Driving Licence | Government identity documents | UK + EU market entry |
| doc_008 Lab Report | Medical / HIPAA-style records | DE / FR / US healthcare verticals |
| doc_009 Lease Clause | Legal / sworn translation | DE + FR sworn-translation industries (the launch-market wedge) |
| doc_010 Public Health Notice | Government public communications | SG / SE Asia bilingual government materials |

If you would like to contribute documents (especially in underrepresented categories like handwritten / certificates / non-Latin scripts), see `docs/submission.md`.

## License

The annotations and manifest are CC-BY-4.0 unless a stricter per-document license is recorded in the manifest.
