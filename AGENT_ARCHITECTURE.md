# Agent Architecture — Faculty Research Publication Monitoring System

> **Version**: 0.1 (Phase 0)
> **Date**: 2026-09-11

---

## 1. Agent Orchestration Framework

### 1.1 Why LangGraph

LangGraph provides:
- **Explicit state machines** — each agent step is a node with defined transitions
- **Conditional routing** — branch based on confidence scores, data completeness
- **Human-in-the-loop** — pause execution for review, resume after decision
- **Persistent state** — checkpoint agent progress, resume on failure
- **Observability** — every step logged with input/output/timing

### 1.2 Design Principles

1. **LLM only where reasoning is needed** — DOI comparison, database writes, arithmetic use deterministic tools
2. **Every agent produces a typed output** — Pydantic models, never unstructured text
3. **Confidence scoring everywhere** — 0.0 to 1.0, thresholds trigger human review
4. **Provenance is mandatory** — every fact carries its source, timestamp, confidence
5. **Agents never fabricate data** — if information is unavailable, record "unknown"
6. **Human decisions are final** — agents never silently override human review outcomes

### 1.3 Orchestration Architecture

```
                         ┌──────────────────────┐
                         │  ORCHESTRATOR GRAPH   │
                         │  (LangGraph StateGraph│
                         └──────────┬───────────┘
                                    │
          ┌─────────────────────────┼─────────────────────────┐
          │                         │                         │
    ┌─────▼──────┐          ┌──────▼───────┐          ┌──────▼───────┐
    │ DISCOVERY   │          │ ENRICHMENT   │          │ MONITORING   │
    │ PIPELINE    │          │ PIPELINE     │          │ PIPELINE     │
    └─────┬──────┘          └──────┬───────┘          └──────┬───────┘
          │                        │                         │
    ┌─────┼─────┐            ┌─────┼─────┐            ┌─────┼─────┐
    │     │     │            │     │     │            │     │     │
   A1    A2    A3           A7    A8    A9           A10   A11   A12
   A4    A5    A6                                         A13
```

---

## 2. Agent Specifications

### Agent 1 — Faculty Identity Agent

**Responsibility**: Maintain the authoritative faculty identity register.

| Attribute | Detail |
|-----------|--------|
| **Trigger** | CSV import, admin updates, identifier discovery |
| **Inputs** | Raw faculty CSV data, discovered external identifiers |
| **Outputs** | `FacultyProfile` with normalized fields and external IDs |
| **LLM Usage** | Name variant generation (e.g., "M. Umadevi" → "Maramreddy Umadevi") |
| **Deterministic** | ID storage, email validation, duplicate name detection |
| **Confidence** | N/A (authoritative source) |

**Fields Managed**:
```
faculty_id          UUID (system-generated)
full_name           "Dr M Umadevi" (as-is from source)
normalized_name     "maramreddy umadevi" (lowercase, no titles, no initials)
first_name          "Maramreddy"
last_name           "Umadevi"
title_prefix        "Dr"
department          "CSE"
designation         "ASSOCIATE PROFESSOR"
email               "druma_cse@vignan.ac.in"
phone               "+91-..."
orcid               null (to be discovered)
openalex_id         null (to be discovered)
semantic_scholar_id null (to be discovered)
scopus_author_id    null (optional)
wos_researcher_id   null (optional)
google_scholar_url  null (to be discovered)
name_variants       ["M Umadevi", "Maramreddy Umadevi", "M. Umadevi", "Umadevi M"]
research_interests  ["Document forensics", "Image Processing", ...]
education           [structured education records]
status              ACTIVE
```

**Key Logic**:
- Parse names from CSV, handling inconsistent casing (e.g., "Dr MD OQAIL AHMAD" vs "Dr M Umadevi")
- Generate name variants using pattern rules + LLM assistance
- Match discovered identifiers (ORCID, OpenAlex) to faculty using name + affiliation evidence
- Never auto-assign identifiers with confidence < 0.85 — send to review

---

### Agent 2 — Affiliation Intelligence Agent

**Responsibility**: Learn and maintain all variants of institutional affiliation strings.

| Attribute | Detail |
|-----------|--------|
| **Trigger** | Publication discovery, admin input, initial seeding |
| **Inputs** | Affiliation strings from publications, known variants |
| **Outputs** | `AffiliationVariant` records with match confidence |
| **LLM Usage** | Classify whether a novel affiliation string refers to VFSTR |
| **Deterministic** | String similarity, known-variant lookup |

