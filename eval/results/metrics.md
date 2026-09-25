# Results on `benchmark_rhp.docx`

75 annotated entities, 43 negative traps, runtime 3.17s.

## Detection (strict matching)

| Class | TP | FP | FN | Precision | Recall | F1 | Accuracy (TP/(TP+FP+FN)) |
|---|---|---|---|---|---|---|---|
| Names | 14 | 0 | 2 | 1.000 | 0.875 | 0.933 | 0.875 |
| Organizations | 7 | 0 | 1 | 1.000 | 0.875 | 0.933 | 0.875 |
| Identifiers | 21 | 0 | 0 | 1.000 | 1.000 | 1.000 | 1.000 |
| Financial | 3 | 0 | 0 | 1.000 | 1.000 | 1.000 | 1.000 |
| Addresses | 5 | 3 | 1 | 0.625 | 0.833 | 0.714 | 0.556 |
| Contacts | 11 | 0 | 0 | 1.000 | 1.000 | 1.000 | 1.000 |
| DOB | 8 | 0 | 0 | 1.000 | 1.000 | 1.000 | 1.000 |
| **ALL** | 69 | 3 | 4 | 0.958 | 0.945 | 0.952 | 0.908 |

False negatives: `{"Organizations": ["Kotak Mahindra Capital Company"], "Addresses": ["saray dan shah, Katrauli, Poore Durgi, Phoolpur, Allahabad, UP 212402"], "Names": ["rakhi shetty", "Subbayya Gowda"]}`

False positives: `{"Addresses": ["Allahabad, UP 212402 [ADDRESS]", "Katrauli, Poore Durgi, Phoolpur, [ADDRESS]", "saray dan shah, [ADDRESS]"]}`

## Detection (lenient matching)

| Class | TP | FP | FN | Precision | Recall | F1 | Accuracy (TP/(TP+FP+FN)) |
|---|---|---|---|---|---|---|---|
| Names | 14 | 0 | 2 | 1.000 | 0.875 | 0.933 | 0.875 |
| Organizations | 7 | 0 | 1 | 1.000 | 0.875 | 0.933 | 0.875 |
| Identifiers | 21 | 0 | 0 | 1.000 | 1.000 | 1.000 | 1.000 |
| Financial | 3 | 0 | 0 | 1.000 | 1.000 | 1.000 | 1.000 |
| Addresses | 6 | 0 | 0 | 1.000 | 1.000 | 1.000 | 1.000 |
| Contacts | 11 | 0 | 0 | 1.000 | 1.000 | 1.000 | 1.000 |
| DOB | 8 | 0 | 0 | 1.000 | 1.000 | 1.000 | 1.000 |
| **ALL** | 70 | 0 | 3 | 1.000 | 0.959 | 0.979 | 0.959 |

False negatives: `{"Organizations": ["Kotak Mahindra Capital Company"], "Names": ["rakhi shetty", "Subbayya Gowda"]}`

False positives: `{}`

## End-to-end leak test (output package incl. OCR of output images)

**74/75 PII values removed (redaction recall 0.987)**

| Class | Values | Leaked | Redaction recall |
|---|---|---|---|
| Names | 18 | 0 | 1.000 |
| Organizations | 8 | 1 | 0.875 |
| Identifiers | 21 | 0 | 1.000 |
| Financial | 3 | 0 | 1.000 |
| Addresses | 6 | 0 | 1.000 |
| Contacts | 11 | 0 | 1.000 |
| DOB | 8 | 0 | 1.000 |

Leaks: `Kotak Mahindra Capital Company` (ORG, no legal suffix)

Partial token leaks (a distinctive name/org token survives somewhere): `Kotak (from 'Kotak Mahindra Capital Company')`, `Mahindra (from 'Kotak Mahindra Capital Company')`, `Gowda (from 'Subbayya Gowda')`

## Over-redaction traps

43/43 preserved

## Consistency & structure

- One pseudonym per entity: yes
- Structure identical (paragraphs, tables, runs, run formatting, images, hyperlinks, sections): True {'paragraphs': True, 'tables': True, 'runs': True, 'run_format_signature': True, 'images': True, 'hyperlinks': True, 'sections': True}
