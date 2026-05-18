"""Qwen-VL runner: prompts a Qwen vision-language model to translate a document image.

For each (document image, target language) pair, the runner asks Qwen to extract
every text region — for each region returning a bounding box and the translated
text — and packages the response as an LTB-format DocumentSubmission.

Heavyweight dependencies (torch, transformers) are imported lazily so this module
can be loaded for static introspection (e.g. CLI help, tests) on machines without
them. Install with:

    pip install -e ".[runners-qwen]"

Default model: Qwen/Qwen3-VL-2B-Instruct (2B, ~4 GB in fp16; the smallest current
Qwen3-VL variant — best fit for CPU inference). Set LTB_QWEN_MODEL_ID to override.
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any

from ltbench.runners.base import Runner
from ltbench.schemas import (
    Annotation,
    DocumentSubmission,
    LangPair,
    PredictedRegion,
    SystemManifest,
)

DEFAULT_MODEL_ID = "Qwen/Qwen3-VL-2B-Instruct"
DEFAULT_MAX_NEW_TOKENS = 2048
DEFAULT_TEMPERATURE = 0.0

_LANG_NAMES: dict[LangPair, str] = {
    "en-es": "Spanish",
    "en-de": "German",
    "en-zh": "Simplified Chinese",
    "en-ar": "Arabic",
    "en-ja": "Japanese",
}


def _build_prompt(target_lang_name: str) -> str:
    """Construct the structured-output prompt asked of the VLM."""
    return (
        "You are looking at a document image. Identify every visible text region in the image. "
        "For each region, output a JSON object with these fields:\n"
        "  - region_id: a short identifier like r0, r1, r2 (assign sequentially in reading order)\n"
        "  - bbox: [x, y, w, h] in pixels (top-left origin)\n"
        "  - text: the translated text in " + target_lang_name + "\n"
        "  - reading_order: 0-based integer (same as region_id index)\n\n"
        "Translate every region — do not summarise, omit, or paraphrase. Preserve numbers, dates, "
        "names, and codes verbatim where they would not be translated (proper nouns, registry "
        "numbers, etc.). Reply with ONLY a JSON array of region objects, no prose, no Markdown "
        "fences, no commentary."
    )


_JSON_ARRAY_PATTERN = re.compile(r"\[\s*\{.*\}\s*\]", re.DOTALL)


def _extract_json_array(raw: str) -> list[dict[str, Any]]:
    """Best-effort extraction of a JSON array of region objects from a free-form reply."""
    raw = raw.strip()
    # Strip Markdown fences if the model added them
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    m = _JSON_ARRAY_PATTERN.search(raw)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    return []


def _normalise_bbox(bbox: Any) -> tuple[float, float, float, float] | None:
    """Coerce a bbox-shaped value into (x, y, w, h). Returns None if uncoercible."""
    if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
        return None
    try:
        x, y, a, b = (float(v) for v in bbox)
    except (TypeError, ValueError):
        return None
    # Accept either (x, y, w, h) or (x1, y1, x2, y2); detect by checking if a/b > x/y
    if a > x and b > y and a < 4000 and b < 4000:
        # Could be either. Heuristic: if "w/h" form, a and b are typically smaller than page size.
        # For 800x1100 pages, both forms can be valid. Prefer (x, y, w, h) form (the LTB convention).
        # If the values look like (x2, y2) (i.e., a > x and b > y AND a+b > some threshold), convert.
        # Without more signal, assume the model followed instructions and returned (x, y, w, h).
        pass
    return (max(0.0, x), max(0.0, y), max(1.0, a), max(1.0, b))


class QwenVLRunner(Runner):
    """Runs a Qwen-VL model locally via transformers."""

    name = "qwen-vl"
    version = "0.1.0"

    def __init__(
        self,
        model_id: str | None = None,
        device: str | None = None,
        dtype: str = "auto",
        max_new_tokens: int = DEFAULT_MAX_NEW_TOKENS,
        temperature: float = DEFAULT_TEMPERATURE,
        data_root: Path = Path("data"),
    ) -> None:
        self.model_id = model_id or os.environ.get("LTB_QWEN_MODEL_ID", DEFAULT_MODEL_ID)
        self.device = device  # None -> auto
        self.dtype = dtype
        self.max_new_tokens = max_new_tokens
        self.temperature = temperature
        self.data_root = data_root
        self._model = None
        self._processor = None
        self._actual_device: str | None = None

    @property
    def name(self) -> str:  # type: ignore[override]
        # Override the class attr so different model IDs produce different system names
        return f"qwen-vl-{self.model_id.split('/')[-1].lower()}"

    def system_manifest(self) -> SystemManifest:
        return SystemManifest(
            system_name=self.name,
            system_version=self.version,
            model_id_or_url=f"https://huggingface.co/{self.model_id}",
            runner_config={
                "max_new_tokens": self.max_new_tokens,
                "temperature": self.temperature,
                "dtype": self.dtype,
            },
            hardware=self._actual_device,
        )

    def _ensure_loaded(self) -> None:
        if self._model is not None and self._processor is not None:
            return
        try:
            import torch  # noqa: F401
            from transformers import AutoModelForCausalLM, AutoProcessor
        except ImportError as e:
            raise RuntimeError(
                "transformers + torch are required for QwenVLRunner. "
                'Install with: pip install -e ".[runners-qwen]"'
            ) from e

        import torch

        if self.device is None:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self._actual_device = self.device

        torch_dtype = None
        if self.dtype == "fp16":
            torch_dtype = torch.float16
        elif self.dtype == "bf16":
            torch_dtype = torch.bfloat16
        elif self.dtype == "fp32":
            torch_dtype = torch.float32

        self._processor = AutoProcessor.from_pretrained(self.model_id, trust_remote_code=True)
        self._model = AutoModelForCausalLM.from_pretrained(
            self.model_id,
            trust_remote_code=True,
            torch_dtype=torch_dtype or "auto",
            device_map=self.device if self.device == "cuda" else None,
        )
        if self.device == "cpu":
            self._model = self._model.to("cpu")
        self._model.eval()

    def _resolve_source_image(self, annotation: Annotation) -> Path:
        """Locate the PNG matching this annotation's doc_id."""
        # Convention: data/sources/<doc_id>.png
        candidate = self.data_root / "sources" / f"{annotation.doc_id}.png"
        if candidate.exists():
            return candidate
        # Fallback: search anywhere under data/sources/
        for ext in (".png", ".jpg", ".jpeg"):
            for p in (self.data_root / "sources").glob(f"{annotation.doc_id}*{ext}"):
                return p
        raise FileNotFoundError(
            f"No rendered source image for {annotation.doc_id}. "
            f"Run `python scripts/render_samples.py` first."
        )

    def translate(self, annotation: Annotation, lang_pair: LangPair) -> DocumentSubmission:
        from PIL import Image

        self._ensure_loaded()
        target_name = _LANG_NAMES[lang_pair]
        prompt = _build_prompt(target_name)
        image_path = self._resolve_source_image(annotation)
        image = Image.open(image_path).convert("RGB")

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": image_path.as_uri()},
                    {"type": "text", "text": prompt},
                ],
            }
        ]

        text_prompt = self._processor.apply_chat_template(  # type: ignore[union-attr]
            messages, tokenize=False, add_generation_prompt=True
        )
        inputs = self._processor(  # type: ignore[misc]
            text=[text_prompt],
            images=[image],
            return_tensors="pt",
            padding=True,
        )
        if self._actual_device == "cuda":
            inputs = {k: v.cuda() for k, v in inputs.items()}

        import torch

        t0 = time.time()
        with torch.inference_mode():
            output_ids = self._model.generate(  # type: ignore[union-attr]
                **inputs,
                max_new_tokens=self.max_new_tokens,
                do_sample=self.temperature > 0,
                temperature=self.temperature if self.temperature > 0 else 1.0,
            )
        runtime = time.time() - t0

        # Strip the prompt prefix from the generated tokens
        input_len = inputs["input_ids"].shape[1]
        generated_ids = output_ids[0, input_len:]
        raw_reply = self._processor.batch_decode(  # type: ignore[union-attr]
            [generated_ids], skip_special_tokens=True
        )[0]

        regions_raw = _extract_json_array(raw_reply)
        regions: list[PredictedRegion] = []
        for idx, r in enumerate(regions_raw):
            if not isinstance(r, dict):
                continue
            bbox = _normalise_bbox(r.get("bbox"))
            if bbox is None:
                continue
            text = str(r.get("text", "")).strip()
            if not text:
                continue
            region_id = str(r.get("region_id") or f"r{idx}")
            reading_order = int(r.get("reading_order", idx))
            regions.append(
                PredictedRegion(
                    region_id=region_id, bbox=bbox, text=text, reading_order=reading_order
                )
            )

        if not regions:
            # Fall back to a single empty placeholder so scoring still runs
            regions = [
                PredictedRegion(
                    region_id="r0", bbox=(0.0, 0.0, 1.0, 1.0), text="", reading_order=0
                )
            ]

        return DocumentSubmission(
            doc_id=annotation.doc_id,
            regions=regions,
            runtime_seconds=runtime,
        )
