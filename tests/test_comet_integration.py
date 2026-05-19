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
    # Use a clearly Spanish hypothesis so the language gate (added v0.1.2)
    # accepts the prediction and routes to COMET. v0.1.2 applies the same
    # language-detection penalty to COMET as it does to chrF — predictions
    # in the wrong target language score 0 regardless of text-metric choice.
    sub = _make_submission(text="Certificado de Nacimiento de la persona")

    fake_comet_module = SimpleNamespace(score_batch=lambda sources, hyps: [82.5])
    with patch.dict(sys.modules, {"ltbench.metrics.comet": fake_comet_module}):
        result = score_document(ann, sub, "en-es", text_metric="comet-kiwi")

    assert result.chrf == pytest.approx(82.5)
    assert result.layout_iou == pytest.approx(1.0)


def test_score_document_comet_kiwi_zeros_wrong_language():
    """The language gate applies to COMET too — wrong-language predictions
    score 0 without consulting the COMET model (which is reference-free
    and would otherwise rate identical English strings as a 'good
    translation' to Spanish)."""
    ann = _make_annotation()
    # English hypothesis for a Spanish target: should be rejected by the
    # language gate and score 0 without COMET being called.
    sub = _make_submission(text="Certificate of Birth is the official record")

    score_batch_called = []

    def fake_score_batch(sources, hyps):
        score_batch_called.append((sources, hyps))
        return [99.0] * len(sources)  # would be high if called

    fake_comet = SimpleNamespace(score_batch=fake_score_batch)
    with patch.dict(sys.modules, {"ltbench.metrics.comet": fake_comet}):
        result = score_document(ann, sub, "en-es", text_metric="comet-kiwi")

    # Language gate rejected → no call to COMET → score 0
    assert score_batch_called == []
    assert result.chrf == pytest.approx(0.0)


def test_score_document_comet_kiwi_batches_multiple_regions():
    """COMET path should call score_batch ONCE per document with all matched
    regions that pass the language gate, not once per region. Verifies
    batching efficiency."""
    ann = Annotation(
        doc_id="doc_test",
        page_size=(800.0, 1100.0),
        regions=[
            Region(
                region_id="r0",
                bbox=(0.0, 0.0, 400.0, 60.0),
                text="Hello world how are you",
                reading_order=0,
                layout_class="title",
                references={"en-es": "Hola mundo cómo estás"},
            ),
            Region(
                region_id="r1",
                bbox=(0.0, 60.0, 400.0, 60.0),
                text="Good morning everyone today",
                reading_order=1,
                layout_class="paragraph",
                references={"en-es": "Buenos días a todos hoy"},
            ),
        ],
    )
    # Clearly Spanish hypotheses that pass the language gate
    sub = DocumentSubmission(
        doc_id="doc_test",
        regions=[
            PredictedRegion(
                region_id="r0",
                bbox=(0.0, 0.0, 400.0, 60.0),
                text="Hola mundo cómo estás",
                reading_order=0,
            ),
            PredictedRegion(
                region_id="r1",
                bbox=(0.0, 60.0, 400.0, 60.0),
                text="Buenos días a todos hoy",
                reading_order=1,
            ),
        ],
    )

    call_log: list[tuple[list[str], list[str]]] = []

    def fake_score_batch(sources, hyps):
        call_log.append((list(sources), list(hyps)))
        return [88.0] * len(sources)

    fake_comet = SimpleNamespace(score_batch=fake_score_batch)
    with patch.dict(sys.modules, {"ltbench.metrics.comet": fake_comet}):
        result = score_document(ann, sub, "en-es", text_metric="comet-kiwi")

    # Exactly ONE call to score_batch with both regions (batching efficiency)
    assert len(call_log) == 1
    assert len(call_log[0][0]) == 2
    assert "Hello world" in call_log[0][0][0]
    # Both regions get the mocked 88.0 score
    assert result.chrf == pytest.approx(88.0)
