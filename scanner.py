"""
PII Scanner — entity detection engine.

Wraps Microsoft Presidio's AnalyzerEngine with:
  - spaCy NER backend for names, orgs, and locations
  - Four custom regex recognizers for Indian phone numbers,
    URLs, CIN codes, and "Contact Person:" patterns
  - Multi-stage post-processing: deny-list filtering,
    DOB context gating, overlap resolution, address merging
"""

import logging
import re
from dataclasses import dataclass
from typing import List, Optional, Set

from presidio_analyzer import (
    AnalyzerEngine,
    PatternRecognizer,
    Pattern,
    RecognizerRegistry,
)
from presidio_analyzer.nlp_engine import NlpEngineProvider

from settings import (
    NLP_MODEL,
    SCORE_THRESHOLDS,
    IGNORED_TYPES,
    SUPPRESSED_TERMS,
    FOOTNOTE_SYMBOLS,
    GEO_CURRENCY_NAMES,
    DATE_CONTEXT_KEYWORDS,
    ADDRESS_KEYWORDS,
)

# Silence tldextract warnings in sandboxed environments
logging.getLogger("tldextract").setLevel(logging.CRITICAL)
try:
    import tldextract
    tldextract.TLDExtract(suffix_list_urls=None)
except Exception:
    pass


# ---------------------------------------------------------------------------
# Detected entity representation
# ---------------------------------------------------------------------------

@dataclass
class SensitiveEntity:
    """A single PII entity found in a block of text."""
    category: str       # e.g. "PERSON", "EMAIL_ADDRESS"
    start: int          # character offset — start
    end: int            # character offset — end
    text: str           # surface form
    confidence: float   # 0-1


# ---------------------------------------------------------------------------
# Custom pattern recognizers
# ---------------------------------------------------------------------------

class IndianTelephoneRecognizer(PatternRecognizer):
    """
    Catches Indian telephone formats Presidio may miss:
      - Landlines: 022-68052182, 020 45053237
      - Mobile with country code: +91 81081 14949
      - Spaced international: + 91 20 4505 3237
    """
    PATTERNS = [
        Pattern("LANDLINE_IN", r"\b0\d{2,4}[-\s]?\d{6,8}\b", 0.7),
        Pattern("MOBILE_IN",   r"\b\+?91[\s-]?\d{4,5}[\s-]?\d{4,6}\b", 0.75),
        Pattern("SPACED_IN",   r"\b\+\s?91\s\d{2}\s\d{4}\s\d{3,4}\b", 0.75),
    ]
    CONTEXT = ["telephone", "phone", "mobile", "contact", "tel", "fax"]

    def __init__(self):
        super().__init__(
            supported_entity="PHONE_NUMBER",
            patterns=self.PATTERNS,
            context=self.CONTEXT,
            supported_language="en",
            name="IndianTelephoneRecognizer",
        )


class WebAddressRecognizer(PatternRecognizer):
    """Recognizes website URLs starting with www. or http(s)://."""
    PATTERNS = [
        Pattern("WWW_URL",   r"\bwww\.[a-zA-Z0-9-]+\.[a-zA-Z.]+(?:/[^\s)]*)?", 0.85),
        Pattern("HTTP_URL",  r"\bhttps?://[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(?:/[^\s)]*)?", 0.9),
    ]

    def __init__(self):
        super().__init__(
            supported_entity="URL",
            patterns=self.PATTERNS,
            context=["website", "web", "site", "url"],
            supported_language="en",
            name="WebAddressRecognizer",
        )


class CorporateIdRecognizer(PatternRecognizer):
    """
    Identifies Indian Corporate Identity Numbers (CIN).
    Format: U28129PN1979PLC141032
    """
    PATTERNS = [
        Pattern("CIN_FORMAT", r"\b[A-Z]\d{5}[A-Z]{2}\d{4}[A-Z]{3}\d{6}\b", 0.9),
    ]

    def __init__(self):
        super().__init__(
            supported_entity="IN_CIN",
            patterns=self.PATTERNS,
            context=["CIN", "Corporate Identity Number", "incorporation"],
            supported_language="en",
            name="CorporateIdRecognizer",
        )


