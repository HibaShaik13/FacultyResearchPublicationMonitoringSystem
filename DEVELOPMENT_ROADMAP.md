# Development Roadmap — Faculty Research Publication Monitoring System

> **Version**: 0.1 (Phase 0)
> **Date**: 2026-09-11
> **Target**: Hackathon-winning institutional research intelligence platform

---

## Phase Summary

| Phase | Name | Scope | Est. Effort | Dependencies |
|-------|------|-------|-------------|--------------|
| **0** | Architecture & Data Analysis | ✅ **COMPLETE** | — | None |
| **1** | Project Foundation | Database, config, project skeleton | 1 day | Phase 0 |
| **2** | Faculty Identity + Affiliation | Agents 1 & 2, CSV import | 1 day | Phase 1 |
| **3** | Research Source Connectors | OpenAlex, Crossref, Semantic Scholar, ORCID | 1 day | Phase 1 |
| **4** | Publication Discovery | Agent 3, scheduled discovery | 1 day | Phase 2, 3 |
| **5** | Normalization + Deduplication | Agents 4 & 5 | 1 day | Phase 4 |
| **6** | Faculty Attribution | Agent 6, confidence scoring | 0.5 day | Phase 5 |
| **7** | Metadata Enrichment | Agent 7, journal/indexing data | 0.5 day | Phase 6 |
| **8** | Research Integrity/Risk | Agent 8, risk detection | 0.5 day | Phase 7 |
| **9** | Citation & Metrics Tracking | Agent 9, historical snapshots | 0.5 day | Phase 7 |
| **10** | Human Verification/Review | Agent 11, review queue UI | 1 day | Phase 8 |
| **11** | Continuous Monitoring | Celery Beat, scheduled sync | 0.5 day | Phase 4 |
| **12** | Research Intelligence Graph | Force-directed graph, D3.js | 0.5 day | Phase 6 |
| **13** | Analytics Dashboard | Charts, KPIs, trends | 1 day | Phase 9 |
| **14** | Reports + Accreditation | Agent 12, PDF/Excel export | 0.5 day | Phase 9 |
| **15** | Research Assistant | Agent 13, NL query interface | 0.5 day | Phase 6 |
| **16** | AutoResearch Integration | Adapt connectors & chatbot | 0.5 day | Phase 15 |
| **17** | Security + Testing | Auth, RBAC, test suite | 1 day | All |
| **18** | Hackathon Demo Polish | Branding, animations, demo script | 0.5 day | All |

---

## Phase Details

### Phase 0 — Architecture & Data Analysis ✅ COMPLETE

**Deliverables**:
- [x] Workspace inspection
- [x] CSV data analysis (24 faculty, 201 publications, 16 columns)
- [x] Data quality assessment (16 missing critical fields identified)
- [x] AutoResearch Agent capability analysis
- [x] `PROJECT_ARCHITECTURE.md`
- [x] `AGENT_ARCHITECTURE.md`
- [x] `DATA_MODEL.md`
- [x] `DEVELOPMENT_ROADMAP.md` (this document)
- [x] Raw data copied to `data/raw/`
- [x] Vignan branding assets copied to `assets/branding/`

---

### Phase 1 — Project Foundation

**Objective**: Set up the complete project skeleton, database, and configuration.

**Backend Tasks**:
- [ ] Initialize Python project with `pyproject.toml`
- [ ] Set up FastAPI application factory (`app/main.py`)
- [ ] Configure Pydantic Settings for environment variables (`app/config.py`)
- [ ] Set up async SQLAlchemy 2.0 with PostgreSQL (`app/database.py`)
- [ ] Set up Alembic migrations
- [ ] Create initial migration with all core tables
- [ ] Set up Docker Compose (PostgreSQL, Redis, backend)
- [ ] Create `.env.example` with all required variables
- [ ] Set up structured logging
- [ ] Create health check endpoint

**Frontend Tasks**:
- [ ] Initialize Vite + React + TypeScript project
- [ ] Configure Tailwind CSS v4
- [ ] Set up project structure (pages, components, services, stores)
- [ ] Create base layout with Vignan branding header
- [ ] Create API client service (axios/fetch wrapper)
- [ ] Set up React Router with page skeleton
- [ ] Create design system tokens (colors, typography, spacing)

**Verification**:
- `docker compose up` starts all services
- Backend responds to `/health` endpoint
- Frontend loads with Vignan-branded layout
- Database migrations run successfully
- `.env.example` documents all required variables

---

### Phase 2 — Faculty Identity + Affiliation Intelligence

**Objective**: Import CSV data, create faculty profiles, seed affiliation variants.

**Tasks**:
- [ ] Implement CSV importer (`app/seed/csv_importer.py`)
  - Parse all 16 columns
  - Handle encoding (UTF-8-BOM)
  - Normalize names (remove titles, handle casing)
  - Infer departments from email
  - Parse pipe-delimited fields
  - Generate name variants
  - Store raw data alongside normalized
- [ ] Implement Agent 1 — Faculty Identity Agent
  - Name parsing and normalization
  - Name variant generation
  - External identifier placeholders
