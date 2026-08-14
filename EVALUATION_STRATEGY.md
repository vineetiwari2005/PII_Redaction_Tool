# Evaluation Strategy and Metrics

## Overview

This document describes how we measure the PII Redaction Tool's detection accuracy. The evaluation framework compares the scanner's output against hand-labelled ground truth annotations using span-overlap matching, and reports precision, recall, and F1 score both globally and per entity type.

## Ground Truth Dataset

### Manual Annotation

A set of paragraph samples was manually annotated from the input Red Herring Prospectus. Each annotation records the exact character offsets, surface text, and entity type for every PII instance in the paragraph.

### Stratified Sampling

To avoid bias toward any single content type, paragraphs are sampled from five categories:

- **Contact info** — emails, phones, names
- **Financial text** — jargon-heavy paragraphs to catch false positives
- **Legal boilerplate** — disclaimers and regulatory clauses
- **Promoter lists** — dense name tables
- **PII-free text** — negative samples to verify true negatives

## Matching Algorithm

A detection is considered a **true positive** when it satisfies all three conditions:

1. Same entity type as the ground truth annotation
2. Character overlap ≥ 50% of the ground truth span
3. Character overlap ≥ 50% of the detected span

This bidirectional overlap threshold tolerates minor boundary differences (trailing punctuation, footnote markers) while requiring substantial alignment.

## Metrics

| Metric | Formula | Meaning |
|---|---|---|
| Precision | TP / (TP + FP) | Fraction of detections that are correct |
| Recall | TP / (TP + FN) | Fraction of real entities that are found |
| F1 Score | 2·P·R / (P+R) | Harmonic mean balancing both |

## Results

### Aggregate

| Metric | Value |
|---|---|
| Precision | 0.8553 |
| Recall | 0.8784 |
| F1 Score | 0.8667 |

### Per-Type Breakdown

| Type | P | R | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| EMAIL_ADDRESS | 1.00 | 1.00 | 1.00 | 21 | 0 | 0 |
| PHONE_NUMBER | 1.00 | 1.00 | 1.00 | 7 | 0 | 0 |
| URL | 1.00 | 1.00 | 1.00 | 8 | 0 | 0 |
| IN_CIN | 1.00 | 1.00 | 1.00 | 1 | 0 | 0 |
| PERSON | 0.95 | 0.80 | 0.87 | 20 | 1 | 5 |
| ORGANIZATION | 0.67 | 1.00 | 0.80 | 8 | 4 | 0 |
| LOCATION | 0.00 | 0.00 | 0.00 | 0 | 6 | 4 |

**Pattern-based detectors** (EMAIL, PHONE, URL, CIN) score perfectly because they use deterministic regex.
**NER-based detectors** (PERSON, ORG, LOCATION) exhibit variance inherent to statistical models.

## Limitations

- **Indian names**: spaCy's training corpus is Western-biased, so names like "Kushal Subbayya Hegde" may be missed.
- **Short abbreviations**: Company names like "KSH" lack sufficient context for statistical NER.
- **Address formats**: Indian addresses with village/taluka/gat references are the hardest entity type due to non-standard formatting.
- **Hosted model**: The free-tier deployment uses `en_core_web_sm` (12MB) instead of `en_core_web_lg` (600MB), which reduces NER accuracy.

## Reproducing

```bash
python evaluator.py --ground-truth ground_truth_sample.json --output evaluation_report.md
```

This generates both a Markdown report and a raw JSON file with detailed error lists.
