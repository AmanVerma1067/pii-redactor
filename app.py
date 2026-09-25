"""Streamlit front-end: upload a .docx -> download the pseudonymized .docx (+ report / mapping)."""
from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from pii_redactor import RedactionConfig, Redactor
from pii_redactor.image_engine import ImageRedactor

st.set_page_config(page_title="PII Redactor for .docx", page_icon="🛡️", layout="wide")
st.title("🛡️ PII Redaction & Pseudonymization for Word documents")
st.caption("Hybrid regex + heuristics (+ optional spaCy NER) · run-split-safe XML editing · OCR for embedded "
           "images · one consistent pseudonym per entity across text, tables, headers, links and images.")

with st.sidebar:
    st.header("Settings")
    policy = st.selectbox("Image PII policy", ["replace", "mask", "blur"],
                          help="replace = paint realistic fake text; mask = black box; blur = gaussian blur")
    ocr = st.toggle("Scan embedded images (OCR)", value=True, disabled=not ImageRedactor.available())
    if not ImageRedactor.available():
        st.warning("Tesseract not found on the server: images will not be scanned.")
    salt = st.text_input("Pseudonym salt (secret)", value="scaler-ai-labs", type="password",
                         help="Same salt -> same pseudonyms across runs. Change it to get an unlinkable mapping.")
    use_spacy = st.toggle("Use spaCy NER (if installed)", value=False)
    allow = st.text_area("Never redact (one per line)", placeholder="e.g. Axis Bank Limited")

@st.cache_resource(show_spinner=False)
def get_redactor(salt: str, policy: str, ocr: bool, use_spacy: bool, allow: tuple[str, ...]) -> Redactor:
    cfg = RedactionConfig(salt=salt, image_policy=policy, enable_ocr=ocr,
                          spacy_model="en_core_web_lg" if use_spacy else None, extra_allowlist=list(allow))
    return Redactor(cfg)

up = st.file_uploader("Upload a .docx", type=["docx"])
if up is not None:
    allow_t = tuple(a.strip() for a in allow.splitlines() if a.strip())
    with st.spinner("Detecting and pseudonymizing PII…"):
        try:
            res = get_redactor(salt, policy, ocr, use_spacy, allow_t).redact(up.getvalue())
        except Exception as exc:  # surface a readable error instead of a stack trace
            st.error(f"Could not process this file: {exc}")
            st.stop()
    r = res.report
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Unique entities", r["entities_unique"])
    c2.metric("Text replacements", r["replacements"]["paragraph_spans"] + r["replacements"]["other_xml_nodes"])
    c3.metric("Image regions", sum(len(i.get("hits", [])) for i in r["images"]))
    c4.metric("Seconds", r["seconds"])

    name = up.name.rsplit(".", 1)[0] + "_redacted.docx"
    st.download_button("⬇️ Download redacted .docx", res.output, file_name=name, type="primary",
                       mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")

    st.subheader("Entities by class")
    st.bar_chart(pd.Series(r["entities_by_class"]).sort_values(ascending=False))

    with st.expander("Mapping preview (original → pseudonym) — sensitive", expanded=False):
        st.warning("This table is a re-identification key. Don't share it alongside the redacted file.")
        st.dataframe(pd.DataFrame(res.mapping), use_container_width=True, hide_index=True)
        st.download_button("Download mapping.json", json.dumps(res.mapping, indent=2, ensure_ascii=False),
                           file_name="mapping.json", mime="application/json")
    with st.expander("Image processing report"):
        st.json(r["images"])
    st.download_button("Download full report.json", json.dumps(r, indent=2, default=str, ensure_ascii=False),
                       file_name="report.json", mime="application/json")
else:
    st.info("Upload a Word document to begin. Nothing is stored: files are processed in memory.")
