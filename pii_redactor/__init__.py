"""pii_redactor: production-grade, format-preserving PII redaction and pseudonymization engine."""
from __future__ import annotations

from .anonymizer import Anonymizer
from .docx_engine import DocxEngine
from .entities import EntityType, Span
from .image_engine import ImageRedactor, OCRRedactor
from .pipeline import Redactor, RedactionConfig, RedactionResult
from .pseudonymizer import Pseudonymizer
from .recognizers import PatternRecognizer

__all__ = [
    "EntityType",
    "Span",
    "Redactor",
    "RedactionConfig",
    "RedactionResult",
    "Anonymizer",
    "Pseudonymizer",
    "DocxEngine",
    "ImageRedactor",
    "OCRRedactor",
    "PatternRecognizer",
]
__version__ = "1.0.0"
