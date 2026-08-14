# PII Redaction Tool

A Python-based tool that detects and redacts Personally Identifiable Information (PII) from `.docx` documents, replacing every detected entity with opaque black bars (`█████`) to produce traditional-style redacted output.

## How It Works

The tool combines **Microsoft Presidio** (an enterprise PII detection framework) with **spaCy's Named Entity Recognition** and custom regex-based recognizers to find sensitive data across two detection layers:

1. **Regex-based detection** (deterministic, high precision): Emails, phone numbers, URLs, and Indian CIN numbers are caught via pattern matching with context boosting.
2. **NER-based detection** (statistical, high recall): Person names, organization names, and geographic locations are identified via spaCy's trained NER model integrated into Presidio.

### Pipeline Architecture

```
pipeline.py               ← Orchestrates the full redaction workflow
  ├── settings.py          ← Centralised configuration (thresholds, deny-lists)
  ├── docx_processor.py    ← Reads/writes .docx with run-level offset mapping
  ├── scanner.py           ← Presidio analyzer + 4 custom recognizers + post-filters
  ├── redactor.py          ← Stateful blackout mapper (█████ replacement)
  ├── glossary_extractor.py← Auto-parses "Definitions and Abbreviations" for deny-list
  └── evaluator.py         ← Computes precision / recall / F1 against ground truth
```

### Custom Recognizers

| Recognizer | Target | Technique |
|---|---|---|
| `IndianTelephoneRecognizer` | Indian landline/mobile numbers | Regex with telephone context words |
| `WebAddressRecognizer` | Website URLs | Regex for `www.*` and `https://...` |
| `CorporateIdRecognizer` | Indian CIN codes | Regex for the standard 21-character CIN format |
| `NameAfterLabelRecognizer` | Names after "Contact Person:" | Regex with custom `analyze()` override |

### Post-Processing Filters

After detection, the raw results pass through several filters to cut false positives:

- **Confidence thresholds** — per-type minimum scores
- **Static deny-list** — 100+ terms (regulatory acronyms, financial jargon)
- **Auto-generated deny-list** — terms parsed from the document's Definitions section
- **Country/currency suppression** — via `pycountry` database (~500 terms)
- **DOB context gating** — DATE_TIME entities require nearby birth-related context
- **Overlap resolution** — highest-scoring span wins when detections overlap
- **Address merging** — adjacent LOCATION entities are combined into full addresses

## Usage

### Command Line
```bash
python pipeline.py
python pipeline.py --input "path/to/doc.docx" --output "path/to/out.docx"
```

### Web Application
```bash
# Start the FastAPI backend
python -m uvicorn api:app --host 0.0.0.0 --port 8000

# In another terminal, start the Next.js frontend
cd frontend && npm run dev
```

### Evaluation
```bash
python evaluator.py --ground-truth ground_truth_sample.json
```

## Evaluation Results

| Metric | Score |
|---|---|
| Precision | 0.8553 |
| Recall | 0.8784 |
| F1 Score | 0.8667 |

Pattern-based detectors (EMAIL, PHONE, URL, CIN) achieve **perfect F1 = 1.0**. NER-based types (PERSON, ORG, LOCATION) show more variance due to the statistical nature of the model.

## Requirements

- Python 3.10+
- spaCy `en_core_web_lg` (or `en_core_web_sm` for memory-constrained environments)
- Dependencies listed in `requirements.txt`
