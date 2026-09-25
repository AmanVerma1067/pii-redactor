# Evaluation Strategy & Metric Report

> **Two evaluations.** Precision, recall and F1 (sections 3.1–3.4) are measured on the annotated
> **RHP-style benchmark** (`eval/data/benchmark_rhp.docx` + `ground_truth.json`, 75 entities, 43
> false-positive traps), which reproduces the entity types and layouts of the KSH International RHP.
> The **real `Red Herring Prospectus.docx`** (section 3.5) has no ground truth, so it is reported with run
> statistics, a structural diff and an automated self-leak audit. P/R/F1 on it need the annotation
> workflow in section 6.

## 1. What we measure (and why)

| Question | Metric | How |
|---|---|---|
| Did we *find* the PII? | Precision / Recall / F1 per class | Entity-level on unique values. **Strict** = normalised string equality. **Lenient** = containment (≥50% length) or, for addresses, ≥80% token coverage by same-class pieces (OCR splits addresses into lines) |
| "Accuracy" | TP/(TP+FP+FN) | Span extraction has no meaningful true negatives, so classic accuracy is undefined. We report the Jaccard/CSI form instead |
| Did PII *leave* the file? | End-to-end redaction recall | Every GT value, including back-references ("Mr. Hegde"), comment authors and tracked deletions, is searched for in the **output package**: re-joined paragraph text, every other XML text node and attribute, hyperlink targets, and **OCR of the output images** |
| Partial leaks | Token leak list | Does any distinctive token of a name/org (≥4 chars) survive anywhere? |
| Did we destroy non-PII? | Over-redaction rate | 43 trap strings (statutory terms, exchanges, ISIN, ₹ amounts, offer dates, section numbers, version numbers, 26 boilerplate RHP sentences) must survive verbatim |
| Consistency | 1 pseudonym per entity | Each normalised original maps to exactly one fake across text, tables, headers, links and images |
| Formatting | Structural diff | Same paragraphs, tables, runs, **run-property signature**, images, hyperlinks and sections before and after |

Detection vs leak test: detection scores the detector alone. The leak test scores the **product**: two-pass
propagation, hyperlinks, metadata and images included. A detection miss can still be redacted (`rakhi shetty`),
and a detection hit can still leak if the writer fails (never observed: see section 4).

## 2. Benchmark dataset (annotated ground truth)

`eval/build_benchmark.py` annotates every PII value at the moment it's written, so the ground truth can't drift.

* **75 annotated entities**: 18 names (including ALL-CAPS cover-page promoters, a split-run name, a lower-case
  name, an unseen name, a surname-only back-reference, a tracked-change author, a comment author and 4 names on ID scans), 8 organisations,
  21 identifiers (CIN in body + footer, 5 DINs, 6 PANs, 3 SEBI numbers, GSTIN, Aadhaar, passport, SSN, 2 IPs),
  3 financial, 6 addresses (including a 3-line address on an Aadhaar scan), 11 contacts (including a `mailto:` hyperlink whose text is split
  across 3 runs), 8 dates of birth (table, prose and scans).
* **Locations**: body, tables (column-header and key/value), header, footer, hyperlink targets, `w:del` tracked
  deletion, comment author, 2 embedded PNG ID cards (one with a QR code).
* **43 negative traps** (see section 1).

## 3. Results

### 3.1 Detection: lenient matching (primary)

| Class | TP | FP | FN | Precision | Recall | F1 | Accuracy (TP/(TP+FP+FN)) |
|---|---|---|---|---|---|---|---|
| Names | 14 | 0 | 2 | 1.000 | 0.875 | 0.933 | 0.875 |
| Organizations | 7 | 0 | 1 | 1.000 | 0.875 | 0.933 | 0.875 |
| Identifiers | 21 | 0 | 0 | 1.000 | 1.000 | 1.000 | 1.000 |
| Financial | 3 | 0 | 0 | 1.000 | 1.000 | 1.000 | 1.000 |
| Addresses | 6 | 0 | 0 | 1.000 | 1.000 | 1.000 | 1.000 |
| Contacts | 11 | 0 | 0 | 1.000 | 1.000 | 1.000 | 1.000 |
| DOB | 8 | 0 | 0 | 1.000 | 1.000 | 1.000 | 1.000 |
| **ALL (micro)** | 70 | 0 | 3 | 1.000 | 0.959 | 0.979 | 0.959 |

