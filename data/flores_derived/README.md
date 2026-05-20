# FLORES-200-Derived LTB Documents (v0.1.5 + v0.1.7 enrichment)

This directory contains **10 synthetic LTB documents (doc_026–doc_035)** composed from FLORES-200 devtest sentences. These are the **first industry-grade-reference documents in LTB** — references are professionally translated, recorded as `provenance.grade: "certified-translator"`.

**v0.1.7 update:** every region now carries references for all **16 LTB pairs**. The original v0.1.5 build covered the core 8; `scripts/add_flores_extension_refs.py` back-filled the v0.1.6 extension 8 (`en-ru`, `en-ko`, `en-vi`, `en-id`, `en-ur`, `en-uz`, `en-kk`, `en-zh-tw`) by matching English region text to `eng_Latn.devtest` and looking up the parallel translation in each extension-pair FLORES file. This closes the `en-ru = 0 docs` gap from v0.1.6.4 and upgrades all 7 surviving extension pairs from ml-curated rileykim refs to certified-translator FLORES refs.

## Why these documents matter

The methodology critique (see `docs/methodology-roadmap.md`) flagged author-curated references as the largest quality limitation of LTB v0.1.x. The v0.2 target was to commission certified translators at ~€10–25k. **The FLORES-200 integration partially closes this gap without budget**: 10 docs × 8 LTB pairs × ~5 sentences/doc = ~400 certified-translator reference strings, *free*.

## What's here

- `annotations/doc_026.json` … `doc_035.json` — one annotation per doc, with FLORES-200 translations attached as references in all 8 LTB pairs
- `sources/doc_026.png` … `doc_035.png` — synthetic layouts rendered via `scripts/compose_flores_docs.py` (single-column, title + 4-5 paragraph regions)
- `LICENSE` — CC-BY-SA-4.0 (required by FLORES-200's share-alike clause)

## How they were composed

Each doc is built from one Wikinews article in FLORES-200's devtest split:
1. Group all 1012 devtest sentences by source article URL (`metadata_devtest.tsv`)
2. Pick the first 10 articles with ≥ 5 consecutive sentences
3. Take the first ≤ 6 sentences as document regions: sentence 0 becomes the title, sentences 1–5 become paragraphs
4. Layout: single-column, top-down, author-determined bboxes
5. References: pull the parallel FLORES-200 translations for all 16 LTB target languages — core 8 (`spa_Latn`, `deu_Latn`, `zho_Hans`, `arb_Arab`, `jpn_Jpan`, `fra_Latn`, `tha_Thai`, `zsm_Latn`) and v0.1.6 extension 8 (`rus_Cyrl`, `kor_Hang`, `vie_Latn`, `ind_Latn`, `urd_Arab`, `uzn_Latn`, `kaz_Cyrl`, `zho_Hant`)

## License segregation

Files in this directory are **CC-BY-SA-4.0** (share-alike) because FLORES-200 is share-alike. The rest of LTB (core annotations under `data/annotations/`, rileykim expansion under `data/rileykim_derived/`) remains under its own licenses (CC-BY-4.0, Apache-2.0).

Downstream users who redistribute these specific files must keep them under CC-BY-SA-4.0. The per-document license is also recorded in `data/manifest.json` for each entry.

## Topics covered

| doc_id | Article topic | Wikinews URL fragment |
|---|---|---|
| doc_026 | business | Amazon_to_buy_smart_doorbell |
| doc_027 | science | Scientists_find_dinosaur_feather |
| doc_028 | politics | Iraq_Study_Group_Report |
| doc_029 | research | Dark_matter_lacks_extra_gravita |
| doc_030 | health | Extremely_drug-resistant_tuberc |
| doc_031 | space | Burning_debris_from_satellites |
| doc_032 | crime & law | Doctor_to_be_charged_after_moth |
| doc_033 | health | India_struggles_with_encephalit |
| doc_034 | culture | Noted_stamp_engraver_Czeslaw_Sl |
| doc_035 | accident | Crossing_guard_killed_by_truck |

Diverse topics ensure no single subject dominates — important for averaging chrF/COMET across categories.

## Reproducing the build

```bash
# 1. Download FLORES-200 (~25MB)
mkdir -p .flores-tmp && cd .flores-tmp
curl -sL -o flores200_dataset.tar.gz \
    https://dl.fbaipublicfiles.com/nllb/flores200_dataset.tar.gz
tar xzf flores200_dataset.tar.gz
cd ..

# 2. Compose docs
python scripts/compose_flores_docs.py --max-docs 10 --start-doc-id 26
```

The composer is deterministic — given the same FLORES release and metadata, it produces the same doc_026–doc_035 every time.