- [ ] Implement Agent 2 — Affiliation Intelligence Agent
  - Seed known VFSTR affiliation variants
  - String similarity matching (fuzzywuzzy/rapidfuzz)
  - LLM-assisted classification for edge cases
- [ ] Create Faculty API endpoints (CRUD, search)
- [ ] Create Faculty profile page (frontend)
- [ ] Create Faculty list page with search/filter

**Verification**:
- All 24 faculty imported with no data loss
- Original CSV preserved unchanged
- `Publications Count` in CSV matches parsed count
- Name variants generated for each faculty member
- Department correctly inferred for 21/24 faculty
- Affiliation variant dictionary seeded

---

### Phase 3 — Research Source Connectors

**Objective**: Build pluggable API connectors for research data sources.

**Tasks**:
- [ ] Create abstract connector interface (`app/connectors/base.py`)
- [ ] Implement OpenAlex connector
  - Author search by name + affiliation
  - Works lookup by author ID
  - Institution search
  - Rate limiting & retry logic
- [ ] Implement Crossref connector
  - DOI resolution
  - Author search
  - Works metadata
- [ ] Implement Semantic Scholar connector
  - Author search
  - Paper search
  - Citation data
- [ ] Implement ORCID connector
  - Profile lookup
  - Works retrieval
- [ ] Implement connector health check & status API
- [ ] Write integration tests with real API calls

**Verification**:
- Each connector returns properly typed results
- Rate limiting prevents API bans
- Retry logic handles transient failures
- Connector status visible in admin UI

---

### Phase 4 — Publication Discovery

**Objective**: Discover publications from external sources using faculty identifiers.

**Tasks**:
- [ ] Implement Agent 3 — Publication Discovery Agent
  - For each faculty: search all configured sources
  - Use name variants + affiliation variants
  - Record raw discovery with full metadata
- [ ] Create discovery trigger API (manual + scheduled)
- [ ] Store raw discoveries in `publication_sources`
- [ ] Implement discovery run tracking (`sync_runs`, `agent_runs`)
- [ ] Create Discovery Pipeline page (frontend)
  - Show active/past runs
  - Publications discovered per source
  - Progress indicators

**Verification**:
- Discovery finds real publications for faculty with known works
- Raw API responses stored for traceability
- No fake/fabricated publications created
- Run statistics accurately tracked

---

### Phase 5 — Normalization + Deduplication

**Objective**: Standardize metadata and identify duplicates across sources.

**Tasks**:
- [ ] Implement Agent 4 — Metadata Normalization
  - Title normalization (Unicode, whitespace, casing)
  - DOI extraction and normalization
  - Author name parsing
  - Date parsing
  - Publication type classification
- [ ] Implement Agent 5 — Deduplication
  - DOI exact match (confidence 1.0)
  - Title similarity (Jaccard/cosine on tokens)
  - Author overlap scoring
  - Merge logic with confidence thresholds
  - Generate merge decisions for review
- [ ] Parse CSV publication text into structured records
  - Extract DOIs from publication text
  - Extract years from publication text
  - Extract journal names from publication text
  - Use LLM for difficult parsing cases

**Verification**:
- Publications from multiple sources merged correctly
- DOI matches produce confidence 1.0
- No unsafe merges below threshold
- Uncertain matches sent to review queue
- CSV publications parsed with original text preserved

---

### Phase 6 — Faculty Attribution + Confidence Scoring

**Objective**: Link publications to the correct VFSTR faculty member.

**Tasks**:
- [ ] Implement Agent 6 — Faculty Attribution
  - External ID matching (ORCID, OpenAlex)
  - Name + affiliation matching
  - Confidence scoring with evidence
  - Ambiguous cases → review queue
- [ ] Create `publication_authors` records with attribution evidence
- [ ] Implement Verification & Evidence Agent (Agent 10)
  - Evidence chain construction
  - Verification state management

**Verification**:
- Publications correctly attributed to CSV faculty
- Confidence scores reflect evidence quality
- No publications auto-attributed below 0.85
- Ambiguous attributions appear in review queue

---

### Phase 7 — Metadata Enrichment

**Tasks**:
- [ ] Implement Agent 7 — Enrichment
  - Journal/conference ISSN lookup
  - Indexing status from OpenAlex
  - Quartile from OpenAlex source data
  - Impact Factor from CSV annotations and trusted sources
  - Publication type classification
- [ ] Store enrichment provenance

---

### Phase 8 — Research Integrity / Risk Analysis

**Tasks**:
- [ ] Implement Agent 8 — Risk Agent
  - Predatory journal detection (DOAJ cross-check)
  - Affiliation mismatch detection
  - Publication velocity analysis
  - Metadata conflict detection
- [ ] Create Risk Flag UI components

---

### Phase 9 — Citation & Metrics Tracking

**Tasks**:
- [ ] Implement Agent 9 — Citation Metrics
  - Fetch citation counts from OpenAlex/Semantic Scholar
  - Compute h-index and i10-index
  - Store snapshots with timestamps
- [ ] Create metrics trend charts

