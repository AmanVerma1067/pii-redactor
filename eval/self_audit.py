"""Self-consistency leak audit for a document that has no ground truth (e.g. the real RHP).

Every original value the redactor itself detected (mapping.json) is searched for in the OUTPUT package
with the same matcher as the benchmark leak test: re-joined paragraph text, every other XML text node
and attribute, external relationship targets, and OCR of the output images. It also checks that every
XML part still parses and that the package re-opens. It cannot find PII the detector never saw: that
needs a ground truth (eval/annotate.py).

    python eval/self_audit.py Red_Herring_Prospectus_Redacted.docx mapping.json [--out audit.json]
"""
from __future__ import annotations

import argparse
import json
import sys
import zipfile
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from lxml import etree  # noqa: E402

from evaluate import harvest, present  # noqa: E402
from pii_redactor.entities import EntityType as T  # noqa: E402


def xml_integrity(path: Path) -> dict:
    errors = []
    with zipfile.ZipFile(path) as z:
        bad_zip = z.testzip()
        names = [n for n in z.namelist() if n.endswith((".xml", ".rels"))]
        for n in names:
            try:
                etree.fromstring(z.read(n))
            except etree.XMLSyntaxError as exc:
                errors.append(f"{n}: {exc}")
    return {"xml_parts": len(names), "xml_errors": errors, "zip_crc_error": bad_zip}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("docx", type=Path)
    ap.add_argument("mapping", type=Path)
    ap.add_argument("--no-ocr", action="store_true")
    ap.add_argument("--out", type=Path)
    a = ap.parse_args()

    mapping = json.loads(a.mapping.read_text())
    blobs, ocr_blobs = harvest(a.docx.read_bytes(), ocr=not a.no_ocr)
    leaks, checked = [], Counter()
    for m in mapping:
        et = T(m["type"])
        checked[et.value] += 1
        where = [n for n, b in (("xml", blobs), ("ocr", ocr_blobs)) if present(m["original"], et, b)]
        if where:
            leaks.append({"type": et.value, "original": m["original"], "found_in": where})
    res = {"values_checked": len(mapping), "by_type": dict(checked), "leaks": leaks,
           "images_ocrd": len(ocr_blobs), **xml_integrity(a.docx)}
    if a.out:
        a.out.write_text(json.dumps(res, indent=2, ensure_ascii=False))
    print(f"{len(mapping)} detected values checked, {len(leaks)} still present in output; "
          f"{res['images_ocrd']} images OCR'd; {res['xml_parts']} XML parts, {len(res['xml_errors'])} parse errors")
    for lk in leaks:
        print(f"  LEAK {lk['type']}: {lk['original']!r} ({', '.join(lk['found_in'])})")
    return 1 if leaks or res["xml_errors"] or res["zip_crc_error"] else 0


if __name__ == "__main__":
    sys.exit(main())
