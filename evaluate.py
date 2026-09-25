#!/usr/bin/env python3
"""Benchmark evaluation script for PII Redaction & Pseudonymization Engine.

Calculates:
  - Precision = TP / (TP + FP)
  - Recall    = TP / (TP + FN)
  - F1-Score  = 2 * P * R / (P + R)
  - Accuracy (CSI/Jaccard) = TP / (TP + FP + FN)

Per-category breakdown:
  - Names, Organizations, Identifiers, Financial, Addresses, Contacts, DOB, Images
Confusion matrix and false positives vs false negatives analysis.
End-to-end leak testing across XML runs, attributes, and embedded image OCR.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from eval.evaluate import main

if __name__ == "__main__":
    raise SystemExit(main())
