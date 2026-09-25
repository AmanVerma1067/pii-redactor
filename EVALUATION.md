# 📊 Empirical Evaluation Strategy & Benchmark Report

> **Evaluation Framework Note (Scaler AI Labs)**: This evaluation report provides an empirical, mathematically rigorous benchmark of the PII Redaction & Pseudonymization Engine against both an annotated ground-truth benchmark (`eval/data/benchmark_rhp.docx` + `eval/data/ground_truth.json`) and the official 400+ page `Red Herring Prospectus.docx`.

---

## 1. Mathematical Evaluation Framework

Information extraction on unstructured legal prose lacks a well-defined definition of true negatives (every non-entity character is trivially unselected). Therefore, the evaluation protocol establishes entity-level classification over unique canonical values:

$$\text{Precision} = \frac{TP}{TP + FP}$$

$$\text{Recall} = \frac{TP}{TP + FN}$$

$$F_1 = \frac{2 \cdot \text{Precision} \cdot \text{Recall}}{\text{Precision} + \text{Recall}} = \frac{2 \cdot TP}{2 \cdot TP + FP + FN}$$

$$\text{Accuracy (Critical Success Index / Jaccard)} = \frac{TP}{TP + FP + FN}$$

### Matching Criteria

1. **Strict Matching**: Requires exact normalized character-sequence equality:
   $$\text{norm}(s) = \text{strip}(\text{lowercase}(s))$$
   For alphanumeric identifiers (PAN, CIN, DIN, Aadhaar), formatting punctuation (spaces, dashes) is stripped.
2. **Lenient Matching (Primary)**: Defines true positives under containment or multi-line coverage:
   - String containment with length overlap $\ge 50\%$:
     $$\frac{\min(|s_1|, |s_2|)}{\max(|s_1|, |s_2|)} \ge 0.5$$
   - Address token coverage $\ge 80\%$ across segmented OCR lines (essential for scanned Aadhaar cards where the physical address is broken across 3 printed lines).

### End-to-End Leak Testing (Redaction Recall)

$$\text{Redaction Recall} = \frac{\text{Measurable Entities Removed}}{\text{Total Measurable Ground-Truth Entities}} = 1 - \frac{\text{Leaked Entities}}{\text{Measurable Entities}}$$

Every ground-truth entity is systematically audited in the final `.docx` package by re-extracting:
- Concatenated text from all paragraph `<w:t>` elements
- Non-run XML nodes (`<w:delText>`, `<w:instrText>`, alt-text `<w:descr>`)
- DrawingML chart labels and document properties (`/docProps/core.xml`, `/docProps/app.xml`)
- External hyperlink target URIs (`r:id` relationships)
- **Tesseract OCR re-extraction on all modified embedded media images**

---

## 2. Benchmark Dataset Profile (`benchmark_rhp.docx`)

The benchmark document reproduces the complex corporate and statutory topology of the KSH International prospectus, synthesized with deliberate edge cases and false-positive traps:

- **Total Ground-Truth Entities**: **75**
- **Negative Traps (False-Positive Stress Test)**: **43**
- **Granular Taxonomy (19 Types)**:
  - `PERSON` (18): Promoters (ALL-CAPS, mixed case, split runs), KMPs, directors, comment author, tracked-change author, and ID card scans.
  - `ORG` (8): Statutory auditors, merchant bankers, registrars, and group companies.
  - `IDENTIFIERS` (21): Corporate Identity Numbers (CIN), Director Identification Numbers (DIN), PANs, Aadhaar numbers, SEBI registration codes, GSTIN, Passports, SSNs, and IP addresses.
  - `FINANCIAL` (3): Bank accounts, IFSC codes, Corporate credit cards.
  - `ADDRESS` (6): Multi-line registered offices, MIDC industrial zones, residential addresses.
  - `CONTACTS` (11): Telephone numbers (landline, mobile, toll-free, international), RFC-compliant emails, corporate website URLs.
  - `DOB` (8): Dates of birth formatted across numeric delimiters and textual month names.

---

## 3. Tabular Benchmark Results

### 3.1 Detection: Lenient Matching (Primary Extraction)

| Evaluation Class | True Positives (TP) | False Positives (FP) | False Negatives (FN) | Precision | Recall | $F_1$-Score | Accuracy (CSI) |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Names** | 14 | 0 | 2 | **1.0000** | 0.8750 | 0.9333 | 0.8750 |
| **Organizations** | 7 | 0 | 1 | **1.0000** | 0.8750 | 0.9333 | 0.8750 |
| **Identifiers** | 21 | 0 | 0 | **1.0000** | **1.0000** | **1.0000** | **1.0000** |
| **Financial** | 3 | 0 | 0 | **1.0000** | **1.0000** | **1.0000** | **1.0000** |
| **Addresses** | 6 | 0 | 0 | **1.0000** | **1.0000** | **1.0000** | **1.0000** |
| **Contacts** | 11 | 0 | 0 | **1.0000** | **1.0000** | **1.0000** | **1.0000** |
| **DOB** | 8 | 0 | 0 | **1.0000** | **1.0000** | **1.0000** | **1.0000** |
| **ALL (Micro Aggregate)** | **70** | **0** | **3** | **1.0000** | **0.9589** | **0.9790** | **0.9589** |

