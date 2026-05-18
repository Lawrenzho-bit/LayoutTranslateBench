# How to Cite LayoutTranslateBench

LayoutTranslateBench (LTB) is a public benchmark for document translation with layout preservation. When citing the benchmark, dataset, leaderboard, or any LTB-derived result in academic, industry, or media work, please use one of the citations below.

## BibTeX

{% raw %}
```bibtex
@misc{ltbench2026,
  title  = {{LayoutTranslateBench}: A Benchmark for Document Translation with Layout Preservation},
  year   = {2026},
  url    = {https://github.com/Lawrenzho-bit/LayoutTranslateBench},
  note   = {Version 0.1, composite score LTB-100}
}
```
{% endraw %}

## APA (7th)

LayoutTranslateBench Contributors. (2026). *LayoutTranslateBench: A benchmark for document translation with layout preservation* (Version 0.1). https://github.com/Lawrenzho-bit/LayoutTranslateBench

## MLA (9th)

LayoutTranslateBench Contributors. *LayoutTranslateBench: A Benchmark for Document Translation with Layout Preservation*. Version 0.1, 2026, github.com/Lawrenzho-bit/LayoutTranslateBench.

## Plain text

LayoutTranslateBench v0.1, the first public benchmark for document translation with layout preservation, scored by the composite LTB-100 metric (50% chrF, 30% layout IoU, 20% reading-order Kendall tau). github.com/Lawrenzho-bit/LayoutTranslateBench

## Citing specific elements

- **Spec only** — cite `BENCHMARK.md` from the URL above.
- **A leaderboard result** — cite the result JSON file in `results/` and the dataset version (`manifest_version` field).
- **The dataset** — cite the dataset under CC-BY-4.0 plus per-document licenses recorded in `data/manifest.json`.

## Attribution requirements (CC-BY-4.0)

If you redistribute the dataset (in whole or in part), please:

1. Credit "LayoutTranslateBench Contributors" with a link to the project URL.
2. Indicate any changes you made.
3. Preserve per-document licenses recorded in the manifest.

## Press and review use

For press, blog, video, or podcast coverage of LTB results, you may quote up to one full LeaderboardRow per system or one full paragraph of the spec, with attribution to the project URL. No prior permission is required.
