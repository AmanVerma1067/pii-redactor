"""Context-aware heuristic recognizers for free-text entities (names, organisations, addresses).

They complement the optional statistical NER (spaCy) and make the tool useful even with no model
installed. Every recognizer returns `Span`s with offsets into the text it was given.
"""
from __future__ import annotations

import re
from typing import Iterator

from .entities import EntityType as T, Span
from .gazetteer import (FIRST_NAMES, HONORIFICS, NAME_STOP, SURNAMES)
from .recognizers import WS

NAME_TOKEN = r"(?:[A-Z][a-z]+(?:['’\-][A-Za-z]+)?|[A-Z]{2,}|[A-Z]\.)"
HON = r"(?:" + "|".join(HONORIFICS) + r")\.?"
_TOKEN_RE = re.compile(NAME_TOKEN)


def _tok_key(tok: str) -> str:
    return tok.lower().strip(".'’")


def _is_stop(tok: str) -> bool:
    return _tok_key(tok) in NAME_STOP


def _tokens_with_pos(text: str, base: int = 0) -> list[tuple[str, int, int]]:
    return [(m.group(), base + m.start(), base + m.end()) for m in re.finditer(r"\S+", text)]


# --------------------------------------------------------------------------- persons
class PersonRecognizer:
    """Honorific-, label-, gazetteer- and table-context-based person-name detection."""

    honorific_re = re.compile(rf"(?<![\w])(?:{HON}){WS}+({NAME_TOKEN}(?:{WS}+{NAME_TOKEN}){{0,3}})(?![\w])")
    cap_run_re = re.compile(rf"(?<![\w.]){NAME_TOKEN}(?:{WS}+{NAME_TOKEN})+(?![\w])")
    label_re = re.compile(
        r"(?i)\b(?:name|contact person|company secretary(?: and compliance officer)?|compliance officer|"
        r"father'?s name|mother'?s name|spouse'?s? name|husband'?s name|s/o|d/o|w/o|c/o|son of|daughter of|wife of)"
        r"([ \t]*[:\-–][ \t]*|[ \t]+)"
        rf"(?:{HON}[ \t]+)?"
        r"([A-Za-z][A-Za-z.'’\-]*(?:[ \t]+[A-Za-z][A-Za-z.'’\-]*){0,3})")

    def find(self, text: str) -> Iterator[Span]:
        yield from self._honorific(text)
        yield from self._labels(text)
        yield from self._gazetteer(text)

    # "Mr. Kushal Subbayya Hegde", "Ms. Shetty"
    def _honorific(self, text: str) -> Iterator[Span]:
        for m in self.honorific_re.finditer(text):
            s, e = m.span(1)
            toks = [(t.group(), s + t.start(), s + t.end()) for t in _TOKEN_RE.finditer(text[s:e])]
            while toks and _is_stop(toks[-1][0]):
                toks.pop()
            if toks and not any(_is_stop(t[0]) for t in toks):
                yield Span(toks[0][1], toks[-1][2], T.PERSON, text[toks[0][1]:toks[-1][2]], 0.88, "honorific")

    # "Contact Person: Ms. Anjali Kulkarni", "S/O Sudhdan Khan"
    def _labels(self, text: str) -> Iterator[Span]:
        for m in self.label_re.finditer(text):
            explicit = bool(re.search(r"[:\-–]", m.group(1)))
            s, e = m.span(2)
            if not explicit and not text[s:s + 1].isupper():
                continue  # "Compliance Officer is responsible..." is prose, not a label
            toks = _tokens_with_pos(text[s:e], s)
            keep = []
            for tok, a, b in toks:
                if _is_stop(tok) or not re.fullmatch(r"[A-Za-z.'’\-]+", tok):
                    break
                keep.append((tok, a, b))
            if keep and (len(keep) >= 2 or _tok_key(keep[0][0]) in SURNAMES | FIRST_NAMES):
                a, b = keep[0][1], keep[-1][2]
                yield Span(a, b, T.PERSON, text[a:b], 0.8, "label")

    # capitalised sequences anchored on the name gazetteer
    def _gazetteer(self, text: str) -> Iterator[Span]:
        for m in self.cap_run_re.finditer(text):
            toks = [(t.group(), m.start() + t.start(), m.start() + t.end()) for t in _TOKEN_RE.finditer(m.group())]
            segment: list = []
            for tok in toks + [("<END>", -1, -1)]:
                if tok[0] == "<END>" or _is_stop(tok[0]):
                    yield from self._judge(text, segment)
                    segment = []
                else:
                    segment.append(tok)

    def _judge(self, text: str, seg: list) -> Iterator[Span]:
        if len(seg) < 2:
            return
        windows = [seg] if len(seg) <= 4 else [seg[i:i + 3] for i in range(len(seg) - 2)
                                               if _tok_key(seg[i][0]) in FIRST_NAMES]
        for w in windows:
            keys = [_tok_key(t[0]) for t in w]
            first_ok = keys[0] in FIRST_NAMES
            last_ok = keys[-1] in SURNAMES
            if first_ok or (last_ok and len(w) >= 2):
                score = 0.8 if (first_ok and last_ok) else 0.7
                yield Span(w[0][1], w[-1][2], T.PERSON, text[w[0][1]:w[-1][2]], score, "gazetteer")


