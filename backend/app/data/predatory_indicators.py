"""
Predatory / delisted journal and publisher indicators.

Curated patterns based on Beall's list criteria, UGC-CARE delisted indicators,
and common predatory journal characteristics.

These are used by the ResearchIntegrityAgent to flag suspicious publications.
"""

# Known predatory publishers — substring or fuzzy matches on publisher/journal name
PREDATORY_PUBLISHER_PATTERNS = [
    "omics international",
    "omics group",
    "sciencedomain",
    "science domain",
    "waset",
    "world academy of science, engineering and technology",
    "academic journals inc",
    "david publishing",
    "hikari ltd",
    "iosr journals",
    "iiste",
    "international institute for science, technology and education",
    "science and education publishing",
    "sciencepublishinggroup",
    "science publishing group",
    "savvy science publisher",
    "lap lambert",
    "medcrave",
    "scitechnol",
    "longdom publishing",
    "pulsus group",
    "insight medical publishing",
    "allied academies",
    "annex publishers",
    "auctores publishing",
    "biomedres",
    "crimson publishers",
    "gavin publishers",
    "imedpub",
    "iris publishers",
    "juniper publishers",
    "lupine publishers",
    "meddocs publishers",
    "medwin publishers",
    "open access text",
    "peertechz",
    "remedy publications",
    "sciforschenonline",
    "scientific literature",
    "sryahwa publications",
    "symbiosis online publishing",
    "whioce publishing",
]

# Suspicious journal name patterns — keywords commonly found in predatory journals
PREDATORY_JOURNAL_NAME_KEYWORDS = [
    "american journal of",  # combined with suspicious publishers
    "international journal of innovative",
    "international journal of advanced",
    "international journal of recent",
    "international journal of modern",
    "international journal of emerging",
    "global journal of",
    "universal journal of",
    "world journal of",
    "european journal of",  # when not from legitimate EU publishers
    "asian journal of",
    "african journal of",
]

# Suspicious email domains (common in predatory journal solicitations)
PREDATORY_EMAIL_DOMAINS = [
    "@openaccesspub.org",
    "@scitechnol.com",
    "@omicsonline.org",
    "@longdom.org",
    "@pulsus.com",
    "@imedpub.com",
]

# Rapid publication threshold: submissions accepted in fewer than this many days
# are flagged as suspicious
RAPID_PUBLICATION_THRESHOLD_DAYS = 14

# Minimum reasonable peer review period (days)
MIN_PEER_REVIEW_DAYS = 30

# UGC-CARE delisted journal patterns (common Indian context)
UGC_CARE_DELISTED_PATTERNS = [
    "international journal of engineering research and technology",
    "international journal of engineering and technology",
    "international journal of pure and applied mathematics",
    "international journal of pharmacy and pharmaceutical sciences",
    "international journal of pharma and bio sciences",
    "international journal of research in engineering and technology",
    "international research journal of engineering and technology",
    "international journal of science and research",
    "international journal of engineering research and applications",
    "international journal of computer science and information technologies",
]


def check_predatory_indicators(journal_name: str = "", publisher: str = "") -> dict:
    """
    Check a publication's journal/publisher against known predatory indicators.
    
    Returns:
        dict with keys:
            - is_suspicious: bool
            - reasons: list of strings explaining flags
            - risk_category: 'predatory_publisher' | 'suspicious_journal' | 'ugc_delisted' | None
    """
    reasons = []
    risk_category = None
    journal_lower = (journal_name or "").lower().strip()
    publisher_lower = (publisher or "").lower().strip()

    # Check predatory publishers
    for pattern in PREDATORY_PUBLISHER_PATTERNS:
        if pattern in publisher_lower:
            reasons.append(f"Publisher '{publisher}' matches known predatory publisher pattern: '{pattern}'")
            risk_category = "predatory_publisher"
            break

    # Check UGC-CARE delisted journals
    if not risk_category:
        for pattern in UGC_CARE_DELISTED_PATTERNS:
            if pattern in journal_lower:
                reasons.append(f"Journal '{journal_name}' matches UGC-CARE delisted journal pattern")
                risk_category = "ugc_delisted"
                break

    # Check suspicious journal name patterns (only if publisher is also unknown/suspicious)
    if not risk_category and journal_lower:
        suspicious_keyword_count = sum(1 for kw in PREDATORY_JOURNAL_NAME_KEYWORDS if kw in journal_lower)
        if suspicious_keyword_count >= 2:
            reasons.append(f"Journal name '{journal_name}' contains multiple suspicious keyword patterns")
            risk_category = "suspicious_journal"

    return {
        "is_suspicious": len(reasons) > 0,
        "reasons": reasons,
        "risk_category": risk_category,
    }
