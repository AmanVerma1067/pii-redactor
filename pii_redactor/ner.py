"""Optional statistical NER adapter (spaCy). The pipeline runs fine without it.

Install e.g. `pip install spacy && python -m spacy download en_core_web_lg` and pass
`--spacy-model en_core_web_lg` (CLI) or tick the box in the Streamlit app.
"""
from __future__ import annotations

import logging
import re
from typing import Iterable, Iterator

from .entities import EntityType as T, Span
from .gazetteer import GENERIC_ORG_WORDS, NAME_STOP

log = logging.getLogger(__name__)
_LABELS = {"PERSON": T.PERSON, "ORG": T.ORG}


class SpacyNER:
    def __init__(self, model: str = "en_core_web_lg"):
        import spacy  # noqa: WPS433 (optional dependency)
        self.nlp = spacy.load(model, disable=["lemmatizer", "textcat"])
        self.nlp.max_length = 2_000_000
        self.model = model

    def find_many(self, texts: Iterable[str], offsets: Iterable[int]) -> Iterator[Span]:
        texts, offsets = list(texts), list(offsets)
        for doc, base in zip(self.nlp.pipe(texts, batch_size=64), offsets):
            for ent in doc.ents:
                et = _LABELS.get(ent.label_)
                if et is None:
                    continue
                val = ent.text.strip()
                if not self._plausible(val, et):
                    continue
                s = base + ent.start_char + (len(ent.text) - len(ent.text.lstrip()))
                yield Span(s, s + len(val), et, val, 0.65, f"spacy:{self.model}")

    @staticmethod
    def _plausible(val: str, et: T) -> bool:
        toks = val.split()
        if not toks or len(val) < 3 or "\n" in val:
            return False
        if et is T.PERSON:
            return (2 <= len(toks) <= 4 and all(t[:1].isupper() for t in toks)
                    and not any(t.lower().strip(".,") in NAME_STOP for t in toks))
        # ORG: must contain at least one distinctive (non-generic, non-stop) capitalised token
        distinct = [t for t in toks if t.lower() not in GENERIC_ORG_WORDS and t.lower() not in NAME_STOP]
        return bool(distinct) and bool(re.search(r"[A-Z]", val)) and len(toks) >= 2


def load_ner(model: str | None):
    if not model:
        return None
    try:
        return SpacyNER(model)
    except Exception as exc:  # pragma: no cover - depends on environment
        log.warning("spaCy model %r unavailable (%s); continuing with regex + heuristics only", model, exc)
        return None
