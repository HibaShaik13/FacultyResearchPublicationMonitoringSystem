# PHASE 2 IMPLEMENTATION REPORT
## Autonomous Initialization & Research Pipeline Architecture

### 1. Phase 2 Objective
The primary objective of Phase 2 is to transform the VESTR Faculty Research Publication Monitoring System into an autonomous, agent-driven monitoring architecture. On a clean deployment to a fresh PostgreSQL database (such as on Render), the system autonomously:
1. Provisions the 25 institutional baseline faculty profiles.
2. Synchronizes corresponding secure user accounts.
3. Automatically queues and executes the initial research discovery pipeline in the background without blocking server startup or API health checks.
4. Uses scholarly researcher identifiers to discover publications from open and configured sources (OpenAlex, Crossref, Semantic Scholar, ORCID, Scopus, IEEE, Vidwan).
5. Normalizes metadata, deduplicates multi-source records to single canonical publications, accurately attributes works to faculty profiles, generates review tasks for ambiguous records, enriches citation metrics, and computes live institutional metrics in PostgreSQL.

---

### 2. Phase 2A Status & Baseline Architecture
- **Faculty Baseline**: [`data/raw/faculty_profiles.csv`](file:///c:/Users/shaik/Downloads/FacultyResearchPublicationMonitoringSystem-main/FacultyResearchPublicationMonitoringSystem-main/data/raw/faculty_profiles.csv) contains exactly **25 faculty** (24 historical baseline faculty + Dr. P. Siva Prasad).
- **Dr. P. Siva Prasad Baseline Presence**: Present exactly once (`drpsp_cse@vignan.ac.in`).
- **Original 24 Baseline Rows**: Byte-for-byte identical to baseline Git HEAD.
- **Publications Baseline Integrity**: [`data/raw/faculty_publications.csv`](file:///c:/Users/shaik/Downloads/FacultyResearchPublicationMonitoringSystem-main/FacultyResearchPublicationMonitoringSystem-main/data/raw/faculty_publications.csv) was **NOT modified** and remains byte-for-byte untouched (SHA-256: `3dccaf2bd296b5a62137c8d8ae0f6b2df475b14acc4d0dbc2c60773e4c5379b1`). Dynamic publication data is **not** seeded via CSV.

---

### 3. Baseline Initialization (`backend/app/seed/bootstrap.py`)
On application startup (or running `python -m app.seed.bootstrap`):
- `ensure_baseline_accounts(session)`:
  - Invokes `FacultyImporter` to parse `faculty_profiles.csv`.
  - Performs non-destructive, idempotent upserts: existing faculty records are matched by institutional email/normalized name and preserved; new faculty profiles (e.g. Dr. P. Siva Prasad) are added.
  - Ensures every faculty profile is associated with an active `User` account (`role="faculty"`) with password hashed using `BOOTSTRAP_FACULTY_PASSWORD`.
  - Ensures the research administrator account is provisioned with `role="research_admin"`.
  - Preserves existing research publications, sources, authors, review tasks, metrics snapshots, and audit logs.

---

### 4. Automatic Startup & Initial Pipeline Architecture (`backend/app/main.py`)
```
APPLICATION START
      ↓
DATABASE CONNECTION & MIGRATIONS READY
      ↓
SCHEDULER INITIALIZATION (APScheduler)
      ↓
BASELINE FACULTY & ACCOUNT RECONCILIATION
      ↓
CHECK INITIAL SYNC STATE (SyncRun DB check)
      ↓
QUEUE INITIAL RESEARCH PIPELINE (asyncio.create_task)
      ↓
RETURN LIFESPAN / HEALTH PROBES HEALTHY (/health -> 200 OK)
      ↓
BACKGROUND MULTI-AGENT PIPELINE RUNS AUTONOMOUSLY
```
Startup completes in < 2 seconds and API health probes return HTTP 200 immediately.

---

### 5. Duplicate Protection & Idempotency
- **Persistent Database State**: Handled via `SyncRun` table in PostgreSQL.
- **Active Run Gate**: `PipelineOrchestrator.run_full_pipeline` queries the database for any `full_sync` with `status == "running"`. If found, subsequent triggers (concurrent Render workers, restarts, health check pings, or manual requests) log `"Pipeline sync already active; duplicate trigger skipped"` and return gracefully without spawning duplicate runs.
- **Initial Sync Gate**: `trigger_initial_research_pipeline_if_needed()` checks `has_initial_sync_completed()` and skips re-triggering if a full sync has already succeeded or is running.

---

### 6. Stale Run Recovery (`backend/app/orchestrator/pipeline_orchestrator.py`)
- If a server process crashes or is killed during a sync run, `recover_stale_runs(stale_threshold_minutes=30)` detects `SyncRun` records that have been in `"running"` status past the threshold.
- Marks them `status = "failed"`, logs the recovery event, records error count, and sets `completed_at`.
- Preserves the historical execution log in the database while allowing subsequent runs to proceed.

---

### 7. Identity-Driven Discovery & Dr. P. Siva Prasad Verification
- **Identity Priority**: Strong Verified Identifiers > Source-Specific IDs > Institutional Affiliation > Normalized Name.
- **Verified Identifiers for Dr. P. Siva Prasad**:
  - Scopus Author ID: `57208392627`
  - ORCID ID: `0000-0002-2789-7431`
  - IEEE Author ID: `256481733945119`
  - Vidwan Profile ID: `84197`
  - Semantic Scholar ID: `2406283009`
- **Safeguard**: OpenAlex ID `A5003901187` is confirmed as a mismatch (Dr. M. Umadevi) and is strictly rejected/disabled from associating with Dr. P. Siva Prasad.

---

### 8. Vidwan Public Profile Connector (`backend/app/connectors/vidwan.py`)
- Dedicated, non-authenticated public profile connector for Vidwan / IRINS (`https://vidwan.inflibnet.ac.in/profile/{id}`).
- Extracts publication titles, years, venues, and DOIs from public profiles.
- Handles network errors and timeouts gracefully with failure isolation.
- Discovered works are ingested with `source_system = "vidwan"`, attached to canonical publications, and linked with verified authorship.

---

### 9. Multi-Source Deduplication & Attribution Safety
- **Canonical Merging**: `PublicationDiscoveryAgent` and `DeduplicationAgent` deduplicate across OpenAlex, Crossref, Scopus, IEEE, Semantic Scholar, ORCID, and Vidwan using case-insensitive DOI matching and normalized title matching.
- **Attribution Safeguards**:
  - Distinguishes VFSTR (Vadlamudi / Guntur) from sibling Vignan institutions (VLITS Lara, VITS Hyderabad, VIIT Vizag, Nirula, Pharmacy).
  - Matches forename tokens and initial variants to eliminate false cross-author collisions.
  - High confidence (>=0.85) produces verified attribution; ambiguous matches route to `ReviewTask` queue for human review.

---

### 10. Connector Execution & Credential Matrix

| Connector | Credential Dependency | Mode | Behavior When Missing |
| :--- | :--- | :--- | :--- |
| **OpenAlex** | `OPENALEX_EMAIL` (Optional) | REST API / Polite Pool | Active (uses default email) |
| **Crossref** | `CROSSREF_EMAIL` (Optional) | REST API / Polite Pool | Active (uses default email) |
| **Semantic Scholar** | `SEMANTIC_SCHOLAR_API_KEY` (Optional) | Public / API Mode | Active (uses public endpoints) |
| **ORCID** | `ORCID_CLIENT_ID` / `SECRET` (Optional) | Public Member API | Active (uses public work summaries) |
| **Vidwan** | None | Public Profile Ingestion | Active (queries public profile by ID) |
| **Scopus** | `SCOPUS_API_KEY` / `INST_TOKEN` (Required) | REST API | Safely skipped when not configured |
| **IEEE Xplore** | `IEEE_API_KEY` (Required) | Gateway REST API | Safely skipped when not configured |
| **Google Scholar** | None (Optional) | Fallback parser | Active where accessible |

---

### 11. Dynamic Metrics & Provenance
- Citation counts, h-index, and i10-index are computed directly from the PostgreSQL database by `MetricsAgent`.
- Every fact records provenance via `ProvenanceRecord` (source system, timestamp, agent name, confidence).
- Baseline CSVs are never used as a dynamic metrics store.

---

### 12. Verification & Testing Summary
- **Backend Test Suite**: **86 / 86 PASSED** (including 5 new Phase 2 integration tests).
- **Frontend Build**: `tsc -b && vite build` succeeded with **0 errors**.
- **`faculty_publications.csv` Integrity**: SHA-256 confirmed unchanged: `3dccaf2bd296b5a62137c8d8ae0f6b2df475b14acc4d0dbc2c60773e4c5379b1`.
- **Git Check**: `git diff --check` passed cleanly with 0 whitespace/syntax errors.

---

### 13. Deployment & Rollback Procedures

#### Deployment Procedure:
1. Ensure all local tests pass (`86/86`).
2. Run database migrations: `alembic upgrade head`.
3. Deploy the application to Render.
4. On startup, application automatically initializes 25 faculty profiles and launches the background discovery pipeline.
5. Monitor logs and `/api/v1/agents/status` to track agent throughput.

#### Rollback Procedure:
1. Roll back application code commit via Git / Render deploy rollback.
2. The database schema and data remain intact without requiring destructive truncation.
