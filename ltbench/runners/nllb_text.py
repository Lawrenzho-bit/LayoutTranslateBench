"""NLLB-200 Text runner — open-source oracle-layout baseline.

Mirrors the deepl-text-oracle pattern but uses Meta's NLLB-200-distilled-600M
as the translation engine instead of DeepL. Predicted bboxes are copied from
the ground-truth annotation (oracle layout); only the text is translated.

Why this matters for the launch story:
  - It puts open-source MT on the exact same scoring axis as DeepL.
  - If NLLB-200 closes the chrF gap to DeepL, then DeepL's commercial moat
    is small in this benchmark, and an open-source product can match
    proprietary quality.
  - If NLLB-200 falls far short, DeepL's quality lead is meaningful — but
    then the product needs to either pay for DeepL or train its own MT.

NLLB-200 supports all 8 LTB v0.1 pairs natively, including en-th and en-ms
(which DeepL does not support) — so unlike deepl-text-oracle this runner
covers 8/8.

License caveat: NLLB-200-distilled-600M is CC-BY-NC-4.0. Fine for benchmark
/ research use; the product should swap in MADLAD-400 (Apache-2.0) or
Helsinki-NLP/opus-mt-* (CC-BY-4.0) for commercial deployment.

Heavyweight deps (torch, transformers, sentencepiece) are imported lazily.
Install with:

    pip install -e ".[runners-nllb]"
"""

from __future__ import annotations

import os
import time

from ltbench.runners.base import Runner
from ltbench.schemas import (
    Annotation,
    DocumentSubmission,
    LangPair,
    PredictedRegion,
    SystemManifest,
)

DEFAULT_NLLB_MODEL = "facebook/nllb-200-distilled-600M"

# NLLB language codes (BCP-47-style with script). Source: NLLB-200 paper.
# NLLB-200 supports all 200+ languages natively; the mapping below covers
# every LTB pair, including the v0.1.6 extension pairs.
_LANG_PAIR_TO_NLLB: dict[LangPair, str] = {
    # Core 8 (v0.1)
    "en-es": "spa_Latn",
    "en-de": "deu_Latn",
    "en-zh": "zho_Hans",  # Simplified Chinese
    "en-ar": "arb_Arab",  # Modern Standard Arabic
    "en-ja": "jpn_Jpan",
    "en-fr": "fra_Latn",
    "en-th": "tha_Thai",
    "en-ms": "zsm_Latn",  # Standard Malay
    # v0.1.6 extension pairs
    "en-ru": "rus_Cyrl",  # Russian
    "en-ko": "kor_Hang",  # Korean (Hangul)
    "en-vi": "vie_Latn",  # Vietnamese
    "en-id": "ind_Latn",  # Indonesian
    "en-ur": "urd_Arab",  # Urdu
    "en-uz": "uzn_Latn",  # Uzbek (Northern, Latin)
    "en-kk": "kaz_Cyrl",  # Kazakh
    "en-zh-tw": "zho_Hant",  # Traditional Chinese
}


