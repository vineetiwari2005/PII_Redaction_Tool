"""
Evaluation harness for the PII Redaction Tool.

Compares scanner output against hand-labelled ground truth using
span-overlap matching to compute precision, recall, and F1 score.

Usage:
    python evaluator.py
    python evaluator.py --ground-truth ground_truth_sample.json
"""

import argparse
import json
import sys
from typing import List, Dict, Optional, Set

from settings import GROUND_TRUTH, SOURCE_DOC
from scanner import build_analyzer, scan_for_sensitive_data
from glossary_extractor import extract_glossary_from_path


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_annotations(path: str) -> List[dict]:
    """Read ground truth annotations from a JSON file."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Evaluation logic
# ---------------------------------------------------------------------------

def run_evaluation(
    annotations: List[dict],
    analyzer,
    deny_supplement: Optional[Set[str]] = None,
) -> dict:
    """
    Compare scanner detections against ground truth using
    bidirectional span-overlap matching (≥50% in each direction).
    """
    tp_all = fp_all = fn_all = 0
    per_type: Dict[str, Dict[str, int]] = {}
    fp_list: List[dict] = []
    fn_list: List[dict] = []

    for sample in annotations:
        text = sample["text"]
        expected = sample["entities"]

        found = scan_for_sensitive_data(
            analyzer, text, supplementary_deny=deny_supplement,
        )

        matched_exp: set = set()
        matched_det: set = set()

        for d_i, det in enumerate(found):
            for e_i, exp in enumerate(expected):
                if e_i in matched_exp:
                    continue
                ol_start = max(det.start, exp["start"])
                ol_end = min(det.end, exp["end"])
                overlap = max(0, ol_end - ol_start)
                exp_len = exp["end"] - exp["start"]
                det_len = det.end - det.start

                if (overlap >= 0.5 * exp_len
                        and overlap >= 0.5 * det_len
                        and det.category == exp["type"]):
                    matched_exp.add(e_i)
                    matched_det.add(d_i)
                    etype = exp["type"]
                    per_type.setdefault(etype, {"tp": 0, "fp": 0, "fn": 0})
                    per_type[etype]["tp"] += 1
                    tp_all += 1
                    break

        for d_i, det in enumerate(found):
            if d_i not in matched_det:
                etype = det.category
                per_type.setdefault(etype, {"tp": 0, "fp": 0, "fn": 0})
                per_type[etype]["fp"] += 1
                fp_all += 1
                fp_list.append({
                    "text": det.text,
                    "type": det.category,
                    "score": det.confidence,
                    "context": text[max(0, det.start - 20):det.end + 20],
                })

        for e_i, exp in enumerate(expected):
            if e_i not in matched_exp:
                etype = exp["type"]
                per_type.setdefault(etype, {"tp": 0, "fp": 0, "fn": 0})
                per_type[etype]["fn"] += 1
                fn_all += 1
                fn_list.append({
                    "text": exp["text"],
                    "type": exp["type"],
                    "context": text[max(0, exp["start"] - 20):exp["end"] + 20],
                })

    return {
        "aggregate": _metrics(tp_all, fp_all, fn_all),
        "per_type": {k: _metrics(v["tp"], v["fp"], v["fn"])
                     for k, v in per_type.items()},
        "false_positives": fp_list,
        "false_negatives": fn_list,
    }


def _metrics(tp: int, fp: int, fn: int) -> dict:
    p = tp / (tp + fp) if (tp + fp) else 0.0
    r = tp / (tp + fn) if (tp + fn) else 0.0
    f = 2 * p * r / (p + r) if (p + r) else 0.0
    return {
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn,
        "precision": round(p, 4),
        "recall": round(r, 4),
        "f1_score": round(f, 4),
    }


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def format_report(results: dict, glossary_count: int = 0) -> str:
    """Produce a Markdown evaluation report."""
    lines = ["# Evaluation Report\n"]

    lines.append("## Methodology\n")
    lines.append("- Ground truth: manually annotated paragraph samples")
    lines.append("- Span-overlap matching (≥50% overlap = true positive)")
    lines.append("- Computed per-type and aggregate metrics\n")

    agg = results["aggregate"]
    lines.append("## Aggregate Results\n")
    lines.append("| Metric | Value |")
    lines.append("|---|---|")
    for key in ("precision", "recall", "f1_score",
                "true_positives", "false_positives", "false_negatives"):
        lines.append(f"| {key.replace('_', ' ').title()} | {agg[key]} |")
    lines.append("")

    lines.append("## Per-Type Results\n")
    lines.append("| Entity Type | Precision | Recall | F1 | TP | FP | FN |")
    lines.append("|---|---|---|---|---|---|---|")
    for etype, m in sorted(results["per_type"].items()):
        lines.append(
            f"| {etype} | {m['precision']:.4f} | {m['recall']:.4f} | "
            f"{m['f1_score']:.4f} | {m['true_positives']} | "
            f"{m['false_positives']} | {m['false_negatives']} |"
        )
    lines.append("")

    if results["false_positives"]:
        lines.append("## Notable False Positives\n")
        for fp in results["false_positives"][:15]:
            lines.append(
                f"- **{fp['type']}**: \"{fp['text']}\" "
                f"(score={fp['score']:.2f}) — context: "
                f"\"...{fp['context']}...\""
            )
        lines.append("")

    if results["false_negatives"]:
        lines.append("## Notable False Negatives\n")
        for fn in results["false_negatives"][:15]:
            lines.append(
                f"- **{fn['type']}**: \"{fn['text']}\" — context: "
                f"\"...{fn['context']}...\""
            )
        lines.append("")

    lines.append("## Known Limitations\n")
    lines.append("- Indian names may show lower recall due to spaCy's Western-biased training data")
    lines.append("- Short company abbreviations (e.g. \"KSH\") lack NER context")
    lines.append("- Indian address formats with village/taluka references are the hardest category")
    lines.append("- DATE_TIME: context-gated to DOB keywords only; financial dates are left intact")
    lines.append(f"- Glossary auto-parser extracted {glossary_count} terms for deny-list")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="Evaluate PII detection accuracy.")
    ap.add_argument("--ground-truth", "-g", default=GROUND_TRUTH)
    ap.add_argument("--output", "-o", default="evaluation_report.md")
    args = ap.parse_args()

    print("Loading annotations...")
    annotations = load_annotations(args.ground_truth)
    print(f"  {len(annotations)} samples loaded")

    print("Parsing document glossary...")
    try:
        glossary = extract_glossary_from_path(SOURCE_DOC)
        print(f"  {len(glossary)} terms extracted")
    except Exception as e:
        print(f"  Glossary unavailable: {e}")
        glossary = None

    print("Building scanner...")
    analyzer = build_analyzer()

    print("Running evaluation...")
    results = run_evaluation(annotations, analyzer, deny_supplement=glossary)

    agg = results["aggregate"]
    print(f"\n--- Results ---")
    print(f"  Precision: {agg['precision']:.4f}")
    print(f"  Recall:    {agg['recall']:.4f}")
    print(f"  F1 Score:  {agg['f1_score']:.4f}")

    report = format_report(results, glossary_count=len(glossary or set()))
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\nReport → {args.output}")

    raw = args.output.replace(".md", "_raw.json")
    with open(raw, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"Raw JSON → {raw}")


if __name__ == "__main__":
    main()
