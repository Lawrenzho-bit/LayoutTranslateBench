"""Helsinki-NLP/opus-mt Text runner — Apache-2.0 oracle-layout baseline.

Why this matters for LTB:
  - NLLB-200 is CC-BY-NC-4.0 (research-only). A product cannot ship it.
  - opus-mt models are mostly Apache-2.0 (with en-de and en-ko on CC-BY-4.0).
    Both license families permit commercial use; this runner is the
    "commercial-safe open-source MT" entry on the leaderboard.
  - Per-pair models (~300MB each) — small, fast on CPU, load-on-demand.

Coverage: all 16 LTB pairs via 14 distinct models. Some pairs use router
models with a `>>lang_code<<` prefix token prepended to the source text:
  - en-th -> opus-mt-en-mul + ">>tha<<"
  - en-ms -> opus-mt-en-poz + ">>zsm_Latn<<"
  - en-uz -> opus-mt-en-trk + ">>uzb_Latn<<"
  - en-kk -> opus-mt-en-trk + ">>kaz_Cyrl<<"
  - en-zh -> opus-mt-en-zh + ">>cmn_Hans<<"
  - en-zh-tw -> opus-mt-en-zh + ">>cmn_Hant<<"
  - en-ar -> opus-mt-en-ar + ">>ara<<" (MSA)

Heavyweight deps (transformers, sentencepiece) are imported lazily.
"""

from __future__ import annotations

import time
from typing import Optional

from ltbench.runners.base import Runner
from ltbench.schemas import (
    Annotation,
    DocumentSubmission,
    LangPair,
    PredictedRegion,
    SystemManifest,
)

# Map LTB language pair -> (HF model id, optional prefix token)
# Prefix token is prepended to each source sentence before tokenization.
_LANG_PAIR_TO_OPUS: dict[LangPair, tuple[str, Optional[str]]] = {
    "en-es": ("Helsinki-NLP/opus-mt-en-es", None),
    "en-de": ("Helsinki-NLP/opus-mt-en-de", None),  # CC-BY-4.0
    "en-zh": ("Helsinki-NLP/opus-mt-en-zh", ">>cmn_Hans<<"),
    "en-ar": ("Helsinki-NLP/opus-mt-en-ar", ">>ara<<"),
    "en-ja": ("Helsinki-NLP/opus-mt-en-jap", None),  # note: 'jap' suffix
    "en-fr": ("Helsinki-NLP/opus-mt-en-fr", None),
    "en-th": ("Helsinki-NLP/opus-mt-en-mul", ">>tha<<"),
    "en-ms": ("Helsinki-NLP/opus-mt-en-poz", ">>zsm_Latn<<"),
    "en-ru": ("Helsinki-NLP/opus-mt-en-ru", None),
    "en-ko": ("Helsinki-NLP/opus-mt-tc-big-en-ko", None),  # CC-BY-4.0
    "en-vi": ("Helsinki-NLP/opus-mt-en-vi", None),
    "en-id": ("Helsinki-NLP/opus-mt-en-id", None),
    "en-ur": ("Helsinki-NLP/opus-mt-en-ur", None),
    "en-uz": ("Helsinki-NLP/opus-mt-en-trk", ">>uzb_Latn<<"),
    "en-kk": ("Helsinki-NLP/opus-mt-en-trk", ">>kaz_Cyrl<<"),
    "en-zh-tw": ("Helsinki-NLP/opus-mt-en-zh", ">>cmn_Hant<<"),
}