class NameAfterLabelRecognizer(PatternRecognizer):
    """
    Extracts names following 'Contact Person:' — a pattern where
    spaCy NER often fails because the prefix confuses boundary detection.
    """
    _RE = re.compile(
        r"Contact\s+[Pp]erson\s*:\s*"
        r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})"
        r"(?=[,\s;]|$)",
    )
    PATTERNS = [
        Pattern("PLACEHOLDER", r"NEVER_MATCH_PLACEHOLDER", 0.0),
    ]

    def __init__(self):
        super().__init__(
            supported_entity="PERSON",
            patterns=self.PATTERNS,
            supported_language="en",
            name="NameAfterLabelRecognizer",
        )

    def analyze(self, text, entities, nlp_artifacts=None, regex_flags=None):
        from presidio_analyzer import RecognizerResult
        hits = []
        for m in self._RE.finditer(text):
            hits.append(RecognizerResult(
                entity_type="PERSON",
                start=m.start(1),
                end=m.end(1),
                score=0.92,
                analysis_explanation=None,
                recognition_metadata={"recognizer_name": self.name},
            ))
        return hits


# ---------------------------------------------------------------------------
# Engine factory
# ---------------------------------------------------------------------------

def build_analyzer() -> AnalyzerEngine:
    """
    Assemble the Presidio AnalyzerEngine with spaCy NLP and all
    custom recognizers registered.
    """
    nlp_config = {
        "nlp_engine_name": "spacy",
        "models": [{"lang_code": "en", "model_name": NLP_MODEL}],
    }
    provider = NlpEngineProvider(nlp_configuration=nlp_config)
    engine = provider.create_engine()

    registry = RecognizerRegistry()
    registry.load_predefined_recognizers(nlp_engine=engine)

    registry.add_recognizer(IndianTelephoneRecognizer())
    registry.add_recognizer(WebAddressRecognizer())
    registry.add_recognizer(CorporateIdRecognizer())
    registry.add_recognizer(NameAfterLabelRecognizer())

    return AnalyzerEngine(nlp_engine=engine, registry=registry)


# ---------------------------------------------------------------------------
# Main detection function
# ---------------------------------------------------------------------------

def scan_for_sensitive_data(
    analyzer: AnalyzerEngine,
    text: str,
    supplementary_deny: Optional[Set[str]] = None,
) -> List[SensitiveEntity]:
    """
    Scan *text* for all PII entities.

    Pipeline:
      1. Run Presidio
      2. Filter by type exclusion + confidence thresholds
      3. Deny-list check (NER types only)
      4. DOB context gating for DATE_TIME
      5. Strip footnote markers
      6. Trim "Contact Person:" prefixes
      7. Suppress standalone country/currency mentions
      8. Resolve overlapping spans
      9. Merge adjacent LOCATION spans into addresses
    """
    if not text or not text.strip():
        return []

    deny_set = SUPPRESSED_TERMS
    if supplementary_deny:
        deny_set = deny_set | supplementary_deny

    raw = analyzer.analyze(text=text, language="en", entities=None)

    entities: List[SensitiveEntity] = []
    for r in raw:
        if r.entity_type in IGNORED_TYPES:
            continue

        min_score = SCORE_THRESHOLDS.get(
            r.entity_type, SCORE_THRESHOLDS["default"]
        )
        if r.score < min_score:
            continue

        surface = text[r.start:r.end]

        # Deny-list filtering for NER-sourced types only
        NER_CATEGORIES = {"PERSON", "ORGANIZATION", "LOCATION"}
        if r.entity_type in NER_CATEGORIES:
            if _matches_deny_list(surface, deny_set):
                continue

        # Context gating for dates
        if r.entity_type == "DATE_TIME":
            if not _context_window_contains(
                text, r.start, r.end, DATE_CONTEXT_KEYWORDS, window=80
            ):
                continue

        entities.append(SensitiveEntity(
            category=r.entity_type,
            start=r.start,
            end=r.end,
            text=surface,
            confidence=r.score,
        ))

    entities = _clean_footnote_edges(entities, text)
    entities = _remove_contact_label(entities, text)
    entities = _suppress_geo_mentions(entities, text)
    entities = _deduplicate_overlaps(entities)
    entities = _combine_adjacent_locations(entities, text)

    return entities


# ---------------------------------------------------------------------------
# Post-processing helpers
# ---------------------------------------------------------------------------

