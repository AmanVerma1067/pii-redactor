"""Command line entry point.

    python -m pii_redactor.cli "Red Herring Prospectus.docx" -o redacted.docx --mapping map.json --report report.json
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from .pipeline import RedactionConfig, Redactor


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Pseudonymize PII in a .docx (text, tables, headers, images).")
    ap.add_argument("input", type=Path)
    ap.add_argument("-o", "--output", type=Path)
    ap.add_argument("--mapping", type=Path, help="write original->pseudonym JSON (SENSITIVE: re-identification key)")
    ap.add_argument("--report", type=Path, help="write detection/processing report JSON")
    ap.add_argument("--salt", default="scaler-ai-labs", help="secret that seeds deterministic pseudonyms")
    ap.add_argument("--image-policy", choices=["replace", "mask", "blur"], default="replace")
    ap.add_argument("--no-ocr", action="store_true", help="skip embedded image scanning")
    ap.add_argument("--ocr-lang", default="eng", help="tesseract languages, e.g. eng+hin")
    ap.add_argument("--spacy-model", default=None, help="optional spaCy model, e.g. en_core_web_lg")
    ap.add_argument("--allow", action="append", default=[], help="extra organisation/person names never to redact")
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO if a.verbose else logging.WARNING, format="%(levelname)s %(message)s")

    cfg = RedactionConfig(salt=a.salt, enable_ocr=not a.no_ocr, image_policy=a.image_policy,
                          ocr_lang=a.ocr_lang, spacy_model=a.spacy_model, extra_allowlist=a.allow)
    res = Redactor(cfg).redact(a.input)
    out = a.output or a.input.with_name(a.input.stem + "_redacted.docx")
    res.save(out)
    if a.mapping:
        a.mapping.write_text(json.dumps(res.mapping, indent=2, ensure_ascii=False))
    if a.report:
        a.report.write_text(json.dumps(res.report, indent=2, ensure_ascii=False, default=str))
    r = res.report
    print(f"✔ {out}  |  {r['entities_unique']} unique entities  |  "
          f"{r['replacements']['paragraph_spans']} text replacements  |  "
          f"{sum(len(i.get('hits', [])) for i in r['images'])} image regions  |  {r['seconds']}s")
    print("  by class:", json.dumps(r["entities_by_class"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
