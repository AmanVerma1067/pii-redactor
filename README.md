# PII Redactor for Word Documents (`.docx`)

A format-preserving PII (Personally Identifiable Information) detection and pseudonymization tool for Microsoft Word (`.docx`) documents, built for the **Scaler AI Labs** technical assignment.

---

## 1. Project Overview

### What the Assignment Does
This project scans Microsoft Word (`.docx`) documents—such as 400+ page SEBI Red Herring Prospectuses—finds sensitive personal and corporate data in both text and embedded images, and replaces that data with realistic, consistent fake values (pseudonyms) while keeping the document's exact formatting intact.

### What Problem It Solves
Legal and financial documents contain sensitive information (names, PAN/Aadhaar numbers, emails, phone numbers, addresses, and scanned ID cards) that must be anonymized before sharing. Naive approaches fail for three reasons:
1. **Broken formatting**: Assigning `paragraph.text = "..."` in `python-docx` wipes out bold text, italics, font sizes, hyperlinks, and table layouts.
2. **Split words in XML**: Microsoft Word often splits a single word across multiple internal XML runs (`<w:r>`) due to spell-check markers or partial styling (e.g., `"Kus" + "hal " + "Hegde"`), causing simple per-run search to miss entities.
3. **Inconsistent replacements & image leaks**: Replacing names randomly breaks family or corporate relationships (e.g., two promoters with the surname `Hegde` getting unrelated fake surnames), and text-only tools completely miss scanned PAN/Aadhaar cards embedded as images.

### Main Features
- **Two-Pass Consistent Pseudonymization**: Pass 1 discovers all entities across text, tables, headers, footers, and images to build a global cache seeded with `HMAC-SHA256`. Pass 2 replaces every mention consistently across the entire document.
- **Relational Integrity**: Family members sharing a surname (`Kushal Subbayya Hegde` and `Rajesh Kushal Hegde`) automatically receive the same fake surname (`Allen`). Company email domains (`cs.connect@kshinternational.com`) stay synced with the fake company name (`cs.connect@klbinternational.example.com`).
- **Format-Preserving XML Editing**: Projects text replacements directly onto `<w:t>` XML text nodes so bold, italic, underline, font styles, and table structures remain 100% unchanged.
- **Valid Checksums & Statutory Formats**: Fake Aadhaar numbers pass the Verhoeff checksum, fake credit cards pass the Luhn algorithm, and fake PAN numbers preserve the 4th character indicating taxpayer category (`P` for Person, `C` for Company).
- **Embedded Image OCR & Redaction**: Extracts images from `/word/media/`, runs Tesseract OCR to find PII on scanned PAN/Aadhaar cards, blurs portrait photos, pixelates QR codes, and paints fake text over bounding boxes.
- **Dual Interface (CLI + Streamlit Web UI)**: Processes files entirely in memory with downloadable `mapping.json` (re-identification key) and `report.json` (audit log).

### Main Technologies Used
- **Python 3.10+**
- **`python-docx` & `lxml`**: OpenXML package traversal and low-level `<w:t>` XML node manipulation.
- **`Pillow`, `pytesseract`, `opencv-python-headless`, `numpy`**: Image preprocessing, OCR bounding-box extraction, Haar cascade face detection, and QR code masking.
- **`streamlit` & `pandas`**: Interactive web interface and summary charts.
- **`pytest`**: Automated test suite (24 unit tests).

---

## 2. How to Run the Project

### Prerequisites
- **Python**: `>= 3.10`
- **System Packages** (for image OCR and font rendering on Debian/Ubuntu):
  ```bash
  sudo apt-get update && sudo apt-get install -y \
    tesseract-ocr tesseract-ocr-eng tesseract-ocr-hin fonts-dejavu-core libgl1
  ```
  *(Note: If Tesseract is not installed, the tool still works for all text, tables, headers, and metadata, and safely skips image OCR with a warning.)*

### Installation Commands
```bash
# 1. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 2. Install production dependencies
pip install -r requirements.txt

# 3. Install development and test dependencies
pip install -r requirements-dev.txt
```

