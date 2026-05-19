"""Runner adapters that wrap a translation system to produce LTB-format submissions."""

from ltbench.runners.base import Runner
from ltbench.runners.identity import IdentityRunner

__all__ = [
    "Runner",
    "IdentityRunner",
    "get_qwen_vl_runner",
    "get_deepl_text_runner",
]


def get_qwen_vl_runner(**kwargs):
    """Lazy import so the heavy deps (torch, transformers) are only loaded when used."""
    from ltbench.runners.qwen_vl import QwenVLRunner

    return QwenVLRunner(**kwargs)


def get_deepl_text_runner(**kwargs):
    """Lazy import so httpx is only required when the runner is actually used."""
    from ltbench.runners.deepl_text import DeepLTextRunner

    return DeepLTextRunner(**kwargs)
