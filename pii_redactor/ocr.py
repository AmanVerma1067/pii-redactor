"""Facade re-export for embedded image OCR & media redaction from image_engine.py."""
from __future__ import annotations

from .image_engine import (
    FONT_CANDIDATES,
    ID_BOILERPLATE,
    ID_KEYWORDS,
     ImageHit,
    ImageRedactor,
    ImageReport,
    Line,
    OCRRedactor,
    Word,
)

__all__ = [
    "ID_KEYWORDS",
    "ID_BOILERPLATE",
    "FONT_CANDIDATES",
    "Word",
    "Line",
    "ImageHit",
    "ImageReport",
    "ImageRedactor",
    "OCRRedactor",
]

