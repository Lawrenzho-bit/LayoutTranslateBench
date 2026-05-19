"""LayoutTranslateBench — benchmark for document translation with layout preservation."""

__version__ = "0.1.0"

LANG_PAIRS: tuple[str, ...] = (
    "en-es",  # Spanish — Latin script, US/LATAM volume, EU adjacency
    "en-de",  # German — text-expansion stress (~30% longer), DACH market
    "en-zh",  # Simplified Chinese — script change + contraction, hub markets
    "en-ar",  # Arabic — RTL stress test
    "en-ja",  # Japanese — mixed scripts
    "en-fr",  # French — added v0.1: France launch market, DeepL-supported
    "en-th",  # Thai — added v0.1: SEA niche, NOT supported by DeepL
    "en-ms",  # Malay — added v0.1: ASEAN hub + Indonesian adjacency, NOT supported by DeepL
)

LTB_WEIGHTS_V01: dict[str, float] = {
    "chrf": 0.50,
    "layout_iou": 0.30,
    "reading_order_tau": 0.20,
}