# --------------------------------------------------------------------------- organisations
LEGAL_SUFFIX = re.compile(
    r"(?i:Private" + WS + r"+Limited|Pvt\.?" + WS + r"*Ltd\.?|Pte\.?" + WS + r"+Ltd\.?|Public" + WS +
    r"+Limited|Limited|Ltd\.?|L\.?L\.?P\.?|Incorporated|Inc\.|Corporation|Corp\.|LLC|PLC|GmbH)(?![\w])"
    r"|(?:&|and)" + WS + r"+(?:Co\.?|Associates|Company)(?![\w])"
    r"|Bank(?![\w])")
ORG_TOKEN = re.compile(r"^(?:[A-Z0-9][A-Za-z0-9'’.\-&]*|\([A-Z][A-Za-z]*\)|&|and|of)$")
ORG_LEAD_STOP = set("""
the our m/s messrs book running lead manager managers registrar to issue offer promoter promoters company
selling shareholder shareholders syndicate member members legal counsel statutory auditor auditors bankers
sponsor refund public escrow collection banks name address contact details brlm brlms registered office
corporate subsidiary subsidiaries group entity entities director directors and of with by from for in at
as a an is are was were joint global coordinator coordinators domestic international indian lenders lender
prospectus red herring draft dated agreement between among
""".split())


class OrgRecognizer:
    """Finds '<Distinctive Tokens> <Legal Suffix>' organisation names by walking back from the suffix."""

    max_tokens = 6

    def find(self, text: str) -> Iterator[Span]:
        for m in LEGAL_SUFFIX.finditer(text):
            s_suffix, e = m.span()
            tail = re.match(rf"{WS}+of{WS}+[A-Z][a-z]+", text[e:])
            if m.group().lower().startswith("bank") and tail:
                e += tail.end()
            line_start = text.rfind("\n", 0, s_suffix) + 1
            prefix = text[line_start:s_suffix]
            if prefix and not prefix[-1] in " \u00a0":
                continue  # suffix glued to a word, e.g. "XYZBank"
            raw = [(mm.group(), line_start + mm.start()) for mm in re.finditer(r"\S+", prefix)]
            toks: list[tuple[str, int]] = []
            for tok, pos in reversed(raw):
                if len(toks) >= self.max_tokens or not ORG_TOKEN.match(tok) or tok.endswith(","):
                    break
                toks.insert(0, (tok, pos))
            while toks and (toks[0][0].lower().strip("().,") in ORG_LEAD_STOP or toks[0][0] == "&"):
                toks.pop(0)
            if not toks or all(t[0].lower() in ("and", "of", "&") for t in toks):
                continue
            start = toks[0][1]
            score = 0.6 if m.group() == "Bank" else 0.85
            yield Span(start, e, T.ORG, text[start:e], score, "legal_suffix")


# --------------------------------------------------------------------------- addresses
PIN_RE = re.compile(r"(?<![\d,.₹])([1-9]\d{2}[ ]?\d{3})(?![\d%]|[,.]\d)")
ADDR_CUES = re.compile(
    r"(?i)\b(road|rd|street|lane|marg|nagar|colony|society|plot|survey|gat|house|flat|floor|building|bldg|"
    r"tower|complex|sector|phase|midc|industrial|estate|area|park|village|taluka|tal|district|dist|near|opp|"
    r"behind|chowk|circle|highway|post|block|wing|apartment|residency|bhavan|bhawan|west|east|north|south|"
    r"maharashtra|karnataka|gujarat|delhi|pune|mumbai|bengaluru|bangalore|chennai|hyderabad|kolkata|"
    r"allahabad|prayagraj|uttar pradesh|u\.p|up|raigad|thane|india|kurla|bandra|vikhroli|unit|shop)\b")
STATES = (r"(?:Maharashtra|Karnataka|Gujarat|Delhi|New Delhi|Tamil Nadu|Telangana|Kerala|West Bengal|"
          r"Uttar Pradesh|U\.P\.|UP|Rajasthan|Madhya Pradesh|Haryana|Punjab|Goa|Bihar|Odisha|Andhra Pradesh)")
ADDR_TAIL = re.compile(rf"^(?:[ ,\-–]*{STATES})?(?:[ ,\-–]*India)?", re.I)
ADDR_LEAD = re.compile(r"(?i)(?:office|address|situated at|located at|residing at|resident of|premises at|"
                       r"at|factory|plant|unit)\s*[:\-–]?\s*$")