**Known VFSTR Affiliation Variants** (initial seed):
```
"Vignan's Foundation for Science, Technology & Research"
"Vignan's Foundation for Science Technology and Research"
"VFSTR"
"Vignan University"
"Vignan's University"
"Vignans Foundation"
"Vignan Engineering College"
"Vignan's Engineering College"
"Vignan Institute of Technology and Science"
"Vignan, Guntur"
"Vignan, Vadlamudi"
```

**Key Logic**:
- Maintain a growing dictionary of confirmed affiliation variants
- Fuzzy match new affiliation strings against known variants (Levenshtein, token-set ratio)
- LLM classifies edge cases (e.g., "Dept. of CSE, VFSTR, Guntur, AP, India")
- Separate department-level variants (e.g., "Department of Computer Science and Engineering, VFSTR")
- Flag publications with unexpected/incorrect affiliations

---

### Agent 3 — Publication Discovery Agent

**Responsibility**: Search configured research sources and discover new publications.

| Attribute | Detail |
|-----------|--------|
| **Trigger** | Scheduled sync, manual trigger |
| **Inputs** | Faculty identifiers, name variants, affiliation variants |
| **Outputs** | `RawDiscoveredPublication` records with source metadata |
| **LLM Usage** | None — purely API-driven |
| **Deterministic** | API calls, response parsing, deduplication against existing records |

**Discovery Strategy per Source**:

```
OpenAlex:
  ├── Search by author OpenAlex ID (if known)
  ├── Search by ORCID (if known)
  ├── Search by author name + affiliation filter
  └── Record: works, citations, concepts, open_access status

Crossref:
  ├── Search by ORCID (if known)
  ├── Search by author name + affiliation
  ├── Verify DOIs discovered from other sources
  └── Record: DOI, title, container-title, publisher, type, dates

Semantic Scholar:
  ├── Search by Semantic Scholar author ID (if known)
  ├── Search by paper title (for verification)
  └── Record: paperId, title, authors, citations, fieldsOfStudy

ORCID:
  ├── Search by faculty email or name
  ├── Retrieve works list from ORCID profile
  └── Record: put-codes, external-ids, titles
```

**Output per discovered record**:
```json
{
  "source": "openalex",
  "source_id": "W4389012345",
  "raw_title": "...",
  "raw_authors": [...],
  "raw_doi": "10.1016/...",
  "raw_affiliation": "...",
  "raw_year": 2025,
  "raw_metadata": { /* full API response */ },
  "discovered_at": "2026-09-11T14:30:00Z",
  "discovery_method": "author_id_search",
  "faculty_hint_id": "uuid-of-faculty"
}
```

---

### Agent 4 — Metadata Normalization Agent

**Responsibility**: Standardize all discovered publication metadata into canonical form.

| Attribute | Detail |
|-----------|--------|
| **Trigger** | After discovery, before deduplication |
| **Inputs** | `RawDiscoveredPublication` |
| **Outputs** | `NormalizedPublication` |
| **LLM Usage** | Parse unstructured publication strings from CSV (title/journal/year extraction) |
| **Deterministic** | DOI normalization, date parsing, title cleaning |

**Normalization Rules**:
```
Title:
  - Remove leading/trailing whitespace
  - Collapse multiple spaces
  - Normalize Unicode (NFC)
  - Generate normalized_title (lowercase, no punctuation, for matching)

DOI:
  - Extract from URLs (https://doi.org/10.xxxx → 10.xxxx)
  - Normalize to lowercase
  - Validate format (10.XXXX/YYYY)

Authors:
  - Parse "LastName, FirstName" and "FirstName LastName" formats
  - Handle et al., & vs and
  - Normalize Unicode names

Dates:
  - Parse various formats: "2025", "2025 May", "May 2025", "2025-05-01"
  - Store as structured: year (int), month (int, nullable), day (int, nullable)

Publication Type:
  - Classify: journal-article, conference-paper, book-chapter, preprint, thesis, other
```

---

### Agent 5 — Publication Deduplication & Entity Resolution Agent

**Responsibility**: Identify duplicate publications across sources and merge safely.

