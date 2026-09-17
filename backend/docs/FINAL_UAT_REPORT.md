# VFSTR Faculty Research Intelligence Platform — Final Pre-Staging UAT & Hard Audit Report
**Date:** September 17, 2026  
**Environment:** Local Pre-Staging (FastAPI Backend on port 8000, Vite React Frontend on port 5173, PostgreSQL Database)  
**Final Pre-Staging Decision:** `CONDITIONALLY_READY_FOR_STAGING` (All internal subsystems, single-entry ID flow, database persistence, deduplication, attribution protection, metrics recalculation, RBAC, and tests are verified; live IEEE Xplore production discovery is conditionally gated behind institutional enterprise API key availability).

---

## A. Requirement Status Breakdown

| Requirement Area | Status | Evidence & Verification Detail |
| :--- | :--- | :--- |
| **Faculty Account Binding** | `VERIFIED` | 100% of 25 faculty accounts bound via `GET /api/v1/faculty/me` (0 "Faculty Profile Not Found"). |
| **Single-Entry ID Flow** | `VERIFIED` | Onboarding banner allows ID entry once; persists to PostgreSQL `faculty_identifiers`. |
| **Zero ID Re-entry** | `VERIFIED` | Returning logins load saved verified IDs automatically without re-prompting. |
| **Scopus Ingestion** | `VERIFIED` | Queries live via exact `AU-ID(...)` with full batch pagination. |
| **OpenAlex Ingestion** | `VERIFIED` | Queries live via `author.id:...` with complete page pagination. |
| **Semantic Scholar Ingestion** | `VERIFIED` | Queries live via `/author/{id}/papers` with offset pagination. |
| **Crossref Enrichment** | `VERIFIED` | Queries metadata and DOIs with polite pool headers. |
| **IEEE Identity Persistence** | `VERIFIED` | IEEE Author ID (e.g., `256481733945119`, `37085445363`) stored & verified with direct profile link. |
| **IEEE Live API Discovery** | `BLOCKED BY EXTERNAL CREDENTIAL` | `CONNECTOR_READY` — requires institutional IEEE Xplore production API key. |
| **ORCID Live Discovery** | `NOT CONFIGURED` | `NOT_CONFIGURED` — requires institutional ORCID OAuth credentials. |
| **Canonical Deduplication** | `VERIFIED` | Multi-source works deduplicated into 1 canonical `Publication` + N `PublicationSource` rows (97 multi-source merged records in DB). |
| **False-Positive Protection** | `VERIFIED` | VLITS Lara (P. Sai Prasad) and Mother Teresa Univ (Physics) homonyms quarantined/rejected (0 false positives confirmed). |
| **Verification Queue** | `VERIFIED` | Ambiguous candidates quarantined into `review_tasks`; CONFIRM adds author & recalculates metrics; REJECT excludes. |
| **Real Publication Navigation** | `VERIFIED` | Blue titles open verified `source_url` or `https://doi.org/<DOI>` in new tab (`target="_blank"`). |
| **Citation Refresh & Metrics** | `VERIFIED` | Recalculates Total Citations, h-index, and i10-index mathematically from confirmed canonical publications. |
| **Scheduled Background Daemon**| `VERIFIED` | APScheduler registered with 5 cron jobs (discovery, citations, metrics, alerts, reports). |
| **RBAC / Tenant Isolation** | `VERIFIED` | Cross-tenant mutation attempts return `403 Forbidden` / `404 Not Found`. |
| **Database Integrity** | `VERIFIED` | 0 duplicate profiles, 0 orphan author links, 0 orphan sources, 0 cross-faculty leakage. |

---

## B. Source Connector Status Taxonomy

| Source | Operational Status | Query Anchor | Pagination Supported | Notes |
| :--- | :--- | :--- | :--- | :--- |
| **Scopus** | `ACTIVE` | `AU-ID(<id>)` | `start` / `count` offset | Operational with live API key |
| **OpenAlex** | `ACTIVE` | `author.id:<id>` | `page` / `per_page` | Operational via polite pool |
| **Semantic Scholar** | `ACTIVE` | `author/<id>/papers` | `offset` / `limit` | Operational via Graph API |
| **Crossref** | `ACTIVE` | `author` + `affiliation` | `offset` / `cursor` | Operational via polite pool |
| **IEEE Xplore** | `CONNECTOR_READY` | `author_id:<id>` | `start_record` | **Awaiting Institutional Enterprise Key** |
| **ORCID** | `NOT_CONFIGURED` | `/<orcid>/works` | Works feed | **Awaiting Institutional OAuth Client ID** |

---

## C. Identity Persistence & Zero Re-entry Audit
1. **First-Time Flow:**
   - Unbound or new faculty accounts display the "CONNECT YOUR RESEARCH PROFILES" banner.
   - User inputs Scopus, IEEE, OpenAlex, ORCID, or Semantic Scholar IDs and clicks "SAVE & VERIFY IDENTIFIERS".
   - Identifiers are validated, checked against live APIs where configured, and committed to PostgreSQL table `faculty_identifiers`.
2. **Returning Flow:**
   - Upon logging out and logging back in, the system retrieves `faculty_identifiers` via `GET /api/v1/faculty/me/identifiers`.
   - The onboarding banner is hidden; persistent cards render with `✓ Verified` badges, direct profile links, and last-verified timestamps.
   - Zero ID re-entry is required.

---

## D. Critical Real-World Test Cases

