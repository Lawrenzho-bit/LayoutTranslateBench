"""Render the 5 sample documents to PNGs from their JSON annotations.

For each annotation under data/annotations/, draws each text region at its
bounding box, picking a sensible font from Windows' built-in fonts based on
the style hint. Output goes to data/sources/<doc_id>.png.

This is what vision-language model runners (and any human inspector) consume
as the *source* image. The annotations are still the ground truth for scoring;
the PNG is just the rendered visual layer.

Run from repo root:
    python scripts/render_samples.py
or via the CLI:
    ltbench render
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw, ImageFont


# Map (font_family, bold, italic) -> candidate font paths (first existing wins)
_FONT_CANDIDATES: dict[tuple[str, bool, bool], list[str]] = {
    ("serif", False, False): [
        r"C:\Windows\Fonts\times.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
    ],
    ("serif", True, False): [
        r"C:\Windows\Fonts\timesbd.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
    ],
    ("serif", False, True): [
        r"C:\Windows\Fonts\timesi.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Italic.ttf",
    ],
    ("serif", True, True): [
        r"C:\Windows\Fonts\timesbi.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif-BoldItalic.ttf",
    ],
    ("sans", False, False): [
        r"C:\Windows\Fonts\arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ],
    ("sans", True, False): [
        r"C:\Windows\Fonts\arialbd.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ],
    ("sans", False, True): [
        r"C:\Windows\Fonts\ariali.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf",
    ],
    ("sans", True, True): [
        r"C:\Windows\Fonts\arialbi.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-BoldOblique.ttf",
    ],
    ("mono", False, False): [
        r"C:\Windows\Fonts\consola.ttf",
        r"C:\Windows\Fonts\cour.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    ],
    ("mono", True, False): [
        r"C:\Windows\Fonts\consolab.ttf",
        r"C:\Windows\Fonts\courbd.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
    ],
    ("handwritten", False, False): [
        r"C:\Windows\Fonts\seguisc.ttf",
        r"C:\Windows\Fonts\segoesc.ttf",
        r"C:\Windows\Fonts\comic.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ],
    ("decorative", False, False): [
        r"C:\Windows\Fonts\GIL_____.TTF",
        r"C:\Windows\Fonts\arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ],
}

_FONT_CACHE: dict[tuple[str, bool, bool, int], ImageFont.FreeTypeFont] = {}


def _pick_font(family: str, size: int, bold: bool, italic: bool) -> ImageFont.FreeTypeFont:
    """Choose a font that exists on disk, falling back to PIL default."""
    cache_key = (family, bold, italic, size)
    if cache_key in _FONT_CACHE:
        return _FONT_CACHE[cache_key]

    candidates = _FONT_CANDIDATES.get((family, bold, italic), [])
    if not candidates:
        candidates = _FONT_CANDIDATES.get((family, False, False), [])
    if not candidates:
        candidates = _FONT_CANDIDATES.get(("sans", False, False), [])

    for path in candidates:
        if Path(path).exists():
            font = ImageFont.truetype(path, size=size)
            _FONT_CACHE[cache_key] = font
            return font

    font = ImageFont.load_default()  # ugly bitmap fallback
    _FONT_CACHE[cache_key] = font  # type: ignore[assignment]
    return font  # type: ignore[return-value]


def _hex_to_rgb(hex_color: str | None, default: tuple[int, int, int]) -> tuple[int, int, int]:
    if not hex_color:
        return default
    hex_color = hex_color.lstrip("#")
    if len(hex_color) != 6:
        return default
    try:
        return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]
    except ValueError:
        return default


def render_annotation(annotation_path: Path, output_path: Path) -> None:
    """Render one annotation JSON to a PNG."""
    with annotation_path.open("r", encoding="utf-8") as f:
        ann = json.load(f)

    page_w, page_h = ann["page_size"]
    img = Image.new("RGB", (int(page_w), int(page_h)), color="white")
    draw = ImageDraw.Draw(img)

    for region in ann["regions"]:
        x, y, w, h = region["bbox"]
        style = region.get("style", {})
        family = style.get("font_family", "sans")
        size_hint = int(style.get("size_hint") or 16)
        bold = bool(style.get("bold", False))
        italic = bool(style.get("italic", False))
        color = _hex_to_rgb(style.get("color"), (0, 0, 0))
        background = style.get("background")

        # Fill background if specified
        if background:
            bg = _hex_to_rgb(background, (255, 255, 255))
            draw.rectangle((x, y, x + w, y + h), fill=bg)

        font = _pick_font(family, size_hint, bold, italic)
        text = region["text"]

        # Anchor to top-left of the bbox; if text would overflow vertically,
        # let it spill — the bbox is a hint, not a clip.
        draw.text((x, y), text, fill=color, font=font)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, format="PNG", optimize=True)


def render_all(
    manifest_path: Path = Path("data/manifest.json"),
    data_root: Path = Path("data"),
) -> Iterable[Path]:
    """Render every document in the manifest. Yields output paths."""
    with manifest_path.open("r", encoding="utf-8") as f:
        manifest = json.load(f)

    for entry in manifest["entries"]:
        ann_path = data_root / entry["annotation_file"]
        out_path = data_root / entry["source_file"]
        render_annotation(ann_path, out_path)
        yield out_path


def main() -> int:
    count = 0
    for path in render_all():
        print(f"  rendered  {path}")
        count += 1
    print(f"Done — {count} PNG(s) written.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
