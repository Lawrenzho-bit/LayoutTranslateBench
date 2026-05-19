"""COMET-Kiwi-22 neural text metric (optional, requires unbabel-comet).

Addresses methodology critique #3: chrF rewards character n-gram overlap and is
blind to paraphrase / adequacy. COMET-Kiwi-22 is a reference-free neural
quality estimator (Unbabel) that correlates with human judgment ~2× better
than chrF on WMT shared tasks.

This metric is OPTIONAL. The main `ltbench` package does not require
`unbabel-comet` because it has heavy dependencies (torch + pytorch-lightning +
scipy + numpy>=2) that conflict with `opencv-contrib-python` on some
development environments (notably Windows + numpy 1.26 pin).

Recommended workflow (see also docs/methodology-roadmap.md):

    python -m venv .comet-env
    .comet-env\\Scripts\\activate     # Windows
    # or: source .comet-env/bin/activate    # macOS / Linux
    pip install unbabel-comet
    pip install -e .

    ltbench score --submission submissions/<system> \\
                  --text-metric comet-kiwi \\
                  --output results/<system>.comet.json

Model: Unbabel/wmt22-cometkiwi-da (~600 MB, downloads on first use to
HuggingFace cache). Reference-FREE — only needs source + hypothesis.
Returns scores in [0, 1]; this module scales them to [0, 100] for
compatibility with chrF in the LTB-100 composite.
"""

from __future__ import annotations

import os
from functools import lru_cache

DEFAULT_COMET_MODEL = "Unbabel/wmt22-cometkiwi-da"


def _comet_model_id() -> str:
    return os.environ.get("LTB_COMET_MODEL", DEFAULT_COMET_MODEL)


@lru_cache(maxsize=1)
def _load_comet():
    """Load and cache the COMET-Kiwi model. Returns the loaded model object.

    Raises ImportError if `unbabel-comet` is not installed (with a pointer
    to the clean-venv workaround).
    """
    try:
        from comet import download_model, load_from_checkpoint
    except ImportError as e:
        raise ImportError(
            "COMET-Kiwi is enabled (--text-metric comet-kiwi) but `unbabel-comet` "
            "is not installed in this Python environment. The package conflicts "
            "with some other heavy deps; install it in a clean venv:\n\n"
            "    python -m venv .comet-env\n"
            "    .comet-env\\Scripts\\activate    # Windows\n"
            "    pip install unbabel-comet\n"
            "    pip install -e .\n\n"
            "Then re-run ltbench from inside the venv."
        ) from e

    model_id = _comet_model_id()
    checkpoint_path = download_model(model_id)
    return load_from_checkpoint(checkpoint_path)


def score_batch(sources: list[str], hypotheses: list[str], batch_size: int = 8) -> list[float]:
    """Score a batch of (source, hypothesis) pairs with COMET-Kiwi.

    Returns a list of scores in [0, 100], one per (source, hypothesis) pair,
    suitable for direct substitution wherever chrF [0, 100] is used.

    COMET-Kiwi natively returns [0, 1]; this function multiplies by 100.

    Args:
        sources: list of source-language strings (English for LTB).
        hypotheses: list of predicted target-language strings, same length.
        batch_size: COMET inference batch size. Default 8; reduce on low-RAM
            machines.

    Returns:
        List of float scores in [0, 100], same length as input.
    """
    if len(sources) != len(hypotheses):
        raise ValueError(
            f"sources ({len(sources)}) and hypotheses ({len(hypotheses)}) must be same length"
        )
    if not sources:
        return []

    model = _load_comet()
    data = [{"src": s, "mt": h} for s, h in zip(sources, hypotheses)]
    # gpus=0 forces CPU; remove to use GPU if available
    output = model.predict(data, batch_size=batch_size, gpus=0, progress_bar=False)
    # Output.scores is a list of floats in [0, 1]
    return [float(s) * 100.0 for s in output.scores]


def score_one(source: str, hypothesis: str) -> float:
    """Convenience: score a single (source, hypothesis) pair. Returns [0, 100]."""
    return score_batch([source], [hypothesis])[0]
