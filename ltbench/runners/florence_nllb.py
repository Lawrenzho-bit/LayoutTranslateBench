"""Florence-2 + NLLB-200 pipeline runner — the v0.1 product-stack baseline.

A two-stage end-to-end pipeline that mirrors what the actual product should
do:

  1. **Layout extraction** with microsoft/Florence-2-base — outputs text +
     polygon for every region. Florence-2 is OCR-grounding-trained on
     documents and is much better at pixel-precise bboxes than a zero-shot
     general-purpose VLM (see Qwen-VL's 4.4% IoU on this benchmark for
     comparison).
  2. **Translation** with facebook/nllb-200-distilled-600M — handles all 200
     NLLB-supported languages including the 8 LTB pairs. CPU-friendly.

The bbox output of stage 1 is used directly (not the GT bboxes), so this is
a **true end-to-end** runner — no oracle layout. The score it posts is the
honest "open-source product baseline".

License note: NLLB-200 is CC-BY-NC-4.0 (non-commercial). For commercial use,
swap in MADLAD-400 (Apache-2.0) or Helsinki-NLP/opus-mt-en-XX (CC-BY-4.0).
Florence-2 is MIT. The runner is intended for benchmark / research use; the
*product* should pick a commercial-friendly MT model.

Heavyweight deps (torch, transformers, Pillow) are imported lazily. Install:

    pip install -e ".[runners-florence-nllb]"
"""

from __future__ import annotations

import os
import re
import time
from pathlib import Path

from ltbench.runners.base import Runner
from ltbench.schemas import (
    Annotation,
    DocumentSubmission,
    LangPair,
    PredictedRegion,
    SystemManifest,
)

DEFAULT_FLORENCE_MODEL = "microsoft/Florence-2-base"
DEFAULT_NLLB_MODEL = "facebook/nllb-200-distilled-600M"


# NLLB language codes (BCP-47-style with script). Source: NLLB-200 README.
_LANG_PAIR_TO_NLLB: dict[LangPair, str] = {
    "en-es": "spa_Latn",
    "en-de": "deu_Latn",
    "en-zh": "zho_Hans",  # Simplified Chinese
    "en-ar": "arb_Arab",  # Modern Standard Arabic
    "en-ja": "jpn_Jpan",
    "en-fr": "fra_Latn",
    "en-th": "tha_Thai",
    "en-ms": "zsm_Latn",  # Standard Malay
}


# Florence-2's grounding output uses bbox coordinates normalized to a
# 0–999 internal space. Pattern: <loc_X1><loc_Y1><loc_X2><loc_Y2>
_FLORENCE_LOC_RE = re.compile(r"<loc_(\d+)>")


