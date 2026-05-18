"""Pydantic schemas for LayoutTranslateBench: manifest, annotation, submission, results."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

LangPair = Literal["en-es", "en-de", "en-zh", "en-ar", "en-ja"]
LayoutClass = Literal[
    "header", "footer", "single-column", "two-column", "form-field",
    "table-cell", "caption", "stamp", "signature", "handwritten",
    "title", "paragraph", "list-item",
]
FontFamilyClass = Literal["serif", "sans", "mono", "handwritten", "decorative", "unknown"]
Category = Literal[
    "certificate", "gov-form", "legal-contract", "scientific-paper",
    "slide", "receipt-invoice", "business-letter", "magazine-news",
    "bank-statement", "handwritten-mixed",
]


BBox = tuple[float, float, float, float]  # (x, y, w, h) in pixels, top-left origin


class StyleHint(BaseModel):
    font_family: FontFamilyClass = "unknown"
    size_hint: float | None = None
    color: str | None = None  # hex
    background: str | None = None  # hex
    bold: bool = False
    italic: bool = False


class Region(BaseModel):
    """A text region in a ground-truth annotation."""

    region_id: str
    bbox: BBox
    text: str
    reading_order: int = Field(ge=0)
    layout_class: LayoutClass = "paragraph"
    style: StyleHint = Field(default_factory=StyleHint)
    references: dict[LangPair, str]

    @field_validator("bbox")
    @classmethod
    def _bbox_positive(cls, v: BBox) -> BBox:
        if v[2] <= 0 or v[3] <= 0:
            raise ValueError(f"bbox width and height must be positive, got {v}")
        return v


class Annotation(BaseModel):
    """Per-document ground-truth annotation."""

    doc_id: str
    page_size: tuple[float, float]  # (width, height) in pixels
    regions: list[Region]

    @field_validator("regions")
    @classmethod
    def _unique_region_ids(cls, v: list[Region]) -> list[Region]:
        ids = [r.region_id for r in v]
        if len(set(ids)) != len(ids):
            raise ValueError("region_id values must be unique within a document")
        return v


class ManifestEntry(BaseModel):
    """One row in the dataset manifest."""

    doc_id: str
    category: Category
    source_file: str  # relative path under data/
    annotation_file: str  # relative path under data/
    page_size: tuple[float, float]
    license: str = "CC-BY-4.0"
    source_url: str | None = None


class Manifest(BaseModel):
    """The dataset manifest. One file under data/manifest.json."""

    benchmark: str = "LayoutTranslateBench"
    version: str = "0.1"
    entries: list[ManifestEntry]

    @field_validator("entries")
    @classmethod
    def _unique_doc_ids(cls, v: list[ManifestEntry]) -> list[ManifestEntry]:
        ids = [e.doc_id for e in v]
        if len(set(ids)) != len(ids):
            raise ValueError("doc_id values must be unique across manifest")
        return v


class PredictedRegion(BaseModel):
    """A region produced by a translation system."""

    region_id: str
    bbox: BBox
    text: str
    reading_order: int = Field(ge=0)


class DocumentSubmission(BaseModel):
    """One translated document by one system in one language pair.

    Serialized as a single line in a JSONL file at
    submissions/<system>/<lang-pair>.jsonl.
    """

    doc_id: str
    regions: list[PredictedRegion]
    output_file: str | None = None  # optional path to rendered output (PDF/PNG)
    runtime_seconds: float | None = None


class SystemManifest(BaseModel):
    """Metadata about a submitted system. Saved as submissions/<system>/manifest.json."""

    system_name: str
    system_version: str = "0.0.0"
    manifest_version: str = "0.1"  # which LTB dataset version was evaluated
    model_id_or_url: str | None = None
    runner_config: dict = Field(default_factory=dict)
    hardware: str | None = None
    total_runtime_seconds: float | None = None
    median_per_doc_runtime_seconds: float | None = None
    cost_usd: float | None = None
    submitter: str | None = None
    notes: str | None = None


# ---------- Result schema (output of `ltbench score`) ----------


class RegionScore(BaseModel):
    region_id: str
    chrf: float
    layout_iou: float
    matched: bool  # whether the predicted region matched a ground-truth region


class DocumentScore(BaseModel):
    doc_id: str
    lang_pair: LangPair
    chrf: float
    layout_iou: float
    reading_order_tau: float
    ltb_100: float
    region_scores: list[RegionScore]


class LangPairScore(BaseModel):
    lang_pair: LangPair
    n_docs: int
    chrf: float
    layout_iou: float
    reading_order_tau: float
    ltb_100: float


class SubmissionResult(BaseModel):
    """The output of `ltbench score`. One file per system under results/."""

    system: SystemManifest
    benchmark_version: str = "0.1"
    weights: dict[str, float]
    overall_ltb_100: float
    overall_chrf: float
    overall_layout_iou: float
    overall_reading_order_tau: float
    per_lang_pair: list[LangPairScore]
    per_doc: list[DocumentScore]
    scored_at: str  # ISO-8601


# ---------- Leaderboard ----------


class LeaderboardRow(BaseModel):
    rank: int
    system_name: str
    system_version: str
    ltb_100: float
    chrf: float
    layout_iou: float
    reading_order_tau: float
    median_runtime_s: float | None = None
    cost_usd: float | None = None
    hardware: str | None = None
    submitter: str | None = None
    verified: bool = False
