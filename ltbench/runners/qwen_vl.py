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


_FEW_SHOT_BY_LANG: dict[str, str] = {
    "Spanish": '"Hola mundo"',
    "German": '"Hallo Welt"',
    "Simplified Chinese": '"你好世界"',
    "Arabic": '"مرحبا بالعالم"',
    "Japanese": '"こんにちは世界"',
}


def _build_prompt(target_lang_name: str) -> str:
    """Construct the structured-output prompt asked of the VLM."""
    example_translation = _FEW_SHOT_BY_LANG.get(target_lang_name, f'"<{target_lang_name}>"')
    return (
        f"TASK: Translate every text region in this document image into {target_lang_name}.\n\n"
        f"OUTPUT FORMAT: A JSON array. Each element has:\n"
        f'  - "region_id": short id like "r0", "r1", "r2", assigned in reading order\n'
        f'  - "bbox": [x1, y1, x2, y2] in absolute pixels, top-left origin\n'
        f'  - "text": the text translated into {target_lang_name}\n'
        f'  - "reading_order": 0-based integer (same as the index in "r0", "r1", ...)\n\n'
        f"CRITICAL RULES:\n"
        f"  1. You MUST translate the text into {target_lang_name}. Do not return English. "
        f"Do not return the source language unchanged.\n"
        f"  2. Keep proper nouns (people's names, places, registry numbers, dates as digits) "
        f"in their original form. Translate the surrounding labels and connective words.\n"
        f"  3. Preserve every visible region — do not skip, merge, or summarise.\n"
        f"  4. Reply with ONLY the JSON array. No prose. No code fences. No commentary.\n\n"
        f"EXAMPLE (correct output for a region containing 'Hello world' at bbox [10,10,100,30]):\n"
        f'  {{"region_id":"r0","bbox":[10,10,100,30],"text":{example_translation},"reading_order":0}}\n'
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


def _normalise_bbox(
    bbox: Any, page_size: tuple[float, float] | None = None
) -> tuple[float, float, float, float] | None:
    """Coerce a bbox value into LTB's (x, y, w, h) form.

    The prompt asks the model for [x1, y1, x2, y2]. Since Qwen-VL outputs in that
    convention natively, we expect that form and convert it. If the third/fourth
    values look like width/height instead (i.e. a < x or b < y, or a + x exceeds
    a plausible page size), we accept them as-is.
    """
    if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
        return None
    try:
        x, y, a, b = (float(v) for v in bbox)
    except (TypeError, ValueError):
        return None

    # Heuristic: if a > x and b > y, treat as (x1, y1, x2, y2) and convert to (x, y, w, h).
    # If the model returned width/height, x2/y2 would equal x+w / y+h which is still > x and > y
    # for any positive w, h — so this heuristic always fires when valid. The opposite case
    # (a < x or b < y) means it can only be width/height (or invalid). We accept either form.
    if a > x and b > y:
        w = a - x
        h = b - y
    else:
        w = a
        h = b

    # Clamp to a sensible minimum so empty/invalid bboxes don't crash the IoU calc
    return (max(0.0, x), max(0.0, y), max(1.0, w), max(1.0, h))


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
            from transformers import AutoProcessor
        except ImportError as e:
            raise RuntimeError(
                "transformers + torch are required for QwenVLRunner. "
                'Install with: pip install -e ".[runners-qwen]"'
            ) from e

        import torch

        # Qwen-VL family are vision-language models — use the right AutoModel class.
        # AutoModelForImageTextToText is the canonical auto-class in transformers 5.x;
        # AutoModelForVision2Seq is the older 4.x name. We try the new one first.
        ModelClass = None
        try:
            from transformers import AutoModelForImageTextToText as ModelClass  # type: ignore
        except ImportError:
            try:
                from transformers import AutoModelForVision2Seq as ModelClass  # type: ignore
            except ImportError as e:
                raise RuntimeError(
                    "transformers must expose AutoModelForImageTextToText or "
                    "AutoModelForVision2Seq to load Qwen-VL models."
                ) from e

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
        self._model = ModelClass.from_pretrained(
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

        # Build messages with the PIL Image inline — works with both qwen-vl-utils
        # and recent transformers chat templates without filesystem URI dance.
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": image},
                    {"type": "text", "text": prompt},
                ],
            }
        ]

        text_prompt = self._processor.apply_chat_template(  # type: ignore[union-attr]
            messages, tokenize=False, add_generation_prompt=True
        )

        # Prefer qwen_vl_utils.process_vision_info if available; otherwise fall back
        # to passing the image directly to the processor.
        image_inputs: list[Any] = [image]
        video_inputs: list[Any] | None = None
        try:
            from qwen_vl_utils import process_vision_info  # type: ignore

            vi = process_vision_info(messages)
            if isinstance(vi, tuple) and len(vi) >= 2:
                image_inputs = vi[0] or [image]
                video_inputs = vi[1] if len(vi) > 1 else None
        except Exception:
            pass

        proc_kwargs: dict[str, Any] = {
            "text": [text_prompt],
            "images": image_inputs,
            "return_tensors": "pt",
            "padding": True,
        }
        if video_inputs:
            proc_kwargs["videos"] = video_inputs
        inputs = self._processor(**proc_kwargs)  # type: ignore[misc]
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
