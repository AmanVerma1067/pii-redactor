"""End-to-end orchestration: two-pass detect -> register -> (images) -> replace -> save."""
from __future__ import annotations

import io
import logging
import time
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import BinaryIO

from docx import Document
from lxml import etree

from .detector import DetectorConfig, PIIDetector
from .docx_engine import (collect_xml_parts, part_paragraph_texts, replace_in_paragraphs, scrub_generic,
                          scrub_relationships, table_context_entities)
from .entities import CLASS_OF, EntityType as T
from .image_engine import ImageRedactor
from .pseudonymizer import Pseudonymizer

log = logging.getLogger(__name__)
REGISTER_ORDER = [T.ORG, T.PERSON, T.ADDRESS, T.EMAIL, T.URL, T.DOMAIN]


@dataclass
class RedactionConfig:
    salt: str = "scaler-ai-labs"
    enable_ocr: bool = True
    image_policy: str = "replace"         # replace | mask | blur
    mask_qr: bool = True
    blur_faces: bool = True
    image_failsafe: bool = True
    ocr_lang: str = "eng"
    spacy_model: str | None = None
    min_score: float = 0.5
    scrub_metadata: bool = True
    extra_allowlist: list[str] = field(default_factory=list)


@dataclass
class RedactionResult:
    output: bytes
    report: dict
    mapping: list[dict]

    def save(self, path: str | Path) -> None:
        Path(path).write_bytes(self.output)


class Redactor:
    def __init__(self, config: RedactionConfig | None = None, detector: PIIDetector | None = None):
        self.config = config or RedactionConfig()
        dcfg = DetectorConfig(spacy_model=self.config.spacy_model, min_score=self.config.min_score)
        dcfg.allowlist += self.config.extra_allowlist
        self.detector = detector or PIIDetector(dcfg)

    def redact(self, src: str | Path | bytes | BinaryIO) -> RedactionResult:
        t0 = time.time()
        if isinstance(src, (bytes, bytearray)):
            src = io.BytesIO(src)
        doc = Document(src)
        pseudo = Pseudonymizer(self.config.salt)
        handles = collect_xml_parts(doc)

        # ---------------- pass 1: detection over every text-bearing part (body, tables, headers,
        # footers, footnotes, comments, text boxes, charts, doc properties)
        detections: list[tuple[str, T, str, str]] = []
        for h in handles:
            texts = part_paragraph_texts(h.root)
            if not any(t.strip() for t in texts):
                texts = [el.text for el in h.root.iter() if isinstance(el.tag, str) and el.text and el.text.strip()]
            if texts:
                for sp in self.detector.detect_stream(texts):
                    detections.append((sp.text, sp.type, sp.source, h.name))
            for text, et in table_context_entities(h.root):
                detections.append((text, et, "table_context", h.name))

        order = {t: i for i, t in enumerate(REGISTER_ORDER)}
        detections.sort(key=lambda d: (order.get(d[1], 99), -len(d[0].split())))
        for text, et, _, _ in detections:
            pseudo.register(text, et)

        # ---------------- images (OCR) share the same mapping
        image_reports = []
        if self.config.enable_ocr:
            ir = ImageRedactor(self.detector, pseudo, policy=self.config.image_policy, lang=self.config.ocr_lang,
                               mask_qr=self.config.mask_qr, blur_faces=self.config.blur_faces,
                               failsafe=self.config.image_failsafe)
            if ir.available():
                for part in doc.part.package.iter_parts():
                    if part.content_type.startswith("image/"):
                        image_reports.append(asdict(ir.process_part(part)))
            else:
                log.warning("Tesseract not available: embedded images were NOT scanned")
                image_reports.append({"skipped": "tesseract not installed"})

        # ---------------- pass 2: global replacement with every known surface form
        n_runs = n_generic = 0
        for h in handles:
            n_runs += replace_in_paragraphs(h.root, pseudo)
            n_generic += scrub_generic(h.root, pseudo)
            if self.config.scrub_metadata and h.name == "/docProps/app.xml":
                for el in h.root.iter():
                    if isinstance(el.tag, str) and el.tag.split("}")[-1] in ("Company", "Manager"):
                        el.text = ""
            h.commit()
        n_rels = scrub_relationships(doc, pseudo)
        if self.config.scrub_metadata:
            cp = doc.core_properties
            cp.author = "Redacted"
            cp.last_modified_by = "Redacted"

        out = io.BytesIO()
        doc.save(out)
        mapping = pseudo.mapping()
        report = {
            "entities_unique": len(mapping),
            "entities_by_type": dict(Counter(m["type"] for m in mapping)),
            "entities_by_class": dict(Counter(CLASS_OF[T(m["type"])] for m in mapping)),
            "detections": [{"text": t, "type": et.value, "source": s, "part": p} for t, et, s, p in detections],
            "replacements": {"paragraph_spans": n_runs, "other_xml_nodes": n_generic, "hyperlinks": n_rels},
            "images": image_reports,
            "seconds": round(time.time() - t0, 2),
            "config": asdict(self.config),
        }
        return RedactionResult(out.getvalue(), report, mapping)