| Attribute | Detail |
|-----------|--------|
| **Trigger** | After normalization |
| **Inputs** | `NormalizedPublication` + existing publication database |
| **Outputs** | Merge decisions with confidence scores |
| **LLM Usage** | Ambiguous title comparison (when titles are similar but not identical) |
| **Deterministic** | DOI exact match, title similarity (Jaccard/cosine), author overlap |

**Matching Hierarchy**:
```
Priority 1: DOI Match
  └── Same DOI → DEFINITE MATCH (confidence = 1.0)

Priority 2: Title Similarity + Author Overlap
  ├── normalized_title similarity ≥ 0.95 AND ≥ 1 author match → HIGH (0.95)
  ├── normalized_title similarity ≥ 0.85 AND ≥ 2 author match → MEDIUM (0.85)
  └── normalized_title similarity ≥ 0.80 → UNCERTAIN → REVIEW QUEUE

Priority 3: Metadata Comparison (when titles are close)
  ├── Same year + same journal + similar title → supportive evidence
  └── Different year or different journal → reduces confidence

NEVER auto-merge below 0.85 confidence.
```

**Output**:
```json
{
  "match_type": "doi_exact | title_similarity | uncertain",
  "confidence": 0.95,
  "source_a": "openalex:W123",
  "source_b": "crossref:10.1016/...",
  "evidence": ["DOI match", "3/4 authors match", "same year"],
  "action": "auto_merge | review_required",
  "merged_record_id": "uuid"
}
```

---

### Agent 6 — Faculty Attribution Agent

**Responsibility**: Determine which VFSTR faculty member authored each publication.

| Attribute | Detail |
|-----------|--------|
| **Trigger** | After deduplication |
| **Inputs** | Merged publication + faculty profiles |
| **Outputs** | Attribution with confidence + evidence |
| **LLM Usage** | Disambiguate similar names (e.g., two faculty named "K. Kumar") |
| **Deterministic** | Author ID matching, exact name matching, email/ORCID verification |

**Attribution Logic**:
```
Step 1: External ID Match
  ├── Publication has author with known ORCID → match faculty → confidence 0.99
  ├── Publication has author with known OpenAlex ID → match → confidence 0.98
  └── Publication has author with known Scopus ID → match → confidence 0.97

Step 2: Name + Affiliation Match
  ├── Author name matches faculty name variant AND
  │   affiliation matches VFSTR variant → confidence 0.90
  ├── Author name matches but no affiliation info → confidence 0.70
  └── Partial name match + VFSTR affiliation → confidence 0.60

Step 3: Contextual Evidence
  ├── Co-author overlap with known collaborators → +0.05
  ├── Research topic alignment → +0.05
  └── Department/field alignment → +0.03

THRESHOLDS:
  ≥ 0.85 → AUTO-ATTRIBUTE
  0.60–0.84 → REVIEW QUEUE (explain why uncertain)
  < 0.60 → SKIP (log as potential match)
```

> [!CAUTION]
> If two faculty have similar names (e.g., "Mihir Barman" and "MIHIR BHATT"), the agent MUST NOT guess. Both are sent to the review queue with the disambiguating evidence presented.

---

### Agent 7 — Research Metadata Enrichment Agent

**Responsibility**: Enrich publication records with journal quality metrics and indexing information.

| Attribute | Detail |
|-----------|--------|
| **Trigger** | After attribution |
| **Inputs** | Publication with journal/conference name |
| **Outputs** | Enriched publication with quality metrics |
| **LLM Usage** | Extract journal info from unstructured text when API lookup fails |
| **Deterministic** | ISSN lookup, OpenAlex source metadata, Crossref container info |

**Enrichment Fields**:
```
journal_name         "Image and Vision Computing"
journal_issn         "0262-8856"
publisher            "Elsevier"
indexing_status      ["SCIE", "Scopus"]  (from OpenAlex/Crossref)
quartile             "Q1"  (where available from OpenAlex)
impact_factor        4.0   (where explicitly provided in source data)
citescore            null  (where available)
publication_type     "journal-article"
open_access          true/false
source_url           "https://doi.org/10.1016/j.imavis.2025.105649"
```

**Data Sources for Enrichment**:
- OpenAlex: journal concepts, host_venue, is_oa, cited_by_count
- Crossref: container-title, ISSN, publisher, type
- CSV text: Some publications in the CSV already contain "{SCIE, IF: 4}" annotations

