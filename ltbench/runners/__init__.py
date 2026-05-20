"""Runner adapters that wrap a translation system to produce LTB-format submissions."""

from ltbench.runners.base import Runner
from ltbench.runners.identity import IdentityRunner

__all__ = [
    "Runner",
    "IdentityRunner",
    "get_qwen_vl_runner",
    "get_deepl_text_runner",
    "get_florence_nllb_runner",
    "get_nllb_text_runner",
    "get_opus_mt_text_runner",
]


def get_qwen_vl_runner(**kwargs):
    """Lazy import so the heavy deps (torch, transformers) are only loaded when used."""
    from ltbench.runners.qwen_vl import QwenVLRunner

    return QwenVLRunner(**kwargs)


def get_deepl_text_runner(**kwargs):
    """Lazy import so httpx is only required when the runner is actually used."""
    from ltbench.runners.deepl_text import DeepLTextRunner

    return DeepLTextRunner(**kwargs)


def get_florence_nllb_runner(**kwargs):
    """Lazy import so torch + transformers are only loaded when used.

    NOTE: Florence-2 has a transformers-5.x compatibility issue
    (TokenizersBackend.additional_special_tokens AttributeError). Deferred
    to v0.2 pending a fix; use nllb-text-oracle in the meantime.
    """
    from ltbench.runners.florence_nllb import FlorenceNllbRunner

    return FlorenceNllbRunner(**kwargs)


def get_nllb_text_runner(**kwargs):
    """Lazy import so heavy deps are only loaded when used."""
    from ltbench.runners.nllb_text import NllbTextRunner

    return NllbTextRunner(**kwargs)


def get_opus_mt_text_runner(**kwargs):
    """Lazy import so transformers + torch are only loaded when used.

    Helsinki-NLP/opus-mt-* per-pair MT models. Apache-2.0 (mostly) — the
    commercial-safe open-source MT entry on the leaderboard. Covers all
    16 LTB pairs via 13 distinct models with prefix-token routing for
    multi-target heads (en-th, en-ms, en-uz, en-kk, en-zh-tw).
    """
    from ltbench.runners.opus_mt_text import OpusMtTextRunner

    return OpusMtTextRunner(**kwargs)