* **False Negatives (3)**:
  - `Organizations`: `"Kotak Mahindra Capital Company"` (missed due to lack of standard corporate legal suffix `Limited` / `LLP`).
  - `Names`: `"rakhi shetty"` (lowercase variant), `"Subbayya Gowda"` (unseen surname with no honorific or contextual label).
* **False Positives (0)**: **Zero false positives across all 7 evaluation classes.**

---

### 3.2 Detection: Strict Matching

| Evaluation Class | True Positives (TP) | False Positives (FP) | False Negatives (FN) | Precision | Recall | $F_1$-Score | Accuracy (CSI) |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Names** | 14 | 0 | 2 | 1.0000 | 0.8750 | 0.9333 | 0.8750 |
| **Organizations** | 7 | 0 | 1 | 1.0000 | 0.8750 | 0.9333 | 0.8750 |
| **Identifiers** | 21 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| **Financial** | 3 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| **Addresses** | 5 | 3 | 1 | 0.6250 | 0.8333 | 0.7143 | 0.5556 |
| **Contacts** | 11 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| **DOB** | 8 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| **ALL (Micro Aggregate)** | **69** | **3** | **4** | **0.9583** | **0.9452** | **0.9517** | **0.9079** |

#### Strict vs. Lenient Discrepancy Analysis
The sole difference between strict and lenient evaluation occurs in `Addresses`. On the embedded scanned Aadhaar card, the physical address is laid out over three separate lines:
1. `saray dan shah, KATRAULI,`
2. `Poore Durgi, Phoolpur,`
3. `Allahabad, UP 212402`

Tesseract OCR detects three distinct bounding boxes. The engine masks all three boxes individually. Under strict string matching, segmenting one address into three sub-spans is scored as 3 False Positives and 1 False Negative. Under lenient matching, multi-piece token coverage reaches 100%, accurately reflecting complete visual redaction.

---

### 3.3 End-to-End Redaction Leak Test

| Evaluation Class | Total Ground-Truth Values | Leaked Values | Redaction Recall |
|---|:---:|:---:|:---:|
| **Names** | 18 | 0 | **1.0000 (100.0%)** |
| **Organizations** | 8 | 1 | **0.8750 (87.5%)** |
| **Identifiers** | 21 | 0 | **1.0000 (100.0%)** |
| **Financial** | 3 | 0 | **1.0000 (100.0%)** |
| **Addresses** | 6 | 0 | **1.0000 (100.0%)** |
| **Contacts** | 11 | 0 | **1.0000 (100.0%)** |
| **DOB** | 8 | 0 | **1.0000 (100.0%)** |
| **OVERALL LEAK METRIC** | **75** | **1** | **0.9867 (98.67%)** |

#### Leak Findings
- **Full Leak Detected**: `"Kotak Mahindra Capital Company"` (Entity: `ORG`).
- **Partial Token Leaks**: `"Kotak"`, `"Mahindra"` (from the leaked organization), `"Gowda"` (from `"Subbayya Gowda"`; note that `"Subbayya"` was successfully redacted via promoter token propagation, while the unseen token `"Gowda"` survived).
- **Two-Pass Protection Highlight**: While `"rakhi shetty"` was a detection false negative due to lowercase formatting, it was **100% redacted in the output document** because Pass 2 propagated the tokens registered from `"Rakhi Girija Shetty"`.

---

## 4. Negative Trap Analysis (Over-Redaction Safeguards)

To verify that the engine does not over-redact statutory and regulatory terms, **43 negative trap strings** were injected into the test document.

**Result**: **43 / 43 Traps Preserved (100.0% Preservation Rate, 0% Over-Redaction)**

```text
[PRESERVED] Companies Act, 2013                  (Statutory Act)
[PRESERVED] SEBI ICDR Regulations                 (Statutory Regulation)
[PRESERVED] Section 2(76)                         (Statutory Section Reference)
[PRESERVED] Rule 19(2)(b)                         (Statutory Rule Reference)
[PRESERVED] Section 92                            (Statutory Filing Provision)
[PRESERVED] BSE Limited                           (Public Stock Exchange)
[PRESERVED] National Stock Exchange of India Ltd  (Public Stock Exchange)
[PRESERVED] Securities and Exchange Board of India(Regulator)
[PRESERVED] Reserve Bank of India                 (Central Bank)
[PRESERVED] Supreme Court of India                (Judicial Body)
[PRESERVED] High Court of Bombay                  (Judicial Body)
[PRESERVED] INE0ABC01018                          (Financial ISIN - Not SEBI Reg)
[PRESERVED] 1,84,89,583                           (Share Count with Indian Lakh Grouping)
[PRESERVED] ₹7,100.00 million                     (Offer Valuation Amount)
[PRESERVED] ₹ 5,00,000                            (UPI Limit Amount)
[PRESERVED] 18.45% / 18.52%                       (Financial Growth Percentages)
[PRESERVED] September 16, 2025                    (Offer Issue Date)
[PRESERVED] February 13, 1979                     (Company Incorporation Date)
[PRESERVED] version 2.1.4.0                       (Software Version - Not IPv4)
[PRESERVED] Company Secretary & Compliance Officer(Corporate Officer Role)
[PRESERVED] Book Running Lead Manager             (Financial Intermediary Role)
[PRESERVED] 26 Boilerplate RHP Sentences          (Standard Legal Prose)
```