> [!NOTE]
> Impact Factor and CiteScore are proprietary metrics. We record them ONLY when they appear in trusted source data (e.g., faculty-provided annotations, OpenAlex-derived proxies). We never fabricate these values.

---

### Agent 8 — Research Integrity / Risk Agent

**Responsibility**: Detect suspicious records and flag for human investigation.

| Attribute | Detail |
|-----------|--------|
| **Trigger** | After enrichment |
| **Inputs** | Enriched publication, faculty publication history |
| **Outputs** | Risk assessment with evidence |
| **LLM Usage** | Analyze pattern anomalies, explain risk rationale |
| **Deterministic** | Publication velocity calculation, known predatory journal list check |

**Risk Indicators**:
```
PREDATORY_JOURNAL:
  - Check journal against known lists (Beall's List, DOAJ delisted)
  - Flag if no ISSN found
  - Flag if publisher not in recognized databases
  Weight: HIGH

AFFILIATION_MISMATCH:
  - Publication lists wrong institution
  - Faculty appears under different affiliation
  Weight: MEDIUM

SUSPICIOUS_VELOCITY:
  - >10 publications in same month
  - >30 publications in a year (abnormal for the discipline)
  Weight: MEDIUM

METADATA_CONFLICT:
  - Different sources report conflicting metadata
  - DOI resolves to different title
  - Author list discrepancy across sources
  Weight: MEDIUM

MISSING_DOI:
  - Publication in supposedly indexed journal has no DOI
  Weight: LOW

SELF_CITATION_ANOMALY:
  - Unusually high self-citation ratio (where citation data available)
  Weight: LOW
```

**Output**:
```json
{
  "publication_id": "uuid",
  "risk_level": "HIGH | MEDIUM | LOW | NONE",
  "risk_indicators": [
    {
      "type": "PREDATORY_JOURNAL",
      "evidence": "Journal 'XYZ' not found in DOAJ or OpenAlex sources",
      "confidence": 0.75,
      "recommendation": "Verify journal legitimacy"
    }
  ],
  "requires_review": true
}
```

---

### Agent 9 — Citation & Research Metrics Agent

**Responsibility**: Track citation counts, h-index, and i10-index over time.

| Attribute | Detail |
|-----------|--------|
| **Trigger** | Scheduled (weekly), after discovery sync |
| **Inputs** | Publication list per faculty, citation data from APIs |
| **Outputs** | `CitationSnapshot`, updated h-index, i10-index |
| **LLM Usage** | None |
| **Deterministic** | All calculations |

**Metrics Computed**:
```
Per Publication:
  - citation_count (from OpenAlex, Semantic Scholar, Crossref)
  - citation_source ("openalex" | "semantic_scholar" | "crossref")
  - snapshot_date

Per Faculty:
  - total_citations (sum across verified publications)
  - h_index (h papers with ≥ h citations each)
  - i10_index (papers with ≥ 10 citations)
  - publication_count (verified only)
  - citation_growth_rate (vs previous snapshot)

Per Department:
  - Aggregated metrics
  - Faculty ranking by h-index

Per Institution:
  - All departmental aggregates
```

**Historical Storage**:
```sql
-- Snapshots, not just current values
citation_snapshots (
  id, publication_id, citation_count,
  source, snapshot_date, created_at
)
faculty_metric_snapshots (
  id, faculty_id, h_index, i10_index,
  total_citations, total_publications,
  snapshot_date, created_at
)
```

---

### Agent 10 — Verification & Evidence Agent

**Responsibility**: Validate evidence chains and determine verification state.

| Attribute | Detail |
|-----------|--------|
| **Trigger** | After enrichment + risk analysis |
| **Inputs** | Publication with all metadata, risk assessment, attribution evidence |
| **Outputs** | Verification status + evidence chain |
| **LLM Usage** | Summarize evidence for human reviewers |
| **Deterministic** | Evidence completeness checks, confidence aggregation |

**Verification States**:
```
PENDING          — Newly discovered, not yet processed
AUTO_VERIFIED    — All checks passed, confidence ≥ 0.90, no risk flags
REVIEW_REQUIRED  — Confidence 0.60–0.89, or has risk flags
HUMAN_VERIFIED   — Reviewer confirmed
HUMAN_REJECTED   — Reviewer rejected
HUMAN_CORRECTED  — Reviewer modified metadata
CONFLICT         — Multiple conflicting evidence sources
```