---

### Phase 10 — Human Verification / Review Workflow

**Tasks**:
- [ ] Implement Agent 11 — Review Agent
  - Review task creation with explanation
  - Evidence presentation
  - Decision recording
- [ ] Create Review Queue page
  - Priority sorting
  - Side-by-side evidence comparison
  - Action buttons (confirm/reject/merge/reassign)
  - Decision audit trail

---

### Phase 11 — Continuous Monitoring

**Tasks**:
- [ ] Set up Celery + Redis
- [ ] Configure Celery Beat scheduler
- [ ] Implement scheduled sync tasks
- [ ] Admin UI for schedule configuration
- [ ] Alert generation on new discoveries/conflicts

---

### Phase 12 — Research Intelligence Graph

**Tasks**:
- [ ] Build force-directed graph visualization
  - Faculty → Publications → Journals → Topics
  - Collaboration networks
  - Department clusters
- [ ] Interactive filtering and exploration

---

### Phase 13 — Analytics Dashboard

**Tasks**:
- [ ] Research Command Center (main dashboard)
  - Live KPIs: total publications, verified count, pending review, active alerts
  - Recent discoveries feed
  - Agent status indicators
- [ ] Citation analytics (h-index trends, citation growth)
- [ ] Quartile distribution charts
- [ ] Department comparison views
- [ ] Faculty research profiles generated from verified data

---

### Phase 14 — Reports + Accreditation Evidence

**Tasks**:
- [ ] Implement Agent 12 — Reporting Agent
- [ ] Faculty publication report (PDF/Excel)
- [ ] Department summary report
- [ ] Institution summary report
- [ ] Accreditation evidence package (ZIP with evidence)
- [ ] Report generation UI

---

### Phase 15 — Natural Language Research Assistant

**Tasks**:
- [ ] Implement Agent 13 — Research Assistant
- [ ] Natural language → database query translation
- [ ] Chat interface with evidence-grounded responses
- [ ] Query history

---

### Phase 16 — AutoResearch Integration

**Tasks**:
- [ ] Refactor ArXiv connector from AutoResearch
- [ ] Adapt Semantic Scholar connector
- [ ] Integrate trend analysis capability
- [ ] Adapt chatbot for institutional context

---

### Phase 17 — Security + Testing

**Tasks**:
- [ ] JWT authentication implementation
- [ ] Role-based access control middleware
- [ ] Faculty login (email-based)
- [ ] Admin login
- [ ] Unit tests for all agents
- [ ] Integration tests for API endpoints
- [ ] Connector integration tests
- [ ] End-to-end pipeline test

---

### Phase 18 — Hackathon Demo Polish

**Tasks**:
- [ ] Vignan branding throughout UI
- [ ] Loading animations and transitions
- [ ] Demo script with real data walkthrough
- [ ] Agent activity visualizations (real, not fake)
- [ ] Error states and empty states
- [ ] Mobile responsive layout
- [ ] README with setup instructions
- [ ] Video recording of demo flow

---

## Risks & Limitations

| Risk | Mitigation |
|------|------------|
| **API rate limits** | Polite pool emails, exponential backoff, request throttling |
| **Incomplete faculty identifiers** | System works without IDs; discovery uses name+affiliation |
| **Name ambiguity** | Human-in-the-loop for < 0.85 confidence; never guess |
| **Publication text parsing** | LLM-assisted extraction; preserve original text; flag uncertain |
| **Predatory journal data** | Use DOAJ + OpenAlex; never label without evidence |
| **Impact Factor accuracy** | Only from trusted sources; clearly label source; never fabricate |
| **Citation count variability** | Store source attribution; snapshot over time; show ranges |
| **LLM hallucination** | Deterministic tools for data operations; LLM only for reasoning |
| **PostgreSQL dependency** | Docker Compose for easy setup; SQLite fallback for dev possible |
| **Scalability (24 faculty)** | Architecture supports growth; batch processing; async operations |

## Hackathon-Winning Differentiators

| Differentiator | Description | Phase |
|---------------|-------------|-------|
| **Research Digital Twin** | Live institutional research graph | 12 |
| **Evidence Chain** | Traceable provenance for every record | 6 |
| **Confidence Scoring** | Transparent attribution reasoning | 6 |
| **Human-in-the-Loop** | AI assists, humans decide | 10 |
| **Research Anomaly Detection** | Predatory journals, velocity flags | 8 |
| **Affiliation Intelligence** | Self-learning affiliation variant matching | 2 |
| **Citation Timelines** | Historical metric snapshots, not just current | 9 |
| **Topic Intelligence** | Research area trends across institution | 12 |
| **NL Research Assistant** | "Show CSE publications in Q1 journals" | 15 |
| **Accreditation Builder** | One-click evidence package | 14 |
| **Conflict Visualization** | Side-by-side metadata comparison | 10 |
| **Agent Activity Center** | Real-time pipeline monitoring | 13 |
| **Collaboration Graph** | Faculty co-authorship networks | 12 |
| **Department Benchmarking** | Comparative research metrics | 13 |
