"""Language-detection guard for text-quality metrics.

Addresses a methodology issue in v0.1: chrF rewards character-n-gram overlap
regardless of whether the output is in the *target language*. Identity-baseline
returns English text, yet scores ~24 chrF on Latin-script targets due to
character bleed-through (proper nouns, numbers, dates, Latin punctuation).

This module provides a language-detection check that should be applied as a
gate to chrF: if the predicted text is not in the target language, chrF is
forced to 0. The check is intentionally permissive (short strings, mostly
numeric/symbolic strings, and detection failures all default to PASS) so the
penalty is only applied to confident-wrong-language predictions.

Mapping uses langdetect's ISO-639 codes; Malay (ms) and Indonesian (id) are
treated as equivalent because they are mutually intelligible and langdetect
cannot reliably distinguish them on short strings.
"""

from __future__ import annotations

# Map LTB language-pair code -> set of acceptable langdetect target codes.
# Each set contains all codes that should be considered "in target language"
# for that pair.
_TARGET_CODES: dict[str, frozenset[str]] = {
    "en-es": frozenset({"es"}),
    "en-de": frozenset({"de"}),
    "en-zh": frozenset({"zh-cn", "zh-tw"}),
    "en-ar": frozenset({"ar"}),
    "en-ja": frozenset({"ja"}),
    "en-fr": frozenset({"fr"}),
    "en-th": frozenset({"th"}),
    "en-ms": frozenset({"ms", "id"}),  # Malay / Indonesian are mutually intelligible
}


# Unicode-block pre-filter. For short non-Latin strings, langdetect can confuse
# Chinese ↔ Korean ↔ Japanese (all share CJK Unified Ideographs) or fail entirely.
# If a significant fraction of the text's alphabetic characters falls in the
# expected script block for the target language, we accept the prediction even
# if langdetect picks a different code. Each entry is a tuple of code-point
# ranges (inclusive) considered "script-correct" for the pair.
_SCRIPT_RANGES: dict[str, list[tuple[int, int]]] = {
    "en-zh": [
        (0x4E00, 0x9FFF),  # CJK Unified Ideographs
        (0x3400, 0x4DBF),  # CJK Unified Ideographs Extension A
        (0x20000, 0x2A6DF),  # CJK Unified Ideographs Extension B
    ],
    "en-ja": [
        (0x3040, 0x309F),  # Hiragana
        (0x30A0, 0x30FF),  # Katakana
        (0x4E00, 0x9FFF),  # CJK Unified Ideographs (kanji)
        (0xFF66, 0xFF9F),  # Halfwidth Katakana
    ],
    "en-ar": [
        (0x0600, 0x06FF),  # Arabic
        (0x0750, 0x077F),  # Arabic Supplement
        (0x08A0, 0x08FF),  # Arabic Extended-A
        (0xFB50, 0xFDFF),  # Arabic Presentation Forms-A
        (0xFE70, 0xFEFF),  # Arabic Presentation Forms-B
    ],
    "en-th": [
        (0x0E00, 0x0E7F),  # Thai
    ],
}

_SCRIPT_MIN_FRACTION = 0.5  # at least half of alpha chars in target script


_MIN_ALPHA_CHARS = 4  # below this, language detection is unreliable


def _script_match_fraction(text: str, target_pair: str) -> float | None:
    """Fraction of alphabetic chars in `text` that fall in the target script block.

    Returns None for pairs without a defined script block (i.e. Latin-script
    targets — for those we rely on langdetect).
    """
    ranges = _SCRIPT_RANGES.get(target_pair)
    if not ranges:
        return None
    n_alpha = 0
    n_match = 0
    for ch in text:
        if not ch.isalpha():
            continue
        n_alpha += 1
        cp = ord(ch)
        for low, high in ranges:
            if low <= cp <= high:
                n_match += 1
                break
    if n_alpha == 0:
        return None
    return n_match / n_alpha


def is_target_language(text: str, target_pair: str) -> bool:
    """Return True iff `text` is plausibly in the target language for `target_pair`.

    Permissive: short strings, mostly numeric/symbolic strings, and detection
    failures all return True (i.e. give the predicted text the benefit of the
    doubt). The penalty is only applied to confident-wrong-language predictions
    (e.g. English text submitted for a Spanish target).
    """
    if not text:
        return True

    accepted = _TARGET_CODES.get(target_pair)
    if accepted is None:
        # Unknown target — fail open
        return True

    # Strip non-alphabetic; if the remaining text is too short, give up
    clean = "".join(c for c in text if c.isalpha() or c.isspace()).strip()
    if len(clean) < _MIN_ALPHA_CHARS:
        return True

    # Script-based pre-filter for non-Latin targets. langdetect can confuse
    # short CJK strings as Korean, Japanese as Chinese, etc. Counting
    # script-block characters directly is more robust.
    script_fraction = _script_match_fraction(text, target_pair)
    if script_fraction is not None and script_fraction >= _SCRIPT_MIN_FRACTION:
        return True
    if script_fraction is not None and script_fraction < _SCRIPT_MIN_FRACTION:
        # Text is in the wrong script for this target — confidently reject
        # without consulting langdetect.
        return False

    # Latin-script targets fall through to langdetect.
    try:
        from langdetect import DetectorFactory, detect

        # Determinism — langdetect uses random seeding by default
        DetectorFactory.seed = 42
        detected = detect(text)
        return detected in accepted
    except Exception:
        # langdetect not installed, or detection failed — fail open
        return True


def chrf_with_lang_check(
    hypothesis: str,
    reference: str,
    target_pair: str,
    n: int = 6,
    beta: float = 2.0,
) -> float:
    """chrF with a language-detection gate.

    Returns 0.0 if `hypothesis` is confidently not in the target language;
    otherwise returns the standard chrF score. Wraps `ltbench.metrics.text.chrf`.
    """
    from ltbench.metrics.text import chrf

    if not is_target_language(hypothesis, target_pair):
        return 0.0
    return chrf(hypothesis, reference, n=n, beta=beta)
