"""WordprocessingML traversal, run-level replacement, and table handling engine.

Preserves all XML run formatting (bold, italic, font styles, colors, spacing, XML properties)
by projecting text replacements back onto run-level text tokens without overwriting paragraph.text.
"""
from __future__ import annotations

from typing import Iterator
from lxml import etree

from .docx_engine import (
    W,
    W_NS,
    XML_SPACE,
    ATTR_REDACT,
    ATTR_REPLACE,
    XmlPartHandle,
    collect_xml_parts,
    own_segments,
    paragraph_text,
    iter_paragraphs,
    apply_replacements,
    replace_in_paragraphs,
    scrub_generic,
    scrub_relationships,
    part_paragraph_texts,
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


class DocxEngine:
    """High-level engine for WordprocessingML traversal and formatting-preserved replacement."""

    def __init__(self, anonymizer):
        self.anonymizer = anonymizer

    def collect_parts(self, doc):
        return collect_xml_parts(doc)

    def extract_table_entities(self, root: etree._Element):
        return table_context_entities(root)

    def replace_paragraphs(self, root: etree._Element) -> int:
        return replace_in_paragraphs(root, self.anonymizer)

    def scrub_xml_attributes(self, root: etree._Element) -> int:
        return scrub_generic(root, self.anonymizer)

    def scrub_rels(self, doc) -> int:
        return scrub_relationships(doc, self.anonymizer)
