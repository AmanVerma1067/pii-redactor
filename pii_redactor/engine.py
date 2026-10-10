"""Facade re-export for WordprocessingML traversal and replacement from docx_engine.py."""
from __future__ import annotations

from .docx_engine import (
    ATTR_REDACT,
    ATTR_REPLACE,
    W,
    W_NS,
    XML_SPACE,
    DocxEngine,
    XmlPartHandle,
    apply_replacements,
    collect_xml_parts,
    iter_paragraphs,
    own_segments,
    paragraph_text,
    part_paragraph_texts,
    replace_in_paragraphs,
    scrub_generic,
    scrub_relationships,
    table_context_entities,
)

__all__ = [
    "W",
    "W_NS",
    "XML_SPACE",
    "ATTR_REDACT",
    "ATTR_REPLACE",
    "XmlPartHandle",
    "collect_xml_parts",
    "own_segments",
    "paragraph_text",
    "iter_paragraphs",
    "apply_replacements",
    "replace_in_paragraphs",
    "scrub_generic",
    "scrub_relationships",
    "part_paragraph_texts",
    "table_context_entities",
    "DocxEngine",
]