**Evidence Chain Format**:
```json
{
  "publication_id": "uuid",
  "verification_status": "AUTO_VERIFIED",
  "overall_confidence": 0.93,
  "evidence_chain": [
    {
      "type": "discovery",
      "source": "openalex",
      "timestamp": "2026-09-11T02:00:00Z",
      "detail": "Found via author ID A5012345678"
    },
    {
      "type": "doi_confirmed",
      "source": "crossref",
      "timestamp": "2026-09-11T02:01:00Z",
      "detail": "DOI 10.1016/j.imavis.2025.105649 resolves to matching title"
    },
    {
      "type": "attribution",
      "confidence": 0.94,
      "method": "openalex_author_id",
      "detail": "Author ID matches Dr M Umadevi"
    },
    {
      "type": "affiliation_match",
      "confidence": 0.91,
      "detail": "Affiliation 'Vignan's Foundation...' matches known variant"
    },
    {
      "type": "journal_verified",
      "source": "openalex",
      "detail": "Image and Vision Computing — SCIE indexed, Q1"
    }
  ]
}
```

---

### Agent 11 — Human Review / Resolution Agent

**Responsibility**: Create and manage review queues, record human decisions.

| Attribute | Detail |
|-----------|--------|
| **Trigger** | When any agent flags a record for review |
| **Inputs** | Review task with evidence, conflicting data, options |
| **Outputs** | Review decision recorded in database |
| **LLM Usage** | Generate human-readable explanation of why review is needed |
| **Deterministic** | Queue management, decision recording, notification |

**Review Task Types**:
```
ATTRIBUTION_AMBIGUOUS   — "Is this publication by Dr X or Dr Y?"
DUPLICATE_UNCERTAIN     — "Are these the same publication?"
AFFILIATION_CONFLICT    — "Affiliation says 'NIT Silchar' but faculty is at VFSTR"
RISK_FLAG               — "Journal appears on predatory list"
METADATA_CONFLICT       — "OpenAlex says 2024, Crossref says 2023"
IDENTIFIER_MATCH        — "Is ORCID 0000-0001-XXXX this faculty member?"
MISSING_FACULTY         — "Publication found with VFSTR affiliation but no matching faculty"
```

**Review Interface Data**:
```json
{
  "task_id": "uuid",
  "task_type": "ATTRIBUTION_AMBIGUOUS",
  "priority": "HIGH",
  "created_at": "2026-09-11T02:05:00Z",
  "explanation": "Publication 'Optimizing multimodal...' has author 'Umadevi M.' which could match Dr M Umadevi (CSE) or could be a different person.",
  "evidence": { /* full evidence chain */ },
  "options": [
    {"action": "CONFIRM", "label": "Yes, this is Dr M Umadevi's publication"},
    {"action": "REJECT", "label": "No, this is not VFSTR faculty"},
    {"action": "REASSIGN", "label": "Assign to different faculty member"},
    {"action": "DEFER", "label": "Need more information"}
  ],
  "decision": null,
  "decided_by": null,
  "decided_at": null
}
```

> [!IMPORTANT]
> Human decisions are **FINAL** and **IMMUTABLE** (append-only audit). Agents never silently override a human's confirmed/rejected decision. If new evidence surfaces, a NEW review task is created referencing the previous decision.

---

### Agent 12 — Reporting & Accreditation Agent

**Responsibility**: Generate structured reports and accreditation-ready evidence packages.

| Attribute | Detail |
|-----------|--------|
| **Trigger** | Scheduled (monthly), on-demand |
| **Inputs** | Verified publication database, metrics snapshots |
| **Outputs** | PDF/Excel/JSON reports |
| **LLM Usage** | Generate narrative summaries for reports |
| **Deterministic** | Data aggregation, chart generation, export formatting |

**Report Types**:
```
FACULTY_REPORT
  - Individual faculty publication list with evidence
  - Citation metrics over time
  - h-index trend
  - Verification status distribution

DEPARTMENT_REPORT
  - All faculty in department
  - Aggregated metrics
  - Publication type distribution
  - Journal quartile distribution
  - Year-over-year comparison

INSTITUTION_REPORT
  - All departments
  - Institutional KPIs
  - Research output trends
  - Top researchers by metrics

ACCREDITATION_EVIDENCE
  - Faculty-wise publication evidence
  - Verification audit trail
  - Source provenance for every record
  - Exportable as structured JSON + PDF

TREND_REPORT
  - Research area trends
  - Citation growth
  - Collaboration patterns
  - New research areas emerging
```

