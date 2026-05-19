# LayoutTranslateBench Dataset

This directory holds the LTB dataset: the manifest, ground-truth annotations, and a placeholder for source page images.

## Layout

```
data/
├── manifest.json         # Index of all documents (one entry per doc_id)
├── annotations/          # One JSON per document, ground-truth bboxes + references
└── sources/              # Page images (PDF/PNG). Large files; not all are redistributable.
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

### v0.1.3 — 5 additional documents (this release, **doubles N**)
- doc_006 — USCIS Arrival/Departure record I-94 style (gov-form)
- doc_007 — UK Driving Licence application excerpt (gov-form)
- doc_008 — Clinical Laboratory lipid panel report (scientific-paper, medical sub-class)
- doc_009 — Residential Lease Agreement rent clause (legal-contract)
- doc_010 — Public Health Advisory bilingual government notice (magazine-news, gov-comms sub-class)

All 10 documents have:
- Source rendered from author-authored text reproducing real-world public-form templates
- Bounding-box annotations across 5–8 text regions per doc
- Reference translations in 8 language pairs (`en-es`, `en-de`, `en-zh`, `en-ar`, `en-ja`, `en-fr`, `en-th`, `en-ms`)

### Reference-translation provenance

| Version | Provenance | Quality grade |
|---|---|---|
| v0.1 (docs 001–005) | Author-curated | Comparable to a competent native-speaker non-professional translator |
| v0.1.3 (docs 006–010) | Author-curated, same standard as v0.1 | Same as above |
| v0.2 (target Q3 2026) | Certified-translator, 2 references per pair | Industry-grade |

References on the current dataset are **not certified-translator outputs**. They are suitable for benchmark development and indicative system comparisons; results computed against them should be reported with the caveat "author-curated references." v0.2 will replace them with certified translations once the dataset-curation budget is secured (~€10–25k; see `docs/methodology-roadmap.md`).

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
