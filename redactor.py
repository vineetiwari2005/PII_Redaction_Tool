"""
Blackout Redactor — replaces PII with opaque █ bars.

Maintains a record of every entity it has masked so that
downstream tools (API, evaluator) can report statistics
and export the entity map.
"""

import json
import os
from typing import Dict


class RedactionMapper:
    """
    Maps detected PII to solid black-bar characters (█████).

    Every unique entity is recorded once. Repeated occurrences
    receive the same bar-length replacement for visual consistency.
    """

    def __init__(self, fill_char: str = "█"):
        self._fill = fill_char
        self._registry: Dict[str, Dict] = {}

    def mask(self, original: str, entity_type: str) -> str:
        """Return a bar string matching the original's length (min 3)."""
        key = original.strip().lower()
        bar = self._fill * max(len(original.strip()), 3)

        if key not in self._registry:
            self._registry[key] = {
                "type": entity_type,
                "original": original.strip(),
                "replacement": "[REDACTED]",
            }
        return bar

    def export(self, filepath: str) -> None:
        """Write the entity registry to a JSON file."""
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as fh:
            json.dump(self._registry, fh, indent=2, ensure_ascii=False)

    def summary(self) -> dict:
        """Return aggregate counts grouped by entity type."""
        counts: Dict[str, int] = {}
        for entry in self._registry.values():
            t = entry["type"]
            counts[t] = counts.get(t, 0) + 1
        return {
            "total_unique_entities": len(self._registry),
            "by_type": counts,
        }