---

## 5. Structural & Format Preservation Verification

The redacted output package was programmatically compared against the original benchmark using `eval/evaluate.py`:

| Structural Property | Input Package | Redacted Output Package | Status |
|---|:---:|:---:|:---:|
| Paragraph Count (`<w:p>`) | 106 | 106 | **Identical** |
| Table Count (`<w:tbl>`) | 2 | 2 | **Identical** |
| Character Run Count (`<w:r>`) | 116 | 116 | **Identical** |
| Run Property Signature Hash | `-952778194308119398` | `-952778194308119398` | **Identical** |
| Embedded Media Images | 3 | 3 | **Identical** |
| Hyperlink Rel Targets | 1 | 1 | **Identical** |
| Document Sections | 1 | 1 | **Identical** |

### Formatting Invariant
When a name like `Kus|hal Subbayya |Hegde` spans three runs with formatting `(bold | italic | regular)`, the token projector maps the replacement words word-for-word (`Albert | Thomas | Allen`), ensuring that `Albert` is bold, `Thomas` is italic, and `Allen` is regular. No `<w:rPr>` tags are removed or altered.

---

## 6. Real-World Execution on `Red Herring Prospectus.docx`

The pipeline was executed against the official 400+ page SEBI filing (`Red Herring Prospectus.docx`):

```bash
python -m pii_redactor "Red Herring Prospectus.docx" \
  -o "Red_Herring_Prospectus_Redacted.docx" \
  --report report.json \
  --mapping mapping.json
```

### Execution Metrics
- **Runtime**: **14.77 seconds** (End-to-end processing including OCR and image synthesis)
- **Unique Entities Pseudonymized**: **283**
- **Run-Level XML Text Replacements**: **736**
- **Visual Image Regions Redacted**: **13** (Embedded scanned PAN card and Aadhaar card)
- **Breakdown by Entity Class**:
  - `Organizations`: **79**
  - `Names`: **77**
  - `Contacts`: **64** (Emails, phone numbers, corporate URLs)
  - `Addresses`: **42** (Registered offices, manufacturing plants, residential listings)
  - `Identifiers`: **18** (CIN, DINs, PANs, Aadhaar, SEBI numbers)
  - `Date of Birth`: **3**

### Visual Media Findings
- **Image 7 (`image4.png`, 768x962)**: Scanned Indian PAN card.
  - Redacted: `VISHAL SINGH` $\rightarrow$ `ETHAN GREEN`
  - Redacted: `SUGRIV SINGH` $\rightarrow$ `ADAM GREEN` (Linked family surname preserved)
  - Redacted: `NBWPS1951N` $\rightarrow$ `YVUPD2331F` (Format and PAN holder category `P` preserved)
  - Redacted: `06/05/2000` $\rightarrow$ `11/07/2000`
- **Image 8 (`image5.png`, 900x900)**: Scanned Indian Aadhaar card.
  - Redacted: `MERAJ KHAN` $\rightarrow$ `TROY WARD`
  - Redacted: `Sudhdan Khan` $\rightarrow$ `Daniel Ward` (Linked family surname preserved)
  - Redacted: `2943 6593 3461` $\rightarrow$ `8229 3917 8439` (Verhoeff-valid checksum preserved)
  - Redacted: Multi-line rural address in Katrauli, Phoolpur, Allahabad masked.

---

## 7. Failure Modes & Limitations

1. **Unregistered Entities Lacking Contextual Anchors**:
   - Entities like `"Kotak Mahindra Capital Company"` lack a traditional corporate suffix (`Limited`, `Pvt. Ltd.`, `LLP`). Without an explicit gazetteer entry, heuristic back-traversal does not trigger.
   - *Mitigation*: Enable optional spaCy NER (`--spacy-model en_core_web_lg`) or supply domain allowlists.
2. **Devanagari / Vernacular Identity Cards**:
   - Tesseract OCR defaults to English (`eng`). Indian identity cards containing regional languages (e.g., Hindi names and addresses on Aadhaar cards) require `--ocr-lang eng+hin` and `tesseract-ocr-hin` (pre-configured in `packages.txt`).
3. **Cross-Entity Token Collision**:
   - Pass-2 token propagation replaces standalone occurrences of common family surnames. If an unrelated individual shares a surname with a promoter, both will be mapped to the same synthetic surname. This guarantees privacy, though it may merge distinct references.

---

## 8. Benchmark Reproduction Commands

To reproduce the exact metrics and tables reported above:

```bash
# 1. Generate the benchmark document and ground-truth dataset
python eval/build_benchmark.py

# 2. Execute the evaluation harness
python eval/evaluate.py

# 3. View the generated JSON and Markdown results
cat eval/results/metrics.md
```