def _matches_deny_list(surface: str, deny_set: Set[str]) -> bool:
    """Check if surface text matches any deny-list entry."""
    normalized = surface.strip().lower()
    if normalized in deny_set:
        return True
    # For short terms (≤3 chars), require exact match only
    for term in deny_set:
        if len(term) <= 3:
            if normalized == term:
                return True
        else:
            if term in normalized or normalized in term:
                return True
    return False


def _context_window_contains(
    text: str, start: int, end: int,
    keywords: list, window: int = 80
) -> bool:
    """Check whether any keyword appears within ±window chars of the span."""
    left = max(0, start - window)
    right = min(len(text), end + window)
    context = text[left:right].lower()
    return any(kw in context for kw in keywords)


def _clean_footnote_edges(
    entities: List[SensitiveEntity], text: str
) -> List[SensitiveEntity]:
    """Strip footnote markers (*, ^, &, etc.) from entity boundaries."""
    cleaned = []
    for e in entities:
        s, end = e.start, e.end
        while end > s and text[end - 1] in FOOTNOTE_SYMBOLS:
            end -= 1
        while s < end and text[s] in FOOTNOTE_SYMBOLS:
            s += 1
        if s < end:
            cleaned.append(SensitiveEntity(
                category=e.category,
                start=s,
                end=end,
                text=text[s:end],
                confidence=e.confidence,
            ))
    return cleaned


def _remove_contact_label(
    entities: List[SensitiveEntity], text: str
) -> List[SensitiveEntity]:
    """Trim 'Contact Person:' prefix from PERSON entities if Presidio included it."""
    prefix_re = re.compile(r"Contact\s+[Pp]erson\s*:\s*", re.IGNORECASE)
    result = []
    for e in entities:
        if e.category == "PERSON":
            m = prefix_re.match(e.text)
            if m:
                new_start = e.start + m.end()
                new_text = text[new_start:e.end].strip()
                if new_text:
                    result.append(SensitiveEntity(
                        category="PERSON",
                        start=new_start,
                        end=e.end,
                        text=new_text,
                        confidence=e.confidence,
                    ))
                    continue
        result.append(e)
    return result


def _suppress_geo_mentions(
    entities: List[SensitiveEntity], text: str
) -> List[SensitiveEntity]:
    """
    Remove standalone country / currency name mentions from LOCATION results
    unless preceded by address context words.
    """
    kept = []
    for e in entities:
        if e.category == "LOCATION":
            normalized = e.text.strip().lower()
            tokens = normalized.split()
            if len(tokens) <= 3 and normalized in GEO_CURRENCY_NAMES:
                if not _context_window_contains(
                    text, e.start, e.end, ADDRESS_KEYWORDS, window=120
                ):
                    continue
        kept.append(e)
    return kept


def _deduplicate_overlaps(
    entities: List[SensitiveEntity],
) -> List[SensitiveEntity]:
    """When spans overlap, keep the one with the highest confidence score."""
    if not entities:
        return []
    sorted_ents = sorted(entities, key=lambda e: e.start)
    result = [sorted_ents[0]]
    for current in sorted_ents[1:]:
        prev = result[-1]
        if current.start < prev.end:
            if current.confidence > prev.confidence:
                result[-1] = current
        else:
            result.append(current)
    return result


def _combine_adjacent_locations(
    entities: List[SensitiveEntity], text: str, gap: int = 5
) -> List[SensitiveEntity]:
    """
    Merge LOCATION entities that are separated by ≤ *gap* characters
    of punctuation / whitespace into a single address span.
    """
    if not entities:
        return []
    sorted_ents = sorted(entities, key=lambda e: e.start)
    merged: List[SensitiveEntity] = []
    for e in sorted_ents:
        if (merged
                and merged[-1].category == "LOCATION"
                and e.category == "LOCATION"
                and e.start - merged[-1].end <= gap):
            between = text[merged[-1].end:e.start]
            if all(c in " ,;.\n\t-–—/" for c in between):
                combined = SensitiveEntity(
                    category="LOCATION",
                    start=merged[-1].start,
                    end=e.end,
                    text=text[merged[-1].start:e.end],
                    confidence=max(merged[-1].confidence, e.confidence),
                )
                merged[-1] = combined
                continue
        merged.append(e)
    return merged
