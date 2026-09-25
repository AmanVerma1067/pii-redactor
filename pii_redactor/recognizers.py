"""Deterministic pattern recognizers (regex + validators + context words)."""
from __future__ import annotations

import datetime
import re
from dataclasses import dataclass, field
from typing import Callable, Iterable, Iterator

from .entities import EntityType as T, Span
from .validators import digits, ip_ok, luhn_ok, phone_digits_ok, verhoeff_ok

WS = r"[ \u00a0]"  # horizontal whitespace only: entities never span paragraph/line breaks

MONTHS = (r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|June?|July?|Aug(?:ust)?|"
          r"Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)")
DATE = (rf"(?:\d{{1,2}}[/\-.]\d{{1,2}}[/\-.](?:\d{{4}}|\d{{2}})"
        rf"|\d{{1,2}}(?:st|nd|rd|th)?{WS}+{MONTHS}\.?,?{WS}+\d{{4}}"
        rf"|{MONTHS}\.?{WS}+\d{{1,2}}(?:st|nd|rd|th)?,?{WS}+\d{{4}})")
DATE_RE = re.compile(rf"(?<![\w/.-]){DATE}(?![\w/-])", re.I)
MIN_BIRTH_YEAR = 1920
# "Tel: 91-20-2721 8080" parses as dd-mm-yyyy; a date right after a phone/fax label is never a birth date
PHONE_LABEL_BEFORE = re.compile(r"(?i)\b(?:tel(?:ephone)?|fax|phone|ph|mob(?:ile)?)\.?\s*(?:no\.?\s*)?[:\-]?\s*\+?$")


@dataclass
class PatternRecognizer:
    name: str
    etype: T
    pattern: re.Pattern
    score: float = 0.9
    group: int = 0
    validator: Callable[[str], bool] | None = None
    context: tuple[str, ...] = ()        # at least one must occur in the window before the match
    context_window: int = 40
    context_bypass_in_id_image: bool = False
    postprocess: Callable[[str, int, int], tuple[int, int] | None] | None = None

    def find(self, text: str, id_context: bool = False) -> Iterator[Span]:
        for m in self.pattern.finditer(text):
            s, e = m.span(self.group)
            if s < 0:
                continue
            if self.postprocess:
                r = self.postprocess(text, s, e)
                if r is None:
                    continue
                s, e = r
            val = text[s:e]
            if self.validator and not self.validator(val):
                continue
            if self.context and not (id_context and self.context_bypass_in_id_image):
                win = text[max(0, m.start() - self.context_window):m.start()].lower()
                if not any(c in win for c in self.context):
                    continue
            yield Span(s, e, self.etype, val, self.score, self.name)


def _trim_phone(text: str, s: int, e: int) -> tuple[int, int] | None:
    """Greedy international-number matches may swallow a trailing number; drop groups until valid."""
    val = text[s:e]
    while len(digits(val)) > 13:
        cut = max(val.rfind(" "), val.rfind("-"), val.rfind("."))
        if cut <= 0:
            return None
        val = val[:cut]
    if len(digits(val)) < 10:
        return None
    return s, s + len(val.rstrip(" -."))


def _trim_url(text: str, s: int, e: int) -> tuple[int, int] | None:
    val = text[s:e].rstrip(".,;:)]}'\"")
    return (s, s + len(val)) if len(val) > 6 else None


def _aadhaar_ok_factory():
    def ok(val: str) -> bool:
        d = digits(val)
        if len(d) != 12:
            return False
        grouped = bool(re.fullmatch(r"\d{4}[ \-]\d{4}[ \-]\d{4}", val))
        return grouped or verhoeff_ok(d)
    return ok


def _dob_ok(val: str) -> bool:
    """Reject impossible dates: day 1-31, month 1-12, four-digit year within a plausible birth range."""
    nums = [int(n) for n in re.findall(r"\d+", val)]
    year = next((n for n in nums if n >= 100), None)
    if year is not None and not MIN_BIRTH_YEAR <= year <= datetime.date.today().year:
        return False
    if re.match(r"\d{1,2}[/\-.]\d{1,2}[/\-.]", val):
        a, b = nums[0], nums[1]
        return 1 <= a <= 31 and 1 <= b <= 31 and min(a, b) <= 12
    day = next((n for n in nums if n < 100), None)
    return day is None or 1 <= day <= 31


def _dob_not_phone(text: str, s: int, e: int) -> tuple[int, int] | None:
    return None if PHONE_LABEL_BEFORE.search(text[max(0, s - 20):s]) else (s, e)


