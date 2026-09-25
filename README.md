# 🛡️ pii-redactor: consistent PII pseudonymization for Word documents

Takes a `.docx` in, finds personally identifiable information **in text, tables, headers/footers,
hyperlinks, tracked changes, comments, document properties and scanned images**, swaps every entity
for a realistic fake that stays the same everywhere it appears, and writes a valid `.docx` back out
with the original formatting intact.

```
Rashi Patil              -> Uma Carter            rashhi.patil@gmail.com -> uma.carter@example.com
KSH International Ltd.   -> KLB International Ltd. cs.connect@kshinternational.com -> cs.connect@klbinternational.example.com
+91 81081 14949          -> +91 91788 34841        U28129PN1979PLC141032  -> U39067TG2009PLC157390
NBWPS1951N (on a scan)   -> YVUPD2331F (painted)   2943 6593 3461         -> 8229 3917 8439 (Verhoeff-valid)
```

## Quick start

```bash
pip install -r requirements.txt            # + system package: tesseract-ocr (see packages.txt)
python -m pii_redactor "Red Herring Prospectus.docx" -o "Red Herring Prospectus_redacted.docx" \
       --report report.json --mapping mapping.json          # mapping = re-identification key, keep private
streamlit run app.py                                         # web UI
python eval/build_benchmark.py && python eval/evaluate.py    # reproduce the metric report
pytest -q                                                    # unit tests
```

CLI flags: `--image-policy replace|mask|blur`, `--no-ocr`, `--ocr-lang eng+hin`, `--spacy-model en_core_web_lg`,
`--salt <secret>`, `--allow "Some Public Body Limited"`.

## Architecture

```
            ┌──────────────────────────── .docx (OPC zip) ─────────────────────────────┐
            │ document.xml · header*/footer* · footnotes · comments · charts · core/app  │
            │ props · hyperlink rels · word/media/* images                               │
            └───────────────┬───────────────────────────────────────────┬──────────────┘
                            │ docx_engine (lxml)                        │ image_engine
                            ▼                                           ▼
  PASS 1  paragraph text per part (runs re-joined,       Tesseract OCR (word boxes, upscale, psm 3→11)
  DETECT  tabs/breaks kept) + table-header semantics     + ID-card layout rules (Name/Father/DOB/Address
                            │                              labels, ALL-CAPS name lines, S/O split)
                            ▼                                           │
           ┌──────── PIIDetector (hybrid) ────────┐                     │
           │ 1. regex recognizers + validators    │◄────────────────────┘ (same detector)
           │    (Luhn, Verhoeff, IP, context cues)│
           │ 2. heuristics: honorific/label/      │
           │    gazetteer names, legal-suffix     │
           │    orgs, PIN-anchored addresses      │
           │ 3. optional spaCy NER (PERSON/ORG)   │
           │ 4. allowlist + tiered overlap resolve│
           └────────────────┬─────────────────────┘
                            ▼
           ┌──── Pseudonymizer = GLOBAL MAPPING CACHE ────┐   HMAC(salt, entity) → deterministic
           │ token-level names (Hegde→Allen everywhere),  │   format-preserving, checksum-valid,
           │ org brand tokens, domains, IDs, dates, addrs │   injective (no two originals share a fake)
           └────────────────┬─────────────────────────────┘
                            ▼
  PASS 2  one compiled matcher of EVERY known surface form (full names, first+last, surnames after
  REPLACE honorifics, org cores/acronyms, e-mail domains, IDs with any spacing) applied to every
          paragraph, field code, tracked deletion, alt-text, chart label, hyperlink target, doc property.
          Images are repainted in place (background-matched box + fake text / mask / blur, QR pixelated,
          faces blurred when the Haar model is present, fail-safe blur for unreadable ID cards).
```

### Why two passes?
Detection is contextual ("Mr. Hegde" is easy, a bare "Hegde" is not). Pass 1 builds the entity
inventory from every place that has strong context. Pass 2 then replaces **every** occurrence of every
known surface form, including weak-context back-references, lower-case repeats and table cells. On the
benchmark this is why `rakhi shetty` (lower-case, missed by detection) still doesn't leak.

### Run splitting (the python-docx trap)
Word stores `Kushal` as `Kus|hal` whenever spell-check marks, revision IDs or partial formatting split
it. Swapping text run by run misses the entity; setting `paragraph.text` wipes every style.
`docx_engine.apply_replacements` builds a character map over the paragraph's own `<w:t>` nodes,
matches on the joined string, then projects each replacement back. If the fake has the same word
count, each fake word lands in the run that held the matching original word (bold stays bold, italic
stays italic); otherwise it goes into the first run. Characters it covers are removed from the other
runs. **No run, rPr, hyperlink, bookmark or field is created or deleted**, and the evaluation checks
this (identical run count and run-property signature before and after).

### Consistency rules
* Names are mapped **per token**, so families stay families: `Kushal Subbayya Hegde → Albert Thomas Allen`,
  `Rajesh Kushal Hegde → Arthur Albert Allen`, `Mr. Hegde → Mr. Allen`, `KUSHAL… → ALBERT…` (case kept).
* Organisations keep their generic words and legal suffix; only distinctive tokens change
  (`Nuvama Wealth Management Limited → Monarch Wealth Management Limited`). E-mail/URL domains reuse the same
  brand (`nuvama.com → monarch.example.com`). Fake domains use the RFC 2606 `example.com` space.
* E-mail local parts follow the person's pseudonym (fuzzy, e.g. `rashhi.patil` ↔ `Rashi Patil`); role
  mailboxes (`cs.connect`, `investor.grievance`) are kept.