class OpusMtTextRunner(Runner):
    """Helsinki-NLP/opus-mt Text + oracle layout.

    For each region in the ground-truth annotation, translates via the
    appropriate opus-mt model and copies the bbox + reading order. Layout is
    given full credit (oracle); only translation quality is measured.

    Models are loaded on demand and cached. Loading 13 models in sequence
    uses ~4GB RAM total; if you only need a subset, scope via --lang-pairs.
    """

    version = "0.1.0"

    def __init__(
        self,
        device: str | None = None,
        max_new_tokens: int = 256,
        num_beams: int = 4,
        batch_size: int = 8,
    ) -> None:
        self.device = device
        self.max_new_tokens = max_new_tokens
        self.num_beams = num_beams
        self.batch_size = batch_size
        self._actual_device: str | None = None
        # Cache: (model_id, prefix_token) -> (tokenizer, model)
        self._model_cache: dict[str, tuple] = {}

    @property
    def name(self) -> str:  # type: ignore[override]
        return "opus-mt-text-oracle"

    def system_manifest(self) -> SystemManifest:
        return SystemManifest(
            system_name=self.name,
            system_version=self.version,
            model_id_or_url="https://huggingface.co/Helsinki-NLP",
            runner_config={
                "max_new_tokens": self.max_new_tokens,
                "num_beams": self.num_beams,
                "batch_size": self.batch_size,
                "oracle_layout": True,
                "covers_th_ms": True,
                "covers_16_pairs": True,
                "commercial_safe": True,  # mostly Apache-2.0; en-de + en-ko are CC-BY-4.0
            },
            hardware=self._actual_device,
            system_type="oracle-layout",
            notes=(
                "Open-source commercial-safe oracle-layout baseline: predicted "
                "bboxes are copied verbatim from the ground-truth annotation; "
                "text is translated by Helsinki-NLP/opus-mt-* per-pair models. "
                "All 16 LTB pairs covered via 14 distinct models. License: "
                "mostly Apache-2.0; en-de and en-ko use CC-BY-4.0 (TC-big). "
                "Both permit commercial use with attribution — this is the "
                "ship-able open-source MT path that NLLB-200 (CC-BY-NC-4.0) "
                "is not."
            ),
        )

    def _ensure_loaded(self) -> None:
        """Trigger the heavyweight imports + set self._actual_device."""
        if self._actual_device is not None:
            return
        try:
            import torch
        except ImportError as e:
            raise RuntimeError(
                "transformers + torch are required for OpusMtTextRunner. "
                'Install with: pip install -e ".[runners-nllb]" (or runners-opus-mt)'
            ) from e
        if self.device is None:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self._actual_device = self.device

    def _get_model(self, lang_pair: LangPair) -> tuple:
        """Return cached (tokenizer, model, prefix) tuple for the pair."""
        entry = _LANG_PAIR_TO_OPUS.get(lang_pair)
        if entry is None:
            raise ValueError(
                f"OpusMtTextRunner has no opus-mt mapping for {lang_pair}"
            )
        model_id, prefix = entry
        key = model_id
        if key in self._model_cache:
            tokenizer, model = self._model_cache[key]
            return tokenizer, model, prefix

        import torch  # noqa: F401
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

        torch_dtype = torch.float32 if self._actual_device == "cpu" else torch.float16
        tokenizer = AutoTokenizer.from_pretrained(model_id)
        model = AutoModelForSeq2SeqLM.from_pretrained(
            model_id, torch_dtype=torch_dtype
        ).to(self._actual_device)
        model.eval()
        self._model_cache[key] = (tokenizer, model)
        return tokenizer, model, prefix

    def _translate_batch(
        self, texts: list[str], lang_pair: LangPair
    ) -> list[str]:
        if not texts:
            return []
        import torch

        tokenizer, model, prefix = self._get_model(lang_pair)
        # Prepend prefix token if the model requires it
        if prefix:
            texts = [f"{prefix} {t}" for t in texts]

        results: list[str] = []
        for start in range(0, len(texts), self.batch_size):
            batch = texts[start : start + self.batch_size]
            inputs = tokenizer(
                batch, return_tensors="pt", padding=True, truncation=True, max_length=512
            )
            if self._actual_device == "cuda":
                inputs = {k: v.cuda() for k, v in inputs.items()}
            with torch.inference_mode():
                out_ids = model.generate(
                    **inputs,
                    max_new_tokens=self.max_new_tokens,
                    num_beams=self.num_beams,
                    do_sample=False,
                )
            results.extend(tokenizer.batch_decode(out_ids, skip_special_tokens=True))
        return results

    def translate(
        self, annotation: Annotation, lang_pair: LangPair
    ) -> DocumentSubmission:
        self._ensure_loaded()
        texts = [r.text for r in annotation.regions]
        t0 = time.time()
        translations = self._translate_batch(texts, lang_pair)
        elapsed = time.time() - t0
        regions = [
            PredictedRegion(
                region_id=gt.region_id,
                bbox=gt.bbox,
                text=translations[i] if i < len(translations) else "",
                reading_order=gt.reading_order,
            )
            for i, gt in enumerate(annotation.regions)
        ]
        return DocumentSubmission(
            doc_id=annotation.doc_id,
            regions=regions,
            runtime_seconds=elapsed,
        )

    def close(self) -> None:
        # Release model handles to free RAM
        self._model_cache.clear()
        try:
            import torch
            if self._actual_device == "cuda":
                torch.cuda.empty_cache()
        except Exception:
            pass