---

### Agent 13 — Research Intelligence / Assistant Agent

**Responsibility**: Natural language interface to the verified research knowledge base.

| Attribute | Detail |
|-----------|--------|
| **Trigger** | User query |
| **Inputs** | Natural language question + verified database |
| **Outputs** | Factual answer with evidence/provenance |
| **LLM Usage** | Query understanding, answer generation, SQL generation |
| **Deterministic** | Database queries, metric lookups |

**Example Queries & Resolution**:
```
"Show publications of the CSE department in 2025"
  → SQL: SELECT * FROM publications WHERE department='CSE' AND year=2025
  → Return structured results with verification status

"Which faculty have the highest citation growth?"
  → Compare latest vs previous metric snapshots
  → Rank by delta, return top N

"Which publications still need verification?"
  → SQL: WHERE verification_status IN ('PENDING', 'REVIEW_REQUIRED')

"Show papers with affiliation conflicts"
  → SQL: WHERE risk_status='AFFILIATION_MISMATCH'

"Generate an accreditation-ready publication summary"
  → Trigger Agent 12 for ACCREDITATION_EVIDENCE report
```

> [!IMPORTANT]
> This agent ONLY answers from verified system data. It NEVER invents publications, citations, or metrics. If data is unavailable, it says so and explains what verification state the data is in.

---

## 3. Agent Communication Flow

```
┌───────────────────────────────────────────────────────────────────┐
│                    LANGGRAPH STATE GRAPH                          │
│                                                                   │
│  ┌─────┐    ┌─────┐    ┌─────┐    ┌─────┐    ┌─────┐    ┌─────┐ │
│  │ A3  │───▶│ A4  │───▶│ A5  │───▶│ A6  │───▶│ A7  │───▶│ A8  │ │
│  │Disc.│    │Norm.│    │Dedup│    │Attr.│    │Enr. │    │Risk │ │
│  └─────┘    └─────┘    └─────┘    └──┬──┘    └─────┘    └──┬──┘ │
│                                      │                      │    │
│                                      │ low confidence        │    │
│                                      ▼                      ▼    │
│                                   ┌──────┐             ┌──────┐  │
│                                   │ A11  │◀────────────│ A10  │  │
│                                   │Review│             │Verify│  │
│                                   └──┬───┘             └──┬───┘  │
│                                      │                    │      │
│                                      │ human decision     │      │
│                                      ▼                    ▼      │
│                                   ┌───────┐          ┌───────┐   │
│                                   │  DB   │◀─────────│  A9   │   │
│                                   │Update │          │Metrics│   │
│                                   └───────┘          └───────┘   │
│                                                                   │
│  Background / On-Demand:                                          │
│  ┌─────┐  ┌─────┐  ┌─────┐                                      │
│  │ A1  │  │ A2  │  │ A12 │  ┌─────┐                             │
│  │Ident│  │Affil│  │Rept.│  │ A13 │                             │
│  └─────┘  └─────┘  └─────┘  │Asst.│                             │
│                              └─────┘                             │
└───────────────────────────────────────────────────────────────────┘
```

---

## 4. Shared Agent State

All agents share a typed state object through the LangGraph state graph:

```python
class PipelineState(TypedDict):
    # Input
    sync_run_id: str
    faculty_profiles: list[FacultyProfile]
    affiliation_variants: list[AffiliationVariant]
    
    # Discovery
    raw_discoveries: list[RawDiscoveredPublication]
    
    # Normalization
    normalized_publications: list[NormalizedPublication]
    
    # Deduplication
    match_decisions: list[MatchDecision]
    merged_publications: list[MergedPublication]
    
    # Attribution
    attribution_results: list[AttributionResult]
    
    # Enrichment
    enriched_publications: list[EnrichedPublication]
    
    # Risk
    risk_assessments: list[RiskAssessment]
    
    # Verification
    verification_results: list[VerificationResult]
    
    # Review
    review_tasks: list[ReviewTask]
    
    # Metrics
    metric_snapshots: list[MetricSnapshot]
    
    # Run metadata
    started_at: datetime
    completed_at: datetime | None
    status: str  # RUNNING | COMPLETED | FAILED | PAUSED_FOR_REVIEW
    errors: list[str]
```
