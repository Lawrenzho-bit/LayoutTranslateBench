"""Tests for COMET-Kiwi-22 integration (v0.1.2 methodology fix #3).

These tests verify the wiring without requiring `unbabel-comet` to be installed
in the test environment (which is the whole point of the optional-metric
design). The COMET model is mocked.
"""

from __future__ import annotations

import sys
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from ltbench.metrics.composite import score_document
from ltbench.schemas import (
    Annotation,
    DocumentSubmission,
    PredictedRegion,
    Region,
    StyleHint,
)


def _make_annotation(doc_id: str = "doc_test") -> Annotation:
    """One-region annotation with reference translations."""
    return Annotation(
        doc_id=doc_id,
        page_size=(800.0, 1100.0),
        regions=[
            Region(
                region_id="r0",
                bbox=(0.0, 0.0, 400.0, 60.0),
                text="Certificate of Birth",
                reading_order=0,
                layout_class="title",
                style=StyleHint(),
                references={
                    "en-es": "Certificado de Nacimiento",
                    "en-de": "Geburtsurkunde",
                    "en-zh": "出生证明",
                    "en-ar": "شهادة ميلاد",
                    "en-ja": "出生証明書",
                    "en-fr": "Acte de Naissance",
                    "en-th": "สูติบัตร",
                    "en-ms": "Sijil Kelahiran",
                },
            )
        ],
    )


def _make_submission(text: str = "Certificado de Nacimiento") -> DocumentSubmission:
    return DocumentSubmission(
        doc_id="doc_test",
        regions=[
            PredictedRegion(
                region_id="r0",
                bbox=(0.0, 0.0, 400.0, 60.0),
                text=text,
                reading_order=0,
            )
        ],
    )


def test_score_document_default_metric_is_chrf():
    """When text_metric is unspecified, chrF is used (backwards-compat)."""
    ann = _make_annotation()
    sub = _make_submission()
    result = score_document(ann, sub, "en-es")
    # chrF on identical strings should be 100; the area-weighted chrF for the
    # single region is also 100.
    assert result.chrf == pytest.approx(100.0)


def test_score_document_invalid_text_metric_raises():
    ann = _make_annotation()
    sub = _make_submission()
    with pytest.raises(ValueError, match="unknown text_metric"):
        score_document(ann, sub, "en-es", text_metric="bleurt")


def test_score_document_comet_kiwi_uses_score_batch():
    """When text_metric='comet-kiwi', the COMET score_batch path is called and
    its return value is used as the per-region 'chrF' field of the result.

    Mocks `ltbench.metrics.comet.score_batch` so the test doesn't require
    `unbabel-comet` installed.
    """
    ann = _make_annotation()
    sub = _make_submission(text="some-translation-output")

    # Create a fake comet module
    fake_comet_module = SimpleNamespace(score_batch=lambda sources, hyps: [82.5])
    with patch.dict(sys.modules, {"ltbench.metrics.comet": fake_comet_module}):
        result = score_document(ann, sub, "en-es", text_metric="comet-kiwi")

    # The single region's chrF field should equal the mocked COMET return
    # (area-weighted, but there's only one full-area region here).
    assert result.chrf == pytest.approx(82.5)
    # IoU should be perfect (identical bboxes)
    assert result.layout_iou == pytest.approx(1.0)


def test_score_document_comet_kiwi_batches_multiple_regions():
    """COMET path should call score_batch ONCE per document with all matched
    regions, not once per region. Verifies batching."""
    ann = Annotation(
        doc_id="doc_test",
        page_size=(800.0, 1100.0),
        regions=[
            Region(
                region_id="r0",
                bbox=(0.0, 0.0, 400.0, 60.0),
                text="Hello",
                reading_order=0,
                layout_class="title",
                references={"en-es": "Hola"},
            ),
            Region(
                region_id="r1",
                bbox=(0.0, 60.0, 400.0, 60.0),
                text="World",
                reading_order=1,
                layout_class="paragraph",
                references={"en-es": "Mundo"},
            ),
        ],
    )
    sub = DocumentSubmission(
        doc_id="doc_test",
        regions=[
            PredictedRegion(region_id="r0", bbox=(0.0, 0.0, 400.0, 60.0), text="Hola", reading_order=0),
            PredictedRegion(region_id="r1", bbox=(0.0, 60.0, 400.0, 60.0), text="Mundo", reading_order=1),
        ],
    )

    call_log: list[tuple[list[str], list[str]]] = []

    def fake_score_batch(sources, hyps):
        call_log.append((list(sources), list(hyps)))
        return [88.0] * len(sources)

    fake_comet = SimpleNamespace(score_batch=fake_score_batch)
    with patch.dict(sys.modules, {"ltbench.metrics.comet": fake_comet}):
        result = score_document(ann, sub, "en-es", text_metric="comet-kiwi")

    # Exactly ONE call to score_batch with both regions
    assert len(call_log) == 1
    assert call_log[0][0] == ["Hello", "World"]
    assert call_log[0][1] == ["Hola", "Mundo"]
    # Both regions get the mocked 88.0 score
    assert result.chrf == pytest.approx(88.0)