RELATION_PREFIX = re.compile(r"(?i)^(?:[sdwc]\s*/\s*o|son of|daughter of|wife of|care of)\s*[:.]?\s*"
                             r"[A-Za-z][A-Za-z.'’\-]*(?:\s+[A-Za-z][A-Za-z.'’\-]*){0,3}\s*,\s*")
ABBR = {"no", "nos", "opp", "st", "rd", "tal", "dist", "nr", "bldg", "p.o", "po", "mr", "mrs", "ms", "dr",
        "co", "ltd", "pvt", "sec", "ph", "plot", "l.b.s", "b", "a", "c"}


class AddressRecognizer:
    max_back = 260

    def find(self, text: str) -> Iterator[Span]:
        for m in PIN_RE.finditer(text):
            pin_s, pin_e = m.span(1)
            window = text[max(0, pin_s - 160):pin_s]
            if len(ADDR_CUES.findall(window)) < 1:
                continue
            start = self._walk_back(text, pin_s)
            tail = ADDR_TAIL.match(text[pin_e:])
            end = pin_e + (tail.end() if tail else 0)
            val = text[start:end].strip(" ,;-–")
            if not val:
                continue
            start = text.index(val, start)
            end = start + len(val)
            if val.count(",") + val.count("\n") < 2 and len(ADDR_CUES.findall(val)) < 2:
                continue
            yield Span(start, end, T.ADDRESS, val, 0.82, "pin_anchor")
        # "Address: ..." up to end of line
        for m in re.finditer(r"(?i)\baddress\b\s*[:\-–]\s*([^\n]{12,200})", text):
            start, val = m.start(1), m.group(1).rstrip(" .;")
            rel = RELATION_PREFIX.match(val)  # "S/O Sudhdan Khan, saray dan shah" -> person is not address
            if rel:
                start, val = start + rel.end(), val[rel.end():]
            if "," in val and not PIN_RE.search(val):
                yield Span(start, start + len(val), T.ADDRESS, val, 0.7, "address_label")

    def _walk_back(self, text: str, pin_s: int) -> int:
        i = pin_s
        lo = max(0, pin_s - self.max_back)
        while i > lo:
            ch = text[i - 1]
            if ch in ":;|\t":
                break
            if ch == "\n":
                prev = text[:i - 1].rstrip(" ")
                if not prev.endswith(","):
                    break
            if ch == "." and i < len(text) and text[i:i + 1] == " ":
                word = re.search(r"([\w.]+)\.$", text[max(0, i - 12):i])
                w = word.group(1).lower() if word else ""
                if w not in ABBR and not (len(w) <= 2) and not w.replace(".", "").isdigit():
                    break
            i -= 1
        seg = text[i:pin_s]
        orgs = list(re.finditer(r"(?i)\b(?:limited|ltd\.?|llp|bank)[ ]*,[ ]*", seg))
        if orgs:  # "XYZ Limited, 801 Wing A, ..." -> the organisation is not part of the address
            i += orgs[-1].end()
            seg = text[i:pin_s]
        lead = re.search(r"(?i)\b(?:situated at|located at|residing at|resident of|premises at|office at|is at|at)\s+", seg)
        if lead and lead.start() < 40:
            i += lead.end()
        return i


# --------------------------------------------------------------------------- table context
HEADER_RULES = [
    (re.compile(r"(?i)\bdin\b"), T.DIN, re.compile(r"^\d{8}$")),
    (re.compile(r"(?i)\bpan\b"), T.PAN, re.compile(r"^[A-Z]{5}\d{4}[A-Z]$")),
    (re.compile(r"(?i)date of birth|\bdob\b"), T.DOB, re.compile(r"\d")),
    (re.compile(r"(?i)\baddress\b"), T.ADDRESS, re.compile(r".{10,},.+")),
    (re.compile(r"(?i)(company|entity|bank|firm|organi[sz]ation|lender)\b.*\bname\b|\bname of (the )?(company|entity|bank)"),
     T.ORG, re.compile(r"^[A-Z0-9].{2,}$")),
    (re.compile(r"(?i)\bname\b"), T.PERSON, re.compile(rf"^(?:{HON}\s+)?[A-Za-z][A-Za-z.'’\-]*(?:\s+[A-Za-z][A-Za-z.'’\-]*){{1,4}}$")),
]


def classify_header(header: str):
    for rx, et, value_rx in HEADER_RULES:
        if rx.search(header):
            return et, value_rx
    return None


def strip_honorific(name: str) -> tuple[str, str]:
    m = re.match(rf"^({HON}){WS}+", name)
    return (m.group(0), name[m.end():]) if m else ("", name)
