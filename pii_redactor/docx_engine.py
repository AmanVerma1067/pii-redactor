"""WordprocessingML traversal + run-split-safe text replacement.

Why this exists: Word freely splits one visible word across several <w:r> runs (spell-check marks,
rsid revision ids, partial bold...). "Kushal Hegde" may be stored as `Kus|hal He|gde`. Replacing
per-run misses such entities; replacing `paragraph.text` wipes all run formatting.

Strategy: for every <w:p> we build a character map over its *own* <w:t> nodes (skipping nested
text-box paragraphs, which are processed on their own), detect/replace on the concatenated string,
then project each replacement back: the fake text is written into the first run touched by the
entity (inheriting its formatting) and the covered characters are removed from the following runs.
Run properties, hyperlinks, fields, bookmarks and comments ranges are never touched.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterator

from lxml import etree

from .entities import EntityType as T
from .heuristics import classify_header

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W = "{%s}" % W_NS
XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"

SKIP_CT_SUFFIX = ("styles+xml", "settings+xml", "fontTable+xml", "webSettings+xml", "numbering+xml",
                  "theme+xml", "stylesWithEffects+xml")
PROCESS_CT_HINTS = ("wordprocessingml", "core-properties", "extended-properties", "custom-properties",
                    "drawingml.chart", "drawingml.diagramData")
ATTR_REDACT = {"author", "initials", "userId", "providerId", "lastModifiedBy"}
ATTR_REPLACE = {"descr", "title", "instr"}


@dataclass
class XmlPartHandle:
    part: object
    root: etree._Element
    from_blob: bool

    @property
    def name(self) -> str:
        return str(self.part.partname)

    def commit(self) -> None:
        if self.from_blob:
            self.part._blob = etree.tostring(self.root, xml_declaration=True, encoding="UTF-8", standalone=True)


def collect_xml_parts(document) -> list[XmlPartHandle]:
    handles = []
    for part in document.part.package.iter_parts():
        ct = part.content_type
        if not ct.endswith("xml") or ct.endswith(SKIP_CT_SUFFIX) or not any(h in ct for h in PROCESS_CT_HINTS):
            continue
        el = getattr(part, "_element", None)
        if el is not None:
            handles.append(XmlPartHandle(part, el, False))
        else:
            try:
                handles.append(XmlPartHandle(part, etree.fromstring(part.blob), True))
            except etree.XMLSyntaxError:
                continue
    return handles


# ------------------------------------------------------------------ paragraphs
Segment = tuple  # (element | None, text)


def own_segments(p: etree._Element) -> list[Segment]:
    segs: list[Segment] = []

    def walk(node):
        for ch in node:
            tag = ch.tag
            if not isinstance(tag, str):
                continue
            if tag == W + "p" or tag in (W + "del", W + "moveFrom"):
                continue
            if tag.startswith(W) and tag.endswith("Pr"):
                continue
            if tag == W + "t":
                segs.append((ch, ch.text or ""))
            elif tag == W + "tab" or tag == W + "ptab":
                segs.append((None, "\t"))
            elif tag in (W + "br", W + "cr"):
                segs.append((None, "\n"))
            elif tag == W + "noBreakHyphen":
                segs.append((None, "-"))
            else:
                walk(ch)

    walk(p)
    return segs


def paragraph_text(p: etree._Element) -> str:
    return "".join(t for _, t in own_segments(p))


def iter_paragraphs(root: etree._Element) -> Iterator[etree._Element]:
    yield from root.iter(W + "p")


def apply_replacements(segs: list[Segment], reps: list[tuple[int, int, str]]) -> int:
    """Project (start, end, replacement) spans on the concatenated text back onto <w:t> nodes.

    If the original entity and its pseudonym have the same number of words, each fake word is
    written into the run that held the corresponding original word ("Kus|hal Subbayya |Hegde" with
    bold/italic/plain runs -> "Albert" bold, "Thomas" italic, "Allen" plain). Otherwise the whole
    pseudonym goes into the first run touched by the entity. Covered characters are removed from
    every other run, so no run, rPr, hyperlink or field is ever created or destroyed.
    """
    spans, pos = [], 0
    full = "".join(t for _, t in segs)
    for el, txt in segs:
        spans.append((el, pos, pos + len(txt)))
        pos += len(txt)
    applied = 0
    for s, e, repl in sorted(reps, key=lambda r: -r[0]):
        touched = [(el, a, b) for el, a, b in spans if el is not None and a < e and b > s and a != b]
        if not touched:
            continue
        # decide which fake text goes into which run
        pieces: dict[int, str] = {}
        orig_words = [(m.start() + s) for m in re.finditer(r"\S+", full[s:e])]
        fake_parts = re.findall(r"\S+\s*", repl)
        if len(touched) > 1 and len(orig_words) == len(fake_parts) > 1:
            for w_start, piece in zip(orig_words, fake_parts):
                idx = next((i for i, (_, a, b) in enumerate(touched) if a <= w_start < b), 0)
                pieces[idx] = pieces.get(idx, "") + piece
            lead = repl[:len(repl) - len(repl.lstrip())]
            pieces[min(pieces)] = lead + pieces[min(pieces)]
        else:
            pieces[0] = repl
        for i, (el, a, b) in enumerate(touched):
            text = el.text or ""
            ls, le = max(s, a) - a, min(e, b) - a
            el.text = text[:ls] + pieces.get(i, "") + text[le:]
            el.set(XML_SPACE, "preserve")
        applied += 1
    return applied


def replace_in_paragraphs(root: etree._Element, pseudo) -> int:
    n = 0
    for p in iter_paragraphs(root):
        segs = own_segments(p)
        text = "".join(t for _, t in segs)
        if not text.strip():
            continue
        reps = pseudo.replace_spans(text)
        if reps:
            n += apply_replacements(segs, reps)
    return n


# ------------------------------------------------------------------ non-run text & attributes
def scrub_generic(root: etree._Element, pseudo) -> int:
    """Field codes, tracked deletions, DrawingML/chart text, alt-text, core/app props, authors."""
    n = 0
    for el in root.iter():
        if not isinstance(el.tag, str):
            continue
        if el.tag != W + "t" and el.text and el.text.strip():
            new = pseudo.replace_text(el.text)
            if new != el.text:
                el.text, n = new, n + 1
        for attr in list(el.attrib):
            local = attr.split("}")[-1]
            if local in ATTR_REDACT:
                el.set(attr, "Redacted")
            elif local in ATTR_REPLACE or (local == "name" and el.tag.endswith(("docPr", "cNvPr"))):
                v = el.get(attr)
                nv = pseudo.replace_text(v)
                if nv != v:
                    el.set(attr, nv)
                    n += 1
    return n


def scrub_relationships(document, pseudo) -> int:
    n = 0
    for part in document.part.package.iter_parts():
        for rel in part.rels.values():
            if rel.is_external:
                t = rel.target_ref
                nt = pseudo.replace_text(t)
                if nt != t:
                    rel._target = nt
                    n += 1
    return n


# ------------------------------------------------------------------ pass-1 helpers
def part_paragraph_texts(root: etree._Element) -> list[str]:
    return [paragraph_text(p) for p in iter_paragraphs(root)]


def _cell_text(tc) -> str:
    return "\n".join(paragraph_text(p) for p in tc.iter(W + "p")).strip()


def table_context_entities(root: etree._Element) -> Iterator[tuple[str, T]]:
    """Column-header ("DIN", "Name", "PAN"...) and row-key ("DIN | 00135070") table semantics."""
    for tbl in root.iter(W + "tbl"):
        grid = [[_cell_text(tc) for tc in tr if tc.tag == W + "tc"] for tr in tbl if tr.tag == W + "tr"]
        if not grid:
            continue
        header = grid[0]
        rules = [classify_header(h) if len(h) < 60 else None for h in header]
        for row in grid[1:]:
            for j, cell in enumerate(row):
                if j < len(rules) and rules[j] and cell:
                    et, rx = rules[j]
                    for line in ([cell] if et is T.ADDRESS else cell.split("\n")):
                        if rx.search(line.strip()):
                            yield line.strip(), et
        for row in grid:  # key/value tables
            if len(row) >= 2 and row[0] and len(row[0]) < 40:
                rule = classify_header(row[0])
                if rule and row[1]:
                    et, rx = rule
                    val = row[1].strip()
                    if rx.search(val if et is T.ADDRESS else val.split("\n")[0]):
                        yield (val if et is T.ADDRESS else val.split("\n")[0]), et
