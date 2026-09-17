import asyncio
import json
import uuid
from sqlalchemy import select, func, text, and_, or_
from app.database import async_session_factory
from app.models.faculty import FacultyProfile
from app.models.publication import Publication, PublicationAuthor
from app.models.review import ReviewTask
from app.models.metrics import FacultyMetricSnapshot
from app.api.v1.analytics import dashboard_stats, publication_trends

SIVA_ID = uuid.UUID('e7399ee0-758c-453b-8a96-329e3dc2cc96')

async def main():
    results = {}
    async with async_session_factory() as session:
        # ----------------------------------------------------
        # CHECK 1: 89 Verified Records
        # ----------------------------------------------------
        pubs_q = await session.execute(
            select(
                Publication.id,
                Publication.title,
                Publication.verification_status,
                Publication.risk_level,
                Publication.citation_count
            )
            .join(Publication.authors)
            .where(PublicationAuthor.faculty_id == SIVA_ID)
        )
        pubs = pubs_q.all()
        status_map = {}
        for p in pubs:
            status_map[p.verification_status] = status_map.get(p.verification_status, 0) + 1
        
        non_verified = [
            {"id": str(p.id), "title": p.title, "status": p.verification_status, "citations": p.citation_count}
            for p in pubs if p.verification_status != "verified"
        ]

        # Check latest snapshot verified_publications
        snap = (await session.execute(
            select(FacultyMetricSnapshot)
            .where(FacultyMetricSnapshot.faculty_id == SIVA_ID)
            .order_by(FacultyMetricSnapshot.snapshot_date.desc())
            .limit(1)
        )).scalars().first()

        results["check1_verified_records"] = {
            "total_attributed_publications": len(pubs),
            "status_breakdown": status_map,
            "verified_count": status_map.get("verified", 0),
            "needs_review_count": status_map.get("needs_review", 0),
            "snapshot_verified_publications": snap.verified_publications if snap else None,
            "non_verified_publications": non_verified
        }

        # ----------------------------------------------------
        # CHECK 2: ReviewTask 84 Isolation & Dehtaj Shaik
        # ----------------------------------------------------
        tasks_q = await session.execute(
            select(ReviewTask)
            .where(
                or_(ReviewTask.related_entity_id == SIVA_ID, ReviewTask.entity_id == SIVA_ID),
                ReviewTask.status == 'pending'
            )
        )
        tasks = tasks_q.scalars().all()
        
        all_84_valid = True
        task_details = []
        dehtaj_tasks = []

        for t in tasks:
            is_siva_candidate = (t.related_entity_id == SIVA_ID)
            if not is_siva_candidate:
                all_84_valid = False
            
            # Find linked authors for this task's publication
            pas = (await session.execute(
                select(PublicationAuthor).where(PublicationAuthor.publication_id == t.entity_id)
            )).scalars().all()
            
            linked_fac = []
            for pa in pas:
                f = (await session.execute(select(FacultyProfile).where(FacultyProfile.id == pa.faculty_id))).scalars().first()
                if f:
                    linked_fac.append({"faculty_id": str(f.id), "name": f.raw_name, "dept": f.department})
                    if "Shaik" in f.raw_name or "Dehtaj" in f.raw_name:
                        pub = (await session.execute(select(Publication).where(Publication.id == t.entity_id))).scalars().first()
                        dehtaj_tasks.append({
                            "task_id": str(t.id),
                            "task_type": t.task_type,
                            "entity_id": str(t.entity_id),
                            "related_entity_id": str(t.related_entity_id),
                            "explanation": t.explanation,
                            "evidence": t.evidence,
                            "publication_title": pub.title if pub else None,
                            "linked_faculty": f.raw_name
                        })

        results["check2_queue_isolation"] = {
            "total_pending_tasks": len(tasks),
            "all_tasks_related_to_siva": all_84_valid,
            "dehtaj_linked_tasks": dehtaj_tasks
        }

        # ----------------------------------------------------
        # CHECK 3: Research Focus Areas
        # ----------------------------------------------------
        fac = (await session.execute(select(FacultyProfile).where(FacultyProfile.id == SIVA_ID))).scalars().first()
        results["check3_research_focus"] = {
            "faculty_research_interests": fac.research_interests if fac else None,
            "interests_count": len(fac.research_interests) if fac and fac.research_interests else 0
        }

        # ----------------------------------------------------
        # CHECK 4: Scholarly Output & Yearly Trend (2021 Spike)
        # ----------------------------------------------------
        yearly_pubs = await session.execute(
            select(
                Publication.year,
                func.count(Publication.id).label("pub_count"),
                func.sum(Publication.citation_count).label("cit_count")
            )
            .join(Publication.authors)
            .where(PublicationAuthor.faculty_id == SIVA_ID)
            .group_by(Publication.year)
            .order_by(Publication.year)
        )
        yearly_breakdown = [
            {"year": r.year, "publications": r.pub_count, "citations": r.cit_count}
            for r in yearly_pubs.all()
        ]

        # Also find top cited publications for Siva to explain 2021 spike
        top_pubs = (await session.execute(
            select(Publication.title, Publication.year, Publication.citation_count, Publication.journal_name, Publication.doi)
            .join(Publication.authors)
            .where(PublicationAuthor.faculty_id == SIVA_ID)
            .order_by(Publication.citation_count.desc())
            .limit(10)
        )).all()
        top_pubs_list = [
            {"title": tp.title, "year": tp.year, "citations": tp.citation_count, "journal": tp.journal_name, "doi": tp.doi}
            for tp in top_pubs
        ]

        results["check4_scholarly_output"] = {
            "yearly_breakdown": yearly_breakdown,
            "top_cited_publications": top_pubs_list
        }

        # ----------------------------------------------------
        # CHECK 5: Metric Consistency Across Tables & APIs
        # ----------------------------------------------------
        # Direct DB
        direct_pubs = (await session.execute(
            select(func.count(Publication.id))
            .join(Publication.authors)
            .where(PublicationAuthor.faculty_id == SIVA_ID)
        )).scalar()
        direct_cits = (await session.execute(
            select(func.sum(Publication.citation_count))
            .join(Publication.authors)
            .where(PublicationAuthor.faculty_id == SIVA_ID)
        )).scalar()

        # Citations list for h-index & i10
        cits = [c for c, in (await session.execute(
            select(Publication.citation_count)
            .join(Publication.authors)
            .where(PublicationAuthor.faculty_id == SIVA_ID)
            .order_by(Publication.citation_count.desc())
        )).all()]
        h_index = sum(1 for i, c in enumerate(cits) if c >= i + 1)
        i10_index = sum(1 for c in cits if c >= 10)

        # Snapshot
        snap_metrics = {
            "publications": snap.total_publications if snap else None,
            "citations": snap.total_citations if snap else None,
            "h_index": snap.h_index if snap else None,
            "i10_index": snap.i10_index if snap else None
        }

        results["check5_metric_consistency"] = {
            "direct_db": {
                "publications": direct_pubs,
                "citations": direct_cits,
                "h_index": h_index,
                "i10_index": i10_index
            },
            "snapshot": snap_metrics
        }

        # ----------------------------------------------------
        # CHECK 6: Zero/Missing Citation Count Sample
        # ----------------------------------------------------
        zero_pubs = (await session.execute(
            select(Publication.title, Publication.doi, Publication.citation_count, Publication.citation_source)
            .join(Publication.authors)
            .where(PublicationAuthor.faculty_id == SIVA_ID, Publication.citation_count == 0)
            .limit(10)
        )).all()

        results["check6_zero_citations"] = [
            {"title": p.title, "doi": p.doi, "citation_count": p.citation_count, "citation_source": p.citation_source}
            for p in zero_pubs
        ]

    with open("readonly_audit_dump.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print("AUDIT_DUMP_COMPLETE")

if __name__ == "__main__":
    asyncio.run(main())