### Environment Variables
No secret API keys or `.env` files are required because the entire pipeline runs locally in memory without calling external APIs.
- `PORT` *(optional, used in Docker/Render deployment)*: Port number for the Streamlit server (default: `10000` in [`Dockerfile`](file:///home/aman/Desktop/Hackathon/pii-redactor/Dockerfile)).
- Pseudonymization secret salt is passed via the `--salt` CLI flag or the Streamlit sidebar (`default="scaler-ai-labs"`), e.g., `--salt "<YOUR_SECRET_SALT>"`.

### How to Start the Application

#### Option A: Streamlit Web UI
```bash
streamlit run app.py
```

#### Option B: Command-Line Interface (CLI)
```bash
python -m pii_redactor "Red Herring Prospectus.docx" \
  -o "Red_Herring_Prospectus_Redacted.docx" \
  --mapping mapping.json \
  --report report.json \
  --salt "<YOUR_SECRET_SALT>" \
  --image-policy replace \
  -v
```

### How to Run Tests and Benchmark Evaluation
```bash
# Run the 24 unit tests
pytest tests/ -v

# Run the benchmark evaluation harness (Precision, Recall, F1, Leak Test, Structure Check)
python evaluate.py
```

---

## 3. Project Structure

```text
pii-redactor/
├── pii_redactor/               # Core Python package
│   ├── __init__.py             # Public package exports (Redactor, RedactionConfig, etc.)
│   ├── __main__.py             # Enables running `python -m pii_redactor`
│   ├── cli.py                  # Command-line argument parser and runner
│   ├── pipeline.py             # Main two-pass orchestrator (Redactor class)
│   ├── detector.py             # Hybrid PII detector and overlapping span resolver
│   ├── recognizers.py          # Compiled regex rules and checksum/context validators
│   ├── heuristics.py           # Context-aware recognizers for names, orgs, and addresses
│   ├── validators.py           # Verhoeff (Aadhaar), Luhn (Card), IP, and phone validators
│   ├── gazetteer.py            # Indian name dictionaries, stop-words, and regulator allowlists
│   ├── pseudonymizer.py        # Seeded HMAC-SHA256 fake generator and Pass-2 surface matcher
│   ├── docx_engine.py          # Low-level Word XML traversal and run-preserving text replacement
│   ├── image_engine.py         # Embedded image OCR, ID card rules, face blur, and QR masking
│   ├── ner.py                  # Optional spaCy NER adapter (disabled by default)
│   ├── entities.py             # 21 EntityType enum values and the Span data class
│   └── engine.py / ocr.py / patterns.py / anonymizer.py  # Backward-compatible re-export facades
├── tests/                      # Automated unit tests (pytest)
│   ├── test_core.py            # Tests run preservation, salt determinism, and checksums
│   ├── test_images.py          # Tests PAN card OCR and layout-based photo masking
│   └── test_redactor.py        # Tests regex patterns, family surname consistency, and tables
├── eval/                       # Evaluation benchmark suite
│   ├── build_benchmark.py      # Generates synthetic benchmark_rhp.docx and ground_truth.json
│   ├── evaluate.py             # Computes Precision, Recall, F1, leak test, and XML structure diff
│   ├── self_audit.py           # Audits any redacted .docx against its mapping.json for leaks
│   ├── annotate.py             # Helper to create human-reviewed ground truth CSVs
│   └── data/                   # Contains benchmark_rhp.docx and ground_truth.json
├── app.py                      # Streamlit web application entry point
├── evaluate.py                 # Root wrapper script to run eval/evaluate.py
├── EVALUATION.md               # Detailed benchmark metrics and error analysis report
├── requirements.txt            # Production Python dependencies
├── requirements-dev.txt        # Test and benchmark dependencies (pytest, segno)
├── packages.txt                # Debian system packages for Streamlit Cloud (tesseract, fonts)
├── Dockerfile                  # Container build configuration
└── render.yaml                 # Render cloud deployment blueprint
```

---

## 4. Application Flow

From the moment a user uploads a `.docx` file in [`app.py`](file:///home/aman/Desktop/Hackathon/pii-redactor/app.py) or passes a file path to [`cli.py`](file:///home/aman/Desktop/Hackathon/pii-redactor/pii_redactor/cli.py), the data moves through [`Redactor.redact()`](file:///home/aman/Desktop/Hackathon/pii-redactor/pii_redactor/pipeline.py#L58-L127) in four stages:

```text
[User Uploads .docx / Runs CLI]
              │
              ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ STAGE 1: OpenXML Package Extraction (docx_engine.collect_xml_parts)     │
│ - Opens .docx zip in memory via python-docx.                            │
│ - Collects XML trees for body, headers, footers, comments, charts,      │
│   and metadata while skipping styles.xml / fontTable.xml.               │
└─────────────────────────────────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ STAGE 2: Pass 1 — Discovery & Cache Registration (pipeline.py)          │
│ - Reconstructs full paragraph text across split <w:r> runs.             │
│ - PIIDetector runs regex recognizers, checksums (Verhoeff/Luhn), and    │
│   heuristics (honorifics, legal suffixes, PIN-anchored addresses).      │
│ - Extracts structured cells from tables via column/row headers.         │
│ - Registers all findings in Pseudonymizer (seeded with HMAC-SHA256)     │
│   in priority order: ORG -> PERSON -> ADDRESS -> EMAIL -> URL -> IDs.   │
└─────────────────────────────────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ STAGE 3: Multimodal Image Pass (image_engine.ImageRedactor)             │
│ - Iterates over image/* parts in /word/media/.                          │
│ - Upscales small images 2x (Lanczos) and runs Tesseract OCR.            │
│ - Detects PII + ID card layouts (PAN/Aadhaar), registers hits in the    │
│   SAME Pseudonymizer cache, blurs faces/QR codes, and paints fake text. │
└─────────────────────────────────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ STAGE 4: Pass 2 — Run-Safe XML Replacement & Export (docx_engine.py)    │
│ - Compiles all registered surface forms (including surname back-refs    │
│   like "Mr. Hegde") into a single longest-match-first regex.            │
│ - Projects replacements back onto <w:t> leaf nodes in reverse offset    │
│   order, preserving bold/italic/underline formatting on each word.      │
│ - Scrubs hyperlinks, XML attributes, and author metadata.               │
│ - Saves and returns RedactionResult(output_bytes, report, mapping).     │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Important Files and Functions

### 1. [`pii_redactor/pipeline.py`](file:///home/aman/Desktop/Hackathon/pii-redactor/pii_redactor/pipeline.py)
- **Purpose**: Orchestrates the end-to-end two-pass redaction workflow.
- **Important Functions**:
  - [`Redactor.redact(src)`](file:///home/aman/Desktop/Hackathon/pii-redactor/pii_redactor/pipeline.py#L58-L127): Runs Pass 1 (text/table detection and cache registration), the OCR image pass, and Pass 2 (global XML replacement and metadata scrubbing).
- **Inputs**: File path, `bytes`, or binary stream (`src`), plus [`RedactionConfig`](file:///home/aman/Desktop/Hackathon/pii-redactor/pii_redactor/pipeline.py#L27-L38) (salt, image policy, OCR toggle, allowlist).
- **Outputs**: [`RedactionResult`](file:///home/aman/Desktop/Hackathon/pii-redactor/pii_redactor/pipeline.py#L42-L48) containing `output` (`.docx` bytes), `report` (metrics dict), and `mapping` (list of `original -> pseudonym` dicts).
- **Used By**: [`app.py`](file:///home/aman/Desktop/Hackathon/pii-redactor/app.py), [`pii_redactor/cli.py`](file:///home/aman/Desktop/Hackathon/pii-redactor/pii_redactor/cli.py), [`eval/evaluate.py`](file:///home/aman/Desktop/Hackathon/pii-redactor/eval/evaluate.py), and unit tests.

### 2. [`pii_redactor/docx_engine.py`](file:///home/aman/Desktop/Hackathon/pii-redactor/pii_redactor/docx_engine.py)
- **Purpose**: Traverses WordprocessingML XML trees and replaces text inside `<w:t>` nodes without breaking run styles (`<w:rPr>`) or document structure.
- **Important Functions**:
  - [`collect_xml_parts(document)`](file:///home/aman/Desktop/Hackathon/pii-redactor/pii_redactor/docx_engine.py#L52-L66): Collects all text-bearing XML parts in the `.docx` package.
  - [`own_segments(p)`](file:///home/aman/Desktop/Hackathon/pii-redactor/pii_redactor/docx_engine.py#L73-L97): Walks a `<w:p>` paragraph element to collect its `<w:t>` text leaves while skipping nested text-box paragraphs and tracked deletions.
  - [`apply_replacements(segs, reps)`](file:///home/aman/Desktop/Hackathon/pii-redactor/pii_redactor/docx_engine.py#L108-L145): Projects `(start, end, replacement)` character spans back onto individual `<w:t>` nodes in reverse order, aligning words across runs so bold/italic styles stay attached to each word.
  - [`table_context_entities(root)`](file:///home/aman/Desktop/Hackathon/pii-redactor/pii_redactor/docx_engine.py#L245-L268): Extracts entities from tables using column headers (`Name`, `DIN`, `PAN`, `DOB`, `Address`) and key-value row pairs.
  - [`scrub_generic(root, pseudo)`](file:///home/aman/Desktop/Hackathon/pii-redactor/pii_redactor/docx_engine.py#L169-L199) & [`scrub_relationships(document, pseudo)`](file:///home/aman/Desktop/Hackathon/pii-redactor/pii_redactor/docx_engine.py#L202-L212): Anonymizes XML attributes (`author`, `lastModifiedBy`), chart/alt text, and external `mailto:`/web hyperlinks.
- **Inputs**: `python-docx` `Document`, `lxml.etree._Element` XML roots, and `Pseudonymizer`.
- **Outputs**: Mutated XML elements in memory and integer counts of replacements made.
- **Used By**: [`pii_redactor/pipeline.py`](file:///home/aman/Desktop/Hackathon/pii-redactor/pii_redactor/pipeline.py) and [`eval/evaluate.py`](file:///home/aman/Desktop/Hackathon/pii-redactor/eval/evaluate.py).

### 3. [`pii_redactor/pseudonymizer.py`](file:///home/aman/Desktop/Hackathon/pii-redactor/pii_redactor/pseudonymizer.py)
- **Purpose**: Generates deterministic, format-preserving fake values using `HMAC-SHA256` and builds the Pass-2 multi-pattern matcher.
- **Important Functions**:
  - [`register(text, etype)`](file:///home/aman/Desktop/Hackathon/pii-redactor/pii_redactor/pseudonymizer.py#L102-L129): Normalizes and registers a discovered entity during Pass 1, splitting person names into given/surname tokens and organizations into brand tokens.
  - [`fake_for(surface, etype)`](file:///home/aman/Desktop/Hackathon/pii-redactor/pii_redactor/pseudonymizer.py#L172-L183): Returns the cached or newly generated fake string for any surface form, preserving case and format.
  - [`_gen_alnum(etype, key, rng)`](file:///home/aman/Desktop/Hackathon/pii-redactor/pii_redactor/pseudonymizer.py#L437-L497): Produces structurally valid fake IDs (PAN with preserved 4th letter, Aadhaar with Verhoeff digit, Credit Card with Luhn digit, GSTIN synced with PAN).
  - [`replace_spans(text)`](file:///home/aman/Desktop/Hackathon/pii-redactor/pii_redactor/pseudonymizer.py#L550-L565): Uses the compiled regex from [`_build_matcher()`](file:///home/aman/Desktop/Hackathon/pii-redactor/pii_redactor/pseudonymizer.py#L518-L536) to find all registered entities and back-references in Pass 2.
- **Inputs**: Secret `salt` string, original entity strings, and [`EntityType`](file:///home/aman/Desktop/Hackathon/pii-redactor/pii_redactor/entities.py#L8-L30).
- **Outputs**: Deterministic pseudonym strings, `(start, end, fake)` replacement tuples, and the final `mapping()` list.
- **Used By**: [`pii_redactor/pipeline.py`](file:///home/aman/Desktop/Hackathon/pii-redactor/pii_redactor/pipeline.py), [`pii_redactor/docx_engine.py`](file:///home/aman/Desktop/Hackathon/pii-redactor/pii_redactor/docx_engine.py), and [`pii_redactor/image_engine.py`](file:///home/aman/Desktop/Hackathon/pii-redactor/pii_redactor/image_engine.py).

### 4. [`pii_redactor/detector.py`](file:///home/aman/Desktop/Hackathon/pii-redactor/pii_redactor/detector.py)
- **Purpose**: Combines regex recognizers, context heuristics, allowlists, and optional spaCy NER, then resolves overlapping matches.
- **Important Functions**:
  - [`detect_stream(paragraphs, id_context)`](file:///home/aman/Desktop/Hackathon/pii-redactor/pii_redactor/detector.py#L42-L58): Runs all recognizers over paragraphs joined by newlines.
  - [`resolve(spans)`](file:///home/aman/Desktop/Hackathon/pii-redactor/pii_redactor/detector.py#L77-L87): Filters out allowlisted entities (e.g., `SEBI`, `BSE Limited`, `gov.in`) and resolves overlapping [`Span`](file:///home/aman/Desktop/Hackathon/pii-redactor/pii_redactor/entities.py#L53-L64) candidates by keeping higher-confidence checksum-backed hits first, then longer spans.
- **Inputs**: List of paragraph strings and boolean `id_context` (True when scanning an ID card image).
- **Outputs**: Sorted list of non-overlapping [`Span`](file:///home/aman/Desktop/Hackathon/pii-redactor/pii_redactor/entities.py#L53-L64) objects.
- **Used By**: [`pii_redactor/pipeline.py`](file:///home/aman/Desktop/Hackathon/pii-redactor/pii_redactor/pipeline.py) and [`pii_redactor/image_engine.py`](file:///home/aman/Desktop/Hackathon/pii-redactor/pii_redactor/image_engine.py).

### 5. [`pii_redactor/recognizers.py`](file:///home/aman/Desktop/Hackathon/pii-redactor/pii_redactor/recognizers.py) & [`pii_redactor/validators.py`](file:///home/aman/Desktop/Hackathon/pii-redactor/pii_redactor/validators.py)
- **Purpose**: Defines compiled regular expressions for 16+ structured PII types and mathematical checksum validators to prevent false positives.
- **Important Functions**:
  - [`PatternRecognizer.find(text, id_context)`](file:///home/aman/Desktop/Hackathon/pii-redactor/pii_redactor/recognizers.py#L71-L88): Matches a compiled regex, applies optional post-processing (`_trim_phone`, `_dob_not_phone`), verifies context keywords (e.g., `"account no"` before bank accounts, `"dob"` before birth dates), and runs checksum validators.
  - [`verhoeff_ok(num)`](file:///home/aman/Desktop/Hackathon/pii-redactor/pii_redactor/validators.py#L18-L22) & [`luhn_ok(num)`](file:///home/aman/Desktop/Hackathon/pii-redactor/pii_redactor/validators.py#L32-L44): Verify 12-digit Aadhaar numbers and 13–19 digit credit card numbers.
- **Inputs**: Raw text string and `id_context` flag.
- **Outputs**: Iterator of [`Span`](file:///home/aman/Desktop/Hackathon/pii-redactor/pii_redactor/entities.py#L53-L64) objects.
- **Used By**: [`pii_redactor/detector.py`](file:///home/aman/Desktop/Hackathon/pii-redactor/pii_redactor/detector.py) and [`pii_redactor/pseudonymizer.py`](file:///home/aman/Desktop/Hackathon/pii-redactor/pii_redactor/pseudonymizer.py).

### 6. [`pii_redactor/heuristics.py`](file:///home/aman/Desktop/Hackathon/pii-redactor/pii_redactor/heuristics.py) & [`pii_redactor/gazetteer.py`](file:///home/aman/Desktop/Hackathon/pii-redactor/pii_redactor/gazetteer.py)
- **Purpose**: Detects unstructured free-text entities (Indian person names, company names, and postal addresses) without requiring a heavy ML model.
- **Important Classes/Functions**:
  - [`PersonRecognizer.find(text)`](file:///home/aman/Desktop/Hackathon/pii-redactor/pii_redactor/heuristics.py#L45-L48): Detects names after honorifics (`Mr.`, `Ms.`, `Shri`), after role labels (`Contact Person:`, `S/O`), and via capitalized Indian name dictionaries (`FIRST_NAMES`, `SURNAMES`) guarded by `NAME_STOP` (200+ legal/statutory stop-words).
  - [`OrgRecognizer.find(text)`](file:///home/aman/Desktop/Hackathon/pii-redactor/pii_redactor/heuristics.py#L125-L147): Finds legal suffixes (`Private Limited`, `Ltd.`, `LLP`, `& Associates`, `Bank`) and walks backward up to 6 capitalized tokens.
  - [`AddressRecognizer.find(text)`](file:///home/aman/Desktop/Hackathon/pii-redactor/pii_redactor/heuristics.py#L172-L196): Anchors on 6-digit Indian PIN codes (`PIN_RE`), checks for address cue words (`Plot`, `MIDC`, `Taluka`, `Road`), and walks backward via `_walk_back()` to capture the full address block.
- **Inputs**: Text string.
- **Outputs**: Iterator of [`Span`](file:///home/aman/Desktop/Hackathon/pii-redactor/pii_redactor/entities.py#L53-L64) objects for `PERSON`, `ORG`, and `ADDRESS`.
- **Used By**: [`pii_redactor/detector.py`](file:///home/aman/Desktop/Hackathon/pii-redactor/pii_redactor/detector.py) and [`pii_redactor/docx_engine.py`](file:///home/aman/Desktop/Hackathon/pii-redactor/pii_redactor/docx_engine.py).

### 7. [`pii_redactor/image_engine.py`](file:///home/aman/Desktop/Hackathon/pii-redactor/pii_redactor/image_engine.py)
- **Purpose**: Extracts embedded images from the `.docx` package, runs OCR and computer vision, and masks or replaces visual PII in place.
- **Important Functions**:
  - [`ImageRedactor.ocr(img)`](file:///home/aman/Desktop/Hackathon/pii-redactor/pii_redactor/image_engine.py#L138-L146): Converts to grayscale, upscales small images 2x, and runs Tesseract (`--psm 3`, falling back to `--psm 11` if `< 6` words are found).
  - [`ImageRedactor.detect(lines)`](file:///home/aman/Desktop/Hackathon/pii-redactor/pii_redactor/image_engine.py#L163-L172) & [`_id_rules(lines)`](file:///home/aman/Desktop/Hackathon/pii-redactor/pii_redactor/image_engine.py#L174-L209): Runs `PIIDetector` on each OCR line and applies ID-card layout rules when `>= 2` ID keywords (`income tax`, `aadhaar`, `dob`, etc.) appear on the image.
  - [`_qr_and_faces(img, rep, lines)`](file:///home/aman/Desktop/Hackathon/pii-redactor/pii_redactor/image_engine.py#L430-L451): Detects QR codes (`cv2.QRCodeDetector` + Canny edge morphology fallback) and faces (`cv2.CascadeClassifier` on raw + histogram-equalized grayscale, plus `_portrait_from_layout` geometric fallback).
  - [`_paint(img, box, fake)`](file:///home/aman/Desktop/Hackathon/pii-redactor/pii_redactor/image_engine.py#L274-L291): Samples the median border color around the text box for the background fill and draws the pseudonym in the darkest local text color.
- **Inputs**: OpenXML image part (`part.blob`).
- **Outputs**: Overwrites `part._blob` in memory and returns an [`ImageReport`](file:///home/aman/Desktop/Hackathon/pii-redactor/pii_redactor/image_engine.py#L97-L107).
- **Used By**: [`pii_redactor/pipeline.py`](file:///home/aman/Desktop/Hackathon/pii-redactor/pii_redactor/pipeline.py) and [`app.py`](file:///home/aman/Desktop/Hackathon/pii-redactor/app.py).

### 8. [`app.py`](file:///home/aman/Desktop/Hackathon/pii-redactor/app.py)
- **Purpose**: Provides the interactive Streamlit web interface.
- **Important Functions**:
  - [`get_redactor(salt, policy, ocr, use_spacy, allow)`](file:///home/aman/Desktop/Hackathon/pii-redactor/app.py#L30-L33): Cached resource builder (`@st.cache_resource`) that initializes `Redactor` once per configuration.
- **Inputs**: User-uploaded `.docx` byte buffer and sidebar settings.
- **Outputs**: Downloadable `_redacted.docx`, `mapping.json`, and `report.json`.

---

## 6. Technology and Dependency Choices

Every dependency in [`requirements.txt`](file:///home/aman/Desktop/Hackathon/pii-redactor/requirements.txt) and [`requirements-dev.txt`](file:///home/aman/Desktop/Hackathon/pii-redactor/requirements-dev.txt) was selected for a specific role in the codebase:

- **`python-docx>=1.1` (Production)**: Required to open `.docx` files as Open Packaging Convention (OPC) zip archives, iterate over internal XML and media parts (`doc.part.package.iter_parts()`), inspect external hyperlink relationships, and re-save the package.
- **`lxml>=4.9` (Production)**: Used directly in [`docx_engine.py`](file:///home/aman/Desktop/Hackathon/pii-redactor/pii_redactor/docx_engine.py) for fast C-based XML tree traversal (`root.iter()`), reading/writing `<w:t>` text nodes, and serializing standalone XML parts (`etree.fromstring`, `etree.tostring`).
- **`Pillow>=10.1` (Production)**: Used in [`image_engine.py`](file:///home/aman/Desktop/Hackathon/pii-redactor/pii_redactor/image_engine.py) to decode image blobs, convert to grayscale, resize with Lanczos interpolation, apply Gaussian blur, and draw replacement text using TrueType fonts (`ImageFont`, `ImageDraw`).
- **`pytesseract>=0.3.10` (Production)**: Wraps the local `tesseract-ocr` binary (`image_to_data`) to get word-level text and pixel bounding boxes from embedded images without sending sensitive images to external cloud OCR APIs.
- **`opencv-python-headless>=4.8,<5` (Production)**: Used in [`image_engine.py`](file:///home/aman/Desktop/Hackathon/pii-redactor/pii_redactor/image_engine.py) for QR code detection (`cv2.QRCodeDetector`), Canny edge morphology (`cv2.Canny`, `cv2.findContours`), and frontal-face Haar cascades (`cv2.CascadeClassifier`). The `-headless` variant avoids unnecessary GUI/X11 libraries in Docker, and `<5` is pinned because OpenCV 5.0 drops `cv2.CascadeClassifier` from the main package.
- **`numpy>=1.24` (Production)**: Converts Pillow images into array buffers for OpenCV processing in [`image_engine.py`](file:///home/aman/Desktop/Hackathon/pii-redactor/pii_redactor/image_engine.py).
- **`streamlit>=1.36` & `pandas>=2.0` (Production UI)**: Used in [`app.py`](file:///home/aman/Desktop/Hackathon/pii-redactor/app.py) to provide the file-upload UI, bar charts (`pd.Series`), and interactive mapping table (`pd.DataFrame`).
- **`pytest>=8` & `segno>=1.5` (Development)**: `pytest` runs the 24 unit tests in `tests/`. `segno` is used in [`eval/build_benchmark.py`](file:///home/aman/Desktop/Hackathon/pii-redactor/eval/build_benchmark.py) to generate synthetic Aadhaar QR codes for the benchmark `.docx`.

---

## 7. Error Handling and Edge Cases

### Handled in the Code
1. **Split XML Runs (`Kus|hal Subbayya |Hegde`)**: Handled in [`docx_engine.py`](file:///home/aman/Desktop/Hackathon/pii-redactor/pii_redactor/docx_engine.py#L108-L145) by concatenating `<w:t>` segments per paragraph for detection, then projecting replacement words back into the original `<w:t>` elements in reverse character-offset order.
2. **Statutory Terms Mistaken for Names (`"Compliance Officer is responsible..."`)**: Handled in [`gazetteer.py`](file:///home/aman/Desktop/Hackathon/pii-redactor/pii_redactor/gazetteer.py#L44-L64) and [`heuristics.py`](file:///home/aman/Desktop/Hackathon/pii-redactor/pii_redactor/heuristics.py#L60-L75) using a 200+ word `NAME_STOP` set and requiring explicit punctuation (`:` or `-`) or uppercase tokens after role labels.
3. **Public Regulators (`SEBI`, `BSE Limited`, `RBI`, `NSE`)**: Preserved via `DEFAULT_ALLOWLIST` and `ALLOWLIST_DOMAINS` (`sebi.gov.in`, `bseindia.com`) in [`detector.py`](file:///home/aman/Desktop/Hackathon/pii-redactor/pii_redactor/detector.py#L65-L75) so public market institutions are not falsely redacted.
4. **Phone Numbers Mistaken for Dates of Birth (`Tel: 91-20-2721 8080`)**: Handled in [`recognizers.py`](file:///home/aman/Desktop/Hackathon/pii-redactor/pii_redactor/recognizers.py#L119-L133) via `_dob_ok()` (validates day 1–31, month 1–12, year 1920–present) and `_dob_not_phone()` (rejects matches preceded by `Tel`, `Fax`, `Phone`, or `Mob`).
5. **Version Numbers & Indian Currency Mistaken for IPs / Bank Accounts**: `ip_ok()` in [`validators.py`](file:///home/aman/Desktop/Hackathon/pii-redactor/pii_redactor/validators.py#L54-L62) requires at least one IPv4 octet `> 9` (so `Version 2.1.4.0` is ignored), and numeric regexes use comma/decimal negative lookarounds so Indian lakh/crore amounts (`1,84,89,583`) are untouched.
6. **Blurry ID Card Photos & QR Codes**: If Haar face detection finds 0 faces on an ID card, [`_portrait_from_layout()`](file:///home/aman/Desktop/Hackathon/pii-redactor/pii_redactor/image_engine.py#L373-L408) locates the portrait geometrically relative to text headers. If an image has ID card keywords (`aadhaar`, `income tax`) but yields 0 OCR hits, a **failsafe Gaussian blur** is applied to the entire image ([`image_engine.py`](file:///home/aman/Desktop/Hackathon/pii-redactor/pii_redactor/image_engine.py#L482-L484)).
7. **Missing Optional Dependencies (`tesseract`, `cv2`, `spacy`)**: Gracefully handled with `try/except` imports and runtime availability checks (`ImageRedactor.available()`, `load_ner()`), logging a warning and continuing rather than crashing.
8. **Unsupported Image Formats (EMF/WMF) or Corrupted Uploads**: Caught in [`process_part()`](file:///home/aman/Desktop/Hackathon/pii-redactor/pii_redactor/image_engine.py#L455-L458) (`rep.skipped = "unsupported image format"`) and in [`app.py`](file:///home/aman/Desktop/Hackathon/pii-redactor/app.py#L41-L43) (`st.error(...)`).

### Not Handled Yet
- **Password-Protected / Encrypted `.docx` Files**: `python-docx` cannot open encrypted Office files; uploading one raises an error message in the UI.
- **Legacy `.doc` (Binary Word 97–2003) or PDF Files**: Only OpenXML `.docx` files are supported.
- **Rotated (90°/180°) Scanned ID Cards**: OCR assumes upright text orientation.

---

## 8. Interview Questions and Short Answers

### 1. Explain the overall architecture of your project.
> "I built a deterministic, two-pass pipeline in Python. In Pass 1, the engine extracts text from all Word XML parts—body paragraphs, tables, headers, footers—and runs Tesseract OCR on embedded images to detect PII using regex, checksum validators, and context heuristics. Every detected entity is registered in a global `HMAC-SHA256` pseudonym cache. In Pass 2, it compiles all registered surface forms into a single matcher and projects replacements back onto the `<w:t>` XML leaf nodes and image bounding boxes, preserving 100% of the document's formatting."

### 2. What happens when the application starts?
> "In the Streamlit web app (`app.py`), starting the app renders the settings sidebar and file uploader. When a user uploads a `.docx`, `@st.cache_resource` initializes the `Redactor` instance—which compiles the 23 regex recognizers and loads the gazetteer sets once in memory—and then calls `Redactor.redact()` on the uploaded byte stream without writing anything to disk."

### 3. Why didn't you just assign `paragraph.text = redacted_text` in `python-docx`?
> "In Word XML, a paragraph `<w:p>` is made of multiple `<w:r>` runs, and each run holds its own styling like bold, italic, or font size in `<w:rPr>`. Word also splits single words across multiple runs because of spell-check markers or revision IDs. Assigning `paragraph.text` deletes all child runs and wipes out all inline formatting. Instead, `docx_engine.py` concatenates the `<w:t>` text nodes to detect entities, and then `apply_replacements()` writes the fake words back into the existing `<w:t>` nodes."

### 4. Walk me through `apply_replacements()` in `docx_engine.py`.
> "`apply_replacements()` takes the list of `<w:t>` segments in a paragraph and the list of `(start, end, replacement)` spans. First, it sorts replacements from right to left (`-r[0]`) so changing text at the end doesn't shift character offsets earlier in the paragraph. Next, if the original entity and fake name have the same number of words, it maps each fake word into the exact `<w:t>` run where the original word started, preserving per-word bold or italic styling. Finally, it sets `xml:space='preserve'` so Word doesn't strip spaces."

### 5. Why does the pipeline use two passes instead of replacing PII in a single pass?
> "Single-pass replacement misses back-references and formatting variations. For example, a promoter is introduced on page 1 as `'Mr. Kushal Subbayya Hegde'`, which our honorific rule catches, and on page 50 is referred to simply as `'Mr. Hegde'` or in lowercase as `'kushal hegde'`. By registering full entities in Pass 1—sorted with organizations and full names first—Pass 2 knows every surname token and company brand root and replaces all variations consistently across the entire document."

### 6. How do you ensure family members keep the same fake last name?
> "In `pseudonymizer.py`, when `_register_person()` processes a full name like `'Kushal Subbayya Hegde'`, it separates given names from the final surname token and hashes each token with its role using `HMAC-SHA256`, like `SUR|hegde`. When `'Rajesh Kushal Hegde'` is registered next, its surname `'Hegde'` hits the exact same `SUR|hegde` cache entry and gets `'Allen'`. That way, family relationships in promoter tables stay intact."

### 7. How do you keep email addresses consistent with fake person and company names?
> "In `pipeline.py`, `REGISTER_ORDER` registers `ORG` and `PERSON` entities before `EMAIL` and `URL`. When `_fake_email()` runs on `'cs.connect@kshinternational.com'`, it checks `org_groups`, sees that `'ksh'` mapped to `'klb'`, and rewrites the domain to `'klbinternational.example.com'`. For personal emails like `'rashhi.patil@gmail.com'`, `_fake_local()` even uses a Levenshtein distance-1 check (`_lev1`) to match `'rashhi'` to the registered name `'Rashi'`."

### 8. Why did you choose Regex + Heuristics over calling an LLM or large Transformer NER by default?
> "Three reasons: privacy, speed, and determinism. Sending a 400-page unredacted IPO prospectus to an external LLM API leaks sensitive PII to a third party. And running a large Transformer on CPU over 400 pages takes several minutes and often mistakes capitalized legal definitions for company names. Our regex, checksum, and heuristic pipeline processes the 400-page prospectus in 15 seconds on CPU with zero external network calls and 100% reproducible outputs."

### 9. How do you avoid false positives on capitalized legal phrases in a prospectus?
> "Prospectuses are full of capitalized phrases like `'Book Running Lead Manager'` or `'Company Secretary and Compliance Officer'`. We prevent false positives using three layers: first, a 200-word `NAME_STOP` dictionary in `gazetteer.py` that blocks legal and role words from being treated as names; second, an allowlist of public regulators like `SEBI`, `BSE Limited`, and `RBI`; and third, checksum validators like Verhoeff for Aadhaar and Luhn for credit cards."

### 10. How does embedded image redaction work in `image_engine.py`?
> "We iterate through all `image/*` parts in the `.docx` package. Small scans are upscaled 2x using Lanczos interpolation and passed to Tesseract OCR to get word bounding boxes. We run `PIIDetector` plus ID-card layout rules for PAN and Aadhaar cards. Before painting fake text, we obscure QR codes and blur faces—using Haar cascades plus a geometric layout fallback if a face is too blurry. Then we fill each word box with its median border background color and draw the pseudonym."

### 11. Why did you pin `opencv-python-headless>=4.8,<5` in `requirements.txt`?
> "We use `elements` of OpenCV for QR code detection and frontal face detection on ID cards via `cv2.CascadeClassifier`. OpenCV 5.0 removed `CascadeClassifier` from the main package, which would disable Haar face detection. We also chose the `headless` build so Docker deployments don't install unnecessary desktop X11/Qt GUI libraries."

### 12. How do you evaluate accuracy, and why is there a difference between strict and lenient metrics?
> "We built a synthetic benchmark (`eval/build_benchmark.py`) with 75 ground-truth entities and 43 negative traps. Under lenient matching, we achieve 1.000 Precision, 0.959 Recall (0.979 F1), and 98.7% end-to-end leak removal, with 43 out of 43 negative traps preserved. Strict precision is 0.958 only because Tesseract splits a 3-line Aadhaar card address into 3 separate lines—we redact all 3 lines, which strict string equality counts as 3 false positives and 1 false negative."

### 13. What happens if someone uploads an invalid file or if Tesseract is not installed?
> "In `app.py`, the uploader restricts files to `.docx` and wraps `redact()` in a `try/except` block that displays a clean `st.error` message instead of a stack trace. If Tesseract is missing on the server, `ImageRedactor.available()` returns `False`, the UI disables the OCR toggle with a warning banner, and text/table redaction proceeds normally."

### 14. What would you improve if you had more time?
> "First, I would normalize punctuation and line-break variations when matching addresses in Pass 2 so address variants like `'Tower-2'` vs `'Tower 2'` are caught automatically. Second, I would replace the Pass-2 regex union in `_build_matcher()` with an Aho-Corasick automaton so matching scales in $O(N)$ linear time even with thousands of entities. Third, I would parallelize OCR across multiple images using a process pool."

---

## 9. Limitations and Possible Improvements

### Existing Features (Implemented & Verified)
- Two-pass text, table, header, footer, hyperlink, and metadata pseudonymization.
- Word-aligned `<w:t>` XML replacement that preserves bold, italic, underline, and font properties.
- Checksum-valid fake generation for Aadhaar (Verhoeff) and credit cards (Luhn), plus format-preserving PAN, CIN, GSTIN, DIN, and SEBI registration numbers.
- In-place image OCR, face blurring, QR code pixelation, and background-matched text painting.

### Genuine Limitations Visible in the Code
1. **Unlabeled Uncommon Names & Suffix-less Orgs in Prose**: As documented in [`EVALUATION.md`](file:///home/aman/Desktop/Hackathon/pii-redactor/EVALUATION.md#L128-L133), if an organization has no legal suffix (`"Kotak Mahindra Capital Company"`) or a person has an uncommon name not in [`gazetteer.py`](file:///home/aman/Desktop/Hackathon/pii-redactor/pii_redactor/gazetteer.py) with no honorific or label (`"Subbayya Gowda"`), rule-based detection misses them unless optional spaCy NER (`--spacy-model`) is enabled.
2. **Address Punctuation Variants on Real Documents**: In Pass 2, [`_build_matcher()`](file:///home/aman/Desktop/Hackathon/pii-redactor/pii_redactor/pseudonymizer.py#L518-L536) matches exact normalized token sequences. If the same office address is repeated elsewhere with different punctuation (`"Tower-2"` vs `"Tower 2"`, or `"Building No."` vs `"No"`), the variant copy can survive unless caught independently by `AddressRecognizer`.
3. **Surname Token Propagation Over-Matching**: Registering a person's surname replaces any standalone capitalized occurrence of that token in Pass 2. If a surname is also part of an unrelated proper noun not in `COMMON_WORD_NAMES`, it will also be replaced.
4. **Sequential Image OCR**: [`pipeline.py`](file:///home/aman/Desktop/Hackathon/pii-redactor/pii_redactor/pipeline.py#L91-L93) processes embedded images sequentially in a `for` loop (~1–2 seconds per image).

### Realistic Future Improvements
- **Fuzzy / Token-Normalized Address Matching in Pass 2**: Normalize hyphens and abbreviations (`No.` / `No`, `Rd.` / `Road`) in `_build_matcher()` to eliminate partial address leaks.
- **Aho-Corasick Multi-Pattern Matcher**: Replace the large alternating regex (`|`.join) in `_build_matcher()` with an Aho-Corasick trie for faster Pass-2 scanning on massive documents.
- **Parallel Image OCR**: Use `concurrent.futures.ProcessPoolExecutor` to run Tesseract OCR on embedded images concurrently, followed by deterministic sequential registration in `Pseudonymizer`.

---

## 10. Five-Minute Project Walkthrough (Interview Script)

> **1. Introduction & Problem (45 seconds)**  
> "Hi! For my assignment, I built `pii-redactor`, an engine that detects and consistently pseudonymizes sensitive PII inside complex Microsoft Word `.docx` files—specifically tested on a 400-page SEBI Red Herring Prospectus.  
> When I looked at the problem, I realized two things break most redaction tools on Word documents: first, Word splits visible words across multiple internal `<w:r>` XML runs, and using `paragraph.text = ...` wipes out all bolding, italics, and fonts. Second, PII appears across both text and scanned KYC ID cards like PAN and Aadhaar, and replacing entities randomly destroys relationships—like family members sharing a last name or company emails matching the company name."
>
> **2. Two-Pass Architecture (1 minute)**  
> "To solve this, I designed a deterministic **Two-Pass Pipeline** orchestrated in [`pii_redactor/pipeline.py`](file:///home/aman/Desktop/Hackathon/pii-redactor/pii_redactor/pipeline.py).  
> In **Pass 1**, we extract text from every XML part in the `.docx` zip—body paragraphs, tables, headers, footers, comments—and run [`PIIDetector`](file:///home/aman/Desktop/Hackathon/pii-redactor/pii_redactor/detector.py). Instead of replacing immediately, Pass 1 registers every discovered entity into a global [`Pseudonymizer`](file:///home/aman/Desktop/Hackathon/pii-redactor/pii_redactor/pseudonymizer.py) seeded with `HMAC-SHA256`.  
> Next, we run our **Multimodal Image Pass** ([`image_engine.py`](file:///home/aman/Desktop/Hackathon/pii-redactor/pii_redactor/image_engine.py)), which OCRs embedded images and registers image PII into that exact same `Pseudonymizer` cache.  
> Finally, in **Pass 2**, the `Pseudonymizer` compiles every known entity—including surname back-references like `'Mr. Hegde'` and company brand tokens—into a longest-match-first regex and projects the replacements back into the Word XML and image pixels."
>
> **3. Deep Dive: Core Modules & Technical Decisions (2 minutes)**  
> "Let me highlight the four most important modules:  
> - First, **[`docx_engine.py`](file:///home/aman/Desktop/Hackathon/pii-redactor/pii_redactor/docx_engine.py)**: In `own_segments()` and `apply_replacements()`, we build a character-offset map over a paragraph's `<w:t>` leaf nodes. When we replace `'Kushal Subbayya Hegde'` split across bold and italic runs with `'Albert Thomas Allen'`, we map each fake word back into the run that held the corresponding original word, in reverse offset order. Zero `<w:rPr>` formatting tags are ever lost.  
> - Second, **[`recognizers.py`](file:///home/aman/Desktop/Hackathon/pii-redactor/pii_redactor/recognizers.py), [`heuristics.py`](file:///home/aman/Desktop/Hackathon/pii-redactor/pii_redactor/heuristics.py), and [`validators.py`](file:///home/aman/Desktop/Hackathon/pii-redactor/pii_redactor/validators.py)**: We combine 23 compiled regex patterns with Verhoeff checksums for Aadhaar and Luhn checksums for credit cards. For unstructured text, `heuristics.py` uses honorifics, role labels, legal suffixes (`Private Limited`, `LLP`), and 6-digit PIN-code backward traversal for addresses. To prevent false positives on legal prose, [`gazetteer.py`](file:///home/aman/Desktop/Hackathon/pii-redactor/pii_redactor/gazetteer.py) enforces a 200-word `NAME_STOP` vocabulary and allowlists regulators like `SEBI` and `BSE Limited`.  
> - Third, **[`pseudonymizer.py`](file:///home/aman/Desktop/Hackathon/pii-redactor/pii_redactor/pseudonymizer.py)**: By hashing individual name tokens with roles (`SUR|hegde`), all members of the Hegde promoter family get the surname `'Allen'`. And in `_gen_alnum()`, fake IDs preserve statutory rules—like keeping the 4th character of a PAN card (`P` for Individual) and syncing the PAN inside a company's 15-character GSTIN.  
> - Fourth, **[`image_engine.py`](file:///home/aman/Desktop/Hackathon/pii-redactor/pii_redactor/image_engine.py)**: For embedded PAN and Aadhaar scans, we upscale small images 2x, run Tesseract OCR, blur portrait photos using OpenCV Haar cascades with a geometric layout fallback, pixelate QR codes, and paint fake text matched to the local background color."
>
> **4. Results & Limitations (1 minute)**  
> "To verify everything, I built an automated test suite (`tests/`) and a ground-truth benchmark (`eval/evaluate.py`) with 75 annotated entities and 43 negative traps. On the benchmark, the engine achieves **100% lenient precision, 95.9% detection recall, 98.7% end-to-end leak removal, and preserves 43 out of 43 negative traps** with 100% identical XML structure. On the real 400-page Red Herring Prospectus, it processes the entire document in **~15 seconds**.  
> The main limitation of the default rule-based mode is that an organization without a legal suffix (like `'Kotak Mahindra Capital Company'`) or an unlabeled person with an unseen surname in free prose can be missed unless the optional spaCy NER flag is enabled, and address variants with different punctuation in Pass 2 could be improved with fuzzy token normalization. I'd be happy to open any file and dive deeper!"