* IDs keep their structure: PAN 4th char (holder type), CIN listing flag + PLC/PTC, SEBI prefix
  (INM/INR…), phone country code and grouping, DIN leading zeros. Aadhaar fakes pass Verhoeff and cards pass Luhn.
  SSNs use the never-issued 9xx area, IPs use documentation ranges, PIN codes start with 9 (APO range).
* Deterministic by `--salt`: same salt gives the same pseudonyms across runs and files; a new salt gives an unlinkable set.

## Entity coverage

| Class | Types | Main technique |
|---|---|---|
| Names | PERSON | honorifics, labels (`Contact Person:`, `S/O`), gazetteer, table headers, token propagation, optional spaCy |
| Organizations | ORG | legal-suffix back-walk (`Limited`, `Pvt. Ltd.`, `LLP`, `& Associates`, `Bank`), core/acronym propagation |
| Identifiers | PAN, AADHAAR, CIN, LLPIN, DIN, SEBI_REG, GSTIN, PASSPORT, SSN, IP | regex + checksum/structure + context |
| Financial | CREDIT_CARD, BANK_ACCOUNT, IFSC | Luhn, context-gated account numbers |
| Addresses | ADDRESS | PIN-code anchor + address cue words, back-walk to label/sentence start, multi-line pieces |
| Contacts | EMAIL, PHONE, URL/DOMAIN | RFC-ish e-mail, Indian mobile/landline/toll-free/international phones |
| DOB | DOB | dates only with a birth cue, or any date on an ID-card image |

## Trade-offs & limitations (read before trusting it)
* **Rule-first on purpose.** RHPs are dense with capitalised legal terms (Bid/Offer Period, Selling
  Shareholders, Designated Stock Exchange). A general NER model flags lots of these as ORG/PERSON. Rules plus
  validators give high precision and full explainability (every hit carries its rule name in `report.json`).
  The cost is recall on *unseen* names/orgs with no context. Turn on spaCy for those, but expect
  more false positives (see EVALUATION.md).
* **Public institutions are allowlisted** (SEBI, BSE, NSE, RBI, RoC, NSDL/CDSL…). That's a policy choice, not a
  detector failure. Change it with `--allow` or `gazetteer.DEFAULT_ALLOWLIST`.
* The org detector needs a legal suffix or propagation from somewhere that has one: `Kotak Mahindra Capital Company` is missed.
* OCR quality sets the ceiling for image recall. Devanagari needs `tesseract-ocr-hin` + `--ocr-lang eng+hin`.
  An ID-card-looking image with no hits gets fully blurred (fail-safe). EMF/WMF vector images are skipped (reported).
* Face blurring needs OpenCV's Haar cascade file (bundled with `opencv-python-headless`). QR codes are pixelated.
* Painted fake text in `replace` mode uses DejaVu Sans Bold. It won't match the card's exact typeface.
* Not covered yet: text inside embedded OLE objects / embedded Excel for charts, SmartArt drawings, and
  fonts rendered as images inside PDFs pasted as pictures (these are OCR'd like any image).
* Whole-document replacement can hit a *different* person who shares a registered token (e.g. a second
  "Singh"). That's safe for privacy but changes meaning. Name tokens under 4 characters and common English words are never propagated on their own.
* Address pseudonyms are realistic, not geographically coherent (city/state don't stay consistent).

## Extending to a new PII type (protocol)
1. **Taxonomy**: add a member to `EntityType` in `entities.py` and map it to a reporting class in `CLASS_OF`.
   If the fake should be format-preserving, add it to `ALNUM_TYPES`.
2. **Detection**: either add a `PatternRecognizer` to `build_pattern_recognizers()` (regex, optional
   `validator`, `context` words, `score`), or write a class with `find(text, id_context) -> Iterable[Span]` and call
   `PIIDetector.register(obj)` at runtime (no core edits needed):
   ```python
   from pii_redactor import Redactor, Span, EntityType
   class VoterIdRecognizer:                                   # e.g. Indian EPIC number
       rx = re.compile(r"\b[A-Z]{3}\d{7}\b")
       def find(self, text, id_context=False):
           for m in self.rx.finditer(text):
               if "voter" in text[max(0, m.start()-40):m.start()].lower() or id_context:
                   yield Span(m.start(), m.end(), EntityType.PASSPORT, m.group(), 0.9, "epic")
   r = Redactor(); r.detector.register(VoterIdRecognizer())
   ```
3. **Pseudonym**: add a branch in `Pseudonymizer._gen_alnum` (structured IDs) or a `_fake_<type>` method in
   `fake_for` (free text). Keep it deterministic (`self._rng(key)`), injective (`self.used`) and checksum-valid.
4. **Precision guard**: add allowlist entries or stop words for known lookalikes.
5. **Evaluate**: annotate examples + negatives in `eval/build_benchmark.py` (or via `eval/annotate.py` on a real
   document), run `eval/evaluate.py`, and add a unit test in `tests/`.

## Deployment
* **Streamlit Community Cloud**: push the repo, then New app → `app.py`. `packages.txt` installs Tesseract + fonts.
* **Render**: `render.yaml` (Docker) → New → Blueprint → select the repo. Or run `docker build -t pii . && docker run -p 8501:8501 pii`.
* Files are processed in memory and never written to disk server-side. The mapping is only offered as a download (it's a re-identification key).

## Repo layout
```
pii_redactor/  entities · gazetteer · validators · recognizers · heuristics · ner · detector
               pseudonymizer · docx_engine · image_engine · pipeline · cli
app.py         Streamlit UI            eval/  build_benchmark · evaluate · annotate · data/ · results/
tests/         unit tests              EVALUATION.md  methodology + scores + error analysis
```