### 3.2 Detection: strict matching

| Class | TP | FP | FN | Precision | Recall | F1 | Accuracy (TP/(TP+FP+FN)) |
|---|---|---|---|---|---|---|---|
| Names | 14 | 0 | 2 | 1.000 | 0.875 | 0.933 | 0.875 |
| Organizations | 7 | 0 | 1 | 1.000 | 0.875 | 0.933 | 0.875 |
| Identifiers | 21 | 0 | 0 | 1.000 | 1.000 | 1.000 | 1.000 |
| Financial | 3 | 0 | 0 | 1.000 | 1.000 | 1.000 | 1.000 |
| Addresses | 5 | 3 | 1 | 0.625 | 0.833 | 0.714 | 0.556 |
| Contacts | 11 | 0 | 0 | 1.000 | 1.000 | 1.000 | 1.000 |
| DOB | 8 | 0 | 0 | 1.000 | 1.000 | 1.000 | 1.000 |
| **ALL (micro)** | 69 | 3 | 4 | 0.958 | 0.945 | 0.952 | 0.908 |

The only strict-vs-lenient gap is the Aadhaar address: OCR returns it as three lines, and we (correctly) redact
three pieces. Strict string equality counts that as 3 FP + 1 FN. It is a segmentation artefact, not an error.

### 3.3 End-to-end leak test (output file, including OCR of repainted images)

**74/75 PII values removed: redaction recall 0.987**

| Class | Values | Leaked | Redaction recall |
|---|---|---|---|
| Names | 18 | 0 | 1.000 |
| Organizations | 8 | 1 | 0.875 |
| Identifiers | 21 | 0 | 1.000 |
| Financial | 3 | 0 | 1.000 |
| Addresses | 6 | 0 | 1.000 |
| Contacts | 11 | 0 | 1.000 |
| DOB | 8 | 0 | 1.000 |

Full-string leaks: `Kotak Mahindra Capital Company`.
Partial token leaks: `Kotak (from 'Kotak Mahindra Capital Company')`, `Mahindra (from 'Kotak Mahindra Capital Company')`, `Gowda (from 'Subbayya Gowda')`.

### 3.4 Over-redaction, consistency, formatting
* Negative traps preserved: **43/43**.
* One pseudonym per entity across all locations and modalities: **yes** (0 inconsistencies). `VISHAL SINGH` on the PAN
  scan and any text mention share one fake. `Hegde` maps to the same fake surname in every variant (full name, ALL-CAPS, `Mr. Hegde`, tracked change).
* Structure identical: **yes**. Same paragraphs, tables, runs and run formatting, plus images, hyperlinks and sections.
  The split-run name `Kus|hal Subbayya |Hegde` (bold | italic | plain) becomes `Albert | Thomas | Allen` with the
  same bold/italic/plain runs.
* Runtime: 1.41s for the benchmark incl. OCR. About 5s per 3.6k paragraphs without OCR, so a 400-page RHP should take
  well under a minute plus ~1–2s per embedded image.

### 3.5 Real `Red Herring Prospectus.docx` (full document, no ground truth)

| Metric | Value |
|---|---|
| Unique entities pseudonymized | **282** (Names 77, Organizations 79, Addresses 42, Contacts 64, Identifiers 18, DOB 2) |
| Run-level text replacements | **736** paragraph spans, plus 79 other XML nodes (fields, tracked changes, properties) |
| Embedded images | 8 scanned: 2 ID cards redacted, 6 logos/graphics left unchanged (4 below 120 px) |
| Image regions redacted | **12** OCR text regions + **2** holder photos + **2** QR codes |
| PAN card | name, father's name, PAN, DOB replaced. Photo and QR pixelated |
| Aadhaar card | name, father's name, DOB, Aadhaar no. (front and back), address replaced. Photo and QR pixelated |
| XML integrity | 160 XML parts, **0** parse errors, zip CRC clean, re-opens in python-docx |
| Structure | identical: 4,561 paragraphs, 76 tables, 48,819 runs, same run-format signature, 8 images, 85 sections |
| Output size | 1.61 MB (input 1.84 MB) |
| Runtime | 15.8 s including OCR |

