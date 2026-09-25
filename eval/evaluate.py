"""Evaluation harness: detection P/R/F1 per class, end-to-end leak test, over-redaction traps,
pseudonym consistency and structural (formatting) integrity.

    python eval/evaluate.py --docx eval/data/benchmark_rhp.docx --gt eval/data/ground_truth.json --out eval/results

Metrics
  * Detection (entity level, unique values): a GT entity is a TP if a detection of the same class
    matches it. strict = normalised string equality; lenient = containment (>=50% length) or, for
    addresses, >=80% token coverage by same-class pieces (multi-line addresses).
  * Accuracy: span extraction has no true negatives, so we report TP/(TP+FP+FN) (a.k.a. CSI/Jaccard).
  * Leak test (end-to-end recall): every GT value (including back-references like "Mr. Hegde",
    comment authors, tracked deletions) is searched for in the OUTPUT package: paragraph text with
    runs re-joined, every other XML text node & attribute, hyperlink targets, and OCR of output images.
  * Over-redaction: the negative trap strings must survive verbatim.
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from docx import Document  # noqa: E402
from lxml import etree  # noqa: E402
from PIL import Image  # noqa: E402

from pii_redactor import RedactionConfig, Redactor  # noqa: E402
from pii_redactor.docx_engine import W, collect_xml_parts, paragraph_text  # noqa: E402
from pii_redactor.entities import ALNUM_TYPES, CLASS_OF, EntityType as T  # noqa: E402
from pii_redactor.gazetteer import GENERIC_ORG_WORDS, NAME_STOP  # noqa: E402
from pii_redactor.image_engine import ImageRedactor  # noqa: E402

CLASSES = ["Names", "Organizations", "Identifiers", "Financial", "Addresses", "Contacts", "DOB"]


def norm(v: str, et: T) -> str:
    if et in ALNUM_TYPES or et is T.IP_ADDRESS:
        return re.sub(r"[^A-Za-z0-9]", "", v).upper()
    return re.sub(r"\s+", " ", v).strip(" ,.;:").lower()


def toks(v: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", v.lower()))


# ---------------------------------------------------------------- detection metrics
def detection_metrics(gt: list[dict], det: list[tuple[str, T]]):
    gt_items = [(g["value"], T(g["type"])) for g in gt if g.get("detect", True)]
    det_u = {}
    for v, et in det:
        det_u.setdefault((norm(v, et), CLASS_OF[et]), (v, et))
    det_items = list(det_u.values())

    def match(gv, gt_t, dv, dt_t, lenient):
        if CLASS_OF[gt_t] != CLASS_OF[dt_t]:
            return False
        a, b = norm(gv, gt_t), norm(dv, dt_t)
        if a == b:
            return True
        if not lenient:
            return False
        if (a in b or b in a) and min(len(a), len(b)) / max(len(a), len(b)) >= 0.5:
            return True
        return False

    out = {}
    for mode in ("strict", "lenient"):
        per = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0, "fn_items": [], "fp_items": []})
        used = set()
        for gv, gtt in gt_items:
            cls = CLASS_OF[gtt]
            hits = [i for i, (dv, dtt) in enumerate(det_items) if match(gv, gtt, dv, dtt, mode == "lenient")]
            ok = bool(hits)
            if not ok and mode == "lenient" and gtt is T.ADDRESS:  # multi-line address pieces
                pieces = [i for i, (dv, dtt) in enumerate(det_items) if dtt is T.ADDRESS
                          and len(toks(dv) & toks(gv)) / max(1, len(toks(dv))) >= 0.5]
                cover = set().union(*[toks(det_items[i][0]) for i in pieces]) if pieces else set()
                if len(cover & toks(gv)) / max(1, len(toks(gv))) >= 0.8:
                    hits, ok = pieces, True
            used.update(hits)
            per[cls]["tp" if ok else "fn"] += 1
            if not ok:
                per[cls]["fn_items"].append(gv)
        for i, (dv, dtt) in enumerate(det_items):
            if i in used:
                continue
            # a detection that matches *some* GT value (e.g. a variant already credited) is not an FP
            if any(match(gv, gtt, dv, dtt, True) for gv, gtt in [(g["value"], T(g["type"])) for g in gt]):
                continue
            per[CLASS_OF[dtt]]["fp"] += 1
            per[CLASS_OF[dtt]]["fp_items"].append(f"{dv} [{dtt.value}]")
        tot = {"tp": 0, "fp": 0, "fn": 0}
        for c in per.values():
            for k in tot:
                tot[k] += c[k]
        per["ALL"] = {**tot, "fn_items": [], "fp_items": []}
        for c in per.values():
            tp, fp, fn = c["tp"], c["fp"], c["fn"]
            c["precision"] = round(tp / (tp + fp), 4) if tp + fp else 1.0
            c["recall"] = round(tp / (tp + fn), 4) if tp + fn else 1.0
            p, r = c["precision"], c["recall"]
            c["f1"] = round(2 * p * r / (p + r), 4) if p + r else 0.0
            c["accuracy_csi"] = round(tp / (tp + fp + fn), 4) if tp + fp + fn else 1.0
        out[mode] = dict(per)
    return out


# ---------------------------------------------------------------- output text harvesting
def harvest(docx_bytes: bytes, ocr: bool = True) -> tuple[list[str], list[str]]:
    doc = Document(io.BytesIO(docx_bytes))
    blobs: list[str] = []
    for h in collect_xml_parts(doc):
        for p in h.root.iter(W + "p"):
            blobs.append(paragraph_text(p))
        for el in h.root.iter():
            if isinstance(el.tag, str):
                if el.tag != W + "t" and el.text and el.text.strip():
                    blobs.append(el.text)
                blobs.extend(v for v in el.attrib.values() if len(v) > 3)
    for part in doc.part.package.iter_parts():
        for rel in part.rels.values():
            if rel.is_external:
                blobs.append(rel.target_ref)
    ocr_blobs: list[str] = []
    if ocr and ImageRedactor.available():
        ir = ImageRedactor(None, None)
        for part in doc.part.package.iter_parts():
            if part.content_type.startswith("image/"):
                try:
                    img = Image.open(io.BytesIO(part.blob)).convert("RGB")
                except Exception:
                    continue
                if min(img.size) >= 120:
                    lines = ir.ocr(img)
                    ocr_blobs.append("\n".join(l.text for l in lines))
    return blobs, ocr_blobs


def present(value: str, et: T, blobs: list[str]) -> bool:
    if et in ALNUM_TYPES or et is T.IP_ADDRESS:
        k = norm(value, et)
        return any(k in re.sub(r"[^A-Za-z0-9]", "", b).upper() for b in blobs)
    if et is T.ADDRESS:  # an address leaks if most of its tokens survive together in one blob
        gt = toks(value)
        return any(len(gt & toks(b)) / max(1, len(gt)) >= 0.6 for b in blobs)
    pat = re.compile(r"(?<![a-z0-9])" + r"\s+".join(map(re.escape, norm(value, et).split())) + r"(?![a-z0-9])")
    return any(pat.search(re.sub(r"\s+", " ", b).lower()) for b in blobs)


# ---------------------------------------------------------------- structure
def structure(docx_bytes: bytes) -> dict:
    doc = Document(io.BytesIO(docx_bytes))
    body = doc.element.body
    runs = list(body.iter(W + "r"))
    sig = [etree.tostring(r.find(W + "rPr")) if r.find(W + "rPr") is not None else b"" for r in runs]
    return {"paragraphs": len(list(body.iter(W + "p"))), "tables": len(list(body.iter(W + "tbl"))),
            "runs": len(runs), "run_format_signature": hash(tuple(sig)),
            "images": sum(1 for p in doc.part.package.iter_parts() if p.content_type.startswith("image/")),
            "hyperlinks": len(list(body.iter(W + "hyperlink"))), "sections": len(doc.sections)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--docx", type=Path, default=Path(__file__).parent / "data" / "benchmark_rhp.docx")
    ap.add_argument("--gt", type=Path, default=Path(__file__).parent / "data" / "ground_truth.json")
    ap.add_argument("--out", type=Path, default=Path(__file__).parent / "results")
    ap.add_argument("--spacy-model", default=None)
    ap.add_argument("--no-ocr", action="store_true")
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)

    gt = json.loads(a.gt.read_text())
    src = a.docx.read_bytes()
    res = Redactor(RedactionConfig(spacy_model=a.spacy_model, enable_ocr=not a.no_ocr)).redact(src)
    (a.out / "benchmark_rhp_redacted.docx").write_bytes(res.output)
    (a.out / "mapping.json").write_text(json.dumps(res.mapping, indent=2, ensure_ascii=False))

    det = [(m["original"], T(m["type"])) for m in res.mapping if m["type"] != "DOMAIN"]
    metrics = detection_metrics(gt["entities"], det)

    blobs_in, ocr_in = harvest(src, ocr=not a.no_ocr)
    blobs_out, ocr_out = harvest(res.output, ocr=not a.no_ocr)
    leaks, per_cls = [], defaultdict(lambda: {"total": 0, "leaked": 0})
    for g in gt["entities"]:
        et = T(g["type"])
        is_img = g["where"] == ["image"]
        before = present(g["value"], et, ocr_in if is_img else blobs_in)
        if not before:  # value not machine-visible in the input (e.g. OCR cannot read it): not measurable
            continue
        per_cls[CLASS_OF[et]]["total"] += 1
        if present(g["value"], et, ocr_out if is_img else blobs_out):
            per_cls[CLASS_OF[et]]["leaked"] += 1
            leaks.append({"value": g["value"], "type": g["type"], "where": g["where"], "note": g.get("note", "")})
    for c in per_cls.values():
        c["redaction_recall"] = round(1 - c["leaked"] / c["total"], 4) if c["total"] else 1.0
    tot = sum(c["total"] for c in per_cls.values())
    leaked = sum(c["leaked"] for c in per_cls.values())

    # stricter view for names/orgs: does ANY distinctive token of the entity survive anywhere?
    token_leaks = []
    for g in gt["entities"]:
        et = T(g["type"])
        if et not in (T.PERSON, T.ORG):
            continue
        pool = ocr_out if g["where"] == ["image"] else blobs_out
        for tok in re.findall(r"[A-Za-z]{4,}", g["value"]):
            k = tok.lower()
            if k in GENERIC_ORG_WORDS or k in NAME_STOP:
                continue
            if present(tok, T.PERSON, pool):
                token_leaks.append(f"{tok} (from '{g['value']}')")
    neg_lost = [n for n in gt["negatives"] if not any(n.lower() in b.lower() for b in blobs_out)]

    fakes = defaultdict(set)
    for m in res.mapping:
        fakes[(m["type"], norm(m["original"], T(m["type"])))].add(m["pseudonym"].lower())
    inconsistent = {f"{k[0]}:{k[1]}": sorted(v) for k, v in fakes.items() if len(v) > 1}

    s_in, s_out = structure(src), structure(res.output)
    struct_ok = {k: s_in[k] == s_out[k] for k in s_in}

    result = {
        "document": a.docx.name, "gt_entities": len(gt["entities"]), "negatives": len(gt["negatives"]),
        "detection": metrics,
        "leak_test": {"measurable": tot, "leaked": leaked, "redaction_recall": round(1 - leaked / tot, 4) if tot else 1.0,
                      "per_class": dict(per_cls), "leaks": leaks, "partial_token_leaks": token_leaks},
        "over_redaction": {"negatives_total": len(gt["negatives"]), "negatives_destroyed": neg_lost,
                           "preservation_rate": round(1 - len(neg_lost) / max(1, len(gt["negatives"])), 4)},
        "consistency": {"entities": len(fakes), "inconsistent": inconsistent},
        "structure": {"input": s_in, "output": s_out, "identical": struct_ok},
        "images": res.report["images"], "seconds": res.report["seconds"],
    }
    (a.out / "metrics.json").write_text(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    (a.out / "metrics.md").write_text(render_md(result))
    print(render_md(result))
    return 0


def render_md(r: dict) -> str:
    L = [f"# Results on `{r['document']}`", "",
         f"{r['gt_entities']} annotated entities, {r['negatives']} negative traps, runtime {r['seconds']}s.", ""]
    for mode in ("strict", "lenient"):
        L += [f"## Detection ({mode} matching)", "", "| Class | TP | FP | FN | Precision | Recall | F1 | Accuracy (TP/(TP+FP+FN)) |",
              "|---|---|---|---|---|---|---|---|"]
        d = r["detection"][mode]
        for c in CLASSES + ["ALL"]:
            if c in d:
                x = d[c]
                L.append(f"| {'**ALL**' if c == 'ALL' else c} | {x['tp']} | {x['fp']} | {x['fn']} | {x['precision']:.3f} | "
                         f"{x['recall']:.3f} | {x['f1']:.3f} | {x['accuracy_csi']:.3f} |")
        L.append("")
        fn = {c: d[c]["fn_items"] for c in d if d[c]["fn_items"]}
        fp = {c: d[c]["fp_items"] for c in d if d[c]["fp_items"]}
        L += [f"False negatives: `{json.dumps(fn, ensure_ascii=False)}`", "", f"False positives: `{json.dumps(fp, ensure_ascii=False)}`", ""]
    lt = r["leak_test"]
    L += ["## End-to-end leak test (output package incl. OCR of output images)", "",
          f"**{lt['measurable'] - lt['leaked']}/{lt['measurable']} PII values removed "
          f"(redaction recall {lt['redaction_recall']:.3f})**", "", "| Class | Values | Leaked | Redaction recall |", "|---|---|---|---|"]
    for c in CLASSES:
        if c in lt["per_class"]:
            x = lt["per_class"][c]
            L.append(f"| {c} | {x['total']} | {x['leaked']} | {x['redaction_recall']:.3f} |")
    L += ["", "Leaks: " + ("none" if not lt["leaks"] else ", ".join(f"`{l['value']}` ({l['type']}, {l['note'] or '/'.join(l['where'])})" for l in lt["leaks"])), "",
          "Partial token leaks (a distinctive name/org token survives somewhere): "
          + ("none" if not lt["partial_token_leaks"] else ", ".join(f"`{t}`" for t in lt["partial_token_leaks"])), ""]
    o = r["over_redaction"]
    L += ["## Over-redaction traps", "", f"{o['negatives_total'] - len(o['negatives_destroyed'])}/{o['negatives_total']} preserved"
          + (f"; destroyed: {o['negatives_destroyed']}" if o["negatives_destroyed"] else ""), ""]
    L += ["## Consistency & structure", "",
          f"- One pseudonym per entity: {'yes' if not r['consistency']['inconsistent'] else r['consistency']['inconsistent']}",
          f"- Structure identical (paragraphs, tables, runs, run formatting, images, hyperlinks, sections): "
          f"{all(r['structure']['identical'].values())} {r['structure']['identical']}", ""]
    return "\n".join(L)


if __name__ == "__main__":
    raise SystemExit(main())
