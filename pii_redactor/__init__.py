"""pii_redactor: production-grade, format-preserving PII redaction and pseudonymization engine."""
from __future__ import annotations

from .anonymizer import Anonymizer, Pseudonymizer
from .engine import DocxEngine
from .entities import EntityType, Span
from .ocr import ImageRedactor, OCRRedactor
from .patterns import PatternRecognizer
from .pipeline import Redactor, RedactionConfig, RedactionResult

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