def build_pattern_recognizers() -> list[PatternRecognizer]:
    R = PatternRecognizer
    c = re.compile
    return [
        R("email", T.EMAIL, c(r"(?<![\w.+-])[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}\b"), 0.97),
        R("url", T.URL, c(r"(?<![\w@/])(?:https?://|www\.)[^\s<>\"']+", re.I), 0.6, postprocess=_trim_url),
        R("gstin", T.GSTIN, c(r"\b\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]\b"), 0.97),
        R("pan", T.PAN, c(r"\b[A-Z]{3}[ABCFGHLJPTK][A-Z]\d{4}[A-Z]\b"), 0.95),
        R("cin", T.CIN, c(r"\b[LU]\d{5}[A-Z]{2}\d{4}[A-Z]{3}\d{6}\b"), 0.98),
        R("llpin", T.LLPIN, c(r"\b[A-Z]{3}-\d{4}\b"), 0.9, context=("llpin", "llp identification")),
        R("din", T.DIN, c(r"\bDIN\b\.?(?:\s*(?:No\.?|Number))?\s*[:\-–]?\s*(\d{8})\b"), 0.97, group=1),
        R("sebi_reg", T.SEBI_REG, c(r"\bIN[A-DF-Z]\d{9}\b"), 0.95),
        R("ifsc", T.IFSC, c(r"\b[A-Z]{4}0[A-Z0-9]{6}\b"), 0.9),
        R("passport", T.PASSPORT, c(r"\b[A-Z][1-9]\d{6}\b"), 0.85, context=("passport",)),  # context-gated
        R("aadhaar", T.AADHAAR, c(r"(?<![\d\-])(?<!\d )[2-9]\d{3}[ \-]?\d{4}[ \-]?\d{4}(?![\d\-])(?! \d)"), 0.95,
          validator=_aadhaar_ok_factory()),
        R("credit_card", T.CREDIT_CARD, c(r"(?<![\d\-])(?:[3-6]\d{3})(?:[ \-]?\d{4}){2}[ \-]?\d{1,7}(?![\d\-])"), 0.93,
          validator=luhn_ok),
        R("bank_account", T.BANK_ACCOUNT, c(r"(?<![\w.,])\d{9,18}(?!\w|,\d)"), 0.9,
          context=("account no", "account number", "a/c", "acct", "bank account", "account:"), context_window=30),
        R("ssn", T.SSN, c(r"(?<![\d-])(?!000|666|9\d\d)\d{3}-(?!00)\d{2}-(?!0000)\d{4}(?![\d-])"), 0.9),
        R("ipv4", T.IP_ADDRESS, c(r"(?<![\d.])(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)(?!\d|\.\d)"), 0.9,
          validator=ip_ok),
        R("ipv6", T.IP_ADDRESS, c(r"\b(?:[0-9A-Fa-f]{1,4}:){7}[0-9A-Fa-f]{1,4}\b"), 0.9, validator=ip_ok),
        # ---- phones (Indian + international)
        R("phone_intl", T.PHONE, c(r"(?<![\w+])\+\d{1,3}(?:[ .\-]?\(?\d{1,8}\)?){1,5}(?![\w])"), 0.85,
          postprocess=_trim_phone),
        R("phone_landline", T.PHONE, c(r"(?<![\w.,/+])\(?0\d{2,4}\)?[ \-]?\d{3,4}[ \-]?\d{3,5}(?![\w.,/])"), 0.75,
          validator=lambda v: phone_digits_ok(v, 10, 12)),
        R("phone_mobile", T.PHONE, c(r"(?<![\w.,/+])[6-9]\d{4}[ \-]?\d{5}(?![\w.,/])"), 0.8),
        R("phone_mobile_334", T.PHONE, c(r"(?<![\w.,/+])[6-9]\d{2}[ \-]\d{3}[ \-]\d{4}(?![\w.,/])"), 0.75),
        R("phone_tollfree", T.PHONE, c(r"(?<!\w)1800[ \-]?\d{3,4}[ \-]?\d{3,4}(?!\w)"), 0.8),
        R("phone_ctx", T.PHONE, c(r"(?<![\w.,])\(?\d{2,5}\)?(?:[ \-]\d{2,8}){1,3}(?![\w.,])"), 0.7,
          context=("tel", "phone", "mobile", "mob", "fax", "contact no", "ph."), context_window=25,
          validator=lambda v: phone_digits_ok(v, 8, 12)),
        # ---- dates of birth: only with a DOB cue (or anywhere on an ID-card image)
        R("dob", T.DOB, DATE_RE, 0.9,
          context=("dob", "d.o.b", "date of birth", "birth date", "born on", "born", "year of birth", "yob", "जन्म"),
          context_window=45, context_bypass_in_id_image=True, validator=_dob_ok, postprocess=_dob_not_phone),
    ]


def run_all(recognizers: Iterable[PatternRecognizer], text: str, id_context: bool = False) -> list[Span]:
    out: list[Span] = []
    for r in recognizers:
        out.extend(r.find(text, id_context))
    return out
