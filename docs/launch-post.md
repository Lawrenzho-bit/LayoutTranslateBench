# Launch post draft

Working drafts for the launch posts. Tone: honest, specific, no hype. The pattern that wins on HN/Reddit/X for benchmarks: clear problem, clear methodology, clear limitations, useful link.

---

## Hacker News — "Show HN" title

**Show HN: LayoutTranslateBench – a benchmark for translating documents without wrecking the layout**

### HN body

Most document translation tools today (DeepL Documents, Google Translate documents, ChatGPT vision, Adobe) translate the text well but destroy the layout — multi-column papers flatten, certificate stamps disappear, RTL output gets mangled. There's no public benchmark for "how badly did it destroy the layout," so there's no incentive for vendors to fix it.

I built LayoutTranslateBench (LTB) as a small open-source attempt at that benchmark. It scores three things jointly:

- **chrF** for translation quality (character-level F-score, robust across scripts)
- **Layout IoU** — does the translated text end up in the same regions of the page?
- **Reading-order Kendall τ** — is the order of regions preserved?

Combined into a single composite, LTB-100 = 100 × (0.5 · chrF/100 + 0.3 · IoU + 0.2 · τ). The identity baseline (returns source text unchanged) scores 62.05 — that's the floor any real translator must beat, because it gets full credit for layout and reading order while contributing nothing on text.

v0.1 ships 5 sample documents across categories (certificate, receipt, scientific paper, business letter, handwritten notes), 5 language pairs (en-es, en-de, en-zh, en-ar, en-ja), full scoring infrastructure, and a static leaderboard. The full 200-document curation with certified human translations is in progress; contributions welcome.

Honest limitations:

- Only 5 sample docs in v0.1; full release pending human-translation curation
- No visual fidelity (LPIPS) or OCR round-trip metrics yet — that's v0.2
- No closed-source benchmarks behind this yet — we wanted the scoring infrastructure public from day 1

Code: Apache-2.0. Dataset: CC-BY-4.0. No paywall, no API gate.

Link: <github URL>

Would especially appreciate feedback on the methodology (`docs/methodology.md`) before the held-out split lands.

---

## r/MachineLearning — "[R] / [P]" post

**Title:** `[P] LayoutTranslateBench — open benchmark for document translation that scores layout & reading order`

**Body:**

Sharing a small open project: a benchmark for translating documents (PDFs, scans, certificates, slides) where the output preserves the source layout.

WMT scores text-only translation. OmniDocBench scores extraction/parsing. There wasn't a public benchmark scoring the *intersection* — translation quality conditional on layout preservation — so I built one.

Three metrics:
- chrF₂ for text
- bbox IoU for layout
- normalized Kendall τ for reading order

One composite (LTB-100, weighted 50/30/20). Pydantic-typed schemas, pure-Python scoring (no heavyweight ML deps in the scoring path), CI-runnable, static leaderboard.

Sample dataset has 5 documents × 5 language pairs (en-es, en-de, en-zh, en-ar, en-ja) with certified-style references. Full 200-doc dataset is in human-translation curation; contributions welcome (especially in handwritten / non-Latin source categories).

Code Apache-2.0, data CC-BY-4.0. Identity-baseline result: LTB-100 = 62.05 (floor).

Repo: <github URL>
Spec: <github URL>/blob/main/BENCHMARK.md
Methodology: <github URL>/blob/main/docs/methodology.md

Specific feedback I'd want:
- Is character-level F (chrF₂) the right text metric here, or should we adopt MetricX / COMET-Kiwi (and accept the GPU dep)?
- Greedy IoU region matching vs Hungarian assignment — does it matter at this scale?
- For v0.2, is LPIPS the right visual-fidelity choice, or is SSIM on non-text masks sufficient?

---

## X / Twitter thread

1/ Shipping a small open benchmark today: **LayoutTranslateBench (LTB)**.

Why? Every document-translation tool (DeepL, Google Translate, ChatGPT vision) translates the text fine — and wrecks the layout. There was no public benchmark scoring "how badly did you wreck the layout." So I built one. Code Apache-2.0, data CC-BY-4.0.

2/ Three metrics, one composite:
• chrF₂ (text quality)
• bbox IoU (layout fidelity)
• Kendall τ (reading order preservation)

LTB-100 = 100 × (0.5·chrF/100 + 0.3·IoU + 0.2·τ). Identity baseline scores 62.05 — that's the floor.

3/ v0.1 ships:
• 5 sample documents × 5 language pairs (en-es, en-de, en-zh, en-ar, en-ja)
• Full scoring pipeline (pure Python, CPU-only)
• Static leaderboard
• 20 unit tests, all passing
• Held-out split design for anti-overfit

4/ What's not in v0.1:
• Full 200-doc dataset (human-translation curation in progress)
• Visual fidelity (LPIPS) and OCR round-trip metrics — those land in v0.2

Want a runner adapter? PRs welcome at <github URL>.

5/ Why open everything?

The benchmark category in 2026 has heavy LLM citation traffic. Whoever owns the metric people quote owns the category. The product comes later — the benchmark *is* the wedge.

<github URL>

---

## Tips for execution

- Post HN on a weekday morning US-Eastern. Avoid Mondays (overloaded) and Fridays (light).
- Post Reddit r/MachineLearning concurrent or +1 day; mention HN cross-post in a comment, not the body.
- X thread posts after first HN traction (don't double-launch cold).
- Reply to every HN comment within first 4 hours; treat criticism as gifts, never argue.
- Be transparent about the 5-doc dataset size in the opening of every post.
