"""Compiled regex rules for Indian CIN, PAN, DIN, Phone, Email, and other identifiers.

This module houses the regex pattern definitions and validator-backed recognizers
specifically tuned for Indian statutory documents and corporate filings.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, Iterable, Iterator

from .entities import EntityType as T, Span
from .validators import digits, ip_ok, luhn_ok, phone_digits_ok, verhoeff_ok

WS = r"[ \u00a0]"  # horizontal whitespace only

# ---------------------------------------------------------------------------
# Compiled regex rules for Indian identifiers and personal data
# ---------------------------------------------------------------------------
CIN_RE = re.compile(r"\b[LU]\d{5}[A-Z]{2}\d{4}[A-Z]{3}\d{6}\b")
PAN_RE = re.compile(r"\b[A-Z]{3}[ABCFGHLJPTK][A-Z]\d{4}[A-Z]\b")
DIN_RE = re.compile(r"\bDIN\b\.?(?:\s*(?:No\.?|Number))?\s*[:\-–]?\s*(\d{8})\b")
SEBI_REG_RE = re.compile(r"\b(?:IN[A-Z]{1,2}|INBI)\d{7,9}\b")
GSTIN_RE = re.compile(r"\b\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]\b")
LLPIN_RE = re.compile(r"\b[A-Z]{3}-\d{4}\b")
IFSC_RE = re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b")
PASSPORT_RE = re.compile(r"\b[A-Z][1-9]\d{6}\b")
AADHAAR_RE = re.compile(r"(?<![\d\-])(?<!\d )[2-9]\d{3}[ \-]?\d{4}[ \-]?\d{4}(?![\d\-])(?! \d)")

EMAIL_RE = re.compile(r"(?<![\w.+-])[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}\b")
URL_RE = re.compile(r"(?<![\w@/])(?:https?://|www\.)[^\s<>\"']+", re.I)

PHONE_INTL_RE = re.compile(r"(?<![\w+])\+\d{1,3}(?:[ .\-]?\(?\d{1,8}\)?){1,5}(?![\w])")
PHONE_LANDLINE_RE = re.compile(r"(?<![\w.,/+])\(?0\d{2,4}\)?[ \-]?\d{3,4}[ \-]?\d{3,5}(?![\w.,/])")
PHONE_MOBILE_RE = re.compile(r"(?<![\w.,/+])[6-9]\d{4}[ \-]?\d{5}(?![\w.,/])")
PHONE_MOBILE_334_RE = re.compile(r"(?<![\w.,/+])[6-9]\d{2}[ \-]\d{3}[ \-]\d{4}(?![\w.,/])")
PHONE_TOLLFREE_RE = re.compile(r"(?<!\w)1800[ \-]?\d{3,4}[ \-]?\d{3,4}(?!\w)")
PHONE_CTX_RE = re.compile(r"(?<![\w.,])\(?\d{2,5}\)?(?:[ \-]\d{2,8}){1,3}(?![\w.,])")

CREDIT_CARD_RE = re.compile(r"(?<![\d\-])(?:[3-6]\d{3})(?:[ \-]?\d{4}){2}[ \-]?\d{1,7}(?![\d\-])")
BANK_ACCOUNT_RE = re.compile(r"(?<![\w.,])\d{9,18}(?!\w|,\d)")
SSN_RE = re.compile(r"(?<![\d-])(?!000|666|9\d\d)\d{3}-(?!00)\d{2}-(?!0000)\d{4}(?![\d-])")
IPV4_RE = re.compile(r"(?<![\d.])(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)(?!\d|\.\d)")
IPV6_RE = re.compile(r"\b(?:[0-9A-Fa-f]{1,4}:){7}[0-9A-Fa-f]{1,4}\b")

MONTHS = (r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|June?|July?|Aug(?:ust)?|"
          r"Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)")
DATE = (rf"(?:\d{{1,2}}[/\-.]\d{{1,2}}[/\-.](?:\d{{4}}|\d{{2}})"
        rf"|\d{{1,2}}(?:st|nd|rd|th)?{WS}+{MONTHS}\.?,?{WS}+\d{{4}}"
        rf"|{MONTHS}\.?{WS}+\d{{1,2}}(?:st|nd|rd|th)?,?{WS}+\d{{4}})")
DATE_RE = re.compile(rf"(?<![\w/.-]){DATE}(?![\w/-])", re.I)


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


def build_pattern_recognizers() -> list[PatternRecognizer]:
    R = PatternRecognizer
    return [
        R("email", T.EMAIL, EMAIL_RE, 0.97),
        R("url", T.URL, URL_RE, 0.6, postprocess=_trim_url),
        R("gstin", T.GSTIN, GSTIN_RE, 0.97),
        R("pan", T.PAN, PAN_RE, 0.95),
        R("cin", T.CIN, CIN_RE, 0.98),
        R("llpin", T.LLPIN, LLPIN_RE, 0.9, context=("llpin", "llp identification")),
        R("din", T.DIN, DIN_RE, 0.97, group=1),
        R("sebi_reg", T.SEBI_REG, SEBI_REG_RE, 0.95),
        R("ifsc", T.IFSC, IFSC_RE, 0.9),
        R("passport", T.PASSPORT, PASSPORT_RE, 0.85, context=("passport",)),
        R("aadhaar", T.AADHAAR, AADHAAR_RE, 0.95, validator=_aadhaar_ok_factory()),
        R("credit_card", T.CREDIT_CARD, CREDIT_CARD_RE, 0.93, validator=luhn_ok),
        R("bank_account", T.BANK_ACCOUNT, BANK_ACCOUNT_RE, 0.9,
          context=("account no", "account number", "a/c", "acct", "bank account", "account:"), context_window=30),
        R("ssn", T.SSN, SSN_RE, 0.9),
        R("ipv4", T.IP_ADDRESS, IPV4_RE, 0.9, validator=ip_ok),
        R("ipv6", T.IP_ADDRESS, IPV6_RE, 0.9, validator=ip_ok),
        # ---- phones
        R("phone_intl", T.PHONE, PHONE_INTL_RE, 0.85, postprocess=_trim_phone),
        R("phone_landline", T.PHONE, PHONE_LANDLINE_RE, 0.75, validator=lambda v: phone_digits_ok(v, 10, 12)),
        R("phone_mobile", T.PHONE, PHONE_MOBILE_RE, 0.8),
        R("phone_mobile_334", T.PHONE, PHONE_MOBILE_334_RE, 0.75),
        R("phone_tollfree", T.PHONE, PHONE_TOLLFREE_RE, 0.8),
        R("phone_ctx", T.PHONE, PHONE_CTX_RE, 0.7,
          context=("tel", "phone", "mobile", "mob", "fax", "contact no", "ph."), context_window=25,
          validator=lambda v: phone_digits_ok(v, 8, 12)),
        # ---- dates of birth
        R("dob", T.DOB, DATE_RE, 0.9,
          context=("dob", "d.o.b", "date of birth", "birth date", "born on", "born", "year of birth", "yob", "जन्म"),
          context_window=45, context_bypass_in_id_image=True),
    ]


def run_all(recognizers: Iterable[PatternRecognizer], text: str, id_context: bool = False) -> list[Span]:
    out: list[Span] = []
    for r in recognizers:
        out.extend(r.find(text, id_context))
    return out
