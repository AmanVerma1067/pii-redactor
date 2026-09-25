"""Deterministic pseudonymization and anonymization engine with salt registry.

Provides global, format-preserving, deterministic pseudonyms:
- Individual names -> Realistic synthetic names (maintaining family branch surname links)
- Emails -> Synthetic emails reflecting synthetic names and domains
- Phone numbers -> Valid formatted pseudo-numbers
- Companies / Orgs -> Synthetic enterprise names
- Statutory IDs -> Algorithmic valid-format dummies (PAN, CIN, DIN, SEBI, GSTIN, Aadhaar with Verhoeff)
- Salt registry: HMAC-SHA256 seeded generator guarantees reproducibility and unlinkability.
"""
from __future__ import annotations

from .pseudonymizer import (
    LEGAL_WORDS,
    SEP,
    STATE_CODES,
    Pseudonymizer,
    alnum_key,
    match_case,
    norm_text,
)

# Alias Anonymizer to Pseudonymizer for interface compliance
Anonymizer = Pseudonymizer

__all__ = [
    "Anonymizer",
    "Pseudonymizer",
    "match_case",
    "norm_text",
    "alnum_key",
    "STATE_CODES",
    "LEGAL_WORDS",
    "SEP",
]