class NllbTextRunner(Runner):
    """NLLB-200 Text + oracle layout.

    For each region in the ground-truth annotation, translates the text via
    NLLB-200 and copies the bbox + reading order verbatim. Layout is given
    full credit (oracle); only translation quality is measured.
    """

    version = "0.1.0"

    def __init__(
        self,
        nllb_model: str | None = None,
        device: str | None = None,
        max_new_tokens: int = 256,
        num_beams: int = 4,
        batch_size: int = 8,
    ) -> None:
        self.nllb_model = nllb_model or os.environ.get("LTB_NLLB_MODEL", DEFAULT_NLLB_MODEL)
        self.device = device
        self.max_new_tokens = max_new_tokens
        self.num_beams = num_beams
        self.batch_size = batch_size
        self._tokenizer = None
        self._model = None
        self._actual_device: str | None = None

    @property
    def name(self) -> str:  # type: ignore[override]  # noqa: F811
        # Fixed short name. The NLLB-200 model ID is recorded separately in
        # model_id_or_url, so no verbose suffix is needed here.
        return "nllb-text-oracle"

    def system_manifest(self) -> SystemManifest:
        return SystemManifest(
            system_name=self.name,
            system_version=self.version,
            model_id_or_url=f"https://huggingface.co/{self.nllb_model}",
            runner_config={
                "max_new_tokens": self.max_new_tokens,
                "num_beams": self.num_beams,
                "batch_size": self.batch_size,
                "oracle_layout": True,
                "covers_th_ms": True,
            },
            hardware=self._actual_device,
            system_type="oracle-layout",
            notes=(
                "Open-source oracle-layout baseline: predicted bboxes are copied "
                "verbatim from the ground-truth annotation; text is translated by "
                "NLLB-200-distilled-600M. Mirrors deepl-text-oracle but uses local "
                "open weights and covers all 8 LTB language pairs (including en-th "
                "and en-ms which DeepL does not support). NLLB-200 license is "
                "CC-BY-NC-4.0 — research use only; for commercial product, swap to "
                "MADLAD-400 (Apache-2.0) or Helsinki-NLP/opus-mt models (CC-BY-4.0)."
            ),
        )

    def _ensure_loaded(self) -> None:
        if self._model is not None and self._tokenizer is not None:
            return
        try:
            import torch  # noqa: F401
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
        except ImportError as e:
            raise RuntimeError(
                "transformers + torch are required for NllbTextRunner. "
                'Install with: pip install -e ".[runners-nllb]"'
            ) from e

        import torch

        if self.device is None:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self._actual_device = self.device
        torch_dtype = torch.float32 if self.device == "cpu" else torch.float16

        self._tokenizer = AutoTokenizer.from_pretrained(self.nllb_model)
        self._model = AutoModelForSeq2SeqLM.from_pretrained(
            self.nllb_model, torch_dtype=torch_dtype
        ).to(self.device)
        self._model.eval()

    def _translate_batch(self, texts: list[str], target_code: str) -> list[str]:
        """Translate a list of English strings to target language."""
        import torch

        tokenizer = self._tokenizer
        model = self._model
        assert tokenizer is not None and model is not None

        if not texts:
            return []

        tokenizer.src_lang = "eng_Latn"
        # NLLB's target language is set via forced_bos_token_id
        forced_bos_id: int
        if hasattr(tokenizer, "lang_code_to_id"):
            forced_bos_id = tokenizer.lang_code_to_id[target_code]  # type: ignore[attr-defined]
        else:
            forced_bos_id = tokenizer.convert_tokens_to_ids(target_code)

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
                    forced_bos_token_id=forced_bos_id,
                    max_new_tokens=self.max_new_tokens,
                    num_beams=self.num_beams,
                    do_sample=False,
                )
            results.extend(tokenizer.batch_decode(out_ids, skip_special_tokens=True))
        return results

    def translate(self, annotation: Annotation, lang_pair: LangPair) -> DocumentSubmission:
        self._ensure_loaded()

        target_code = _LANG_PAIR_TO_NLLB.get(lang_pair)
        if target_code is None:
            raise ValueError(f"NllbTextRunner has no NLLB mapping for {lang_pair}")

        texts = [r.text for r in annotation.regions]
        t0 = time.time()
        translated = self._translate_batch(texts, target_code)
        runtime = time.time() - t0

        # Defensive: pad if NLLB returned fewer items than expected
        while len(translated) < len(annotation.regions):
            translated.append("")

        regions: list[PredictedRegion] = []
        for i, r in enumerate(annotation.regions):
            regions.append(
                PredictedRegion(
                    region_id=r.region_id,
                    bbox=r.bbox,  # ORACLE: copy GT verbatim
                    text=translated[i],
                    reading_order=r.reading_order,
                )
            )
        return DocumentSubmission(
            doc_id=annotation.doc_id,
            regions=regions,
            runtime_seconds=runtime,
        )

    def close(self) -> None:
        """Free model memory."""
        self._model = None
        self._tokenizer = None
