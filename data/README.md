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

## v0.1 sample status

The v0.1 release ships 5 sample documents with synthesized layouts and certified-style reference translations as a smoke test. The full 200-document dataset is being curated and will be released in stages. Each batch will:

- Be human-translated by native speakers
- Carry per-document licenses
- Include source page images redistributable under CC-BY-4.0 or compatible

If you would like to contribute documents (especially in underrepresented categories like handwritten / certificates / non-Latin scripts), see `docs/submission.md`.

## License

The annotations and manifest are CC-BY-4.0 unless a stricter per-document license is recorded in the manifest.
