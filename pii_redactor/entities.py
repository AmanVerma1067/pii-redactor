"""Entity taxonomy shared by every module."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class EntityType(str, Enum):
    PERSON = "PERSON"
    ORG = "ORG"
    EMAIL = "EMAIL"
    PHONE = "PHONE"
    URL = "URL"
    DOMAIN = "DOMAIN"
    ADDRESS = "ADDRESS"
    DOB = "DOB"
    PAN = "PAN"
    AADHAAR = "AADHAAR"
    CIN = "CIN"
    LLPIN = "LLPIN"
    DIN = "DIN"
    SEBI_REG = "SEBI_REG"
    GSTIN = "GSTIN"
    PASSPORT = "PASSPORT"
    IFSC = "IFSC"
    BANK_ACCOUNT = "BANK_ACCOUNT"
    CREDIT_CARD = "CREDIT_CARD"
    IP_ADDRESS = "IP_ADDRESS"
    SSN = "SSN"


T = EntityType

# Reporting classes requested by the evaluation brief.
CLASS_OF: dict[EntityType, str] = {
    T.PERSON: "Names",
    T.ORG: "Organizations",
    T.ADDRESS: "Addresses",
    T.EMAIL: "Contacts", T.PHONE: "Contacts", T.URL: "Contacts", T.DOMAIN: "Contacts",
    T.DOB: "DOB",
    T.CREDIT_CARD: "Financial", T.BANK_ACCOUNT: "Financial", T.IFSC: "Financial",
}
for _t in T:
    CLASS_OF.setdefault(_t, "Identifiers")

# Types whose pseudonym is produced by format-preserving alphanumeric substitution.
ALNUM_TYPES = {
    T.PAN, T.AADHAAR, T.CIN, T.LLPIN, T.DIN, T.SEBI_REG, T.GSTIN, T.PASSPORT,
    T.IFSC, T.BANK_ACCOUNT, T.CREDIT_CARD, T.SSN, T.PHONE,
}


@dataclass(frozen=True)
class Span:
    """A detected entity inside a piece of text."""
    start: int
    end: int
    type: EntityType
    text: str
    score: float
    source: str

    def overlaps(self, other: "Span") -> bool:
        return self.start < other.end and other.start < self.end
