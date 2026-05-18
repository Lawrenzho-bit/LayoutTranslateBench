"""LayoutTranslateBench — benchmark for document translation with layout preservation."""

__version__ = "0.1.0"

LANG_PAIRS: tuple[str, ...] = ("en-es", "en-de", "en-zh", "en-ar", "en-ja")

LTB_WEIGHTS_V01: dict[str, float] = {
    "chrf": 0.50,
    "layout_iou": 0.30,
    "reading_order_tau": 0.20,
}
