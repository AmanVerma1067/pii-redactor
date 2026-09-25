# Results on `benchmark_rhp.docx`

75 annotated entities, 43 negative traps, runtime 3.15s.

## Detection (strict matching)

| Class | TP | FP | FN | Precision | Recall | F1 | Accuracy (TP/(TP+FP+FN)) |
|---|---|---|---|---|---|---|---|
| Names | 15 | 0 | 1 | 1.000 | 0.938 | 0.968 | 0.938 |
| Organizations | 7 | 0 | 1 | 1.000 | 0.875 | 0.933 | 0.875 |
| Identifiers | 21 | 0 | 0 | 1.000 | 1.000 | 1.000 | 1.000 |
| Financial | 3 | 0 | 0 | 1.000 | 1.000 | 1.000 | 1.000 |
| Addresses | 5 | 3 | 1 | 0.625 | 0.833 | 0.714 | 0.556 |
| Contacts | 11 | 0 | 0 | 1.000 | 1.000 | 1.000 | 1.000 |
| DOB | 8 | 0 | 0 | 1.000 | 1.000 | 1.000 | 1.000 |
| **ALL** | 70 | 3 | 3 | 0.959 | 0.959 | 0.959 | 0.921 |

False negatives: `{"Organizations": ["Axis Bank Limited"], "Addresses": ["saray dan shah, Katrauli, Poore Durgi, Phoolpur, Allahabad, UP 212402"], "Names": ["rakhi shetty"]}`

False positives: `{"Addresses": ["Allahabad, UP 212402 [ADDRESS]", "Katrauli, Poore Durgi, Phoolpur, [ADDRESS]", "saray dan shah, [ADDRESS]"]}`

## Detection (lenient matching)

| Class | TP | FP | FN | Precision | Recall | F1 | Accuracy (TP/(TP+FP+FN)) |
|---|---|---|---|---|---|---|---|
| Names | 15 | 0 | 1 | 1.000 | 0.938 | 0.968 | 0.938 |
| Organizations | 8 | 0 | 0 | 1.000 | 1.000 | 1.000 | 1.000 |
| Identifiers | 21 | 0 | 0 | 1.000 | 1.000 | 1.000 | 1.000 |
| Financial | 3 | 0 | 0 | 1.000 | 1.000 | 1.000 | 1.000 |
| Addresses | 6 | 0 | 0 | 1.000 | 1.000 | 1.000 | 1.000 |
| Contacts | 11 | 0 | 0 | 1.000 | 1.000 | 1.000 | 1.000 |
| DOB | 8 | 0 | 0 | 1.000 | 1.000 | 1.000 | 1.000 |
| **ALL** | 72 | 0 | 1 | 1.000 | 0.986 | 0.993 | 0.986 |

False negatives: `{"Names": ["rakhi shetty"]}`

False positives: `{}`

## End-to-end leak test (output package incl. OCR of output images)

**75/75 PII values removed (redaction recall 1.000)**

| Class | Values | Leaked | Redaction recall |
|---|---|---|---|
| Names | 18 | 0 | 1.000 |
| Organizations | 8 | 0 | 1.000 |
| Identifiers | 21 | 0 | 1.000 |
| Financial | 3 | 0 | 1.000 |
| Addresses | 6 | 0 | 1.000 |
| Contacts | 11 | 0 | 1.000 |
| DOB | 8 | 0 | 1.000 |

Leaks: none

Partial token leaks (a distinctive name/org token survives somewhere): none

## Over-redaction traps

43/43 preserved

## Consistency & structure

- One pseudonym per entity: yes
- Structure identical (paragraphs, tables, runs, run formatting, images, hyperlinks, sections): True {'paragraphs': True, 'tables': True, 'runs': True, 'run_format_signature': True, 'images': True, 'hyperlinks': True, 'sections': True}
