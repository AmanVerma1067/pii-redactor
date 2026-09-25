"""Hybrid detector: regex recognizers + heuristics + optional NER, with overlap resolution."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .entities import EntityType as T, Span
from .gazetteer import ALLOWLIST_DOMAINS, DEFAULT_ALLOWLIST
from .heuristics import AddressRecognizer, OrgRecognizer, PersonRecognizer
from .ner import load_ner
from .recognizers import build_pattern_recognizers, run_all


@dataclass
class DetectorConfig:
    spacy_model: str | None = None
    min_score: float = 0.5
    allowlist: list[str] = field(default_factory=lambda: list(DEFAULT_ALLOWLIST))
    allowlist_domains: list[str] = field(default_factory=lambda: list(ALLOWLIST_DOMAINS))
    disabled_types: set[T] = field(default_factory=set)


class PIIDetector:
    def __init__(self, config: DetectorConfig | None = None):
        self.config = config or DetectorConfig()
        self.patterns = build_pattern_recognizers()
        self.persons = PersonRecognizer()
        self.orgs = OrgRecognizer()
        self.addresses = AddressRecognizer()
        self.ner = load_ner(self.config.spacy_model)
        self._allow = {self._norm(a) for a in self.config.allowlist}
        self.custom: list = []  # user-registered recognizers exposing .find(text, id_context)

    # ------------------------------------------------------------------ public API
    def register(self, recognizer) -> None:
        """Plug in a custom recognizer (see README > Extending)."""
        self.custom.append(recognizer)

    def detect(self, text: str, id_context: bool = False) -> list[Span]:
        return self.detect_stream([text], id_context=id_context)

    def detect_stream(self, paragraphs: list[str], id_context: bool = False) -> list[Span]:
        """Detect over paragraphs joined by '\\n' (offsets refer to the joined text)."""
        text = "\n".join(paragraphs)
        spans: list[Span] = []
        spans += run_all(self.patterns, text, id_context)
        spans += list(self.persons.find(text))
        spans += list(self.orgs.find(text))
        spans += list(self.addresses.find(text))
        for rec in self.custom:
            spans += list(rec.find(text, id_context))
        if self.ner is not None:
            offs, pos = [], 0
            for p in paragraphs:
                offs.append(pos)
                pos += len(p) + 1
            spans += list(self.ner.find_many(paragraphs, offs))
        return self.resolve(spans)

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _norm(s: str) -> str:
        return re.sub(r"\s+", " ", s).strip().lower()

    def _allowed(self, sp: Span) -> bool:
        if sp.type in self.config.disabled_types or sp.score < self.config.min_score:
            return False
        n = self._norm(sp.text)
        if sp.type in (T.ORG, T.PERSON) and (n in self._allow or any(n.endswith(" " + a) or n == a for a in self._allow)):
            return False
        if sp.type in (T.URL, T.EMAIL):
            host = re.sub(r"^(?:https?://)?(?:www\.)?", "", n.split("@")[-1]).split("/")[0]
            if any(host == d or host.endswith("." + d) for d in self.config.allowlist_domains):
                return False
        return True

    def resolve(self, spans: list[Span]) -> list[Span]:
        """Keep the best non-overlapping set: higher score first, then longer span."""
        def tier(s: Span) -> int:  # structured, checksum-backed hits > addresses > free-text entities
            return 0 if s.score >= 0.9 else (1 if s.type is T.ADDRESS else 2)
        cands = sorted((s for s in spans if self._allowed(s)),
                       key=lambda s: (tier(s), -s.score, -(s.end - s.start), s.start))
        kept: list[Span] = []
        for c in cands:
            if not any(c.overlaps(k) for k in kept):
                kept.append(c)
        return sorted(kept, key=lambda s: s.start)