**Self-leak audit** (`eval/self_audit.py`). Each of the 282 detected originals is searched for in the output
package with the benchmark's leak matcher (paragraph text, other XML text/attributes, link targets, OCR of
output images). **272/282 are gone. 10 still match:**

* 7 office-address variants (registered office in Birdewadi/Chakan, corporate office in Baner, BRLM office at
  Inspire BKC). The detected form was replaced, but the same address also appears written differently
  (`Tower-2` vs `Tower 2`, `Building No.` vs `No`, split across table cells or lines), and those copies survive.
  **Real leak.**
* `State Bank of India`: registered, but one occurrence (`State Bank of India, Industrial Finance…`) survives.
* `Account Bank` (from `Public Offer Account Bank`) and `Registrar of Companies, Maharashtra at Pune` (tagged
  ADDRESS) are detector false positives. Their text surviving is the correct outcome.

The audit only checks values the detector found. PII the detector never saw needs a ground truth (section 6).

## 4. Error analysis

### 4.1 False negatives (PII that got through, or nearly did)
| Case | Why it was missed | Impact | Fix |
|---|---|---|---|
| `Kotak Mahindra Capital Company` | No legal suffix (`Limited`/`Ltd`/`LLP`) and never seen elsewhere with one, so nothing to propagate from | **Full leak** (org) | Enable spaCy ORG, add a curated org gazetteer (SEBI intermediary list), or accept `<Distinctive> ... Company` with ≥2 non-generic tokens |
| `Subbayya Gowda` | Neither token is in the gazetteer, no honorific, no label | **Partial leak**: `Subbayya` is replaced by propagation (seen in a promoter's name), `Gowda` survives | spaCy PERSON, a larger surname list, or a "capitalised bigram next to a known name token" rule |
| `rakhi shetty` | Lower-case, so every case-sensitive name rule skips it | **No leak**: pass 2 matches the registered first+last variant of `Rakhi Girija Shetty` case-insensitively | (Shows why the two-pass design matters) |

What leaks or would leak on the *real* RHP, ranked by risk:
1. Office addresses repeated with different punctuation/line breaks (seen in section 3.5). Fix: token-normalised
   address propagation (hyphens, `No.`/`No`, cell and line joins) in pass 2.
2. People named only in running prose with no honorific or label and uncommon names (KMP bios, litigation sections). Mitigation: spaCy + review of `report.json` detections.
3. Organisations without a suffix (group companies, customers, lenders referred to by brand). Same mitigation as above.
4. Low-resolution or rotated scans. Mitigation: 2x upscale, psm-11 retry, and the fail-safe blur on ID-looking images with no hits.
5. Hindi-script names on the Aadhaar/PAN card. On the real RHP, the Devanagari name, father's name and address on
   the Aadhaar card stay readable with the default `eng` OCR. Mitigation: `--ocr-lang eng+hin` (installed via
   `packages.txt`/Dockerfile).

### 4.2 False positives (non-PII that we changed)
| Trap / case | Outcome | Mechanism |
|---|---|---|
| `SEBI ICDR Regulations`, `Companies Act, 2013`, `Section 2(76)`, `Rule 19(2)(b)` | preserved | Name/org rules need a gazetteer name, honorific or legal suffix. Statutory vocabulary is in `NAME_STOP` |
| `BSE Limited`, `National Stock Exchange of India Limited`, `Reserve Bank of India`, `Supreme Court of India` | preserved | Public-institution allowlist (policy: not personal data) |
| `INE0ABC01018` (ISIN) vs SEBI reg. pattern `IN?#########` | preserved | `INE` prefix excluded. ISINs contain letters after the prefix |
| `1,84,89,583`, `₹7,100.00 million`, `2,43,000`, `₹ 5,00,000` | preserved | Comma/decimal-aware lookarounds on every numeric pattern (Indian lakh grouping) |
| Offer and incorporation dates (`September 16, 2025`, `February 13, 1979`) | preserved | Dates are only redacted with a birth cue (`DOB`, `born on`) or on an ID-card image |
| `Tel: 91-20-2721 8080` on the PAN card reverse | **was an FP in v1.0** (read as DOB `91-20-2721`), **fixed** | DOB values must be real dates (day ≤ 31, month ≤ 12, year 1920–current), and a date right after `Tel`/`Fax`/`Phone`/`Mobile` is never a DOB |
| `version 2.1.4.0` vs IPv4 | preserved | IP validator requires a real address with at least one octet > 9 |
| `Company Secretary and Compliance Officer is responsible…` | **was an FP in v0** (`is responsible` → PERSON), **fixed** | Found by the stress section: the label rule accepted any text after `Compliance Officer`. Now it needs an explicit `:`/`-` separator or a capitalised value. v0 preserved 42/43 traps, v1 preserves 43/43 |

Known FP risks on the real RHP that the benchmark doesn't cover:
* Surname-only gazetteer rule: a capitalised word followed by a common surname (e.g. a place or a product like `Shah Industrial`) can come out as PERSON.
* Token propagation replaces *any* capitalised occurrence of a registered name token (e.g. a second, unrelated `Singh`).
  Privacy-safe, but it changes meaning.
* PIN-anchored addresses: a 6-digit number near an address cue word (e.g. a plot area) could be read as a PIN.
* spaCy (if enabled) will add ORG false positives on defined terms. The adapter drops single-token and all-generic
  entities, but it can't remove them all. This is why it's off by default.

## 5. Iteration log (how the numbers moved)
| Version | Change | Lenient F1 | Redaction recall | Traps preserved |
|---|---|---|---|---|
| v0.1 | first end-to-end run | 0.930 | 0.960 | 17/17 |
| v0.2 | IP lookahead (`… 10.24.8.199.`), bank-account `,` lookahead, context-gated passport `[A-Z]`, split `S/O <name>` out of OCR addresses | 0.979 | 0.987 | 17/17 |
| v0.3 | +26 boilerplate RHP sentences (stress set) exposed the `is responsible` label FP | 0.972 | 0.987 | 42/43 |
| v1.0 | label rule needs explicit separator or capitalised value; word-aligned run formatting | 0.979 | 0.987 | 43/43 |
| v1.1 | ID photos: Haar faces (raw + equalised) widened to the photo frame, PAN/Aadhaar layout fallback; QR fallback for blurred codes; DOB date validation + phone-label guard; OpenCV pinned < 5 (5.0 drops `CascadeClassifier`) | **0.979** | **0.987** | **43/43** |

## 6. Ground-truth protocol for the real RHP
```bash
python eval/annotate.py propose "Red Herring Prospectus.docx" --csv eval/rhp_review.csv   # candidates + context
#   label each row TP / FP / TYPE:<X>; append missed PII as FN rows (search promoters, KMP, "Tel", "@", "DIN", "PAN")
python eval/annotate.py build-gt eval/rhp_review.csv --out eval/data/rhp_ground_truth.json
python eval/evaluate.py --docx "Red Herring Prospectus.docx" --gt eval/data/rhp_ground_truth.json --out eval/results_rhp
```
Time-boxed sampling: label 100% of structured types (IDs, contacts, DOB) and a stratified random sample of
PERSON/ORG/ADDRESS (e.g. 150 rows). Report the sample size next to the scores. Recall on a real document is
bounded by what the annotator finds, so also do a targeted FN hunt: search the output for the promoter surnames,
`@`, `+91`, `DIN`, `PAN` and the office PIN codes. The leak test automates this for every GT value.
