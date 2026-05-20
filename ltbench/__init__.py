"""LayoutTranslateBench — benchmark for document translation with layout preservation."""

__version__ = "0.1.0"

LANG_PAIRS: tuple[str, ...] = (
    # Core 8 pairs (v0.1) — used by author-curated docs 001–010 and FLORES docs 026–035
    "en-es",  # Spanish — Latin script, US/LATAM volume, EU adjacency
    "en-de",  # German — text-expansion stress (~30% longer), DACH market
    "en-zh",  # Simplified Chinese — script change + contraction, hub markets
    "en-ar",  # Arabic — RTL stress test
    "en-ja",  # Japanese — mixed scripts
    "en-fr",  # French — France launch market, DeepL-supported
    "en-th",  # Thai — SEA niche, NOT supported by DeepL
    "en-ms",  # Malay — ASEAN hub + Indonesian adjacency, NOT supported by DeepL
    # v0.1.6 extension pairs — sourced from rileykim/multilingual-document (Apache-2.0)
    "en-ru",  # Russian — Cyrillic, European market gap (DeepL supports it; many open models too)
    "en-ko",  # Korean — Hangul script, Asian market
    "en-vi",  # Vietnamese — Latin (diacritics), SEA volume
    "en-id",  # Indonesian — Latin, SEA partner to en-ms
    "en-ur",  # Urdu — Perso-Arabic script, South Asian market
    "en-uz",  # Uzbek — Latin (post-2018 reform), Central Asian
    "en-kk",  # Kazakh — Cyrillic, Central Asian
    "en-zh-tw",  # Traditional Chinese — Han script variant, TW/HK market
)

# Subset of LANG_PAIRS that author-curated docs (v0.1, v0.1.3) and FLORES docs
# (v0.1.5) are guaranteed to cover. The v0.1.6 extension pairs are
# rileykim-sourced only and are NOT expected to appear in author-curated /
# certified-translator docs. The verify command uses this set to decide what
# "complete coverage" means for non-rileykim docs.
CORE_LANG_PAIRS: tuple[str, ...] = (
    "en-es",
    "en-de",
    "en-zh",
    "en-ar",
    "en-ja",
    "en-fr",
    "en-th",
    "en-ms",
)

LTB_WEIGHTS_V01: dict[str, float] = {
    "chrf": 0.50,
    "layout_iou": 0.30,
    "reading_order_tau": 0.20,
}
