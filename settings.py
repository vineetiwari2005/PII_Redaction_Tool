"""
Centralized settings for the PII Redaction Tool.
All tunable values live here — no magic numbers in the logic modules.
"""

import os

import pycountry

# ---------------------------------------------------------------------------
# Directory and File Paths
# ---------------------------------------------------------------------------

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
SOURCE_DOC = os.path.join(ROOT_DIR, "..", "Red Herring Prospectus.docx")
RESULTS_DIR = os.path.join(ROOT_DIR, "output")
REDACTED_DOC = os.path.join(RESULTS_DIR, "Red Herring Prospectus_redacted.docx")
GROUND_TRUTH = os.path.join(ROOT_DIR, "ground_truth_sample.json")
MAPPING_FILE = os.path.join(RESULTS_DIR, "entity_map.json")

# ---------------------------------------------------------------------------
# NLP Model
# ---------------------------------------------------------------------------

NLP_MODEL = os.environ.get("SPACY_MODEL", "en_core_web_lg")

# ---------------------------------------------------------------------------
# Supported Entity Categories
# ---------------------------------------------------------------------------

ENTITY_TYPES = [
    "PERSON",
    "EMAIL_ADDRESS",
    "PHONE_NUMBER",
    "ORGANIZATION",
    "LOCATION",
    "URL",
    "IN_CIN",
    "CREDIT_CARD",
    "US_SSN",
    "IP_ADDRESS",
    "DATE_TIME",
]

# ---------------------------------------------------------------------------
# Ignored Entity Types
# ---------------------------------------------------------------------------
# Presidio may return these, but they carry no PII relevance here.
# DATE_TIME is handled via context gating instead of blanket exclusion.

IGNORED_TYPES = {
    "NRP",
    "MEDICAL_LICENSE",
    "US_BANK_NUMBER",
    "US_DRIVER_LICENSE",
    "US_ITIN",
    "US_PASSPORT",
    "UK_NHS",
    "AU_ABN",
    "AU_ACN",
    "AU_TFN",
    "AU_MEDICARE",
    "SG_NRIC_FIN",
    "IBAN_CODE",
}

# ---------------------------------------------------------------------------
# Footnote Markers
# ---------------------------------------------------------------------------
# Superscript characters commonly appended to names in table rows.
# Cleaned from entity boundaries before mapping to ensure consistency.

FOOTNOTE_SYMBOLS = frozenset("*^&†‡§#")

# ---------------------------------------------------------------------------
# Terms to Never Redact (Static Deny List)
# ---------------------------------------------------------------------------

SUPPRESSED_TERMS = {
    # Document identifiers
    "red herring", "red herring prospectus", "prospectus",
    "draft red herring prospectus", "drhp",

    # Regulatory bodies / acronyms
    "scra", "scrr", "sebi", "rbi", "roc", "mca",
    "goi", "gaap", "ind as", "ifrs",

    # Structural headings
    "section", "chapter", "annexure", "schedule",

    # Role labels incorrectly tagged as PERSON
    "email", "e-mail", "cfo", "ceo", "cs", "cmd", "coo", "cto",
    "company secretary", "compliance officer",

    # Capital market abbreviations
    "asba", "asba account", "ebitda", "adjusted ebitda",
    "brlm", "book running lead manager",
    "bse", "nse", "isin", "ipo",
    "roe", "roce", "pat", "cagr", "eps", "nav", "npa",
    "equity shares", "allotted equity shares",
    "alternate investment fund", "audit committee",
    "5th floor",

    # Technical / product jargon
    "continuous transposed conductors",

    # Place names or brand names falsely tagged as PERSON
    "lok sabha", "the lok sabha", "rajya sabha", "the rajya sabha",
    "tanishq showroom", "tanishq",
    "corrigenda", "challan", "fiscals", "fiscal",
    "showroom", "website",

    # Individual place names commonly mis-classified
    "ahmednagar", "ahilyanagar", "erandawane", "vikhroli",
    "kanjurmarg", "prabhadevi", "taloja", "kilovolt",
    "bhonde", "birdewadi", "khalumbre",

    # Multi-word place / building references
    "lower parel", "shivaji nagar", "deen dayal",
    "appasaheb marathe marg", "chakan taluka",
    "taluka parner", "taluka-khed", "chakan taluka-khed",
    "chakan taluka - khed",
    "gopal house", "gopalkrupa apartment", "pushpakamal apartment",
    "tara chambers", "supa parner industrial park",
    "mauje palve khurd", "gopal bo", "birdewadi chakan",
    "supa ahilyanagar",

    # Manufacturing terms
    "urja suraksha", "grill",
}

# ---------------------------------------------------------------------------
# Country and Currency Names (auto-generated via pycountry)
# ---------------------------------------------------------------------------

def _compile_geo_currency_set():
    """
    Build a comprehensive set of country names, ISO codes, and currency
    names/codes using pycountry. Covers ~250 countries and ~170 currencies.
    """
    terms = set()
    for country in pycountry.countries:
        terms.add(country.name.lower())
        terms.add(country.alpha_2.lower())
        terms.add(country.alpha_3.lower())
        if hasattr(country, "common_name"):
            terms.add(country.common_name.lower())
        if hasattr(country, "official_name"):
            terms.add(country.official_name.lower())

    for currency in pycountry.currencies:
        terms.add(currency.alpha_3.lower())
        terms.add(currency.name.lower())

    # Informal names not covered by ISO
    extras = {
        "uae", "uk", "usa", "s. korea", "n. korea",
        "vatican", "congo", "ivory coast", "czech republic",
        "holland", "burma", "persia", "ceylon",
        "the united states", "the united kingdom",
        "the republic of india",
    }
    terms.update(extras)
    return terms

GEO_CURRENCY_NAMES = _compile_geo_currency_set()

# ---------------------------------------------------------------------------
# Per-Type Confidence Thresholds
# ---------------------------------------------------------------------------

SCORE_THRESHOLDS = {
    "default":       0.7,
    "PERSON":        0.7,
    "ORGANIZATION":  0.7,
    "LOCATION":      0.7,
    "EMAIL_ADDRESS":  0.5,
    "PHONE_NUMBER":  0.6,
    "URL":           0.6,
    "IN_CIN":        0.7,
    "DATE_TIME":     0.85,
    "CREDIT_CARD":   0.7,
    "US_SSN":        0.4,
    "IP_ADDRESS":    0.5,
}

# ---------------------------------------------------------------------------
# Context Keywords (for gated entity types)
# ---------------------------------------------------------------------------

DATE_CONTEXT_KEYWORDS = [
    "date of birth", "dob", "born on", "born", "birthday",
    "birth date", "birthdate", "d.o.b", "d.o.b.",
]

ADDRESS_KEYWORDS = [
    "registered office", "corporate office", "address",
    "office at", "situated at", "located at", "premises at",
    "gat no", "village", "taluka", "survey no",
]
