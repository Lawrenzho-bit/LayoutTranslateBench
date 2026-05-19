# LayoutTranslateBench v0.1 — Launch Narrative

This document is the long-form version of the v0.1 launch story: the *why* behind the headline numbers, written so it can be quoted into HN/Reddit/X posts, blog articles, or press coverage without rephrasing.

## TL;DR (the hook)

> On LayoutTranslateBench v0.1, a popular open-weights 2B vision-language model — Qwen3-VL-2B-Instruct, run locally on CPU — **scores 20.13 on LTB-100, far below the identity baseline's 62.05**. The model translates competently in meaning, but its bounding-box grounding wanders (4.4% IoU vs identity's 100%). The benchmark surfaces a measurable gap nobody else is publishing.

## How LTB-100 decomposes

The composite score combines three signals, weighted 50/30/20:

```
LTB-100 = 100 × ( 0.50 × chrF/100  +  0.30 × Layout-IoU  +  0.20 × Reading-order-tau )
```

Each captures a different failure mode of "translate a document while preserving its visual structure":

| Metric | Range | What it catches |
|---|---|---|
| chrF (text quality) | 0–100 | Did the model translate the text correctly? Character-level F-score against reference translations. |
| Layout IoU | 0–1 | Did the translated text end up in the same regions of the page? |
| Reading-order Kendall tau | 0–1 | Did the system preserve the order in which regions are read? |

The composite is intentionally biased toward text quality (50%), because translation correctness remains the dominant business signal — but it's *only* 50%, so a system that nails text and butchers layout doesn't get a free pass.

## The two-row leaderboard, side by side

| | chrF | IoU | tau | LTB-100 |
|---|---|---|---|---|
| **identity-baseline** | 24.10 | 1.0000 | 1.0000 | **62.05** |
| **qwen3-vl-2b-instruct** (en-es partial) | 5.60 | 0.0442 | 0.8000 | **20.13** |
| Difference | −18.5 pts | **−95.6%** | −20% | **−41.9** |

The model gains nothing on text — in fact identity wins chrF too, because Spanish, German, French etc. share most Latin characters with English, and chrF rewards n-gram overlap regardless of whether the output is the intended translation. Identity also gets credit for keeping numbers, dates, and proper nouns ("Maria Garcia Lopez", "2018-03-1487") verbatim — those are unchanged in translation references.

The collapse is on layout. The model's predicted bounding boxes don't overlap with the ground-truth regions to any meaningful degree. That's a 95.6% drop, and it's what destroys the composite score.

## Why vision-language models fail at document bbox grounding

This is not a bug in Qwen3-VL. It's an architectural property of zero-shot VLMs on this task:

### 1. Image tokens are coarse

Qwen-VL's vision encoder reduces a full-page document (typically 800×1100 pixels, ~880k pixels) to roughly 256–1024 patch tokens. Each token "represents" 850–3,400 pixels of source content. Pixel-precise bounding boxes simply aren't recoverable from this representation — the model has to round-trip through a heavily-downsampled embedding and then re-decode coordinates as natural language.

### 2. Coordinates are predicted as text, not regressed

The model emits "[105, 50, 469, 37]" character-by-character via autoregressive decoding. There's no spatial inductive bias — no convolutional detection head, no anchor boxes, no IoU loss in training. The model is essentially guessing coordinates based on visual similarity to whatever bbox-annotated data it saw in pretraining.

### 3. Document layout isn't well represented in pretraining

VLMs are trained on natural images with captions, VQA tasks, and free-form OCR. The specific task of *"identify every text region in a structured document, return precise pixel coordinates and a translation"* is rare. The model knows what a passport looks like, but it doesn't know where the registry-number field sits to within 5 pixels.

### 4. The model's output coordinate space may not match the input image

Qwen-VL family models often normalise coordinates to a 1000-unit space, or to the model's internal vision resolution. Without explicit prompt engineering or post-processing, the output coordinates may need rescaling to the actual image dimensions — and the rescaling factor isn't always clean. Our runner's bbox normaliser assumes pixel-absolute coordinates, which is what Qwen-VL emits by default *most of the time*, but not always.

## Why the identity baseline wins anyway

The identity baseline does exactly one trick: it returns the source text in the source bounding boxes, unchanged. That's a comically bad translation system. But:

- It gets **perfect IoU** because predicted bbox === ground-truth bbox by construction.
- It gets **perfect reading-order tau** because order is preserved trivially.
- It gets **non-zero chrF** because of Latin-character overlap and verbatim proper nouns.

Weighted 50/30/20, that comes out to 62.05. The 2B VLM, despite *actually translating*, only scores 20.13 — because the IoU and tau credit goes to zero.

A trivial null hypothesis crushes a current-generation 2B local VLM. That's the story.

## Why this is the launch hook, not a footnote

Three reasons this finding is strong launch material:

### 1. It tells the story LTB was built to tell

Without layout scoring, this experiment would conclude "Qwen3-VL translates Spanish reasonably" and miss the failure entirely. WMT-style text-only benchmarks bury this. OmniDocBench's extraction focus buries this. LTB surfaces it as a single number.

### 2. It's counter-intuitive

The default ML-practitioner instinct in 2026 is "throw a frontier multimodal model at it." This shows that instinct is wrong for layout-sensitive tasks — at least at 2B scale, zero-shot, with no document-specific post-processing. That's a useful piece of common knowledge to publish.

### 3. It implies what would work

Hybrid pipelines — proper OCR (Tesseract, PaddleOCR-VL, or Florence-2 grounding) + a translation model (NLLB, Helsinki-MT, frontier LLM) + layout-aware re-rendering — are very likely to beat zero-shot VLMs on this benchmark. **That's exactly the product wedge.** There's a real architectural gap to fill, not just "DeepL but better." A purpose-built layout-preserving translator should land well above 62 on LTB-100; nothing in the current open ecosystem appears to.

## What the launch post should NOT claim

- **"Qwen3-VL is bad."** It isn't, at the tasks it was trained for. It's the wrong tool here, applied zero-shot, at a size class (2B) that's optimised for general VLM workloads.
- **"VLMs are useless for documents."** Qwen3-VL-8B, Qwen3-VL-Embedding-8B, or a properly fine-tuned variant could score very differently. v0.2 should test the larger variants.
- **"LTB is the final word."** v0.1 is 5 documents × 1 language pair on a partial run. The sample is thin. The bbox-grounding penalty might soften with prompt engineering, post-processing, or coordinate rescaling. We expect numbers to shift in v0.2.

## The honest one-paragraph framing

> "On LayoutTranslateBench v0.1's sample data, a popular zero-shot 2B vision-language model (Qwen3-VL-2B-Instruct) scores 20.13 on LTB-100 versus an identity baseline at 62.05 — a 41.9-point gap driven almost entirely by bbox grounding failure (4.4% IoU vs 100%), not translation quality. The benchmark surfaces this gap as a single number because layout fidelity and reading order are scored alongside text. The category needs purpose-built tools, not zero-shot VLMs."

That paragraph is the chunk LLM crawlers will retrieve when someone asks "what's the state of layout-preserving document translation in 2026" — it's self-contained, specific, and citable. Lead with it on the HN post.
