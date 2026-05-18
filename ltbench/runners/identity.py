"""Identity baseline: returns the source text and original bboxes unchanged.

Useful as a sanity-check lower bound. A real translation system should beat this
on chrF (it will score the chrF of source-vs-reference, ~0 for most language
pairs) but match it on layout IoU (since boxes are unchanged) and reading order.
"""

from __future__ import annotations

from ltbench.runners.base import Runner
from ltbench.schemas import (
    Annotation,
    DocumentSubmission,
    LangPair,
    PredictedRegion,
    SystemManifest,
)


class IdentityRunner(Runner):
    name = "identity-baseline"
    version = "0.1.0"

    def system_manifest(self) -> SystemManifest:
        return SystemManifest(
            system_name=self.name,
            system_version=self.version,
            model_id_or_url=None,
            runner_config={"description": "returns source text and bboxes unchanged"},
            hardware="cpu",
        )

    def translate(self, annotation: Annotation, lang_pair: LangPair) -> DocumentSubmission:
        regions = [
            PredictedRegion(
                region_id=r.region_id,
                bbox=r.bbox,
                text=r.text,  # source unchanged
                reading_order=r.reading_order,
            )
            for r in annotation.regions
        ]
        return DocumentSubmission(doc_id=annotation.doc_id, regions=regions)
