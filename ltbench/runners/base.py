"""Base class for translation system runners.

A Runner wraps any translation system and produces LTB-format submission files.
Implementations live in ltbench/runners/<system>.py.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ltbench.schemas import Annotation, DocumentSubmission, LangPair, SystemManifest


class Runner(ABC):
    """Abstract base for systems-under-test."""

    name: str = "abstract-runner"
    version: str = "0.0.0"

    def system_manifest(self) -> SystemManifest:
        """Return system metadata for the submission. Override to add specifics."""
        return SystemManifest(system_name=self.name, system_version=self.version)

    @abstractmethod
    def translate(
        self,
        annotation: Annotation,
        lang_pair: LangPair,
    ) -> DocumentSubmission:
        """Translate one document into one target language.

        Implementations must return a DocumentSubmission containing the predicted
        regions (text and bbox placement). The bbox should reflect where the system
        actually placed the translated text in the rendered output.
        """
        raise NotImplementedError
