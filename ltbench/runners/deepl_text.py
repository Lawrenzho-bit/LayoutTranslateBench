"""DeepL Text API runner — oracle-layout baseline.

Calls the DeepL Text API (https://www.deepl.com/docs-api) to translate each
text region of an annotation, and copies the ground-truth bounding boxes as
"predicted" bboxes verbatim.

This is intentionally an **oracle-layout** runner: it measures how good a
state-of-the-art commercial MT (DeepL) is at translating the text, assuming
perfect layout extraction. It does NOT measure DeepL Documents' end-to-end
PDF translation product — that's a separate runner (deferred to v0.2,
because LTB's v0.1 sample documents are PNGs, which DeepL Documents won't
accept without an OCR pre-step).

The system_name is **deepl-text-oracle** so the leaderboard makes it clear
this is a text-quality upper bound, not a realistic end-to-end score.

Auth: set the DEEPL_API_KEY environment variable (free tier works fine
for the v0.1 sample dataset — total < 6k characters across 5 docs x 5 pairs).
Free tier endpoint is used by default; pass free_tier=False for Pro.
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

FREE_TIER_ENDPOINT = "https://api-free.deepl.com/v2/translate"
PRO_TIER_ENDPOINT = "https://api.deepl.com/v2/translate"

# Map LTB language-pair codes to DeepL target-language codes
_LANG_PAIR_TO_DEEPL: dict[LangPair, str] = {
    "en-es": "ES",
    "en-de": "DE",
    "en-zh": "ZH",  # Simplified Chinese (DeepL default)
    "en-ar": "AR",
    "en-ja": "JA",
}


class DeepLTextRunner(Runner):
    """DeepL Text API runner with oracle layout (GT bboxes copied verbatim)."""

    version = "0.1.0"

    def __init__(
        self,
        api_key: str | None = None,
        free_tier: bool = True,
        formality: str | None = None,
        max_retries: int = 3,
        retry_backoff_seconds: float = 2.0,
    ) -> None:
        self.api_key = api_key or os.environ.get("DEEPL_API_KEY")
        if not self.api_key:
            raise RuntimeError(
                "DEEPL_API_KEY env var not set, and no api_key argument provided. "
                "Get a free-tier key at https://www.deepl.com/pro-api?cta=header-pro-api"
            )
        self.free_tier = free_tier
        self.endpoint = FREE_TIER_ENDPOINT if free_tier else PRO_TIER_ENDPOINT
        self.formality = formality  # None | "more" | "less" | "default" (DE/JA/FR/ES support this)
        self.max_retries = max_retries
        self.retry_backoff_seconds = retry_backoff_seconds
        self._http_client = None

    @property
    def name(self) -> str:  # type: ignore[override]
        return "deepl-text-oracle"

    def system_manifest(self) -> SystemManifest:
        return SystemManifest(
            system_name=self.name,
            system_version=self.version,
            model_id_or_url="https://www.deepl.com/translator (DeepL Text API)",
            runner_config={
                "endpoint_tier": "free" if self.free_tier else "pro",
                "formality": self.formality,
                "oracle_layout": True,
                "max_retries": self.max_retries,
            },
            hardware="api",
            notes=(
                "Oracle-layout baseline: predicted bboxes are copied verbatim from "
                "the ground-truth annotation. This measures DeepL's text-quality "
                "ceiling, NOT DeepL's end-to-end document-translation product. The "
                "true DeepL Documents API runner (operating on PDFs) is deferred to "
                "v0.2 because the v0.1 sample dataset is PNG-based."
            ),
        )

    def _http(self):
        """Lazy-initialize the httpx client. Lets the module load without httpx installed."""
        if self._http_client is not None:
            return self._http_client
        try:
            import httpx
        except ImportError as e:
            raise RuntimeError(
                "httpx is required for the DeepL runner. "
                'Install with: pip install -e ".[runners-deepl]"'
            ) from e
        self._http_client = httpx.Client(timeout=30.0)
        return self._http_client

    def _translate_batch(self, texts: list[str], target_lang: str) -> list[str]:
        """One DeepL API call translating up to 50 texts to the target language."""
        if not texts:
            return []

        client = self._http()
        # DeepL accepts repeated `text` fields for batched translation
        data: list[tuple[str, str]] = [("text", t) for t in texts]
        data.append(("source_lang", "EN"))
        data.append(("target_lang", target_lang))
        if self.formality:
            data.append(("formality", self.formality))

        headers = {"Authorization": f"DeepL-Auth-Key {self.api_key}"}

        last_err: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                response = client.post(self.endpoint, headers=headers, data=data)
                # Free tier returns 456 (quota exceeded) explicitly; surface clearly
                if response.status_code == 456:
                    raise RuntimeError(
                        "DeepL free-tier monthly quota exceeded. Upgrade to Pro or "
                        "wait until the quota resets at the start of next month."
                    )
                response.raise_for_status()
                payload = response.json()
                return [t["text"] for t in payload["translations"]]
            except Exception as e:  # pragma: no cover — depends on network
                last_err = e
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_backoff_seconds * (2**attempt))
                    continue
                raise
        raise RuntimeError(f"DeepL request failed after {self.max_retries} attempts") from last_err

    def translate(self, annotation: Annotation, lang_pair: LangPair) -> DocumentSubmission:
        target_lang = _LANG_PAIR_TO_DEEPL.get(lang_pair)
        if target_lang is None:
            raise ValueError(f"DeepL runner has no mapping for {lang_pair}")

        texts = [r.text for r in annotation.regions]
        t0 = time.time()
        translated = self._translate_batch(texts, target_lang)
        runtime = time.time() - t0

        # Defensive: if DeepL returned fewer items than we sent (shouldn't happen), pad
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
        """Close the underlying httpx client. Optional — most runs are short."""
        if self._http_client is not None:
            self._http_client.close()
            self._http_client = None