### 1. Dr. P. Siva Prasad (IEEE Author ID: `256481733945119`)
- **External IEEE Profile Status:** Visibly lists 2 publications at `https://ieeexplore.ieee.org/author/256481733945119`.
- **IEEE Identity Persistence:** `VERIFIED` (Stored in PostgreSQL `faculty_identifiers` with direct link `https://ieeexplore.ieee.org/author/256481733945119`).
- **IEEE Live API Discovery Status:** `NOT_CONFIGURED / CONNECTOR_READY`.
- **Source Reconciliation:**
  - IEEE External Profile Total: **2**
  - Records Requested: **0** (Live API key unconfigured in `.env`)
  - Records Received: **0**
  - Live Access Status: `CONNECTOR_READY` (Awaiting production API key)
  - Confirmed Publications in System: **15** (High-confidence institutional publications)
  - Quarantined Review Tasks: **89** (Homonym candidates from VLITS Lara / P. Sai Prasad safely isolated)

### 2. Dr. M. Umadevi Multi-Source Ingestion
- **Persistent Identifiers Loaded:**
  - **Scopus:** `54788460700` (`✓ Verified`)
  - **IEEE:** `37085445363` (`✓ Verified`)
  - **OpenAlex:** `https://openalex.org/A5003901187`
- **Confirmed Publications:** **27**
- **Citations:** **33**
- **h-index:** **4**
- **i10-index:** **1**
- **Citation Distribution:** `[10, 5, 4, 4, 3, 2, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]`
- **Collision Protection:** Homonyms from Mother Teresa Women's University (Department of Physics) cleanly rejected (**0** false positives).

---

## E. Source Reconciliation Summary (Dr. M. Umadevi)

| Source | Status | Records Discovered | Canonical Pubs | Confirmed | Ambiguous (Queue) | Rejected |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Scopus** | `ACTIVE` | 18 | 18 | 18 | 0 | 0 |
| **OpenAlex** | `ACTIVE` | 15 | 15 | 9 | 6 | 0 |
| **Crossref** | `ACTIVE` | 12 | 12 | 8 | 4 | 0 |
| **Semantic Scholar** | `ACTIVE` | 6 | 6 | 4 | 2 | 0 |
| **IEEE Xplore** | `CONNECTOR_READY` | 0 (Awaiting Key) | 0 | 0 | 0 | 0 |
| **ORCID** | `NOT_CONFIGURED` | 0 | 0 | 0 | 0 | 0 |

---

## F. Background Synchronization & Scheduler Audit
- **APScheduler Status:** Operational in-process with FastAPI event loop.
- **Registered Cron Jobs:**
  1. `full_discovery_sync`: Weekly (Sunday 2am) -> `PipelineOrchestrator.run_full_pipeline`
  2. `citation_refresh`: Wednesday (3am) -> `MetricsAgent.run`
  3. `metrics_compute`: Wednesday (4am) -> `MetricsAgent.run`
  4. `alert_generation`: Daily (5am) -> `NotificationService`
  5. `report_generation`: Monthly (1st 6am) -> `ReportingAgent.generate_institution_report`

---

## G. Database Truth & Integrity Audit

| Database Metric | Value | Audit Verification Result |
| :--- | :--- | :--- |
| **Total Faculty Profiles** | **25** | Exactly matches institutional faculty roster (0 duplicates) |
| **Total User Accounts** | **26** | 25 Faculty Users + 1 System Admin |
| **Bound Faculty Accounts** | **25** | 100% of faculty accounts cleanly bound to profiles |
| **Canonical Publications** | **1,678** | Unique canonical records across the institution |
| **Publication Sources** | **1,775** | Ingested source entries (97 multi-source merged records) |
| **Confirmed Author Links** | **371** | High-confidence attribution links ($\ge 0.70$) |
| **Quarantined Review Tasks** | **3,651** | Ambiguous records requiring human review |
| **Orphan PublicationAuthors** | **0** | Foreign keys strictly intact |
| **Orphan PublicationSources** | **0** | Foreign keys strictly intact |
| **Orphan ReviewTasks** | **0** | Foreign keys strictly intact |

---

## H. Security & RBAC Isolation Audit
- **Endpoint Authorization:** Endpoints `/api/v1/faculty/me`, `/me/identifiers`, and `/me/sync` strictly bind to the authenticated JWT subject.
- **Cross-Tenant Attack Test:** Verified that attempting cross-faculty identifier mutation returns `403 Forbidden` / `404 Not Found`.
- **Zero Client Secret Exposure:** API keys and database credentials reside strictly on the server backend and are never exposed in frontend code, responses, or client storage.

---

## I. Automated Test Suite & Build Results
- **Backend Pytest Suite (`.venv\Scripts\pytest`):** **81 / 81 Tests Passed (100% Pass Rate)**
- **Frontend Production Build (`npm run build`):** **Compiled successfully in 4.85s with 0 errors**

---

## J. Final Pre-Staging Classification

### Classification: `CONDITIONALLY_READY_FOR_STAGING`

**Rationale & External Prerequisites:**
1. **Core Platform:** Complete, fully tested, mathematically verified, and zero-error frontend build.
2. **External Requirement 1 (IEEE Xplore):** Connector implementation is ready; live production discovery requires provisioning an institutional IEEE Xplore Enterprise API key.
3. **External Requirement 2 (ORCID):** Requires registering institutional ORCID OAuth credentials for live institutional sync.
4. **Deployment Constraint:** System is paused locally without premature deployment to Render per explicit instructions.
