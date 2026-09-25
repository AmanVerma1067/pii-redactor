"""Human-in-the-loop ground truth for a REAL document (e.g. the 400+ page RHP).

1) propose:  python eval/annotate.py propose "Red Herring Prospectus.docx" --csv eval/rhp_review.csv
   -> one row per unique candidate (type, value, 3 context snippets, detector rule) with an empty
      `label` column. Also runs OCR over embedded images.
2) review the CSV in Excel/Sheets:
      label = TP  (correct PII)          label = FP  (not PII; kept as an over-redaction trap)
      label = TYPE:<ENTITY> (right span, wrong type, e.g. TYPE:ORG)
      and APPEND rows for anything missed with label = FN, `type` and `value` filled in
      (search the document for promoter/KMP names, "Tel", "@", "DIN", "PAN", "Registered Office"...).
3) build-gt: python eval/annotate.py build-gt eval/rhp_review.csv --out eval/data/rhp_ground_truth.json
4) score:    python eval/evaluate.py --docx "Red Herring Prospectus.docx" --gt eval/data/rhp_ground_truth.json

Tip: sampling protocol for time-boxed reviews: label 100% of structured types (ID/contact) and a
stratified random sample (e.g. 150 rows) of PERSON/ORG/ADDRESS; report the sample size with the scores.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from docx import Document  # noqa: E402

from pii_redactor import RedactionConfig, Redactor  # noqa: E402
from pii_redactor.docx_engine import collect_xml_parts, part_paragraph_texts  # noqa: E402


def propose(docx: Path, out_csv: Path) -> None:
    res = Redactor(RedactionConfig()).redact(docx.read_bytes())
    doc = Document(str(docx))
    corpus = "\n".join(t for h in collect_xml_parts(doc) for t in part_paragraph_texts(h.root))
    rows, seen = [], set()
    by_value = defaultdict(set)
    for d in res.report["detections"]:
        by_value[(d["type"], d["text"])].add(d["source"])
    for img in res.report["images"]:
        for h in img.get("hits", []):
            by_value[(h["type"], h["text"])].add("image:" + h["rule"])
    for (et, val), srcs in sorted(by_value.items()):
        key = (et, val.lower())
        if key in seen:
            continue
        seen.add(key)
        ctx = [corpus[max(0, m.start() - 60):m.end() + 60].replace("\n", " ⏎ ")
               for m in list(re.finditer(re.escape(val), corpus))[:3]]
        rows.append({"type": et, "value": val, "label": "", "rules": "|".join(sorted(srcs)),
                     "occurrences": len(re.findall(re.escape(val), corpus)), "context": " … ".join(ctx)})
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["type", "value", "label"])
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} candidates -> {out_csv}. Fill the `label` column, append FN rows, then run build-gt.")


def build_gt(in_csv: Path, out_json: Path) -> None:
    ents, negs = [], []
    with in_csv.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            lab = (r.get("label") or "").strip().upper()
            if lab in ("TP", "FN"):
                ents.append({"value": r["value"], "type": r["type"], "where": ["text"], "detect": True, "note": lab})
            elif lab.startswith("TYPE:"):
                ents.append({"value": r["value"], "type": lab.split(":", 1)[1], "where": ["text"], "detect": True, "note": "retyped"})
            elif lab == "FP":
                negs.append(r["value"])
    out_json.write_text(json.dumps({"entities": ents, "negatives": negs}, indent=2, ensure_ascii=False))
    print(f"{len(ents)} entities, {len(negs)} negatives -> {out_json}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p1 = sub.add_parser("propose"); p1.add_argument("docx", type=Path); p1.add_argument("--csv", type=Path, required=True)
    p2 = sub.add_parser("build-gt"); p2.add_argument("csv", type=Path); p2.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    propose(a.docx, a.csv) if a.cmd == "propose" else build_gt(a.csv, a.out)
