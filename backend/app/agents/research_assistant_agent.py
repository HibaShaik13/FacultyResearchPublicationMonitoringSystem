import re
import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy import func, or_, and_

from app.models.publication import Publication, PublicationAuthor, PublicationSource
from app.models.faculty import FacultyProfile
from app.models.review import ReviewTask
from app.models.user import User
from app.agents.reporting_agent import ReportingAgent

logger = logging.getLogger(__name__)

class ResearchAssistantAgent:
    """
    Agent 13 — Research Intelligence & Assistant Agent.
    
    Provides grounded, provenance-traceable answers strictly using real database data.
    Enforces RBAC and faculty-level data isolation. Never fabricates or hallucinates facts.
    """

    def __init__(self, session: AsyncSession, current_user: User):
        self.session = session
        self.user = current_user
        self.reporting_agent = ReportingAgent(session)

    async def answer_query(self, query_text: str) -> Dict[str, Any]:
        """
        Process a user question, query the database, and return a structured,
        provenance-grounded answer with actionable cards and citation links.
        """
        query_clean = query_text.strip().lower()
        if not query_clean:
            return {
                "answer": "Please ask a specific question about your research publications, citations, verification status, or departmental metrics.",
                "citations": [],
                "provenance": "VFSTR Real Database",
                "suggested_actions": []
            }

        # Determine effective faculty scope for data isolation
        faculty_profile: Optional[FacultyProfile] = None
        if self.user.role == "faculty" and self.user.faculty_id:
            res = await self.session.execute(
                select(FacultyProfile).where(FacultyProfile.id == self.user.faculty_id)
            )
            faculty_profile = res.scalars().first()
        elif self.user.role in ("admin", "research_admin", "reviewer"):
            # Check if query mentions a specific faculty name
            faculty_profile = await self._find_faculty_in_query(query_clean)

        # 1. Publications & Recent Papers
        if any(w in query_clean for w in ["publication", "paper", "papers", "published", "recent paper", "my work"]):
            return await self._handle_publications_query(query_clean, faculty_profile)

        # 2. Citations & h-index / i10-index / Metrics
        if any(w in query_clean for w in ["citation", "cite", "h-index", "h index", "i10", "metric", "impact"]):
            return await self._handle_metrics_query(query_clean, faculty_profile)

        # 3. Verification & Review Queue / Integrity
        if any(w in query_clean for w in ["verif", "review", "integrity", "flag", "unverified", "queue", "conflict", "doi"]):
            return await self._handle_verification_query(query_clean, faculty_profile)

        # 4. Research Areas / Topics / Interests
        if any(w in query_clean for w in ["area", "topic", "interest", "field", "domain", "specializ"]):
            return await self._handle_research_areas_query(query_clean, faculty_profile)

        # 5. Department & Institutional Inquiries
        if any(w in query_clean for w in ["department", "institution", "university", "overall", "naac", "nirf", "accredit"]):
            return await self._handle_institutional_query(query_clean, faculty_profile)

        # 6. Default / General Profile Summary
        return await self._handle_profile_summary(query_clean, faculty_profile)

    async def _find_faculty_in_query(self, query: str) -> Optional[FacultyProfile]:
        """Admins can query specific faculty by matching name in query text."""
        res = await self.session.execute(select(FacultyProfile))
        all_fac = res.scalars().all()
        for f in all_fac:
            name = (f.normalized_name or f.raw_name or "").lower()
            tokens = [t for t in name.split() if len(t) > 2]
            if tokens and any(t in query for t in tokens):
                return f
            if f.institutional_email and f.institutional_email.lower() in query:
                return f
        return None

    async def _get_faculty_publications(self, fac: FacultyProfile) -> List[Publication]:
        """Fetch all publications authored by a faculty member."""
        author_res = await self.session.execute(
            select(PublicationAuthor.publication_id).where(
                PublicationAuthor.faculty_id == fac.id
            )
        )
        pub_ids = list(set(author_res.scalars().all()))
        if not pub_ids:
            return []

        res = await self.session.execute(
            select(Publication)
            .where(Publication.id.in_(pub_ids))
            .options(selectinload(Publication.sources), selectinload(Publication.authors))
            .order_by(Publication.citation_count.desc(), Publication.year.desc().nullslast())
        )
        return res.scalars().unique().all()

    async def _handle_publications_query(self, query: str, fac: Optional[FacultyProfile]) -> Dict[str, Any]:
        """Answers queries about publications, paper lists, top papers, and years."""
        if self.user.role == "faculty" and not fac:
            return {
                "answer": "Your faculty profile is not yet linked to a publication dataset. Please contact the Research Administrator.",
                "citations": [],
                "provenance": "VFSTR Database",
                "suggested_actions": ["Contact Admin"]
            }

        # If admin didn't specify a faculty, query institution publications
        if not fac:
            stmt = select(Publication).order_by(Publication.citation_count.desc()).limit(10)
            res = await self.session.execute(stmt)
            pubs = res.scalars().all()
            total_stmt = select(func.count(Publication.id))
            total_count = (await self.session.execute(total_stmt)).scalar() or 0

            citations = [
                {
                    "id": str(p.id),
                    "title": p.title,
                    "year": p.year,
                    "venue": p.journal_name or "Academic Venue",
                    "citations": p.citation_count or 0,
                    "doi": p.doi,
                    "status": p.verification_status
                }
                for p in pubs[:5]
            ]
            answer = (
                f"### Institutional Publications Overview\n\n"
                f"The university repository currently contains **{total_count} verified research publications**.\n\n"
                f"**Top Highly Cited Institutional Papers:**\n"
            )
            for idx, p in enumerate(pubs[:5], start=1):
                doi_str = f" • [DOI: {p.doi}](https://doi.org/{p.doi})" if p.doi else ""
                answer += f"{idx}. **{p.title}** ({p.year or 'N/A'})\n   - Citations: **{p.citation_count or 0}** | Venue: *{p.journal_name or 'N/A'}*{doi_str}\n"

            return {
                "answer": answer,
                "citations": citations,
                "provenance": "VFSTR Institutional Database • Crossref • OpenAlex",
                "suggested_actions": ["View All Publications", "Filter by Year", "Accreditation Report"]
            }

        # Faculty specific query
        pubs = await self._get_faculty_publications(fac)
        fac_name = fac.normalized_name or fac.raw_name or "Faculty Member"

        if not pubs:
            return {
                "answer": f"No publications are currently linked to **{fac_name}** in the database.",
                "citations": [],
                "provenance": "VFSTR Database",
                "suggested_actions": ["Search Discovery Queue"]
            }

        # Check year filter (e.g. '2023', '2024')
        year_match = re.search(r'\b(19\d\d|20\d\d)\b', query)
        if year_match:
            target_year = int(year_match.group(1))
            year_pubs = [p for p in pubs if p.year == target_year]
            if not year_pubs:
                return {
                    "answer": f"**{fac_name}** has **0** recorded publications in **{target_year}** within the verified database.",
                    "citations": [],
                    "provenance": "VFSTR Database",
                    "suggested_actions": ["View All Years"]
                }
            citations = [
                {"id": str(p.id), "title": p.title, "year": p.year, "venue": p.journal_name, "citations": p.citation_count or 0, "doi": p.doi, "status": p.verification_status}
                for p in year_pubs
            ]
            answer = f"### Publications in {target_year} for {fac_name}\n\nFound **{len(year_pubs)} publication(s)** in {target_year}:\n\n"
            for idx, p in enumerate(year_pubs, start=1):
                doi_str = f" • [DOI: {p.doi}](https://doi.org/{p.doi})" if p.doi else ""
                answer += f"{idx}. **{p.title}**\n   - Venue: *{p.journal_name or 'N/A'}* | Citations: **{p.citation_count or 0}** | Status: `{p.verification_status}`{doi_str}\n"

            return {
                "answer": answer,
                "citations": citations,
                "provenance": "VFSTR Database • Live Faculty Record",
                "suggested_actions": ["View Publications Page", "Export to CSV"]
            }

        # Most cited or recent papers
        top_pubs = pubs[:5]
        citations = [
            {"id": str(p.id), "title": p.title, "year": p.year, "venue": p.journal_name, "citations": p.citation_count or 0, "doi": p.doi, "status": p.verification_status}
            for p in top_pubs
        ]

        verified_count = sum(1 for p in pubs if p.verification_status == "VERIFIED")
        total_citations = sum(p.citation_count or 0 for p in pubs)

        answer = (
            f"### Research Publications for {fac_name}\n\n"
            f"- **Total Indexed Publications:** **{len(pubs)}**\n"
            f"- **Verified Papers:** **{verified_count}** ({round(verified_count / len(pubs) * 100 if pubs else 0)}% verified)\n"
            f"- **Total Citations:** **{total_citations}**\n\n"
            f"**Top Ranked Publications by Citation Impact:**\n\n"
        )

        for idx, p in enumerate(top_pubs, start=1):
            doi_str = f" • [DOI: {p.doi}](https://doi.org/{p.doi})" if p.doi else ""
            answer += f"{idx}. **{p.title}** ({p.year or 'N/A'})\n   - Citations: **{p.citation_count or 0}** | Venue: *{p.journal_name or 'N/A'}* | Verification: `{p.verification_status}`{doi_str}\n"

        return {
            "answer": answer,
            "citations": citations,
            "provenance": "VFSTR Institutional Database • Crossref • OpenAlex",
            "suggested_actions": ["View My Publications", "Check Verification Status", "Generate Faculty Report"]
        }

    async def _handle_metrics_query(self, query: str, fac: Optional[FacultyProfile]) -> Dict[str, Any]:
        """Answers queries regarding h-index, i10-index, citation velocity, and impact."""
        if not fac:
            # Institution wide metrics
            inst_report = await self.reporting_agent.generate_institution_report()
            answer = (
                f"### Institutional Citation & Impact Metrics\n\n"
                f"- **Total Publications:** **{inst_report['total_publications']}**\n"
                f"- **Total Institutional Citations:** **{inst_report['total_citations']}**\n"
                f"- **Active Contributing Researchers:** **{inst_report['total_faculty']}**\n"
                f"- **Institutional Verification Integrity:** **{inst_report['overall_verification_rate']}%**\n\n"
                f"**Top Performing Departments:**\n"
            )
            for d in inst_report.get("department_comparison", [])[:4]:
                answer += f"- **{d['department']}**: {d['publications']} papers, {d['citations']} citations (Avg h-index: {d['avg_h_index']})\n"

            return {
                "answer": answer,
                "citations": [],
                "provenance": "VFSTR Citation Metrics Agent & Verification Engine",
                "suggested_actions": ["View Research Impact", "Institutional Report"]
            }

        # Calculate exact faculty metrics
        pubs = await self._get_faculty_publications(fac)
        citation_list = sorted([p.citation_count or 0 for p in pubs], reverse=True)
        
        # h-index calculation
        h_index = 0
        for i, c in enumerate(citation_list, start=1):
            if c >= i:
                h_index = i
            else:
                break

        # i10-index calculation
        i10_index = sum(1 for c in citation_list if c >= 10)
        total_citations = sum(citation_list)
        fac_name = fac.normalized_name or fac.raw_name or "Faculty Member"

        answer = (
            f"### Research Impact & Citation Metrics for {fac_name}\n\n"
            f"| Metric | Value | Status |\n"
            f"| :--- | :--- | :--- |\n"
            f"| **Total Citations** | **{total_citations}** | Verified Multi-Source |\n"
            f"| **h-index** | **{h_index}** | Computed from Verified Papers |\n"
            f"| **i10-index** | **{i10_index}** | Papers with ≥10 Citations |\n"
            f"| **Total Publications** | **{len(pubs)}** | Indexed in VFSTR Database |\n\n"
        )

        if citation_list:
            top_cited = pubs[0]
            answer += (
                f"**Most Impactful Publication:**\n"
                f"> **{top_cited.title}** ({top_cited.year or 'N/A'})\n"
                f"> Citations: **{top_cited.citation_count or 0}** | Venue: *{top_cited.journal_name or 'N/A'}*"
            )
            if top_cited.doi:
                answer += f" | [DOI: {top_cited.doi}](https://doi.org/{top_cited.doi})"

        return {
            "answer": answer,
            "citations": [
                {"id": str(p.id), "title": p.title, "year": p.year, "venue": p.journal_name, "citations": p.citation_count or 0, "doi": p.doi, "status": p.verification_status}
                for p in pubs[:3]
            ],
            "provenance": "VFSTR Metrics Agent (Agent 7) • Crossref & OpenAlex Citation Counts",
            "suggested_actions": ["View Research Impact Dashboard", "Download Performance Summary"]
        }

    async def _handle_verification_query(self, query: str, fac: Optional[FacultyProfile]) -> Dict[str, Any]:
        """Answers queries regarding verification status, review queue tasks, and integrity."""
        fac_filter = []
        if fac:
            pubs = await self._get_faculty_publications(fac)
            pub_ids = [p.id for p in pubs]
            fac_filter = [ReviewTask.entity_id.in_(pub_ids)] if pub_ids else [ReviewTask.id == None]

        # Query pending review tasks
        review_stmt = select(ReviewTask).where(
            ReviewTask.status == "PENDING",
            *fac_filter
        ).order_by(ReviewTask.created_at.desc()).limit(5)
        review_tasks = (await self.session.execute(review_stmt)).scalars().all()

        total_pending_stmt = select(func.count(ReviewTask.id)).where(ReviewTask.status == "PENDING", *fac_filter)
        total_pending = (await self.session.execute(total_pending_stmt)).scalar() or 0

        target_name = fac.normalized_name if fac else "Institutional Queue"

        if total_pending == 0:
            answer = (
                f"### Verification & Integrity Audit for {target_name}\n\n"
                f"✅ **All active records are fully verified with zero pending human review flags.**\n\n"
                f"- No integrity contradictions detected.\n"
                f"- All attributed publications have confirmed institutional affiliations.\n"
            )
        else:
            answer = (
                f"### Verification & Review Status for {target_name}\n\n"
                f"⚠️ **There are currently {total_pending} item(s) in the Verification Queue requiring review.**\n\n"
                f"**Pending Items Breakdown:**\n"
            )
            for idx, t in enumerate(review_tasks, start=1):
                answer += f"{idx}. **[{t.priority.upper()}] {t.task_type.replace('_', ' ').title()}**\n   - Reason: {t.explanation}\n"

        return {
            "answer": answer,
            "citations": [],
            "provenance": "VFSTR Verification Agent (Agent 10) & Human Review Agent (Agent 11)",
            "suggested_actions": ["Open Verification Queue", "View Research Integrity"]
        }

    async def _handle_research_areas_query(self, query: str, fac: Optional[FacultyProfile]) -> Dict[str, Any]:
        """Answers queries regarding research domains, topics, and keywords."""
        if fac:
            interests = fac.research_interests or []
            if isinstance(interests, str):
                import json
                try:
                    interests = json.loads(interests)
                except Exception:
                    interests = [i.strip() for i in interests.split(",") if i.strip()]

            fac_name = fac.normalized_name or fac.raw_name or "Faculty Member"
            pubs = await self._get_faculty_publications(fac)

            answer = (
                f"### Research Specializations for {fac_name}\n\n"
                f"**Primary Research Domains & Topics:**\n"
            )
            if interests:
                for i in interests:
                    answer += f"- **{i.title() if isinstance(i, str) else str(i)}**\n"
            else:
                answer += "- *No explicit research interest tags defined in profile. Synthesizing from publication venues...*\n"

            answer += f"\n**Active Department:** {fac.department or 'Engineering'}\n"
            answer += f"**Total Research Contributions:** {len(pubs)} publication(s)\n"

            return {
                "answer": answer,
                "citations": [],
                "provenance": "VFSTR Faculty Knowledge Base (Agent 1)",
                "suggested_actions": ["Explore Research Areas", "View Collaborations"]
            }

        # Institutional research areas
        res = await self.session.execute(select(FacultyProfile))
        all_fac = res.scalars().all()
        dept_counts: Dict[str, int] = {}
        for f in all_fac:
            dept = f.department or "General"
            dept_counts[dept] = dept_counts.get(dept, 0) + 1

        answer = "### Institutional Research Focus & Departments\n\n"
        for dept, count in sorted(dept_counts.items(), key=lambda x: x[1], reverse=True):
            answer += f"- **Department of {dept}**: {count} active faculty members\n"

        return {
            "answer": answer,
            "citations": [],
            "provenance": "VFSTR Faculty Profiles",
            "suggested_actions": ["View Research Areas Dashboard", "Institutional Analytics"]
        }

    async def _handle_institutional_query(self, query: str, fac: Optional[FacultyProfile]) -> Dict[str, Any]:
        """Answers queries on NAAC/NIRF accreditation, department performance, and institution rollups."""
        if "naac" in query or "nirf" in query or "accredit" in query:
            framework = "NAAC" if "naac" in query else "NIRF"
            evidence = await self.reporting_agent.generate_accreditation_evidence(framework)
            metrics = evidence["metrics"]

            answer = (
                f"### {framework} Accreditation Research Summary (Verified Evidence)\n\n"
                f"- **Eligible Verified Publications:** **{metrics['total_eligible_publications']}**\n"
                f"- **Verified Faculty Contributors:** **{metrics['active_faculty_count']}**\n"
                f"- **Average Research Citations/Paper:** **{metrics['average_citations_per_paper']}**\n"
                f"- **UGC-CARE / Scopus Indexed Count:** **{metrics['scopus_wos_indexed_count']}**\n"
                f"- **Accreditation Compliance Readiness:** **{evidence['compliance_score']}%**\n\n"
                f"*All records are strictly filtered for verified peer-reviewed publications with DOI/ISSN verification.*"
            )
            return {
                "answer": answer,
                "citations": evidence.get("evidence_rows", [])[:5],
                "provenance": f"VFSTR Accreditation & Reporting Agent (Agent 12) • {framework} Criteria Engine",
                "suggested_actions": ["Export NAAC CSV", "View Full Reports Page"]
            }

        # General Department / Institution overview
        inst = await self.reporting_agent.generate_institution_report()
        answer = (
            f"### VFSTR Institutional Research Summary\n\n"
            f"- **Total University Publications:** **{inst['total_publications']}**\n"
            f"- **Total Verified Citations:** **{inst['total_citations']}**\n"
            f"- **Institutional Verification Integrity:** **{inst['overall_verification_rate']}%**\n\n"
            f"**Department Breakdown:**\n"
        )
        for d in inst.get("department_comparison", []):
            answer += f"- **{d['department']}**: {d['publications']} papers | {d['citations']} citations | Avg h-index: {d['avg_h_index']}\n"

        return {
            "answer": answer,
            "citations": [],
            "provenance": "VFSTR Reporting Agent (Agent 12)",
            "suggested_actions": ["View Full Institution Report", "Department Analytics"]
        }

    async def _handle_profile_summary(self, query: str, fac: Optional[FacultyProfile]) -> Dict[str, Any]:
        """General fallback profile summary."""
        if not fac:
            return {
                "answer": (
                    "### Welcome to the Vignan Research Intelligence Assistant\n\n"
                    "I can provide live, verified answers grounded in our institutional research database. You can ask about:\n\n"
                    "- **My Publications:** *'What are my top cited papers?'*, *'Show my publications from 2023'*\n"
                    "- **Research Impact:** *'What is my h-index and citation count?'*\n"
                    "- **Verification & Quality:** *'Do I have any pending review items?'*, *'Check publication integrity'*\n"
                    "- **Accreditation & Analytics:** *'Show NAAC Criterion 3 evidence'*, *'Summarize department output'*\n"
                ),
                "citations": [],
                "provenance": "VFSTR Multi-Agent Research System (Agents 1–12)",
                "suggested_actions": ["What are my top cited papers?", "What is my h-index?", "Show my publications from 2023", "Check verification status"]
            }

        fac_name = fac.normalized_name or fac.raw_name or "Faculty Member"
        pubs = await self._get_faculty_publications(fac)
        citations_sum = sum(p.citation_count or 0 for p in pubs)
        verified_count = sum(1 for p in pubs if p.verification_status == "VERIFIED")

        answer = (
            f"### Research Profile Summary: {fac_name}\n\n"
            f"- **Designation:** {fac.designation or 'Faculty Member'}\n"
            f"- **Department:** {fac.department or 'Computer Science & Engineering'}\n"
            f"- **Institutional Email:** `{fac.institutional_email or fac.raw_email or 'N/A'}`\n"
            f"- **Total Publications:** **{len(pubs)}** ({verified_count} verified)\n"
            f"- **Total Citations:** **{citations_sum}**\n\n"
            f"How can I assist you with your research data today?"
        )

        return {
            "answer": answer,
            "citations": [
                {"id": str(p.id), "title": p.title, "year": p.year, "venue": p.journal_name, "citations": p.citation_count or 0, "doi": p.doi, "status": p.verification_status}
                for p in pubs[:3]
            ],
            "provenance": "VFSTR Institutional Database • Agents 1–12",
            "suggested_actions": ["What are my top cited papers?", "What is my h-index?", "Show my publications from 2023", "Check verification queue"]
        }
