"""
PII Redaction Tool — orchestration pipeline.

Loads a .docx, runs entity detection, masks every PII instance with
opaque black bars (█████), and saves the redacted output.

Usage:
    python pipeline.py
    python pipeline.py --input "path/to/doc.docx" --output "path/to/out.docx"
"""

import argparse
import time
from typing import Callable, Optional

from docx import Document

from settings import SOURCE_DOC, REDACTED_DOC, MAPPING_FILE
from docx_processor import (
    gather_segments, inject_replacements, apply_blackout_style,
    persist_document,
)
from scanner import build_analyzer, scan_for_sensitive_data
from redactor import RedactionMapper
from glossary_extractor import extract_glossary_terms


# ---------------------------------------------------------------------------
# Core pipeline (used by both CLI and the web API)
# ---------------------------------------------------------------------------

def run_redaction(
    input_path: str,
    output_path: str,
    mapping_path: Optional[str] = None,
    on_progress: Optional[Callable] = None,
) -> dict:
    """
    End-to-end redaction: Load → Parse glossary → Detect → Mask → Save.

    Returns a dict with processing statistics.
    """
    def _tick(frac, msg=""):
        if on_progress:
            on_progress(frac, msg)

    _tick(0.0, "Loading document...")
    doc = Document(input_path)

    _tick(0.05, "Extracting glossary terms...")
    glossary = extract_glossary_terms(doc)

    _tick(0.10, "Splitting document into segments...")
    segments = gather_segments(doc)

    _tick(0.15, "Initializing NLP scanner...")
    analyzer = build_analyzer()
    mapper = RedactionMapper()

    n = len(segments)
    total_hits = 0

    for i, seg in enumerate(segments):
        pct = 0.20 + 0.70 * (i / n)
        if (i + 1) % 100 == 0 or i == n - 1:
            _tick(pct, f"Scanning segment {i + 1}/{n}...")

        hits = scan_for_sensitive_data(
            analyzer, seg.content,
            supplementary_deny=glossary if glossary else None,
        )
        if not hits:
            continue

        edits = []
        for h in hits:
            masked = mapper.mask(h.text, h.category)
            edits.append((h.start, h.end, masked))

        inject_replacements(seg, edits)
        apply_blackout_style(seg)
        total_hits += len(hits)

    _tick(0.92, "Saving redacted document...")
    persist_document(doc, output_path)

    out_map = mapping_path or MAPPING_FILE
    mapper.export(out_map)

    _tick(1.0, "Done!")

    stats = mapper.summary()
    return {
        "total_entities": total_hits,
        "unique_entities": stats["total_unique_entities"],
        "by_type": stats["by_type"],
        "definitions_count": len(glossary) if glossary else 0,
        "segments_count": n,
        "entity_map_path": out_map,
    }


# ---------------------------------------------------------------------------
# Command-line interface
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(
        description="PII Redaction Tool — mask PII with opaque black bars.",
    )
    ap.add_argument("--input",  "-i", default=SOURCE_DOC,
                    help="Input .docx file path")
    ap.add_argument("--output", "-o", default=REDACTED_DOC,
                    help="Output redacted .docx file path")
    args = ap.parse_args()

    t0 = time.time()

    def log_progress(frac, msg):
        if msg:
            print(f"  [{frac*100:5.1f}%%] {msg}")

    result = run_redaction(
        args.input, args.output,
        on_progress=log_progress,
    )
    elapsed = time.time() - t0

    print(f"\n--- Redaction Summary ---")
    print(f"Entities masked:  {result['total_entities']}")
    print(f"Unique entities:  {result['unique_entities']}")
    for etype, cnt in sorted(result["by_type"].items()):
        print(f"  {etype}: {cnt}")
    print(f"Entity map:       {result['entity_map_path']}")
    print(f"\nFinished in {elapsed:.1f}s")


if __name__ == "__main__":
    main()