class FlorenceNllbRunner(Runner):
    """Florence-2 (layout) -> NLLB-200 (translation) pipeline."""

    version = "0.1.0"

    def __init__(
        self,
        florence_model: str | None = None,
        nllb_model: str | None = None,
        device: str | None = None,
        data_root: Path = Path("data"),
        max_translation_tokens: int = 256,
    ) -> None:
        self.florence_model = florence_model or os.environ.get(
            "LTB_FLORENCE_MODEL", DEFAULT_FLORENCE_MODEL
        )
        self.nllb_model = nllb_model or os.environ.get("LTB_NLLB_MODEL", DEFAULT_NLLB_MODEL)
        self.device = device
        self.data_root = data_root
        self.max_translation_tokens = max_translation_tokens
        self._florence_processor = None
        self._florence_model = None
        self._nllb_tokenizer = None
        self._nllb_model = None
        self._actual_device: str | None = None

    @property
    def name(self) -> str:  # type: ignore[override]  # noqa: F811
        # Fixed short name. The Florence-2 / NLLB-200 model IDs are recorded
        # separately in model_id_or_url, so no verbose suffix is needed here.
        return "florence-nllb"

    def system_manifest(self) -> SystemManifest:
        return SystemManifest(
            system_name=self.name,
            system_version=self.version,
            model_id_or_url=(
                f"https://huggingface.co/{self.florence_model} + "
                f"https://huggingface.co/{self.nllb_model}"
            ),
            runner_config={
                "florence_model": self.florence_model,
                "nllb_model": self.nllb_model,
                "max_translation_tokens": self.max_translation_tokens,
                "pipeline": "florence-2-grounded-ocr -> nllb-200-translation",
            },
            hardware=self._actual_device,
            system_type="end-to-end",
            notes=(
                "End-to-end open-source product baseline. Florence-2 (MIT) extracts "
                "text regions with bboxes; NLLB-200 (CC-BY-NC-4.0) translates per "
                "region. NOT an oracle-layout runner — bboxes come from the model, "
                "not the GT annotation. License note: NLLB-200 is CC-BY-NC-4.0 — "
                "for commercial product use, swap in MADLAD-400 (Apache-2.0) or "
                "Helsinki-NLP/opus-mt models (CC-BY-4.0)."
            ),
        )

    def _ensure_loaded(self) -> None:
        if self._florence_model is not None and self._nllb_model is not None:
            return
        try:
            import torch  # noqa: F401
            from transformers import (
                AutoModelForCausalLM,
                AutoModelForSeq2SeqLM,
                AutoProcessor,
                AutoTokenizer,
            )
        except ImportError as e:
            raise RuntimeError(
                "transformers + torch are required for FlorenceNllbRunner. "
                'Install with: pip install -e ".[runners-florence-nllb]"'
            ) from e

        import torch

        if self.device is None:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self._actual_device = self.device
        torch_dtype = torch.float32 if self.device == "cpu" else torch.float16

        # Florence-2 — vision model with custom code (trust_remote_code)
        self._florence_processor = AutoProcessor.from_pretrained(
            self.florence_model, trust_remote_code=True
        )
        self._florence_model = AutoModelForCausalLM.from_pretrained(
            self.florence_model, trust_remote_code=True, torch_dtype=torch_dtype,
            attn_implementation="eager"
        ).to(self.device)
        self._florence_model.eval()

        # NLLB — standard seq2seq
        self._nllb_tokenizer = AutoTokenizer.from_pretrained(self.nllb_model)
        self._nllb_model = AutoModelForSeq2SeqLM.from_pretrained(
            self.nllb_model, torch_dtype=torch_dtype
        ).to(self.device)
        self._nllb_model.eval()

    def _resolve_source_image(self, annotation: Annotation) -> Path:
        candidate = self.data_root / "sources" / f"{annotation.doc_id}.png"
        if candidate.exists():
            return candidate
        raise FileNotFoundError(
            f"No rendered source image for {annotation.doc_id}. "
            f"Run `python scripts/render_samples.py` first."
        )

    def _florence_ocr_regions(
        self, image, image_width: int, image_height: int
    ) -> list[tuple[str, tuple[float, float, float, float]]]:
        """Run Florence-2's OCR-with-region task; return [(text, bbox)] in pixels."""
        import torch

        task = "<OCR_WITH_REGION>"
        inputs = self._florence_processor(  # type: ignore[misc]
            text=task, images=image, return_tensors="pt"
        )
        if self._actual_device == "cuda":
            inputs = {k: v.cuda() for k, v in inputs.items()}

        with torch.inference_mode():
            generated_ids = self._florence_model.generate(  # type: ignore[union-attr]
                input_ids=inputs["input_ids"],
                pixel_values=inputs["pixel_values"],
                max_new_tokens=1024,
                num_beams=3,
                do_sample=False,
                use_cache=False,
            )
        generated_text = self._florence_processor.batch_decode(  # type: ignore[union-attr]
            generated_ids, skip_special_tokens=False
        )[0]

        parsed = self._florence_processor.post_process_generation(  # type: ignore[union-attr]
            generated_text, task=task, image_size=(image_width, image_height)
        )
        # parsed shape: {"<OCR_WITH_REGION>": {"quad_boxes": [...], "labels": [...]}}
        result = parsed.get(task, {})
        quad_boxes = result.get("quad_boxes", [])
        labels = result.get("labels", [])

        regions: list[tuple[str, tuple[float, float, float, float]]] = []
        for label, quad in zip(labels, quad_boxes):
            # quad is a flat list of 8 floats: [x0, y0, x1, y1, x2, y2, x3, y3]
            xs = quad[::2]
            ys = quad[1::2]
            x_min, x_max = min(xs), max(xs)
            y_min, y_max = min(ys), max(ys)
            w = max(1.0, x_max - x_min)
            h = max(1.0, y_max - y_min)
            # Florence sometimes prefixes labels with </s>; strip
            text = str(label).replace("</s>", "").strip()
            if not text:
                continue
            regions.append((text, (float(x_min), float(y_min), float(w), float(h))))
        return regions

    def _nllb_translate(self, text: str, target_code: str) -> str:
        """Translate a single string en -> target via NLLB-200."""
        import torch

        tokenizer = self._nllb_tokenizer
        model = self._nllb_model
        assert tokenizer is not None and model is not None

        tokenizer.src_lang = "eng_Latn"
        inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=512)
        if self._actual_device == "cuda":
            inputs = {k: v.cuda() for k, v in inputs.items()}

        # NLLB expects forced_bos_token_id = lang code id
        # Different transformers versions: convert_tokens_to_ids OR lang_code_to_id
        forced_bos_id: int
        if hasattr(tokenizer, "convert_tokens_to_ids"):
            forced_bos_id = tokenizer.convert_tokens_to_ids(target_code)
        else:
            forced_bos_id = tokenizer.lang_code_to_id[target_code]  # type: ignore[attr-defined]

        with torch.inference_mode():
            out_ids = model.generate(
                **inputs,
                forced_bos_token_id=forced_bos_id,
                max_new_tokens=self.max_translation_tokens,
                num_beams=4,
                do_sample=False,
            )
        return tokenizer.batch_decode(out_ids, skip_special_tokens=True)[0]

    def translate(self, annotation: Annotation, lang_pair: LangPair) -> DocumentSubmission:
        from PIL import Image

        self._ensure_loaded()

        target_code = _LANG_PAIR_TO_NLLB.get(lang_pair)
        if target_code is None:
            raise ValueError(f"FlorenceNllbRunner has no NLLB mapping for {lang_pair}")

        image_path = self._resolve_source_image(annotation)
        image = Image.open(image_path).convert("RGB")
        page_w, page_h = image.size

        t0 = time.time()
        # Stage 1: Florence-2 grounded OCR
        ocr_regions = self._florence_ocr_regions(image, page_w, page_h)

        # Stage 2: per-region NLLB translation
        predicted_regions: list[PredictedRegion] = []
        for idx, (src_text, bbox) in enumerate(ocr_regions):
            translated = self._nllb_translate(src_text, target_code)
            predicted_regions.append(
                PredictedRegion(
                    region_id=f"p{idx}",
                    bbox=bbox,
                    text=translated,
                    reading_order=idx,
                )
            )

        if not predicted_regions:
            # Fallback so scoring doesn't crash
            predicted_regions = [
                PredictedRegion(
                    region_id="p0", bbox=(0.0, 0.0, 1.0, 1.0), text="", reading_order=0
                )
            ]

        runtime = time.time() - t0
        return DocumentSubmission(
            doc_id=annotation.doc_id,
            regions=predicted_regions,
            runtime_seconds=runtime,
        )

    def close(self) -> None:
        """Free GPU memory if applicable."""
        self._florence_model = None
        self._nllb_model = None
        self._florence_processor = None
        self._nllb_tokenizer = None
